"""
==============================================================================
Módulo do Passo 6 - Exportação, Impressão e Assinaturas Oficiais da Escala
Atua estritamente como a camada visual/espelho estilizada do Passo 5,
com leitor universal de planilhas e Painel Interativo de Mapeamento de Horas
filtrando rigorosamente apenas legendas de turnos reais (sem dias da semana ou afastamentos).
==============================================================================
"""

import streamlit as st
import datetime
import calendar
import pandas as pd
import io
import os
import base64
import copy
import re
import zipfile
import xml.etree.ElementTree as ET
import streamlit.components.v1 as components

from core.database import supabase, carregar_militares_supabase
from modules.escalas.passos.passo3_efetivo import padronizar_graduacao, PESOS_HIERARQUIA
from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS
from modules.escalas.passos.passo5_quadro import (
    executar_auto_save_banco,
    calcular_horas_efetivas_turno,
    emitir_sinal_atualizacao_espelho,
    SIGLAS_DIAS_NEUTROS,
    SIGLAS_ABATEM_META
)

BRASAO_SVG_FALLBACK = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='90' viewBox='0 0 100 120'>"
    "<path d='M50 5 L90 25 L90 70 C90 95 50 115 50 115 C50 115 10 95 10 70 L10 25 Z' fill='%23b91c1c' stroke='%23f59e0b' stroke-width='4'/>"
    "<path d='M50 20 L80 35 L80 68 C80 88 50 102 50 102 C50 102 20 88 20 68 L20 35 Z' fill='%231e3a8a'/>"
    "<polygon points='50,30 56,45 72,45 59,55 64,70 50,60 36,70 41,55 28,45 44,45' fill='%23f59e0b'/>"
    "<text x='50' y='90' font-size='10' font-weight='bold' fill='%23ffffff' text-anchor='middle'>PMMG</text></svg>"
)

CORES_EQUIPES = {
    "CPU": "#a16207", 
    "RP": "#1e293b", 
    "SUPERVISÃO": "#b91c1c", 
    "ADMINISTRAÇÃO": "#0f766e", 
    "TM ALPHA": "#0369a1", 
    "GEPAR": "#047857",
    "A": "#1e3a8a",
    "B": "#065f46",
    "C": "#9a3412",
    "D": "#854d0e",
    "E": "#4c1d95",
    "F": "#0f766e"
}

SIGLAS_NAO_TURNO = {
    # Folgas e dias neutros
    "F", "D", "X", "FE", "LM", "ATE", "LUT", "NUP", "DIS", "LI", "LP", "DN", "DNT", "DES", "TPB",
    "NAN", "NONE", "NULL", "", "0",
    # Dias da semana (para nunca entrarem como legendas)
    "DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SAB", "SÁB",
    "DOMINGO", "SEGUNDA", "TERÇA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "SABADO"
}


def extrair_apenas_digitos(valor):
    """Extrai estritamente os dígitos de qualquer string para cruzamento de matrícula."""
    if valor is None or pd.isna(valor):
        return ""
    val_str = str(valor).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    digitos = re.sub(r'\D', '', val_str)
    return digitos.lstrip('0')


def carregar_planilha_universal_passo6(file_bytes_or_content):
    """
    Leitor universal capaz de abrir arquivos Excel regulares (.xlsx, .xls), CSV
    e planilhas no padrão Strict OpenXML geradas por sistemas corporativos da PMMG.
    """
    if hasattr(file_bytes_or_content, 'getvalue'):
        conteudo = file_bytes_or_content.getvalue()
    elif isinstance(file_bytes_or_content, bytes):
        conteudo = file_bytes_or_content
    else:
        conteudo = file_bytes_or_content.read()

    try:
        df = pd.read_excel(io.BytesIO(conteudo), engine='openpyxl', header=None)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass

    try:
        df_csv = pd.read_csv(io.BytesIO(conteudo), encoding='utf-8', sep=None, engine='python', header=None)
        if df_csv is not None and not df_csv.empty:
            return df_csv
    except Exception:
        try:
            df_csv = pd.read_csv(io.BytesIO(conteudo), encoding='latin1', sep=None, engine='python', header=None)
            if df_csv is not None and not df_csv.empty:
                return df_csv
        except Exception:
            pass

    try:
        with zipfile.ZipFile(io.BytesIO(conteudo), 'r') as z:
            if 'xl/sharedStrings.xml' in z.namelist() and 'xl/worksheets/sheet1.xml' in z.namelist():
                ss_data = z.read('xl/sharedStrings.xml')
                ss_root = ET.fromstring(ss_data)
                ns = {'s': 'http://purl.oclc.org/ooxml/spreadsheetml/main'}
                
                strings = []
                for si in ss_root.findall('.//s:si', ns):
                    t_elems = si.findall('.//s:t', ns)
                    strings.append("".join([t.text for t in t_elems if t.text]))
                    
                sheet_data = z.read('xl/worksheets/sheet1.xml')
                sheet_root = ET.fromstring(sheet_data)
                
                rows = []
                for r in sheet_root.findall('.//s:row', ns):
                    row_dict = {}
                    for c in r.findall('s:c', ns):
                        ref = c.get('r')
                        col = "".join([char for char in ref if char.isalpha()])
                        t_type = c.get('t')
                        v_elem = c.find('s:v', ns)
                        val = v_elem.text if v_elem is not None else ""
                        if t_type == 's' and val != "":
                            idx_str = int(val)
                            val = strings[idx_str] if idx_str < len(strings) else val
                        row_dict[col] = val
                    rows.append(row_dict)
                    
                df_strict = pd.DataFrame(rows)
                if not df_strict.empty:
                    return df_strict
    except Exception:
        pass

    return pd.DataFrame()


def obter_brasao_base64():
    pasta_assets = "assets"
    extensoes_validas = ('.png', '.jpg', '.jpeg', '.svg', '.webp')

    if os.path.exists(pasta_assets):
        arquivos = sorted(os.listdir(pasta_assets))
        for arq in arquivos:
            caminho_completo = os.path.join(pasta_assets, arq)
            if os.path.isfile(caminho_completo) and arq.lower().endswith(extensoes_validas):
                try:
                    ext = arq.split('.')[-1].lower()
                    mime_type = "svg+xml" if ext == "svg" else ("jpeg" if ext in ["jpg", "jpeg"] else ext)
                    
                    with open(caminho_completo, "rb") as image_file:
                        encoded = base64.b64encode(image_file.read()).decode("utf-8")
                        return f"data:image/{mime_type};base64,{encoded}"
                except Exception as ex:
                    print(f"Erro ao converter imagem {arq} em Base64: {ex}")

    return BRASAO_SVG_FALLBACK


def obter_cor_equipe(eq): 
    return CORES_EQUIPES.get(str(eq).upper().strip(), "#475569")


def extrair_texto_pdf(arq_pdf):
    try:
        import pypdf
        reader = pypdf.PdfReader(arq_pdf)
        texto = ""
        for page in reader.pages:
            texto += (page.extract_text() or "") + "\n"
        return texto
    except Exception as e:
        st.error(f"Erro ao extrair texto do PDF: {e}")
        return ""


def escanear_siglas_da_planilha(df_raw, num_dias_mes):
    """
    Varre a planilha procurando estritamente linhas onde haja militares com matrícula,
    ignorando linhas de cabeçalho de dias da semana (DOM, SEG, etc.) e afastamentos regulamentares.
    """
    header_idx = None
    for idx_r, r_vals in df_raw.iterrows():
        linha_str = " ".join([str(v).strip().upper() for v in r_vals.values if pd.notna(v)])
        if any(k in linha_str for k in ["EQUIPES", "EQUIPE", "MATRÍCULA", "MATRICULA", "Nº POLÍCIA", "POLICIA", "MILITARES", "MILITAR"]):
            header_idx = idx_r
            break

    if header_idx is None:
        return []

    col_names = [str(c).strip().upper() for c in df_raw.iloc[header_idx].values]
    df_imp = df_raw.iloc[header_idx + 1:].copy()
    df_imp.columns = col_names

    col_matricula = next((c for c in df_imp.columns if any(k in str(c) for k in ["POLICIA", "POLÍCIA", "NUMERO", "Nº", "MATRICULA", "MATRÍCULA"])), None)
    col_militar = next((c for c in df_imp.columns if any(k in str(c) for k in ["MILITAR", "NOME", "SERVIDOR"])), None)

    mapa_colunas_dias = {}
    termos_ignorar = ["EQUIPE", "MILITAR", "POLICIA", "POLÍCIA", "Nº", "NOME", "HORAS", "META", "CIA", "BPM", "PEL", "SALDO", "AUX", "TPB"]

    for c in df_imp.columns:
        c_clean = str(c).strip().upper()
        if any(termo in c_clean for termo in termos_ignorar):
            continue
        numeros = re.findall(r'\b\d{1,2}\b', c_clean)
        if numeros:
            dia_num = int(numeros[0])
            if 1 <= dia_num <= num_dias_mes and dia_num not in mapa_colunas_dias:
                mapa_colunas_dias[dia_num] = c

    siglas_encontradas = set()

    for _, row in df_imp.iterrows():
        val_mat = str(row.get(col_matricula, "")).strip() if col_matricula else ""
        val_mil = str(row.get(col_militar, "")).strip() if col_militar else ""

        # Descarta linhas de cabeçalho secundário (dias da semana como DOM, SEG) ou sem militar
        digs_mat = extrair_apenas_digitos(val_mat)
        if not digs_mat and val_mil:
            cand = re.findall(r'\b\d{6,7}\b', re.sub(r'[\.\-]', '', val_mil))
            if cand:
                digs_mat = extrair_apenas_digitos(cand[0])

        if not digs_mat or len(digs_mat) < 5:
            continue

        texto_linha = " ".join([str(v).strip().upper() for v in row.values if pd.notna(v)])
        if any(k in texto_linha for k in ["LEGENDA", "RESPONSÁVEL", "RESPONSAVEL", "COMANDANTE", "QTDE DE MILITARES"]):
            break

        for col_d in mapa_colunas_dias.values():
            val = str(row.get(col_d, "")).strip().upper()
            if val.endswith(".0"):
                val = val[:-2]
            if val and val not in SIGLAS_NAO_TURNO:
                siglas_encontradas.add(val)

    # Ordenação lógica: números primeiro (1, 2, 3...) e depois letras (S, EE...)
    def ordem_siglas(item):
        nums = re.findall(r'\d+', item)
        val_n = int(nums[0]) if nums else 999
        return (val_n, item)

    return sorted(list(siglas_encontradas), key=ordem_siglas)


def gerar_excel_escala(df_dados, unidade, subunidade, mes_ano_str, cmt_cia_str, resp_escala_str, obs_escala, texto_legenda=""):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet('Escala Mensal')
        num_cols = len(df_dados.columns)
        
        fmt_titulo = workbook.add_format({'bold': True, 'font_size': 13, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#1E3A8A', 'font_color': '#FFFFFF'})
        fmt_sub = workbook.add_format({'bold': True, 'font_size': 10, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#F1F5F9', 'border': 1})
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#E2E8F0', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        fmt_cell = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        fmt_sig_bold = workbook.add_format({'align': 'center', 'bold': True})
        fmt_sig_text = workbook.add_format({'align': 'center', 'font_size': 10})
        fmt_legenda = workbook.add_format({'align': 'left', 'font_size': 10, 'bold': True, 'font_color': '#B91C1C'})
        
        worksheet.merge_range(0, 0, 0, num_cols-1, f"POLÍCIA MILITAR DE MINAS GERAIS — {unidade.upper()}", fmt_titulo)
        worksheet.merge_range(1, 0, 1, num_cols-1, f"{subunidade.upper()}", fmt_sub)
        worksheet.merge_range(2, 0, 2, num_cols-1, f"QUADRO GERAL DE ESCALA DE SERVIÇO - {mes_ano_str.upper()}", fmt_sub)
        
        for col_num, value in enumerate(df_dados.columns):
            worksheet.write(4, col_num, value, fmt_header)
            if col_num == 0: worksheet.set_column(col_num, col_num, 12)
            elif col_num == 1: worksheet.set_column(col_num, col_num, 14)
            elif col_num == 2: worksheet.set_column(col_num, col_num, 24)
            elif col_num > 2: worksheet.set_column(col_num, col_num, 8)

        linha_excel = 5
        for _, row in df_dados.iterrows():
            fmt_eq = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_color': '#FFFFFF', 'bg_color': obter_cor_equipe(row['EQUIPE'])})
            
            for col_num, col_name in enumerate(df_dados.columns):
                val = str(row[col_name]).replace("<br>", "\n").replace("<b>", "").replace("</b>", "")
                worksheet.write(linha_excel, col_num, val, fmt_eq if col_num == 0 else fmt_cell)
            worksheet.set_row(linha_excel, 32)
            linha_excel += 1

        linha_excel += 1
        
        if texto_legenda:
            worksheet.merge_range(linha_excel, 0, linha_excel, num_cols-1, texto_legenda, fmt_legenda)
            linha_excel += 2
        else:
            linha_excel += 1

        c_mit = num_cols // 2
        worksheet.merge_range(linha_excel, 0, linha_excel, c_mit-1, "Responsável pela Escala", fmt_sig_bold)
        worksheet.merge_range(linha_excel+1, 0, linha_excel+1, c_mit-1, resp_escala_str.upper(), fmt_sig_text)
        worksheet.merge_range(linha_excel, c_mit, linha_excel, num_cols-1, "Homologado por / Comandante", fmt_sig_bold)
        worksheet.merge_range(linha_excel+1, c_mit, linha_excel+1, num_cols-1, cmt_cia_str.upper(), fmt_sig_text)
        
    return output.getvalue()


def processar_planilha_escala_passo6(df_raw, m_ano, m_mes, num_dias_mes, mapa_horas_informadas, substituir_quadro=True):
    """
    Executa a importação linha a linha da planilha carregada.
    Aplica os valores exatos de horas informados pelo operador para cada sigla de turno.
    """
    try:
        header_idx = None
        for idx_r, r_vals in df_raw.iterrows():
            linha_str = " ".join([str(v).strip().upper() for v in r_vals.values if pd.notna(v)])
            if any(k in linha_str for k in ["EQUIPES", "EQUIPE", "MATRÍCULA", "MATRICULA", "Nº POLÍCIA", "POLICIA", "MILITARES", "MILITAR"]):
                header_idx = idx_r
                break

        if header_idx is not None:
            col_names = [str(c).strip().upper() for c in df_raw.iloc[header_idx].values]
            df_imp = df_raw.iloc[header_idx + 1:].copy()
            df_imp.columns = col_names
        else:
            df_imp = df_raw.copy()
            df_imp.columns = [str(c).strip().upper() for c in df_imp.iloc[0].values]
            df_imp = df_imp.iloc[1:].copy()

        if substituir_quadro:
            grade_nova = {}
            chaves_novas = []
        else:
            grade_nova = copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {}))
            chaves_novas = list(st.session_state.get("militares_no_quadro_chaves", []))
        
        mils_cad = st.session_state.get("lista_militares", []) or carregar_militares_supabase() or []
        
        mapa_mils_digitos = {}
        for m in mils_cad:
            num_limpo = extrair_apenas_digitos(m.get("num_policia", ""))
            if num_limpo:
                mapa_mils_digitos[num_limpo] = m
                if len(num_limpo) == 7:
                    mapa_mils_digitos[num_limpo[:6]] = m

        col_equipe = next((c for c in df_imp.columns if "EQUIP" in str(c)), None)
        col_matricula = next((c for c in df_imp.columns if any(k in str(c) for k in ["POLICIA", "POLÍCIA", "NUMERO", "Nº", "MATRICULA", "MATRÍCULA"])), None)
        col_militar = next((c for c in df_imp.columns if any(k in str(c) for k in ["MILITAR", "NOME", "SERVIDOR"])), None)

        mapa_colunas_dias = {}
        termos_ignorar_dias = ["EQUIPE", "MILITAR", "POLICIA", "POLÍCIA", "Nº", "NOME", "HORAS", "META", "CIA", "BPM", "PEL", "SALDO", "AUX", "TPB"]
        
        for c in df_imp.columns:
            c_clean = str(c).strip().upper()
            if any(termo in c_clean for termo in termos_ignorar_dias):
                continue
            numeros = re.findall(r'\b\d{1,2}\b', c_clean)
            if numeros:
                dia_num = int(numeros[0])
                if 1 <= dia_num <= num_dias_mes and dia_num not in mapa_colunas_dias:
                    mapa_colunas_dias[dia_num] = c

        linhas_importadas = 0
        militares_nao_localizados = []
        equipe_corrente = "A"

        if "resumo_horas_passo6" not in st.session_state:
            st.session_state["resumo_horas_passo6"] = {}

        for idx_row, row in df_imp.iterrows():
            val_equipe_raw = str(row.get(col_equipe, "")).strip().upper() if col_equipe else ""
            val_militar_txt = str(row.get(col_militar, "")).strip().upper() if col_militar else ""
            val_mat_txt = str(row.get(col_matricula, "")).strip() if col_matricula else ""

            texto_linha_inteira = f"{val_equipe_raw} {val_militar_txt} {val_mat_txt}".upper()
            if any(k in texto_linha_inteira for k in ["LEGENDA", "RESPONSÁVEL", "RESPONSAVEL", "COMANDANTE", "QTDE DE MILITARES", "OBS.:", "QUADRO GERAL"]):
                break

            if val_equipe_raw and val_equipe_raw not in ["NAN", "NONE", "N/I", ""]:
                equipe_corrente = val_equipe_raw

            tem_lancamento_real = False
            for d in range(1, num_dias_mes + 1):
                col_d = mapa_colunas_dias.get(d)
                if col_d is not None and col_d in row:
                    v_raw = str(row.get(col_d, "")).strip().upper()
                    if v_raw and v_raw not in ["NAN", "NONE", "NULL", ""]:
                        tem_lancamento_real = True
                        break

            if not tem_lancamento_real:
                continue

            digitos_mat = extrair_apenas_digitos(val_mat_txt)
            if not digitos_mat and val_militar_txt:
                candidatos_nums = re.findall(r'\b\d{6,7}\b', re.sub(r'[\.\-]', '', val_militar_txt))
                if candidatos_nums:
                    digitos_mat = extrair_apenas_digitos(candidatos_nums[0])

            if not digitos_mat or len(digitos_mat) < 5:
                continue

            m_obj_encontrado = mapa_mils_digitos.get(digitos_mat)
            if not m_obj_encontrado and len(digitos_mat) == 7:
                m_obj_encontrado = mapa_mils_digitos.get(digitos_mat[:6])

            if m_obj_encontrado:
                m_id = str(m_obj_encontrado.get("id"))
                pair_linha = (m_id, equipe_corrente)
                if pair_linha not in chaves_novas:
                    chaves_novas.append(pair_linha)

                total_horas_linha = 0.0
                dias_abatidos = 0

                for d in range(1, num_dias_mes + 1):
                    col_dia = mapa_colunas_dias.get(d)
                    if col_dia is not None and col_dia in row:
                        val_celula = str(row.get(col_dia, "")).strip()
                        if val_celula and val_celula.upper() not in ["NAN", "NONE", ""]:
                            if val_celula.endswith(".0"):
                                val_celula = val_celula[:-2]
                            val_u = val_celula.upper()
                            grade_nova[f"{m_id}_{equipe_corrente}_{m_ano}_{m_mes:02d}_{d:02d}"] = val_u

                            h_turno = float(mapa_horas_informadas.get(val_u, 0.0))
                            total_horas_linha += h_turno

                            if val_u in SIGLAS_ABATEM_META:
                                dias_abatidos += 1
                        else:
                            grade_nova[f"{m_id}_{equipe_corrente}_{m_ano}_{m_mes:02d}_{d:02d}"] = "F"
                    else:
                        grade_nova[f"{m_id}_{equipe_corrente}_{m_ano}_{m_mes:02d}_{d:02d}"] = "F"

                cfg_bh = st.session_state.get("bh_configs", {}).get(m_id, {})
                carga_base_mes = 80.0 if cfg_bh.get("reduzida") else 160.0
                taxa_diaria = carga_base_mes / float(num_dias_mes)
                meta_apurada = max(0.0, (num_dias_mes - dias_abatidos) * taxa_diaria)

                st.session_state["resumo_horas_passo6"][m_id] = {
                    "horas_trabalhadas": total_horas_linha,
                    "meta": meta_apurada,
                    "tpb": 0.0
                }

                linhas_importadas += 1
            else:
                identificador = val_militar_txt or val_mat_txt
                if identificador and len(identificador) > 2:
                    militares_nao_localizados.append(identificador)

        if linhas_importadas > 0:
            st.session_state["militares_no_quadro_chaves"] = chaves_novas
            st.session_state["grade_escala_lancamentos"] = grade_nova
            executar_auto_save_banco()
            emitir_sinal_atualizacao_espelho()
            return True, f"✅ {linhas_importadas} militar(es) importado(s) com sucesso!"
        else:
            return False, "Nenhum militar localizado na base de efetivo."
    except Exception as ex_imp:
        return False, f"Erro ao processar: {ex_imp}"


def renderizar_passo6():
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    num_dias_mes = calendar.monthrange(m_ano, m_mes)[1]
    
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    unidade = str(st.session_state.get("cfg_unidade") or usr_dados.get("unidade") or "21º BPM").strip().upper()
    subunidade = str(usr_dados.get("subunidade") or usr_dados.get("lotacao") or st.session_state.get("cfg_subunidade") or "111ª CIA PM").strip().upper()
    
    img_brasao = obter_brasao_base64()
    mils_todos = st.session_state.get("lista_militares", []) or carregar_militares_supabase() or []

    nome_resp_escala = str(st.session_state.get("p5_elaborador_sel") or "GESTOR P3").strip().upper()
    nome_homologador = str(st.session_state.get("p5_homologador_sel") or "COMANDANTE DA CIA").strip().upper()

    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
    grade_lancamentos = st.session_state.get("grade_escala_lancamentos", {})

    with st.expander("📌 PASSO 6: Visualização da Escala, Importação e Exportação Oficial", expanded=True):

        # ----------------------------------------------------------------------
        # SEÇÃO DE UPLOAD COM PAINEL LIMPO DE CONFIRMAÇÃO DE LEGENDAS
        # ----------------------------------------------------------------------
        st.markdown("##### 📥 **Importar Escala Mensal (.xlsx / .csv / .pdf):**")
        arq_escala_up = st.file_uploader(
            "Selecione o arquivo da escala:", 
            type=["xlsx", "xls", "pdf", "csv"], 
            key="p6_uploader_escala_principal",
            label_visibility="collapsed"
        )

        if arq_escala_up is not None:
            ext_arq = arq_escala_up.name.lower()

            if ext_arq.endswith((".xlsx", ".xls", ".csv")):
                df_temp = carregar_planilha_universal_passo6(arq_escala_up)
                siglas_detectadas = escanear_siglas_da_planilha(df_temp, num_dias_mes)

                if siglas_detectadas:
                    st.info(f"📋 **Legendas de turnos identificadas ({len(siglas_detectadas)} siglas):** Confirme a quantidade de horas de cada turno:")
                    
                    sugestoes_padrao = {
                        "1": 12.5, "2": 13.5, "3": 10.5, "4": 10.5, 
                        "7": 3.0, "S": 6.0, "EE": 6.0
                    }

                    mapa_valores_confirmados = {}
                    cols_sig = st.columns(min(6, max(1, len(siglas_detectadas))))

                    for idx_s, s_code in enumerate(siglas_detectadas):
                        val_padrao = sugestoes_padrao.get(s_code, 12.0)
                        with cols_sig[idx_s % len(cols_sig)]:
                            h_inf = st.number_input(
                                f"Turno `{s_code}` (Horas):",
                                min_value=0.0,
                                max_value=24.0,
                                value=float(val_padrao),
                                step=0.5,
                                key=f"input_h_sig_{s_code}"
                            )
                            mapa_valores_confirmados[s_code] = h_inf

                    if st.button("🚀 Processar e Carregar Escala com os Valores Confirmados", type="primary", use_container_width=True):
                        with st.spinner("Processando equipes, matrículas e aplicando horas..."):
                            sucesso, msg = processar_planilha_escala_passo6(
                                df_temp, m_ano, m_mes, num_dias_mes, mapa_valores_confirmados, substituir_quadro=True
                            )
                            if sucesso:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                else:
                    if st.button("🚀 Processar Escala Importada", type="secondary", use_container_width=True):
                        sucesso, msg = processar_planilha_escala_passo6(
                            df_temp, m_ano, m_mes, num_dias_mes, {}, substituir_quadro=True
                        )
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        st.divider()

        # ----------------------------------------------------------------------
        # TABELA VISUAL / ESPELHO OFICIAL
        # ----------------------------------------------------------------------
        mils_linhas_quadro = []
        for pair in chaves_quadro:
            if isinstance(pair, (tuple, list)) and len(pair) == 2:
                m_obj = next((m for m in mils_todos if str(m.get("id")).strip() == str(pair[0]).strip()), None)
                if m_obj:
                    mils_linhas_quadro.append({
                        "id": str(pair[0]).strip(), 
                        "equipe": pair[1], 
                        "posto_grad": padronizar_graduacao(m_obj.get("posto_grad")), 
                        "nome_guerra": m_obj.get("nome_guerra", "MILITAR"), 
                        "num_policia": m_obj.get("num_policia", ""), 
                        "chave_linha": f"{pair[0]}_{pair[1]}"
                    })

        mils_escala_ord = sorted(mils_linhas_quadro, key=lambda x: (
            st.session_state.get("ordem_customizada_map", {}).get(x["chave_linha"], 99), 
            PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99), 
            x["nome_guerra"]
        ))

        header_dias_html = ""
        cols_excel_names = ["EQUIPE", "Nº POLÍCIA", "MILITAR"]

        for d in range(1, num_dias_mes + 1):
            dia_sem_idx = calendar.weekday(m_ano, m_mes, d)
            sigla_sem = DIAS_SEMANA_SIGLAS[dia_sem_idx]
            bg_class = "th-weekend" if dia_sem_idx in [5, 6] else "th-weekday"
            
            header_dias_html += f"""
                <th class="{bg_class}">
                    <div class="d-num">{d}</div>
                    <div class="d-sig">{sigla_sem}</div>
                </th>
            """
            cols_excel_names.append(f"{d} {sigla_sem}")

        cols_excel_names.append("HORAS TRAB / META")
        tbody_html = ""
        linhas_excel_data = []
        equipes_unicas = list(dict.fromkeys([m["equipe"] for m in mils_escala_ord]))

        resumo_p6 = st.session_state.get("resumo_horas_passo6", {})

        for eq_nome in equipes_unicas:
            mils_da_eq = [m for m in mils_escala_ord if m["equipe"] == eq_nome]
            rowspan_eq = len(mils_da_eq)
            cor_bg_eq = obter_cor_equipe(eq_nome)

            for idx_m, item in enumerate(mils_da_eq):
                m_id = item["id"]
                pg = padronizar_graduacao(item["posto_grad"])
                nome_g = item["nome_guerra"]
                num_pol = item["num_policia"]
                
                row_html = "<tr>"
                if idx_m == 0: 
                    row_html += f"""
                        <td rowspan="{rowspan_eq}" class="td-equipe" style="background-color: {cor_bg_eq} !important; color: #ffffff !important;">
                            {eq_nome}
                        </td>
                    """
                row_html += f"""
                    <td class="td-num-policia">{num_pol}</td>
                    <td class="td-militar">
                        <div class="m-nome">{pg} {nome_g}</div>
                    </td>
                """

                linha_xls = [eq_nome, num_pol, f"{pg} {nome_g}"]
                total_horas_calc = 0.0
                neutros = 0

                for d in range(1, num_dias_mes + 1):
                    val = grade_lancamentos.get(f"{m_id}_{eq_nome}_{m_ano}_{m_mes:02d}_{d:02d}", "F")
                    val_raw = str(val).strip()
                    val_str = val_raw.upper()

                    dt_ref_dia = datetime.date(m_ano, m_mes, d)
                    eh_sup = (eq_nome == "SUPERVISÃO" or "SUPERVISÃO" in val_str)
                    total_horas_calc += calcular_horas_efetivas_turno(val_str, dt_ref_dia, eh_supervisao=eh_sup)

                    tokens_dia = set(val_str.replace("/", " ").split())
                    if any(sig in tokens_dia for siglic in [SIGLAS_ABATEM_META] for sig in siglic if sig not in ["F", "D", "X"]):
                        neutros += 1

                    cell_content = ""
                    if val_raw not in ["F", "D", "X", "", None, "0"]:
                        cell_content = f'<div class="shift-badge">{val_raw}</div>'
                        linha_xls.append(val_raw)
                    elif val_raw in ["D", "F"]:
                        cell_content = f'<div style="font-weight: bold; color: #64748b;">{val_raw}</div>'
                        linha_xls.append(val_raw)
                    elif val_raw in SIGLAS_DIAS_NEUTROS:
                        cell_content = f'<div class="shift-badge" style="background-color: #fca5a5 !important; border-color: #f87171 !important;">{val_raw}</div>'
                        linha_xls.append(val_raw)
                    elif val_raw == "X":
                        cell_content = '<div class="shift-x">X</div>'
                        linha_xls.append("X")
                    else:
                        linha_xls.append(str(val_raw) if val_raw else "")
                        
                    row_html += f'<td class="td-day">{cell_content}</td>'

                dados_m_p6 = resumo_p6.get(m_id, {})
                if dados_m_p6.get("horas_trabalhadas") is not None:
                    total_horas = dados_m_p6["horas_trabalhadas"]
                    meta_efetiva = dados_m_p6["meta"] if dados_m_p6.get("meta") is not None else 160.0
                else:
                    cfg_bh = st.session_state.get("bh_configs", {}).get(str(m_id), {})
                    carga_base_mes = 80.0 if cfg_bh.get("reduzida") else 160.0
                    taxa_diaria = carga_base_mes / float(num_dias_mes)
                    dias_efetivos = num_dias_mes - neutros
                    meta_efetiva = max(0.0, dias_efetivos * taxa_diaria)
                    total_horas = total_horas_calc

                saldo_horas = total_horas - meta_efetiva
                prefixo_alerta = "⚠️ " if saldo_horas > 0 else ""
                cor_saldo = "#b91c1c" if saldo_horas > 0 else "#2563eb"

                row_html += f"""
                    <td class="td-horas">
                        <div class="h-main">{prefixo_alerta}{total_horas:.1f}h / {meta_efetiva:.1f}h</div>
                        <div class="h-sub" style="color: {cor_saldo} !important;">{saldo_horas:+.1f}h</div>
                    </td>
                </tr>
                """
                tbody_html += row_html
                linha_xls.append(f"{prefixo_alerta}{total_horas:.1f}h / {meta_efetiva:.1f}h\n({saldo_horas:+.1f}h)")
                linhas_excel_data.append(linha_xls)

        df_excel_export = pd.DataFrame(linhas_excel_data, columns=cols_excel_names)
        mes_ano_str = f"{m_mes:02d}/{m_ano}"
        
        texto_legenda_final = "LEGENDA DE HORÁRIOS: 1 = 06:00 às 18:00 | 2 = 18:00 às 06:00 | 3 = 13:00 às 23:00 | 4 = 06:00 às 16:00 | S = SOBREAVISO | EE = ESCALA ESPECIAL"

        html_documento = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; box-sizing: border-box; }}
                @media print {{ @page {{ size: A4 landscape; margin: 4mm; }} body {{ background: #ffffff !important; padding: 0 !important; }} }}
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 8px; color: #0f172a; }}
                .card-container {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; width: 100%; }}
                .header-table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; border-bottom: 2px solid #cbd5e1; }}
                .header-table td {{ border: none !important; padding: 2px; }}
                .brasao-box {{ width: 65px; height: 65px; border: 1px solid #cbd5e1; border-radius: 6px; padding: 2px; display: flex; align-items: center; justify-content: center; background-color: #ffffff; }}
                .brasao-img {{ max-height: 100%; max-width: 100%; object-fit: contain; }}
                .header-titles {{ text-align: center; }}
                .header-titles h2 {{ margin: 0; font-size: 15px; font-weight: 900; color: #0f172a; text-transform: uppercase; }}
                .header-titles h3 {{ margin: 2px 0; font-size: 13px; font-weight: 800; color: #1e3a8a; text-transform: uppercase; }}
                .header-titles h4 {{ margin: 2px 0 0 0; font-size: 11px; font-weight: 800; color: #334155; text-transform: uppercase; }}
                table.escala-table {{ width: 100%; border-collapse: collapse; font-size: 9px; table-layout: auto; }}
                table.escala-table th, table.escala-table td {{ border: 1px solid #94a3b8; text-align: center; vertical-align: middle; padding: 2px 0px; }}
                th.th-eq {{ width: 5%; background: #e2e8f0; font-weight: 800; }}
                th.th-num {{ width: 7%; background: #e2e8f0; font-weight: 800; }}
                th.th-mil {{ width: 11%; background: #e2e8f0; font-weight: 800; }}
                th.th-hor {{ width: 7%; background: #e2e8f0; font-weight: 800; }}
                th.th-weekday {{ background: #e0f2fe !important; color: #0369a1 !important; }}
                th.th-weekend {{ background: #ffe4e6 !important; color: #be123c !important; }}
                .d-num {{ font-size: 10px; font-weight: 800; }}
                .d-sig {{ font-size: 7px; font-weight: 700; text-transform: uppercase; }}
                td.td-equipe {{ font-weight: 900 !important; font-size: 10px; text-transform: uppercase; word-wrap: break-word; }}
                td.td-num-policia {{ font-weight: 700; font-size: 8px; color: #475569; background: #ffffff; }}
                td.td-militar {{ text-align: center; padding: 2px; background: #ffffff; }}
                .m-nome {{ font-weight: 800; font-size: 9px; color: #0f172a; text-transform: uppercase; }}
                td.td-day {{ background: #ffffff; height: 34px; min-width: 20px; }}
                .shift-badge {{ background-color: #fef08a !important; color: #0f172a !important; font-weight: 900; font-size: 8px; padding: 2px 0px; border-radius: 3px; border: 1px solid #fde047; text-transform: uppercase; display: inline-block; width: 95%; }}
                .shift-x {{ color: #dc2626 !important; font-weight: 900; font-size: 11px; }}
                td.td-horas {{ background: #ffffff; }}
                .h-main {{ font-weight: 800; font-size: 8.5px; color: #0f172a; }}
                .h-sub {{ font-weight: 800; font-size: 8.5px; margin-top: 1px; }}
                table.signatures-table {{ width: 100%; margin-top: 25px; border-collapse: collapse; }}
                table.signatures-table td {{ border: none !important; text-align: center; width: 50%; }}
                .sig-title {{ font-weight: 800; font-size: 10px; color: #0f172a; margin-bottom: 2px; }}
                .sig-name {{ font-weight: 800; font-size: 9.5px; color: #334155; text-transform: uppercase; }}
            </style>
        </head>
        <body>
            <div class="card-container">
                <table class="header-table">
                    <tr>
                        <td style="width: 70px;">
                            <div class="brasao-box">
                                <img src="{img_brasao}" class="brasao-img" alt="Brasão PMMG" />
                            </div>
                        </td>
                        <td class="header-titles">
                            <h2>POLÍCIA MILITAR DE MINAS GERAIS — {unidade}</h2>
                            <h3>{subunidade}</h3>
                            <h4>QUADRO GERAL DE ESCALA DE SERVIÇO - {mes_ano_str}</h4>
                        </td>
                        <td style="width: 70px;"></td>
                    </tr>
                </table>

                <table class="escala-table">
                    <thead>
                        <tr>
                            <th class="th-eq">EQUIPE</th>
                            <th class="th-num">Nº POLÍCIA</th>
                            <th class="th-mil">MILITAR</th>
                            {header_dias_html}
                            <th class="th-hor">HORAS<br><span style="font-size:6.5px; font-weight:normal;">TRAB / META</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        {tbody_html}
                    </tbody>
                </table>
                
                <div style="font-size: 10px; font-weight: bold; color: #b91c1c; text-align: left; margin-top: 10px;">
                    {texto_legenda_final}
                </div>

                <table class="signatures-table">
                    <tr>
                        <td>
                            <div class="sig-title">Responsável pela Escala</div>
                            <div class="sig-name">{nome_resp_escala}</div>
                        </td>
                        <td>
                            <div class="sig-title">Homologado por / Comandante</div>
                            <div class="sig-name">{nome_homologador}</div>
                        </td>
                    </tr>
                </table>
            </div>
        </body>
        </html>
        """

        components.html(html_documento, height=520, scrolling=True)

        st.divider()

        c_act1, c_act2 = st.columns([1, 1], gap="small")
        with c_act1:
            bytes_xls = gerar_excel_escala(df_excel_export, unidade, subunidade, mes_ano_str, nome_homologador, nome_resp_escala, "", texto_legenda_final)
            st.download_button(
                "📊 Baixar Escala em Excel (.xlsx)", 
                data=bytes_xls, 
                file_name=f"Escala_{subunidade}_{m_mes:02d}_{m_ano}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                use_container_width=True
            )
            
        with c_act2: 
            if st.button("🖨️ Imprimir / Salvar PDF", type="primary", use_container_width=True):
                components.html(
                    f"""
                    <script>
                    const printWin = window.open('', '_blank');
                    printWin.document.write(`{html_documento}`);
                    printWin.document.close();
                    printWin.focus();
                    setTimeout(() => {{ printWin.print(); }}, 600);
                    </script>
                    """,
                    height=0
                )