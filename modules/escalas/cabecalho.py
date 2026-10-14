"""
==============================================================================
Módulo de Cabeçalho Institucional PMMG - Escalas (modules/escalas/cabecalho.py)
Design tático idêntico ao padrão oficial com relógio dinâmico e leitura
direta e fiel da Lotação Real do militar logado.
==============================================================================
"""

import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import streamlit.components.v1 as components

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def formatar_matricula_pm(mat: str) -> str:
    """Formata a matrícula funcional de 7 dígitos para o padrão PM (Ex: 1337468 -> 133.746-8)."""
    mat_limpa = "".join(filter(str.isalnum, str(mat)))
    if len(mat_limpa) == 7:
        return f"{mat_limpa[:3]}.{mat_limpa[3:6]}-{mat_limpa[6]}"
    return str(mat)


def renderizar_cabecalho_escalas(unidade_lotacao="21º BPM", subunidade_lotacao="", titulo_modulo="Gestão de Escalas & Planejamento Operacional"):
    """
    Renderiza o cabeçalho tático corporativo extraindo a lotação REAL do militar logado.
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

    # LEITURA REAL DA LOTAÇÃO/UNIDADE DO MILITAR (Mesma lógica usada no TCO e na Governança)
    lotacao_real = str(
        usr_dados.get("unidade")
        or usr_dados.get("lotacao")
        or usr_dados.get("subunidade")
        or st.session_state.get("cfg_subunidade")
        or unidade_lotacao
    ).strip().upper()

    # LEITURA REAL DO NÍVEL GERAL DE ACESSO
    nivel_geral = str(
        usr_dados.get("nivel_acesso")
        or usr_dados.get("perfil_escala")
        or usr_dados.get("perfil")
        or usr_dados.get("cargo_funcao")
        or "TROPA"
    ).strip().upper()

    # Mapeamento do Nível Geral para a Função Institucional da PMMG
    mapa_nivel_para_funcao = {
        "CMT_CIA": "COMANDANTE DE CIA",
        "COMANDANTE_CIA": "COMANDANTE DE CIA",
        "GESTOR_CIA": "COMANDANTE DE CIA",
        "CMT_PEL": "COMANDANTE DE PELOTÃO",
        "CMT_PELOTAO": "COMANDANTE DE PELOTÃO",
        "COMANDANTE_PELOTAO": "COMANDANTE DE PELOTÃO",
        "SARGENTIACAO": "SARGENTEAÇÃO",
        "SARGENTEAÇÃO": "SARGENTEAÇÃO",
        "SARGENTEACAO": "SARGENTEAÇÃO",
        "SARGENTEANTE": "SARGENTEAÇÃO",
        "AUXILIAR_CIA": "SARGENTEAÇÃO / AUX. CIA",
        "AUX_P3": "AUXILIAR DA P/3",
        "P3": "AUXILIAR DA P/3",
        "CHEFE_P3": "CHEFE DA P/3",
        "CPU": "COMANDANTE DE POLICIAMENTO URBANO (CPU)",
        "OFICIAL_DIA": "OFICIAL DE DIA",
        "GESTOR_UNIDADE": "COMANDANTE / GESTOR DA UNIDADE",
        "CMT_BATALHAO": "COMANDANTE DE BATALHÃO",
        "PROGRAMADOR": "PROGRAMADOR / DESENVOLVEDOR",
        "ADMIN": "ADMINISTRADOR DO SIOP",
        "OPERADOR": "OPERADOR DE ESCALAS",
        "TROPA": "POLICIAL EM CAMPO / TROPA"
    }

    funcao_exibicao = mapa_nivel_para_funcao.get(nivel_geral, nivel_geral)

    # Identificação tática do local
    if "21" in lotacao_real and "UBÁ" not in lotacao_real and "UBA" not in lotacao_real:
        tag_local = f"{lotacao_real} (Ubá-MG)"
    else:
        tag_local = lotacao_real

    html_cabecalho_escalas = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: transparent;
            }}
            .banner-container {{
                background: linear-gradient(135deg, #7d6539 0%, #63502c 100%);
                border: 2px solid #c5a059;
                border-radius: 12px;
                padding: 14px 20px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.45);
                box-sizing: border-box;
            }}
            .left-box {{
                display: flex;
                align-items: center;
                gap: 16px;
            }}
            .icon-box {{
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
            }}
            .title-txt {{
                font-size: 1.30rem;
                font-weight: 800;
                color: #ffffff;
                margin: 0 0 3px 0;
                padding: 0;
                display: flex;
                align-items: center;
                gap: 8px;
                text-shadow: 0 1px 2px rgba(0,0,0,0.4);
            }}
            .subtitle-txt {{
                font-size: 0.84rem;
                color: #f5ebe0;
                margin: 0;
            }}
            .right-box {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            .clock-box {{
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
            }}
            .green-dot {{
                width: 8px;
                height: 8px;
                background-color: #22c55e;
                border-radius: 50%;
                display: inline-block;
                box-shadow: 0 0 6px #22c55e;
            }}
            .user-box {{
                background: rgba(20, 15, 13, 0.65);
                border: 1px solid #c5a059;
                border-radius: 8px;
                padding: 7px 14px;
                text-align: left;
                line-height: 1.35;
                white-space: nowrap;
            }}
            .user-name {{
                color: #ffffff;
                font-size: 0.86rem;
                font-weight: 800;
            }}
            .user-sub {{
                color: #ffe0b2;
                font-size: 0.76rem;
                font-weight: 700;
            }}
        </style>
    </head>
    <body>
        <div class="banner-container">
            <div class="left-box">
                <div class="icon-box">🛡️</div>
                <div>
                    <div class="title-txt">
                        📅 {titulo_modulo}
                    </div>
                    <div class="subtitle-txt">
                        SIOP PMMG — Gestão Operacional e Rastreabilidade Imutável • 
                        <span style="color: #ffe0b2; font-weight: 700;">📍 {tag_local}</span>
                    </div>
                </div>
            </div>
            <div class="right-box">
                <div class="clock-box">
                    <span class="green-dot"></span>
                    <span id="relogio_escalas_iframe">--/--/---- --:--:--</span>
                </div>
                <div class="user-box">
                    <div class="user-name">
                        👤 {militar_completo} <span style="color: #f5ebe0; font-size: 0.80rem; font-weight: normal;">(Mat. {matricula_fmt})</span>
                    </div>
                    <div class="user-sub">
                        🏛️ {lotacao_real} — {funcao_exibicao}
                    </div>
                </div>
            </div>
        </div>

        <script>
            function atualizarRelogioIframe() {{
                var el = document.getElementById('relogio_escalas_iframe');
                if (el) {{
                    var agora = new Date();
                    var dia = String(agora.getDate()).padStart(2, '0');
                    var mes = String(agora.getMonth() + 1).padStart(2, '0');
                    var ano = agora.getFullYear();
                    var horas = String(agora.getHours()).padStart(2, '0');
                    var minutos = String(agora.getMinutes()).padStart(2, '0');
                    var segundos = String(agora.getSeconds()).padStart(2, '0');
                    el.innerText = dia + '/' + mes + '/' + ano + ' ' + horas + ':' + minutos + ':' + segundos;
                }}
            }}
            atualizarRelogioIframe();
            setInterval(atualizarRelogioIframe, 1000);
        </script>
    </body>
    </html>
    """

    components.html(html_cabecalho_escalas, height=95)