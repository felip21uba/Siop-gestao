import streamlit as st
import datetime
import calendar
import pandas as pd
import io
import streamlit.components.v1 as components
from modules.escalas.passos.passo3_efetivo import padronizar_graduacao, PESOS_HIERARQUIA
from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS

SIGLAS_DIAS_NEUTROS = [
    "FER", "FERIAS", "FÉRIAS", "FE",
    "LTSP", "LM",
    "ATEST", "ATESTADO", "ATE",
    "LUTO", "NUPCIAS", "NÚPCIAS", "LUT", "NUP", "DN", "DNT"
]

lista_meses = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

URL_BRASAO_PADRAO = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Bras%C3%A3o_PMMG.svg/500px-Bras%C3%A3o_PMMG.svg.png"

CORES_EQUIPES = {
    "CPU": "#a16207", 
    "RP": "#1e293b", 
    "SUPERVISÃO": "#b91c1c", 
    "ADMINISTRAÇÃO": "#0f766e", 
    "TM ALPHA": "#0369a1", 
    "GEPAR": "#047857"
}

def obter_cor_equipe(eq): 
    return CORES_EQUIPES.get(str(eq).upper().strip(), "#475569")

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
            if col_num == 0: worksheet.set_column(col_num, col_num, 16)
            elif col_num == 1: worksheet.set_column(col_num, col_num, 25)
            elif col_num > 1: worksheet.set_column(col_num, col_num, 8)

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
    img_brasao = st.session_state.get("cfg_brasao_url", URL_BRASAO_PADRAO)
    
    usr_logado = st.session_state.get("usuario_dados", {})
    nome_resp_escala = f"{usr_logado.get('cargo_funcao', 'PROGRAMADOR / TESTADOR')} {usr_logado.get('nome_guerra', 'DESENVOLVEDOR')}".strip()
    
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil_str = str(usr_logado.get("perfil", "")).upper()
    eh_programador_ou_admin = "PROGRAMADOR" in cargo_str or "TESTADOR" in cargo_str or "ADMIN" in perfil_str or "DESENVOLVEDOR" in cargo_str

    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
    mils_todos = st.session_state.get("lista_militares", [])
    grade_lancamentos = st.session_state.get("grade_escala_lancamentos", {})
    escala_fechada = st.session_state.get("escala_fechada_auditoria", False)

    exp6 = st.expander("📌 PASSO 6: Visualização da Escala e Exportação Oficial", expanded=True)
    with exp6:
        with st.container(border=True):
            if escala_fechada:
                st.error("🔒 **ESCALA HOMOLOGADA (AUDITORIA ATIVADA).**")
                st.caption("A edição de dias passados está bloqueada permanentemente.")
                if eh_programador_ou_admin:
                    if st.button("🔓 Reabrir Escala Completamente (Acesso Restrito Admin)", type="secondary"):
                        st.session_state["escala_fechada_auditoria"] = False
                        st.rerun()
            else:
                st.success("🔓 **ESCALA ABERTA (MODO RASCUNHO / EDIÇÃO TOTAL).**")
                st.caption("Ao terminar o planejamento do mês, feche a escala para ativar a auditoria diária.")
                if st.button("🔒 Encerrar e Homologar Escala (Ativar Auditoria)", type="primary"):
                    st.session_state["escala_fechada_auditoria"] = True
                    st.rerun()
        
        st.divider()

        c_h1, c_h2 = st.columns(2)
        with c_h1: 
            cmt_cia = st.selectbox(
                "Comandante da Cia / Pelotão:", 
                options=[f"{m.get('posto_grad')} {m.get('nome_guerra')}" for m in mils_todos] if mils_todos else ["TEN CEL LOPES"], 
                key="p6_cmt_cia_sel"
            )
        with c_h2: 
            st.text_input("Responsável pela Escala (Militar Logado):", value=nome_resp_escala, disabled=True)
            
        obs_escala = st.text_area("📝 Observações e Diretrizes P1:", placeholder="Digite mensagens...", key="p6_obs_texto")
        st.divider()

        turnos_encontrados = set()
        for d in range(1, num_dias_mes + 1):
            for pair in chaves_quadro:
                if len(pair) == 2:
                    val = grade_lancamentos.get(f"{pair[0]}_{pair[1]}_{m_ano}_{m_mes:02d}_{d:02d}", "")
                    if val and ("às" in str(val).lower() or "as" in str(val).lower()):
                        turnos_encontrados.add(val)

        usar_legendas = st.checkbox("⚙️ Substituir horários por legendas (ex: T1, T2)", value=False, help="Substitui textos longos como '07:00 às 19:00' por siglas no PDF/Excel.")
        mapa_legendas = {}
        texto_legenda_final = ""

        if usar_legendas and turnos_encontrados:
            st.caption("Defina a sigla para cada turno encontrado na escala:")
            cols_leg = st.columns(3)
            for i, t in enumerate(sorted(turnos_encontrados)):
                with cols_leg[i % 3]:
                    mapa_legendas[t] = st.text_input(f"Legenda para: {t}", value=f"T{i+1}")
            
            leg_str_list = [f"{v} = {k}" for k, v in mapa_legendas.items()]
            texto_legenda_final = "LEGENDA DE TURNOS:   " + "   |   ".join(leg_str_list)
        
        st.divider()

        mils_linhas_quadro = []
        for pair in chaves_quadro:
            if isinstance(pair, (tuple, list)) and len(pair) == 2:
                m_obj = next((m for m in mils_todos if str(m.get("id")) == str(pair[0])), None)
                if m_obj:
                    mils_linhas_quadro.append({
                        "id": pair[0], 
                        "equipe": pair[1], 
                        "posto_grad": m_obj.get("posto_grad", "SD"), 
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
        cols_excel_names = ["EQUIPE", "MILITAR"]

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
                    <td class="td-militar">
                        <div class="m-nome">{pg} {nome_g}</div>
                        <div class="m-num">{num_pol}</div>
                    </td>
                """

                linha_xls = [eq_nome, f"{pg} {nome_g}\n{num_pol}"]
                total_horas = 0.0
                dias_neutros_cnt = 0

                for d in range(1, num_dias_mes + 1):
                    val = grade_lancamentos.get(f"{m_id}_{eq_nome}_{m_ano}_{m_mes:02d}_{d:02d}", "F")
                    val_str = str(val).upper().strip() if val else ""
                    tokens_dia = set(val_str.replace("/", " ").split())
                    
                    if any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                        dias_neutros_cnt += 1
                        
                    if val_str and val_str not in ["", "F", "D", "X"] and not any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                        total_horas += 12.0
                        
                    cell_content = ""
                    if val not in ["F", "D", "X", "", None]:
                        if usar_legendas and val in mapa_legendas:
                            val_display = mapa_legendas[val]
                            cell_content = f'<div class="shift-badge">{val_display}</div>'
                            linha_xls.append(str(val_display))
                        else:
                            val_quebrado = str(val).replace(" às ", "<br>AS<br>").replace(" AS ", "<br>AS<br>")
                            cell_content = f'<div class="shift-badge">{val_quebrado}</div>'
                            linha_xls.append(str(val))
                    elif val == "X":
                        cell_content = '<div class="shift-x">X</div>'
                        linha_xls.append("X")
                    else:
                        linha_xls.append(str(val) if val else "")
                        
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
        
        bloco_legenda_html = ""
        if texto_legenda_final:
            bloco_legenda_html = f"""
            <div style="font-size: 10px; font-weight: bold; color: #b91c1c; text-align: left; margin-top: 10px;">
                {texto_legenda_final}
            </div>
            """

        html_documento = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                    color-adjust: exact !important;
                    box-sizing: border-box;
                }}
                @media print {{
                    @page {{ size: A4 landscape; margin: 4mm; }}
                    body {{ background: #ffffff !important; padding: 0 !important; margin: 0 !important; }}
                    .card-container {{ border: none !important; box-shadow: none !important; padding: 0 !important; width: 100% !important; }}
                }}
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 8px; color: #0f172a; }}
                .card-container {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); width: 100%; }}
                .header-table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; border-bottom: 2px solid #cbd5e1; }}
                .header-table td {{ border: none !important; padding: 2px; }}
                .brasao-box {{ width: 65px; height: 65px; border: 1px solid #cbd5e1; border-radius: 6px; padding: 2px; text-align: center; }}
                .brasao-img {{ max-height: 100%; max-width: 100%; }}
                .header-titles {{ text-align: center; }}
                .header-titles h2 {{ margin: 0; font-size: 16px; font-weight: 900; color: #0f172a; text-transform: uppercase; }}
                .header-titles h3 {{ margin: 1px 0; font-size: 12px; font-weight: 700; color: #475569; text-transform: uppercase; }}
                .header-titles h4 {{ margin: 2px 0 0 0; font-size: 11px; font-weight: 800; color: #334155; text-transform: uppercase; }}
                table.escala-table {{ width: 100%; border-collapse: collapse; font-size: 9px; table-layout: auto; }}
                table.escala-table th, table.escala-table td {{ border: 1px solid #94a3b8; text-align: center; vertical-align: middle; padding: 2px 0px; }}
                th.th-eq {{ width: 5%; background: #e2e8f0; font-weight: 800; }}
                th.th-mil {{ width: 12%; background: #e2e8f0; font-weight: 800; }}
                th.th-hor {{ width: 7%; background: #e2e8f0; font-weight: 800; }}
                th.th-weekday {{ background: #e0f2fe !important; color: #0369a1 !important; }}
                th.th-weekend {{ background: #ffe4e6 !important; color: #be123c !important; }}
                .d-num {{ font-size: 10px; font-weight: 800; }}
                .d-sig {{ font-size: 7px; font-weight: 700; text-transform: uppercase; }}
                
                td.td-equipe {{ font-weight: 900 !important; font-size: 10px; text-transform: uppercase; word-wrap: break-word; }}
                td.td-militar {{ text-align: center; padding: 2px; background: #ffffff; }}
                .m-nome {{ font-weight: 800; font-size: 9px; color: #0f172a; text-transform: uppercase; }}
                .m-num {{ font-size: 7px; color: #64748b; font-weight: 700; margin-top: 1px; }}
                
                td.td-day {{ background: #ffffff; height: 34px; min-width: 20px; }}
                
                .shift-badge {{ background-color: #fef08a !important; color: #0f172a !important; font-weight: 900; font-size: 7.5px; line-height: 1.0; padding: 2px 0px; border-radius: 3px; border: 1px solid #fde047; text-transform: uppercase; display: inline-block; width: 95%; }}
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
                                <img src="{img_brasao}" class="brasao-img" onerror="this.style.display='none'">
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
                            <th class="th-mil">MILITAR</th>
                            {header_dias_html}
                            <th class="th-hor">HORAS<br><span style="font-size:6.5px; font-weight:normal;">TRAB / META</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        {tbody_html}
                    </tbody>
                </table>
                
                {bloco_legenda_html}

                <table class="signatures-table">
                    <tr>
                        <td>
                            <div class="sig-title">Responsável pela Escala</div>
                            <div class="sig-name">{nome_resp_escala}</div>
                        </td>
                        <td>
                            <div class="sig-title">Comandante da Cia</div>
                            <div class="sig-name">{cmt_cia}</div>
                        </td>
                    </tr>
                </table>
            </div>
        </body>
        </html>
        """

        components.html(html_documento, height=520, scrolling=True)
        st.divider()

        c_act1, c_act2 = st.columns(2)
        with c_act1:
            bytes_xls = gerar_excel_escala(df_excel_export, unidade, subunidade, mes_ano_str, cmt_cia, nome_resp_escala, obs_escala, texto_legenda_final)
            
            st.download_button(
                "📊 Baixar Escala em Excel (.xlsx)", 
                data=bytes_xls, 
                file_name=f"Escala_{m_mes:02d}_{m_ano}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                use_container_width=True
            )
            
        with c_act2: 
            if st.button("🖨️ Imprimir / Salvar PDF", type="primary", use_container_width=True):
                components.html(html_documento + "<script>window.print();</script>", height=600, scrolling=True)