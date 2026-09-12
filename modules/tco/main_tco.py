import streamlit as st
from modules.tco.database import carregar_materiais_supabase, carregar_logs_supabase
from modules.tco.views import (
    renderizar_aba_ingestao,
    renderizar_aba_meus_bens,
    renderizar_aba_transferencias,
    renderizar_aba_creds,
    renderizar_aba_logs,
    renderizar_aba_gestores_creds
)
from modules.tco.pdf_generator import renderizar_aba_gerador_oficios
from modules.tco.compliance import (
    verificar_aceite_compliance_supabase,
    exibir_modal_termo_compliance,
    aplicar_estilo_tco
)

def renderizar_modulo_tco():
    """Ponto de entrada do Módulo TCO / Custódia no SIOP."""
    aplicar_estilo_tco()

    usr_logado = st.session_state.get("usuario_dados", {})
    usr_id = str(usr_logado.get("id") or usr_logado.get("usuario_login") or "").strip()
    nome_militar_atual = f"{usr_logado.get('cargo_funcao', 'CB PM')} {usr_logado.get('nome_guerra', 'OPERADOR')}".strip()
    unidade_militar_atual = str(usr_logado.get("unidade", "35ª CIA PM")).strip().upper()
    perfil_usuario = str(usr_logado.get("nivel_acesso", "TROPA")).upper()
    cargo_str = str(usr_logado.get("cargo_funcao", "POLICIAL MILITAR")).upper()

    if not st.session_state.get("termo_compliance_aceito", False):
        if verificar_aceite_compliance_supabase(usr_id):
            st.session_state["termo_compliance_aceito"] = True
        else:
            exibir_modal_termo_compliance(usr_id, nome_militar_atual, cargo_str, unidade_militar_atual)

    st.markdown("### 📦 Custódia de Materiais TCO & Cadeia de Custódia")
    
    col_hdr1, col_hdr2 = st.columns(2)
    with col_hdr1:
        st.markdown(f"👤 **Operador Ativo:** **{nome_militar_atual}**")
    with col_hdr2:
        st.markdown(f"🏛️ **Unidade Atual:** **{unidade_militar_atual}**")

    st.divider()

    eh_gestor_creds = "PROGRAMADOR" in cargo_str or "ADMIN" in perfil_usuario or "P1" in perfil_usuario or "COMANDANTE" in cargo_str or "CREDS" in perfil_usuario

    all_bens_banco = carregar_materiais_supabase()
    all_logs_banco = carregar_logs_supabase()

    aba1, aba2, aba3, aba4, aba5, aba6, aba7 = st.tabs([
        "📥 1. Ingestão REDS & Mídias",
        "🎒 2. Meus Materiais em Custódia",
        "🔄 3. Transferência & Aceite Parcial",
        "📄 4. Gerador de Ofícios (PDF)",
        "🏛️ 5. Painel CREDS-TCO (Gestor)",
        "📜 6. Trilha de Auditoria Imutável",
        "👥 7. Designar Gestores CREDS"
    ])

    with aba1:
        renderizar_aba_ingestao(nome_militar_atual, unidade_militar_atual)

    with aba2:
        renderizar_aba_meus_bens(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    with aba3:
        renderizar_aba_transferencias(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    with aba4:
        renderizar_aba_gerador_oficios(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    with aba5:
        renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual)

    with aba6:
        renderizar_aba_logs(all_logs_banco)

    with aba7:
        renderizar_aba_gestores_creds(nome_militar_atual, unidade_militar_atual, cargo_str, perfil_usuario)