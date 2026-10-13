"""
==============================================================================
Módulo de Cabeçalho Institucional PMMG - Escalas (modules/escalas/cabecalho.py)
Design tático idêntico ao padrão oficial do TCO (gradiente caqui/dourado)
com relógio dinâmico em tempo real rodando segundo a segundo.
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
    Renderiza o cabeçalho tático corporativo em HTML/CSS com relógio vivo em tempo real.
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

    if "21" in unidade_atual and "UBÁ" not in unidade_atual and "UBA" not in unidade_atual:
        tag_local = f"{subunidade_atual} / P3/EM/{unidade_atual}/4 RPM (Ubá-MG)"
    else:
        tag_local = f"{subunidade_atual} / P3/EM/{unidade_atual}/4 RPM"

    hora_inicial = datetime.datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")

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
                    📅 {titulo_modulo}
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
                <span id="relogio_escalas_vivo">{hora_inicial}</span>
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
                    🏛️ {subunidade_atual} — PLANTÃO
                </div>
            </div>
        </div>
    </div>

    <script>
    (function() {{
        function atualizarRelogioVivo() {{
            var elemento = document.getElementById('relogio_escalas_vivo');
            if (elemento) {{
                var agora = new Date();
                var dia = String(agora.getDate()).padStart(2, '0');
                var mes = String(agora.getMonth() + 1).padStart(2, '0');
                var ano = agora.getFullYear();
                var horas = String(agora.getHours()).padStart(2, '0');
                var minutos = String(agora.getMinutes()).padStart(2, '0');
                var segundos = String(agora.getSeconds()).padStart(2, '0');
                elemento.innerText = dia + '/' + mes + '/' + ano + ' ' + horas + ':' + minutos + ':' + segundos;
            }}
        }}
        atualizarRelogioVivo();
        if (!window.timerRelogioEscalasVivo) {{
            window.timerRelogioEscalasVivo = setInterval(atualizarRelogioVivo, 1000);
        }}
    }})();
    </script>
    """, unsafe_allow_html=True)