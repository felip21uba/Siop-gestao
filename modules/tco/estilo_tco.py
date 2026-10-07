"""
==============================================================================
🛡️ SIOP PMMG - Cabeçalho Tático Operacional Dinâmico
Arquivo: modules/tco/estilo_tco.py
==============================================================================
"""

import datetime
from zoneinfo import ZoneInfo
import streamlit as st

FUSO_BR = ZoneInfo("America/Sao_Paulo")

def formatar_matricula_pm(mat: str) -> str:
    """Formata 1764921 para 176.492-1 caso seja numérico."""
    mat_limpa = "".join(filter(str.isalnum, str(mat)))
    if len(mat_limpa) == 7:
        return f"{mat_limpa[:3]}.{mat_limpa[3:6]}-{mat_limpa[6]}"
    return str(mat)

def renderizar_cabecalho_tatico_tco(usr_dados: dict):
    """
    Renderiza o cabeçalho tático com as cores dos botões da sidebar e dados 100% dinâmicos.
    """
    # 1. Extração Dinâmica do Operador
    posto_grad = str(usr_dados.get("cargo_funcao") or usr_dados.get("posto_grad") or "").strip().upper()
    nome_guerra = str(usr_dados.get("nome_guerra") or usr_dados.get("nome_completo") or "OPERADOR").strip().upper()
    
    if posto_grad and not nome_guerra.startswith(posto_grad):
        militar_completo = f"{posto_grad} {nome_guerra}"
    else:
        militar_completo = nome_guerra

    # 2. Extração Dinâmica da Matrícula
    mat_raw = str(
        usr_dados.get("num_policia") 
        or usr_dados.get("usuario_login") 
        or usr_dados.get("usuario") 
        or "N/I"
    ).strip()
    matricula_fmt = formatar_matricula_pm(mat_raw)

    # 3. Extração Dinâmica da Unidade
    unidade_atual = str(
        st.session_state.get("cfg_unidade") 
        or usr_dados.get("unidade") 
        or "21º BPM"
    ).strip().upper()

    # Montagem da lotação CREDS
    if "21" in unidade_atual and "UBÁ" not in unidade_atual and "UBA" not in unidade_atual:
        tag_local = f"CREDS TCO / {unidade_atual} (Ubá-MG)"
    else:
        tag_local = f"CREDS TCO / {unidade_atual}"

    # 4. Data e Hora Operacional em Tempo Real
    hora_atual = datetime.datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")

    # 5. CSS com as cores dos cards da sidebar (#8c7343 / #a38953 / texto #f7e6d0)
    st.markdown(f"""
    <style>
    .siop-header-container {{
        background: linear-gradient(135deg, #2b231d 0%, #1e1814 100%);
        border: 1.5px solid #6b5735;
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 22px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.45);
    }}

    .siop-header-left {{
        display: flex;
        align-items: center;
        gap: 16px;
    }}

    /* Emblema Escudo - Cor exata dos botões da sidebar */
    .siop-shield-badge {{
        background: linear-gradient(135deg, #8c7343 0%, #6e5932 100%);
        border: 1.5px solid #c5a059;
        border-radius: 10px;
        width: 50px;
        height: 50px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.4);
        flex-shrink: 0;
    }}

    .siop-title-text h1 {{
        font-size: 1.30rem !important;
        font-weight: 800 !important;
        color: #f7e6d0 !important;
        margin: 0 0 3px 0 !important;
        padding: 0 !important;
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    .siop-subtitle-text {{
        font-size: 0.84rem;
        color: #bfa59a;
        margin: 0;
    }}

    .siop-location-tag {{
        color: #c5a059;
        font-weight: 700;
    }}

    .siop-header-right {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}

    /* Relógio Digital Operacional */
    .siop-clock-badge {{
        background: #140f0d;
        border: 1px solid #54432a;
        border-radius: 8px;
        padding: 8px 12px;
        color: #e5c78b;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.86rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 8px;
        white-space: nowrap;
    }}

    .siop-pulse-dot {{
        width: 8px;
        height: 8px;
        background-color: #22c55e;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 6px #22c55e;
    }}

    /* Badge do Militar Logado */
    .siop-user-badge {{
        background: #140f0d;
        border: 1px solid #54432a;
        border-radius: 8px;
        padding: 7px 14px;
        text-align: left;
        line-height: 1.35;
        white-space: nowrap;
    }}

    .siop-user-name {{
        color: #f7e6d0;
        font-size: 0.86rem;
        font-weight: 800;
    }}

    .siop-user-mat {{
        color: #a89389;
        font-size: 0.80rem;
        font-weight: normal;
    }}

    .siop-user-unit {{
        color: #c5a059;
        font-size: 0.76rem;
        font-weight: 700;
    }}

    @media (max-width: 900px) {{
        .siop-header-container {{
            flex-direction: column;
            align-items: flex-start;
        }}
        .siop-header-right {{
            width: 100%;
            justify-content: space-between;
        }}
    }}
    </style>

    <div class="siop-header-container">
        <div class="siop-header-left">
            <div class="siop-shield-badge">🛡️</div>
            <div class="siop-title-text">
                <h1>📦 Custódia de Materiais TCO & Cadeia de Custódia</h1>
                <div class="siop-subtitle-text">
                    SIOP PMMG — Gestão Operacional e Rastreabilidade Imutável • 
                    <span class="siop-location-tag">📍 {tag_local}</span>
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
                    👤 {militar_completo} <span class="siop-user-mat">(Mat. {matricula_fmt})</span>
                </div>
                <div class="siop-user-unit">
                    🏛️ {unidade_atual} — PLANTÃO
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)