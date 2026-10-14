"""
==============================================================================
Módulo de Estilos e Componentes Visuais do TCO (modules/tco/estilo_tco.py)
Contém o cabeçalho tático oficial (com relógio dinâmico em tempo real isolado) e os
modais da Cadeia de Custódia e Guia Oficial de Depósito.
==============================================================================
"""

import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def formatar_matricula_pm(mat: str) -> str:
    """Formata a matrícula funcional de 7 dígitos para o padrão PM (Ex: 1337468 -> 133.746-8)."""
    mat_limpa = "".join(filter(str.isalnum, str(mat)))
    if len(mat_limpa) == 7:
        return f"{mat_limpa[:3]}.{mat_limpa[3:6]}-{mat_limpa[6]}"
    return str(mat)


def injetar_estilo_passo3_tco():
    """Injeta estilos CSS táticos para os modais e cards do TCO."""
    st.markdown("""
    <style>
        .badge-fase-status {
            background-color: #8c7343 !important;
            color: #ffffff !important;
            border: 1px solid #c5a059 !important;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
        }
        .tag-info-retangulo {
            background-color: #140f0d;
            border: 1px solid #54432a;
            border-radius: 6px;
            padding: 3px 8px;
            color: #ffe0b2;
            font-family: monospace;
            font-size: 0.82rem;
            font-weight: 700;
            display: inline-block;
            margin-right: 4px;
        }
        .timeline-item-box {
            background-color: #1e1814;
            border-left: 4px solid #c5a059;
            padding: 10px 14px;
            margin-bottom: 10px;
            border-radius: 0 6px 6px 0;
        }
    </style>
    """, unsafe_allow_html=True)


def renderizar_cabecalho_tatico_tco(usr_dados: dict):
    """Renderiza o cabeçalho tático operacional oficial do TCO com relógio dinâmico segundo a segundo."""
    injetar_estilo_passo3_tco()

    posto_grad = str(usr_dados.get("cargo_funcao") or usr_dados.get("posto_grad") or "").strip().upper()
    nome_guerra = str(usr_dados.get("nome_guerra") or usr_dados.get("nome_completo") or "OPERADOR").strip().upper()

    if posto_grad and not nome_guerra.startswith(posto_grad):
        militar_completo = f"{posto_grad} {nome_guerra}"
    else:
        militar_completo = nome_guerra

    mat_raw = str(
        usr_dados.get("num_policia")
        or usr_dados.get("usuario_login")
        or usr_dados.get("usuario")
        or "N/I"
    ).strip()
    matricula_fmt = formatar_matricula_pm(mat_raw)

    unidade_atual = str(
        st.session_state.get("cfg_unidade")
        or usr_dados.get("unidade")
        or "21º BPM"
    ).strip().upper()

    # Mapeamento dinâmico da função/perfil do militar
    funcao_militar = str(
        usr_dados.get("perfil_creds")
        or usr_dados.get("funcao")
        or usr_dados.get("cargo_funcao")
        or usr_dados.get("perfil")
        or "OPERADOR TCO"
    ).strip().upper()

    # Formata legendas legíveis se vier código de perfil interno
    mapa_funcoes_legiveis = {
        "GESTOR_UNIDADE": "GESTOR CREDS UNIDADE",
        "GESTOR_CIA": "GESTOR CREDS CIA",
        "OPERADOR": "OPERADOR CREDS",
        "TROPA": "POLICIAL EM CAMPO / TROPA"
    }
    funcao_exibicao = mapa_funcoes_legiveis.get(funcao_militar, funcao_militar)

    if "21" in unidade_atual and "UBÁ" not in unidade_atual and "UBA" not in unidade_atual:
        tag_local = f"CREDS TCO / {unidade_atual} (Ubá-MG)"
    else:
        tag_local = f"CREDS TCO / {unidade_atual}"

    # Renderização HTML + JS do Cabeçalho e Relógio num iframe isolado
    html_cabecalho = f"""
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
                        📦 Custódia de Materiais TCO &amp; Cadeia de Custódia
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
                    <span id="relogio_tco_iframe">--/--/---- --:--:--</span>
                </div>
                <div class="user-box">
                    <div class="user-name">
                        👤 {militar_completo} <span style="color: #f5ebe0; font-size: 0.80rem; font-weight: normal;">(Mat. {matricula_fmt})</span>
                    </div>
                    <div class="user-sub">
                        🏛️ {unidade_atual} — {funcao_exibicao}
                    </div>
                </div>
            </div>
        </div>

        <script>
            function atualizarRelogioIframe() {{
                var el = document.getElementById('relogio_tco_iframe');
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

    components.html(html_cabecalho, height=95)


@st.dialog("🔗 Cadeia de Custódia Imutável (Art. 158-B do CPP)", width="large")
def modal_cadeia_custodia_timeline(item_dados: dict):
    """Exibe a linha do tempo imutável das movimentações do material."""
    num_reds = item_dados.get("num_reds", "N/I")
    desc = item_dados.get("descricao", "N/I")
    id_bem = item_dados.get("id_bem") or item_dados.get("id", "N/I")
    lacre = item_dados.get("involucro_lacre", "SEM LACRE")

    st.markdown(f"##### 📦 Material: **{desc}**")
    st.markdown(f"📄 REDS: **`{num_reds}`** | 🏷️ Invólucro/Lacre: **`{lacre}`** | 🆔 ID Bem: **`{id_bem}`**")
    st.divider()

    from core.database import supabase

    logs = []
    if supabase:
        try:
            res = supabase.table("tco_logs").select("*").eq("num_reds", num_reds).order("data_hora", desc=False).execute()
            logs = res.data or []
        except Exception as e:
            st.error(f"Erro ao buscar histórico: {e}")

    if logs:
        st.markdown("##### 📜 Histórico Sequencial de Rastreabilidade:")
        for idx, l in enumerate(logs):
            dt_raw = l.get("data_hora", "")
            try:
                dt_fmt = pd.to_datetime(dt_raw).strftime("%d/%m/%Y às %H:%M:%S")
            except Exception:
                dt_fmt = str(dt_raw)

            st.markdown(f"""
            <div class="timeline-item-box">
                <strong style="color: #ffe0b2;">#{idx+1} — {l.get('acao', 'EVENTO')}</strong> ({dt_fmt})<br/>
                👤 <strong>Origem:</strong> {l.get('origem', 'N/I')} ({l.get('unidade_origem', 'N/I')}) ➔ 
                🎯 <strong>Destino:</strong> {l.get('destino', 'N/I')} ({l.get('unidade_destino', 'N/I')})<br/>
                📝 <em>{l.get('detalhe', '')}</em>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Nenhum histórico registrado para este material na tabela de auditoria.")


@st.dialog("📄 Guia Oficial de Depósito e Apreensão TCO", width="large")
def modal_guia_termo_oficial(item_dados: dict, nome_operador: str, num_pm_operador: str, unidade_operador: str):
    """Gera e exibe a Guia Oficial de Depósito de Bens Apreendidos."""
    num_reds = item_dados.get("num_reds", "N/I")
    desc = item_dados.get("descricao", "N/I")
    qtd = item_dados.get("quantidade", 1)
    unid = item_dados.get("unidade_medida", "UN")
    lacre = item_dados.get("involucro_lacre", "SEM LACRE")
    autor = item_dados.get("autores", "N/I")
    fiel = item_dados.get("fiel_depositario_atual", nome_operador)
    fase = item_dados.get("fase_destinacao", "Com Fiel Depositário / Policial")
    dt_agora = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

    st.markdown(f"#### 🏛️ TERMO DE FIEL DEPÓSITO E GUARDA DE BENS — REDS {num_reds}")
    
    st.markdown(f"""
    Aos **{datetime.datetime.now().strftime('%d de %B de %Y')}**, na sede da **{unidade_operador}**, o militar 
    **{nome_operador}** (Matrícula {num_pm_operador}) fez a entrega/conferência formal do bem apreendido abaixo discriminado, 
    ficando o depositário **{fiel}** devidamente cientificado da responsabilidade de guarda e conservação da Cadeia de Custódia (Art. 158-A CPP).
    """)

    st.markdown("---")
    st.markdown(f"📦 **Descrição:** {desc}")
    st.markdown(f"📊 **Quantidade:** {qtd} {unid} | 🏷️ **Invólucro/Lacre:** {lacre}")
    st.markdown(f"👤 **Autor/Envolvido:** {autor}")
    st.markdown(f"📍 **Situação Atual:** {fase}")
    st.markdown(f"⏱️ **Data da Emissão:** {dt_agora}")
    st.markdown("---")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.caption("✍️ Assinatura do Fiel Depositário")
        st.markdown(f"______________________________________  \n**{fiel}**")
    with col_g2:
        st.caption("✍️ Assinatura do Responsável pela Custódia")
        st.markdown(f"______________________________________  \n**{nome_operador} ({num_pm_operador})**")