import streamlit as st
import datetime
import pandas as pd
from core.database import supabase

# Configuração da página de teste
st.set_page_config(page_title="Preview Módulo TCO", layout="wide")

# Simulação de usuário logado (Perfil Programador/TI)
if "usuario_dados" not in st.session_state:
    st.session_state["usuario_dados"] = {
        "id": "user_teste_123",
        "nome_guerra": "PROGRAMADOR OLIVEIRA",
        "nivel_acesso": "PROGRAMADOR"
    }

# ESTILO VISUAL: Tons Terrosos e Marrom PMMG
def aplicar_estilo_tco():
    st.markdown("""
        <style>
        .card-tco {
            background-color: #f5f0eb;
            border-left: 6px solid #6c4e31;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 14px;
            color: #1a1a1a;
            box-shadow: 0 2px 5px rgba(0,0,0,0.06);
        }
        .card-tco h5 {
            color: #4a3420;
            font-weight: 700;
            margin-top: 0;
            margin-bottom: 8px;
        }
        .stButton>button {
            border-radius: 6px;
        }
        </style>
    """, unsafe_allow_html=True)

# MODAL: Termo de Sigilo
@st.dialog("🔒 Termo de Ciência, Sigilo e Responsabilidade", width="large")
def exibir_modal_termo_sigilo(usuario_id):
    st.markdown("""
    <div class="card-tco">
        <h5>ATENÇÃO: LEI DE ACESSO À INFORMAÇÃO E SIGILO MIGRATÓRIO/POLICIAL</h5>
        <p>Ao utilizar o módulo TCO do SIOP, o militar declara ciência referente às obrigações da <b>Lei nº 12.527/2011 (LAI)</b>, <b>LGPD</b> e às normas internas da PMMG quanto à preservação da intimidade das partes, dados sensíveis e sigilo das investigações.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.warning("⚠️ **Aviso Legal:** Todas as ações nesta ferramenta são auditadas e vinculadas ao seu número de polícia.")
    
    check_aceite = st.checkbox("Li, compreendo e aceito os termos de sigilo e responsabilidade funcional.")
    
    if st.button("✅ Confirmar Aceite", type="primary", disabled=not check_aceite, use_container_width=True):
        agora = datetime.datetime.now().isoformat()
        if supabase:
            try:
                supabase.table("usuarios").update({
                    "termo_sigilo_aceito": True,
                    "termo_sigilo_data_aceite": agora
                }).eq("id", str(usuario_id)).execute()
            except Exception as e:
                st.error(f"Erro ao gravar no banco: {e}")
        
        st.session_state["termo_sigilo_aceito"] = True
        st.success("Termo assinado com sucesso!")
        st.rerun()

# PAINEL EXCLUSIVO: Compliance do Programador
def renderizar_gestao_compliance_programador():
    usr = st.session_state.get("usuario_dados", {})
    nivel = str(usr.get("nivel_acesso", "")).upper()
    
    if nivel in ["PROGRAMADOR", "ADMIN", "DEV"]:
        with st.expander("🛡️ **Painel de Compliance e Termos Assinados (Gestão TI)**", expanded=True):
            st.caption("Relatório auditável de militares que assinaram o Termo de Ciência e Sigilo.")
            if supabase:
                try:
                    res = supabase.table("usuarios").select(
                        "usuario_login, nome_guerra, cargo_funcao, termo_sigilo_aceito, termo_sigilo_data_aceite"
                    ).eq("termo_sigilo_aceito", True).execute()
                    
                    if res.data:
                        st.dataframe(res.data, use_container_width=True)
                    else:
                        st.info("Nenhum registro de aceite encontrado até o momento no Supabase.")
                except Exception as ex:
                    st.caption(f"Aviso do banco: {ex}")

# TELA PRINCIPAL DE PREVIEW
aplicar_estilo_tco()

st.title("📋 Módulo TCO - Preview de Interface")
st.caption("Ambiente de testes visuais e validação de compliance.")

st.divider()

# Exemplo de Cartão Visual em Tons Terrosos
st.markdown("""
<div class="card-tco">
    <h5>📌 DADOS GERAIS DA OCORRÊNCIA</h5>
    <p><b>BPM / Cia:</b> 21º BPM / 35ª CIA PM &nbsp;|&nbsp; <b>Município:</b> UBÁ &nbsp;|&nbsp; <b>Natureza:</b> Posse de Drogas para Consumo Pessoal</p>
</div>
""", unsafe_allow_html=True)

# Botão para testar o Modal
c1, c2 = st.columns([2, 2])
with c1:
    if st.button("🔒 Abrir Modal de Termo de Sigilo", type="primary", use_container_width=True):
        exhibir_usr_id = st.session_state["usuario_dados"]["id"]
        exibir_modal_termo_sigilo(exhibir_usr_id)

st.markdown("<br>", unsafe_allow_html=True)

# Renderiza o Painel do Programador
renderizar_gestao_compliance_programador()