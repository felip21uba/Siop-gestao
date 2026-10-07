"""
==============================================================================
🛡️ SIOP PMMG - Identidade Visual & Cabeçalho Operacional TCO
Arquivo: modules/tco/estilo_tco.py
==============================================================================
"""

import datetime
from zoneinfo import ZoneInfo
import streamlit as st

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def obter_hora_atual_formatada():
    """Retorna data e hora exatas de Brasília formatadas."""
    return datetime.datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")


def aplicar_estilo_tco_completo():
    """Aplica o design militar escuro (marrom/castanho/bege) ao módulo TCO."""
    st.markdown(
        """
    <style>
    /* Cartão Principal do Cabeçalho Tático */
    .siop-header-container {
        background: linear-gradient(135deg, #2b1f1c 0%, #1c1412 100%);
        border: 1px solid #4a342e;
        border-radius: 12px;
        padding: 14px 22px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.45);
    }

    .siop-header-left {
        display: flex;
        align-items: center;
        gap: 16px;
    }

    /* Ícone Escudo / Brasão */
    .siop-shield-badge {
        background: linear-gradient(135deg, #3d2b25 0%, #201715 100%);
        border: 1.5px solid #d4a373;
        border-radius: 10px;
        width: 52px;
        height: 52px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 26px;
        box-shadow: inset 0 0 8px rgba(212, 163, 115, 0.2);
        flex-shrink: 0;
    }

    .siop-title-text h1 {
        font-size: 1.35rem !important;
        font-weight: 800 !important;
        color: #f7e6d0 !important;
        margin: 0 !important;
        padding: 0 !important;
        letter-spacing: 0.3px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .siop-subtitle-text {
        font-size: 0.84rem;
        color: #bfa59a;
        margin-top: 4px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .siop-location-tag {
        color: #d4a373;
        font-weight: 600;
    }

    /* Seção Direita: Relógio e Badge de Usuário */
    .siop-header-right {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    /* Relógio Digital Operacional */
    .siop-clock-badge {
        background: #140d0c;
        border: 1px solid #4a342e;
        border-radius: 8px;
        padding: 8px 14px;
        color: #f0c987;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.88rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 8px;
        box-shadow: inset 0 1px 4px rgba(0,0,0,0.6);
        white-space: nowrap;
    }

    .siop-pulse-dot {
        width: 9px;
        height: 9px;
        background-color: #22c55e;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 6px #22c55e;
    }

    /* Card com Dados do Militar */
    .siop-user-badge {
        background: #160e0d;
        border: 1px solid #4a342e;
        border-radius: 8px;
        padding: 7px 14px;
        text-align: left;
        line-height: 1.35;
        white-space: nowrap;
    }

    .siop-user-name {
        color: #f7e6d0;
        font-size: 0.85rem;
        font-weight: 800;
    }

    .siop-user-mat {
        color: #a38c82;
        font-weight: normal;
        font-size: 0.80rem;
    }

    .siop-user-unit {
        color: #c9b1a7;
        font-size: 0.76rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 5px;
    }

    @media (max-width: 900px) {
        .siop-header-container {
            flex-direction: column;
            align-items: flex-start;
        }
        .siop-header-right {
            width: 100%;
            justify-content: space-between;
        }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def renderizar_cabecalho_tatico_tco(usr_dados: dict):
    """
    Renderiza o cabeçalho idêntico à Foto 2, extraindo dados dinâmicos da sessão.
    """
    aplicar_estilo_tco_completo()

    # Extrai o nome de guerra ou nome completo
    posto_grad = str(
        usr_dados.get("cargo_funcao") or usr_dados.get("posto_grad") or "MILITAR"
    ).strip().upper()
    nome_guerra = str(
        usr_dados.get("nome_guerra") or usr_dados.get("nome_completo") or "OPERADOR"
    ).strip().upper()
    
    # Monta a identificação (Ex: CB PM OPERADOR ou CAP PEREIRA)
    if posto_grad and not nome_guerra.startswith(posto_grad):
        militar_identificacao = f"{posto_grad} {nome_guerra}"
    else:
        militar_identificacao = nome_guerra

    # Matrícula / Nº de Polícia
    matricula = str(
        usr_dados.get("num_policia")
        or usr_dados.get("usuario_login")
        or usr_dados.get("usuario")
        or "N/I"
    ).strip()

    # Unidade / Lotação ativa da sessão
    unidade_sessao = (
        st.session_state.get("cfg_unidade")
        or usr_dados.get("unidade")
        or "35ª CIA PM / 21º BPM"
    )
    
    # Subunidade e Cidade de referência
    local_detalhe = "CREDS TCO / 35ª Cia PM - 21º BPM (Ubá-MG)"
    if "21" in str(unidade_sessao):
        local_detalhe = f"CREDS TCO / {unidade_sessao} (Ubá-MG)"
    else:
        local_detalhe = f"CREDS TCO / {unidade_sessao}"

    hora_atual = obter_hora_atual_formatada()

    html_header = f"""
    <div class="siop-header-container">
        <div class="siop-header-left">
            <div class="siop-shield-badge">🛡️</div>
            <div class="siop-title-text">
                <h1>📦 Custódia de Materiais TCO & Cadeia de Custódia</h1>
                <div class="siop-subtitle-text">
                    SIOP PMMG — Gestão Operacional e Rastreabilidade Imutável • 
                    <span class="siop-location-tag">📍 {local_detalhe}</span>
                </div>
            </div>
        </div>
        <div class="siop-header-right">
            <div class="siop-clock-badge">
                <span class="siop-pulse-dot"></span>
                <span>{hora_atual}</span>
            </div>
            <div class="siop-user-badge">
                <div class="siop-user-name">
                    👤 {militar_identificacao} <span class="siop-user-mat">(Mat. {matricula})</span>
                </div>
                <div class="siop-user-unit">
                    🏛️ {unidade_sessao} — PLANTÃO
                </div>
            </div>
        </div>
    </div>
    """

    st.markdown(html_header, unsafe_allow_html=True)