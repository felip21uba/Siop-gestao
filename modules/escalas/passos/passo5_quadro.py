import streamlit as st
import datetime
import calendar
import pandas as pd
import copy
import re
import streamlit.components.v1 as components

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
    "F", "D", "X", "FER", "DOM", "FERIADO",
    "LM", "ATE", "FE", "LUT", "NUP", "DN", "DNT"
}

SIGLAS_ABATEM_META = {
    "F", "D", "X", "FER", "DOM", "FERIADO",
    "LM", "ATE", "FE", "LUT", "NUP", "DN", "DNT"
}

# ============================================================
# UTILITÁRIOS E MOTOR DE CÁLCULO DE HORAS
# ============================================================

def padronizar_entrada_quadro(valor):
    if valor is None or pd.isna(valor):
        return "F"
    v = str(valor).strip().upper()
    if not v or v in ["F", "FOLGA"]:
        return "F"
    if v in ["D", "DOM", "DOMINGO", "DESCANSO", "OFF"]:
        return "D"
    if v in ["X", "FER", "FERIADO"]:
        return "X"
    return str(valor).strip()

def extrair_intervalos_horarios(texto_celula, data_ref):
    if not texto_celula:
        return []
    texto = str(texto_celula).strip().upper()
    if texto in SIGLAS_DIAS_NEUTROS:
        return []

    padrao = re.findall(r'(\d{1,2}:\d{2})\s*(?:ÀS|AS|-|A)\s*(\d{1,2}:\d{2})', texto)
    intervalos = []

    for h_ini_str, h_fim_str in padrao:
        try:
            h_ini_p = [int(x) for x in h_ini_str.split(":")]
            h_fim_p = [int(x) for x in h_fim_str.split(":")]

            dt_ini = datetime.datetime(data_ref.year, data_ref.month, data_ref.day, h_ini_p[0], h_ini_p[1])
            dt_fim = datetime.datetime(data_ref.year, data_ref.month, data_ref.day, h_fim_p[0], h_fim_p[1])

            if dt_fim <= dt_ini:
                dt_fim += datetime.timedelta(days=1)

            intervalos.append((dt_ini, dt_fim))
        except Exception:
            continue

    return intervalos

def calcular_horas_efetivas_turno(texto_celula, data_ref, eh_supervisao=False):
    intervalos = extrair_intervalos_horarios(texto_celula, data_ref)
    if not intervalos:
        return 0.0

    horas_presenciais_efetivas = 0.0
    minutos_presenciais_reais = 0.0

    for dt_ini, dt_fim in intervalos:
        dt_curr = dt_ini
        while dt_curr < dt_fim:
            dt_next = dt_curr + datetime.timedelta(minutes=1)
            minutos_presenciais_reais += 1.0
            hora_atual = dt_curr.hour

            is_noturno = (hora_atual >= 23 or hora_atual < 5)
            fator_minuto = (70.0 / 60.0) if is_noturno else 1.0
            horas_presenciais_efetivas += (1.0 / 60.0) * fator_minuto

            dt_curr = dt_next

    if eh_supervisao or "SUPERVISÃO" in str(texto_celula).upper():
        horas_presenciais_reais = minutos_presenciais_reais / 60.0
        horas_sobreaviso_restantes = max(0.0, 24.0 - horas_presenciais_reais)
        credito_sobreaviso = horas_sobreaviso_restantes * 0.25
        return horas_presenciais_efetivas + credito_sobreaviso

    return horas_presenciais_efetivas

# ============================================================
# PERSISTÊNCIA NO BANCO DE DADOS (SUPABASE)
# ============================================================

def salvar_estado_undo():
    st.session_state.setdefault("pilha_undo", []).append({
        "grade": copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {})),
        "chaves": copy.deepcopy(st.session_state.get("militares_no_quadro_chaves", [])),
        "ordem": copy.deepcopy(st.session_state.get("ordem_customizada_map", {}))
    })
    if len(st.session_state["pilha_undo"]) > 10:
        st.session_state["pilha_undo"].pop(0)

def executar_auto_save_banco():
    try:
        m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
        m_mes = st.session_state.get("mes_escala", datetime.date.today().month)

        chaves_norm = [
            (str(p[0]), str(p[1]))
            for p in st.session_state.get("militares_no_quadro_chaves", [])
            if isinstance(p, (tuple, list)) and len(p) == 2
        ]

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
        st.error(f"Erro ao salvar no banco de dados: {e}")
        return False

def carregar_escala_salva_banco():
    if not supabase:
        return False

    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)

    try:
        res = supabase.table("escalas_mensais").select("matriz_dados").eq("ano", m_ano).eq("mes", m_mes).execute()
        if res and res.data:
            md = res.data[0].get("matriz_dados", {})
            st.session_state["grade_escala_lancamentos"] = md.get("grade_escala_lancamentos", {})
            chaves_raw = md.get("militares_no_quadro_chaves", [])
            st.session_state["militares_no_quadro_chaves"] = [
                (str(p[0]), str(p[1]))
                for p in chaves_raw
                if isinstance(p, (tuple, list)) and len(p) == 2
            ]
            st.session_state["ordem_customizada_map"] = md.get("ordem_customizada_map", {})
            st.session_state["bh_configs"] = md.get("bh_configs", {})
            st.session_state["ajuste_saldo_map"] = md.get("ajuste_saldo_map", {})
            st.session_state["dias_selecionados_passo4"] = md.get("dias_selecionados_passo4", [])
            st.session_state["chave_escala_carregada"] = f"{m_ano}_{m_mes:02d}"
            return True
        return False
    except Exception as ex:
        print(f"Aviso ao carregar do banco: {ex}")
        return False

# ============================================================
# AUDITORIA E TRAVAS DE SOBREPOSIÇÃO ESTREITAMENTE POR MILITAR
# ============================================================

def verificar_trava_sobreposicao(dias_filtro=None, militares_filtro=None):
    if st.session_state.get("limpar_avisos_manual", False) and not dias_filtro:
        st.session_state["lista_bloqueios_auditoria"] = []
        st.session_state["lista_avisos_descanso"] = []
        return

    bloqueios = []
    avisos_descanso = []

    grade = st.session_state.get("grade_escala_lancamentos", {})
    chaves = st.session_state.get("militares_no_quadro_chaves", [])
    mils = st.session_state.get("lista_militares", [])
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    num_dias = calendar.monthrange(m_ano, m_mes)[1]

    mils_map = {
        str(m.get("id")).strip(): f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')}"
        for m in mils if m.get("id")
    }

    if militares_filtro:
        mils_alvo_map = {k: v for k, v in mils_map.items() if k in militares_filtro}
    else:
        mils_alvo_map = mils_map

    dias_alvo = dias_filtro if dias_filtro else list(range(1, num_dias + 1))

    for m_id_alvo, nome_mil in mils_alvo_map.items():
        todos_intervalos_militar = []

        for d in range(1, num_dias + 1):
            dt_ref = datetime.date(m_ano, m_mes, d)
            
            eqs_deste_militar = [
                str(p[1]) for p in chaves
                if isinstance(p, (tuple, list)) and str(p[0]).strip() == m_id_alvo
            ]

            for eq in eqs_deste_militar:
                val = grade.get(f"{m_id_alvo}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "F")
                val_clean = str(val).strip().upper()

                if val_clean in SIGLAS_DIAS_NEUTROS or val_clean in ["", "NONE", "NAN", "F", "D", "X"]:
                    continue

                intervalos = extrair_intervalos_horarios(val_clean, dt_ref)
                for inter in intervalos:
                    todos_intervalos_militar.append({
                        "dia": d,
                        "equipe": eq,
                        "inicio": inter[0],
                        "fim": inter[1],
                        "texto_raw": val_clean
                    })

        if not todos_intervalos_militar:
            continue

        for i in range(len(todos_intervalos_militar)):
            for j in range(i + 1, len(todos_intervalos_militar)):
                t1 = todos_intervalos_militar[i]
                t2 = todos_intervalos_militar[j]

                if dias_filtro and (t1["dia"] not in dias_alvo and t2["dia"] not in dias_alvo):
                    continue

                if (t1["inicio"] < t2["fim"]) and (t1["fim"] > t2["inicio"]):
                    bloqueios.append({
                        "militar": nome_mil,
                        "mensagem": f"Choque no Dia {t1['dia']:02d}/{m_mes:02d}: Lançamento [{t1['equipe']}] ({t1['texto_raw']}) e [{t2['equipe']}] ({t2['texto_raw']}) se sobrepõem no mesmo horário!"
                    })

        intervalos_ordenados = sorted(todos_intervalos_militar, key=lambda x: x["inicio"])
        for i in range(len(intervalos_ordenados) - 1):
            atual = intervalos_ordenados[i]
            proximo = intervalos_ordenados[i + 1]

            if dias_filtro and (atual["dia"] not in dias_alvo and proximo["dia"] not in dias_alvo):
                continue

            if proximo["inicio"] >= atual["fim"]:
                diferenca_horas = (proximo["inicio"] - atual["fim"]).total_seconds() / 3600.0
                if diferenca_horas < 6.0:
                    avisos_descanso.append({
                        "militar": nome_mil,
                        "mensagem": f"Intervalo de descanso curto: Término no Dia {atual['dia']:02d} ({atual['texto_raw']}) e Início no Dia {proximo['dia']:02d} ({proximo['texto_raw']}) com apenas {diferenca_horas:.1f}h de descanso (mínimo: 6h)."
                    })

    st.session_state["lista_bloqueios_auditoria"] = bloqueios
    st.session_state["lista_avisos_descanso"] = avisos_descanso

def recalcular_escala_matriz():
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    mod_nome = st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso")
    eq_ativa = str(st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))
    num_dias = calendar.monthrange(m_ano, m_mes)[1]

    grade = st.session_state.get("grade_escala_lancamentos", {})
    dias_ativos = set(st.session_state.get("dias_selecionados_passo4", []))

    h_avulso = st.session_state.get("horario_avulso_p2", "07:00 às 19:00")
    h_adm_norm = st.session_state.get("adm_h_norm", "08:00 às 12:00\n13:30 às 17:00")
    h_adm_qua = st.session_state.get("adm_h_qua", "08:30 às 13:00")

    seq_36 = {"Dia (Trabalho)": [st.session_state.get("c36_h_dia", "07:00 às 19:00"), "D", st.session_state.get("c36_h_noite", "19:00 às 07:00"), "D", "F"]}.get(
        st.session_state.get("c36_fase_ini", "Dia (Trabalho)"), ["07:00 às 19:00", "D", "19:00 às 07:00", "D", "F"]
    )
    seq_72 = {"Fase 1 (Dia)": [st.session_state.get("c72_h_dia", "06:00 às 18:00"), st.session_state.get("c72_h_noite", "18:00 às 06:00"), "D", "D", "F"]}.get(
        st.session_state.get("c72_fase_ini", "Fase 1 (Dia)"), ["06:00 às 18:00", "18:00 às 06:00", "D", "D", "F"]
    )
    sem_iso_d1 = datetime.date(m_ano, m_mes, 1).isocalendar()[1]

    for pair in st.session_state.get("militares_no_quadro_chaves", []):
        if not (isinstance(pair, (tuple, list)) and len(pair) == 2 and str(pair[1]) == eq_ativa):
            continue

        m_id = str(pair[0])

        for d in range(1, num_dias + 1):
            k = f"{m_id}_{eq_ativa}_{m_ano}_{m_mes:02d}_{d:02d}"

            if any(sig in str(grade.get(k, "")).upper() for sig in SIGLAS_DIAS_NEUTROS if sig not in ["F", "D", "X"]):
                continue

            valor_dia = "F"

            if mod_nome == "Turno Único / Avulso":
                valor_dia = h_avulso if d in dias_ativos else "F"

            elif mod_nome == "ADM (Seg-Sex)":
                w = calendar.weekday(m_ano, m_mes, d)
                if w < 5 and d in dias_ativos:
                    valor_dia = h_adm_qua if w == 2 else h_adm_norm
                else:
                    valor_dia = "F"

            elif mod_nome == "Ciclo 12x36":
                val_c = seq_36[(d - 1) % 5]
                valor_dia = val_c if (d in dias_ativos or val_c in ["D", "F"]) else "F"

            elif mod_nome == "Ciclo 12x72 (5D)":
                val_c = seq_72[(d - 1) % 5]
                valor_dia = val_c if (d in dias_ativos or val_c in ["D", "F"]) else "F"

            elif mod_nome == "Dobradinha (14D)":
                w = calendar.weekday(m_ano, m_mes, d)
                eh_sem_a = ((datetime.date(m_ano, m_mes, d).isocalendar()[1] - sem_iso_d1) % 2 == 0) if "SEMANA A" in st.session_state.get("dob_sem_ini", "SEMANA A") else ((datetime.date(m_ano, m_mes, d).isocalendar()[1] - sem_iso_d1) % 2 != 0)
                trabalha = ((eh_sem_a and w in [0, 2, 5, 6]) or (not eh_sem_a and w in [1, 3, 4]))
                if trabalha and d in dias_ativos:
                    valor_dia = (st.session_state.get("dob_h_sq", "14:00 às 00:00") if w in [0, 1, 2, 3] else (st.session_state.get("dob_h_ss", "18:00 às 04:00") if w in [4, 5] else st.session_state.get("dob_h_dom", "18:00 às 02:00")))
                else:
                    valor_dia = "F"

            grade[k] = valor_dia

    st.session_state["grade_escala_lancamentos"] = grade
    st.session_state["limpar_avisos_manual"] = False
    verificar_trava_sobreposicao()

def abrir_segunda_janela_popup(m_mes, m_ano):
    url_espelho = f"espelho?mes={m_mes}&ano={m_ano}"
    components.html(
        f"""
        <script>
        const url = "{url_espelho}";
        const largura = Math.min(screen.availWidth, 1800);
        const altura = Math.min(screen.availHeight, 1000);
        const esquerda = Math.max(0, screen.availWidth - largura) / 2;
        const topo = Math.max(0, screen.availHeight - altura) / 2;
        window.open(
            url,
            "SIOP_QUADRO_5_ESPELHO",
            "width=" + largura + ",height=" + altura + ",left=" + esquerda + ",top=" + topo + ",resizable=yes,scrollbars=yes,toolbar=no,menubar=no,location=no,status=no"
        );
        </script>
        """,
        height=0
    )

# ============================================================
# TELA PRINCIPAL (PASSO 5)
# ============================================================

def renderizar_passo5():
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)

    chave_periodo = f"{m_ano}_{m_mes:02d}"
    if st.session_state.get("chave_escala_carregada") != chave_periodo:
        carregar_escala_salva_banco()
        st.session_state["chave_escala_carregada"] = chave_periodo

    if st.session_state.get("atualizar_quadro_passo5", False):
        sel_ids = set(str(mid) for mid in st.session_state.get("militares_selecionados_ids", []))
        eq_ativa = str(st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))
        existentes = [(str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", []) if isinstance(p, (tuple, list)) and len(p) == 2]
        existentes_set = set(existentes)

        st.session_state["militares_no_quadro_chaves"] = [p for p in existentes if (p[1] != eq_ativa or p[0] in sel_ids)] + [(mid, eq_ativa) for mid in sel_ids if (mid, eq_ativa) not in existentes_set]
        st.session_state["limpar_avisos_manual"] = False
        recalcular_escala_matriz()
        executar_auto_save_banco()
        st.session_state["atualizar_quadro_passo5"] = False

    verificar_trava_sobreposicao()

    bloqueios = st.session_state.get("lista_bloqueios_auditoria", [])
    avisos_descanso = st.session_state.get("lista_avisos_descanso", [])
    militares = st.session_state.get("lista_militares") or carregar_militares_supabase() or []
    st.session_state["lista_militares"] = militares
    quadro_travado = st.session_state.get("toggle_trava_quadro", False)

    with st.expander("📌 PASSO 5: Quadro Mensal de Escalas e Carga Horária", expanded=True):
        st.markdown(
            """
            <style>
            div[data-testid="stExpander"] div[data-testid="stVerticalBlock"] > div {
                gap: 0.3rem !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        col_esq, col_btn, col_link = st.columns([2.0, 1.2, 0.8], vertical_alignment="center")

        with col_esq:
            cnt_linhas = len(st.session_state.get("militares_no_quadro_chaves", []))
            st.markdown(f"👮‍♂️ **Linhas Ativas:** `{cnt_linhas}` &nbsp;|&nbsp; 💡 *Legenda `X` = serviço em outra equipe.*")

        with col_btn:
            if st.button("⚡ Aplicar Lançamentos", type="primary", use_container_width=True):
                st.session_state["atualizar_quadro_passo5"] = True
                st.session_state["limpar_avisos_manual"] = False
                recalcular_escala_matriz()
                executar_auto_save_banco()
                st.rerun()

        with col_link:
            if st.button("🖥️ Abrir 2ª Tela", type="secondary", use_container_width=True, help="Abre o Quadro 5 em uma janela separada em pop-up."):
                abrir_segunda_janela_popup(m_mes, m_ano)

        # QUADRO DE AUDITORIA DE AVISOS E TRAVAS
        if (bloqueios or avisos_descanso) and not st.session_state.get("limpar_avisos_manual", False):
            st.markdown("---")
            c_head_av, c_btn_fechar = st.columns([4, 1])
            with c_head_av:
                st.markdown("##### 🚨 Quadro de Auditoria da Escala:")
            with c_btn_fechar:
                if st.button("✖ OK / Entendido", type="secondary", use_container_width=True, key="btn_limpar_avisos_p5"):
                    st.session_state["lista_bloqueios_auditoria"] = []
                    st.session_state["lista_avisos_descanso"] = []
                    st.session_state["limpar_avisos_manual"] = True
                    st.toast("🧹 Avisos cientes e limpados da memória!", icon="✅")
                    st.rerun()

            if bloqueios:
                for b in bloqueios:
                    st.error(f"❌ **IMPEDIMENTO ({b['militar']}):** {b['mensagem']}")

            if avisos_descanso:
                for a in avisos_descanso:
                    st.warning(f"⚠️ **ALERTA DE DESCANSO < 6H ({a['militar']}):** {a['mensagem']}")
            st.markdown("---")

        num_dias = calendar.monthrange(m_ano, m_mes)[1]
        chaves_existentes = st.session_state.get("militares_no_quadro_chaves", [])
        mils_linhas = [
            {
                "id": str(p[0]),
                "equipe": str(p[1]),
                "posto_grad": m.get("posto_grad", "SD"),
                "nome_guerra": m.get("nome_guerra", "MILITAR"),
                "num_policia": m.get("num_policia", ""),
                "chave_linha": f"{p[0]}_{p[1]}"
            }
            for p in chaves_existentes if isinstance(p, (tuple, list)) and len(p) == 2
            for m in [next((x for x in militares if str(x.get("id")) == str(p[0])), {})] if m
        ]

        st.session_state.setdefault("ordem_customizada_map", {})
        for idx, item in enumerate(mils_linhas):
            st.session_state["ordem_customizada_map"].setdefault(item["chave_linha"], idx + 1)

        mils_ord = sorted(mils_linhas, key=lambda x: (
            st.session_state["ordem_customizada_map"].get(x["chave_linha"], 99),
            PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99),
            x["nome_guerra"]
        ))

        # ============================================================
        # PAINEL DE AJUSTE RÁPIDO COM OPÇÃO DE REMOÇÃO DE EQUIPE/LINHA
        # ============================================================
        with st.expander("⚡ Painel de Ajuste Rápido no Quadro (Lançamento em Lote / Remoção)", expanded=False):
            if mils_ord and not quadro_travado:
                dict_mils = {f"[{m['equipe']}] {m['posto_grad']} {m['nome_guerra']} ({m['num_policia']})": m for m in mils_ord}
                
                # Agrupa também por Equipes para permitir remoção coletiva
                equipes_no_quadro = sorted(list(set(m['equipe'] for m in mils_ord)))
                opcoes_selecao_mils = [f"--- TODA A EQUIPE: {eq} ---" for eq in equipes_no_quadro] + list(dict_mils.keys())

                c_f1, c_f2, c_f3 = st.columns([3, 2.5, 2.5])
                mils_sel_lote = c_f1.multiselect("Militar(es) ou Equipe(s):", opcoes_selecao_mils, key="p5_lote_mils")
                dt_hoje = datetime.date(m_ano, m_mes, 1)

                datas_sel = c_f2.date_input(
                    "Selecione a(s) Data(s) no Calendário:",
                    value=(dt_hoje, dt_hoje),
                    min_value=datetime.date(m_ano, m_mes, 1),
                    max_value=datetime.date(m_ano, m_mes, num_dias),
                    format="DD/MM/YYYY",
                    key="p5_cal_picker"
                )
                
                opcoes_eventos = [
                    "Horário Normal", 
                    "FE (Férias)", 
                    "LM (Licença)", 
                    "ATE (Atestado)", 
                    "D (Descanso)", 
                    "F (Folga)", 
                    "X (Outra Equipe)", 
                    "DN (Dia Neutro)", 
                    "DNT (Neutro Trab.)", 
                    "DIS (Dispensa)",
                    "❌ [REMOVER DA EQUIPE]",
                    "🧹 [LIMPAR HORÁRIOS DA LINHA]"
                ]

                tipo_ev = c_f3.selectbox("Evento / Ação:", opcoes_eventos, key="p5_tipo")

                if "Horário Normal" in tipo_ev or "DNT" in tipo_ev:
                    c_h1, c_h2, c_btn = st.columns([1.5, 1.5, 3])
                    with c_h1:
                        h_i = st.time_input("Início:", datetime.time(7, 0), key="p5_h_ini")
                    with c_h2:
                        h_f = st.time_input("Fim:", datetime.time(19, 0), key="p5_h_fim")
                    with c_btn:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        btn_aplicar_lote = st.button("⚡ Aplicar Alteração Direta", type="primary", use_container_width=True, key="btn_aplicar_lote_norm")
                    val_final_lote = f"{h_i.strftime('%H:%M')} às {h_f.strftime('%H:%M')}" + (" (DNT)" if "DNT" in tipo_ev else "")
                else:
                    val_final_lote = tipo_ev.split()[0]
                    btn_aplicar_lote = st.button("⚡ Aplicar Alteração Direta", type="primary", use_container_width=True, key="btn_aplicar_lote_sigla")

                if btn_aplicar_lote:
                    dias_alvo = []
                    if isinstance(datas_sel, (tuple, list)):
                        d_start = datas_sel[0].day
                        d_end = datas_sel[1].day if len(datas_sel) > 1 else d_start
                        dias_alvo = list(range(d_start, d_end + 1))
                    elif isinstance(datas_sel, datetime.date):
                        dias_alvo = [datas_sel.day]

                    if mils_sel_lote:
                        salvar_estado_undo()
                        grade_tmp = st.session_state.get("grade_escala_lancamentos", {})
                        chaves_tmp = list(st.session_state.get("militares_no_quadro_chaves", []))
                        
                        mils_efetivos_alvo = []
                        for sel_item in mils_sel_lote:
                            if sel_item.startswith("--- TODA A EQUIPE:"):
                                eq_nome_alvo = sel_item.replace("--- TODA A EQUIPE:", "").replace("---", "").strip()
                                mils_efetivos_alvo.extend([m for m in mils_ord if m["equipe"] == eq_nome_alvo])
                            elif sel_item in dict_mils:
                                mils_efetivos_alvo.append(dict_mils[sel_item])

                        cnt = 0
                        mids_lote = [str(it["id"]).strip() for it in mils_efetivos_alvo]

                        # AÇÃO 1: REMOVER LINHA/EQUIPE COMPLETA DO QUADRO
                        if "[REMOVER" in tipo_ev:
                            for it in mils_efetivos_alvo:
                                pair_rem = (str(it["id"]), str(it["equipe"]))
                                chaves_tmp = [p for p in chaves_tmp if not (isinstance(p, (tuple, list)) and str(p[0]) == pair_rem[0] and str(p[1]) == pair_rem[1])]
                                for d_a in range(1, num_dias + 1):
                                    grade_tmp.pop(f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d_a:02d}", None)
                                cnt += 1
                            st.session_state["militares_no_quadro_chaves"] = chaves_tmp
                            msg_sucesso = f"✅ {cnt} linha(s) de equipe removida(s) com sucesso do Quadro!"

                        # AÇÃO 2: LIMPAR APENAS OS HORÁRIOS NOS DIAS SELECIONADOS
                        elif "[LIMPAR" in tipo_ev:
                            for it in mils_efetivos_alvo:
                                for d_a in dias_alvo:
                                    ck = f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d_a:02d}"
                                    grade_tmp[ck] = "F"
                                    cnt += 1
                            msg_sucesso = f"✅ Horários limpos em {cnt} célula(s) com sucesso!"

                        # AÇÃO 3: LANÇAMENTO NORMAL DE HORÁRIO OU SIGLA
                        else:
                            for it in mils_efetivos_alvo:
                                for d_a in dias_alvo:
                                    ck = f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d_a:02d}"
                                    grade_tmp[ck] = val_final_lote
                                    cnt += 1
                            msg_sucesso = f"✅ Alteração aplicada a {cnt} célula(s) com sucesso!"

                        if cnt:
                            st.session_state["grade_escala_lancamentos"] = grade_tmp
                            executar_auto_save_banco()
                            st.session_state["limpar_avisos_manual"] = False
                            verificar_trava_sobreposicao(dias_filtro=dias_alvo, militares_filtro=mids_lote)
                            st.success(msg_sucesso)
                            st.rerun()

        colunas_dias = [(d, f"{'🔴 ' if calendar.weekday(m_ano, m_mes, d) in [5,6] else ''}{d:02d} {DIAS_SEMANA_SIGLAS[calendar.weekday(m_ano, m_mes, d)]}") for d in range(1, num_dias + 1)]
        matriz = []
        grade = st.session_state.get("grade_escala_lancamentos", {})

        for idx_r, item in enumerate(mils_ord):
            m_id, eq, pg, ng, np = item["id"], item["equipe"], padronizar_graduacao(item["posto_grad"]), item["nome_guerra"], item["num_policia"]
            linha = {"ORDEM": int(st.session_state["ordem_customizada_map"].get(item["chave_linha"], idx_r + 1)), "EQUIPE": eq, "Nº POLÍCIA": np, "MILITAR": f"{pg} {ng}"}
            tot_h, neutros = 0.0, 0

            for d, col_name in colunas_dias:
                v = padronizar_entrada_quadro(grade.get(f"{m_id}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "F"))
                if v in ["F", "", None] and any(str(p[0]) == str(m_id) and p[1] != eq and grade.get(f"{m_id}_{p[1]}_{m_ano}_{m_mes:02d}_{d:02d}") not in ["F", "D", "", None] for p in chaves_existentes if isinstance(p, (tuple, list)) and len(p) == 2):
                    v = "X"

                linha[col_name] = v
                v_str = str(v).upper().strip()
                tokens_dia = set(v_str.replace("/", " ").split())

                if any(sig in tokens_dia for sig in SIGLAS_ABATEM_META if sig not in ["F", "D", "X"]):
                    neutros += 1

                if v_str not in ["", "F", "D", "X"] and (not any(sig in tokens_dia for sig in SIGLAS_ABATEM_META if sig not in ["F", "D", "X"]) or "DNT" in tokens_dia):
                    dt_ref_dia = datetime.date(m_ano, m_mes, d)
                    eh_sup = (eq == "SUPERVISÃO" or "SUPERVISÃO" in v_str)
                    tot_h += calcular_horas_efetivas_turno(v_str, dt_ref_dia, eh_supervisao=eh_sup)

            cfg_bh = st.session_state.get("bh_configs", {}).get(str(m_id), {})
            carga_base_mes = 80.0 if cfg_bh.get("reduzida") else 160.0
            taxa_diaria = carga_base_mes / float(num_dias)

            dias_efetivos = num_dias - neutros
            meta_efetiva = max(0.0, dias_efetivos * taxa_diaria)
            saldo_exc = (tot_h + float(st.session_state.get("ajuste_saldo_map", {}).get(str(m_id), 0.0))) - meta_efetiva

            linha["HORAS / META"] = f"⚠️ {tot_h:.1f}h / {meta_efetiva:.1f}h ({saldo_exc:+.1f}h)" if saldo_exc > 0 else f"{tot_h:.1f}h / {meta_efetiva:.1f}h ({saldo_exc:+.1f}h)"
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

            alterou_quadro = False
            for idx_r, row in df_ed.iterrows():
                if idx_r >= len(mils_ord):
                    continue

                it = mils_ord[idx_r]
                nova_ordem = int(row.get("ORDEM", idx_r + 1))

                if st.session_state["ordem_customizada_map"].get(it["chave_linha"]) != nova_ordem:
                    salvar_estado_undo()
                    st.session_state["ordem_customizada_map"][it["chave_linha"]] = nova_ordem
                    alterou_quadro = True

                for d, col_name in colunas_dias:
                    vp = padronizar_entrada_quadro(str(row.get(col_name, "")).strip())
                    ck = f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d:02d}"
                    if padronizar_entrada_quadro(grade.get(ck, "")) != vp:
                        salvar_estado_undo()
                        grade[ck] = vp
                        alterou_quadro = True

            st.session_state["grade_escala_lancamentos"] = grade
            if alterou_quadro:
                st.session_state["limpar_avisos_manual"] = False
                verificar_trava_sobreposicao()
                executar_auto_save_banco()
        else:
            st.info("💡 Clique em '⚡ Aplicar Lançamentos' para montar a escala com os militares selecionados.")

        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        c_act1, c_act2 = st.columns(2)

        with c_act1:
            if st.button("🧹 Limpar Todo o Quadro", use_container_width=True, disabled=quadro_travado):
                salvar_estado_undo()
                st.session_state["grade_escala_lancamentos"] = {}
                st.session_state["militares_no_quadro_chaves"] = []
                st.session_state["lista_bloqueios_auditoria"] = []
                st.session_state["lista_avisos_descanso"] = []
                st.session_state["limpar_avisos_manual"] = False
                executar_auto_save_banco()
                st.success("🧹 Quadro limpo com sucesso!")
                st.rerun()

        with c_act2:
            if st.button("💾 Salvar Rascunho no Banco", type="primary", use_container_width=True):
                if executar_auto_save_banco():
                    st.success("✅ Rascunho da escala salvo no Supabase com sucesso!")