import streamlit as st
import datetime
import calendar

DIAS_SEMANA_SIGLAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

def calcular_dias_trabalho_ciclo(mod_nome, m_a, m_m, num_dias):
    """Calcula os dias de trabalho automático para ciclos fixos. Supervisão e Avulso ficam manuais."""
    if mod_nome == "ADM (Seg-Sex)":
        return [d for d in range(1, num_dias + 1) if calendar.weekday(m_a, m_m, d) < 5]

    elif mod_nome == "Ciclo 12x36":
        h_d = st.session_state.get("c36_h_dia", "07:00 às 19:00")
        h_n = st.session_state.get("c36_h_noite", "19:00 às 07:00")
        f_ini = st.session_state.get("c36_fase_ini", "Dia (Trabalho)")
        seq_map = {
            "Dia (Trabalho)": [h_d, "D", h_n, "D", "F"],
            "Descanso Pós-Dia": ["D", h_n, "D", "F", h_d],
            "Noite (Trabalho)": [h_n, "D", "F", h_d, "D"],
            "Descanso Pós-Noite": ["D", "F", h_d, "D", h_n],
            "Folga": ["F", h_d, "D", h_n, "D"]
        }
        padr = seq_map.get(f_ini, [h_d, "D", h_n, "D", "F"])
        return [d for d in range(1, num_dias + 1) if padr[(d - 1) % 5] not in ["D", "F"]]

    elif mod_nome == "Dobradinha (14D)":
        sem_ini = st.session_state.get("dob_sem_ini", "SEMANA A")
        eh_sem_a_ini = "SEMANA A" in sem_ini
        sem_iso_d1 = datetime.date(m_a, m_m, 1).isocalendar()[1]
        dias = []
        for d in range(1, num_dias + 1):
            dt = datetime.date(m_a, m_m, d)
            w = dt.weekday()
            diff_s = dt.isocalendar()[1] - sem_iso_d1
            eh_sem_a = (diff_s % 2 == 0) if eh_sem_a_ini else (diff_s % 2 != 0)
            trabalha = (eh_sem_a and w in [0, 2, 5, 6]) or ((not eh_sem_a) and w in [1, 3, 4])
            if trabalha:
                dias.append(d)
        return dias

    elif mod_nome == "Ciclo 12x72 (5D)":
        h_d = st.session_state.get("c72_h_dia", "06:00 às 18:00")
        h_n = st.session_state.get("c72_h_noite", "18:00 às 06:00")
        f_ini = st.session_state.get("c72_fase_ini", "Fase 1 (Dia)")
        seq_map = {
            "Fase 1 (Dia)": [h_d, h_n, "D", "D", "F"],
            "Fase 2 (Noite)": [h_n, "D", "D", "F", h_d],
            "Descanso 1": ["D", "D", "F", h_d, h_n],
            "Descanso 2": ["D", "F", h_d, h_n, "D"],
            "Folga": ["F", h_d, h_n, "D", "D"]
        }
        padr = seq_map.get(f_ini, [h_d, h_n, "D", "D", "F"])
        return [d for d in range(1, num_dias + 1) if padr[(d - 1) % 5] not in ["D", "F"]]

    else:
        return []

@st.fragment
def renderizar_fragmento_passo4():
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    lista_meses = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    num_dias_mes = calendar.monthrange(m_ano, m_mes)[1]

    st.markdown(f"#### 🗓️ Escolha os Dias do Mês de **{lista_meses[m_mes-1]}/{m_ano}**:")

    c_b1, c_b2 = st.columns(2)
    with c_b1:
        if st.button("✔ Marcar Todos os Dias", use_container_width=True, key="btn_marcar_dias_frag"):
            st.session_state["dias_selecionados_passo4"] = list(range(1, num_dias_mes + 1))
            st.rerun()
    with c_b2:
        if st.button("❌ Desmarcar Todos os Dias", use_container_width=True, key="btn_desmarcar_dias_frag"):
            st.session_state["dias_selecionados_passo4"] = []
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    dias_selecionados_set = set(st.session_state.get("dias_selecionados_passo4", []))
    
    cols_cal = st.columns(7)
    for d in range(1, num_dias_mes + 1):
        dia_semana_idx = calendar.weekday(m_ano, m_mes, d)
        sigla_sem = DIAS_SEMANA_SIGLAS[dia_semana_idx]
        eh_fds = dia_semana_idx in [5, 6]
        
        is_dia_sel = d in dias_selecionados_set
        prefixo_fds = "🔴 " if eh_fds else "🗓️ "
        label_dia = f"{prefixo_fds}{d:02d}\n\n{sigla_sem}"
        
        col_idx = (d - 1) % 7
        with cols_cal[col_idx]:
            tipo_btn_dia = "primary" if is_dia_sel else "secondary"
            if st.button(
                label_dia, 
                key=f"btn_dia_p4_frag_{d}", 
                type=tipo_btn_dia, 
                use_container_width=True,
                help=f"Dia {d:02d}/{m_mes:02d} ({sigla_sem})" + (" - Final de Semana" if eh_fds else "")
            ):
                if is_dia_sel:
                    st.session_state["dias_selecionados_passo4"].remove(d)
                else:
                    st.session_state["dias_selecionados_passo4"].append(d)
                st.rerun()

    qtd_dias_sel = len(st.session_state.get("dias_selecionados_passo4", []))
    st.info(f"📍 **{qtd_dias_sel} dia(s) selecionado(s)** para a escala.")

def renderizar_passo4(recalcular_matriz_passo5_func):
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    mod_ativa = st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso")
    num_dias = calendar.monthrange(m_ano, m_mes)[1]

    fase_36 = st.session_state.get("c36_fase_ini", "")
    fase_72 = st.session_state.get("c72_fase_ini", "")
    sem_dob = st.session_state.get("dob_sem_ini", "")
    
    assinatura_p2 = f"{m_ano}_{m_mes}_{mod_ativa}_{fase_36}_{fase_72}_{sem_dob}"
    
    if st.session_state.get("ultima_assinatura_p2") != assinatura_p2:
        st.session_state["dias_selecionados_passo4"] = calcular_dias_trabalho_ciclo(mod_ativa, m_ano, m_mes, num_dias)
        st.session_state["ultima_assinatura_p2"] = assinatura_p2

    exp4 = st.expander("📌 PASSO 4: Calendário de Dias da Escala", expanded=True)
    with exp4:
        renderizar_fragmento_passo4()

        st.divider()
        c_app1, c_app2, c_app3 = st.columns([1, 2, 1])
        with c_app2:
            if st.button("🔄 Sincronizar e Re-Gerar Quadro com Dias Marcados", type="primary", use_container_width=True):
                recalcular_matriz_passo5_func()
                st.success("✅ Escala sincronizada com os dias selecionados no Passo 4!")
                st.rerun()

        # PAINEL DE AUDITORIA: EXIBIÇÃO DE BLOQUEIOS E AVISOS DE DESCANSO < 8H
        bloqueios = st.session_state.get("lista_bloqueios_auditoria", [])
        alertas_descanso = st.session_state.get("lista_avisos_descanso", [])

        if bloqueios:
            st.error("🚨 **Lançamentos Bloqueados (Sobreposição de Horários):**")
            for b in bloqueios:
                st.write(f"• **{b['militar']}**: {b['mensagem']}")

        if alertas_descanso:
            st.warning("⚠️ **Alertas de Auditoria (Descanso Interjornada < 8 Horas):**")
            for a in alertas_descanso:
                st.write(f"• **{a['militar']}**: {a['mensagem']}")