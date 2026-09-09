import pandas as pd
import re
import streamlit as st
import datetime
import calendar

# Tabela padrão de conversão de legendas para horários completos
MAPA_CONVERSAO_LEGENDAS = {
    "T1": "07:00 às 19:00",
    "T2": "19:00 às 07:00",
    "M1": "07:00 às 13:00",
    "T3": "13:00 às 19:00",
    "N1": "19:00 às 01:00",
    "D": "D",
    "F": "F",
    "X": "X",
    "FE": "FE",
    "LM": "LM",
    "ATE": "ATE",
    "LUT": "LUT",
    "NUP": "NUP",
    "DN": "DN",
    "DNT": "DNT",
    "DIS": "DIS"
}

def sanitizar_matricula(valor):
    """Remove pontuações, traços, espaços e zeros flutuantes de matrículas."""
    if pd.isna(valor) or valor is None:
        return ""
    v_str = str(valor).strip()
    if v_str.endswith(".0"):
        v_str = v_str[:-2]
    return re.sub(r'\D', '', v_str)

def identificar_coluna_militar(df):
    """Localiza a coluna que contém o nome ou número de polícia do militar."""
    for col in df.columns:
        c_upper = str(col).strip().upper()
        if any(k in c_upper for k in ["MATRICULA", "MATRÍCULA", "NUMERO", "Nº", "POLICIA", "POLÍCIA", "MILITAR", "NOME"]):
            return col
    return df.columns[0] if len(df.columns) > 0 else None

def identificar_coluna_equipe(df):
    """Localiza a coluna de equipe ou fração."""
    for col in df.columns:
        c_upper = str(col).strip().upper()
        if any(k in c_upper for k in ["EQUIPE", "GUARNIÇÃO", "GUARNICAO", "FRAÇÃO", "FRACAO", "TURMA", "PELOTAO", "PELOTÃO"]):
            return col
    return None

def escanear_legendas_unicas_excel(arquivo_excel, ano_alvo, mes_alvo):
    """
    Abre a planilha e extrai todas as siglas/legendas não padrão
    presentes nas colunas de dias para preencher o modal dinamicamente.
    """
    try:
        df = pd.read_excel(arquivo_excel)
        num_dias_mes = calendar.monthrange(ano_alvo, mes_alvo)[1]
        
        cols_dias = []
        for col in df.columns:
            match = re.search(r'\b([1-9]|[12][0-9]|3[01])\b', str(col).strip())
            if match and 1 <= int(match.group(1)) <= num_dias_mes:
                cols_dias.append(col)

        legendas_encontradas = set()
        padroes_ignorados = {"F", "D", "X", "FE", "LM", "ATE", "LUT", "NUP", "DN", "DNT", "DIS", "NAN", "NONE", ""}

        for col in cols_dias:
            for val in df[col].dropna():
                val_clean = str(val).strip().upper()
                if val_clean not in padroes_ignorados and not ("ÀS" in val_clean or "AS" in val_clean):
                    legendas_encontradas.add(val_clean)

        return sorted(list(legendas_encontradas))
    except Exception:
        return []

def processar_upload_escala_excel(arquivo_excel, ano_alvo, mes_alvo, mapa_custom_legendas=None):
    """
    Lê o arquivo Excel, interpreta as variações de matrícula/dias,
    converte siglas de legendas para horários por extenso e carrega no Passo 5.
    """
    try:
        df = pd.read_excel(arquivo_excel)
    except Exception as ex:
        return False, f"Erro ao processar arquivo Excel: {ex}", []

    mapa_legendas_final = MAPA_CONVERSAO_LEGENDAS.copy()
    if mapa_custom_legendas and isinstance(mapa_custom_legendas, dict):
        mapa_legendas_final.update(mapa_custom_legendas)

    col_militar = identificar_coluna_militar(df)
    col_equipe = identificar_coluna_equipe(df)

    if not col_militar:
        return False, "Não foi possível identificar a coluna de Militares/Matrícula na planilha.", []

    num_dias_mes = calendar.monthrange(ano_alvo, mes_alvo)[1]
    mapa_colunas_dias = {}

    for col in df.columns:
        col_str = str(col).strip()
        match = re.search(r'\b([1-9]|[12][0-9]|3[01])\b', col_str)
        if match:
            dia_num = int(match.group(1))
            if 1 <= dia_num <= num_dias_mes:
                mapa_colunas_dias[dia_num] = col

    if not mapa_colunas_dias:
        return False, f"Nenhuma coluna correspondente aos dias do mês (1 a {num_dias_mes}) foi encontrada.", []

    militares_sistema = st.session_state.get("lista_militares", [])
    mapa_mils_por_num = {}
    
    for m in militares_sistema:
        num_limpo = sanitizar_matricula(m.get("num_policia", ""))
        if num_limpo:
            mapa_mils_por_num[num_limpo] = m

    grade_lancamentos = st.session_state.get("grade_escala_lancamentos", {})
    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])

    militares_importados_cnt = 0
    militares_nao_encontrados = []

    for idx, row in df.iterrows():
        val_militar_raw = str(row.get(col_militar, "")).strip()
        if not val_militar_raw or val_militar_raw.upper() in ["NAN", "NONE", ""]:
            continue

        num_extraido = sanitizar_matricula(val_militar_raw)
        militar_obj = mapa_mils_por_num.get(num_extraido)

        if not militar_obj:
            tokens_linha = set(val_militar_raw.upper().split())
            for m in militares_sistema:
                nome_guerra_m = str(m.get("nome_guerra", "")).upper().strip()
                if nome_guerra_m and nome_guerra_m in tokens_linha:
                    militar_obj = m
                    break

        if not militar_obj:
            militares_nao_encontrados.append(val_militar_raw)
            continue

        m_id = militar_obj["id"]
        equipe_nome = str(row.get(col_equipe, "RP")).strip().upper() if col_equipe else "RP"
        if equipe_nome in ["NAN", "NONE", ""]:
            equipe_nome = "RP"

        par_chave = (m_id, equipe_nome)
        if par_chave not in chaves_quadro:
            chaves_quadro.append(par_chave)

        for dia_num, col_nome_excel in mapa_colunas_dias.items():
            val_celula = row.get(col_nome_excel, "F")
            val_str = str(val_celula).strip().upper() if pd.notna(val_celula) else "F"
            if val_str in ["NAN", "NONE", ""]:
                val_str = "F"

            val_convertido = mapa_legendas_final.get(val_str, val_celula)
            chave_matriz = f"{m_id}_{equipe_nome}_{ano_alvo}_{mes_alvo:02d}_{dia_num:02d}"
            grade_lancamentos[chave_matriz] = str(val_convertido).strip()

        militares_importados_cnt += 1

    st.session_state["grade_escala_lancamentos"] = grade_lancamentos
    st.session_state["militares_no_quadro_chaves"] = chaves_quadro

    msg_sucesso = f"✅ Importação concluída! {militares_importados_cnt} militar(es) carregado(s) com sucesso para o Quadro."
    return True, msg_sucesso, militares_nao_encontrados