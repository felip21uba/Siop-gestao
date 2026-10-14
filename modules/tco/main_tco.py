"""
==============================================================================
Módulo Principal do TCO (modules/tco/main_tco.py)
Renderiza a navegação e direciona para as abas conforme o perfil do usuário.
==============================================================================
"""

import streamlit as st
from core.permissions import usuario_eh_gestor_creds
from modules.tco.views import (
    renderizar_aba_importacao,
    renderizar_aba_logs,
    renderizar_aba_gestores_creds
)
from modules.tco.views_oficios import renderizar_aba_gerador_oficios
from modules.tco.database import carregar_logs_supabase


def renderizar_modulo_tco(subnav_ativo: str = "importacao"):
    """Controla a exibição das abas do TCO conforme as permissões do usuário."""
    usr_logado = st.session_state.get("usuario_dados", {})
    eh_gestor = usuario_eh_gestor_creds(usr_logado)

    nome_militar = str(usr_logado.get("nome_guerra") or usr_logado.get("nome") or "MILITAR").upper().strip()
    unidade_militar = str(usr_logado.get("unidade") or "21º BPM").strip()

    # Define as abas permitidas por perfil
    if eh_gestor:
        abas_disponiveis = {
            "importacao": "📄 1. Importação REDS",
            "oficios": "📝 2. Gerador de Ofícios",
            "auditoria": "📜 3. Trilha de Auditoria",
            "gestores": "👥 4. Gestão de Permissões"
        }
    else:
        abas_disponiveis = {
            "importacao": "📄 1. Importação REDS",
            "oficios": "📝 2. Gerador de Ofícios"
        }

    st.markdown("## 🛡️ Gestão de Termo Circunstanciado de Ocorrência (TCO / CREDS)")
    
    opcao_selecionada = st.radio(
        label="Navegação do Módulo TCO",
        options=list(abas_disponiveis.keys()),
        format_func=lambda x: abas_disponiveis[x],
        horizontal=True,
        label_visibility="collapsed",
        key="subnav_tco_radio"
    )

    st.divider()

    # Roteamento seguro estritamente mapeado nas views existentes
    if opcao_selecionada == "importacao":
        renderizar_aba_importacao(nome_militar, unidade_militar)
    elif opcao_selecionada == "oficios":
        renderizar_aba_gerador_oficios(nome_militar, unidade_militar)
    elif opcao_selecionada == "auditoria" and eh_gestor:
        all_logs = carregar_logs_supabase()
        renderizar_aba_logs(all_logs)
    elif opcao_selecionada == "gestores" and eh_gestor:
        renderizar_aba_gestores_creds(nome_militar, unidade_militar)
    else:
        renderizar_aba_importacao(nome_militar, unidade_militar)