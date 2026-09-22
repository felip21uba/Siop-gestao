import streamlit as st
import datetime
import re
import pandas as pd
from core.database import supabase, carregar_militares_supabase

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # Limite de 10MB

def processar_txt_ferias_pmmg(file_bytes):
    """Lê o arquivo TXT/CSV oficial do SIRH/PMMG separado por ponto e vírgula extraindo lotação/fração detalhada."""
    try:
        try:
            df = pd.read_csv(file_bytes, sep=';', dtype=str, encoding='latin1')
        except Exception:
            file_bytes.seek(0)
            df = pd.read_csv(file_bytes, sep=';', dtype=str, encoding='utf-8')

        df.columns = [str(c).strip().upper() for c in df.columns]

        ferias_mapeadas = []
        for _, row in df.iterrows():
            num_pm = str(row.get("NUMERO", "")).strip()
            dv = str(row.get("DV", "")).strip()
            
            if not num_pm or num_pm.upper() in ["NAN", "NONE", ""]:
                continue

            num_policia_completo = f"{num_pm}-{dv}" if dv and dv.upper() != "NAN" else num_pm
            posto = str(row.get("POSTO", "")).strip()
            nome = str(row.get("NOME SERVIDOR", "")).strip()
            
            # Captura a Fração/Lotação Detalhada (ex: 2 GP/3 PEL/35 CIA PM/21 BPM/4 RPM)
            lotacao_detalhada = str(
                row.get("NOME UNIDADE", row.get("UNIDADE", row.get("UNID PRINCIPAL", "N/I")))
            ).strip().upper()
            
            dt_inicio = str(row.get("DT INICIO FERIAS", "")).strip()
            dt_fim = str(row.get("DT TERMINO FERIAS", "")).strip()
            num_dias = str(row.get("NUM DIAS", "")).strip()

            if dt_inicio and dt_fim:
                try:
                    num_dias_int = int(num_dias)
                except ValueError:
                    num_dias_int = 0

                ferias_mapeadas.append({
                    "num_policia": num_policia_completo,
                    "posto_grad": posto,
                    "nome_militar": f"{posto} {nome}".strip(),
                    "nome_servidor": nome,
                    "unidade": lotacao_detalhada,
                    "dt_inicio": dt_inicio,
                    "dt_fim": dt_fim,
                    "dias_qtd": num_dias_int,
                    "nota_publicacao": f"Férias SIRH ({dt_inicio} a {dt_fim})"
                })

        return ferias_mapeadas
    except Exception as e:
        st.error(f"Erro ao processar arquivo TXT de Férias: {e}")
        return []

def extrair_registros_ferias_texto(texto_bruto):
    """Extrai férias a partir de padrões textuais de PDFs e colagens de texto."""
    registros = []
    linhas = texto_bruto.split("\n")

    for linha in linhas:
        s = str(linha).strip()
        if s.startswith(('=', '+', '-', '@')): 
            s = "'" + s
        linha_clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s).upper()
        if not linha_clean: 
            continue

        m_num = re.search(r'\b\d{6,7}\b', linha_clean)
        num_pol = m_num.group(0) if m_num else ""

        m_intervalo = re.search(r'(\d{2}/\d{2}/\d{4})\s*(?:A|À|-|ATE)\s*(\d{2}/\d{2}/\d{4})', linha_clean)
        m_dias_partir = re.search(r'(\d+)\s*DIAS?\s*(?:A\s*PARTIR\s*DE|A\s*CONTAR\s*DE)\s*(\d{2}/\d{2}/\d{4})', linha_clean)

        dt_i, dt_f = None, None

        if m_intervalo:
            try:
                dt_i = datetime.datetime.strptime(m_intervalo.group(1), "%d/%m/%Y").date()
                dt_f = datetime.datetime.strptime(m_intervalo.group(2), "%d/%m/%Y").date()
            except ValueError: 
                pass
        elif m_dias_partir:
            try:
                qtd_dias = int(m_dias_partir.group(1))
                dt_i = datetime.datetime.strptime(m_dias_partir.group(2), "%d/%m/%Y").date()
                dt_f = dt_i + datetime.timedelta(days=qtd_dias - 1)
            except ValueError: 
                pass

        if dt_i and dt_f:
            qtd_dias_calculada = (dt_f - dt_i).days + 1
            registros.append({
                "num_policia": num_pol,
                "nome_militar": linha_clean[:60],
                "nome_servidor": linha_clean[:60],
                "dt_inicio": dt_i.strftime("%d/%m/%Y"),
                "dt_fim": dt_f.strftime("%d/%m/%Y"),
                "dias_qtd": qtd_dias_calculada,
                "ano": dt_i.year,
                "mes": dt_i.month,
                "nota_publicacao": linha_clean
            })
    return registros

def salvar_ferias_supabase_lote(lista_registros):
    """Grava o lote de férias extraído na tabela plano_ferias_anual do Supabase."""
    if supabase and lista_registros:
        try:
            registros_db = []
            for r in lista_registros:
                item = r.copy()
                try:
                    dt_i = datetime.datetime.strptime(r["dt_inicio"], "%d/%m/%Y").strftime("%Y-%m-%d")
                    dt_f = datetime.datetime.strptime(r["dt_fim"], "%d/%m/%Y").strftime("%Y-%m-%d")
                    dt_obj = datetime.datetime.strptime(r["dt_inicio"], "%d/%m/%Y")
                    item["ano"] = dt_obj.year
                    item["mes"] = dt_obj.month
                except Exception:
                    dt_i = r["dt_inicio"]
                    dt_f = r["dt_fim"]
                    item["ano"] = datetime.date.today().year
                    item["mes"] = datetime.date.today().month

                item["dt_inicio"] = dt_i
                item["dt_fim"] = dt_f
                registros_db.append(item)
                
            supabase.table("plano_ferias_anual").insert(registros_db).execute()
            return True, "✅ Registros salvos com sucesso no Supabase!"
        except Exception as ex:
            return False, f"Erro ao salvar no banco: {ex}"
    return False, "Banco Supabase indisponível."

def carregar_ferias_supabase(ano=None, mes=None, busca="", lotacao_sel="Todas", cidade_sel="Todas", filtro_dias="Todos"):
    """Consulta as férias no Supabase filtrando por Fração/Lotação, Cidade e Duração das Férias."""
    if not supabase: 
        return []
    try:
        query = supabase.table("plano_ferias_anual").select("*")
        if ano: 
            query = query.eq("ano", ano)
        if mes and mes != 0: 
            query = query.eq("mes", mes)
        res = query.order("dt_inicio").execute()
        
        dados = res.data or []
        
        mils_banco = carregar_militares_supabase() or []
        mapa_mils = {
            str(m.get("num_policia", "")).strip().upper(): m 
            for m in mils_banco if m.get("num_policia")
        }

        dados_completos = []
        for d in dados:
            if d.get("dt_inicio") and "-" in str(d["dt_inicio"]):
                d["dt_inicio"] = datetime.datetime.strptime(str(d["dt_inicio"]), "%Y-%m-%d").strftime("%d/%m/%Y")
            if d.get("dt_fim") and "-" in str(d["dt_fim"]):
                d["dt_fim"] = datetime.datetime.strptime(str(d["dt_fim"]), "%Y-%m-%d").strftime("%d/%m/%Y")

            num_p = str(d.get("num_policia", "")).strip().upper()
            m_cadastro = mapa_mils.get(num_p, {})
            
            d["lotacao"] = str(m_cadastro.get("unidade") or d.get("unidade") or "N/I").strip().upper()
            d["cidade"] = str(m_cadastro.get("cidade") or "N/I").strip().upper()

            # Filtro por Fração / Lotação Detalhada
            if lotacao_sel != "Todas" and lotacao_sel not in d["lotacao"]:
                continue
            
            # Filtro por Cidade
            if cidade_sel != "Todas" and cidade_sel not in d["cidade"]:
                continue
            
            # Filtro por Duração de Férias (10, 15 ou 20+ dias)
            if filtro_dias != "Todos":
                qtd_d = int(d.get("dias_qtd") or 0)
                if filtro_dias == "10 dias" and qtd_d != 10:
                    continue
                elif filtro_dias == "15 dias" and qtd_d != 15:
                    continue
                elif filtro_dias == "20+ dias" and qtd_d < 20:
                    continue

            # Filtro por Busca Textual
            if busca:
                termo_b = busca.upper()
                if not (
                    termo_b in num_p or 
                    termo_b in str(d.get("nota_publicacao", "")).upper() or 
                    termo_b in str(d.get("nome_militar", "")).upper() or 
                    termo_b in str(d.get("nome_servidor", "")).upper()
                ):
                    continue

            dados_completos.append(d)

        return dados_completos
    except Exception: 
        return []

def renderizar_modulo_ferias_anual():
    """Renderiza a interface do Passo 8 com seletores de Lotação Detalhada, Cidade e Duração das Férias."""
    with st.expander("📌 PASSO 8: Mapeamento Anual de Férias & Indisponibilidade", expanded=True):
        st.caption("Cadastre ou consulte o plano anual de férias. O sistema verifica estes dados para alertar e injetar na escala mensal.")

        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)

        with st.expander("➕ 📥 Importar Arquivo de Férias (TXT do SIRH, CSV ou PDF)", expanded=False):
            c_up1, c_up2 = st.columns(2)
            
            with c_up1:
                st.markdown("**Upload de Ficheiro (TXT / CSV / PDF):**")
                arq_upload = st.file_uploader(
                    "Selecione o arquivo do SIRH (.txt), planilha (.csv) ou publicação (.pdf):", 
                    type=["txt", "csv", "pdf"], 
                    key="uploader_ferias_anual_unificado_p8_v5"
                )
                
                if arq_upload is not None:
                    nome_ext = arq_upload.name.lower()
                    
                    if nome_ext.endswith(".txt") or nome_ext.endswith(".csv"):
                        if st.button("🚀 Processar Arquivo TXT/CSV (SIRH)", type="primary", use_container_width=True):
                            regs = processar_txt_ferias_pmmg(arq_upload)
                            if regs:
                                st.session_state["temp_ferias_extraidas"] = regs
                                st.success(f"✅ {len(regs)} registro(s) de férias identificados do SIRH!")
                            else:
                                st.warning("Nenhum registro no padrão SIRH foi encontrado no arquivo.")

                    elif nome_ext.endswith(".pdf"):
                        if st.button("🚀 Extrair Férias do PDF", type="primary", use_container_width=True):
                            try:
                                import pypdf
                                reader = pypdf.PdfReader(arq_upload)
                                texto_extraido = "".join([(page.extract_text() or "") + "\n" for page in reader.pages])
                                regs = extrair_registros_ferias_texto(texto_extraido)
                                if regs:
                                    st.session_state["temp_ferias_extraidas"] = regs
                                    st.success(f"✅ {len(regs)} registro(s) identificados no PDF!")
                                else:
                                    st.warning("Nenhum padrão de férias localizado no PDF.")
                            except Exception as ex:
                                st.error(f"Erro ao processar PDF: {ex}")

            with c_up2:
                st.markdown("**Ou Cole o Texto da Nota / Publicação:**")
                txt_area = st.text_area(
                    "Cole o texto da publicação aqui:", 
                    placeholder="Ex: 1234567 SD SILVA - 10 DIAS A PARTIR DE 02/02/2027", 
                    height=120
                )
                if st.button("⚡ Processar Texto Copiado", use_container_width=True):
                    regs = extrair_registros_ferias_texto(txt_area)
                    if regs:
                        st.session_state["temp_ferias_extraidas"] = regs
                        st.success(f"✅ {len(regs)} registro(s) identificados no texto!")
                    else:
                        st.warning("Nenhum padrão reconhecido no texto.")

            if st.session_state.get("temp_ferias_extraidas"):
                st.divider()
                st.markdown("##### 🔍 Confirme os registros antes de gravar no Supabase:")
                df_temp = pd.DataFrame(st.session_state["temp_ferias_extraidas"])
                st.dataframe(df_temp, use_container_width=True, hide_index=True)
                
                if st.button("💾 Gravar Férias no Banco de Dados", type="primary", use_container_width=True):
                    ok, msg = salvar_ferias_supabase_lote(st.session_state["temp_ferias_extraidas"])
                    if ok:
                        st.session_state.pop("temp_ferias_extraidas", None)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        # SUB-EXPANDER DE CONSULTA E GESTÃO COM PAINEL DE FILTROS ORGANIZADO EM 2 LINHAS
        with st.expander("➕ 🔍 Consulta e Gestão do Mapeamento Anual de Férias", expanded=True):
            mils_cadastrados = carregar_militares_supabase() or []
            
            # Puxa todas as opções dinâmicas de Fração/Lotação e Cidades do cadastro de militares
            opcoes_lotacao = ["Todas"] + sorted(list(set([
                str(m.get("unidade", "")).strip().upper() 
                for m in mils_cadastrados 
                if m.get("unidade") and str(m.get("unidade")).strip().upper() not in ["NONE", "NAN", "N/I", ""]
            ])))
            
            opcoes_cidade = ["Todas"] + sorted(list(set([
                str(m.get("cidade", "")).strip().upper() 
                for m in mils_cadastrados 
                if m.get("cidade") and str(m.get("cidade")).strip().upper() not in ["NONE", "NAN", "N/I", ""]
            ])))

            st.markdown("##### 🎯 Painel de Filtros do Mapeamento de Férias:")

            # LINHA 1: PERÍODO E DURAÇÃO
            c_f1, c_f2, c_f3 = st.columns([1.5, 2, 2])
            with c_f1:
                ano_sel = st.number_input("Ano da Escala:", min_value=2024, max_value=2035, value=st.session_state.get("ano_escala", datetime.date.today().year))
            with c_f2:
                meses_nomes = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
                mes_filtro_nome = st.selectbox("Mês de Referência:", meses_nomes)
                mes_num = meses_nomes.index(mes_filtro_nome)
            with c_f3:
                filtro_dias = st.selectbox("Duração das Férias:", ["Todos", "10 dias", "15 dias", "20+ dias"])

            # LINHA 2: FRAÇÃO / LOTAÇÃO DETALHADA E BUSCA
            c_f4, c_f5, c_f6 = st.columns([2.5, 2, 2.5])
            with c_f4:
                lotacao_sel = st.selectbox("Lotação / Fração Detalhada:", opcoes_lotacao)
            with c_f5:
                cidade_sel = st.selectbox("Cidade / Fração:", opcoes_cidade)
            with c_f6:
                busca_militar = st.text_input("Buscar Militar / Nº Polícia:", placeholder="Digite número ou nome...").strip().upper()

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

            registros_banco = carregar_ferias_supabase(
                ano=ano_sel, 
                mes=mes_num, 
                busca=busca_militar, 
                lotacao_sel=lotacao_sel, 
                cidade_sel=cidade_sel,
                filtro_dias=filtro_dias
            )

            if registros_banco:
                df_p = pd.DataFrame(registros_banco)
                st.markdown(f"📊 **{len(df_p)} registro(s) localizado(s):**")
                df_p["Excluir"] = False
                
                cols_exibir = [c for c in ["id", "num_policia", "nome_militar", "lotacao", "cidade", "dt_inicio", "dt_fim", "dias_qtd", "nota_publicacao", "Excluir"] if c in df_p.columns]
                
                df_edit = st.data_editor(
                    df_p[cols_exibir],
                    column_config={
                        "id": None,
                        "num_policia": "Nº Polícia",
                        "nome_militar": "Nome Militar",
                        "lotacao": "Lotação / Fração Detalhada",
                        "cidade": "Cidade / Fração",
                        "dt_inicio": "Data Início",
                        "dt_fim": "Data Fim",
                        "dias_qtd": "Dias",
                        "nota_publicacao": "Nota / Publicação",
                        "Excluir": st.column_config.CheckboxColumn("🗑️ Remover")
                    },
                    hide_index=True, use_container_width=True, key="editor_plano_anual_ferias"
                )

                if any(df_edit["Excluir"]):
                    ids_deletar = df_edit[df_edit["Excluir"]]["id"].tolist()
                    if supabase and ids_deletar:
                        for id_del in ids_deletar:
                            supabase.table("plano_ferias_anual").delete().eq("id", id_del).execute()
                        st.success("Registro(s) removido(s) com sucesso!")
                        st.rerun()
            else:
                st.info("Nenhuma férias cadastrada no banco para o período e filtros selecionados.")