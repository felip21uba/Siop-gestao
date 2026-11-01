"""
==============================================================================
SIOP PMMG - INTERFACE NATIVA DO RITO PCD (PROCESSO DE COMUNICAÇÃO DISCIPLINAR)
Código Completo: Gestão dos 10 Atos Oficiais, Upload de Anexos/Comprovantes,
Carimbo Fls. Manual sem travas, Dicas Processuais da IA e Chat Interativo.
==============================================================================
"""

import streamlit as st
import datetime
import re
from core.database import supabase
from .core.prazos_engine import calcular_prazo_continuo_cedm
from .ritos.pcd.modelos_pcd import (
    renderizar_tav,
    renderizar_termo_oitiva,
    renderizar_termo_juntada,
    renderizar_relatorio_pcd,
    gerar_cabecalho_oficial
)

# Sequência exata e oficial dos Atos do PCD conforme o MAPPA
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

# Dicas estritas da IA parametrizadas para cada ato processual
DICAS_IA_POR_ATO = {
    "1. Portaria de Instauração (Anexo)": (
        "📌 **Dica da IA para a Portaria:**\n"
        "- A Portaria é a peça inaugural delegatória. Anexe o documento assinado pela autoridade instauradora.\n"
        "- **Contagem do Art. 86 do CEDM:** O prazo de 15 dias contínuos começa a correr a partir do primeiro dia útil subsequente ao recebimento/carga formal dos autos pelo encarregado.\n"
        "- Verifique se a síntese do fato contém dia, hora, local e os elementos essenciais da conduta imputada."
    ),
    "2. Abertura de Vista Inicial / Notificação": (
        "📌 **Dica da IA para Abertura de Vista:**\n"
        "- Notifique o militar formalmente com cópia da Comunicação e da Portaria.\n"
        "- Certifique-se de recolher a assinatura do comunicado ou de duas testemunhas idôneas em caso de recusa.\n"
        "- Esse ato assegura o exercício do contraditório e da ampla defesa desde a instauração."
    ),
    "3. Notificação de Testemunha / Envio por E-mail": (
        "📌 **Dica da IA para Notificação de Testemunhas:**\n"
        "- Caso a notificação seja enviada por e-mail institucional, anexe o comprovante de envio e de leitura aos autos.\n"
        "- Respeite a antecedência mínima para que a testemunha e a defesa possam se organizar.\n"
        "- O militar comunicado e seu defensor devem ser previamente cientificados da data, hora e local da audiência."
    ),
    "4. Termo de Oitiva - Testemunha da Administração": (
        "📌 **Dica da IA para Testemunha de Acusação:**\n"
        "- Ouça primeiro as testemunhas arroladas pela administração (limite legal de até 3 testemunhas no PCD).\n"
        "- Qualifique o depoente na íntegra (nome, cargo, identidade funcional, profissão, residência e costumes).\n"
        "- Certifique se o militar comunicado e seu defensor compareceram ou se foram ausentes injustificadamente."
    ),
    "5. Termo de Oitiva - Testemunha da Defesa": (
        "📌 **Dica da IA para Testemunha da Defesa:**\n"
        "- Devem ser inquiridas após o término das testemunhas da administração (limite de até 3 testemunhas).\n"
        "- O encarregado pode indeferir perguntas impertinentes ou protelatórias, fundamentando no próprio termo.\n"
        "- A defesa tem direito de formular reperguntas à testemunha."
    ),
    "6. Termo de Oitiva - Interrogatório do Comunicado": (
        "📌 **Dica da IA para Oitiva do Comunicado:**\n"
        "- **REGRA DE OURO MAPPA:** O interrogatório do militar investigado deve ser impreterivelmente o ÚLTIMO ato oral instrutório.\n"
        "- Informe previamente o direito constitucional ao silêncio quanto ao mérito, sem que isso implique presunção de culpa.\n"
        "- Certifique se o militar estava assistido por advogado ou defensor ad hoc caso não compareça com defensor constituído."
    ),
    "7. Termo de Abertura de Vista Final (TAV)": (
        "📌 **Dica da IA para o TAV Final:**\n"
        "- **Prazo Estrito:** 05 (cinco) dias úteis contados a partir do primeiro dia útil subsequente à intimação (Art. 57, §1º do CEDM).\n"
        "- Abra vista integral de todos os atos realizados (todas as folhas numeradas até o momento).\n"
        "- Alerte expressamente sobre a cominação de revelia e nomeação de defensor ad hoc em caso de inércia injustificada."
    ),
    "8. Razões Escritas de Defesa (Anexo)": (
        "📌 **Dica da IA para a Defesa Escrita:**\n"
        "- Faça a juntada da peça de defesa apresentada pelo militar ou por seu advogado constituído.\n"
        "- Se o prazo transcorrer in albis sem manifestação, lavre a **Certidão de Revelia** e solicite a nomeação de defensor ad hoc para apresentar a defesa.\n"
        "- Registre o Termo de Juntada com o intervalo de folhas ocupado pela peça."
    ),
    "9. Relatório Conclusivo do Encarregado": (
        "📌 **Dica da IA para o Relatório:**\n"
        "- O relatório é opinativo, mas deve conter os 6 tópicos do MAPPA:\n"
        "  1. Dados cadastrais e tipificação;\n"
        "  2. Análise dos fatos e das provas (máximo de 20 linhas por tese/fato);\n"
        "  3. Análise objetiva das alegações da defesa;\n"
        "  4. Incidentes processuais havidos;\n"
        "  5. Conclusão fundamentada;\n"
        "  6. Parecer com a proposta disciplinar sugerida."
    ),
    "10. Ofício de Remessa e Encaminhamento": (
        "📌 **Dica da IA para o Ofício de Remessa:**\n"
        "- Peça de fechamento dos trabalhos para devolução formal dos autos à autoridade instauradora.\n"
        "- Indique o número total de folhas que compõem os autos encadernados.\n"
        "- Solicite a homologação do relatório e a emissão do Despacho/Solução Final."
    )
}

def extrair_dados_texto_portaria(texto: str) -> dict:
    """Extrai automaticamente dados da Portaria por expressão regular se houver texto."""
    dados = {}
    if not texto:
        return dados
    
    # Busca de matrícula (ex: 123.456-7 ou 1234567)
    match_matr = re.search(r'(?:N[º°\.]?\s*|matr[íi]cula\s*:?\s*)(\d{3}\.?\d{3}-?\d|\d{6,7})', texto, re.IGNORECASE)
    if match_matr:
        dados["comunicado_numero"] = match_matr.group(1).replace(".", "").replace("-", "")

    # Busca de número de processo (ex: PCD nº 001/2026)
    match_proc = re.search(r'(?:PCD|Portaria|Processo)\s*(?:n[º°\.]?)?\s*(\d+[\/\-]\d{4})', texto, re.IGNORECASE)
    if match_proc:
        dados["numero_pcd"] = match_proc.group(1)

    return dados

def renderizar_notificacao_testemunha_padrao(dados: dict) -> str:
    """Modelo padrão PMMG de Notificação de Testemunha com menção a envio por e-mail."""
    cabecalho = gerar_cabecalho_oficial(dados)
    return (
        f"{cabecalho}\n"
        f"NOTIFICAÇÃO DE TESTEMUNHA\n\n"
        f"Ao: {dados.get('notif_destinatario_nome', '________________________________________________')}\n"
        f"Cargo/Posto/Graduação: {dados.get('notif_destinatario_cargo', '________________________')} - N.º {dados.get('notif_destinatario_num', '__________')}\n"
        f"Lotação/Endereço: {dados.get('notif_destinatario_unidade', '________________________________')}\n\n"
        f"1. Fica V. S.ª NOTIFICADO(A) a comparecer na sede do {dados.get('unidade_abreviada', 'Quartel da PMMG')}, "
        f"situado em {dados.get('municipio', 'Ubá/MG')}, no dia {dados.get('notif_data_audiencia', '__/__/____')} às {dados.get('notif_hora_audiencia', '__:__')} horas, "
        f"a fim de prestar depoimento na qualidade de TESTEMUNHA nos autos do Processo de Comunicação Disciplinar n.º {dados.get('numero_pcd', '____/____')}, "
        f"ao qual responde o militar {dados.get('comunicado_posto_nome', '____________________')}.\n\n"
        f"2. Fica advertido de que o não comparecimento injustificado implicará nas sanções da legislação pertinente.\n\n"
        f"3. Caso este expediente seja transmitido por correio eletrônico institucional (e-mail), o comprovante de envio e confirmação "
        f"de leitura/entrega servirá como certidão formal de intimação aos autos.\n\n"
        f"Quartel em {dados.get('municipio', '__________')}, {datetime.date.today().strftime('%d de %B de %Y')}.\n\n"
        f"_____________________________________________________\n"
        f"{dados.get('encarregado_posto_nome', 'ENCARREGADO DO PROCESSO')}\n\n"
        f"CIÊNCIA DO NOTIFICADO:\n"
        f"Em ____/____/________ às ____:____ hs. Assinatura: _____________________________________"
    )

def renderizar_oficio_remessa(dados: dict) -> str:
    """Modelo de Ofício de Remessa dos Autos Conclusos à autoridade delegante."""
    cabecalho = gerar_cabecalho_oficial(dados)
    return (
        f"{cabecalho}\n"
        f"OFÍCIO N.º ______/{datetime.date.today().year} - PCD\n\n"
        f"Do: Encarregado do Processo de Comunicação Disciplinar n.º {dados.get('numero_pcd', '____/____')}\n"
        f"Ao: Sr. Comandante da Unidade / Autoridade Instauradora\n"
        f"Assunto: Remessa de autos conclusos de Processo Disciplinar\n\n"
        f"Senhor Comandante,\n\n"
        f"1. Cumprimentando-o cordialmente, encaminho a V. S.ª os autos conclusos do Processo de Comunicação Disciplinar n.º {dados.get('numero_pcd', '____/____')}, "
        f"instaurado por meio da Portaria de folhas {dados.get('fls_portaria', '02')}, autuado em desfavor do militar {dados.get('comunicado_posto_nome', '________________________')}, "
        f"composto por {dados.get('total_folhas_autos', '____')} folhas devidamente rubricadas e numeradas.\n\n"
        f"2. Na oportunidade, apresento em anexo o Relatório Conclusivo dos trabalhos apuratórios para deliberação, homologação "
        f"e emissão do ato final de Solução da Autoridade.\n\n"
        f"Respeitosamente,\n\n"
        f"_____________________________________________________\n"
        f"{dados.get('encarregado_posto_nome', 'ENCARREGADO DO PROCESSO')}"
    )

def renderizar_regua_topo(calculo_prazo: dict):
    """Renderiza a Régua de Prazos contínua do Art. 86 no topo sem sobrepor elementos."""
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


def exibir_view_pcd_nativa(dados_pcd: dict):
    """Área central de trabalho do Encarregado."""
    data_rec = dados_pcd.get("data_recebimento_autos", datetime.date.today())
    if isinstance(data_rec, str):
        try:
            data_rec = datetime.datetime.strptime(data_rec, "%Y-%m-%d").date()
        except Exception:
            data_rec = datetime.date.today()

    calc_prazo = calcular_prazo_continuo_cedm(data_rec, dados_pcd.get("prazo_dias_estipulado", 15))

    # 1. Régua Superior Estável
    renderizar_regua_topo(calc_prazo)

    # 2. Barra de Seleção de Atos e Carimbo Fls. Manual
    col_ato, col_fls, col_salvar = st.columns([3.5, 1.3, 1.2])

    with col_ato:
        ato_selecionado = st.selectbox(
            "📜 Selecionar Ato Processual:",
            LISTA_ATOS_PCD,
            key="sb_selecao_ato_pcd"
        )

    with col_fls:
        # Folhas sem pré-definição forçada: o usuário digita livremente
        fls_digitada = st.text_input(
            "📑 Carimbo Fls.:",
            value=st.session_state.get(f"fls_salva_{ato_selecionado}", ""),
            placeholder="Ex: Fls. 03 ou Fls. 05 a 08",
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
    dica_do_ato = DICAS_IA_POR_ATO.get(ato_selecionado, "Siga a ordem dos atos conforme o MAPPA.")
    st.info(dica_do_ato)

    # 4. Alternância do Conteúdo: Peça de Upload vs. Peça de Redação Oficial
    col_editor, col_ia = st.columns([3.2, 1.8])

    with col_editor:
        # ATOS QUE POSSUEM ANEXO / UPLOAD FÍSICO
        if ato_selecionado in [
            "1. Portaria de Instauração (Anexo)",
            "3. Notificação de Testemunha / Envio por E-mail",
            "8. Razões Escritas de Defesa (Anexo)"
        ]:
            st.markdown(f"##### 📤 Anexar Documento / Comprovante: {ato_selecionado}")
            arquivo_anexo = st.file_uploader(
                f"Selecione o arquivo digitalizado ou comprovante de e-mail (PDF, DOCX ou Imagem):",
                type=["pdf", "docx", "png", "jpg", "jpeg"],
                key=f"uploader_{ato_selecionado}"
            )

            if arquivo_anexo is not None:
                st.success(f"📎 Arquivo '{arquivo_anexo.name}' carregado ({arquivo_anexo.size} bytes).")
                
                # Leitura inteligente de dados da Portaria
                if ato_selecionado == "1. Portaria de Instauração (Anexo)":
                    try:
                        nome_arq = arquivo_anexo.name
                        dados_extraidos = extrair_dados_texto_portaria(nome_arq)
                        if dados_extraidos:
                            dados_pcd.update(dados_extraidos)
                            st.toast("Dados do militar e processo pré-identificados do anexo!", icon="⚡")
                    except Exception:
                        pass

            st.caption("Termo de Juntada do Anexo:")
            # Gera minuta do termo de juntada para ser rubricado
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

        # ATOS QUE SÃO FORMADOS POR REDAÇÃO TEXTUAL DIRETA
        else:
            chave_texto = f"texto_salvo_{ato_selecionado}"
            if chave_texto not in st.session_state:
                if "Abertura de Vista Inicial" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_tav({**dados_pcd, "anexos_especificados": "Cópia da Portaria inaugural"})
                elif "Notificação de Testemunha" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_notificacao_testemunha_padrao(dados_pcd)
                elif "Oitiva" in ato_selecionado:
                    polo_txt = "Testemunha da Administração" if "Administração" in ato_selecionado else ("Testemunha da Defesa" if "Defesa" in ato_selecionado else "Militar Comunicado")
                    st.session_state[chave_texto] = renderizar_termo_oitiva({**dados_pcd, "ordem_testemunha": polo_txt})
                elif "TAV" in ato_selecionado or "Final" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_tav(dados_pcd)
                elif "Relatório" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_relatorio_pcd(dados_pcd)
                elif "Ofício" in ato_selecionado:
                    st.session_state[chave_texto] = renderizar_oficio_remessa(dados_pcd)
                else:
                    st.session_state[chave_texto] = ""

            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; background:#1e293b; padding:8px 12px; border-radius:4px 4px 0 0;">
                <span style="font-weight:bold; color:#f8fafc; font-size:0.85rem;">{ato_selecionado}</span>
                <span style="background:#0f172a; color:#00f0ff; padding:2px 8px; border-radius:3px; font-size:0.8rem; font-weight:bold; border:1px solid #334155;">
                    {fls_digitada if fls_digitada else "Sem Fls."}
                </span>
            </div>
            """, unsafe_allow_html=True)

            texto_redigido = st.text_area(
                "Redação da Peça Oficial:",
                value=st.session_state[chave_texto],
                height=550,
                key=f"editor_texto_{ato_selecionado}",
                label_visibility="collapsed"
            )
            st.session_state["texto_editor_atual"] = texto_redigido

    # 5. Painel da IA Interativa (Dúvidas em Tempo Real do Encarregado)
    with col_ia:
        st.markdown("#### 🤖 Assistente Tático Jurídico MAPPA")
        st.caption("Converse com a IA para esclarecer dúvidas sobre o ato em andamento:")

        if "historico_chat_ia_pcd" not in st.session_state:
            st.session_state["historico_chat_ia_pcd"] = [
                {
                    "role": "assistant",
                    "content": (
                        "Olá, Encarregado. Estou monitorando os autos do processo. "
                        "Você está no ato: **" + ato_selecionado + "**. Pode me perguntar sobre ritos, legalidade do Art. 86 ou pedir sugestões de perguntas para oitiva."
                    )
                }
            ]

        # Renderiza mensagens anteriores do chat
        with st.container(height=420):
            for msg in st.session_state["historico_chat_ia_pcd"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # Input do chat
        pergunta_usuario = st.chat_input("Dúvida sobre este ato? Digite aqui...")
        if pergunta_usuario:
            st.session_state["historico_chat_ia_pcd"].append({"role": "user", "content": pergunta_usuario})
            with st.chat_message("user"):
                st.markdown(pergunta_usuario)

            # Respostas táticas da IA integradas com a fase atual do PCD
            with st.chat_message("assistant"):
                p_up = pergunta_usuario.upper()
                resposta = ""

                if "PRAZO" in p_up or "DIAS" in p_up or "86" in p_up:
                    resposta = (
                        f"**Parecer sobre Prazos:**\n"
                        f"- O prazo contínuo de 15 dias iniciou em **{calc_prazo.get('inicio_contagem')}** e finda em **{calc_prazo.get('data_fatal_real')}**.\n"
                        f"- Para o TAV, o prazo é improrrogável de **5 dias úteis** contados a partir da ciência expressa.\n"
                        f"- Caso vença em dia não útil, prorroga-se automaticamente para o primeiro dia útil seguinte."
                    )
                elif "PERGUNTA" in p_up or "OITIVA" in p_up or "DEPOIMENTO" in p_up:
                    resposta = (
                        "**Roteiro Técnico Sugerido para Inquirição:**\n"
                        "1. Confirmação do turno e situação funcional no momento dos fatos;\n"
                        "2. Se presenciou diretamente a ação ou conduta relatada na portaria;\n"
                        "3. Se existiram ordens verbais contrárias ou motivos de força maior;\n"
                        "*Atenção:* O encarregado não deve emitir juízo de valor durante a audiência."
                    )
                elif "REVELIA" in p_up or "NAO RESPONDEU" in p_up or "PRAZO ACABOU" in p_up:
                    resposta = (
                        "**Rito de Revelia no PCD:**\n"
                        "Se o comunicado devidamente citado no TAV deixar escoar os 5 dias úteis sem manifestação:\n"
                        "1. Certifique a revelia nos autos;\n"
                        "2. Solicite à autoridade instauradora a nomeação de militar de posto ou graduação igual ou superior como defensor ad hoc;\n"
                        "3. Abra novo prazo de 5 dias úteis para o defensor ad hoc apresentar as alegações."
                    )
                elif "RELATORIO" in p_up or "PARECER" in p_up or "FECHAMENTO" in p_up:
                    resposta = (
                        "**Fechamento do Relatório:**\n"
                        "Confronte a versão da acusação com a tese da defesa. "
                        "Se a transgressão restar comprovada, aponte a atenuante ou agravante aplicável do CEDM antes de propor a sanção."
                    )
                else:
                    resposta = (
                        f"Analisando o ato **{ato_selecionado}**: certifique-se de que o carimbo de folhas (Fls.) está correto "
                        f"e que todas as partes foram intimadas nos termos do MAPPA para evitar nulidades processuais."
                    )

                st.markdown(resposta)
                st.session_state["historico_chat_ia_pcd"].append({"role": "assistant", "content": resposta})