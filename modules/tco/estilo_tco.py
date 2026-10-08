"""
==============================================================================
🛡️ SIOP PMMG - Identidade Visual do Passo 3, Cabeçalho Tático, FAV e Guias
Arquivo: modules/tco/estilo_tco.py
==============================================================================
"""

import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from modules.tco.database import carregar_logs_supabase

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def formatar_matricula_pm(mat: str) -> str:
    """Formata matrícula funcional de 7 dígitos para o padrão militar (Ex: 1764921 -> 176.492-1)."""
    mat_limpa = "".join(filter(str.isalnum, str(mat)))
    if len(mat_limpa) == 7:
        return f"{mat_limpa[:3]}.{mat_limpa[3:6]}-{mat_limpa[6]}"
    return str(mat)


def injetar_estilo_passo3_tco():
    """Injeta as cores do Passo 3 das Escalas (Caqui #9e854e e Marrom Oliva #4a3e20) sem alterar fundo global."""
    st.markdown("""
    <style>
    /* 1. Botões nos Tons do Passo 3 */
    div.stButton > button[kind="secondary"] {
        background-color: #9e854e !important;
        color: #1b1b1b !important;
        border: 1.5px solid #bfa76f !important;
        font-weight: 700 !important;
        border-radius: 6px !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #4a3e20 !important;
        color: #ffe0b2 !important;
        border-color: #d4af37 !important;
    }

    div.stButton > button[kind="primary"] {
        background-color: #4a3e20 !important;
        color: #ffe0b2 !important;
        border: 1.5px solid #d4af37 !important;
        font-weight: 800 !important;
        border-radius: 6px !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #9e854e !important;
        color: #1b1b1b !important;
        border-color: #bfa76f !important;
    }

    /* 2. Caixas de Métricas */
    [data-testid="stMetric"], .stMetric {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        padding: 12px 14px !important;
        border-radius: 8px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.65rem !important;
        font-weight: 800 !important;
        color: #ffe0b2 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #cbd5e1 !important;
    }

    /* 3. Cards Alternados com o Visual Exato */
    .card-material-item {
        border-radius: 8px !important;
        padding: 16px 20px 14px 20px !important;
        margin-bottom: 12px !important;
        line-height: 1.65 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.35) !important;
    }

    .card-material-item.card-par {
        background-color: #231714 !important;
        border: 1.5px solid #3e2a24 !important;
        color: #f5ebe0 !important;
    }
    .card-material-item.card-par b, .card-material-item.card-par strong { 
        color: #ffffff !important; 
    }

    .card-material-item.card-impar {
        background-color: #2b1d18 !important;
        border: 1.5px solid #4a332a !important;
        color: #f5ebe0 !important;
    }
    .card-material-item.card-impar b, .card-material-item.card-impar strong { 
        color: #ffffff !important; 
    }

    /* Caixa Arredondada de Destaque da Data/Hora */
    .caixa-data-destaque {
        background-color: #38241d !important;
        border: 1px solid #4d3329 !important;
        color: #ffe0b2 !important;
        border-radius: 6px !important;
        padding: 2px 10px !important;
        font-size: 0.88rem !important;
        font-weight: 700 !important;
        display: inline-block !important;
        margin-top: 2px !important;
    }

    /* Linha Pontilhada de Auditoria e Responsável */
    .linha-auditoria-div {
        border-top: 1px dashed #4d3329 !important;
        margin-top: 12px !important;
        padding-top: 10px !important;
        font-size: 0.84rem !important;
        color: #d7ccc8 !important;
        display: flex !important;
        align-items: center !important;
        gap: 20px !important;
    }
    .linha-auditoria-div strong, .linha-auditoria-div b { 
        color: #ffe0b2 !important; 
    }

    .badge-creds-status {
        border: 1.5px solid #d4af37 !important;
        background-color: transparent !important;
        color: #ffe0b2 !important;
        border-radius: 8px !important;
        padding: 4px 12px !important;
        font-size: 0.80rem !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
        display: inline-flex !important;
        align-items: center !important;
        text-transform: uppercase !important;
        white-space: nowrap !important;
    }
    </style>
    """, unsafe_allow_html=True)


def renderizar_cabecalho_tatico_tco(usr_dados: dict):
    """Renderiza o cabeçalho tático operacional oficial."""
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

    if "21" in unidade_atual and "UBÁ" not in unidade_atual and "UBA" not in unidade_atual:
        tag_local = f"CREDS TCO / {unidade_atual} (Ubá-MG)"
    else:
        tag_local = f"CREDS TCO / {unidade_atual}"

    hora_atual = datetime.datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")

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


# ==============================================================================
# MODAL 1: 🔗 FAV - RENDERIZAÇÃO CORRETA DOS BLOCOS VERTICAIS
# ==============================================================================

def modal_cadeia_custodia_timeline(bem: dict):
    """Exibe modal com a estrutura vertical de blocos da FAV renderizada perfeitamente."""
    @st.dialog("🔗 FAV — Ficha de Acompanhamento de Vestígio (Art. 158-B CPP)", width="large")
    def _dialog_fav():
        num_reds = str(bem.get("num_reds") or "N/I").strip()
        id_bem = str(bem.get("id_bem") or bem.get("id") or "").strip()
        desc = str(bem.get("descricao") or "N/I").strip()
        lacre = str(bem.get("involucro_lacre") or "SEM LACRE").strip()
        autor = str(bem.get("autores") or "N/I").strip()
        custodiante = str(bem.get("fiel_depositario_atual") or "N/I").strip()
        unidade = str(bem.get("unidade_posse_atual") or "N/I").strip()
        fase_atual = str(bem.get("fase_destinacao") or bem.get("status_tramite") or "Em Custódia").strip()

        logs_todos = carregar_logs_supabase() or []
        logs_especificos = [
            l for l in logs_todos
            if str(l.get("num_reds", "")).strip() == num_reds
            or (id_bem and id_bem in str(l.get("bem_id", "")))
        ]

        if logs_especificos:
            try:
                logs_especificos.sort(key=lambda x: str(x.get("data_hora", "")), reverse=True)
            except Exception:
                pass
        else:
            dt_criacao = bem.get("data_envio_tramite") or bem.get("data_posse_atual") or bem.get("data_ingestao") or "Data N/I"
            logs_especificos = [{
                "data_hora": dt_criacao,
                "acao": "IMPORTAÇÃO / CUSTÓDIA INICIAL",
                "origem": custodiante,
                "unidade_origem": unidade,
                "unidade_destino": unidade,
                "destino": custodiante,
                "detalhe": f"Importação individual do material ({desc} | Qtd: {bem.get('quantidade', 1)} | Lacre: {lacre})"
            }]

        itens_html = []
        for log in logs_especificos:
            dt_raw = log.get("data_hora", "")
            try:
                dt_fmt = pd.to_datetime(dt_raw).strftime("%d/%m/%Y às %H:%M")
            except Exception:
                dt_fmt = str(dt_raw)[:16]

            acao_str = str(log.get("acao", "Movimentação")).strip()
            agente_orig = str(log.get("origem") or "Operador").strip()
            detalhe_str = str(log.get("detalhe") or "").strip()

            if "confirmada por" in detalhe_str.lower():
                partes = detalhe_str.split("confirmada por")
                agente_responsavel = partes[1].split(".")[0].split("|")[0].strip() if len(partes) > 1 else agente_orig
            elif "confirmado pelo operador" in detalhe_str.lower():
                partes = detalhe_str.split("confirmado pelo operador")
                agente_responsavel = partes[1].split(".")[0].split("|")[0].strip() if len(partes) > 1 else agente_orig
            elif agente_orig.startswith("Entregue ao "):
                agente_responsavel = agente_orig.replace("Entregue ao ", "")
            else:
                agente_responsavel = agente_orig

            local_raw = str(log.get("unidade_destino") or log.get("destino") or log.get("unidade_origem") or unidade).strip()
            if "Entregue ao " in local_raw:
                local_raw = local_raw.replace("Entregue ao ", "").split("(Ofício:")[0].strip()

            if any(term in local_raw.upper() for term in ["PERÍCIA", "PCMG", "DELEGACIA", "JECRIM", "FÓRUM", "MINISTÉRIO PÚBLICO", "TRIBUNAL"]):
                local_exibicao = f"CREDS {local_raw}" if not local_raw.startswith("CREDS") else local_raw
            elif local_raw.upper().startswith("CREDS"):
                local_exibicao = local_raw
            elif any(c in local_raw.upper() for c in ["BPM", "CIA", "PEL"]):
                local_exibicao = f"CREDS {local_raw}"
            else:
                local_exibicao = local_raw

            bloco = (
                '<div style="border-left: 2px solid #c5a059; padding-left: 14px; margin-left: 8px; margin-bottom: 14px; position: relative;">'
                '<div style="position: absolute; left: -6px; top: 0; width: 10px; height: 10px; border-radius: 50%; background: #c5a059;"></div>'
                '<div style="background: rgba(30, 24, 20, 0.95); border: 1px solid #54432a; border-radius: 6px; padding: 10px 14px;">'
                f'<span style="color: #c5a059; font-size: 0.80rem; font-weight: 700;">⏱️ {dt_fmt}</span><br/>'
                f'<span style="color: #ffffff; font-size: 0.90rem; font-weight: 700;">{acao_str}</span><br/>'
                f'<span style="color: #d7ccc8; font-size: 0.82rem;">Agente Responsável: <b>{agente_responsavel}</b></span><br/>'
                f'<span style="color: #e5c78b; font-size: 0.82rem; font-weight: 600;">📍 Local: {local_exibicao}</span><br/>'
                f'<span style="color: #a89389; font-size: 0.80rem;">{detalhe_str}</span>'
                '</div>'
                '</div>'
            )
            itens_html.append(bloco)

        corpo_eventos = "".join(itens_html)

        html_fav = (
            '<div id="print-area-fav" style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">'
            '<div style="background: rgba(20, 15, 13, 0.85); border: 1.5px solid #6b5735; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;">'
            f'<span style="color: #bfa59a; font-size: 0.85rem;">REDS: <b style="color: #ffffff;">{num_reds}</b> | Lacre Oficial: <code style="background: #3e2723; color: #ffe0b2; padding: 2px 6px; border-radius: 4px;">{lacre}</code></span><br/>'
            f'<span style="color: #ffffff; font-weight: 700;">Material: {desc} (Qtd: {bem.get("quantidade", 1)} {bem.get("unidade_medida", "UN")})</span><br/>'
            f'<span style="color: #d7ccc8; font-size: 0.82rem;">Autor da Ocorrência: <b>{autor}</b> | Custodiante Atual: <b style="color: #c5a059;">{custodiante} ({unidade})</b></span><br/>'
            f'<span style="color: #e5c78b; font-size: 0.80rem;">Fase Atual: <b>{fase_atual}</b></span>'
            '</div>'
            '<h5 style="color: #c5a059; margin-bottom: 12px;">🔗 Rastreabilidade em Cadeia Fechada (Art. 158-B CPP):</h5>'
            f'{corpo_eventos}'
            '</div>'
        )

        st.markdown(html_fav, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        col_btn_p, col_btn_f = st.columns([1.5, 1])
        with col_btn_p:
            if st.button("🖨️ Imprimir FAV", type="primary", use_container_width=True):
                components.html(f"""
                <script>
                    var printContents = `{html_fav}`;
                    var win = window.open('', '', 'height=700,width=900');
                    win.document.write('<html><head><title>FAV - Cadeia de Custodia - {num_reds}</title>');
                    win.document.write('<style>body{{font-family:Arial,sans-serif;padding:20px;color:#111;background:#fff;}} div{{color:#111 !important;}} span{{color:#111 !important;}} code{{border:1px solid #999;padding:2px 4px;}}</style>');
                    win.document.write('</head><body>');
                    win.document.write(printContents);
                    win.document.write('</body></html>');
                    win.document.close();
                    win.print();
                </script>
                """, height=0)
        with col_btn_f:
            if st.button("Fechar", use_container_width=True):
                st.rerun()

    _dialog_fav()


# ==============================================================================
# MODAL 2: 📄 GUIA OFICIAL DE CUSTÓDIA & DEPÓSITO PMMG (AUTO DE APREENSÃO)
# ==============================================================================

@st.dialog("📄 Auto de Apreensão e Guia de Cadeia de Custódia PMMG", width="large")
def modal_guia_termo_oficial(bem: dict, operador_nome: str, operador_mat: str, operador_unid: str):
    """Exibe e imprime o Auto de Apreensão e Guia Oficial da PMMG com dados reais."""
    if not bem or not isinstance(bem, dict):
        st.error("Não foi possível carregar os dados do material selecionado.")
        return

    # Extração com fallback para todas as variações de chaves do banco
    num_reds = str(bem.get("num_reds") or bem.get("numero_reds") or "N/I").strip()
    lacre_real = str(bem.get("involucro_lacre") or bem.get("involucro") or bem.get("lacre") or "SEM LACRE").strip()
    desc_real = str(bem.get("descricao") or bem.get("material") or "N/I").strip()
    autor_real = str(bem.get("autores") or bem.get("autor") or "AUTOR NÃO INFORMADO").strip()
    
    qtd_val = bem.get("quantidade", 1.0)
    try:
        qtd_val = float(qtd_val)
        if qtd_val.is_integer():
            qtd_val = int(qtd_val)
    except Exception:
        pass
        
    unid_med = str(bem.get("unidade_medida") or bem.get("unidade") or "UN").strip()
    custodiante_real = str(bem.get("fiel_depositario_atual") or bem.get("custodiante") or "CREDS TCO - 35ª CIA PM").strip()

    # Data e hora com fallback
    dt_criacao = bem.get("data_envio_tramite") or bem.get("data_posse_atual") or bem.get("data_ingestao") or bem.get("created_at") or "Data N/I"
    try:
        dt_fmt = pd.to_datetime(dt_criacao).strftime("%d/%m/%Y às %H:%M")
    except Exception:
        dt_fmt = str(dt_criacao)[:16]

    # Busca condutor/relator nos logs do Supabase
    logs_todos = carregar_logs_supabase() or []
    logs_especificos = [l for l in logs_todos if str(l.get("num_reds", "")).strip() == num_reds]
    condutor_real = ""
    for l in logs_especificos:
        orig = str(l.get("origem", ""))
        if "Relator:" in orig:
            condutor_real = orig.split("Relator:")[1].replace(")", "").strip()
            break
        elif l.get("acao") == "IMPORTAÇÃO / CUSTÓDIA INICIAL":
            condutor_real = str(l.get("origem", "")).strip()

    if not condutor_real:
        condutor_real = str(bem.get("ultimo_gestor_movimentou") or f"{operador_nome} - MAT. {formatar_matricula_pm(operador_mat)}").strip()

    mat_operador_fmt = formatar_matricula_pm(operador_mat)

    # Identificador numérico da guia
    id_bruto = str(bem.get("id_bem") or bem.get("id") or "2")
    id_clean = "".join(filter(str.isdigit, id_bruto))
    num_guia = f"{id_clean[-3:] if len(id_clean) >= 3 else '2'}/2026"

    html_termo = f"""
    <div id="print-area-guia" style="background: #ffffff; color: #111827; padding: 25px; border-radius: 8px; border: 1px solid #d1d5db; font-family: 'Segoe UI', Arial, sans-serif;">
        <div style="text-align: center; border-bottom: 2px solid #111827; padding-bottom: 10px; margin-bottom: 15px;">
            <h4 style="margin: 0; font-size: 0.95rem; color: #111827; text-transform: uppercase;">POLÍCIA MILITAR DE MINAS GERAIS</h4>
            <p style="margin: 3px 0; font-size: 0.80rem; color: #374151;">4ª RPM • 21º BATALHÃO DE POLÍCIA MILITAR • 35ª COMPANHIA PM (UBÁ/MG)</p>
            <p style="margin: 1px 0; font-size: 0.78rem; font-weight: 700; color: #1f2937;">CENTRO DE REGISTRO E CUSTÓDIA DE MATERIAIS DE TCO (CREDS TCO)</p>
            <h3 style="margin: 8px 0 0 0; font-size: 1.05rem; color: #111827; text-transform: uppercase;">AUTO DE APREENSÃO E GUIA DE CADEIA DE CUSTÓDIA Nº {num_guia}</h3>
        </div>
        <p style="font-size: 0.85rem; line-height: 1.6; text-align: justify; color: #1f2937;">
            Certifico que, aos <b>{dt_fmt}</b>, nesta cidade de Ubá/MG, nos termos do Art. 6º, II c/c Arts. 158-A a 158-F do Código de Processo Penal e normativas da PMMG,
            foi devidamente arrecadado, acondicionado e depositado sob guarda o material abaixo caracterizado:
        </p>
        <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; margin: 15px 0; font-size: 0.84rem; line-height: 1.8;">
            • <b>REDS:</b> {num_reds}<br/>
            • <b>NÚMERO DO LACRE INVIOLÁVEL:</b> <span style="font-family: monospace; font-weight: 700; background: #e5e7eb; padding: 1px 6px; border-radius: 4px;">{lacre_real}</span><br/>
            • <b>AUTOR/CONDUZIDO:</b> {autor_real}<br/>
            • <b>DESCRIÇÃO DO OBJETO:</b> {desc_real}<br/>
            • <b>QUANTIDADE/PESO:</b> {qtd_val} {unid_med}<br/>
            • <b>CUSTODIANTE ATUAL:</b> {custodiante_real}
        </div>
        <p style="font-size: 0.82rem; color: #4b5563; text-align: justify;">
            O presente invólucro encontra-se devidamente lacrado, não apresentando sinais de rompimento ou violação. A integridade física e o trâmite processual ficam asseverados pelo sistema SIOP PMMG.
        </p>
        <div style="margin-top: 45px; display: flex; justify-content: space-around; text-align: center;">
            <div style="border-top: 1px solid #111827; width: 44%; padding-top: 5px; font-size: 0.80rem;">
                <b>{operador_nome} - MAT. {mat_operador_fmt}</b><br/>
                Responsável pelo CREDS TCO / 35ª Cia PM
            </div>
            <div style="border-top: 1px solid #111827; width: 44%; padding-top: 5px; font-size: 0.80rem;">
                <b>{condutor_real}</b><br/>
                Policial Condutor / Recebedor
            </div>
        </div>
    </div>
    """

    st.markdown(html_termo, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col_g_print, col_g_close = st.columns([1.5, 1])
    with col_g_print:
        if st.button("🖨️ Imprimir Guia Oficial", type="primary", use_container_width=True, key=f"btn_act_print_guia_{id_bruto}"):
            components.html(f"""
            <script>
                var printContents = `{html_termo}`;
                var win = window.open('', '', 'height=750,width=900');
                win.document.write('<html><head><title>Guia de Custodia - {num_reds}</title>');
                win.document.write('<style>body{{font-family:Arial,sans-serif;padding:25px;color:#111;background:#fff;}}</style>');
                win.document.write('</head><body>');
                win.document.write(printContents);
                win.document.write('</body></html>');
                win.document.close();
                win.print();
            </script>
            """, height=0)
    with col_g_close:
        if st.button("Fechar Guia", use_container_width=True, key=f"btn_act_close_guia_{id_bruto}"):
            st.rerun()

    _dialog_guia()