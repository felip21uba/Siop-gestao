import pandas as pd
import datetime

def analisar_mancha_criminal_e_sugerir_cartao(df_crimes, turno_inicio="07:00", turno_fim="19:00"):
    """
    Analisa os dados de ocorrências e gera sugestões automáticas de Cartão Programa.
    df_crimes deve conter as colunas: ['natureza', 'bairro', 'logradouro', 'hora_fato']
    """
    if df_crimes.empty:
        return []

    # 1. Agrupamento por Bairro e Natureza do Crime
    hotspots = df_crimes.groupby(['bairro', 'natureza']).size().reset_index(name='qtd_ocorrencias')
    hotspots = hotspots.sort_values(by='qtd_ocorrencias', ascending=False)

    sugestoes_cartao = []
    posto_num = 1

    # Regras de Negócio / Prompt de Sugestão Tática
    regras_taticas = {
        "ROUBO": {
            "objetivo": "Prevenção e neutralização de crimes violentos contra o patrimônio.",
            "missao": "Patrulhamento ostensivo com foco em abordagens a motocicletas com dois ocupantes e indivíduos em atitude suspeita.",
            "obs": "Manter viatura com giroflex ligado e realizar 15min de Ponto Base nos corredores comerciais."
        },
        "FURTO": {
            "objetivo": "Redução de furtos em estabelecimentos comerciais e a transeuntes.",
            "missao": "Contatos comunitários com comerciantes e patrulhamento preventivo em locais de maior fluxo de pedestres.",
            "obs": "Atentar para autores contumazes e egressos do sistema prisional."
        },
        "TRÁFICO": {
            "objetivo": "Sufocamento de Zonas Quentes de Criminalidade (ZQC) e apreensão de ilícitos.",
            "missao": "Operação presença e abordagens qualificadas em locais de aglomeração suspeita.",
            "obs": "Foco no cumprimento de mandados de prisão em aberto."
        }
    }

    # 2. Construção dinâmica dos Postos (PE)
    for idx, row in hotspots.head(5).iterrows():
        bairro = str(row['bairro']).upper()
        natureza = str(row['natureza']).upper()
        qtd = row['qtd_ocorrencias']

        # Identifica a regra mais adequada
        regra = regras_taticas.get("FURTO")
        for chave in regras_taticas:
            if chave in natureza:
                regra = regras_taticas[chave]
                break

        sugestoes_cartao.append({
            "posto": posto_num,
            "local_emprego": f"BAIRRO {bairro} (Concentração: {qtd} ocorrência(s) de {natureza})",
            "objetivo": regra["objetivo"],
            "missao": regra["missao"],
            "observacoes": regra["obs"]
        })
        posto_num += 1

    return sugestoes_cartao