"""
==============================================================================
Módulo de Cabeçalho Institucional PMMG - Escalas (modules/escalas/cabecalho.py)
Design tático idêntico ao padrão oficial, sem iframe, com relógio dinâmico 
em tempo real e paleta de cores do Módulo de Escalas (Azul Corporativo).
==============================================================================
"""

import datetime
from zoneinfo import ZoneInfo
import streamlit as st

FUSO_BR = ZoneInfo("America/Sao_Paulo")

def formatar_matricula_pm(mat: str) -> str:
    """Formata a matrícula funcional de 7 dígitos para o padrão PM (Ex: 1337468 -> 133.746-8)."""
    mat_limpa = "".join(filter(str.isalnum, str(mat)))
    if len(mat_limpa) == 7:
        return f"{mat_limpa[:3]}.{mat_limpa[3:6]}-{mat_limpa[6]}"
    return str(mat)

def renderizar_cabecalho_escalas(unidade_lotacao="21º BPM", subunidade_lotacao="35ª CIA PM", titulo_modulo="Gestão de Escalas & Planejamento Operacional"):
    """
    Renderiza o cabeçalho tático corporativo em HTML/CSS nativo (sem iframe) no tom Azul das Escalas.
    """
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    posto_grad = str(usr_dados.get("cargo_funcao") or usr_dados.get("posto_grad") or "CAP PM").strip().upper()
    nome_guerra = str(usr_dados.get("nome_guerra") or usr_dados.get("nome_completo") or "PEREIRA").strip().upper()

    if posto_grad and not nome_guerra.startswith(posto_grad):
        militar_completo = f"{posto_grad} {nome_guerra}"
    else:
        militar_completo = nome_guerra

    mat_raw = str(
        usr_dados.get("num_policia")
        or usr_dados.get("usuario_login")
        or usr_dados.get("usuario")
        or "1337468"
    ).strip()
    matricula_fmt = formatar_matricula_pm(mat_raw)

    unidade_atual = str(st.session_state.get("cfg_unidade") or unidade_lotacao or "21º BPM").strip().upper()
    subunidade_atual = str(st.session_state.get("cfg_subunidade") or subunidade_lotacao or "35ª CIA PM").strip().upper()

    lotacao_detalhada = f"{subunidade_atual} - P3/EM/{unidade_atual}/4 RPM" if "P3" not in subunidade_atual else subunidade_atual

    st.markdown(f"""
    <div style="
        background-color: #232a35;
        border: 1px solid #3c4858;
        border-radius: 8px;
        padding: 14px 20px;
        margin-bottom: 20px;
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    ">
        <!-- LADO ESQUERDO: INSÍGNIA + TÍTULOS -->
        <div style="display: flex; align-items: center; gap: 14px;">
            <div style="
                width: 44px;
                height: 44px;
                background-color: #1a222d;
                border: 1px solid #5b7fa6;
                border-radius: 6px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #93c5fd;
                font-size: 20px;
                flex-shrink: 0;
            ">
                🛡️
            </div>
            <div>
                <h1 style="
                    font-size: 1.15rem;
                    color: #f0f4f8;
                    margin: 0 0 2px 0;
                    padding: 0;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-weight: 700;
                ">
                    📅 {titulo_modulo}
                </h1>
                <p style="
                    font-size: 0.82rem;
                    color: #94a3b8;
                    margin: 0;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    flex-wrap: wrap;
                ">
                    <span>SIOP PMMG — Gestão Operacional e Rastreabilidade Imutável</span>
                    <span>•</span>
                    <span style="color: #60a5fa; font-weight: 600;">📍 {lotacao_detalhada} (Ubá-MG)</span>
                </p>
            </div>
        </div>

        <!-- LADO DIREITO: RELÓGIO TEMPO REAL E DADOS DO OPERADOR -->
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <div style="
                background-color: #161c24;
                border: 1px solid #334155;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 0.85rem;
                color: #e6dfd5;
                font-family: 'Consolas', 'Courier New', monospace;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 8px;
                white-space: nowrap;
            ">
                <span style="
                    width: 7px;
                    height: 7px;
                    border-radius: 50%;
                    background-color: #22c55e;
                    display: inline-block;
                    box-shadow: 0 0 5px #22c55e;
                "></span>
                <span id="relogio_escalas_nativo">--/--/---- --:--:--</span>
            </div>
            <div style="
                background-color: #161c24;
                border: 1px solid #334155;
                padding: 5px 12px;
                border-radius: 6px;
                font-size: 0.82rem;
                color: #ffffff;
                line-height: 1.25;
                white-space: nowrap;
            ">
                <div style="font-size: 0.82rem; font-weight: 800; color: #ffffff;">
                    <span style="color: #a855f7;">👤</span> {militar_completo} <span style="color: #a39683; font-weight: 500; font-size: 0.78rem;">(Mat. {matricula_fmt})</span>
                </div>
                <div style="font-size: 0.75rem; color: #a39683; font-weight: 600;">
                    🏛️ {lotacao_detalhada} — PLANTÃO
                </div>
            </div>
        </div>
    </div>

    <img src="x" onerror="
        if (!window.relogioEscalasIniciado) {{
            window.relogioEscalasIniciado = true;
            function attRelogio() {{
                var el = document.getElementById('relogio_escalas_nativo');
                if (el) {{
                    var agora = new Date();
                    var d = String(agora.getDate()).padStart(2, '0');
                    var m = String(agora.getMonth() + 1).padStart(2, '0');
                    var a = agora.getFullYear();
                    var h = String(agora.getHours()).padStart(2, '0');
                    var min = String(agora.getMinutes()).padStart(2, '0');
                    var s = String(agora.getSeconds()).padStart(2, '0');
                    el.innerText = d + '/' + m + '/' + a + ' ' + h + ':' + min + ':' + s;
                }}
            }}
            attRelogio();
            setInterval(attRelogio, 1000);
        }}
    " style="display:none;" />
    """, unsafe_allow_html=True)