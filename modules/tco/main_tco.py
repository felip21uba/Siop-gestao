"""
==============================================================================
Módulo Principal do TCO (modules/tco/main_tco.py)
Renderiza a barra de navegação superior do módulo TCO e direciona para as abas
de acordo com o perfil de permissão do usuário logado.
==============================================================================
"""

import streamlit as st
from core.permissions import usuario_eh_gestor_creds
from modules.tco.views import (
    renderizar_aba_importacao,
    renderizar_aba_logs,
    renderizar_aba_gestores_creds
)
from modules.tco.views_tramite import renderizar_aba_creds, renderizar_aba_meus_materiais
from modules.tco.views_oficios import renderizar_aba_gerador_oficios


def renderizar_modulo_tco(subnav_ativo: str = "importacao"):
    """
    Controla a exibição das abas do TCO limitando a visualização
    conforme as permissões do usuário logado.
    """
    usr_logado = st.session_state.get("usuario_dados", {})
    eh_gestor = usuario_eh_gestor_creds(usr_logado)

    nome_militar = str(usr_logado.get("nome_guerra") or usr_logado.get("nome") or "MILITAR").upper().strip()
    unidade_militar = str(usr_logado.get("unidade") or "21º BPM").strip()

    # Define as abas permitidas
    if eh_gestor:
        abas_disponiveis = {
            "importacao": "📄 1. Importação REDS",
            "meus_materiais": "📦 2. Meus Materiais",
            "tramitacao": "🔀 3. Tramitação & Custódia",
            "oficios": "📝 4. Gerador de Ofícios",
            "painel_creds": "📊 5. Painel CREDS",
            "auditoria": "📜 6. Trilha de Auditoria",
            "gestores": "👥 7. Gestão de Permissões"
        }
    else:
        abas_disponiveis = {
            "importacao": "📄 1. Importação REDS",
            "meus_materiais": "📦 2. Meus Materiais",
            "tramitacao": "🔀 3. Tramitação & Custódia",
            "oficios": "📝 4. Gerador de Ofícios"
        }

    st.markdown("## 🛡️ Gestão de Termo Circunstanciado de Ocorrência (TCO / CREDS)")
    
    # Barra de navegação por rádio
    opcao_selecionada = st.radio(
        label="Navegação do Módulo TCO",
        options=list(abas_disponiveis.keys()),
        format_func=lambda x: abas_disponiveis[x],
        horizontal=True,
        label_visibility="collapsed",
        key="subnav_tco_radio"
    )

    st.divider()

    # Roteamento das views
    if opcao_selecionada == "importacao":
        renderizar_aba_importacao(nome_militar, unidade_militar)
    elif opcao_selecionada == "meus_materiais":
        renderizar_aba_meus_materiais(nome_militar, unidade_militar)
    elif opcao_selecionada == "tramitacao":
        renderizar_aba_creds(nome_militar, unidade_militar)
    elif opcao_selecionada == "oficios":
        renderizar_aba_gerador_oficios(nome_militar, unidade_militar)
    elif opcao_selecionada == "painel_creds" and eh_gestor:
        renderizar_aba_creds(nome_militar, unidade_militar, visao_gestor_global=True)
    elif opcao_selecionada == "auditoria" and eh_gestor:
        from modules.tco.database import carregar_logs_supabase
        all_logs = carregar_logs_supabase()
        renderizar_aba_logs(all_logs)
    elif opcao_selecionada == "gestores" and eh_gestor:
        renderizar_aba_gestores_creds(nome_militar, unidade_militar)
    else:
        renderizar_aba_importacao(nome_militar, unidade_militar)