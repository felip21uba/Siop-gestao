"""
==============================================================================
🛡️ SIOP PMMG - Identidade Visual & Cabeçalho Operacional TCO
Arquivo: modules/tco/estilo_tco.py (Cores Originais da Aplicação)
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
    """Aplica o design original fiel à paleta fornecida."""
    st.markdown(
        """
    <style>
    /* Cartão Principal do Cabeçalho - Gradiente Original #2c1d18 -> #3e2723 */
    .siop-header-container {
        background: linear-gradient(135deg, #2c1d18 0%, #3e2723 100%);
        border: 1px solid #5d4037;
        border-radius: 10px;
        padding: 14px 20px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    }

    .siop-header-left {
        display: flex;
        align-items: center;
        gap: 14px;
    }

    /* Emblema / Brasão com o tom #8d6e63 e borda #a1887f */
    .siop-shield-badge {
        background-color: #2c1d18;
        border: 1.5px solid #8d6e63;
        border-radius: 8px;
        width: 48px;
        height: 48px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        flex-shrink: 0;
    }

    /* Títulos e Tipografia em Bege Suave (#ffe0b2) */
    .siop-title-text h1 {
        font-size: 1.30rem !important;
        font-weight: 700 !important;
        color: #ffe0b2 !important;
        margin: 0 !important;
        padding: 0 !important;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Subtítulo em Bege Acinzentado (#bcaaa4) */
    .siop-subtitle-text {
        font-size: 0.85rem;
        color: #bcaaa4;
        margin-top: 3px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .siop-location-tag {
        color: #ffe0b2;
        font-weight: 600;
    }

    .siop-header-right {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    /* Relógio Digital Operacional */
    .siop-clock-badge {
        background-color: #1a120f;
        border: 1px solid #4e342e;
        border-radius: 6px;
        padding: 8px 12px;
        color: #ffe0b2;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.86rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 8px;
        white-space: nowrap;
    }

    .siop-pulse-dot {
        width: 8px;
        height: 8px;
        background-color: #4ade80;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 6px #4ade80;
    }

    /* Badge do Usuário (#1a120f com borda #4e342e) */
    .siop-user-badge {
        background-color: #1a120f;
        border: 1px solid #4e342e;
        border-radius: 6px;
        padding: 7px 14px;
        text-align: left;
        line-height: 1.35;
        white-space: nowrap;
    }

    .siop-user-name {
        color: #ffe0b2;
        font-size: 0.86rem;
        font-weight: 700;
    }

    .siop-user-mat {
        color: #bcaaa4;
        font-weight: normal;
        font-size: 0.80rem;
    }

    .siop-user-unit {
        color: #d7ccc8;
        font-size: 0.76rem;
        font-weight: 600;
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
    Renderiza o cabeçalho tático com os dados reais da sessão do militar.
    """
    aplicar_estilo_tco_completo()

    posto_grad = str(
        usr_dados.get("cargo_funcao") or usr_dados.get("posto_grad") or "MILITAR"
    ).strip().upper()
    nome_guerra = str(
        usr_dados.get("nome_guerra") or usr_dados.get("nome_completo") or "OPERADOR"
    ).strip().upper()

    if posto_grad and not nome_guerra.startswith(posto_grad):
        militar_identificacao = f"{posto_grad} {nome_guerra}"
    else:
        militar_identificacao = nome_guerra

    matricula = str(
        usr_dados.get("num_policia")
        or usr_dados.get("usuario_login")
        or usr_dados.get("usuario")
        or "N/I"
    ).strip()

    unidade_sessao = (
        st.session_state.get("cfg_unidade")
        or usr_dados.get("unidade")
        or "35ª CIA PM / 21º BPM"
    )

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