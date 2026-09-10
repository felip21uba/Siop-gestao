import streamlit as st
from modules.tco.database import carregar_materiais_supabase, carregar_logs_supabase
from modules.tco.views import (
    renderizar_aba_ingestao,
    renderizar_aba_meus_bens,
    renderizar_aba_transferencias,
    renderizar_aba_creds,
    renderizar_aba_logs
)

def renderizar_modulo_tco():
    """Ponto de entrada do Módulo TCO / Custódia no SIOP."""
    st.title("📋 Custódia de Materiais TCO / JECRIM & Cadeia de Custódia")
    st.caption("Ingestão oficial por recibo JECRIM, rastreabilidade multi-unidades, mídias com SHA-256 e controle do CREDS.")
    st.divider()

    usr_logado = st.session_state.get("usuario_dados", {})
    nome_militar_atual = f"{usr_logado.get('cargo_funcao', 'CB PM')} {usr_logado.get('nome_guerra', 'OPERADOR')}".strip()
    unidade_militar_atual = str(usr_logado.get("unidade", "35ª CIA PM")).strip().upper()
    perfil_usuario = str(usr_logado.get("nivel_acesso", "TROPA")).upper()
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    
    eh_gestor_creds = "PROGRAMADOR" in cargo_str or "ADMIN" in perfil_usuario or "P1" in perfil_usuario or "COMANDANTE" in cargo_str or "CREDS" in perfil_usuario

    st.markdown(f"👤 **Operador Ativo:** `{nome_militar_atual}` | 🏛️ **Unidade Atual:** `{unidade_militar_atual}`")

    # CARREGAMENTO EM TEMPO REAL DO SUPABASE
    all_bens_banco = carregar_materiais_supabase()
    all_logs_banco = carregar_logs_supabase()

    aba1, aba2, aba3, aba4, aba5 = st.tabs([
        "📥 1. Ingestão REDS & Mídias",
        "🎒 2. Meus Materiais em Custódia",
        "🔄 3. Transferência & Aceite Parcial",
        "🏛️ 4. Painel CREDS-TCO (Gestor)",
        "📜 5. Trilha de Auditoria Imutável"
    ])

    with aba1:
        renderizar_aba_ingestao(nome_militar_atual, unidade_militar_atual)

    with aba2:
        renderizar_aba_meus_bens(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    with aba3:
        renderizar_aba_transferencias(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    with aba4:
        renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual)

    with aba5:
        renderizar_aba_logs(all_logs_banco)