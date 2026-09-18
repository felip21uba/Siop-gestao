import json
import streamlit as st
from core.database import supabase

def carregar_equipes_persistidas():
    """Carrega as equipes salvas do Supabase ou usa o padrão inicial."""
    if "lista_equipes" not in st.session_state:
        equipes_padrao = ["ADMINISTRAÇÃO", "SUPERVISÃO", "CPU", "RP", "TM ALPHA", "GEPAR"]
        if supabase:
            try:
                res = supabase.table("configuracoes_sistema").select("valor").eq("chave", "lista_equipes_escala").execute()
                if res.data and len(res.data) > 0:
                    st.session_state["lista_equipes"] = json.loads(res.data[0]["valor"])
                else:
                    st.session_state["lista_equipes"] = equipes_padrao
            except Exception:
                st.session_state["lista_equipes"] = equipes_padrao
        else:
            st.session_state["lista_equipes"] = equipes_padrao

def salvar_equipes_persistidas(lista):
    """Persiste a lista de equipes no session_state e no banco de dados Supabase."""
    st.session_state["lista_equipes"] = lista
    if supabase:
        try:
            supabase.table("configuracoes_sistema").upsert({
                "chave": "lista_equipes_escala",
                "valor": json.dumps(lista)
            }).execute()
        except Exception:
            pass

def sincronizar_efetivo_equipe_ativa(eq_nome):
    """Carrega no Passo 3 apenas os militares que pertencem à equipe selecionada no Passo 5."""
    st.session_state["equipe_ativa"] = str(eq_nome)
    chaves = st.session_state.get("militares_no_quadro_chaves", [])
    mils_da_equipe = [
        str(pair[0]) for pair in chaves 
        if isinstance(pair, (tuple, list)) and len(pair) == 2 and str(pair[1]) == str(eq_nome)
    ]
    st.session_state["militares_selecionados_ids"] = mils_da_equipe

def expurgar_equipe_em_cascata(eq_alvo):
    """Exclui a equipe e expurga seus lançamentos sem reatribuir militares automaticamente."""
    eq_alvo_str = str(eq_alvo).strip()

    if "lista_equipes" in st.session_state and eq_alvo_str in st.session_state["lista_equipes"]:
        st.session_state["lista_equipes"].remove(eq_alvo_str)
        salvar_equipes_persistidas(st.session_state["lista_equipes"])

    if st.session_state.get("equipe_ativa") == eq_alvo_str:
        if st.session_state.get("lista_equipes"):
            st.session_state["equipe_ativa"] = st.session_state["lista_equipes"][0]

    chaves_atuais = st.session_state.get("militares_no_quadro_chaves", [])
    novas_chaves = [
        (str(pair[0]), str(pair[1])) for pair in chaves_atuais 
        if isinstance(pair, (tuple, list)) and len(pair) == 2 and str(pair[1]) != eq_alvo_str
    ]
    st.session_state["militares_no_quadro_chaves"] = novas_chaves

    grade = st.session_state.get("grade_escala_lancamentos", {})
    chaves_remover = [k for k in list(grade.keys()) if f"_{eq_alvo_str}_" in k]
    for k in chaves_remover:
        grade.pop(k, None)
    st.session_state["grade_escala_lancamentos"] = grade

    sincronizar_efetivo_equipe_ativa(st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))

    try:
        from modules.escalas.passos.passo5_quadro import executar_auto_save_banco
        executar_auto_save_banco()
    except Exception as ex:
        print(f"Aviso ao salvar auto save no expurgo: {ex}")

@st.dialog("➕ Cadastrar Nova Equipe", width="medium")
def abrir_modal_nova_equipe():
    with st.form("form_inserir_equipe_p1_modal", clear_on_submit=True):
        nova_equipe_input = st.text_input("Nome da Nova Equipe:", placeholder="Ex: TM ALPHA, GEPAR, CPU...").strip().upper()
        btn_salvar_eq = st.form_submit_button("💾 Inserir Equipe", type="primary", use_container_width=True)
        if btn_salvar_eq and nova_equipe_input:
            if nova_equipe_input not in st.session_state["lista_equipes"]:
                st.session_state["lista_equipes"].append(nova_equipe_input)
                salvar_equipes_persistidas(st.session_state["lista_equipes"])
                sincronizar_efetivo_equipe_ativa(nova_equipe_input)
                st.success(f"✅ Equipe '{nova_equipe_input}' cadastrada e salva no banco!")
                st.rerun()
            else:
                st.warning("⚠️ Esta equipe já está cadastrada.")

@st.dialog("🗑️ Gerenciar e Excluir Equipes", width="medium")
def abrir_modal_excluir_equipes():
    st.markdown("##### ⚠️ Clique na lixeira ao lado da equipe para removê-la:")
    st.warning("⚠️ **Atenção:** Ao remover uma equipe, todos os seus turnos serão expurgados da escala.")
    
    carregar_equipes_persistidas()
    equipes = st.session_state["lista_equipes"]
    
    if len(equipes) <= 1:
        st.info("ℹ️ É necessário manter pelo menos 1 equipe cadastrada no sistema.")
        return

    for eq in list(equipes):
        c_nome, c_btn = st.columns([3, 1])
        with c_nome:
            st.markdown(f"🛡️ **{eq}**")
        with c_btn:
            if st.button("🗑️ Excluir", key=f"btn_del_eq_modal_{eq}", use_container_width=True):
                expurgar_equipe_em_cascata(eq)
                st.success(f"Equipe '{eq}' e seus lançamentos foram totalmente removidos!")
                st.rerun()

def renderizar_passo1():
    carregar_equipes_persistidas()
    if "equipe_ativa" not in st.session_state or st.session_state["equipe_ativa"] not in st.session_state["lista_equipes"]:
        st.session_state["equipe_ativa"] = st.session_state["lista_equipes"][0]

    with st.expander("📌 PASSO 1: Configuração da Unidade, Brasão e Gestão de Equipes", expanded=True):
        with st.expander("➕ 🏛️ Dados da Unidade Operacional & Brasão", expanded=False):
            col_u1, col_u2, col_u3 = st.columns([2, 2, 1.2])
            with col_u1:
                st.session_state["cfg_unidade"] = st.text_input("Unidade Operacional:", value=st.session_state.get("cfg_unidade", "21º BPM / 4ª RPM")).strip().upper()
                st.session_state["cfg_subunidade"] = st.text_input("Subunidade / Cia:", value=st.session_state.get("cfg_subunidade", "35ª CIA PM / UBÁ")).strip().upper()
            with col_u2:
                st.session_state["cfg_brasao_url"] = st.text_input("URL do Brasão / Logo:", value=st.session_state.get("cfg_brasao_url", "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Bras%C3%A3o_PMMG.svg/500px-Bras%C3%A3o_PMMG.svg.png")).strip()
            with col_u3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Salvar Dados", use_container_width=True, type="primary"):
                    st.success("✅ Configurações salvas!")

        st.divider()

        st.markdown("#### 🛡️ Gestão de Equipes e Portfólios")
        col_equipes_disp, col_gestao = st.columns([3.5, 1.2], gap="large")
        
        with col_equipes_disp:
            st.markdown("**Selecione a equipe ativa para os lançamentos:**")
            equipes = st.session_state.get("lista_equipes", ["ADMINISTRAÇÃO", "SUPERVISÃO", "CPU", "RP"])
            
            max_colunas = 5
            for i in range(0, len(equipes), max_colunas):
                grupo_equipes = equipes[i:i + max_colunas]
                cols = st.columns(max_colunas)
                for idx, eq_nome in enumerate(grupo_equipes):
                    eh_ativa = (eq_nome == st.session_state.get("equipe_ativa"))
                    with cols[idx]:
                        if st.button(f"🛡️ {eq_nome}", key=f"btn_eq_p1_{eq_nome}", type="primary" if eh_ativa else "secondary", use_container_width=True):
                            sincronizar_efetivo_equipe_ativa(eq_nome)
                            st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            st.success(f"📍 Equipe Ativa no Momento: **{st.session_state.get('equipe_ativa')}**")

        with col_gestao:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Cadastrar Nova Equipe", use_container_width=True, type="primary", key="btn_abrir_modal_add_eq"):
                abrir_modal_nova_equipe()

            if st.button("🗑️ Excluir Equipes", use_container_width=True, key="btn_abrir_modal_del_eq"):
                abrir_modal_excluir_equipes()