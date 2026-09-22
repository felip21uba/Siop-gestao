import streamlit as st
import datetime
from modules.governanca.logs import renderizar_aba_trilha_auditoria
from modules.governanca.matriz import renderizar_aba_rbac
from modules.governanca.termos import renderizar_aba_termos

def renderizar_modulo_governanca(usuario_logado: dict = None):
    st.markdown("## 🛡️ Governança, Segurança & Compliance (SIOP)")
    st.caption("Homologado conforme Parte Informativa Nº 12.4/2026 – 35ª Cia PM / 21º BPM")

    # CARDS VISUAIS DE SEGURANÇA ORGANIZADOS POR ESCOPO
    with st.container(border=True):
        st.markdown("#### 🌐 1. Camada de Segurança Global do Sistema")
        col_g1, col_g2, col_g3 = st.columns(3)
        with col_g1:
            st.markdown("**🔐 Autenticação 2FA/TOTP**\n- Authy / Google Authenticator.\n- Dispositivo e sessão única.")
        with col_g2:
            st.markdown("**⏱️ Sessão & Concorrência**\n- Timeout automático de 30 min.\n- Derrubada de acesso concorrente.")
        with col_g3:
            st.markdown("**🛡️ Sanitização & Banco**\n- Anti-XSS / Anti-SQLi.\n- RLS no PostgreSQL/Supabase.")

    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### 📅 2. Travas do Módulo de Escalas")
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            st.markdown("**🚨 Auditoria de Horários**\n- Trava de sobreposição no mesmo dia.\n- Alerta de descanso < 6h.")
        with col_e2:
            st.markdown("**🏖️ Injeção de Férias (Passo 8)**\n- Leitura TXT/SIRH e PDF.\n- Injeção automática no Quadro 5.")
        with col_e3:
            st.markdown("**🔒 Trava de Homologação**\n- Congelamento retroativo.\n- Reabertura restrita a Admins.")

    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### 📦 3. Travas da Cadeia de Custódia (TCO / CREDS)")
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.markdown("**⛓️ Custódia CPP Art. 158-A**\n- Duplo aceite obrigatório.\n- Rastreabilidade irretratável.")
        with col_t2:
            st.markdown("**📄 Chancela & QR Code**\n- Hash SHA-256 no PDF.\n- Validação por órgãos externos.")
        with col_t3:
            st.markdown("**🚨 Trava de Duplicidade**\n- Bloqueio por número do REDS.\n- Registro em `tco_logs` com IP.")

    st.markdown("---")

    aba_doc, aba_matriz, aba_audit, aba_termos = st.tabs([
        "📜 Parte Informativa 12.4/2026",
        "🔑 Matriz RBAC (7 Níveis)",
        "📋 Trilha de Auditoria (Logs)",
        "📝 Termos e Privacidade"
    ])

    with aba_doc:
        st.markdown("### 🏛️ Documento de Conformidade Técnica e Operacional")
        st.info("""
        **21º BATALHÃO DE POLÍCIA MILITAR – 35ª CIA PM**  
        **PARTE INFORMATIVA Nº 12.4/2026**  
        **Do:** OPERADOR SIOP CAP OLIVEIRA ALVES  
        **Ao:** Senhor Comandante do 21º BPM  
        """)

    with aba_matriz:
        renderizar_aba_rbac()

    with aba_audit:
        renderizar_aba_trilha_auditoria()

    with aba_termos:
        renderizar_aba_termos()