"""
==============================================================================
Módulo de Gestão de Escalas - SIOP PMMG
Arquivo: modules/escalas/__init__.py
==============================================================================
"""

import streamlit as st
from modules.escalas.cabecalho import renderizar_cabecalho_escalas

from modules.escalas.passos.passo1_unidade import renderizar_passo1
from modules.escalas.passos.passo2_turno import renderizar_passo2
from modules.escalas.passos.passo3_efetivo import renderizar_passo3
from modules.escalas.passos.passo4_calendario import renderizar_passo4
from modules.escalas.passos.passo5_quadro import renderizar_passo5
from modules.escalas.passos.passo6_exportar import renderizar_passo6
from modules.escalas.passos.passo7_banco_horas import renderizar_passo7
from modules.escalas.passos.passo8_ferias import renderizar_modulo_ferias_anual


def exibir_modulo_escalas():
    """
    Renderiza o Módulo de Escalas com o Cabeçalho Tático Oficial no topo,
    lendo os dados de login e permissões do utilizador em tempo real.
    """
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    unidade_lotacao = (
        st.session_state.get("cfg_unidade")
        or usr_dados.get("unidade")
        or usr_dados.get("unidade_nome")
        or "21º BPM"
    )

    subunidade_lotacao = (
        st.session_state.get("cfg_subunidade")
        or usr_dados.get("subunidade")
        or usr_dados.get("subunidade_nome")
        or "35ª CIA PM"
    )

    # 1. RENDERIZA O CABEÇALHO TÁTICO CORPORATIVO NO TOPO
    renderizar_cabecalho_escalas(
        unidade_lotacao=unidade_lotacao,
        subunidade_lotacao=subunidade_lotacao,
        titulo_modulo="Gestão de Escalas & Planejamento Operacional"
    )

    # 2. CONTROLE DE NAVEGAÇÃO DOS PASSOS DA ESCALA
    passo_ativo = st.session_state.get("passo_escala_ativo", "VISUALIZAR TODOS")

    if passo_ativo == "PASSO 1: Unidade & Equipes":
        renderizar_passo1()

    elif passo_ativo == "PASSO 2: Turno & Horários":
        renderizar_passo2()

    elif passo_ativo == "PASSO 3: Efetivo & Ausências":
        renderizar_passo3()

    elif passo_ativo == "PASSO 4: Matriz Mensal":
        renderizar_passo4()

    elif passo_ativo == "PASSO 5: Quadro Geral":
        renderizar_passo5()

    elif passo_ativo == "PASSO 6: Exportação & Auditoria":
        renderizar_passo6()

    elif passo_ativo == "PASSO 7: Banco de Horas":
        renderizar_passo7()

    elif passo_ativo == "PASSO 8: Férias Anuais":
        renderizar_modulo_ferias_anual()

    else:
        # VISUALIZAR TODOS OS PASSOS EM SEQUÊNCIA
        renderizar_passo1()
        st.markdown("<br>", unsafe_allow_html=True)
        renderizar_passo2()
        st.markdown("<br>", unsafe_allow_html=True)
        renderizar_passo3()
        st.markdown("<br>", unsafe_allow_html=True)
        renderizar_passo4()
        st.markdown("<br>", unsafe_allow_html=True)
        renderizar_passo5()
        st.markdown("<br>", unsafe_allow_html=True)
        renderizar_passo6()
        st.markdown("<br>", unsafe_allow_html=True)
        renderizar_passo7()
        st.markdown("<br>", unsafe_allow_html=True)
        renderizar_modulo_ferias_anual()