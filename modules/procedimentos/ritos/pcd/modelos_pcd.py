"""
==============================================================================
SIOP PMMG - MODELOS LITERAIS DO PCD / RIP (BASE: 21º BPM / 4ª RPM / MAPPA)
Fidelidade aos modelos reais: Portaria Inaugural, Termo de Oitiva, TAV e Relatório.
Assinaturas centralizadas e estrutura paramétrica do 21º BPM.
==============================================================================
"""

import datetime


def gerar_cabecalho_oficial(dados: dict) -> str:
    """Gera o cabeçalho institucional em caixa alta no padrão PMMG."""
    rpm = str(dados.get("regiao_rpm", "QUARTA REGIÃO DA POLÍCIA MILITAR")).upper()
    unidade = str(dados.get("unidade_lotacao", "VIGÉSIMO PRIMEIRO BATALHÃO DE POLICIA MILITAR")).upper()
    return f"POLICIA MILITAR DE MINAS GERAIS\n{rpm}\n{unidade}\n"


def renderizar_portaria_despacho(dados: dict) -> str:
    """
    Modelo literal de Despacho de Instauração / Portaria Delegatória
    Fiel ao padrão expedido pelo Comando do 21º BPM / 4ª RPM.
    """
    rpm_abrev = dados.get("regiao_rpm_abrev", "4ª RPM")
    bpm_abrev = dados.get("unidade_abreviada", "21º BPM")
    despacho_num = dados.get("numero_despacho", dados.get("numero_pcd", "105016/26-RIP/21 BPM"))
    protocolo_sicor = dados.get("protocolo_sicor", "2026-000364620")
    
    encarregado_num = dados.get("encarregado_numero", "133.746-8")
    encarregado_posto = dados.get("encarregado_posto", "CAP PM")
    encarregado_nome = dados.get("encarregado_nome", "FELIPE DE OLIVEIRA ALVES PEREIRA")
    
    comandante_posto = dados.get("autoridade_delegante_posto", "TENENTE CORONEL PM")
    comandante_nome = dados.get("autoridade_delegante_nome", "ERICK LEAL LOPES")
    
    reclamante_ofendido = dados.get("ofendido_nome", "Ismael Carlos da Silva Martins")
    data_fato = dados.get("data_fato_ocorrencia", "10/04/2026")
    prazo_estipulado = dados.get("prazo_dias_estipulado", 15)
    municipio = dados.get("municipio", "Ubá")

    sintese_portaria = dados.get(
        "sintese_fato_portaria",
        f"noticia a suposta ocorrência de agressões físicas praticadas por policiais militares em desfavor do "
        f"reclamante {reclamante_ofendido}, durante sua prisão, ocorrida em {data_fato}. Consta dos autos que o "
        f"reclamante relatou ter sido agredido por militares, restando lesões corporais, com atendimento médico "
        f"no Hospital São Vicente de Paulo."
    )

    return (
        f"POLÍCIA MILITAR DE MINAS GERAIS\n"
        f"{rpm_abrev}\n"
        f"{bpm_abrev}/{rpm_abrev}\n\n"
        f"DESPACHO N°: {despacho_num}\n"
        f"Ao nº {encarregado_num} {encarregado_posto} {encarregado_nome} - Encarregado.\n"
        f"Anexos: Protocolo SICOR: {protocolo_sicor}\n\n"
        f"O {comandante_posto}, COMANDANTE DO {bpm_abrev}, no uso de suas atribuições legais, "
        f"previstas no art. 107 do Manual de Processos e Procedimentos Administrativos (MAPPA), criado pela "
        f"Resolução n° 4.220, de 28/06/2012, e:\n\n"
        f"CONSIDERANDO QUE:\n\n"
        f"1- Submeteu-se ao crivo desta Autoridade Administrativa a documentação em epígrafe, na qual se {sintese_portaria}\n\n"
        f"2- Mostra-se exigível a elucidação dos fatos narrados de forma a constatar suas circunstâncias, confirmar a "
        f"materialidade e identificar sua autoria bem como possíveis afrontas ao CPM e/ou CEDM, para decisão quanto às "
        f"eventuais medidas penais e/ou administrativo-disciplinares decorrentes, conforme o que restar aflorado nos autos.\n\n"
        f"RESOLVE:\n\n"
        f"a) determinar que seja, com a possível urgência, elaborado o procedimento apuratório, delegando-lhe, para este fim, "
        f"as atribuições que me competem, devendo o encarregado observar as orientações que regulam o assunto;\n"
        f"b) Neste sentido, o encarregado deverá:\n"
        f"   b.1) Ter pleno conhecimento do Capítulo V do MAPPA;\n"
        f"   b.2) Tomar conhecimento desta portaria e de seus anexos;\n"
        f"   b.3) Realizar demais diligências necessárias para a elucidação do fato;\n"
        f"c) recomendar ao encarregado que comunique, via painel administrativo, o Núcleo de Justiça e Disciplina, "
        f"a data efetiva na qual recebeu esta documentação, para fins de agendamento e acompanhamento dos prazos;\n"
        f"d) determinar ao encarregado que ao final entregue cópia digitalizada em formato .pdf juntamente com o procedimento físico;\n"
        f"e) determinar o prazo de {prazo_estipulado} (quinze) dias;\n"
        f"f) lançar no sistema de controle da IME.\n\n"
        f"Quartel em {municipio}, data da assinatura eletrônica.\n\n"
        f"                                ________________________________________________\n"
        f"                                           {comandante_nome}, {comandante_posto}\n"
        f"                                                COMANDANTE DO {bpm_abrev}\n"
    )


def renderizar_tav(dados: dict) -> str:
    """Modelo literal de Termo de Abertura de Vista (TAV) para Apresentação das Alegações de Defesa."""
    rpm_bpm = f"{dados.get('regiao_rpm_abrev', '4ª RPM')} / {dados.get('unidade_abreviada', '21º BPM')}"
    hoje = datetime.date.today()
    dia_str = str(hoje.day).zfill(2)
    mes_extenso = hoje.strftime("%B")
    ano_str = str(hoje.year)

    municipio = dados.get("municipio", "Ubá")
    unidade_quartel = dados.get("unidade_abreviada", "21º BPM")
    encarregado = dados.get("encarregado_posto_nome", "Cap PM Felipe de Oliveira Alves Pereira")
    comunicado_num = dados.get("comunicado_numero", "__________")
    comunicado_posto = dados.get("comunicado_posto", "Cb PM")
    comunicado_nome = dados.get("comunicado_nome", "______________________________")
    comunicado_lotacao = dados.get("comunicado_lotacao", "35ª CIA PM / 21º BPM")
    fls_total = dados.get("fls_total_autos", "_____")
    fls_ini = dados.get("fls_inicial_autos", "01")
    fls_fim = dados.get("fls_final_autos", "_____")
    art_mapa = dados.get("artigo_mappa", "____")
    enquadramento = dados.get("enquadramento_cedm", "inciso _____ do art. _____ do CEDM")
    sintese_fato = dados.get("sintese_fato", "No dia __/__/____, na cidade de Ubá/MG, o militar comunicado cometeu conduta que em tese afronta os preceitos regulamentares.")
    anexos = dados.get("anexos_especificados", "Cópia da Portaria inaugural de instauração e documentos que instruem a acusação.")

    return (
        f"{rpm_bpm}\n\n"
        f"TERMO DE ABERTURA DE VISTA (TAV) PARA\n"
        f"APRESENTAÇÃO DAS ALEGAÇÕES DE DEFESA\n\n"
        f"Anexo(s): {anexos}\n\n"
        f"Aos {dia_str} dias do mês de {mes_extenso} do ano de {ano_str}, nesta cidade de {municipio}, "
        f"Estado de Minas Gerais, no Quartel do {unidade_quartel}, onde eu, {encarregado}, encarregado do processo, "
        f"encontrava-me, compareceu o n. {comunicado_num}, {comunicado_posto} {comunicado_nome}, lotado no(a) {comunicado_lotacao}, "
        f"(ou o seu defensor), ao qual foi feita a abertura de vista da comunicação disciplinar anexa, contendo {fls_total} fls., "
        f"numeradas de {fls_ini} a {fls_fim}, nos termos do inciso LV, do art. 5º, da Constituição Federal, e em observância ao art. {art_mapa} do MAPPA, "
        f"que asseguram o amplo direito de defesa e do exercício do contraditório, e, considerando que o militar supracitado cometeu, "
        f"em tese, atos que configuram transgressão(ões) disciplinar(es), especificada(s) no {enquadramento}, conforme síntese abaixo:\n\n"
        f"“{sintese_fato} Posto isto, encontra-se esse comunicado incurso, em tese, no {enquadramento}.”\n\n"
        f"Passo os documentos anexos, que compõem as peças acusatórias, para que, no prazo de 05 (cinco) dias úteis, "
        f"apresente suas alegações de defesa, diretamente ou através de defensor constituído, ficando advertido quanto ao previsto no "
        f"art. 316 do CPM, que trata da divulgação/extravio de documentos e alertado que a não apresentação das alegações de defesa, "
        f"injustificadamente, dentro do prazo estipulado, será considerado como precluso o direito, operando-se os efeitos da revelia, "
        f"quando lhe será nomeado defensor ad hoc.\n\n"
        f"Recebi 01 (uma) via do presente termo e os autos anexos.\n\n"
        f"Quartel em {municipio}, {dia_str} de {mes_extenso} de {ano_str}.\n\n"
        f"                                ________________________________________________\n"
        f"                                                   COMUNICADO\n\n"
        f"                                ________________________________________________\n"
        f"                                                   TESTEMUNHA\n\n"
        f"                                ________________________________________________\n"
        f"                                                   TESTEMUNHA\n\n"
        f"                                ________________________________________________\n"
        f"                                            ENCARREGADO DO PROCESSO\n"
    )


def renderizar_termo_oitiva(dados: dict) -> str:
    """Modelo literal de Termo de Depoimento de Testemunha conforme modelo 21º BPM."""
    cabecalho = gerar_cabecalho_oficial(dados)
    ordem_testemunha = dados.get("ordem_testemunha", "PRIMEIRA TESTEMUNHA").upper()
    local = dados.get("local_oitiva", f"Quartel do {dados.get('unidade_abreviada', '21º BPM')}, em {dados.get('municipio', 'Ubá')}")
    data_oitiva = dados.get("data_oitiva", datetime.date.today().strftime("%d/%m/%Y - %A"))
    encarregado = dados.get("encarregado_posto_nome", "Cap PM Felipe de Oliveira Alves Pereira")

    nome_dep = dados.get("depoente_nome", "LETÍCIA FELÍCIO PEREIRA DO VALE")
    prof_dep = dados.get("depoente_profissao", "Policial Militar")
    posto_dep = dados.get("depoente_posto", "Cb PM")
    num_dep = dados.get("depoente_numero", "150.411-7")
    pai_dep = dados.get("depoente_pai", "José Raimundo Pereira da Silva")
    mae_dep = dados.get("depoente_mae", "Maria Alice Balbi Felício Pereira")
    idade_dep = dados.get("depoente_idade", "44 anos")
    nasc_dep = dados.get("depoente_nasc", "11/03/1981")
    sexo_dep = dados.get("depoente_sexo", "F")
    nac_dep = dados.get("depoente_nacionalidade", "Brasileira")
    nat_dep = dados.get("depoente_naturalidade", "Ubá/MG")
    apelido_dep = dados.get("depoente_apelido", "(se houver)")
    est_civil = dados.get("depoente_est_civil", "Casada")
    cpf_dep = dados.get("depoente_cpf", "048.523.716-44")
    rg_dep = dados.get("depoente_rg", "10892502")
    trab_dep = dados.get("depoente_trabalho", "Rua Farmacêutico José Rodrigues de Andrade, 545 A – São Sebastião. Ubá/MG")
    res_dep = dados.get("depoente_residencia", "Rua Amélia Duarte Sol, 121, bairro Vitória, Ubá/MG, CEP: 36.500-240.")
    cel_dep = dados.get("depoente_celular", "(32) 9 9944-1149")
    tel_res = dados.get("depoente_tel_res", "")
    tel_com = dados.get("depoente_tel_com", "")
    escolaridade = dados.get("depoente_escolaridade", "Superior Completo")
    le_dep = dados.get("depoente_le", "sim")
    escreve_dep = dados.get("depoente_escreve", "sim")

    processo_despacho = dados.get("despacho_numero", f"despacho nº {dados.get('numero_pcd', '109.186-2025-21º BPM')} – PCD")
    depoimento_corpo = dados.get(
        "depoimento_corpo_texto",
        "PERGUNTADO acerca dos fatos constantes na Portaria/Despacho, que lhe foi lida, respondeu que..."
    )

    comparecimento_comunicado = dados.get(
        "certidao_presenca_comunicado",
        "NOTIFICADO PARA ACOMPANHAR A AUDIÇÃO DA TESTEMUNHA, CONFORME FLS. _________ O COMUNICADO NÃO COMPARECEU."
    )

    hora_ini = dados.get("hora_inicio", "14hs")
    hora_fim = dados.get("hora_fim", "14h30min")

    return (
        f"{cabecalho}\n\n"
        f"TERMO DE DEPOIMENTO - {ordem_testemunha}\n\n"
        f"Local: {local}\n"
        f"Data da oitiva: {data_oitiva}\n"
        f"Nome do encarregado: {encarregado}\n\n"
        f"DEPOIMENTO OU INFORMAÇÃO (caso não seja compromissada) que presta:\n"
        f"NOME: {nome_dep}\n"
        f"Profissão: {prof_dep}; Posto/Grad: {posto_dep}; Número: {num_dep}.\n"
        f"Filiação: Pai: {pai_dep},\n"
        f"          Mãe: {mae_dep}\n"
        f"Idade: {idade_dep}. Data de nascimento: {nasc_dep}; Sexo: {sexo_dep}.\n"
        f"Nacionalidade: {nac_dep}, Naturalidade: {nat_dep}\n"
        f"Apelido: {apelido_dep} Estado civil: {est_civil}\n"
        f"CPF: {cpf_dep}           Identidade: {rg_dep}\n"
        f"Local de trabalho: {trab_dep}\n"
        f"Residência: {res_dep}\n"
        f"Tel. celular: {cel_dep}       Tel. residencial: {tel_res}         Tel. comercial: {tel_com}\n"
        f"Escolaridade: {escolaridade}\n"
        f"Lê: {le_dep}           Escreve: {escreve_dep}\n\n"
        f"Costumes: disse nada. Compromisso legal: na forma da lei. "
        f"PERGUNTADO acerca dos fatos constantes no {processo_despacho}, que lhe foi lida, "
        f"respondeu que {depoimento_corpo}\n\n"
        f"{comparecimento_comunicado}\n\n"
        f"Nada mais disse, nem lhe foi perguntado e para constar, lavrei este termo, que iniciado às {hora_ini}, "
        f"foi encerrado às {hora_fim} do mesmo dia, o qual depois de lido e achado conforme, vai assinado.\n\n"
        f"                                ________________________________________________\n"
        f"                                         {nome_dep}, {posto_dep}\n"
        f"                                                    TESTEMUNHA\n\n"
        f"                                ________________________________________________\n"
        f"                                         {encarregado}\n"
        f"                                                    ENCARREGADO\n"
    )


def renderizar_relatorio_pcd(dados: dict) -> str:
    """Modelo literal de Relatório do Encarregado em 6 Tópicos do MAPPA."""
    rpm_bpm = f"{dados.get('regiao_rpm_abrev', '4ª RPM')} / {dados.get('unidade_abreviada', '21º BPM')}"
    hoje = datetime.date.today()
    dia_str = str(hoje.day).zfill(2)
    mes_extenso = hoje.strftime("%B")
    ano_str = str(hoje.year)
    municipio = dados.get("municipio", "Ubá")
    encarregado = dados.get("encarregado_posto_nome", "Cap PM Felipe de Oliveira Alves Pereira")

    num_pcd = dados.get("numero_pcd", "001/2026")
    data_pcd = dados.get("data_pcd", hoje.strftime("%d/%m/%Y"))
    comunicado_num = dados.get("comunicado_numero", "150.123-4")
    comunicado_posto = dados.get("comunicado_posto", "Cb PM")
    comunicado_nome = dados.get("comunicado_nome", "SILVA")
    enquadramento = dados.get("enquadramento_cedm", "art. 13, inciso II, do CEDM")
    vitima = dados.get("ofendidos_vitimas", "O Estado / A Administração Militar (fls. 02)")
    fato_sucinto = dados.get("fato_sucinto", "apurar conduta atribuída ao militar comunicado constante na Portaria inaugural.")
    local_fato = dados.get("local_fato", "Ubá/MG")
    data_hora_fato = dados.get("data_hora_fato", "__/__/____ às __:__ hs")
    em_servico = dados.get("em_servico", "Sim")
    testemunhas_ouvidas = dados.get("testemunhas_ouvidas_lista", "Cb PM Letícia Felício Pereira do Vale (fls. 05/06)")
    objetos_apreendidos = dados.get("objetos_apreendidos", "Nenhum")
    outras_provas = dados.get("outras_provas_lista", "Cópia do REDS, extrato funcional e registros de escalas.")

    analise_fatos = dados.get(
        "analise_fatos_provas",
        "Do que foi apurado, constata-se que os fatos ocorreram da seguinte forma: "
        "No dia do ocorrido, o militar... (Descrever de forma motivada nas provas, sem cópias integrais de depoimentos, "
        "observando o limite regulamentar de até 20 linhas por tese/fato apurado)."
    )
    analise_defesa = dados.get(
        "analise_alegacoes_defesa",
        "A defesa sustentou em suas razões escritas que... No entanto, da análise probatória restou comprovado que..."
    )
    incidentes = dados.get(
        "incidentes_processuais",
        "O procedimento transcorreu em estrita observância ao contraditório e ampla defesa, cumprindo-se os prazos do Art. 86 e Art. 57, §1º do CEDM, sem intercorrências."
    )
    conclusao = dados.get(
        "conclusao_texto",
        f"Restou comprovado, em síntese, o cometimento da transgressão disciplinar imputada, praticada pelo seguinte militar:\n"
        f"- N. {comunicado_num}, {comunicado_posto} {comunicado_nome}, {enquadramento}."
    )
    parecer = dados.get(
        "parecer_proposta",
        f"Concluídos os trabalhos, somos de parecer que:\n"
        f"- o militar N. {comunicado_num}, {comunicado_posto} {comunicado_nome}, seja enquadrado e sancionado disciplinarmente pela autoridade competente."
    )

    return (
        f"{rpm_bpm}\n\n"
        f"RELATÓRIO\n\n"
        f"1. Dados\n"
        f"a. Processo de Comunicação Disciplinar n. {num_pcd}, de {data_pcd}.\n"
        f"b. Comunicado, com a tipificação da(s) transgressão(ões) disciplinar(es) imputada(s):\n"
        f"N. {comunicado_num}, {comunicado_posto} {comunicado_nome}, {enquadramento};\n"
        f"c. Ofendido(s)/vítima(s): {vitima};\n"
        f"d. Fato: Este Processo de Comunicação Disciplinar teve por finalidade {fato_sucinto};\n"
        f"e. Local: {local_fato} | Data/hora: {data_hora_fato} | Em serviço? {em_servico};\n"
        f"f. Testemunhas ouvidas: {testemunhas_ouvidas};\n"
        f"g. Objetos apreendidos/arrecadados: {objetos_apreendidos};\n"
        f"h. Outras provas: {outras_provas}.\n\n"
        f"2. Dos fatos e da análise das provas\n"
        f"{analise_fatos}\n\n"
        f"3. Das alegações de defesa\n"
        f"{analise_defesa}\n\n"
        f"4. Incidentes processuais\n"
        f"{incidentes}\n\n"
        f"5. Conclusão\n"
        f"{conclusao}\n\n"
        f"6. Parecer\n"
        f"{parecer}\n\n"
        f"Quartel em {municipio}, {dia_str} de {mes_extenso} de {ano_str}.\n\n"
        f"                                _________________________________________\n"
        f"                                            {encarregado}\n"
        f"                                                    ENCARREGADO\n"
    )


def renderizar_termo_juntada(dados: dict) -> str:
    """Modelo formal de Termo de Juntada com fechos centralizados."""
    cabecalho = gerar_cabecalho_oficial(dados)
    hoje = datetime.date.today()
    dia_str = str(hoje.day).zfill(2)
    mes_extenso = hoje.strftime("%B")
    ano_str = str(hoje.year)
    municipio = dados.get("municipio", "Ubá")
    encarregado = dados.get("encarregado_posto_nome", "Cap PM Felipe de Oliveira Alves Pereira")
    doc_desc = dados.get("origem_documento_desc", "documento apresentado aos autos")
    fls_ini = dados.get("fls_inicial", "___")
    fls_fim = dados.get("fls_final", "___")

    return (
        f"{cabecalho}\n\n"
        f"TERMO DE JUNTADA\n\n"
        f"Aos {dia_str} dias do mês de {mes_extenso} do ano de {ano_str}, nesta cidade de {municipio}, "
        f"Estado de Minas Gerais, no Quartel do {dados.get('unidade_abreviada', '21º BPM')}, faço a juntada aos autos "
        f"do Processo de Comunicação Disciplinar n.º {dados.get('numero_pcd', '____/____')} do(s) seguinte(s) documento(s): {doc_desc}, "
        f"o(s) qual(is) segue(m) autuado(s) e numerado(s) da(s) folha(s) {fls_ini} até {fls_fim}, do que, para constar, lavrei o presente termo.\n\n"
        f"Quartel em {municipio}, {dia_str} de {mes_extenso} de {ano_str}.\n\n"
        f"                                _________________________________________\n"
        f"                                            {encarregado}\n"
        f"                                                    ENCARREGADO\n"
    )