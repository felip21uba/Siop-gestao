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
from modules.escalas.passos.passo5_quadro import verificar_trava_sobreposicao, executar_auto_save_banco

SIGLAS_DIAS_NEUTROS = [
    "FER", "FERIAS", "FÉRIAS", "FE",
    "LTSP", "LM",
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
    "GEPAR": "#047857"
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
    """Extrai estritamente os dígitos do Nº de Polícia tratando floats do Excel (ex: '1337468.0' -> '1337468')."""
    val_str = str(valor).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    return re.sub(r'\D', '', val_str).lstrip('0')

def calcular_duracao_turno_texto(val_str):
    """Calcula a carga horária em horas a partir do texto do turno/legenda."""
    v = str(val_str).upper().strip()
    if not v or v in ["F", "D", "X", "NAN", "NONE"] or any(sigla in v for sigla in SIGLAS_DIAS_NEUTROS):
        return 0.0
    if "24" in v or "24X72" in v:
        return 24.0
    if "18" in v:
        return 18.0
    if "8" in v or "08" in v or "EXPEDIENTE" in v:
        return 8.0
    # Padrão para plantões de turno (12h) quando for sigla (ex: 1, 2, 3, T1, T2) ou horário
    return 12.0

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
            elif col_num == 1: worksheet.set_column(col_num, col_num, 15)  # Coluna Nº POLÍCIA
            elif col_num == 2: worksheet.set_column(col_num, col_num, 25)  # Coluna MILITAR
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

    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil_str = str(usr_logado.get("perfil", "")).upper()
    eh_programador_ou_admin = "PROGRAMADOR" in cargo_str or "TESTADOR" in cargo_str or "ADMIN" in perfil_str or "DESENVOLVEDOR" in cargo_str

    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
    grade_lancamentos = st.session_state.get("grade_escala_lancamentos", {})
    escala_fechada = st.session_state.get("escala_fechada_auditoria", False)

    with st.expander("📌 PASSO 6: Visualização da Escala e Exportação Oficial", expanded=True):
        
        with st.expander("➕ ⚙️ Configurações de Emissão, Assinaturas e Importação Externa", expanded=False):
            c_cfg1, c_cfg2 = st.columns([2, 2], gap="large")
            
            with c_cfg1:
                st.markdown("##### 🔒 Status de Homologação da Escala")
                if escala_fechada:
                    st.error("🔒 **ESCALA HOMOLOGADA (AUDITORIA ATIVADA)**")
                    st.caption("A edição de dias passados está bloqueada permanentemente.")
                    if eh_programador_ou_admin:
                        if st.button("🔓 Reabrir Escala (Acesso Restrito)", type="secondary", use_container_width=True):
                            st.session_state["escala_fechada_auditoria"] = False
                            st.rerun()
                else:
                    st.success("🔓 **ESCALA ABERTA (MODO RASCUNHO)**")
                    st.caption("Ao terminar o planejamento do mês, feche a escala para ativar a auditoria diária.")
                    
                    if st.button("🔒 Encerrar e Homologar Escala", type="primary", use_container_width=True):
                        st.session_state["limpar_avisos_manual"] = False
                        verificar_trava_sobreposicao()
                        
                        bloqueios_p6 = st.session_state.get("lista_bloqueios_auditoria", [])
                        avisos_descanso_p6 = st.session_state.get("lista_avisos_descanso", [])
                        
                        if bloqueios_p6 or avisos_descanso_p6:
                            st.error("🚨 **A homologação foi interrompida devido a pendências de auditoria na escala!**")
                        else:
                            st.session_state["escala_fechada_auditoria"] = True
                            st.success("✅ Escala homologada e encerrada com sucesso!")
                            st.rerun()

                # 🟢 LEITOR DE EXCEL CAPTURANDO D, F, X E PLANTÕES
                st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
                st.markdown("##### 📥 Importar Escala Externa em Excel")
                st.caption("Importa a escala mantendo os dias de folga (D, F), licenças e plantões.")
                
                arq_excel_escala = st.file_uploader(
                    "Selecione o arquivo Excel da Escala:", 
                    type=["xlsx", "xls"], 
                    key="p6_uploader_excel_escala"
                )

                if arq_excel_escala is not None:
                    if st.button("🚀 Processar e Carregar no Quadro (Passo 5)", type="primary", use_container_width=True):
                        try:
                            df_raw = pd.read_excel(arq_excel_escala, header=None)
                            
                            header_idx = None
                            for idx_r, r_vals in df_raw.iterrows():
                                line_str = [str(v).strip().upper() for v in r_vals.values if pd.notna(v)]
                                if any(k in line_str for k in ["EQUIPE", "MILITAR", "Nº POLÍCIA", "POLICIA"]):
                                    header_idx = idx_r
                                    break

                            if header_idx is None:
                                header_idx = 4

                            df_imp = pd.read_excel(arq_excel_escala, header=header_idx)
                            df_imp.columns = [str(c).strip().upper() for c in df_imp.columns]

                            grade_nova = copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {}))
                            chaves_novas = list(st.session_state.get("militares_no_quadro_chaves", []))
                            mils_cad = st.session_state.get("lista_militares", []) or carregar_militares_supabase() or []
                            
                            mapa_mils_digitos = {}
                            for m in mils_cad:
                                num_p_dig = extrair_matricula_limpa(m.get("num_policia", ""))
                                if num_p_dig:
                                    mapa_mils_digitos[num_p_dig] = m

                            col_equipe = next((c for c in df_imp.columns if "EQUIPE" in c), None)
                            col_matricula = next((c for c in df_imp.columns if any(k in c for k in ["POLICIA", "POLÍCIA", "NUMERO", "NÚMERO", "MATRICULA", "MATRÍCULA", "NUM_POLICIA", "PM"])), None)
                            col_militar = next((c for c in df_imp.columns if any(k in c for k in ["MILITAR", "NOME", "NOME_GUERRA", "SERVIDOR"])), None)

                            linhas_importadas = 0
                            militar_nao_encontrado_lista = []

                            for idx_row, row in df_imp.iterrows():
                                eq_imp = str(row.get(col_equipe, "ADMINISTRAÇÃO")).strip().upper() if col_equipe else "ADMINISTRAÇÃO"
                                val_militar_txt = str(row.get(col_militar, "")).strip().upper() if col_militar else ""
                                val_mat_txt = str(row.get(col_matricula, "")).strip() if col_matricula else ""

                                texto_comb = f"{eq_imp} {val_militar_txt} {val_mat_txt}".upper()
                                if any(k in texto_comb for k in ["RESPONSÁVEL", "RESPONSAVEL", "COMANDANTE DA CIA"]):
                                    break

                                if not val_militar_txt and not val_mat_txt:
                                    continue

                                m_obj_encontrado = None
                                digitos_mat = extrair_matricula_limpa(val_mat_txt)
                                if not digitos_mat and val_militar_txt:
                                    digitos_mat = extrair_matricula_limpa(val_militar_txt)

                                if digitos_mat and digitos_mat in mapa_mils_digitos:
                                    m_obj_encontrado = mapa_mils_digitos[digitos_mat]

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
                                                if val_celula.endswith(".0"):
                                                    val_celula = val_celula[:-2]
                                                # Garante gravação mesmo para D, F, X ou Horários
                                                grade_nova[f"{m_id}_{eq_imp}_{m_ano}_{m_mes:02d}_{d:02d}"] = val_celula.upper()
                                            else:
                                                grade_nova[f"{m_id}_{eq_imp}_{m_ano}_{m_mes:02d}_{d:02d}"] = "F"
                                    
                                    linhas_importadas += 1
                                else:
                                    militar_nao_encontrado_lista.append(f"{val_militar_txt} (Nº {val_mat_txt})")

                            if linhas_importadas > 0:
                                st.session_state["militares_no_quadro_chaves"] = chaves_novas
                                st.session_state["grade_escala_lancamentos"] = grade_nova
                                
                                executar_auto_save_banco()
                                st.success(f"✅ {linhas_importadas} militar(es) cruzado(s) e importados com sucesso!")
                                st.rerun()
                            else:
                                st.error("❌ Nenhuma matrícula da planilha bateu com os militares cadastrados no sistema (Passo 3).")
                        except Exception as ex_imp:
                            st.error(f"Erro ao processar arquivo Excel: {ex_imp}")

            with c_cfg2:
                st.markdown("##### ✍️ Assinaturas & Observações")
                cmt_cia = st.selectbox(
                    "Comandante da Cia / Pelotão:", 
                    options=[f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')}" for m in mils_todos] if mils_todos else ["TEN CEL LOPES"], 
                    key="p6_cmt_cia_sel"
                )
                st.text_input("Responsável pela Escala:", value=nome_resp_escala, disabled=True)
                obs_escala = st.text_area("📝 Observações e Diretrizes P1:", placeholder="Digite instruções ou notas de rodapé...", height=80, key="p6_obs_texto")

        with st.expander("➕ 📄 Visualização Oficial do Quadro & Exportação PDF / Excel", expanded=True):
            
            turnos_encontrados = set()
            for d in range(1, num_dias_mes + 1):
                for pair in chaves_quadro:
                    if len(pair) == 2:
                        val = grade_lancamentos.get(f"{pair[0]}_{pair[1]}_{m_ano}_{m_mes:02d}_{d:02d}", "")
                        val_s = str(val).strip().upper()
                        if val_s and val_s not in ["F", "D", "X", "FE", "LM", "ATE", "NONE", "NAN", ""]:
                            turnos_encontrados.add(str(val).strip())

            st.markdown("##### ⚙️ Mapeamento e Conversão de Horários / Legendas")
            
            modo_conversao = st.radio(
                "Escolha o modo de exibição no Quadro/PDF/Excel:",
                ["Exibir exatamente como lançado no Quadro", 
                 "Substituir Horários Extensos por Legendas (ex: 07:00 às 19:00 ➔ T1)", 
                 "Substituir Legendas Importadas por Horários (ex: T1 ➔ 07:00 às 19:00)"],
                key="p6_modo_conversao_legendas"
            )

            mapa_legendas = {}
            texto_legenda_final = ""

            if modo_conversao == "Substituir Horários Extensos por Legendas (ex: 07:00 às 19:00 ➔ T1)" and turnos_encontrados:
                st.caption("Defina qual sigla/legenda irá substituir cada horário longo:")
                cols_leg = st.columns(3)
                for i, t in enumerate(sorted(turnos_encontrados)):
                    with cols_leg[i % 3]:
                        mapa_legendas[t] = st.text_input(f"Sigla para [{t}]:", value=f"T{i+1}", key=f"leg_input_hor_{i}")
                
                leg_str_list = [f"{v} = {k}" for k, v in mapa_legendas.items()]
                texto_legenda_final = "LEGENDA DE TURNOS:   " + "   |   ".join(leg_str_list)

            elif modo_conversao == "Substituir Legendas Importadas por Horários (ex: T1 ➔ 07:00 às 19:00)" and turnos_encontrados:
                st.caption("Informe qual horário real corresponde a cada sigla/legenda encontrada na planilha:")
                cols_leg = st.columns(3)
                for i, t in enumerate(sorted(turnos_encontrados)):
                    with cols_leg[i % 3]:
                        mapa_legendas[t] = st.text_input(f"Horário para Sigla [{t}]:", value="07:00 às 19:00", key=f"leg_input_sig_{i}")

                # 🔄 BOTAO DE APLICAR CONVERSAO NO QUADRO DO PASSO 5
                if mapa_legendas and st.button("🔄 Aplicar Horários Convertidos no Passo 5 (Recalcular Carga Horária)", type="primary"):
                    grade_atualizada = copy.deepcopy(grade_lancamentos)
                    for k_g, v_g in grade_atualizada.items():
                        v_str = str(v_g).strip()
                        if v_str in mapa_legendas:
                            grade_atualizada[k_g] = mapa_legendas[v_str]
                    
                    st.session_state["grade_escala_lancamentos"] = grade_atualizada
                    executar_auto_save_banco()
                    st.success("✅ Horários e carga horária atualizados no Passo 5 com sucesso!")
                    st.rerun()

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

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
                        
                        # 🟢 CALCULA HORAS TRABALHADAS REAL CONSIDERANDO PLANTÃO OU SIGLA
                        val_efetivo = mapa_legendas.get(val_raw, val_raw) if mapa_legendas else val_raw
                        total_horas += calcular_duracao_turno_texto(val_efetivo)

                        tokens_dia = set(val_str.replace("/", " ").split())
                        if any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                            dias_neutros_cnt += 1

                        cell_content = ""
                        if val_raw not in ["F", "D", "X", "", None]:
                            val_quebrado = str(val_efetivo).replace(" às ", "<br>AS<br>").replace(" AS ", "<br>AS<br>").replace(" ÀS ", "<br>AS<br>")
                            cell_content = f'<div class="shift-badge">{val_quebrado}</div>'
                            linha_xls.append(str(val_efetivo))
                        elif val_raw in ["D", "F"]:
                            cell_content = f'<div style="font-weight: bold; color: #64748b;">{val_raw}</div>'
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
                    
                    {bloco_legenda_html}

                    <table class="signatures-table">
                        <tr>
                            <td>
                                <div class="sig-title">Responsável pela Escala</div>
                                <div class="sig-name">{nome_resp_escala}</div>
                            </td>
                            <td>
                                <div class="sig-title">Comandante da Cia</div>
                                <div class="sig-name">{cmt_cia if 'cmt_cia' in locals() else 'COMANDANTE'}</div>
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
                bytes_xls = gerar_excel_escala(df_excel_export, unidade, subunidade, mes_ano_str, cmt_cia if 'cmt_cia' in locals() else 'COMANDANTE', nome_resp_escala, obs_escala if 'obs_escala' in locals() else '', texto_legenda_final)
                
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