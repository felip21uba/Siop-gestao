"""
==============================================================================
🛡️ SIOP PMMG - Módulo TCO / Cadeia de Custódia
Arquivo: modules/tco/main_tco.py (Roteador Integrado com o Menu Lateral)
==============================================================================
"""

import streamlit as st
from modules.tco.database import carregar_materiais_supabase, carregar_logs_supabase
from modules.tco.views import (
    renderizar_aba_importacao,
    renderizar_aba_creds,
    renderizar_aba_logs,
    renderizar_aba_gestores_creds
)
from modules.tco.views_tramitacao_unificada import renderizar_aba_custodia_tramitacao_unificada
from modules.tco.views_oficios import renderizar_aba_gerador_oficios
from modules.tco.compliance import (
    verificar_aceite_compliance_supabase,
    exibir_modal_termo_compliance,
    aplicar_estilo_tco
)

def renderizar_modulo_tco(subnav_ativo="📥 Importar REDS", *args, **kwargs):
    """Ponto de entrada isolado do Módulo TCO / Custódia no SIOP com suporte a subnav."""
    aplicar_estilo_tco()

    usr_logado = st.session_state.get("usuario_dados", {})
    if isinstance(usr_logado, str):
        usr_logado = {"nome_guerra": usr_logado}

    usr_login = str(usr_logado.get("usuario_login") or usr_logado.get("usuario") or "").strip().upper()
    
    nome_militar_atual = f"{usr_logado.get('cargo_funcao', 'CB PM')} {usr_logado.get('nome_guerra', 'OPERADOR')}".strip()
    unidade_militar_atual = str(usr_logado.get("unidade", "35ª CIA PM")).strip().upper()
    perfil_usuario = str(usr_logado.get("nivel_acesso") or usr_logado.get("perfil") or "TROPA").upper()
    cargo_str = str(usr_logado.get("cargo_funcao", "POLICIAL MILITAR")).upper()

    # =========================================================================
    # 🔒 BLOQUEIO ABSOLUTO NO 1º ACESSO (TERMO DE COMPLIANCE)
    # =========================================================================
    termo_ja_aceito = st.session_state.get("termo_compliance_aceito", False)
    if not termo_ja_aceito:
        if verificar_aceite_compliance_supabase(usr_login):
            st.session_state["termo_compliance_aceito"] = True
        else:
            exibir_modal_termo_compliance(usr_login, nome_militar_atual, cargo_str, unidade_militar_atual)
            return

    # =========================================================================
    # 📦 ÁREA LOGADA DO TCO
    # =========================================================================
    st.markdown("### 📦 Custódia de Materiais TCO & Cadeia de Custódia")
    
    with st.container(border=True):
        col_hdr1, col_hdr2 = st.columns(2)
        with col_hdr1:
            st.markdown(f"👤 **Operador Ativo:** **{nome_militar_atual}**")
        with col_hdr2:
            st.markdown(f"🏛️ **Unidade Atual:** **{unidade_militar_atual}**")

    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

    eh_gestor_creds = (
        "PROGRAMADOR" in cargo_str or 
        "DESENVOLVEDOR" in cargo_str or 
        "ADMIN" in perfil_usuario or 
        "PROGRAMADOR" in perfil_usuario or 
        "DESENVOLVEDOR" in perfil_usuario or 
        "P1" in perfil_usuario or 
        "COMANDANTE" in cargo_str or 
        "CREDS" in perfil_usuario or
        "GESTOR" in perfil_usuario
    )

    all_bens_banco = carregar_materiais_supabase() or []
    all_logs_banco = carregar_logs_supabase() or []

    # Captura a sub-aba escolhida
    subnav_selecionado = subnav_ativo or st.session_state.get("subnav_tco", "📥 Importar REDS")

    mapa_indices = {
        "📥 Importar REDS": 0,
        "🎒 Meus Materiais": 1,
        "🔄 Tramitação": 1,
        "📄 Ofícios": 2,
        "🏛️ Painel CREDS": 3,
        "📜 Auditoria": 4,
        "👥 Gestores": 5
    }
    
    idx_aba_ativa = 0
    for chave, idx in mapa_indices.items():
        if chave in subnav_selecionado:
            idx_aba_ativa = idx
            break

    lista_titulos_abas = [
        "📥 Importar REDS",
        "🎒 Custódia & Tramitação",
        "📄 Ofícios",
        "🏛️ Painel CREDS",
        "📜 Auditoria",
        "👥 Gestores"
    ]

    abas = st.tabs(lista_titulos_abas)

    with abas[0]:
        renderizar_aba_importacao(nome_militar_atual, unidade_militar_atual)

    with abas[1]:
        renderizar_aba_custodia_tramitacao_unificada(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    with abas[2]:
        renderizar_aba_gerador_oficios(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    with abas[3]:
        renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual)

    with abas[4]:
        renderizar_aba_logs(all_logs_banco)

    with abas[5]:
        renderizar_aba_gestores_creds(nome_militar_atual, unidade_militar_atual, cargo_str, perfil_usuario)

    st.components.v1.html(
        f"""
        <script>
        setTimeout(function() {{
            const tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
            if (tabs && tabs.length > {idx_aba_ativa}) {{
                tabs[{idx_aba_ativa}].click();
            }}
        }}, 100);
        </script>
        """,
        height=0
    )