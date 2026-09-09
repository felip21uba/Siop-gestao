import pandas as pd
import re
import streamlit as st
import datetime
import calendar

MAPA_CONVERSAO_LEGENDAS = {
    "T1": "07:00 às 19:00",
    "T2": "19:00 às 07:00",
    "M1": "07:00 às 13:00",
    "T3": "13:00 às 19:00",
    "N1": "19:00 às 01:00",
    "D": "D", "F": "F", "X": "X", "FE": "FE",
    "LM": "LM", "ATE": "ATE", "LUT": "LUT",
    "NUP": "NUP", "DN": "DN", "DNT": "DNT", "DIS": "DIS"
}

TERMOS_IGNORAR_RODAPE = [
    "RESPONSÁVEL", "RESPONSAVEL", "COMANDANTE", "LEGENDA", 
    "QUADRO GERAL", "UNIDADE", "SUBUNIDADE", "OBSERVAÇ", "ASSINATURA", "ESCALA DE SERVIÇO"
]

def sanitizar_matricula(valor):
    if pd.isna(valor) or valor is None: return ""
    v_str = str(valor).strip()
    if v_str.endswith(".0"): v_str = v_str[:-2]
    return re.sub(r'\D', '', v_str)

def localizar_linha_cabecalho_real(df_raw):
    for idx_row, row in df_raw.iterrows():
        linha_texto = " ".join([str(v).upper() for v in row.values if pd.notna(v)])
        if any(k in linha_texto for k in ["MATRICULA", "MATRÍCULA", "EQUIPE", "MILITAR", "Nº POLÍCIA", "NUMERO POLICIA"]):
            return idx_row
    return 0

def identificar_coluna_militar(df):
    for col in df.columns:
        c_upper = str(col).strip().upper()
        if any(k in c_upper for k in ["MATRICULA", "MATRÍCULA", "NUMERO", "Nº", "POLICIA", "POLÍCIA", "MILITAR", "NOME"]):
            return col
    return df.columns[0] if len(df.columns) > 0 else None

def identificar_coluna_equipe(df):
    for col in df.columns:
        c_upper = str(col).strip().upper()
        if any(k in c_upper for k in ["EQUIPE", "GUARNIÇÃO", "GUARNICAO", "FRAÇÃO", "FRACAO", "TURMA", "PELOTAO", "PELOTÃO"]):
            return col
    return None

def extrair_dias_colunas(df, num_dias_mes):
    """Busca cega infalível para identificar colunas que representam os dias 1 a 31."""
    mapa_dias = {}
    termos_ignorar = ["EQUIPE", "MILITAR", "MATRICULA", "MATRÍCULA", "Nº", "NOME", "HORAS", "META", "PEL", "CIA", "BPM", "RPM"]
    
    for col in df.columns:
        col_str = str(col).strip().upper()
        if any(termo in col_str for termo in termos_ignorar):
            continue
            
        numeros = re.findall(r'\d+', col_str)
        if numeros:
            dia_num = int(numeros[0])
            if 1 <= dia_num <= num_dias_mes:
                mapa_dias[dia_num] = col
                
    return mapa_dias

def escanear_legendas_unicas_excel(arquivo_excel, ano_alvo, mes_alvo):
    try:
        df_raw = pd.read_excel(arquivo_excel, header=None)
        idx_cabecalho = localizar_linha_cabecalho_real(df_raw)
        df = pd.read_excel(arquivo_excel, header=idx_cabecalho)
        
        num_dias_mes = calendar.monthrange(ano_alvo, mes_alvo)[1]
        mapa_cols_dias = extrair_dias_colunas(df, num_dias_mes)

        legendas_encontradas = set()
        padroes_ignorados = {"F", "D", "X", "FE", "LM", "ATE", "LUT", "NUP", "DN", "DNT", "DIS", "NAN", "NONE", ""}

        col_militar = identificar_coluna_militar(df)

        for _, row in df.iterrows():
            txt_mil = str(row.get(col_militar, "")).upper().strip()
            if any(termo in txt_mil for termo in TERMOS_IGNORAR_RODAPE):
                continue

            for col in mapa_cols_dias.values():
                val = row[col]
                if pd.notna(val):
                    val_clean = str(val).strip().upper()
                    if val_clean not in padroes_ignorados and not ("ÀS" in val_clean or "AS" in val_clean):
                        legendas_encontradas.add(val_clean)

        return sorted(list(legendas_encontradas))
    except Exception:
        return []

def processar_upload_escala_excel(arquivo_excel, ano_alvo, mes_alvo, mapa_custom_legendas=None, limpar_quadro=False):
    try:
        df_raw = pd.read_excel(arquivo_excel, header=None)
        idx_cabecalho = localizar_linha_cabecalho_real(df_raw)
        df = pd.read_excel(arquivo_excel, header=idx_cabecalho)
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
    mapa_colunas_dias = extrair_dias_colunas(df, num_dias_mes)

    if not mapa_colunas_dias:
        return False, f"Nenhuma coluna correspondente aos dias do mês (1 a {num_dias_mes}) foi encontrada.", []

    militares_sistema = st.session_state.get("lista_militares", [])
    mapa_mils_por_num = {}
    for m in militares_sistema:
        num_limpo = sanitizar_matricula(m.get("num_policia", ""))
        if num_limpo:
            mapa_mils_por_num[num_limpo] = m

    # AQUI RESOLVE O CASO DO CAP PEREIRA FIXO
    if limpar_quadro:
        grade_lancamentos = {}
        chaves_quadro = []
    else:
        grade_lancamentos = st.session_state.get("grade_escala_lancamentos", {})
        chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])

    militares_importados_cnt = 0
    militares_nao_encontrados = []

    for idx, row in df.iterrows():
        val_militar_raw = str(row.get(col_militar, "")).strip()
        val_militar_upper = val_militar_raw.upper()
        
        if not val_militar_raw or val_militar_upper in ["NAN", "NONE", ""]:
            continue
            
        if any(termo in val_militar_upper for termo in TERMOS_IGNORAR_RODAPE):
            continue

        num_extraido = sanitizar_matricula(val_militar_raw)
        militar_obj = mapa_mils_por_num.get(num_extraido)

        if not militar_obj:
            tokens_linha = set(re.findall(r'\b[A-Z0-9]+\b', val_militar_upper))
            for m in militares_sistema:
                nome_guerra_m = str(m.get("nome_guerra", "")).upper().strip()
                if nome_guerra_m and nome_guerra_m in tokens_linha:
                    militar_obj = m
                    break

        if not militar_obj:
            if len(val_militar_raw) > 3 and not val_militar_upper.startswith("HORAS"):
                militares_nao_encontrados.append(val_militar_raw.replace("\n", " "))
            continue

        m_id = militar_obj["id"]
        equipe_nome = str(row.get(col_equipe, "RP")).strip().upper() if col_equipe else "RP"
        if equipe_nome in ["NAN", "NONE", ""] or any(t in equipe_nome for t in TERMOS_IGNORAR_RODAPE):
            equipe_nome = "RP"

        par_chave = (m_id, equipe_nome)
        if par_chave not in chaves_quadro:
            chaves_quadro.append(par_chave)

        for dia_num, col_nome_excel in mapa_colunas_dias.items():
            val_celula = row.get(col_nome_excel, "F")
            val_str = str(val_celula).strip().upper() if pd.notna(val_celula) else "F"
            if val_str in ["NAN", "NONE", ""]:
                val_str = "F"

            val_convertido = mapa_legendas_final.get(val_str, val_str)
            if val_str not in mapa_legendas_final:
                val_convertido = val_celula

            chave_matriz = f"{m_id}_{equipe_nome}_{ano_alvo}_{mes_alvo:02d}_{dia_num:02d}"
            grade_lancamentos[chave_matriz] = str(val_convertido).strip()

        militares_importados_cnt += 1

    st.session_state["grade_escala_lancamentos"] = grade_lancamentos
    st.session_state["militares_no_quadro_chaves"] = chaves_quadro

    msg_sucesso = f"✅ Importação concluída! {militares_importados_cnt} militar(es) carregado(s)."
    return True, msg_sucesso, militares_nao_encontrados