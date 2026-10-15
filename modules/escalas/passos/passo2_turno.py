"""
==============================================================================
Módulo do Passo 2 - Gestão de Equipes (Cards) & Modalidade do Turno / Ciclo
Consome o Mês, Ano, Fração e Pré-Turno configurados exclusivamente no Passo 1.
==============================================================================
"""

import streamlit as st
import datetime

MODALIDADES_TURNOS = [
    "Turno Único / Avulso",
    "ADM (Seg-Sex)",
    "Ciclo 12x36",
    "Ciclo 12x72 (5D)",
    "Dobradinha (14D)"
]

CORES_PADRAO_EQUIPES = {
    "CPU": "#a16207",
    "RP": "#1e293b",
    "SUPERVISÃO": "#b91c1c",
    "ADMINISTRAÇÃO": "#0f766e",
    "TM ALPHA": "#0369a1",
    "GEPAR": "#047857",
    "TÁTICO MÓVEL": "#1e1b4b"
}


def renderizar_passo2():
    sub_ativa = st.session_state.get("cfg_subunidade", "111ª CIA PM")
    esc_ativa = st.session_state.get("nome_escala_ativa", "ESCALA ORDINÁRIA")

    with st.expander("📌 PASSO 2: Gestão de Equipes, Modalidade do Turno & Ciclos", expanded=True):
        
        # ----------------------------------------------------------------------
        # 1. CARDS E SELEÇÃO DAS EQUIPES OPERACIONAIS
        # ----------------------------------------------------------------------
        st.markdown(f"##### 👥 **Gestão de Equipes e Empregos Operacionais ({sub_ativa} — {esc_ativa}):**")
        st.caption("Clique no card da equipe desejada para alternar a edição e vincular a modalidade de turno.")

        if "lista_equipes_unidade" not in st.session_state:
            st.session_state["lista_equipes_unidade"] = ["CPU", "RP", "SUPERVISÃO", "ADMINISTRAÇÃO", "TM ALPHA", "GEPAR"]

        if "equipe_ativa" not in st.session_state:
            st.session_state["equipe_ativa"] = "ADMINISTRAÇÃO"

        # GRID DE CARDS DAS EQUIPES
        lista_eqs = st.session_state["lista_equipes_unidade"]
        cols_cards = st.columns(min(len(lista_eqs), 6))

        for idx, eq_item in enumerate(lista_eqs):
            col_target = cols_cards[idx % len(cols_cards)]
            is_ativa = (st.session_state["equipe_ativa"] == eq_item)
            
            tipo_btn = "primary" if is_ativa else "secondary"
            
            with col_target:
                label_card = f"{'🟢 ' if is_ativa else ''}{eq_item}"
                if st.button(label_card, key=f"btn_card_eq_p2_{eq_item}", type=tipo_btn, use_container_width=True):
                    st.session_state["equipe_ativa"] = eq_item
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        c_eq1, c_eq2 = st.columns([3, 1.5])
        with c_eq1:
            eq_sel = st.selectbox(
                "Equipe / Emprego Operacional em Edição:",
                options=st.session_state["lista_equipes_unidade"],
                index=0 if st.session_state["equipe_ativa"] not in st.session_state["lista_equipes_unidade"] else st.session_state["lista_equipes_unidade"].index(st.session_state["equipe_ativa"]),
                key="sb_equipe_ativa_passo2"
            )
            st.session_state["equipe_ativa"] = eq_sel

        with c_eq2:
            nova_eq_nome = st.text_input("➕ Criar Nova Equipe:", placeholder="Ex: TÁTICO MÓVEL", key="txt_nova_eq_passo2").strip().upper()
            if st.button("➕ Adicionar Equipe", use_container_width=True, key="btn_add_eq_passo2"):
                if nova_eq_nome and nova_eq_nome not in st.session_state["lista_equipes_unidade"]:
                    st.session_state["lista_equipes_unidade"].append(nova_eq_nome)
                    st.session_state["equipe_ativa"] = nova_eq_nome
                    st.success(f"✅ Equipe '{nova_eq_nome}' adicionada com sucesso!")
                    st.rerun()

        st.info(f"🎯 **Equipe Ativa para Lançamento:** `{st.session_state['equipe_ativa']}`")

        st.divider()

        # ----------------------------------------------------------------------
        # 2. SELEÇÃO DA MODALIDADE DO TURNO / CICLO
        # ----------------------------------------------------------------------
        st.markdown(f"##### ⏰ **Seleção da Modalidade do Turno / Ciclo ({st.session_state['equipe_ativa']}):**")

        if "modalidade_turno_ativa" not in st.session_state:
            st.session_state["modalidade_turno_ativa"] = "Turno Único / Avulso"

        c_mod1, c_mod2 = st.columns([2.5, 2])

        with c_mod1:
            st.session_state["modalidade_turno_ativa"] = st.selectbox(
                "Escolha a Modalidade do Turno:",
                options=MODALIDADES_TURNOS,
                index=MODALIDADES_TURNOS.index(st.session_state["modalidade_turno_ativa"]),
                key="sb_passo2_modalidade_turno"
            )

        mod = st.session_state["modalidade_turno_ativa"]
        st.divider()

        # CONFIGURAÇÃO DE HORÁRIOS DA MODALIDADE SELECIONADA
        if mod == "Turno Único / Avulso":
            st.markdown("###### 🕒 **Configuração de Turno Único / Avulso:**")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                h_i = st.time_input("Horário de Início:", datetime.time(7, 0), key="p2_av_h_ini")
            with col_a2:
                h_f = st.time_input("Horário de Término:", datetime.time(19, 0), key="p2_av_h_fim")
            st.session_state["horario_avulso_p2"] = f"{h_i.strftime('%H:%M')} às {h_f.strftime('%H:%M')}"

        elif mod == "ADM (Seg-Sex)":
            st.markdown("###### 🏛️ **Horários do Expediente Administrativo:**")
            c_adm1, c_adm2 = st.columns(2)
            with c_adm1:
                st.session_state["adm_h_norm"] = st.text_area("Horário Padrão (Seg, Ter, Qui, Sex):", value="08:00 às 12:00\n13:30 às 17:00", height=68, key="p2_adm_norm")
            with c_adm2:
                st.session_state["adm_h_qua"] = st.text_input("Horário Quarta-feira (Especial):", value="08:30 às 13:00", key="p2_adm_qua")

        elif mod == "Ciclo 12x36":
            st.markdown("###### 🔄 **Turnos da Escala 12x36:**")
            c_36_1, c_36_2, c_36_3 = st.columns([2, 2, 2])
            with c_36_1:
                st.session_state["c36_h_dia"] = st.text_input("Turno Diurno:", value="07:00 às 19:00", key="p2_36_dia")
            with c_36_2:
                st.session_state["c36_h_noite"] = st.text_input("Turno Noturno:", value="19:00 às 07:00", key="p2_36_noite")
            with c_36_3:
                st.session_state["c36_fase_ini"] = st.selectbox(
                    "Fase Inicial (Dia 1):",
                    ["Dia (Trabalho)", "Descanso Pós-Dia", "Noite (Trabalho)", "Descanso Pós-Noite", "Folga"],
                    key="p2_36_fase"
                )

        elif mod == "Ciclo 12x72 (5D)":
            st.markdown("###### 🔄 **Turnos da Escala 12x72:**")
            c_72_1, c_72_2, c_72_3 = st.columns([2, 2, 2])
            with c_72_1:
                st.session_state["c72_h_dia"] = st.text_input("Turno Fase 1:", value="06:00 às 18:00", key="p2_72_dia")
            with c_72_2:
                st.session_state["c72_h_noite"] = st.text_input("Turno Fase 2:", value="18:00 às 06:00", key="p2_72_noite")
            with c_72_3:
                st.session_state["c72_fase_ini"] = st.selectbox(
                    "Fase Inicial (Dia 1):",
                    ["Fase 1 (Dia)", "Fase 2 (Noite)", "Descanso 1", "Descanso 2", "Folga"],
                    key="p2_72_fase"
                )

        elif mod == "Dobradinha (14D)":
            st.markdown("###### 🔄 **Horários da Escala Dobradinha:**")
            c_dob1, c_dob2, c_dob3, c_dob4 = st.columns([1.5, 1.5, 1.5, 1.5])
            with c_dob1:
                st.session_state["dob_h_sq"] = st.text_input("Seg a Qui:", value="14:00 às 00:00", key="p2_dob_sq")
            with c_dob2:
                st.session_state["dob_h_ss"] = st.text_input("Sexta e Sáb:", value="18:00 às 04:00", key="p2_dob_ss")
            with c_dob3:
                st.session_state["dob_h_dom"] = st.text_input("Domingo:", value="18:00 às 02:00", key="p2_dob_dom")
            with c_dob4:
                st.session_state["dob_sem_ini"] = st.selectbox("Semana Inicial:", ["SEMANA A", "SEMANA B"], key="p2_dob_sem")

        st.success(f"✅ Configuração do turno `{mod}` da equipe `{st.session_state['equipe_ativa']}` pronta para o Quadro (Passo 5).")