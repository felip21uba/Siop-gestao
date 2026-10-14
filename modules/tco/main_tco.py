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
    renderizar_aba_gestores_creds,
    renderizar_aba_painel_creds
)
from modules.tco.views_oficios import renderizar_aba_gerador_oficios
from modules.tco.database import carregar_materiais_supabase, carregar_logs_supabase


def renderizar_modulo_tco(subnav_ativo: str = "importacao"):
    """
    Controla a exibição das abas do TCO limitando a visualização
    conforme as permissões do usuário logado.
    """
    usr_logado = st.session_state.get("usuario_dados", {})
    eh_gestor = usuario_eh_gestor_creds(usr_logado)

    nome_militar = str(usr_logado.get("nome_guerra") or usr_logado.get("nome") or "MILITAR").upper().strip()
    unidade_militar = str(usr_logado.get("unidade") or "21º BPM").strip()

    # Define as abas permitidas estritamente por perfil
    if eh_gestor:
        abas_disponiveis = {
            "importacao": "📄 1. Importação REDS",
            "meus_materiais": "📦 2. Meus Materiais & Custódia",
            "oficios": "📝 3. Gerador de Ofícios",
            "painel_creds": "📊 4. Painel CREDS",
            "auditoria": "📜 5. Trilha de Auditoria",
            "gestores": "👥 6. Gestão de Permissões"
        }
    else:
        # Tropa: visualiza estritamente as abas operacionais
        abas_disponiveis = {
            "importacao": "📄 1. Importação REDS",
            "meus_materiais": "📦 2. Meus Materiais & Custódia",
            "oficios": "📝 3. Gerador de Ofícios"
        }

    st.markdown("## 🛡️ Gestão de Termo Circunstanciado de Ocorrência (TCO / CREDS)")
    
    # Barra de navegação horizontal
    opcao_selecionada = st.radio(
        label="Navegação do Módulo TCO",
        options=list(abas_disponiveis.keys()),
        format_func=lambda x: abas_disponiveis[x],
        horizontal=True,
        label_visibility="collapsed",
        key="subnav_tco_radio"
    )

    st.divider()

    # Carrega apenas os materiais permitidos pelo escopo do usuário
    all_bens_banco = carregar_materiais_supabase(usr_logado)

    # Roteamento seguro das views
    if opcao_selecionada == "importacao":
        renderizar_aba_importacao(nome_militar, unidade_militar)
    elif opcao_selecionada == "meus_materiais":
        renderizar_aba_painel_creds(all_bens_banco, nome_militar, unidade_militar)
    elif opcao_selecionada == "oficios":
        renderizar_aba_gerador_oficios(all_bens_banco, nome_militar, unidade_militar)
    elif opcao_selecionada == "painel_creds" and eh_gestor:
        renderizar_aba_painel_creds(all_bens_banco, nome_militar, unidade_militar)
    elif opcao_selecionada == "auditoria" and eh_gestor:
        all_logs = carregar_logs_supabase()
        renderizar_aba_logs(all_logs)
    elif opcao_selecionada == "gestores" and eh_gestor:
        renderizar_aba_gestores_creds(nome_militar, unidade_militar)
    else:
        renderizar_aba_importacao(nome_militar, unidade_militar)