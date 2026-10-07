"""
==============================================================================
🛡️ SIOP PMMG - Identidade Visual, Cabeçalho Tático & Modais com Impressão Real
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
    """Formata matrícula funcional de 7 dígitos para o padrão militar (Ex: 1337468 -> 133.746-8)."""
    mat_limpa = "".join(filter(str.isalnum, str(mat)))
    if len(mat_limpa) == 7:
        return f"{mat_limpa[:3]}.{mat_limpa[3:6]}-{mat_limpa[6]}"
    return str(mat)


def injetar_estilo_cards_selecao_invertida():
    """
    Aplica as cores exatas do Passo 3:
    - Padrão (Sem Seleção): Caqui militar suave (#9e854e) com borda #bfa76f e texto escuro.
    - Selecionado: Marrom oliva escuro (#4a3e20) com borda dourada (#d4af37) e texto bege claro.
    """
    st.markdown("""
    <style>
    /* 1. CARD PADRÃO: Caqui Militar */
    .card-material-item {
        background-color: #9e854e !important;
        border: 1.5px solid #bfa76f !important;
        border-radius: 8px !important;
        padding: 14px 18px !important;
        margin-bottom: 10px !important;
        color: #1b1b1b !important;
        line-height: 1.55 !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.25) !important;
    }
    .card-material-item strong, .card-material-item b {
        color: #000000 !important;
    }
    .card-material-item .tag-codigo, .card-material-item code {
        background-color: #7d6539 !important;
        color: #ffe0b2 !important;
        border: 1px solid #54432a !important;
        padding: 2px 7px !important;
        border-radius: 4px !important;
        font-family: monospace !important;
        font-weight: 700 !important;
    }

    /* 2. CARD MARCADO: Marrom Oliva Militar */
    .card-material-item.selecionado {
        background-color: #4a3e20 !important;
        border: 1.5px solid #d4af37 !important;
        border-radius: 8px !important;
        color: #f7e6d0 !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.55) !important;
    }
    .card-material-item.selecionado strong, .card-material-item.selecionado b {
        color: #ffe0b2 !important;
    }
    .card-material-item.selecionado .tag-codigo, .card-material-item.selecionado code {
        background-color: #2b2313 !important;
        color: #ffe0b2 !important;
        border: 1px solid #c5a059 !important;
    }

    /* 3. BOTÕES NO MESMO PADRÃO DO PASSO 3 */
    div.stButton > button[kind="secondary"] {
        background-color: #9e854e !important;
        color: #1b1b1b !important;
        border: 1.5px solid #bfa76f !important;
        font-weight: 700 !important;
    }
    div.stButton > button[kind="primary"] {
        background-color: #4a3e20 !important;
        color: #ffe0b2 !important;
        border: 1.5px solid #d4af37 !important;
        font-weight: 800 !important;
    }
    </style>
    """, unsafe_allow_html=True)


def renderizar_cabecalho_tatico_tco(usr_dados: dict):
    """
    Renderiza o cabeçalho tático com o card grande na tonalidade caqui bronze do símbolo
    e dados dinâmicos da sessão do militar.
    """
    injetar_estilo_cards_selecao_invertida()

    # 1. Posto e Nome de Guerra
    posto_grad = str(usr_dados.get("cargo_funcao") or usr_dados.get("posto_grad") or "").strip().upper()
    nome_guerra = str(usr_dados.get("nome_guerra") or usr_dados.get("nome_completo") or "OPERADOR").strip().upper()

    if posto_grad and not nome_guerra.startswith(posto_grad):
        militar_completo = f"{posto_grad} {nome_guerra}"
    else:
        militar_completo = nome_guerra

    # 2. Matrícula Funcional formatada
    mat_raw = str(
        usr_dados.get("num_policia")
        or usr_dados.get("usuario_login")
        or usr_dados.get("usuario")
        or "N/I"
    ).strip()
    matricula_fmt = formatar_matricula_pm(mat_raw)

    # 3. Unidade Ativa da Sessão
    unidade_atual = str(
        st.session_state.get("cfg_unidade")
        or usr_dados.get("unidade")
        or "21º BPM"
    ).strip().upper()

    if "21" in unidade_atual and "UBÁ" not in unidade_atual and "UBA" not in unidade_atual:
        tag_local = f"CREDS TCO / {unidade_atual} (Ubá-MG)"
    else:
        tag_local = f"CREDS TCO / {unidade_atual}"

    # 4. Horário de Brasília em tempo real
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
# MODAL 1: CADEIA DE CUSTÓDIA COM TIMELINE E IMPRESSÃO
# ==============================================================================

@st.dialog("🔗 Cadeia de Custódia — Histórico Imutável", width="large")
def modal_cadeia_custodia_timeline(bem: dict):
    """Exibe modal com rastreabilidade vertical do Art. 158-B do CPP e suporte a impressão."""
    num_reds = bem.get("num_reds", "N/I")
    id_bem = str(bem.get("id_bem") or bem.get("id", ""))
    desc = bem.get("descricao", "N/I")
    lacre = bem.get("involucro_lacre", "SEM LACRE")
    autor = bem.get("autores", "N/I")
    custodiante = bem.get("fiel_depositario_atual", "N/I")
    unidade = bem.get("unidade_posse_atual", "N/I")
    fase_atual = bem.get("fase_destinacao") or bem.get("status_tramite") or "Em Custódia"

    # Busca logs reais gravados no Supabase
    logs_todos = carregar_logs_supabase() or []
    logs_especificos = [
        l for l in logs_todos
        if str(l.get("num_reds", "")).strip() == str(num_reds).strip()
        or id_bem in str(l.get("bem_id", ""))
    ]

    if not logs_especificos:
        dt_criacao = bem.get("data_envio_tramite") or bem.get("data_posse_atual") or "Data N/I"
        logs_especificos = [{
            "data_hora": dt_criacao,
            "acao": "Entrada e Acondicionamento Inicial",
            "origem": custodiante,
            "unidade_origem": unidade,
            "detalhe": f"Material registrado no sistema sob custódia de {custodiante}."
        }]

    # Construção dos eventos da timeline
    itens_timeline_html = ""
    for log in logs_especificos:
        dt_raw = log.get("data_hora", "")
        try:
            dt_fmt = pd.to_datetime(dt_raw).strftime("%d/%m/%Y às %H:%M")
        except Exception:
            dt_fmt = str(dt_raw)[:16]

        itens_timeline_html += f"""
        <div style="border-left: 2px solid #c5a059; padding-left: 14px; margin-left: 8px; margin-bottom: 14px; position: relative;">
            <div style="position: absolute; left: -6px; top: 0; width: 10px; height: 10px; border-radius: 50%; background: #c5a059;"></div>
            <div style="background: rgba(30, 24, 20, 0.95); border: 1px solid #54432a; border-radius: 6px; padding: 10px 14px;">
                <span style="color: #c5a059; font-size: 0.80rem; font-weight: 700;">⏱️ {dt_fmt}</span><br/>
                <span style="color: #ffffff; font-size: 0.90rem; font-weight: 700;">{log.get('acao', 'Movimentação')}</span><br/>
                <span style="color: #d7ccc8; font-size: 0.82rem;">Agente Responsável: <b>{log.get('origem', 'Operador')}</b> ({log.get('unidade_origem', 'Unidade')})</span><br/>
                <span style="color: #a89389; font-size: 0.80rem;">{log.get('detalhe', '')}</span>
            </div>
        </div>
        """

    html_completo_timeline = f"""
    <div id="print-area-cadeia" style="font-family: 'Segoe UI', Arial, sans-serif;">
        <div style="background: rgba(20, 15, 13, 0.85); border: 1.5px solid #6b5735; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;">
            <span style="color: #bfa59a; font-size: 0.85rem;">REDS: <b style="color: #ffffff;">{num_reds}</b> | Lacre Oficial: <code style="background: #3e2723; color: #ffe0b2; padding: 2px 6px; border-radius: 4px;">{lacre}</code></span><br/>
            <span style="color: #ffffff; font-size: 0.95rem; font-weight: 700;">Material: {desc} (Qtd: {bem.get('quantidade', 1)} {bem.get('unidade_medida', 'UN')})</span><br/>
            <span style="color: #d7ccc8; font-size: 0.82rem;">Autor da Ocorrência: <b>{autor}</b> | Custodiante Atual: <b style="color: #c5a059;">{custodiante} ({unidade})</b></span><br/>
            <span style="color: #e5c78b; font-size: 0.80rem;">Fase Atual: <b>{fase_atual}</b></span>
        </div>
        <h5 style="color: #c5a059; margin-bottom: 12px;">🔗 Rastreabilidade em Cadeia Fechada (Art. 158-B CPP):</h5>
        {itens_timeline_html}
    </div>
    """

    st.markdown(html_completo_timeline, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col_btn_p, col_btn_f = st.columns([1.5, 1])
    with col_btn_p:
        if st.button("🖨️ Imprimir Rastreabilidade", type="primary", use_container_width=True):
            components.html(f"""
            <script>
                var printContents = `{html_completo_timeline}`;
                var win = window.open('', '', 'height=700,width=900');
                win.document.write('<html><head><title>Cadeia de Custódia - {num_reds}</title>');
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


# ==============================================================================
# MODAL 2: GUIA OFICIAL DE CUSTÓDIA & DEPÓSITO COM DADOS REAIS E IMPRESSÃO
# ==============================================================================

@st.dialog("📄 Termo de Custódia & Depósito PMMG", width="large")
def modal_guia_termo_oficial(bem: dict, operador_nome: str, operador_mat: str, operador_unid: str):
    """Exibe e imprime o Auto de Apreensão e Depósito conforme as normas da PMMG com dados 100% dinâmicos."""
    num_reds = bem.get("num_reds", "N/I")
    lacre = bem.get("involucro_lacre", "SEM LACRE")
    desc = bem.get("descricao", "N/I")
    autor = bem.get("autores", "N/I")
    qtd_val = bem.get("quantidade", 1)
    unid_val = bem.get("unidade_medida", "UN")
    custodiante_real = bem.get("fiel_depositario_atual", "CREDS TCO")
    unidade_posse = bem.get("unidade_posse_atual", operador_unid)
    
    # Extrai o remetente / recebedor real do histórico ou da tramitação
    recebedor_real = bem.get("ultimo_gestor_movimentou") or bem.get("destinatario_pendente") or "Policial Condutor / Recebedor"
    observacao_rec = bem.get("dados_originais_pdf", {}).get("recibo") or ""

    dt_criacao = bem.get("data_envio_tramite") or bem.get("data_posse_atual") or "Data N/I"
    try:
        dt_fmt = pd.to_datetime(dt_criacao).strftime("%d/%m/%Y às %H:%M")
    except Exception:
        dt_fmt = str(dt_criacao)

    mat_operador_fmt = formatar_matricula_pm(operador_mat)

    html_termo = f"""
    <div id="print-area-guia" style="background: #ffffff; color: #111827; padding: 25px; border-radius: 8px; border: 1px solid #d1d5db; font-family: 'Segoe UI', Arial, sans-serif;">
        <div style="text-align: center; border-bottom: 2px solid #111827; padding-bottom: 10px; margin-bottom: 15px;">
            <h4 style="margin: 0; font-size: 0.95rem; color: #111827; text-transform: uppercase;">POLÍCIA MILITAR DE MINAS GERAIS</h4>
            <p style="margin: 3px 0; font-size: 0.80rem; color: #374151;">{operador_unid} • CENTRO DE REGISTRO E CUSTÓDIA DE MATERIAIS DE TCO (CREDS TCO)</p>
            <h3 style="margin: 8px 0 0 0; font-size: 1.1rem; color: #111827; text-transform: uppercase;">AUTO DE APREENSÃO E GUIA DE CADEIA DE CUSTÓDIA</h3>
        </div>
        <p style="font-size: 0.85rem; line-height: 1.6; text-align: justify; color: #1f2937;">
            Certifico que, aos <b>{dt_fmt}</b>, nesta cidade de Ubá/MG, nos termos do Art. 6º, II c/c Arts. 158-A a 158-F do Código de Processo Penal e normativas da PMMG,
            foi devidamente arrecadado, acondicionado e depositado sob guarda o material abaixo caracterizado:
        </p>
        <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; margin: 15px 0; font-size: 0.84rem; line-height: 1.8;">
            • <b>REDS:</b> {num_reds}<br/>
            • <b>NÚMERO DO LACRE INVIOLÁVEL:</b> <span style="font-family: monospace; font-weight: 700;">{lacre}</span><br/>
            • <b>AUTOR/CONDUZIDO:</b> {autor}<br/>
            • <b>DESCRIÇÃO DO OBJETO:</b> {desc}<br/>
            • <b>QUANTIDADE/PESO:</b> {qtd_val} {unid_val}<br/>
            • <b>CUSTODIANTE ATUAL:</b> {custodiante_real} ({unidade_posse})
        </div>
        <p style="font-size: 0.82rem; color: #4b5563; text-align: justify;">
            O presente invólucro encontra-se devidamente lacrado, não apresentando sinais de rompimento ou violação. A integridade física e o trâmite processual ficam asseverados pelo sistema SIOP PMMG.
        </p>
        <div style="margin-top: 40px; display: flex; justify-content: space-around; text-align: center;">
            <div style="border-top: 1px solid #111827; width: 45%; padding-top: 5px; font-size: 0.80rem;">
                <b>{operador_nome} - MAT. {mat_operador_fmt}</b><br/>
                Responsável pelo CREDS TCO / {operador_unid}
            </div>
            <div style="border-top: 1px solid #111827; width: 45%; padding-top: 5px; font-size: 0.80rem;">
                <b>{recebedor_real}</b><br/>
                Policial Condutor / Recebedor
            </div>
        </div>
    </div>
    """

    st.markdown(html_termo, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col_g_print, col_g_close = st.columns([1.5, 1])
    with col_g_print:
        if st.button("🖨️ Imprimir Guia Oficial", type="primary", use_container_width=True):
            components.html(f"""
            <script>
                var printContents = `{html_termo}`;
                var win = window.open('', '', 'height=750,width=900');
                win.document.write('<html><head><title>Guia de Custódia - {num_reds}</title>');
                win.document.write('<style>body{{font-family:Arial,sans-serif;padding:20px;color:#111;background:#fff;}}</style>');
                win.document.write('</head><body>');
                win.document.write(printContents);
                win.document.write('</body></html>');
                win.document.close();
                win.print();
            </script>
            """, height=0)
    with col_g_close:
        if st.button("Fechar Guia", use_container_width=True):
            st.rerun()