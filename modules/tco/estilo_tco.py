"""
==============================================================================
🛡️ SIOP PMMG - Cabeçalho Tático Operacional
Arquivo: modules/tco/estilo_tco.py
==============================================================================
"""

import datetime
from zoneinfo import ZoneInfo
import streamlit as st

FUSO_BR = ZoneInfo("America/Sao_Paulo")

def formatar_matricula_pm(mat: str) -> str:
    """Formata matricula numerica para padrao militar (ex: 1337468 -> 133.746-8)."""
    mat_limpa = "".join(filter(str.isalnum, str(mat)))
    if len(mat_limpa) == 7:
        return f"{mat_limpa[:3]}.{mat_limpa[3:6]}-{mat_limpa[6]}"
    return str(mat)

def renderizar_cabecalho_tatico_tco(usr_dados: dict):
    """
    Renderiza o cabecalho tatico com o card grande na mesma cor exata do simbolo pequeno.
    """
    # 1. Dados dinamicos do Militar
    posto_grad = str(usr_dados.get("cargo_funcao") or usr_dados.get("posto_grad") or "").strip().upper()
    nome_guerra = str(usr_dados.get("nome_guerra") or usr_dados.get("nome_completo") or "OPERADOR").strip().upper()
    
    if posto_grad and not nome_guerra.startswith(posto_grad):
        militar_completo = f"{posto_grad} {nome_guerra}"
    else:
        militar_completo = nome_guerra

    # 2. Matricula formatada
    mat_raw = str(
        usr_dados.get("num_policia") 
        or usr_dados.get("usuario_login") 
        or usr_dados.get("usuario") 
        or "N/I"
    ).strip()
    matricula_fmt = formatar_matricula_pm(mat_raw)

    # 3. Unidade da sessao
    unidade_atual = str(
        st.session_state.get("cfg_unidade") 
        or usr_dados.get("unidade") 
        or "21º BPM"
    ).strip().upper()

    if "21" in unidade_atual and "UBÁ" not in unidade_atual and "UBA" not in unidade_atual:
        tag_local = f"CREDS TCO / {unidade_atual} (Ubá-MG)"
    else:
        tag_local = f"CREDS TCO / {unidade_atual}"

    # 4. Horario de Brasilia em tempo real
    hora_atual = datetime.datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")

    # 5. CARD GRANDE COM A COR EXATA DO SIMBOLO PEQUENO (#7a6237 / #8c7343 e borda #c5a059)
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #7d6539 0%, #63502c 100%);
        border: 2px solid #c5a059;
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 22px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.45);
    ">
        <div style="display: flex; align-items: center; gap: 16px;">
            <div style="
                background: linear-gradient(135deg, #8f7442 0%, #5e4b29 100%);
                border: 1.5px solid #e0c283;
                border-radius: 10px;
                width: 50px;
                height: 50px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                flex-shrink: 0;
            ">🛡️</div>
            <div>
                <h1 style="font-size: 1.30rem; font-weight: 800; color: #ffffff; margin: 0 0 3px 0; padding: 0; display: flex; align-items: center; gap: 8px; text-shadow: 0 1px 2px rgba(0,0,0,0.4);">
                    📦 Custódia de Materiais TCO & Cadeia de Custódia
                </h1>
                <div style="font-size: 0.84rem; color: #f5ebe0; margin: 0;">
                    SIOP PMMG — Gestão Operacional e Rastreabilidade Imutável • 
                    <span style="color: #ffe0b2; font-weight: 700;">📍 {tag_local}</span>
                </div>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="
                background: rgba(20, 15, 13, 0.65);
                border: 1px solid #c5a059;
                border-radius: 8px;
                padding: 8px 12px;
                color: #ffe0b2;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 0.86rem;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 8px;
                white-space: nowrap;
            ">
                <span style="width: 8px; height: 8px; background-color: #22c55e; border-radius: 50%; display: inline-block; box-shadow: 0 0 6px #22c55e;"></span>
                <span>{hora_atual}</span>
            </div>
            <div style="
                background: rgba(20, 15, 13, 0.65);
                border: 1px solid #c5a059;
                border-radius: 8px;
                padding: 7px 14px;
                text-align: left;
                line-height: 1.35;
                white-space: nowrap;
            ">
                <div style="color: #ffffff; font-size: 0.86rem; font-weight: 800;">
                    👤 {militar_completo} <span style="color: #f5ebe0; font-size: 0.80rem; font-weight: normal;">(Mat. {matricula_fmt})</span>
                </div>
                <div style="color: #ffe0b2; font-size: 0.76rem; font-weight: 700;">
                    🏛️ {unidade_atual} — PLANTÃO
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)