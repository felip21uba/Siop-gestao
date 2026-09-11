import streamlit as st

def renderizar_passo1():
    # Garantia de inicialização em segundo plano (sem alterar a interface)
    if "cfg_subunidade" not in st.session_state:
        st.session_state["cfg_subunidade"] = "35ª COMPANHIA DE POLÍCIA MILITAR"

    if "lista_equipes" not in st.session_state or not isinstance(st.session_state["lista_equipes"], list):
        st.session_state["lista_equipes"] = ["EQUIPE ALPHA", "EQUIPE BRAVO", "EQUIPE CHARLIE", "EQUIPE DELTA"]

    st.markdown("### 📌 PASSO 1: Configuração da Unidade & Cadastramento de Equipes")
    
    col1, col2 = st.columns([2, 2], gap="large")

    with col1:
        subunidade_input = st.text_input(
            "Nome da Subunidade / OPM:", 
            value=st.session_state.get("cfg_subunidade", "35ª COMPANHIA DE POLÍCIA MILITAR"),
            key="input_cfg_subunidade"
        ).strip().upper()

        if subunidade_input and subunidade_input != st.session_state["cfg_subunidade"]:
            st.session_state["cfg_subunidade"] = subunidade_input
            st.toast("✅ Subunidade atualizada!", icon="🏢")

    with col2:
        c_add1, c_add2 = st.columns([3, 1])
        with c_add1:
            nova_equipe_input = st.text_input(
                "Nova Equipe:", 
                key="txt_nova_equipe", 
                placeholder="Ex: EQUIPE ECHO"
            ).strip().upper()
        with c_add2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.button("➕ Add", use_container_width=True, key="btn_add_equipe"):
                if nova_equipe_input:
                    if nova_equipe_input not in st.session_state["lista_equipes"]:
                        st.session_state["lista_equipes"].append(nova_equipe_input)
                        st.toast(f"✅ {nova_equipe_input} adicionada!", icon="🛡️")
                        st.rerun()
                    else:
                        st.warning("⚠️ Esta equipe já está cadastrada.")
                else:
                    st.warning("⚠️ Digite o nome da equipe.")

        equipes_atuais = list(st.session_state.get("lista_equipes", []))
        
        for eq in equipes_atuais:
            c_eq1, c_eq2 = st.columns([4, 1])
            with c_eq1:
                st.markdown(f"• **{eq}**")
            with c_eq2:
                if st.button("🗑️", key=f"btn_del_eq_{eq}", help=f"Remover {eq}"):
                    st.session_state["lista_equipes"].remove(eq)
                    st.toast(f"🗑️ {eq} removida!", icon="✅")
                    st.rerun()