import streamlit as st
import datetime
import calendar

lista_meses = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

def calcular_dias_trabalho_ciclo(mod_nome, m_a, m_m, num_dias):
    """Calcula estritamente os dias em que há turno de trabalho efetivo."""
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

    elif mod_nome == "Supervisão":
        return list(range(1, num_dias + 1))

    else:
        return []

def renderizar_passo2():
    exp2 = st.expander("📌 PASSO 2: Período de Apuração, Modalidade do Turno e Pré-Turno", expanded=True)
    with exp2:
        col_m, col_a, col_pt = st.columns([1.5, 1.5, 2])
        with col_m:
            mes_atual = st.session_state.get("mes_escala", datetime.date.today().month)
            mes_sel = st.selectbox("Mês da Escala:", lista_meses, index=mes_atual - 1, key="sel_mes_p2")
            st.session_state["mes_escala"] = lista_meses.index(mes_sel) + 1
        with col_a:
            st.session_state["ano_escala"] = st.number_input("Ano da Escala:", min_value=2024, max_value=2035, value=st.session_state.get("ano_escala", datetime.date.today().year), key="sel_ano_p2")
        with col_pt:
            st.selectbox("⏱️ Pré-Turno de Apresentação:", ["Sem Pré-Turno (0 min)", "Pré-Turno 15 min", "Pré-Turno 30 min (+0.5h)", "Pré-Turno 45 min"], index=2, key="sel_pre_turno_p2")

        st.divider()
        st.markdown("#### ⏰ Seleção da Modalidade do Turno / Ciclo")
        
        m_m = st.session_state["mes_escala"]
        m_a = st.session_state["ano_escala"]
        num_dias = calendar.monthrange(m_a, m_m)[1]

        modalidades = ["Turno Único / Avulso", "ADM (Seg-Sex)", "Supervisão", "Ciclo 12x36", "Dobradinha (14D)", "Ciclo 12x72 (5D)"]
        cols_mod = st.columns(len(modalidades))
        
        for idx, mod_nome in enumerate(modalidades):
            eh_mod_ativa = (mod_nome == st.session_state.get("modalidade_turno_ativa"))
            with cols_mod[idx]:
                if st.button(f"⏰ {mod_nome}", key=f"btn_mod_p2_{mod_nome}", type="primary" if eh_mod_ativa else "secondary", use_container_width=True):
                    st.session_state["modalidade_turno_ativa"] = mod_nome
                    st.session_state["dias_selecionados_passo4"] = calcular_dias_trabalho_ciclo(mod_nome, m_a, m_m, num_dias)
                    st.session_state["atualizar_quadro_passo5"] = True
                    st.rerun()

        mod_atual = st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso")
        st.info(f"📍 Modalidade Selecionada: **{mod_atual}**")

        # PARAMETRIZAÇÃO DAS MODALIDADES
        if mod_atual == "Turno Único / Avulso":
            st.warning("👉 **Escolha os dias no Passo 4.** O Quadro do Passo 5 reflete exatamente os dias marcados.")
            c_h1, c_h2 = st.columns(2)
            with c_h1:
                t_ini = st.time_input("Hora Início:", datetime.time(7, 0), key="avulso_hora_ini_clock")
            with c_h2:
                t_fim = st.time_input("Hora Fim:", datetime.time(19, 0), key="avulso_hora_fim_clock")
            st.session_state["horario_avulso_p2"] = f"{t_ini.strftime('%H:%M')} às {t_fim.strftime('%H:%M')}"

        elif mod_atual == "ADM (Seg-Sex)":
            st.markdown("**Configuração de Horários do Expediente ADM:**")
            col_a1, col_a2, col_a3, col_a4 = st.columns(4)
            with col_a1:
                adm1_ini = st.time_input("Entrada Manhã:", datetime.time(8, 0), key="adm_t1_ini")
                adm1_fim = st.time_input("Saída Manhã:", datetime.time(12, 0), key="adm_t1_fim")
            with col_a2:
                adm2_ini = st.time_input("Entrada Tarde:", datetime.time(13, 30), key="adm_t2_ini")
                adm2_fim = st.time_input("Saída Tarde:", datetime.time(17, 0), key="adm_t2_fim")
            with col_a3:
                qua_ini = st.time_input("Quarta Entrada:", datetime.time(8, 30), key="adm_qua_ini")
                qua_fim = st.time_input("Quarta Saída:", datetime.time(13, 0), key="adm_qua_fim")
            with col_a4:
                opc_adm = st.radio("Padrão Seg,Ter,Qui,Sex:", ["08:00/17:00", "08:30/17:00"], key="radio_padr_adm")

            # APLICANDO A QUEBRA DE LINHA (\n) NO HORÁRIO DA ADM
            if opc_adm == "08:30/17:00":
                horario_normal_adm = f"08:30 às 12:00\n{adm2_ini.strftime('%H:%M')} às {adm2_fim.strftime('%H:%M')}"
            else:
                horario_normal_adm = f"{adm1_ini.strftime('%H:%M')} às {adm1_fim.strftime('%H:%M')}\n{adm2_ini.strftime('%H:%M')} às {adm2_fim.strftime('%H:%M')}"
            
            horario_qua_adm = f"{qua_ini.strftime('%H:%M')} às {qua_fim.strftime('%H:%M')}"
            st.session_state["adm_h_norm"] = horario_normal_adm
            st.session_state["adm_h_qua"] = horario_qua_adm

        elif mod_atual == "Supervisão":
            st.markdown("**Configuração de Horários da Supervisão:**")
            c_s1, c_s2, c_s3, c_s4 = st.columns(4)
            with c_s1:
                sup_dq_ini = st.time_input("Dom-Qui Início:", datetime.time(15, 0), key="sup_dq_ini")
            with c_s2:
                sup_dq_fim = st.time_input("Dom-Qui Fim:", datetime.time(21, 0), key="sup_dq_fim")
            with c_s3:
                sup_ss_ini = st.time_input("Sex-Sáb Início:", datetime.time(18, 0), key="sup_ss_ini")
            with c_s4:
                sup_ss_fim = st.time_input("Sex-Sáb Fim:", datetime.time(0, 0), key="sup_ss_fim")

            st.session_state["horario_sup_dom_qui"] = f"{sup_dq_ini.strftime('%H:%M')} às {sup_dq_fim.strftime('%H:%M')}"
            st.session_state["horario_sup_sex_sab"] = f"{sup_ss_ini.strftime('%H:%M')} às {sup_ss_fim.strftime('%H:%M')}"

        elif mod_atual == "Ciclo 12x36":
            st.markdown("#### Sequência do Ciclo: `Dia` ➔ `Descanso (D)` ➔ `Noite` ➔ `Descanso (D)` ➔ `Folga (F)`")
            c_c1, c_c2, c_c3, c_c4, c_c5 = st.columns(5)
            with c_c1:
                c36_d_ini = st.time_input("Dia Início:", datetime.time(7, 0), key="c36_d_ini")
            with c_c2:
                c36_d_fim = st.time_input("Dia Fim:", datetime.time(19, 0), key="c36_d_fim")
            with c_c3:
                c36_n_ini = st.time_input("Noite Início:", datetime.time(19, 0), key="c36_n_ini")
            with c_c4:
                c36_n_fim = st.time_input("Noite Fim:", datetime.time(7, 0), key="c36_n_fim")
            with c_c5:
                fase_ini_36 = st.selectbox(
                    "Sequência no DIA 01:",
                    ["Dia (Trabalho)", "Descanso Pós-Dia", "Noite (Trabalho)", "Descanso Pós-Noite", "Folga"],
                    key="sb_fase_ini_36_clock"
                )

            st.session_state["c36_h_dia"] = f"{c36_d_ini.strftime('%H:%M')} às {c36_d_fim.strftime('%H:%M')}"
            st.session_state["c36_h_noite"] = f"{c36_n_ini.strftime('%H:%M')} às {c36_n_fim.strftime('%H:%M')}"
            
            if st.session_state.get("c36_fase_ini") != fase_ini_36:
                st.session_state["c36_fase_ini"] = fase_ini_36
                st.session_state["dias_selecionados_passo4"] = calcular_dias_trabalho_ciclo(mod_atual, m_a, m_m, num_dias)
                st.session_state["atualizar_quadro_passo5"] = True
                st.rerun()

        elif mod_atual == "Dobradinha (14D)":
            st.markdown("**Parâmetros e Horários do Ciclo Dobradinha (14 Dias):**")
            semana_ini_dob = st.radio(
                "Qual a semana do militar no DIA 01 do mês?",
                ["SEMANA A (Trabalha: Seg, Qua, Sáb, Dom)", "SEMANA B (Trabalha: Ter, Qui, Sex)"],
                key="radio_dobradinha_sem_clock"
            )

            st.markdown("**Ajuste os Horários Padrão por Período:**")
            c_dob1, c_dob2, c_dob3 = st.columns(3)
            with c_dob1:
                st.caption("📅 Segunda a Quinta-Feira")
                d_sq_ini = st.time_input("Início (Seg-Qui):", datetime.time(14, 0), key="dob_sq_ini")
                d_sq_fim = st.time_input("Fim (Seg-Qui):", datetime.time(0, 0), key="dob_sq_fim")
            with c_dob2:
                st.caption("📅 Sexta-Feira e Sábado")
                d_ss_ini = st.time_input("Início (Sex-Sáb):", datetime.time(18, 0), key="dob_ss_ini")
                d_ss_fim = st.time_input("Fim (Sex-Sáb):", datetime.time(4, 0), key="dob_ss_fim")
            with c_dob3:
                st.caption("📅 Domingo")
                d_dom_ini = st.time_input("Início (Dom):", datetime.time(18, 0), key="dob_dom_ini")
                d_dom_fim = st.time_input("Fim (Dom):", datetime.time(2, 0), key="dob_dom_fim")

            st.session_state["dob_h_sq"] = f"{d_sq_ini.strftime('%H:%M')} às {d_sq_fim.strftime('%H:%M')}"
            st.session_state["dob_h_ss"] = f"{d_ss_ini.strftime('%H:%M')} às {d_ss_fim.strftime('%H:%M')}"
            st.session_state["dob_h_dom"] = f"{d_dom_ini.strftime('%H:%M')} às {d_dom_fim.strftime('%H:%M')}"

            if st.session_state.get("dob_sem_ini") != semana_ini_dob:
                st.session_state["dob_sem_ini"] = semana_ini_dob
                st.session_state["dias_selecionados_passo4"] = calcular_dias_trabalho_ciclo(mod_atual, m_a, m_m, num_dias)
                st.session_state["atualizar_quadro_passo5"] = True
                st.rerun()

        elif mod_atual == "Ciclo 12x72 (5D)":
            st.markdown("#### Sequência do Ciclo: `Dia` ➔ `Noite` ➔ `Descanso (D)` ➔ `Descanso (D)` ➔ `Folga (F)`")
            c_72_1, c_72_2, c_72_3, c_72_4, c_72_5 = st.columns(5)
            with c_72_1:
                c72_d_ini = st.time_input("Dia Início:", datetime.time(6, 0), key="c72_d_ini")
            with c_72_2:
                c72_d_fim = st.time_input("Dia Fim:", datetime.time(18, 0), key="c72_d_fim")
            with c_72_3:
                c72_n_ini = st.time_input("Noite Início:", datetime.time(18, 0), key="c72_n_ini")
            with c_72_4:
                c72_n_fim = st.time_input("Noite Fim:", datetime.time(6, 0), key="c72_n_fim")
            with c_72_5:
                fase_ini_72 = st.selectbox(
                    "Fase no DIA 01:",
                    ["Fase 1 (Dia)", "Fase 2 (Noite)", "Descanso 1", "Descanso 2", "Folga"],
                    key="sb_fase_ini_72_clock"
                )

            st.session_state["c72_h_dia"] = f"{c72_d_ini.strftime('%H:%M')} às {c72_d_fim.strftime('%H:%M')}"
            st.session_state["c72_h_noite"] = f"{c72_n_ini.strftime('%H:%M')} às {c72_n_fim.strftime('%H:%M')}"

            if st.session_state.get("c72_fase_ini") != fase_ini_72:
                st.session_state["c72_fase_ini"] = fase_ini_72
                st.session_state["dias_selecionados_passo4"] = calcular_dias_trabalho_ciclo(mod_atual, m_a, m_m, num_dias)
                st.session_state["atualizar_quadro_passo5"] = True
                st.rerun()