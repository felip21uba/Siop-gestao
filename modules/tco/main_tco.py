from modules.tco.estilo_tco import renderizar_cabecalho_tatico_tco
"""
==============================================================================
🛡️ SIOP PMMG - Módulo TCO / Cadeia de Custódia
Arquivo: modules/tco/main_tco.py (Roteamento Direcionado por Sub-Aba)
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

def renderizar_modulo_tco(subnav_ativo=None, *args, **kwargs):
    """Ponto de entrada do Módulo TCO com direcionamento específico de sub-abas."""
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
    # 📦 CABEÇALHO OPERACIONAL TÁTICO UNIFICADO (FOTO 2)
    # =========================================================================
    renderizar_cabecalho_tatico_tco(usr_logado)

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

    # =========================================================================
    # 🚀 ROTEAMENTO CONDICIONAL
    # =========================================================================
    opcao_menu = subnav_ativo or st.session_state.get("subnav_tco", "📥 Importar REDS")

    if "Importar" in opcao_menu:
        renderizar_aba_importacao(nome_militar_atual, unidade_militar_atual)

    elif "Materiais" in opcao_menu:
        # Foco nos Materiais em Custódia e Histórico Permanente (Abas 1 e 3)
        renderizar_aba_custodia_tramitacao_unificada(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    elif "Tramitação" in opcao_menu:
        # Foco na confirmação e retorno de Órgão Externo (2ª Aba)
        renderizar_aba_custodia_tramitacao_unificada(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    elif "Ofícios" in opcao_menu:
        renderizar_aba_gerador_oficios(all_bens_banco, nome_militar_atual, unidade_militar_atual)

    elif "CREDS" in opcao_menu:
        renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual)

    elif "Auditoria" in opcao_menu:
        renderizar_aba_logs(all_logs_banco)

    elif "Gestores" in opcao_menu:
        renderizar_aba_gestores_creds(nome_militar_atual, unidade_militar_atual, cargo_str, perfil_usuario)

    else:
        renderizar_aba_importacao(nome_militar_atual, unidade_militar_atual)