import streamlit as st
import datetime
import calendar
import pandas as pd
import io
import os
import base64
import copy
import re
import streamlit.components.v1 as components

from core.database import supabase, carregar_militares_supabase
from modules.escalas.passos.passo3_efetivo import padronizar_graduacao, PESOS_HIERARQUIA
from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS
from modules.escalas.passos.passo5_quadro import executar_auto_save_banco

SIGLAS_DIAS_NEUTROS = [
    "FER", "FERIAS", "FÉRIAS", "FE",
    "LTSP", "LM", "LMM",
    "ATEST", "ATESTADO", "ATE",
    "LUTO", "NUPCIAS", "NÚPCIAS", "LUT", "NUP", "DN", "DNT"
]

URL_BRASAO_PADRAO = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Bras%C3%A3o_PMMG.svg/500px-Bras%C3%A3o_PMMG.svg.png"

CORES_EQUIPES = {
    "CPU": "#a16207", 
    "RP": "#1e293b", 
    "SUPERVISÃO": "#b91c1c", 
    "ADMINISTRAÇÃO": "#0f766e", 
    "TM ALPHA": "#0369a1", 
    "GEPAR": "#047857",
    "A": "#1e3a8a",
    "B": "#065f46",
    "C": "#9a3412"
}

def obter_brasao_base64(url_padrao):
    caminho_local = "assets/brasao.png"
    if os.path.exists(caminho_local):
        try:
            with open(caminho_local, "rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode("utf-8")
                return f"data:image/png;base64,{encoded}"
        except Exception:
            pass
    return url_padrao

def obter_cor_equipe(eq): 
    return CORES_EQUIPES.get(str(eq).upper().strip(), "#475569")

def extrair_matricula_limpa(valor):
    val_str = str(valor).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    return re.sub(r'\D', '', val_str).lstrip('0')

def calcular_horas_por_legenda(val_str, mapa_horarios):
    v = str(val_str).upper().strip()
    if not v or v in ["F", "D", "X", "NAN", "NONE", "0"] or any(sigla in v for sigla in SIGLAS_DIAS_NEUTROS):
        return 0.0

    h_ini_str, h_fim_str = None, None

    # 1. Busca primeiro no dicionário de legendas mapeadas (ex: '1', '2', 'RH', 'TPB')
    if v in mapa_horarios:
        h_ini_str = mapa_horarios[v].get("inicio")
        h_fim_str = mapa_horarios[v].get("fim")

    # 2. Se não achou no mapa, tenta extrair horário do texto no formato HH:MM (ex: 19:00 às 07:00, 19/07)
    if not h_ini_str or not h_fim_str:
        m = re.findall(r'(\d{1,2})(?::(\d{2}))?\s*(?:ÀS|AS|-|A|/)\s*(\d{1,2})(?::(\d{2}))?', v)
        if m:
            h1, m1 = int(m[0][0]), int(m[0][1]) if m[0][1] else 0
            h2, m2 = int(m[0][2]), int(m[0][3]) if m[0][3] else 0
            h_ini_str = f"{h1:02d}:{m1:02d}"
            h_fim_str = f"{h2:02d}:{m2:02d}"

    # Se mesmo assim não achar horário válido, assume 12h padrão
    if not h_ini_str or not h_fim_str:
        return 12.0

    try:
        h_i = datetime.datetime.strptime(h_ini_str, "%H:%M")
        h_f = datetime.datetime.strptime(h_fim_str, "%H:%M")

        dt_curr = datetime.datetime(2026, 1, 1, h_i.hour, h_i.minute)
        dt_fim = datetime.datetime(2026, 1, 1, h_f.hour, h_f.minute)

        if dt_fim <= dt_curr:
            dt_fim += datetime.timedelta(days=1)

        horas_efetivas = 0.0
        while dt_curr < dt_fim:
            hora_atual = dt_curr.hour
            # Bonificação noturna de +10 min por hora (23:00 às 05:00) => Fator (70/60)
            is_noturno = (hora_atual >= 23 or hora_atual < 5)
            fator_minuto = (70.0 / 60.0) if is_noturno else 1.0
            horas_efetivas += (1.0 / 60.0) * fator_minuto
            dt_curr += datetime.timedelta(minutes=1)

        return horas_efetivas
    except Exception:
        return 12.0

    dt_ini, dt_fim = None, None

    # 1. Tenta mapear diretamente pelo dicionário de legendas
    if v in mapa_horarios:
        info = mapa_horarios[v]
        try:
            h_i = datetime.datetime.strptime(info["inicio"], "%H:%M")
            h_f = datetime.datetime.strptime(info["fim"], "%H:%M")
            dt_ini = datetime.datetime(2026, 1, 1, h_i.hour, h_i.minute)
            dt_fim = datetime.datetime(2026, 1, 1, h_f.hour, h_f.minute)
            if dt_fim <= dt_ini:
                dt_fim += datetime.timedelta(days=1)
        except Exception:
            pass

    # 2. Se não encontrou no mapa, faz o parse de padrões flexíveis no texto
    if not dt_ini:
        m = re.findall(r'(\d{1,2})(?::(\d{2}))?\s*(?:ÀS|AS|-|A|/)\s*(\d{1,2})(?::(\d{2}))?', v)
        if m:
            try:
                h1, m1 = int(m[0][0]), int(m[0][1]) if m[0][1] else 0
                h2, m2 = int(m[0][2]), int(m[0][3]) if m[0][3] else 0
                dt_ini = datetime.datetime(2026, 1, 1, h1, m1)
                dt_fim = datetime.datetime(2026, 1, 1, h2, m2)
                if dt_fim <= dt_ini:
                    dt_fim += datetime.timedelta(days=1)
            except Exception:
                pass

    if not dt_ini or not dt_fim:
        return 12.0

    # 3. Cálculo minuto a minuto aplicando bonificação noturna de +10 min/hora (23:00 às 05:00)
    horas_efetivas = 0.0
    dt_curr = dt_ini

    while dt_curr < dt_fim:
        hora_atual = dt_curr.hour
        is_noturno = (hora_atual >= 23 or hora_atual < 5)
        fator_minuto = (70.0 / 60.0) if is_noturno else 1.0
        horas_efetivas += (1.0 / 60.0) * fator_minuto
        dt_curr += datetime.timedelta(minutes=1)

    return horas_efetivas

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
        
        worksheet.merge_range(0, 0, 0, num_cols-1, f"{unidade.upper()}", fmt_titulo)
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
        worksheet.merge_range(linha_excel, c_mit, linha_excel, num_cols-1, "Comandante da Cia", fmt_sig_bold)
        worksheet.merge_range(linha_excel+1, c_mit, linha_excel+1, num_cols-1, cmt_cia_str.upper(), fmt_sig_text)
        
    return output.getvalue()

def renderizar_passo6():
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    num_dias_mes = calendar.monthrange(m_ano, m_mes)[1]
    
    unidade = st.session_state.get("cfg_unidade", "UNIDADE OPERACIONAL")
    subunidade = st.session_state.get("cfg_subunidade", "PEL/COMPANHIA")
    
    img_brasao_cfg = st.session_state.get("cfg_brasao_url", URL_BRASAO_PADRAO)
    img_brasao = obter_brasao_base64(img_brasao_cfg)
    
    mils_todos = st.session_state.get("lista_militares", []) or carregar_militares_supabase() or []
    usr_logado = st.session_state.get("usuario_dados", {})
    
    mat_usr = str(usr_logado.get("usuario_login") or usr_logado.get("usuario") or "").strip().upper()
    mil_usr_obj = next((m for m in mils_todos if str(m.get("num_policia")).strip().replace("-", "") == mat_usr.replace("-", "")), None)
    
    if mil_usr_obj:
        pg_usr = padronizar_graduacao(mil_usr_obj.get("posto_grad"))
        ng_usr = mil_usr_obj.get("nome_guerra", "OPERADOR").strip().upper()
        nome_resp_escala = f"{pg_usr} {ng_usr}"
    else:
        cargo_raw = usr_logado.get('cargo_funcao') or usr_logado.get('posto_grad') or 'ESCALANTE'
        ng_usr = usr_logado.get('nome_guerra', 'OPERADOR').strip().upper()
        nome_resp_escala = f"{padronizar_graduacao(cargo_raw)} {ng_usr}"

    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
    grade_lancamentos = st.session_state.get("grade_escala_lancamentos", {})

    with st.expander("📌 PASSO 6: Visualização da Escala, Importação e Exportação Oficial", expanded=True):
        
        turnos_encontrados = set()
        for d in range(1, num_dias_mes + 1):
            for pair in chaves_quadro:
                if len(pair) == 2:
                    val = grade_lancamentos.get(f"{pair[0]}_{pair[1]}_{m_ano}_{m_mes:02d}_{d:02d}", "")
                    val_s = str(val).strip().upper()
                    if val_s and val_s not in ["F", "D", "X", "FE", "LM", "ATE", "NONE", "NAN", "", "0"]:
                        turnos_encontrados.add(val_s)

        legendas_lista = sorted(list(turnos_encontrados)) if turnos_encontrados else ["1", "2", "RH", "TPB"]
        mapa_horarios = st.session_state.get("mapa_legendas_custom", {})

        with st.expander("⚙️ Editar / Mapear Legendas de Horários (Clique para Expandir)", expanded=False):
            st.caption("Verifique ou troque os horários das siglas detectadas na escala para que a contagem final de horas e PDF fiquem exatos.")
            
            cols_leg = st.columns(min(4, max(1, len(legendas_lista))))
            for idx_leg, leg_code in enumerate(legendas_lista):
                with cols_leg[idx_leg % len(cols_leg)]:
                    st.markdown(f"**Sigla/Legenda: `{leg_code}`**")
                    def_ini = mapa_horarios.get(leg_code, {}).get("inicio", "19:00" if leg_code == "2" else "07:00")
                    def_fim = mapa_horarios.get(leg_code, {}).get("fim", "07:00" if leg_code == "2" else "19:00")
                    
                    h_ini = st.text_input(f"Início ({leg_code})", value=def_ini, key=f"leg_ini_{leg_code}")
                    h_fim = st.text_input(f"Término ({leg_code})", value=def_fim, key=f"leg_fim_{leg_code}")
                    mapa_horarios[leg_code] = {"inicio": h_ini, "fim": h_fim}
            
            st.session_state["mapa_legendas_custom"] = mapa_horarios

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
                total_horas = 0.0
                dias_neutros_cnt = 0

                for d in range(1, num_dias_mes + 1):
                    val = grade_lancamentos.get(f"{m_id}_{eq_nome}_{m_ano}_{m_mes:02d}_{d:02d}", "F")
                    val_raw = str(val).strip()
                    val_str = val_raw.upper()

                    total_horas += calcular_horas_por_legenda(val_str, mapa_horarios)

                    tokens_dia = set(val_str.replace("/", " ").split())
                    if any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                        dias_neutros_cnt += 1

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

                cfg_bh = st.session_state.get("bh_configs", {}).get(str(m_id), {})
                eh_reduzida = cfg_bh.get("reduzida", False)
                carga_base_mes = 80.0 if eh_reduzida else 160.0
                
                taxa_diaria = carga_base_mes / float(num_dias_mes)
                dias_efetivos = num_dias_mes - dias_neutros_cnt
                meta_efetiva = max(0.0, dias_efetivos * taxa_diaria)
                saldo_horas = total_horas - meta_efetiva
                
                row_html += f"""
                    <td class="td-horas">
                        <div class="h-main">{total_horas:.0f}h / {meta_efetiva:.1f}h</div>
                        <div class="h-sub">{saldo_horas:+.1f}h</div>
                    </td>
                </tr>
                """
                tbody_html += row_html
                linha_xls.append(f"{total_horas:.0f}h / {meta_efetiva:.1f}h\n({saldo_horas:+.1f}h)")
                linhas_excel_data.append(linha_xls)

        df_excel_export = pd.DataFrame(linhas_excel_data, columns=cols_excel_names)
        mes_ano_str = f"{m_mes:02d}/{m_ano}"
        
        leg_str_list = [f"{k} = {v['inicio']} às {v['fim']}" for k, v in mapa_horarios.items()]
        texto_legenda_final = "LEGENDA DE HORÁRIOS:   " + "   |   ".join(leg_str_list) if leg_str_list else ""

        html_documento = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; box-sizing: border-box; }}
                @media print {{ @page {{ size: A4 landscape; margin: 4mm; }} body {{ background: #ffffff !important; padding: 0 !important; }} }}
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 8px; color: #0f172a; }}
                .card-container {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; width: 100%; }}
                .header-table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; border-bottom: 2px solid #cbd5e1; }}
                .header-table td {{ border: none !important; padding: 2px; }}
                .brasao-box {{ width: 65px; height: 65px; border: 1px solid #cbd5e1; border-radius: 6px; padding: 2px; display: flex; align-items: center; justify-content: center; background-color: #ffffff; }}
                .brasao-img {{ max-height: 100%; max-width: 100%; object-fit: contain; }}
                .header-titles {{ text-align: center; }}
                .header-titles h2 {{ margin: 0; font-size: 16px; font-weight: 900; color: #0f172a; text-transform: uppercase; }}
                .header-titles h3 {{ margin: 1px 0; font-size: 12px; font-weight: 700; color: #475569; text-transform: uppercase; }}
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
                .h-sub {{ font-weight: 800; font-size: 8.5px; color: #2563eb; margin-top: 1px; }}
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
                            <h2>{unidade}</h2>
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
                            <div class="sig-title">Comandante da Cia</div>
                            <div class="sig-name">{st.session_state.get('p6_cmt_cia_sel', 'TEN CEL LOPES')}</div>
                        </td>
                    </tr>
                </table>
            </div>
        </body>
        </html>
        """

        components.html(html_documento, height=520, scrolling=True)
        st.divider()

        # --- LINHA INFERIOR DE AÇÕES: IMPORTAÇÃO DE ARQUIVOS (EXCEL E PDF) ---
        c_act1, c_act2, c_act3 = st.columns([1.3, 1, 1], gap="small")
        
        with c_act1:
            arq_escala_up = st.file_uploader(
                "📥 Importar Escala (.xlsx / .pdf):", 
                type=["xlsx", "xls", "pdf"], 
                key="p6_uploader_escala_bottom",
                label_visibility="collapsed"
            )

            if arq_escala_up is not None:
                ext_arq = arq_escala_up.name.lower()
                
                if ext_arq.endswith(".pdf"):
                    if st.button("🚀 Processar Texto do PDF", type="secondary", use_container_width=True):
                        texto_pdf = extrair_texto_pdf(arq_escala_up)
                        if texto_pdf:
                            st.session_state["p6_texto_pdf_lido"] = texto_pdf
                            st.success("✅ Texto do PDF extraído! Defina os horários das legendas acima para aplicar.")
                        else:
                            st.warning("⚠️ Não foi possível ler texto estruturado neste PDF.")

                elif ext_arq.endswith((".xlsx", ".xls")):
                    if st.button("🚀 Processar Escala Importada", type="secondary", use_container_width=True):
                        try:
                            xls_imp = pd.ExcelFile(arq_escala_up)
                            mapa_auto_leg = copy.deepcopy(mapa_horarios)
                            
                            if len(xls_imp.sheet_names) > 1:
                                try:
                                    df_leg = pd.read_excel(arq_escala_up, sheet_name=1)
                                    df_leg.columns = [str(c).strip().lower() for c in df_leg.columns]
                                    if "legenda" in df_leg.columns and "horario" in df_leg.columns:
                                        for _, r_leg in df_leg.dropna(subset=["horario"]).iterrows():
                                            leg_k = str(r_leg["legenda"]).strip().upper()
                                            hor_v = str(r_leg["horario"]).strip()
                                            parts = re.split(r'[/|-|às|as]', hor_v, flags=re.IGNORECASE)
                                            if len(parts) >= 2:
                                                mapa_auto_leg[leg_k] = {"inicio": parts[0].strip(), "fim": parts[1].strip()}
                                        st.session_state["mapa_legendas_custom"] = mapa_auto_leg
                                except Exception:
                                    pass

                            df_raw = pd.read_excel(arq_escala_up, sheet_name=0, header=None)
                            header_idx = None
                            for idx_r, r_vals in df_raw.iterrows():
                                line_str = [str(v).strip().upper() for v in r_vals.values if pd.notna(v)]
                                if any(k in line_str for k in ["EQUIPE", "MILITAR", "Nº POLÍCIA", "POLICIA", "NUMERO", "NÚMERO"]):
                                    header_idx = idx_r
                                    break

                            if header_idx is None: header_idx = 3
                            df_imp = pd.read_excel(arq_escala_up, sheet_name=0, header=header_idx)
                            df_imp.columns = [str(c).strip().upper() for c in df_imp.columns]

                            grade_nova = copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {}))
                            chaves_novas = list(st.session_state.get("militares_no_quadro_chaves", []))
                            mils_cad = st.session_state.get("lista_militares", []) or carregar_militares_supabase() or []
                            
                            mapa_mils_digitos = {}
                            for m in mils_cad:
                                num_p_dig = extrair_matricula_limpa(m.get("num_policia", ""))
                                if num_p_dig: mapa_mils_digitos[num_p_dig] = m

                            col_equipe = next((c for c in df_imp.columns if "EQUIPE" in c), None)
                            col_matricula = next((c for c in df_imp.columns if any(k in c for k in ["POLICIA", "POLÍCIA", "NUMERO", "NÚMERO", "MATRICULA", "MATRÍCULA"])), None)
                            col_militar = next((c for c in df_imp.columns if any(k in c for k in ["MILITAR", "NOME", "SERVIDOR"])), None)

                            linhas_importadas = 0
                            for idx_row, row in df_imp.iterrows():
                                eq_imp = str(row.get(col_equipe, "A")).strip().upper() if col_equipe else "A"
                                val_militar_txt = str(row.get(col_militar, "")).strip().upper() if col_militar else ""
                                val_mat_txt = str(row.get(col_matricula, "")).strip() if col_matricula else ""

                                if any(k in f"{eq_imp} {val_militar_txt}".upper() for k in ["RESPONSÁVEL", "COMANDANTE DA CIA"]):
                                    break

                                digitos_mat = extrair_matricula_limpa(val_mat_txt)
                                if not digitos_mat and val_militar_txt:
                                    digitos_mat = extrair_matricula_limpa(val_militar_txt)

                                m_obj_encontrado = mapa_mils_digitos.get(digitos_mat)
                                if m_obj_encontrado:
                                    m_id = str(m_obj_encontrado.get("id"))
                                    pair = (m_id, eq_imp)
                                    if pair not in chaves_novas:
                                        chaves_novas.append(pair)

                                    for d in range(1, num_dias_mes + 1):
                                        col_dia = next((c for c in df_imp.columns if re.match(rf'^{d}\b', c.strip())), None)
                                        if col_dia:
                                            val_celula = str(row.get(col_dia, "")).strip()
                                            if val_celula and val_celula.upper() not in ["NAN", "NONE"]:
                                                if val_celula.endswith(".0"): val_celula = val_celula[:-2]
                                                grade_nova[f"{m_id}_{eq_imp}_{m_ano}_{m_mes:02d}_{d:02d}"] = val_celula.upper()
                                            else:
                                                grade_nova[f"{m_id}_{eq_imp}_{m_ano}_{m_mes:02d}_{d:02d}"] = "F"
                                    linhas_importadas += 1

                            if linhas_importadas > 0:
                                st.session_state["militares_no_quadro_chaves"] = chaves_novas
                                st.session_state["grade_escala_lancamentos"] = grade_nova
                                executar_auto_save_banco()
                                st.success(f"✅ {linhas_importadas} militar(es) importado(s) com sucesso!")
                                st.rerun()
                        except Exception as ex_imp:
                            st.error(f"Erro ao processar importação: {ex_imp}")

        with c_act2:
            bytes_xls = gerar_excel_escala(df_excel_export, unidade, subunidade, mes_ano_str, st.session_state.get('p6_cmt_cia_sel', 'TEN CEL LOPES'), nome_resp_escala, "", texto_legenda_final)
            st.download_button(
                "📊 Baixar Escala em Excel (.xlsx)", 
                data=bytes_xls, 
                file_name=f"Escala_{m_mes:02d}_{m_ano}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                use_container_width=True
            )
            
        with c_act3: 
            if st.button("🖨️ Imprimir / Salvar PDF", type="primary", use_container_width=True):
                components.html(html_documento + "<script>window.print();</script>", height=600, scrolling=True)