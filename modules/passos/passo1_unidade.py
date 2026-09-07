import streamlit as st
from core.database import supabase

def buscar_autoridades_homologadoras():
    if supabase:
        try:
            res = supabase.table("autoridades_homologadoras").select("*").eq("ativo", True).execute()
            if res.data and len(res.data) > 0:
                return res.data
        except Exception:
            pass
    return [
        {"id": "h1", "posto_grad": "CAP QOPM", "nome_guerra": "ARRIGHI", "cargo_funcao": "COMANDANTE DA 35ª CIA PM"},
        {"id": "h2", "posto_grad": "TEN CEL PM", "nome_guerra": "ERICK", "cargo_funcao": "COMANDANTE DO 21º BPM"}
    ]

@st.dialog("🗑️ Gerenciar e Excluir Equipes", width="medium")
def abrir_modal_excluir_equipes():
    st.markdown("##### ⚠️ Clique na lixeira ao lado da equipe para removê-la:")
    equipes = st.session_state.get("lista_equipes", [])
    
    if len(equipes) <= 1:
        st.warning("ℹ️ É necessário manter pelo menos 1 equipe cadastrada no sistema.")
        return

    for eq in equipes:
        c_nome, c_btn = st.columns([3, 1])
        with c_nome:
            st.markdown(f"🛡️ **{eq}**")
        with c_btn:
            if st.button("🗑️ Excluir", key=f"btn_del_eq_modal_{eq}", use_container_width=True):
                st.session_state["lista_equipes"].remove(eq)
                # Reajusta a equipe ativa caso a excluída estivesse selecionada
                if st.session_state.get("equipe_ativa") == eq:
                    st.session_state["equipe_ativa"] = st.session_state["lista_equipes"][0]
                st.success(f"Equipe '{eq}' removida com sucesso!")
                st.rerun()

def renderizar_passo1():
    exp1 = st.expander("📌 PASSO 1: Configuração da Unidade, Homologador e Gestão de Equipes", expanded=True)
    with exp1:
        st.markdown("#### 🏛️ Dados da Unidade Operacional e Autoridade Homologadora")
        lista_homologadores_db = buscar_autoridades_homologadoras()
        col_u1, col_u2, col_u3 = st.columns(3)
        with col_u1:
            st.session_state["cfg_unidade"] = st.text_input("Unidade Operacional:", value=st.session_state.get("cfg_unidade", "21º BPM / 4ª RPM")).strip().upper()
            st.session_state["cfg_subunidade"] = st.text_input("Subunidade / Cia:", value=st.session_state.get("cfg_subunidade", "35ª CIA PM / UBÁ")).strip().upper()
        with col_u2:
            opcoes_homolog = [f"{h['posto_grad']} {h['nome_guerra']} - {h['cargo_funcao']}" for h in lista_homologadores_db]
            st.selectbox("Selecione a Autoridade Homologadora:", opcoes_homolog, index=0)
        with col_u3:
            st.session_state["cfg_brasao_url"] = st.text_input("URL do Brasão / Logo:", value=st.session_state.get("cfg_brasao_url", "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Bras%C3%A3o_PMMG.svg/500px-Bras%C3%A3o_PMMG.svg.png")).strip()
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Salvar Dados da Unidade no Supabase", use_container_width=True):
                st.success("✅ Configurações salvas!")

        st.divider()
        st.markdown("#### 🛡️ Gestão de Equipes e Portfólios")
        col_equipes_disp, col_gestao = st.columns([3.5, 1.2], gap="large")
        with col_equipes_disp:
            st.markdown("**Selecione a equipe ativa para os lançamentos:**")
            equipes = st.session_state.get("lista_equipes", ["ADMINISTRAÇÃO", "SUPERVISÃO", "CPU", "RP"])
            
            # Grade com limite máximo de 5 cards por linha
            max_colunas = 5
            for i in range(0, len(equipes), max_colunas):
                grupo_equipes = equipes[i:i + max_colunas]
                cols = st.columns(max_colunas)
                for idx, eq_nome in enumerate(grupo_equipes):
                    eh_ativa = (eq_nome == st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))
                    with cols[idx]:
                        if st.button(f"🛡️ {eq_nome}", key=f"btn_eq_p1_{eq_nome}", type="primary" if eh_ativa else "secondary", use_container_width=True):
                            st.session_state["equipe_ativa"] = eq_nome
                            st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            st.success(f"📍 Equipe Ativa no Momento: **{st.session_state.get('equipe_ativa', 'ADMINISTRAÇÃO')}**")

        with col_gestao:
            with st.expander("➕ **Cadastrar Nova Equipe**", expanded=False):
                with st.form("form_inserir_equipe_p1", clear_on_submit=True):
                    nova_equipe_input = st.text_input("Nome da Nova Equipe", placeholder="Ex: TM ALPHA, GPMOR").strip().upper()
                    btn_salvar_eq = st.form_submit_button("💾 Inserir Equipe")
                    if btn_salvar_eq and nova_equipe_input:
                        if nova_equipe_input not in st.session_state["lista_equipes"]:
                            st.session_state["lista_equipes"].append(nova_equipe_input)
                            st.session_state["equipe_ativa"] = nova_equipe_input
                            st.success(f"Equipe '{nova_equipe_input}' cadastrada e ativada!")
                            st.rerun()

            if st.button("🗑️ Excluir Equipes", use_container_width=True, key="btn_abrir_modal_del_eq"):
                abrir_modal_excluir_equipes()