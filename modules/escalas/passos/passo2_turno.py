"""
==============================================================================
Módulo do Passo 2 - Gestão de Equipes (Cards) & Modalidades de Turno (Cards)
Lógica visual 100% baseada em Cards Clicáveis para Equipes e Turnos/Ciclos.
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


def renderizar_passo2():
    sub_ativa = st.session_state.get("cfg_subunidade", "111ª CIA PM")

    with st.expander("📌 PASSO 2: Gestão de Equipes, Modalidade do Turno & Horários Operacionais", expanded=True):
        
        # ----------------------------------------------------------------------
        # 1. CARDS CLICÁVEIS DE GESTÃO DE EQUIPES
        # ----------------------------------------------------------------------
        st.markdown(f"##### 👥 **Gestão de Equipes e Empregos Operacionais ({sub_ativa}):**")
        st.caption("Clique no card da equipe desejada para alternar a edição e vincular a modalidade de turno.")

        if "lista_equipes_unidade" not in st.session_state:
            st.session_state["lista_equipes_unidade"] = ["CPU", "RP", "SUPERVISÃO", "ADMINISTRAÇÃO", "TM ALPHA", "GEPAR"]

        if "equipe_ativa" not in st.session_state:
            st.session_state["equipe_ativa"] = "ADMINISTRAÇÃO"

        # EXIBIÇÃO DOS CARDS DE EQUIPES
        lista_eqs = st.session_state["lista_equipes_unidade"]
        cols_cards_eq = st.columns(min(max(len(lista_eqs), 1), 6))

        for idx, eq_item in enumerate(lista_eqs):
            col_target = cols_cards_eq[idx % len(cols_cards_eq)]
            is_ativa = (st.session_state["equipe_ativa"] == eq_item)
            
            tipo_btn = "primary" if is_ativa else "secondary"
            
            with col_target:
                label_card = f"{'🟢 ' if is_ativa else ''}{eq_item}"
                if st.button(label_card, key=f"btn_card_eq_p2_{eq_item}", type=tipo_btn, use_container_width=True):
                    st.session_state["equipe_ativa"] = eq_item
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # ADIÇÃO E EXCLUSÃO DE EQUIPES
        c_add1, c_add2, c_del1, c_del2 = st.columns([2.5, 1.2, 2.5, 1.2])

        with c_add1:
            nova_eq_nome = st.text_input("➕ Criar Nova Equipe:", placeholder="Ex: TÁTICO MÓVEL", key="txt_nova_eq_passo2").strip().upper()
        with c_add2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("➕ Adicionar", use_container_width=True, key="btn_add_eq_passo2"):
                if nova_eq_nome and nova_eq_nome not in st.session_state["lista_equipes_unidade"]:
                    st.session_state["lista_equipes_unidade"].append(nova_eq_nome)
                    st.session_state["equipe_ativa"] = nova_eq_nome
                    st.success(f"✅ Equipe '{nova_eq_nome}' adicionada!")
                    st.rerun()

        with c_del1:
            eq_para_excluir = st.selectbox(
                "🗑️ Remover Equipe Existente:",
                options=st.session_state["lista_equipes_unidade"],
                key="sb_excluir_equipe_p2"
            )
        with c_del2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🗑️ Excluir", use_container_width=True, type="secondary", key="btn_del_eq_passo2"):
                if len(st.session_state["lista_equipes_unidade"]) > 1:
                    st.session_state["lista_equipes_unidade"].remove(eq_para_excluir)
                    if st.session_state["equipe_ativa"] == eq_para_excluir:
                        st.session_state["equipe_ativa"] = st.session_state["lista_equipes_unidade"][0]
                    st.warning(f"🗑️ Equipe '{eq_para_excluir}' removida!")
                    st.rerun()
                else:
                    st.error("⚠️ A lista precisa conter pelo menos uma equipe.")

        st.info(f"🎯 **Equipe Ativa para Lançamento:** `{st.session_state['equipe_ativa']}`")

        st.divider()

        # ----------------------------------------------------------------------
        # 2. CARDS CLICÁVEIS DA MODALIDADE DO TURNO / CICLO
        # ----------------------------------------------------------------------
        st.markdown(f"##### ⏰ **Seleção da Modalidade do Turno / Ciclo ({st.session_state['equipe_ativa']}):**")
        st.caption("Clique no card da modalidade desejada para configurar os horários da equipe ativa.")

        if "modalidade_turno_ativa" not in st.session_state:
            st.session_state["modalidade_turno_ativa"] = "Turno Único / Avulso"

        # EXIBIÇÃO DOS CARDS DAS MODALIDADES DE TURNO
        cols_cards_mod = st.columns(len(MODALIDADES_TURNOS))

        for idx_m, mod_item in enumerate(MODALIDADES_TURNOS):
            col_target_m = cols_cards_mod[idx_m]
            is_mod_ativa = (st.session_state["modalidade_turno_ativa"] == mod_item)
            
            tipo_btn_m = "primary" if is_mod_ativa else "secondary"
            
            with col_target_m:
                label_card_m = f"{'⏰ ' if is_mod_ativa else ''}{mod_item}"
                if st.button(label_card_m, key=f"btn_card_mod_p2_{mod_item}", type=tipo_btn_m, use_container_width=True):
                    st.session_state["modalidade_turno_ativa"] = mod_item
                    st.rerun()

        mod = st.session_state["modalidade_turno_ativa"]
        st.markdown("<br>", unsafe_allow_html=True)

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

        st.success(f"✅ Configuração do turno **{mod}** da equipe **{st.session_state['equipe_ativa']}** pronta para o Quadro (Passo 5).")