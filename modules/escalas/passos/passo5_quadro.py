import streamlit as st
import datetime
import calendar
import pandas as pd
import copy
import re
import json

from core.database import (
    salvar_escala_mensal_supabase,
    supabase,
    carregar_militares_supabase,
)

from modules.escalas.passos.passo3_efetivo import (
    PESOS_HIERARQUIA,
    padronizar_graduacao,
)

from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS

SIGLAS_DIAS_NEUTROS = {
    "F", "D", "X", "FER", "DOM", "FERIADO", "LM", "ATE", "FE", "LUT", "NUP", "DN", "DNT"
}

# ============================================================
# UTILITÁRIOS E SANITIZAÇÃO
# ============================================================

def _valor_vazio(valor):
    if valor is None:
        return True
    try:
        return bool(pd.isna(valor))
    except Exception:
        return False

def _sanitizar_widget_key(valor):
    valor = str(valor or "geral")
    valor = re.sub(r"[^a-zA-Z0-9_-]+", "_", valor)
    return valor[:80] or "geral"

def _normalizar_matriz_banco(matriz):
    if matriz is None:
        return {}
    if isinstance(matriz, dict):
        return matriz
    if isinstance(matriz, str):
        try:
            resultado = json.loads(matriz)
            if isinstance(resultado, dict):
                return resultado
        except Exception:
            pass
    return {}

def _ordem_registro_banco(registro):
    for campo in ("updated_at", "created_at"):
        valor = registro.get(campo)
        if valor:
            try:
                dt = pd.to_datetime(valor, utc=True, errors="coerce")
                if not pd.isna(dt):
                    return (3, dt.timestamp())
            except Exception:
                pass
    valor_id = registro.get("id")
    if valor_id is not None:
        try:
            return (2, float(valor_id))
        except Exception:
            return (2, str(valor_id))
    return (1, 0)

# ============================================================
# BANCO DE DADOS (SUPABASE)
# ============================================================

def carregar_escala_monitor_banco(m_ano, m_mes):
    if supabase is None:
        return {}
    try:
        resposta = (
            supabase
            .table("escalas_mensais")
            .select("*")
            .eq("ano", int(m_ano))
            .eq("mes", int(m_mes))
            .execute()
        )
        registros = getattr(resposta, "data", None) or []
        if not registros:
            return {}
        registro_mais_recente = max(registros, key=_ordem_registro_banco)
        matriz = registro_mais_recente.get("matriz_dados", {})
        return _normalizar_matriz_banco(matriz)
    except Exception as e:
        print("Erro ao carregar monitor:", e)
        return {}

def carregar_escala_salva_banco():
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    md = carregar_escala_monitor_banco(m_ano, m_mes)

    if not md:
        st.session_state["grade_escala_lancamentos"] = {}
        st.session_state["militares_no_quadro_chaves"] = []
        st.session_state["ordem_customizada_map"] = {}
        st.session_state["bh_configs"] = {}
        st.session_state["ajuste_saldo_map"] = {}
        st.session_state["dias_selecionados_passo4"] = []
        st.session_state["chave_escala_carregada"] = None
        return False

    st.session_state["grade_escala_lancamentos"] = copy.deepcopy(md.get("grade_escala_lancamentos", {}))
    
    chaves_raw = md.get("militares_no_quadro_chaves", [])
    st.session_state["militares_no_quadro_chaves"] = [(str(p[0]), str(p[1])) for p in chaves_raw if isinstance(p, (tuple, list)) and len(p) == 2]
    
    st.session_state["ordem_customizada_map"] = copy.deepcopy(md.get("ordem_customizada_map", {}))
    st.session_state["bh_configs"] = copy.deepcopy(md.get("bh_configs", {}))
    st.session_state["ajuste_saldo_map"] = copy.deepcopy(md.get("ajuste_saldo_map", {}))
    st.session_state["dias_selecionados_passo4"] = copy.deepcopy(md.get("dias_selecionados_passo4", []))
    st.session_state["chave_escala_carregada"] = f"{m_ano}_{m_mes}"
    return True

def executar_auto_save_banco():
    try:
        m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
        m_mes = st.session_state.get("mes_escala", datetime.date.today().month)

        chaves_norm = [(str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", []) if isinstance(p, (tuple, list)) and len(p) == 2]

        matriz_dados = {
            "grade_escala_lancamentos": copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {})),
            "militares_no_quadro_chaves": chaves_norm,
            "ordem_customizada_map": copy.deepcopy(st.session_state.get("ordem_customizada_map", {})),
            "bh_configs": copy.deepcopy(st.session_state.get("bh_configs", {})),
            "ajuste_saldo_map": copy.deepcopy(st.session_state.get("ajuste_saldo_map", {})),
            "dias_selecionados_passo4": copy.deepcopy(st.session_state.get("dias_selecionados_passo4", [])),
        }

        salvar_escala_mensal_supabase(
            ano=m_ano,
            mes=m_mes,
            equipe_nome=st.session_state.get("equipe_ativa", "GERAL"),
            modalidade=st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso"),
            matriz_dados=matriz_dados,
            elaborado_por="GESTOR",
            homologado_por="GESTOR",
            status="RASCUNHO"
        )
        st.session_state["ultima_gravacao"] = datetime.datetime.now()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar escala: {e}")
        return False

# ============================================================
# REGRAS E AUDITORIA
# ============================================================

def padronizar_entrada_quadro(valor):
    if _valor_vazio(valor):
        return "F"
    valor = str(valor).strip()
    if not valor:
        return "F"
    valor_upper = valor.upper()
    if valor_upper in {"F", "FOLGA"}:
        return "F"
    if valor_upper in {"D", "DOM", "DOMINGO"}:
        return "D"
    if valor_upper in {"X", "FER", "FERIADO"}:
        return "X"
    return valor

def extrair_datetime_de_string_turno(valor, data_base):
    if not valor:
        return None, None
    texto = str(valor).strip()
    if not texto:
        return None, None
    numeros = re.findall(r"\d{1,2}:\d{2}", texto)
    if len(numeros) < 2:
        return None, None
    try:
        primeiro, ultimo = numeros[0].split(":"), numeros[-1].split(":")
        inicio = datetime.datetime.combine(data_base, datetime.time(int(primeiro[0]), int(primeiro[1])))
        fim = datetime.datetime.combine(data_base, datetime.time(int(ultimo[0]), int(ultimo[1])))
        if fim <= inicio:
            fim += datetime.timedelta(days=1)
        return inicio, fim
    except Exception:
        return None, None

def auditar_escalacao_militar(militar_id, equipe, data, novo_valor):
    resultado = {"status": "OK", "mensagem": ""}
    novo_valor = padronizar_entrada_quadro(novo_valor)

    if novo_valor in SIGLAS_DIAS_NEUTROS:
        return resultado

    grade = st.session_state.get("grade_escala_lancamentos", {})
    inicio_novo, fim_novo = extrair_datetime_de_string_turno(novo_valor, data)

    if inicio_novo is None:
        return resultado

    # 1. EMPENHO MÍNIMO RECOMENDADO (< 6.0 Horas)
    if inicio_novo and fim_novo:
        duracao_empenho = (fim_novo - inicio_novo).total_seconds() / 3600.0
        if 0 < duracao_empenho < 6.0:
            resultado["status"] = "AVISO"
            resultado["mensagem"] = f"Empenho reduzido de {duracao_empenho:.1f}h (recomendado mínimo de 6.0h)."
            return resultado

    avisos = []
    prefixo = f"{militar_id}_"

    for chave, valor in grade.items():
        if not str(chave).startswith(prefixo):
            continue
        partes = str(chave).rsplit("_", 3)
        if len(partes) < 4:
            continue
        try:
            data_existente = datetime.date(int(partes[-3]), int(partes[-2]), int(partes[-1]))
        except Exception:
            continue

        if data_existente != data:
            continue

        valor_existente = padronizar_entrada_quadro(valor)
        if valor_existente in SIGLAS_DIAS_NEUTROS:
            continue

        inicio_existente, fim_existente = extrair_datetime_de_string_turno(valor_existente, data_existente)
        if inicio_existente is None or fim_existente is None:
            continue

        if inicio_novo < fim_existente and fim_novo > inicio_existente:
            avisos.append("Existe sobreposição de horários para este militar.")

    # 2. DESCANSO INTERJORNADA (< 8.0 Horas)
    for chave, valor in grade.items():
        if not str(chave).startswith(prefixo):
            continue
        partes = str(chave).rsplit("_", 3)
        if len(partes) < 4:
            continue
        try:
            data_existente = datetime.date(int(partes[-3]), int(partes[-2]), int(partes[-1]))
        except Exception:
            continue

        diferenca = (data_existente - data).days
        if abs(diferenca) > 2:
            continue

        valor_existente = padronizar_entrada_quadro(valor)
        if valor_existente in SIGLAS_DIAS_NEUTROS:
            continue

        inicio_existente, fim_existente = extrair_datetime_de_string_turno(valor_existente, data_existente)
        if inicio_existente is None or fim_existente is None:
            continue

        descanso = (inicio_existente - fim_novo).total_seconds() / 3600.0 if data_existente > data else (inicio_novo - fim_existente).total_seconds() / 3600.0
        if 0 <= descanso < 8.0:
            avisos.append(f"Intervalo de descanso interjornada reduzido ({descanso:.1f}h).")

    if avisos:
        resultado["status"] = "AVISO"
        resultado["mensagem"] = " ".join(dict.fromkeys(avisos))

    return resultado

# ============================================================
# MODALIDADE STANDALONE / MONITOR SECUNDÁRIO (SEGUNDA TELA)
# ============================================================

def construir_dados_monitor(matriz, m_ano, m_mes):
    grade = matriz.get("grade_escala_lancamentos", {})
    chaves = matriz.get("militares_no_quadro_chaves", [])
    ordem_map = matriz.get("ordem_customizada_map", {})

    militares = st.session_state.get("lista_militares", []) or carregar_militares_supabase() or []
    if not militares:
        return None

    mapa_militares = {str(m.get("id") or m.get("chave") or m.get("num_policia")): m for m in militares if m}
    
    mils_linhas = []
    for pair in chaves:
        if isinstance(pair, (tuple, list)) and len(pair) == 2:
            m_obj = mapa_militares.get(str(pair[0]))
            if m_obj:
                mils_linhas.append({
                    "id": str(pair[0]),
                    "equipe": str(pair[1]),
                    "posto_grad": m_obj.get("posto_grad", "SD"),
                    "nome_guerra": m_obj.get("nome_guerra", "MILITAR"),
                    "num_policia": m_obj.get("num_policia", ""),
                    "chave_linha": f"{pair[0]}_{pair[1]}"
                })

    if not mils_linhas:
        return None

    mils_ord = sorted(mils_linhas, key=lambda x: (ordem_map.get(x["chave_linha"], 99), PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99), x["nome_guerra"]))
    ultimo_dia = calendar.monthrange(int(m_ano), int(m_mes))[1]
    datas = [datetime.date(int(m_ano), int(m_mes), dia) for dia in range(1, ultimo_dia + 1)]

    cabecalho = ["EQUIPE", "MILITAR"] + [f"{data.day:02d}<br>{DIAS_SEMANA_SIGLAS[data.weekday()]}" for data in datas]

    linhas_html = []
    for item in mils_ord:
        m_id, eq, pg, ng, np = item["id"], item["equipe"], padronizar_graduacao(item["posto_grad"]), item["nome_guerra"], item["num_policia"]
        
        html_linha = f"<tr><td><b>{eq}</b></td><td class='militar'>{pg} {ng}</td>"
        for data in datas:
            chave = f"{m_id}_{eq}_{data.year}_{data.month:02d}_{data.day:02d}"
            valor = padronizar_entrada_quadro(grade.get(chave, "F"))

            valor_str = str(valor)
            valor_html = valor_str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            classe = "normal"
            if valor_str.upper() == "F": classe = "folga"
            elif valor_str.upper() == "D": classe = "domingo"
            elif valor_str.upper() == "X": classe = "feriado"

            html_linha += f"<td class='{classe}'>{valor_html}</td>"

        html_linha += "</tr>"
        linhas_html.append(html_linha)

    return f"""
    <div class="quadro-scroll">
        <table class="quadro-monitor">
            <thead><tr>{"".join(f"<th>{c}</th>" for c in cabecalho)}</tr></thead>
            <tbody>{"".join(linhas_html)}</tbody>
        </table>
    </div>
    """

@st.fragment(run_every=2)
def monitor_automatico(m_ano, m_mes):
    matriz = carregar_escala_monitor_banco(m_ano, m_mes)
    if not matriz:
        st.info(f"💡 Nenhuma escala aplicada ou salva no banco para {m_mes:02d}/{m_ano}.")
        return

    tabela = construir_dados_monitor(matriz, m_ano, m_mes)
    if tabela is None:
        st.info("💡 Clique em '⚡ Aplicar Lançamentos e Atualizar Quadro' na tela principal para exibir os militares.")
        return

    st.markdown(tabela, unsafe_allow_html=True)
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(f'<div class="status-monitor">🟢 Sincronizado com o banco — última consulta: {agora}</div>', unsafe_allow_html=True)

def renderizar_modo_segunda_tela():
    params = st.query_params
    try:
        m_ano = int(params.get("ano", st.session_state.get("ano_escala", datetime.date.today().year)))
    except Exception:
        m_ano = datetime.date.today().year

    try:
        m_mes = int(params.get("mes", st.session_state.get("mes_escala", datetime.date.today().month)))
    except Exception:
        m_mes = datetime.date.today().month

    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        header { visibility: hidden; height: 0; }
        .block-container { padding: 0.8rem !important; max-width: 100% !important; }
        .quadro-scroll { width: 100%; overflow: auto; max-height: calc(100vh - 145px); border: 1px solid #b8b8b8; }
        .quadro-monitor { border-collapse: collapse; width: max-content; min-width: 100%; font-family: Arial, sans-serif; font-size: 12px; }
        .quadro-monitor th, .quadro-monitor td { border: 1px solid #a9a9a9; padding: 4px 5px; text-align: center; white-space: nowrap; height: 29px; }
        .quadro-monitor th { position: sticky; top: 0; z-index: 5; font-weight: bold; background: #e9ecef; }
        .quadro-monitor th:first-child { left: 0; z-index: 7; min-width: 100px; text-align: center; }
        .quadro-monitor td:first-child + td { position: sticky; left: 100px; z-index: 3; min-width: 200px; text-align: left; font-weight: 600; background: white; }
        .quadro-monitor td.folga { background: #dff0d8; font-weight: bold; }
        .quadro-monitor td.domingo { background: #eeeeee; font-weight: bold; }
        .quadro-monitor td.feriado { background: #fff2cc; font-weight: bold; }
        .titulo-monitor { font-size: 22px; font-weight: 700; }
        .subtitulo-monitor { font-size: 13px; color: #555; margin-bottom: 8px; }
        .status-monitor { margin-top: 5px; font-size: 11px; color: #555; }
        </style>
    """, unsafe_allow_html=True)

    lista_meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    nome_mes = lista_meses[int(m_mes) - 1]
    st.markdown(f'<div class="titulo-monitor">🖥️ QUADRO GERAL (MONITOR STANDALONE)</div><div class="subtitulo-monitor">{nome_mes.upper()} / {m_ano}</div>', unsafe_allow_html=True)

    monitor_automatico(m_ano, m_mes)

# ============================================================
# PASSO 5 - PAINEL PRINCIPAL
# ============================================================

def renderizar_passo5():
    # Roteamento se aberto como Segunda Tela na URL
    params = st.query_params
    if str(params.get("modo_monitor", "")).lower() == "segunda_tela":
        renderizar_modo_segunda_tela()
        return

    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)

    chave_periodo = f"{m_ano}_{m_mes:02d}"
    if st.session_state.get("chave_escala_carregada") != chave_periodo:
        carregar_escala_salva_banco()
        st.session_state["chave_escala_carregada"] = chave_periodo

    # LÓGICA DE APLICAÇÃO: SÓ ATUALIZA E MONTA AS CHAVES QUANDO O BOTAO APLICAR FOR CLICADO
    if st.session_state.get("atualizar_quadro_passo5", False):
        sel_ids = set(str(mid) for mid in st.session_state.get("militares_selecionados_ids", []))
        eq_ativa = str(st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))
        
        st.session_state["militares_no_quadro_chaves"] = [
            (str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", []) 
            if isinstance(p, (tuple, list)) and len(p) == 2 and (str(p[1]) != eq_ativa or str(p[0]) in sel_ids)
        ] + [(mid, eq_ativa) for mid in sel_ids if (mid, eq_ativa) not in set((str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", []) if isinstance(p, (tuple, list)) and len(p) == 2)]
        
        executar_auto_save_banco()
        st.session_state["atualizar_quadro_passo5"] = False

    militares = st.session_state.get("lista_militares") or carregar_militares_supabase() or []
    st.session_state["lista_militares"] = militares

    with st.expander("📌 PASSO 5: Quadro Mensal de Escalas e Carga Horária", expanded=True):
        c1, c2, c3 = st.columns([2.5, 2.5, 1.5])
        
        with c1:
            st.caption(f"👮‍♂️ **Linhas Ativas:** `{len(st.session_state.get('militares_no_quadro_chaves', []))}` | 💡 *Legenda `X` = serviço em outra equipe.*")
        
        with c2:
            if st.button("⚡ Aplicar Lançamentos e Atualizar Quadro", type="primary", use_container_width=True):
                st.session_state["atualizar_quadro_passo5"] = True
                executar_auto_save_banco()
                st.success("✅ Quadro atualizado e sincronizado!")
                st.rerun()

        with c3:
            monitor_url = f"?modo_monitor=segunda_tela&ano={m_ano}&mes={m_mes}"
            st.markdown(
                f"""
                <a href="{monitor_url}" target="_blank" style="text-decoration:none;">
                    <button style="width:100%; padding:8px; border-radius:6px; background:#f0f2f6; border:1px solid #d3d3d3; font-weight:600; cursor:pointer;">
                        🖥️ Abrir Segunda Tela
                    </button>
                </a>
                """,
                unsafe_allow_html=True
            )

        st.divider()

        num_dias = calendar.monthrange(m_ano, m_mes)[1]
        chaves_existentes = st.session_state.get("militares_no_quadro_chaves", [])
        mils_linhas = [{"id": str(p[0]), "equipe": str(p[1]), "posto_grad": m.get("posto_grad", "SD"), "nome_guerra": m.get("nome_guerra", "MILITAR"), "num_policia": m.get("num_policia", ""), "chave_linha": f"{p[0]}_{p[1]}"} for p in chaves_existentes if isinstance(p, (tuple, list)) and len(p) == 2 for m in [next((x for x in militares if str(x.get("id")) == str(p[0])), {})] if m]

        st.session_state.setdefault("ordem_customizada_map", {})
        for idx, item in enumerate(mils_linhas): st.session_state["ordem_customizada_map"].setdefault(item["chave_linha"], idx + 1)
        mils_ord = sorted(mils_linhas, key=lambda x: (st.session_state["ordem_customizada_map"].get(x["chave_linha"], 99), PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99), x["nome_guerra"]))

        colunas_dias = [(d, f"{'🔴 ' if calendar.weekday(m_ano, m_mes, d) in [5,6] else ''}{d:02d} {DIAS_SEMANA_SIGLAS[calendar.weekday(m_ano, m_mes, d)]}") for d in range(1, num_dias + 1)]
        matriz = []
        grade = st.session_state.get("grade_escala_lancamentos", {})

        for idx_r, item in enumerate(mils_ord):
            m_id, eq, pg, ng, np = item["id"], item["equipe"], padronizar_graduacao(item["posto_grad"]), item["nome_guerra"], item["num_policia"]
            linha = {"ORDEM": int(st.session_state["ordem_customizada_map"].get(item["chave_linha"], idx_r + 1)), "EQUIPE": eq, "Nº POLÍCIA": np, "MILITAR": f"{pg} {ng}"}
            tot_h, neutros = 0.0, 0

            for d, col_name in colunas_dias:
                v = padronizar_entrada_quadro(grade.get(f"{m_id}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "F"))
                linha[col_name] = v
                v_str = str(v).upper().strip()
                if any(sig in set(v_str.replace("/", " ").split()) for sig in SIGLAS_DIAS_NEUTROS): neutros += 1
                elif v_str not in ["", "F", "D", "X"]: tot_h += 12.0

            cfg_bh = st.session_state.get("bh_configs", {}).get(str(m_id), {})
            meta = max(0.0, (num_dias - neutros) * ((80.0 if cfg_bh.get("reduzida") else 160.0) / float(num_dias)))
            exc = (tot_h + float(st.session_state.get("ajuste_saldo_map", {}).get(str(m_id), 0.0))) - meta
            linha["HORAS / META"] = f"⚠️ {tot_h:.1f}h / {meta:.1f}h (+{exc:.1f}h)" if exc > 0 else f"{tot_h:.1f}h / {meta:.1f}h"
            matriz.append(linha)

        df_escala = pd.DataFrame(matriz)

        if not df_escala.empty:
            df_ed = st.data_editor(
                df_escala,
                use_container_width=True,
                hide_index=True,
                height=450,
                key="editor_escala_principal"
            )
            alt = False
            for idx_r, row in df_ed.iterrows():
                if idx_r < len(mils_ord):
                    it = mils_ord[idx_r]
                    for d, col_name in colunas_dias:
                        vp = padronizar_entrada_quadro(str(row.get(col_name, "")).strip())
                        ck = f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d:02d}"
                        if padronizar_entrada_quadro(grade.get(ck, "")) != vp:
                            grade[ck] = vp
                            alt = True
            if alt:
                st.session_state["grade_escala_lancamentos"] = grade
                executar_auto_save_banco()
                st.rerun()
        else:
            st.info("💡 Clique em '⚡ Aplicar Lançamentos e Atualizar Quadro' para montar a escala com os militares selecionados.")