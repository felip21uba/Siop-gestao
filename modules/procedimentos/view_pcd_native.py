"""
==============================================================================
SIOP PMMG - INTERFACE NATIVA DO RITO PCD (PROCESSO DE COMUNICAÇÃO DISCIPLINAR)
Tipografia Padrão: Fonte Rawline 12, Títulos Negrito 15, Assinaturas Finais Centralizadas.
Uploads com leitura de Portaria, Carimbo Fls. Manual sem travas, Dicas da IA e Chat Interativo.
==============================================================================
"""

import streamlit as st
import datetime
import re
from core.database import supabase
from .core.prazos_engine import calcular_prazo_continuo_cedm
from .ritos.pcd.modelos_pcd import (
    renderizar_portaria_despacho,
    renderizar_tav,
    renderizar_termo_oitiva,
    renderizar_relatorio_pcd,
    renderizar_termo_juntada,
    gerar_cabecalho_oficial
)

LISTA_ATOS_PCD = [
    "1. Portaria de Instauração (Anexo)",
    "2. Abertura de Vista Inicial / Notificação",
    "3. Notificação de Testemunha / Envio por E-mail",
    "4. Termo de Oitiva - Testemunha da Administração",
    "5. Termo de Oitiva - Testemunha da Defesa",
    "6. Termo de Oitiva - Interrogatório do Comunicado",
    "7. Termo de Abertura de Vista Final (TAV)",
    "8. Razões Escritas de Defesa (Anexo)",
    "9. Relatório Conclusivo do Encarregado",
    "10. Ofício de Remessa e Encaminhamento"
]

DICAS_IA_POR_ATO = {
    "1. Portaria de Instauração (Anexo)": (
        "📌 **Dica da IA para a Portaria de Instauração (Despacho):**\n"
        "- A Portaria transfere a competência delegatória do Comandante para o encarregado.\n"
        "- **Contagem de Prazo (Art. 86 do CEDM):** O prazo de 15 dias contínuos começa no 1º dia útil subsequente à data em que recebeu formalmente a documentação.\n"
        "- Comunique ao Núcleo de Justiça e Disciplina a data do recebimento para agendamento dos prazos no painel da Unidade."
    ),
    "2. Abertura de Vista Inicial / Notificação": (
        "📌 **Dica da IA para Abertura de Vista Inicial:**\n"
        "- Notifique o militar comunicado com cópia da comunicação disciplinar e da portaria inaugural.\n"
        "- Colha o recibo formal na primeira via. Em caso de recusa, recolha a assinatura de 2 testemunhas que presenciaram o ato."
    ),
    "3. Notificação de Testemunha / Envio por E-mail": (
        "📌 **Dica da IA para Notificação de Testemunhas:**\n"
        "- Se o expediente for transmitido por correio eletrónico institucional (e-mail), anexe o relatório de envio e confirmação de leitura aos autos.\n"
        "- O militar investigado e o seu defensor devem ser cientificados previamente da data e hora da audiência."
    ),
    "4. Termo de Oitiva - Testemunha da Administração": (
        "📌 **Dica da IA para Testemunha de Acusação:**\n"
        "- Inquira as testemunhas da acusação primeiro (limite de até 3 testemunhas no PCD).\n"
        "- Qualifique o depoente com filiação, RG, CPF, endereço e telefones.\n"
        "- Lavre a certidão obrigatória de que o comunicado foi notificado, registando se compareceu ou esteve ausente."
    ),
    "5. Termo de Oitiva - Testemunha da Defesa": (
        "📌 **Dica da IA para Testemunha da Defesa:**\n"
        "- São ouvidas após o término da inquirição das testemunhas da administração.\n"
        "- O encarregado pode indeferir fundamentadamente perguntas impertinentes ou meramente protelatórias."
    ),
    "6. Termo de Oitiva - Interrogatório do Comunicado": (
        "📌 **Dica da IA para o Interrogatório:**\n"
        "- **REGRA DE OURO MAPPA:** O interrogatório do comunicado deve ser impreterivelmente o ÚLTIMO ato oral instrutório.\n"
        "- Informe previamente o direito constitucional ao silêncio sobre o mérito dos factos."
    ),
    "7. Termo de Abertura de Vista Final (TAV)": (
        "📌 **Dica da IA para o TAV Final:**\n"
        "- **Prazo Improrrogável:** 05 (cinco) dias úteis contados a partir da ciência formal (Art. 57, §1º do CEDM).\n"
        "- Alerte expressamente sobre a cominação de preclusão e revelia com nomeação de defensor ad hoc se não apresentar a defesa no prazo."
    ),
    "8. Razões Escritas de Defesa (Anexo)": (
        "📌 **Dica da IA para as Razões de Defesa:**\n"
        "- Faça a juntada da peça de defesa e lavre o Termo de Juntada com a numeração correta das folhas.\n"
        "- Se transcorrer o prazo in albis sem manifestação, certifique a revelia e requisite a nomeação de defensor ad hoc."
    ),
    "9. Relatório Conclusivo do Encarregado": (
        "📌 **Dica da IA para o Relatório do MAPPA:**\n"
        "- Estruture o parecer estritamente nos 6 tópicos do MAPPA.\n"
        "- Limite a análise probatória a 20 linhas por tese/fato apurado, sendo vedada a transcrição integral de depoimentos (não fazer Ctrl+C / Ctrl+V)."
    ),
    "10. Ofício de Remessa e Encaminhamento": (
        "📌 **Dica da IA para o Ofício de Remessa:**\n"
        "- Fechamento dos autos físicos e digitais para devolução formal ao Comandante do Batalhão com indicação da quantidade total de folhas rubricadas."
    )
}


def extrair_metadados_portaria(texto: str) -> dict:
    """Extrai informações cadastrais do despacho caso o encarregado anexe o arquivo da portaria."""
    metadados = {}
    if not texto:
        return metadados

    # Procura número do despacho (ex: 105016/26-RIP/21 BPM)
    m_despacho = re.search(r'(?:DESPACHO\s*N[°º\.]?:\s*)([^\n\r]+)', texto, re.IGNORECASE)
    if m_despacho:
        metadados["numero_despacho"] = m_despacho.group(1).strip()
        metadados["numero_pcd"] = m_despacho.group(1).strip()

    # Procura protocolo SICOR (ex: 2026-000364620)
    m_sicor = re.search(r'(?:Protocolo\s*SICOR:\s*)([0-9\-]+)', texto, re.IGNORECASE)
    if m_sicor:
        metadados["protocolo_sicor"] = m_sicor.group(1).strip()

    # Procura nome do encarregado
    m_enc = re.search(r'(?:Ao\s*n[°º]?\s*[0-9\.\-]+\s*)([^\-\n]+)(?:-\s*Encarregado)', texto, re.IGNORECASE)
    if m_enc:
        metadados["encarregado_posto_nome"] = m_enc.group(1).strip()

    return metadados


def renderizar_notificacao_testemunha_padrao(dados: dict) -> str:
    """Modelo padrão de Notificação de Testemunha com menção a meio eletrónico."""
    cabecalho = gerar_cabecalho_oficial(dados)
    hoje = datetime.date.today()
    dia_str = str(hoje.day).zfill(2)
    mes_extenso = hoje.strftime("%B")
    ano_str = str(hoje.year)
    municipio = dados.get("municipio", "Ubá")
    encarregado = dados.get("encarregado_posto_nome", "Cap PM Felipe de Oliveira Alves Pereira")

    return (
        f"{cabecalho}\n\n"
        f"NOTIFICAÇÃO DE TESTEMUNHA\n\n"
        f"Ao: {dados.get('notif_destinatario_nome', '________________________________________________')}\n"
        f"Cargo/Posto/Graduação: {dados.get('notif_destinatario_cargo', '________________________')} - N.º {dados.get('notif_destinatario_num', '__________')}\n"
        f"Lotação/Endereço: {dados.get('notif_destinatario_unidade', '________________________________')}\n\n"
        f"1. Fica V. S.ª NOTIFICADO(A) a comparecer na sede do {dados.get('unidade_abreviada', 'Quartel do 21º BPM')}, "
        f"situado em {municipio}/MG, no dia {dados.get('notif_data_audiencia', '__/__/____')} às {dados.get('notif_hora_audiencia', '__:__')} horas, "
        f"a fim de prestar depoimento na qualidade de TESTEMUNHA nos autos do Processo Disciplinar n.º {dados.get('numero_pcd', '____/____')}, "
        f"ao qual responde o militar {dados.get('comunicado_posto_nome', '____________________')}.\n\n"
        f"2. Fica advertido de que o não comparecimento injustificado implicará nas sanções legais pertinentes.\n\n"
        f"3. Caso este expediente seja transmitido por correio eletrónico institucional (e-mail), o comprovante de envio e confirmação "
        f"de leitura/entrega servirá como certidão formal de intimação aos autos.\n\n"
        f"Quartel em {municipio}, {dia_str} de {mes_extenso} de {ano_str}.\n\n"
        f"                                ________________________________________________\n"
        f"                                            {encarregado}\n"
        f"                                                    ENCARREGADO\n\n"
        f"CIÊNCIA DO NOTIFICADO:\n"
        f"Em ____/____/________ às ____:____ hs. Assinatura: _____________________________________"
    )


def renderizar_oficio_remessa(dados: dict) -> str:
    """Modelo padrão de Ofício de Remessa dos Autos Conclusos ao Comandante."""
    cabecalho = gerar_cabecalho_oficial(dados)
    hoje = datetime.date.today()
    dia_str = str(hoje.day).zfill(2)
    mes_extenso = hoje.strftime("%B")
    ano_str = str(hoje.year)
    municipio = dados.get("municipio", "Ubá")
    encarregado = dados.get("encarregado_posto_nome", "Cap PM Felipe de Oliveira Alves Pereira")

    return (
        f"{cabecalho}\n\n"
        f"OFÍCIO N.º ______/{ano_str} - PCD\n\n"
        f"Do: Encarregado do Processo de Comunicação Disciplinar n.º {dados.get('numero_pcd', '____/____')}\n"
        f"Ao: Sr. Comandante da Unidade / Autoridade Instauradora\n"
        f"Assunto: Remessa de autos conclusos de Processo Disciplinar\n\n"
        f"Senhor Comandante,\n\n"
        f"1. Cumprimentando-o cordialmente, encaminho a V. S.ª os autos conclusos do Processo Disciplinar n.º {dados.get('numero_pcd', '____/____')}, "
        f"instaurado por meio do Despacho/Portaria de folhas {dados.get('fls_portaria', '02')}, autuado em desfavor do militar {dados.get('comunicado_posto_nome', '________________________')}, "
        f"composto por {dados.get('total_folhas_autos', '____')} folhas devidamente rubricadas e numeradas.\n\n"
        f"2. Na oportunidade, apresento em anexo o Relatório Conclusivo dos trabalhos apuratórios para deliberação, homologação "
        f"e emissão do ato final de Solução da Autoridade.\n\n"
        f"Respeitosamente,\n\n"
        f"                                ________________________________________________\n"
        f"                                            {encarregado}\n"
        f"                                                    ENCARREGADO\n"
    )


def renderizar_regua_ia(calculo_prazo: dict):
    """Exibe o cálculo contínuo do Art. 86 do CEDM no topo."""
    dias_restantes = calculo_prazo.get("dias_restantes", 0)
    status_prazo = calculo_prazo.get("status_prazo", "NO_PRAZO")
    pct = calculo_prazo.get("porcentagem_decorrida", 0.0)

    cor_barra = "#00f0ff"
    if status_prazo == "ALERTA":
        cor_barra = "#f59e0b"
    elif status_prazo in ["CRITICO", "VENCIDO"]:
        cor_barra = "#ef4444"

    st.markdown(f"""
    <div style="background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 12px 18px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 6px;">
            <div style="font-size: 0.85rem; color: #94a3b8;">
                <span style="background: rgba(0,240,255,0.12); color: #00f0ff; padding: 2px 8px; border-radius: 4px; font-weight: bold; border: 1px solid rgba(0,240,255,0.3); margin-right: 8px;">
                    RÉGUA IA - ART. 86 CEDM
                </span>
                Recebimento dos Autos: <b style="color:#f8fafc;">{calculo_prazo.get('data_recebimento')}</b> | 
                Início da Contagem: <b style="color:#f8fafc;">{calculo_prazo.get('inicio_contagem')}</b> | 
                Data Fatal: <b style="color:#f8fafc;">{calculo_prazo.get('data_fatal_real')}</b>
            </div>
            <div style="font-size: 0.9rem; font-weight: bold; color: {cor_barra};">
                ⏳ {dias_restantes} DIAS RESTANTES ({status_prazo})
            </div>
        </div>
        <div style="width: 100%; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden;">
            <div style="width: {pct}%; height: 100%; background: {cor_barra};"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def aplicar_estilo_rawline():
    """Injeta tipografia oficial: Fonte Rawline tamanho 12, títulos 15 negrito e assinaturas centralizadas."""
    st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/rawline');

    /* Editor de texto com tipografia Rawline 12 e títulos 15 negrito */
    textarea[aria-label="Redação da Peça Oficial:"], 
    textarea[aria-label="Termo de Juntada Oficial:"] {
        font-family: 'Rawline', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace !important;
        font-size: 12pt !important;
        line-height: 1.5 !important;
        color: #f8fafc !important;
        background-color: #050914 !important;
        border: 1px solid #334155 !important;
        border-radius: 4px !important;
        padding: 16px !important;
    }
    
    .titulo-ato-negrito-15 {
        font-family: 'Rawline', sans-serif !important;
        font-size: 15pt !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
        letter-spacing: 0.5px !important;
    }
    </style>
    """, unsafe_allow_html=True)


def exibir_view_pcd_nativa(dados_pcd: dict):
    """Página de Trabalho do Encarregado do PCD."""
    aplicar_estilo_rawline()

    data_rec = dados_pcd.get("data_recebimento_autos", datetime.date.today())
    if isinstance(data_rec, str):
        try:
            data_rec = datetime.datetime.strptime(data_rec, "%Y-%m-%d").date()
        except Exception:
            data_rec = datetime.date.today()

    calc_prazo = calcular_prazo_continuo_cedm(data_rec, dados_pcd.get("prazo_dias_estipulado", 15))

    # 1. Régua de Prazos do Art. 86
    renderizar_regua_ia(calc_prazo)

    # 2. Barra de Seleção de Atos e Carimbo Fls. Manual
    col_ato, col_fls, col_salvar = st.columns([3.5, 1.3, 1.2])

    with col_ato:
        ato_selecionado = st.selectbox(
            "📜 Selecionar Ato Processual:",
            LISTA_ATOS_PCD,
            key="sb_selecao_ato_pcd"
        )

    with col_fls:
        # Carimbo Fls. manual: livre para digitação, sem valores pré-fixados
        fls_digitada = st.text_input(
            "📑 Carimbo Fls.:",
            value=st.session_state.get(f"fls_salva_{ato_selecionado}", ""),
            placeholder="Ex: Fls. 01 ou Fls. 03 a 04",
            key=f"input_fls_{ato_selecionado}"
        ).strip()
        st.session_state[f"fls_salva_{ato_selecionado}"] = fls_digitada

    with col_salvar:
        st.write("")
        st.write("")
        if st.button("💾 Salvar Ato", type="primary", use_container_width=True):
            st.session_state[f"texto_salvo_{ato_selecionado}"] = st.session_state.get("texto_editor_atual", "")
            st.toast("✅ Ato processual e carimbo de folhas salvos com sucesso!", icon="💾")

    # 3. Dica da IA para o Ato Selecionado em destaque
    st.info(DICAS_IA_POR_ATO.get(ato_selecionado, "Siga o rito previsto no MAPPA."))

    # 4. Área de Trabalho: Upload de Documentos vs. Redação Oficial
    col_editor, col_ia = st.columns([3.2, 1.8])

    with col_editor:
        # ATOS QUE POSSUEM ARQUIVO FÍSICO / UPLOAD
        if ato_selecionado in [
            "1. Portaria de Instauração (Anexo)",
            "3. Notificação de Testemunha / Envio por E-mail",
            "8. Razões Escritas de Defesa (Anexo)"
        ]:
            st.markdown(f"<div class='titulo-ato-negrito-15'>{ato_selecionado}</div>", unsafe_allow_html=True)
            st.caption("Faça o upload do documento digitalizado ou comprovante de recebimento/leitura de e-mail:")
            
            arquivo_anexo = st.file_uploader(
                f"Anexar Arquivo Digitalizado (PDF, DOCX ou Imagem):",
                type=["pdf", "docx", "png", "jpg", "jpeg"],
                key=f"uploader_{ato_selecionado}"
            )

            if arquivo_anexo is not None:
                st.success(f"📎 Anexo '{arquivo_anexo.name}' carregado aos autos ({arquivo_anexo.size} bytes).")

            st.caption("Termo de Juntada para rubrica nos autos físicos:")
            chave_texto = f"texto_salvo_{ato_selecionado}"
            if chave_texto not in st.session_state:
                st.session_state[chave_texto] = renderizar_termo_juntada({
                    **dados_pcd,
                    "origem_documento_desc": f"referente a {ato_selecionado}",
                    "fls_inicial": fls_digitada or "___",
                    "fls_final": fls_digitada or "___"
                })

            texto_juntada = st.text_area(
                "Termo de Juntada Oficial:",
                value=st.session_state[chave_texto],
                height=320,
                key=f"editor_juntada_{ato_selecionado}"
            )
            st.session_state["texto_editor_atual"] = texto_juntada

        # ATOS DE REDAÇÃO OFICIAL DIRETA
        else:
            chave_texto = f"texto_salvo_{ato_selecionado}"
            if chave_texto not in st.session_state:
                if "Abertura de Vista Inicial" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_tav({
                        **dados_pcd,
                        "anexos_especificados": "Cópia da Portaria inaugural de instauração"
                    })
                elif "Notificação de Testemunha" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_notificacao_testemunha_padrao(dados_pcd)
                elif "Termo de Oitiva - Testemunha da Administração" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_termo_oitiva({
                        **dados_pcd,
                        "ordem_testemunha": "PRIMEIRA TESTEMUNHA (ADMINISTRAÇÃO)",
                        "depoente_nome": "LETÍCIA FELÍCIO PEREIRA DO VALE",
                        "depoente_posto": "Cb PM",
                        "depoente_numero": "150.411-7",
                        "depoimento_corpo_texto": "se recorda do comunicante na 35 Cia; que fez a continência para ele, pois o conhecia da época em que ele era sargento na banda de música do 21 BPM; que há muito tempo não o via e não ouvia falar dele; que não sabia que ele era capitão...",
                        "certidao_presenca_comunicado": "NOTIFICADO PARA ACOMPANHAR A AUDIÇÃO DA TESTEMUNHA, CONFORME FLS. _________ O COMUNICADO NÃO COMPARECEU."
                    })
                elif "Termo de Oitiva - Testemunha da Defesa" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_termo_oitiva({
                        **dados_pcd,
                        "ordem_testemunha": "TESTEMUNHA DA DEFESA",
                        "depoente_nome": "________________________________________",
                        "depoente_posto": "SD/CB/SGT PM",
                        "depoente_numero": "__________",
                        "depoimento_corpo_texto": "PERGUNTADO acerca dos fatos, respondeu que...",
                        "certidao_presenca_comunicado": "O MILITAR COMUNICADO COMPARECEU ACOMPANHADO DE SEU DEFENSOR."
                    })
                elif "Interrogatório do Comunicado" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_termo_oitiva({
                        **dados_pcd,
                        "ordem_testemunha": "MILITAR COMUNICADO (INVESTIGADO)",
                        "depoente_nome": dados_pcd.get("comunicado_nome", "EDSON"),
                        "depoente_posto": dados_pcd.get("comunicado_posto", "Ten PM"),
                        "depoente_numero": dados_pcd.get("comunicado_numero", "150.123-4"),
                        "depoimento_corpo_texto": "Cientificado do teor da portaria e do direito constitucional de permanecer em silêncio quanto ao mérito, respondeu que...",
                        "certidao_presenca_comunicado": "PRESENTE O MILITAR COMUNICADO."
                    })
                elif "TAV" in ato_selecionado or "Final" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_tav(dados_pcd)
                elif "Relatório" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_relatorio_pcd(dados_pcd)
                elif "Ofício" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_oficio_remessa(dados_pcd)
                else:
                    st.session_state[chave_texto] = ""

            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; background:#1e293b; padding:8px 14px; border-radius:4px 4px 0 0;">
                <span class='titulo-ato-negrito-15'>{ato_selecionado}</span>
                <span style="background:#0f172a; color:#00f0ff; padding:2px 8px; border-radius:3px; font-size:0.8rem; font-weight:bold; border:1px solid #334155;">
                    {fls_digitada if fls_digitada else "Sem Fls."}
                </span>
            </div>
            """, unsafe_allow_html=True)

            texto_redigido = st.text_area(
                "Redação da Peça Oficial:",
                value=st.session_state[chave_texto],
                height=560,
                key=f"editor_texto_{ato_selecionado}",
                label_visibility="collapsed"
            )
            st.session_state["texto_editor_atual"] = texto_redigido

    # 5. Painel da IA Interativa (Dúvidas em Tempo Real)
    with col_ia:
        st.markdown("#### 🤖 Assistente Tático Jurídico MAPPA")
        st.caption("Pergunte à IA sobre dúvidas do ato em andamento:")

        if "historico_chat_ia_pcd" not in st.session_state:
            st.session_state["historico_chat_ia_pcd"] = [
                {
                    "role": "assistant",
                    "content": (
                        f"Olá, Encarregado. Estou com os autos do PCD/RIP carregados. "
                        f"Você está trabalhando no ato: **{ato_selecionado}**. Em que posso auxiliar na instrução probatória?"
                    )
                }
            ]

        with st.container(height=430):
            for msg in st.session_state["historico_chat_ia_pcd"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        pergunta_usuario = st.chat_input("Dúvida sobre este ato? Digite aqui...")
        if pergunta_usuario:
            st.session_state["historico_chat_ia_pcd"].append({"role": "user", "content": pergunta_usuario})
            with st.chat_message("user"):
                st.markdown(pergunta_usuario)

            with st.chat_message("assistant"):
                p_up = pergunta_usuario.upper()
                resposta = ""

                if "PRAZO" in p_up or "DIAS" in p_up or "86" in p_up:
                    resposta = (
                        f"**Parecer sobre Prazos (Art. 86 CEDM):**\n"
                        f"- O prazo contínuo de 15 dias do procedimento iniciou em **{calc_prazo.get('inicio_contagem')}** e finda em **{calc_prazo.get('data_fatal_real')}**.\n"
                        f"- Para o TAV de Defesa Prévia, o prazo é improrrogável de **5 dias úteis** contados a partir da ciência formal do militar."
                    )
                elif "PORTARIA" in p_up or "DESPACHO" in p_up or "DELEGA" in p_up:
                    resposta = (
                        "**Orientações sobre o Despacho/Portaria:**\n"
                        "O Despacho nº 105016/26-RIP/21 BPM delega competência expressa com fulcro no art. 107 do MAPPA. "
                        "Certifique-se de autuar o documento como Folha 01/02 e comunicar formalmente o Núcleo de Justiça e Disciplina "
                        "para fixar o termo inicial da contagem contínua."
                    )
                elif "LETICIA" in p_up or "OITIVA" in p_up or "PERGUNTA" in p_up:
                    resposta = (
                        "**Orientação Tática da Oitiva:**\n"
                        "No modelo adotado, certifique-se de perguntar à testemunha se ela presenciou os factos narrados, "
                        "qualifique-a completamente e lavre expressamente a certidão de que o comunicado foi notificado, constando se compareceu ou esteve ausente."
                    )
                elif "REVELIA" in p_up or "NAO APRESENTOU" in p_up:
                    resposta = (
                        "**Operação dos Efeitos da Revelia:**\n"
                        "Se o comunicado intimado no TAV deixar transcorrer os 5 dias úteis sem manifestação:\n"
                        "1. Certifique a preclusão e a revelia nos autos;\n"
                        "2. Solicite ao Comandante do Batalhão a nomeação de defensor ad hoc;\n"
                        "3. Abra novo prazo de 5 dias úteis para o defensor nomeado apresentar a defesa."
                    )
                elif "RELATORIO" in p_up or "20 LINHAS" in p_up:
                    resposta = (
                        "**Regra do Relatório do MAPPA:**\n"
                        "O relatório deve conter os 6 tópicos normativos. No item 2 (análise das provas), seja direto e fundamentado: "
                        "não faça transcrições integrais de depoimentos e limite a análise a no máximo 20 linhas por tese/fato apurado."
                    )
                else:
                    resposta = (
                        f"Analisando o ato **{ato_selecionado}**: verifique se o carimbo de folhas (Fls.) reflete a sequência real dos autos "
                        f"e se todas as partes foram intimadas nos termos do MAPPA para assegurar a higidez jurídica do processo."
                    )

                st.markdown(resposta)
                st.session_state["historico_chat_ia_pcd"].append({"role": "assistant", "content": resposta})