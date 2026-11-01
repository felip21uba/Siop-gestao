"""
SIOP PMMG - MODELOS DOCUMENTAIS OFICIAIS DO RITO PCD
Parametrizados pelo MAPPA e Código de Ética e Disciplina dos Militares de Minas Gerais.
Todos os cabeçalhos, datas, comarcas e dados funcionais são dinâmicos.
"""
from typing import Dict, Any

def gerar_cabecalho_oficial(dados: Dict[str, Any]) -> str:
    """Gera o cabeçalho timbrado oficial da PMMG."""
    regiao = dados.get("regiao_rpm", "4ª REGIÃO DA POLÍCIA MILITAR").upper()
    unidade = dados.get("unidade_lotacao", "VIGÉSIMO PRIMEIRO BATALHÃO DE POLÍCIA MILITAR").upper()
    return f"POLÍCIA MILITAR DE MINAS GERAIS\n{regiao}\n{unidade}\n"

def renderizar_tav(dados: Dict[str, Any]) -> str:
    """
    Renderiza o Termo de Abertura de Vista (TAV) para Alegações de Defesa.
    Prazo legal: 5 dias úteis com cominação de revelia e defensor ad hoc.
    """
    cabecalho = gerar_cabecalho_oficial(dados)
    return (
        f"{cabecalho}\n"
        f"TERMO DE ABERTURA DE VISTA (TAV) PARA\n"
        f"APRESENTAÇÃO DAS ALEGAÇÕES DE DEFESA\n\n"
        f"Anexo(s): {dados.get('anexos_especificados', 'Cópia da Comunicação Disciplinar e Despacho')}\n\n"
        f"Aos {dados.get('dia_extenso', '..........')} dias do mês de {dados.get('mes_extenso', '..........................')} "
        f"do ano de {dados.get('ano_extenso', '................')}, nesta cidade de {dados.get('municipio', '..............................')}, "
        f"Estado de Minas Gerais, no Quartel do {dados.get('unidade_abreviada', '........................')}, onde eu, "
        f"{dados.get('encarregado_posto_nome', '......................................................')}, encarregado do processo, encontrava-me, "
        f"compareceu o n. {dados.get('comunicado_numero', '........................')}, {dados.get('comunicado_posto_nome', '..............................')}, "
        f"lotado no {dados.get('comunicado_lotacao', '..............................')}, (ou o seu defensor), ao qual foi feita a abertura de vista "
        f"da comunicação disciplinar anexa, contendo {dados.get('qtd_fls', '.....')} fls., numeradas de {dados.get('fls_inicial', '.....')} a "
        f"{dados.get('fls_final', '.....')}, nos termos do inciso LV, do art. 5º, da Constituição Federal, e em observância ao MAPPA, que asseguram "
        f"o amplo direito de defesa e do exercício do contraditório, e, considerando que o militar supracitado cometeu, em tese, atos que configuram "
        f"transgressão(ões) disciplinar(es), especificada(s) no(s) {dados.get('enquadramento_cedm', 'inciso(s)........... do art.................')} "
        f"do Código de Ética e Disciplina dos Militares, conforme síntese abaixo:\n\n"
        f"\"{dados.get('sintese_fato_motivada', 'Descrever a síntese circunstanciada da conduta imputada.')}\"\n\n"
        f"Posto isto, encontra-se esse comunicado incurso, em tese, no {dados.get('enquadramento_cedm', 'inciso.... do art....')} do CEDM.\n\n"
        f"Passo os documentos anexos, que compõem as peças acusatórias, para que, no prazo de 05 (cinco) dias úteis, apresente suas alegações de defesa, "
        f"diretamente ou através de defensor constituído, ficando advertido quanto ao previsto no art. 316 do CPM, que trata da divulgação/extravio "
        f"de documentos e alertado que a não apresentação das alegações de defesa, injustificadamente, dentro do prazo estipulado, será considerado como "
        f"precluso o direito, operando-se os efeitos da revelia, quando lhe será nomeado defensor ad hoc.\n\n"
        f"Recebi 01 (uma) via do presente termo e os autos anexos.\n\n"
        f"Quartel em {dados.get('municipio', '....................')}, {dados.get('dia_numero', '....')} de "
        f"{dados.get('mes_nome', '................')} de {dados.get('ano_numero', '........')}.\n\n"
        f"________________________________________________\n"
        f"{dados.get('comunicado_posto_nome', 'COMUNICADO')}\n\n"
        f"________________________________________________\n"
        f"TESTEMUNHA\n\n"
        f"________________________________________________\n"
        f"TESTEMUNHA\n\n"
        f"________________________________________________\n"
        f"{dados.get('encarregado_posto_nome', 'ENCARREGADO DO PROCESSO')}\n"
    )

def renderizar_termo_oitiva(dados: Dict[str, Any]) -> str:
    """
    Renderiza o Termo Oficial de Depoimento/Oitiva de Testemunha (Padrão 21º BPM / MAPPA).
    Contém qualificação completa e certidão de cientificação do investigado.
    """
    cabecalho = gerar_cabecalho_oficial(dados)
    certidao = dados.get(
        "certidao_presenca_comunicado",
        f"NOTIFICADO PARA ACOMPANHAR A AUDIÇÃO DA TESTEMUNHA, CONFORME FLS. {dados.get('fls_notificacao', '_______')}, "
        f"O COMUNICADO NÃO COMPARECEU."
    )
    
    return (
        f"{cabecalho}\n"
        f"TERMO DE DEPOIMENTO - {dados.get('ordem_testemunha', 'PRIMEIRA')} TESTEMUNHA\n\n"
        f"Local: Quartel do {dados.get('unidade_abreviada', '21º BPM')}, em {dados.get('municipio', 'Ubá')}\n"
        f"Data da oitiva: {dados.get('data_oitiva', '__/__/____')} – {dados.get('dia_semana', 'Segunda-feira')}\n"
        f"Nome do encarregado: {dados.get('encarregado_posto_nome', 'Cap PM Encarregado')}\n\n"
        f"DEPOIMENTO OU INFORMAÇÃO (caso não seja compromissada) que presta:\n"
        f"NOME: {dados.get('depoente_nome', '')}\n"
        f"Profissão: {dados.get('depoente_profissao', 'Policial Militar')}; Posto/Grad: {dados.get('depoente_posto', '')}; Número: {dados.get('depoente_numero', '')}.\n"
        f"Filiação: Pai: {dados.get('depoente_pai', '')},\n"
        f"          Mãe: {dados.get('depoente_mae', '')}\n"
        f"Idade: {dados.get('depoente_idade', '')} anos. Data de nascimento: {dados.get('depoente_nascimento', '')}; Sexo: {dados.get('depoente_sexo', '')}.\n"
        f"Nacionalidade: {dados.get('depoente_nacionalidade', 'Brasileira')}, Naturalidade: {dados.get('depoente_naturalidade', '')}\n"
        f"Apelido: {dados.get('depoente_apelido', '(nada)')} Estado civil: {dados.get('depoente_estado_civil', '')}\n"
        f"CPF: {dados.get('depoente_cpf', '')}           Identidade: {dados.get('depoente_rg', '')}\n"
        f"Local de trabalho: {dados.get('depoente_local_trabalho', '')}\n"
        f"Residência: {dados.get('depoente_residencia', '')}, CEP: {dados.get('depoente_cep', '')}.\n"
        f"Tel. celular: {dados.get('depoente_celular', '')}       Tel. residencial: {dados.get('depoente_tel_fixo', '')}\n"
        f"Escolaridade: {dados.get('depoente_escolaridade', '')}\n"
        f"Lê: {dados.get('depoente_le', 'sim')}           Escreve: {dados.get('depoente_escreve', 'sim')}\n"
        f"Costumes: {dados.get('depoente_costumes', 'disse nada')}. Compromisso legal: {dados.get('depoente_compromisso', 'na forma da lei')}.\n\n"
        f"PERGUNTADO acerca dos fatos constantes no despacho nº {dados.get('num_pcd', '____')} – PCD, que lhe foi lida, respondeu {dados.get('depoimento_corpo_texto', 'que nada disse.')}\n\n"
        f"{certidao}\n\n"
        f"Nada mais disse, nem lhe foi perguntado e para constar, lavrei este termo, que iniciado às {dados.get('hora_inicio', '__:__')}hs, "
        f"foi encerrado às {dados.get('hora_fim', '__:__')}min do mesmo dia, o qual depois de lido e achado conforme, vai assinado.\n\n"
        f"________________________________________________\n"
        f"{dados.get('depoente_nome', '')}, {dados.get('depoente_posto', '')}\n"
        f"TESTEMUNHA\n\n"
        f"________________________________________________\n"
        f"{dados.get('encarregado_posto_nome', '')}\n"
        f"ENCARREGADO\n"
    )

def renderizar_termo_juntada(dados: Dict[str, Any]) -> str:
    """Renderiza o Termo de Juntada para acoplar alegações, certidões ou laudos."""
    cabecalho = gerar_cabecalho_oficial(dados)
    return (
        f"{cabecalho}\n"
        f"TERMO DE JUNTADA\n\n"
        f"Aos {dados.get('dia_extenso', '..........')} dias do mês de {dados.get('mes_extenso', '..........................')} "
        f"do ano de {dados.get('ano_extenso', '................')}, nesta cidade de {dados.get('municipio', '..............................')}, "
        f"Estado de Minas Gerais, no Quartel do {dados.get('unidade_abreviada', '........................')}, faço a juntada a estes autos "
        f"de Processo de Comunicação Disciplinar nº {dados.get('num_pcd', '________')} do(s) documento(s) "
        f"{dados.get('origem_documento_desc', 'apresentados pela defesa')}, constante(s) de {dados.get('qtd_folhas', '...')} folha(s), "
        f"numeradas de Fls. {dados.get('fls_inicial', '...')} a Fls. {dados.get('fls_final', '...')}.\n"
        f"Do que para constar, lavrei este termo que assino.\n\n"
        f"Quartel em {dados.get('municipio', '....................')}, {dados.get('dia_numero', '....')} de "
        f"{dados.get('mes_nome', '................')} de {dados.get('ano_numero', '........')}.\n\n"
        f"________________________________________________\n"
        f"{dados.get('encarregado_posto_nome', 'ENCARREGADO DO PROCESSO')}\n"
    )

def renderizar_relatorio_pcd(dados: Dict[str, Any]) -> str:
    """
    Renderiza o Relatório Conclusivo de PCD de acordo com a matriz do MAPPA.
    Comporta os 6 tópicos analíticos estritos.
    """
    cabecalho = gerar_cabecalho_oficial(dados)
    return (
        f"{cabecalho}\n"
        f"RELATÓRIO\n\n"
        f"1. Dados\n"
        f"a. Processo de Comunicação Disciplinar n. {dados.get('num_pcd', '_________')}, de {dados.get('data_pcd', '__/__/____')}.\n"
        f"b. Comunicado, com a tipificação da(s) transgressão(ões) disciplinar(es) imputada(s):\n"
        f"N. {dados.get('comunicado_numero', '_________')}, {dados.get('comunicado_posto_nome', '______________________')}, {dados.get('enquadramento_cedm', 'art. ____ do CEDM')};\n"
        f"c. Ofendido(s)/vítima(s): {dados.get('vitima_dados', 'A Administração Militar')} - (fls. {dados.get('fls_vitima', '___')});\n"
        f"d. Fato: Este Processo de Comunicação Disciplinar teve por finalidade apurar {dados.get('sintese_apuracao', 'o fato constante da comunicação disciplinar')};\n"
        f"e. Local: {dados.get('local_fato', '__________')} Data/hora: {dados.get('data_hora_fato', '__________')} Em serviço? {dados.get('em_servico', 'Sim')};\n"
        f"f. Testemunhas ouvidas: {dados.get('testemunhas_relacao_fls', '__________ (fls. ___ )')};\n"
        f"g. Objetos apreendidos/arrecadados: {dados.get('objetos_relacionados', 'Nada a registrar')};\n"
        f"h. Outras provas: {dados.get('outras_provas_fls', 'Documentos anexos')}.\n\n"
        f"2. Dos fatos e da análise das provas\n"
        f"Do que foi apurado, constata-se que os fatos ocorreram da seguinte forma:\n"
        f"{dados.get('analise_fatos_provas', 'No dia __/__/__, ...')}\n\n"
        f"3. Das alegações de defesa\n"
        f"{dados.get('analise_alegacoes_defesa', 'A defesa alegou em síntese...')}\n\n"
        f"4. Incidentes processuais\n"
        f"{dados.get('incidentes_processuais', 'Não ocorreram incidentes ou pedidos de prorrogação.')}\n\n"
        f"5. Conclusão\n"
        f"Restou comprovado, em síntese, o cometimento da(s) transgressão(ões) disciplinar(es) abaixo descrita(s), praticada(s) pelo seguinte militar:\n"
        f"- N. {dados.get('comunicado_numero', '_________')}, {dados.get('comunicado_posto_nome', '______________________')}, {dados.get('enquadramento_cedm', 'art. ____ do CEDM')}.\n"
        f"{dados.get('conclusao_justificacao_ou_crime', '')}\n\n"
        f"6. Parecer\n"
        f"Concluídos os trabalhos, somos de parecer que:\n"
        f"{dados.get('parecer_proposta_final', '- o comunicado seja enquadrado disciplinarmente na transgressão cometida;')}\n\n"
        f"Quartel em {dados.get('municipio', '....................')}, {dados.get('dia_numero', '....')} de "
        f"{dados.get('mes_nome', '................')} de {dados.get('ano_numero', '........')}.\n\n"
        f"_________________________________________\n"
        f"{dados.get('encarregado_posto_nome', 'ENCARREGADO')}\n"
    )