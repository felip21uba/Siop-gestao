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

from utils.excel_escala_importer import (
    processar_upload_escala_excel,
    escanear_legendas_unicas_excel,
    MAPA_CONVERSAO_LEGENDAS,
)

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
    m_ano = st.session_state.get("ano_selecionado", datetime.date.today().year)
    m_mes = st.session_state.get("mes_selecionado", datetime.date.today().month)
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
    st.session_state["militares_no_quadro_chaves"] = copy.deepcopy(md.get("militares_no_quadro_chaves", []))
    st.session_state["ordem_customizada_map"] = copy.deepcopy(md.get("ordem_customizada_map", {}))
    st.session_state["bh_configs"] = copy.deepcopy(md.get("bh_configs", {}))
    st.session_state["ajuste_saldo_map"] = copy.deepcopy(md.get("ajuste_saldo_map", {}))
    st.session_state["dias_selecionados_passo4"] = copy.deepcopy(md.get("dias_selecionados_passo4", []))
    st.session_state["chave_escala_carregada"] = f"{m_ano}_{m_mes}"
    return True

def executar_auto_save_banco():
    try:
        m_ano = st.session_state.get("ano_selecionado", datetime.date.today().year)
        m_mes = st.session_state.get("mes_selecionado", datetime.date.today().month)

        matriz_dados = {
            "grade_escala_lancamentos": copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {})),
            "militares_no_quadro_chaves": copy.deepcopy(st.session_state.get("militares_no_quadro_chaves", [])),
            "ordem_customizada_map": copy.deepcopy(st.session_state.get("ordem_customizada_map", {})),
            "bh_configs": copy.deepcopy(st.session_state.get("bh_configs", {})),
            "ajuste_saldo_map": copy.deepcopy(st.session_state.get("ajuste_saldo_map", {})),
            "dias_selecionados_passo4": copy.deepcopy(st.session_state.get("dias_selecionados_passo4", [])),
        }

        salvar_escala_mensal_supabase(
            ano=m_ano,
            mes=m_mes,
            equipe=st.session_state.get("equipe_ativa", ""),
            modalidade=st.session_state.get("modalidade_escala", ""),
            matriz_dados=matriz_dados,
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
            resultado["mensagem"] = f"Empenho curto de {duracao_empenho:.1f}h (recomendado mínimo de 6.0h)."
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
# MODALIDADE POP-UP / MONITOR SECUNDÁRIO (SEGUNDA TELA)
# ============================================================

def construir_dados_monitor(matriz, m_ano, m_mes):
    grade = matriz.get("grade_escala_lancamentos", {})
    chaves = matriz.get("militares_no_quadro_chaves", [])
    ordem_map = matriz.get("ordem_customizada_map", {})

    militares = st.session_state.get("lista_militares", []) or carregar_militares_supabase() or []
    if not militares:
        return None

    mapa_militares = {str(m.get("chave") or m.get("id") or m.get("numero") or m.get("matricula")): m for m in militares if m}
    linhas = [mapa_militares.get(str(chave)) for chave in chaves if mapa_militares.get(str(chave))]
    if not linhas:
        linhas = militares.copy()

    def ordem_militar(militar):
        chave = militar.get("chave") or militar.get("id") or militar.get("numero") or militar.get("matricula")
        try:
            return int(ordem_map.get(str(chave), ordem_map.get(chave, 999999)))
        except Exception:
            return 999999

    linhas.sort(key=ordem_militar)
    ultimo_dia = calendar.monthrange(int(m_ano), int(m_mes))[1]
    datas = [datetime.date(int(m_ano), int(m_mes), dia) for dia in range(1, ultimo_dia + 1)]

    cabecalho = ["MILITAR"] + [f"{data.day:02d}<br>{DIAS_SEMANA_SIGLAS.get(data.weekday(), '')}" for data in datas]

    linhas_html = []
    for militar in linhas:
        militar_id = militar.get("id") or militar.get("numero") or militar.get("chave") or militar.get("matricula")
        equipe = militar.get("equipe", "")
        nome = militar.get("nome") or militar.get("militar") or militar.get("nome_guerra") or ""

        html_linha = f"<tr><td class='militar'>{nome}</td>"
        for data in datas:
            chave = f"{militar_id}_{equipe}_{data.year}_{data.month:02d}_{data.day:02d}"
            valor = grade.get(chave, "F")
            if _valor_vazio(valor): valor = "F"

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
        st.warning(f"Nenhuma escala salva no banco para {m_mes:02d}/{m_ano}.")
        return

    tabela = construir_dados_monitor(matriz, m_ano, m_mes)
    if tabela is None:
        st.warning("Não foi possível carregar os militares.")
        return

    st.markdown(tabela, unsafe_allow_html=True)
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(f'<div class="status-monitor">🟢 Sincronizado com o banco — última consulta: {agora}</div>', unsafe_allow_html=True)

def renderizar_modo_segunda_tela():
    params = st.query_params
    try:
        m_ano = int(params.get("ano", datetime.date.today().year))
    except Exception:
        m_ano = datetime.date.today().year

    try:
        m_mes = int(params.get("mes", datetime.date.today().month))
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
        .quadro-monitor th:first-child { left: 0; z-index: 7; min-width: 220px; text-align: left; }
        .quadro-monitor td:first-child { position: sticky; left: 0; z-index: 3; min-width: 220px; text-align: left; font-weight: 600; background: white; }
        .quadro-monitor td.folga { background: #dff0d8; font-weight: bold; }
        .quadro-monitor td.domingo { background: #eeeeee; font-weight: bold; }
        .quadro-monitor td.feriado { background: #fff2cc; font-weight: bold; }
        .titulo-monitor { font-size: 22px; font-weight: 700; }
        .subtitulo-monitor { font-size: 13px; color: #555; margin-bottom: 8px; }
        .status-monitor { margin-top: 5px; font-size: 11px; color: #555; }
        </style>
    """, unsafe_allow_html=True)

    nome_mes = calendar.month_name[int(m_mes)]
    st.markdown(f'<div class="titulo-monitor">🖥️ QUADRO GERAL (MONITOR STANDALONE)</div><div class="subtitulo-monitor">{nome_mes.upper()} / {m_ano}</div>', unsafe_allow_html=True)

    monitor_automatico(m_ano, m_mes)

# ============================================================
# PASSO 5 - PAINEL PRINCIPAL
# ============================================================

def renderizar_passo5():
    # Roteamento automático se aberto na URL da Segunda Tela
    params = st.query_params
    if str(params.get("modo_monitor", "")).lower() == "segunda_tela":
        renderizar_modo_segunda_tela()
        return

    hoje = datetime.date.today()
    st.session_state.setdefault("ano_selecionado", hoje.year)
    st.session_state.setdefault("mes_selecionado", hoje.month)
    st.session_state.setdefault("grade_escala_lancamentos", {})
    st.session_state.setdefault("militares_no_quadro_chaves", [])
    st.session_state.setdefault("ordem_customizada_map", {})

    militares = st.session_state.get("lista_militares") or carregar_militares_supabase() or []
    st.session_state["lista_militares"] = militares

    col1, col2 = st.columns(2)
    with col1:
        ano = st.number_input("Ano", min_value=2020, max_value=2100, value=int(st.session_state["ano_selecionado"]), step=1)
    with col2:
        mes = st.selectbox("Mês", options=list(range(1, 13)), index=int(st.session_state["mes_selecionado"]) - 1, format_func=lambda x: calendar.month_name[x].capitalize())

    if ano != st.session_state.get("ano_selecionado") or mes != st.session_state.get("mes_selecionado"):
        st.session_state["ano_selecionado"] = int(ano)
        st.session_state["mes_selecionado"] = int(mes)
        st.session_state.pop("_editor_escala_contexto", None)
        st.session_state.pop("chave_escala_carregada", None)
        st.rerun()

    m_ano, m_mes = int(ano), int(mes)
    chave_periodo = f"{m_ano}_{m_mes}"
    if st.session_state.get("chave_escala_carregada") != chave_periodo:
        carregar_escala_salva_banco()

    equipes = sorted({str(m.get("equipe", "")) for m in militares if m.get("equipe", "")}) or ["GERAL"]
    equipe_atual = st.session_state.get("equipe_ativa")
    if equipe_atual not in equipes:
        equipe_atual = equipes[0]

    equipe_atual = st.selectbox("Equipe", equipes, index=equipes.index(equipe_atual), key="equipe_ativa_select")
    if st.session_state.get("equipe_ativa") != equipe_atual:
        st.session_state["equipe_ativa"] = equipe_atual
        st.session_state.pop("_editor_escala_contexto", None)
        st.rerun()

    st.session_state["equipe_ativa"] = equipe_atual

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⚡ Aplicar Lançamentos e Atualizar Quadro", type="primary", use_container_width=True):
            if executar_auto_save_banco():
                st.success("✅ Quadro atualizado e sincronizado com o monitor!")
                st.rerun()
    with c2:
        if st.button("📂 Recarregar do Banco", use_container_width=True):
            st.session_state.pop("_editor_escala_contexto", None)
            carregar_escala_salva_banco()
            st.rerun()
    with c3:
        monitor_url = f"?modo_monitor=segunda_tela&ano={m_ano}&mes={m_mes}"
        st.markdown(
            f"""
            <a href="{monitor_url}" target="_blank" style="text-decoration:none;">
                <button style="width:100%; padding:8px; border-radius:6px; background:#f0f2f6; border:1px solid #d3d3d3; font-weight:600; cursor:pointer;">
                    🖥️ Abrir Segunda Tela (Pop-out)
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )

    st.divider()

    mils_equipe = [m for m in militares if str(m.get("equipe", "")) == str(equipe_atual)]
    if not mils_equipe:
        st.info("💡 Nenhum militar vinculado a esta equipe.")
        return

    ordem_map = st.session_state.get("ordem_customizada_map", {})
    def obter_ordem(militar):
        chave = militar.get("chave") or militar.get("id") or militar.get("numero") or militar.get("matricula")
        try:
            return int(ordem_map.get(str(chave), 999999))
        except Exception:
            return 999999

    mils_ord = sorted(mils_equipe, key=obter_ordem)
    ultimo_dia = calendar.monthrange(m_ano, m_mes)[1]
    datas = [datetime.date(m_ano, m_mes, dia) for dia in range(1, ultimo_dia + 1)]

    colunas = ["ORDEM", "EQUIPE", "Nº POLÍCIA", "MILITAR"] + [f"{data.day:02d} {DIAS_SEMANA_SIGLAS.get(data.weekday(), '')}" for data in datas] + ["HORAS / META"]
    linhas = []
    grade = st.session_state.get("grade_escala_lancamentos", {})

    for posicao, militar in enumerate(mils_ord, start=1):
        militar_id = militar.get("id") or militar.get("numero") or militar.get("chave") or militar.get("matricula")
        nome = militar.get("nome") or militar.get("militar") or militar.get("nome_guerra") or ""
        equipe = militar.get("equipe", equipe_atual)
        ordem = obter_ordem(militar)
        if ordem == 999999: ordem = posicao

        linha = [ordem, equipe, militar_id, nome]
        total_horas = 0.0

        for data in datas:
            chave = f"{militar_id}_{equipe}_{data.year}_{data.month:02d}_{data.day:02d}"
            valor = padronizar_entrada_quadro(grade.get(chave, "F"))
            linha.append(valor)
            if valor not in SIGLAS_DIAS_NEUTROS:
                total_horas += 12.0

        meta = 160 if str(st.session_state.get("modalidade_escala", "")).lower() not in {"meia", "80h"} else 80
        linha.append(f"{total_horas:.0f} / {meta}")
        linhas.append(linha)

    df_escala = pd.DataFrame(linhas, columns=colunas)

    equipe_key = _sanitizar_widget_key(equipe_atual)
    editor_key = f"editor_escala_principal_{m_ano}_{m_mes:02d}_{equipe_key}"

    if st.session_state.get("_editor_escala_contexto") != editor_key:
        st.session_state.pop(editor_key, None)
        st.session_state["_editor_escala_contexto"] = editor_key

    df_editado = st.data_editor(
        df_escala,
        key=editor_key,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["EQUIPE", "Nº POLÍCIA", "MILITAR", "HORAS / META"],
        column_config={
            "ORDEM": st.column_config.NumberColumn("ORDEM", min_value=1, step=1),
        },
    )

    if not df_editado.equals(df_escala):
        grade = st.session_state.get("grade_escala_lancamentos", {})
        ordem_map = st.session_state.get("ordem_customizada_map", {})
        alterou = False

        for idx in range(len(df_editado)):
            linha_original = df_escala.iloc[idx]
            linha_nova = df_editado.iloc[idx]
            militar_id = mils_ord[idx].get("id") or mils_ord[idx].get("numero") or mils_ord[idx].get("chave") or mils_ord[idx].get("matricula")
            equipe = mils_ord[idx].get("equipe", equipe_atual)

            for data in datas:
                coluna = f"{data.day:02d} {DIAS_SEMANA_SIGLAS.get(data.weekday(), '')}"
                if coluna not in df_editado.columns: continue

                valor_novo = padronizar_entrada_quadro(linha_nova[coluna])
                if valor_novo == padronizar_entrada_quadro(linha_original[coluna]): continue

                chave = f"{militar_id}_{equipe}_{data.year}_{data.month:02d}_{data.day:02d}"
                grade[chave] = valor_novo
                alterou = True

        st.session_state["grade_escala_lancamentos"] = grade
        st.session_state["ordem_customizada_map"] = ordem_map

        if alterou:
            executar_auto_save_banco()
            st.rerun()