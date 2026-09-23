import streamlit as st
import datetime
import re
import pandas as pd
from core.database import supabase, carregar_militares_supabase

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

# ==============================================================================
# 1. FUNÇÕES DE TRATAMENTO E HIGIENIZAÇÃO DE DADOS
# ==============================================================================

def extrair_apenas_digitos(valor):
    """Extrai estritamente os dígitos da matrícula para garantir casamento único."""
    if not valor:
        return ""
    return re.sub(r'\D', '', str(valor)).lstrip("0")

def extrair_dias_inteiro(valor):
    """Converte valores de dias (ex: '10', '15 dias') para inteiro numérico."""
    try:
        val_str = str(valor).upper().replace("DIAS", "").strip()
        return int(float(val_str))
    except (ValueError, TypeError):
        return 0

# ==============================================================================
# 2. PARSING E IMPORTAÇÃO (COM DESDUPLICAÇÃO NA ORIGEM)
# ==============================================================================

def normalizar_texto(valor):
    """Normaliza texto para comparação, removendo espaços e diferenças de caixa."""
    if valor is None:
        return ""
    return re.sub(r"\\s+", " ", str(valor).strip()).upper()

def chave_ferias_unica(reg):
    """Gera uma chave estável para impedir o mesmo lançamento de férias mais de uma vez."""
    numero = extrair_apenas_digitos(reg.get("num_policia", ""))
    nome = normalizar_texto(reg.get("nome_servidor", reg.get("nome_militar", "")))
    dt_i = normalizar_texto(reg.get("dt_inicio", ""))
    dt_f = normalizar_texto(reg.get("dt_fim", ""))
    return f"{numero}|{nome}|{dt_i}|{dt_f}"

def deduplicar_registros_ferias(registros):
    """Remove duplicidades exatas mantendo somente a primeira ocorrência."""
    unicos = []
    chaves = set()
    for reg in registros or []:
        chave = chave_ferias_unica(reg)
        if not chave or chave in chaves:
            continue
        chaves.add(chave)
        unicos.append(reg)
    return unicos

def dias_ferias_no_mes(reg, ano, mes):
    """Calcula quantos dias do período de férias caem dentro do mês consultado."""
    try:
        dt_i_raw = str(reg.get("dt_inicio", ""))
        dt_f_raw = str(reg.get("dt_fim", ""))
        formatos = ("%d/%m/%Y", "%Y-%m-%d")
        dt_i = dt_f = None
        for fmt in formatos:
            try:
                dt_i = datetime.datetime.strptime(dt_i_raw, fmt).date()
                break
            except Exception:
                pass
        for fmt in formatos:
            try:
                dt_f = datetime.datetime.strptime(dt_f_raw, fmt).date()
                break
            except Exception:
                pass
        if not dt_i or not dt_f:
            return 0

        primeiro = datetime.date(int(ano), int(mes), 1)
        ultimo = datetime.date(
            int(ano), int(mes),
            __import__("calendar").monthrange(int(ano), int(mes))[1]
        )
        inicio = max(dt_i, primeiro)
        fim = min(dt_f, ultimo)
        return max(0, (fim - inicio).days + 1)
    except Exception:
        return 0

def processar_txt_sirh(file_bytes):
    """Lê TXT/CSV do SIRH, eliminando linhas duplicadas do mesmo militar/período."""
    try:
        try:
            df = pd.read_csv(file_bytes, sep=';', dtype=str, encoding='latin1')
        except Exception:
            file_bytes.seek(0)
            df = pd.read_csv(file_bytes, sep=';', dtype=str, encoding='utf-8')

        df.columns = [str(c).strip().upper() for c in df.columns]
        lista_ferias = []
        chaves_unicas = set()

        for _, row in df.iterrows():
            num_pm = str(row.get("NUMERO", "")).strip()
            dv = str(row.get("DV", "")).strip()
            
            if not num_pm or num_pm.upper() in ["NAN", "NONE", ""]:
                continue

            num_policia_raw = f"{num_pm}{dv}" if dv and dv.upper() != "NAN" else num_pm
            num_policia_digitos = extrair_apenas_digitos(num_policia_raw)

            posto = str(row.get("POSTO", "")).strip()
            nome = str(row.get("NOME SERVIDOR", "")).strip()
            
            unidade = str(
                row.get("NOME UNIDADE", row.get("UNIDADE", row.get("UNID PRINCIPAL", "N/I")))
            ).strip().upper()
            
            dt_inicio = str(row.get("DT INICIO FERIAS", "")).strip()
            dt_fim = str(row.get("DT TERMINO FERIAS", "")).strip()
            dias_qtd = extrair_dias_inteiro(row.get("NUM DIAS", 0))

            if dt_inicio and dt_fim and num_policia_digitos:
                # TRAVA RÍGIDA ANTI-DUPLICIDADE
                chave_item = f"{num_policia_digitos}_{dt_inicio}_{dt_fim}"
                if chave_item in chaves_unicas:
                    continue
                chaves_unicas.add(chave_item)

                lista_ferias.append({
                    "num_policia": num_policia_digitos,
                    "posto_grad": posto,
                    "nome_militar": f"{posto} {nome}".strip(),
                    "nome_servidor": nome,
                    "unidade": unidade,
                    "dt_inicio": dt_inicio,
                    "dt_fim": dt_fim,
                    "dias_qtd": dias_qtd,
                    "nota_publicacao": f"Férias SIRH ({dt_inicio} a {dt_fim})"
                })

        return deduplicar_registros_ferias(lista_ferias)
    except Exception as e:
        st.error(f"Erro ao processar arquivo TXT do SIRH: {e}")
        return []

def extrair_texto_ferias(texto_bruto):
    """Extrai férias a partir de texto copiado ou documentos PDF."""
    lista_ferias = []
    chaves_unicas = set()
    linhas = str(texto_bruto).split("\n")

    for linha in linhas:
        l_clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', str(linha).strip()).upper()
        if not l_clean:
            continue

        m_num = re.search(r'\b\d{6,7}\b', l_clean)
        num_pol_digitos = extrair_apenas_digitos(m_num.group(0)) if m_num else ""

        m_intervalo = re.search(r'(\d{2}/\d{2}/\d{4})\s*(?:A|À|-|ATE)\s*(\d{2}/\d{2}/\d{4})', l_clean)
        m_dias = re.search(r'(\d+)\s*DIAS?\s*(?:A\s*PARTIR\s*DE|A\s*CONTAR\s*DE)\s*(\d{2}/\d{2}/\d{4})', l_clean)

        dt_i, dt_f = None, None
        qtd_dias = 0

        if m_intervalo:
            try:
                dt_i = datetime.datetime.strptime(m_intervalo.group(1), "%d/%m/%Y").date()
                dt_f = datetime.datetime.strptime(m_intervalo.group(2), "%d/%m/%Y").date()
                qtd_dias = (dt_f - dt_i).days + 1
            except ValueError:
                pass
        elif m_dias:
            try:
                qtd_dias = int(m_dias.group(1))
                dt_i = datetime.datetime.strptime(m_dias.group(2), "%d/%m/%Y").date()
                dt_f = dt_i + datetime.timedelta(days=qtd_dias - 1)
            except ValueError:
                pass

        if dt_i and dt_f and num_pol_digitos:
            chave_item = f"{num_pol_digitos}_{dt_i}_{dt_f}"
            if chave_item in chaves_unicas:
                continue
            chaves_unicas.add(chave_item)

            lista_ferias.append({
                "num_policia": num_pol_digitos,
                "nome_militar": l_clean[:60],
                "nome_servidor": l_clean[:60],
                "dt_inicio": dt_i.strftime("%d/%m/%Y"),
                "dt_fim": dt_f.strftime("%d/%m/%Y"),
                "dias_qtd": qtd_dias,
                "ano": dt_i.year,
                "mes": dt_i.month,
                "nota_publicacao": l_clean
            })
    return deduplicar_registros_ferias(lista_ferias)

# ==============================================================================
# 3. INTERAÇÃO COM BANCO DE DADOS (SUPABASE)
# ==============================================================================

def salvar_ferias_supabase_lote(lista_dados):
    """Insere o lote no Supabase sem repetir o mesmo militar/período."""
    if not supabase or not lista_dados:
        return False, "Dados ou conexão indisponíveis."
    try:
        lista_dados = deduplicar_registros_ferias(lista_dados)

        # Também evita inserir novamente registros que já estão no banco.
        existentes = supabase.table("plano_ferias_anual").select(
            "num_policia,nome_servidor,nome_militar,dt_inicio,dt_fim"
        ).execute().data or []

        chaves_existentes = {chave_ferias_unica(r) for r in existentes}
        payload = []
        chaves_lote = set()

        for reg in lista_dados:
            if chave_ferias_unica(reg) in chaves_existentes:
                continue
            if chave_ferias_unica(reg) in chaves_lote:
                continue
            chaves_lote.add(chave_ferias_unica(reg))
            item = reg.copy()
            try:
                dt_i_obj = datetime.datetime.strptime(reg["dt_inicio"], "%d/%m/%Y")
                dt_f_obj = datetime.datetime.strptime(reg["dt_fim"], "%d/%m/%Y")
                item["dt_inicio"] = dt_i_obj.strftime("%Y-%m-%d")
                item["dt_fim"] = dt_f_obj.strftime("%Y-%m-%d")
                item["ano"] = dt_i_obj.year
                item["mes"] = dt_i_obj.month
            except Exception:
                item["ano"] = datetime.date.today().year
                item["mes"] = datetime.date.today().month

            payload.append(item)

        supabase.table("plano_ferias_anual").insert(payload).execute()
        st.cache_data.clear()
        return True, f"✅ {len(payload)} registro(s) salvos no banco com sucesso!"
    except Exception as e:
        return False, f"Erro ao gravar no Supabase: {e}"

def limpar_todas_ferias_supabase(ano_alvo=None):
    """Remove os registros de férias do ano selecionado ou todos."""
    if not supabase:
        return False, "Supabase indisponível."
    try:
        query = supabase.table("plano_ferias_anual").delete()
        if ano_alvo:
            query = query.eq("ano", ano_alvo)
        else:
            query = query.neq("id", 0)
        query.execute()
        st.cache_data.clear()
        return True, "🗑️ Registros de férias limpos com sucesso!"
    except Exception as e:
        return False, f"Erro ao apagar banco: {e}"

def carregar_ferias_supabase(ano=None, mes=None, busca="", lotacao_sel="Todas", cidade_sel="Todas", filtro_dias="Todos"):
    """Consulta as férias agrupando estritamente por militar/período para eliminar nomes repetidos."""
    if not supabase:
        return []
    try:
        query = supabase.table("plano_ferias_anual").select("*")
        if ano:
            query = query.eq("ano", ano)
        if mes and mes != 0:
            query = query.eq("mes", mes)

        res = query.order("dt_inicio").execute()
        dados_brutos = res.data or []

        mils_banco = carregar_militares_supabase() or []
        mapa_militares = {}
        for m in mils_banco:
            if isinstance(m, dict) and m.get("num_policia"):
                key_digitos = extrair_apenas_digitos(m["num_policia"])
                if key_digitos and key_digitos not in mapa_militares:
                    mapa_militares[key_digitos] = m

        dados_filtrados = []
        processados = set()

        for row in dados_brutos:
            if not isinstance(row, dict):
                continue

            num_p_raw = str(row.get("num_policia", "")).strip()
            num_p_key = extrair_apenas_digitos(num_p_raw)
            dt_i_raw = str(row.get("dt_inicio", ""))
            dt_f_raw = str(row.get("dt_fim", ""))

            # 🛑 GARANTE REGISTRO ÚNICO POR MILITAR + NOME + PERÍODO
            chave_unq = (
                num_p_key,
                normalizar_texto(row.get("nome_servidor", row.get("nome_militar", ""))),
                normalizar_texto(dt_i_raw),
                normalizar_texto(dt_f_raw),
            )
            if chave_unq in processados:
                continue
            processados.add(chave_unq)

            # Formata datas para visualização
            if "-" in dt_i_raw:
                row["dt_inicio"] = datetime.datetime.strptime(dt_i_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
            if "-" in dt_f_raw:
                row["dt_fim"] = datetime.datetime.strptime(dt_f_raw, "%Y-%m-%d").strftime("%d/%m/%Y")

            cad_militar = mapa_militares.get(num_p_key, {})
            row["lotacao"] = str(row.get("unidade") or cad_militar.get("unidade") or "N/I").strip().upper()
            row["cidade"] = str(cad_militar.get("cidade") or "N/I").strip().upper()

            # FILTRO 1: LOTAÇÃO E CIDADE
            if lotacao_sel != "Todas" and lotacao_sel.lower() not in row["lotacao"].lower():
                continue
            if cidade_sel != "Todas" and cidade_sel.lower() not in row["cidade"].lower():
                continue

            # FILTRO 2: DURAÇÃO EM DIAS DE FÉRIAS (10, 15, 20, 25, 30)
            qtd_dias_row = extrair_dias_inteiro(row.get("dias_qtd", 0))
            row["dias_qtd"] = qtd_dias_row

            if filtro_dias != "Todos":
                val_dias_esperado = extrair_dias_inteiro(filtro_dias)
                if qtd_dias_row != val_dias_esperado:
                    continue

            # FILTRO 3: BUSCA TEXTUAL
            if busca:
                termo = busca.upper()
                if not (
                    termo in num_p_raw.upper() or
                    termo in str(row.get("nome_militar", "")).upper() or
                    termo in str(row.get("nota_publicacao", "")).upper()
                ):
                    continue

            row["dias_no_mes_consulta"] = dias_ferias_no_mes(row, ano or row.get("ano"), mes or row.get("mes"))
            dados_filtrados.append(row)

        return deduplicar_registros_ferias(dados_filtrados)
    except Exception as e:
        print(f"Erro na consulta de férias: {e}")
        return []

# ==============================================================================
# 4. SOBRESCRIÇÃO AUTOMÁTICA NO PASSO 5 (QUADRO GERAL)
# ==============================================================================

def aplicar_sobrescricao_ferias_no_quadro(grade_escala, ano_escala, mes_escala):
    """Lê o banco e força a sigla 'FE' nas datas de férias dos militares no Passo 5."""
    ferias_mes = carregar_ferias_supabase(ano=ano_escala, mes=mes_escala)
    if not ferias_mes:
        return grade_escala

    for reg in ferias_mes:
        num_pol_digitos = extrair_apenas_digitos(reg.get("num_policia", ""))
        try:
            dt_i = datetime.datetime.strptime(reg["dt_inicio"], "%d/%m/%Y").date()
            dt_f = datetime.datetime.strptime(reg["dt_fim"], "%d/%m/%Y").date()
        except Exception:
            continue

        dt_cursor = dt_i
        while dt_cursor <= dt_f:
            if dt_cursor.year == ano_escala and dt_cursor.month == mes_escala:
                dia = dt_cursor.day
                for key in list(grade_escala.keys()):
                    m_id_chave = extrair_apenas_digitos(key.split("_")[0])
                    if m_id_chave and m_id_chave == num_pol_digitos and key.endswith(f"{ano_escala}_{mes_escala:02d}_{dia:02d}"):
                        grade_escala[key] = "FE"
            dt_cursor += datetime.timedelta(days=1)

    return grade_escala

# ==============================================================================
# 5. ESTRUTURA PRINCIPAL DA INTERFACE (PASSO 8)
# ==============================================================================

def renderizar_modulo_ferias_anual():
    st.subheader("📌 PASSO 8: Mapeamento Anual de Férias & Indisponibilidade")
    st.caption("Cadastre ou consulte o plano anual de férias. O sistema verifica estes dados e sobrescreve na escala mensal (Passo 5).")

    # --------------------------------------------------------------------------
    # BLOCO 1: CONSULTA, FILTROS E AJUSTES RÁPIDOS
    # --------------------------------------------------------------------------
    with st.expander("🔍 1. Consulta, Filtros e Gestão de Férias Cadastradas", expanded=True):
        mils = carregar_militares_supabase() or []
        unidades_set = set([
            str(m.get("unidade", "")).strip().upper() 
            for m in mils 
            if isinstance(m, dict) and m.get("unidade") and str(m.get("unidade")).strip().upper() not in ["NONE", "NAN", "N/I", ""]
        ])
        opcoes_lotacao = ["Todas"] + sorted(list(unidades_set))
        
        cidades_set = set([
            str(m.get("cidade", "")).strip().upper() 
            for m in mils 
            if isinstance(m, dict) and m.get("cidade") and str(m.get("cidade")).strip().upper() not in ["NONE", "NAN", "N/I", ""]
        ])
        opcoes_cidade = ["Todas"] + sorted(list(cidades_set))

        st.markdown("**🎯 Painel de Filtros de Busca:**")
        f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([1.1, 1.4, 1.4, 1.8, 2.2])

        with f_col1:
            v_ano = st.number_input("Ano da Escala:", min_value=2024, max_value=2035, value=st.session_state.get("ano_escala", datetime.date.today().year), key="p8_f_ano_v12")
        with f_col2:
            m_nomes = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            v_mes_nome = st.selectbox("Mês de Referência:", m_nomes, key="p8_f_mes_v12")
            v_mes_num = m_nomes.index(v_mes_nome)
        with f_col3:
            v_dias = st.selectbox("Duração (Dias):", ["Todos", "10 dias", "15 dias", "20 dias", "25 dias", "30 dias"], key="p8_f_dias_v12")
        with f_col4:
            v_lotacao = st.selectbox("Lotação / Fração:", opcoes_lotacao, key="p8_f_lot_v12")

        with f_col5:
            v_busca = st.text_input(
                "🔎 Buscar Militar:",
                placeholder="Nome ou Nº Polícia...",
                key="p8_f_busca_v12"
            ).strip().upper()

        c_f5, c_f6 = st.columns([2.5, 2.5])
        with c_f5:
            v_cidade = st.selectbox("Cidade / Fração:", opcoes_cidade, key="p8_f_cid_v12")
        with c_f6:
            v_dias_mes = st.number_input(
                "Dias lançados no mês:",
                min_value=0,
                max_value=31,
                value=0,
                step=1,
                help="0 = todos. Quando informado, mostra somente militares com essa quantidade de dias de férias no mês selecionado.",
                key="p8_f_dias_mes_v12"
            )

        # Executa a consulta no Supabase com desduplicação
        registros_banco = carregar_ferias_supabase(
            ano=v_ano,
            mes=v_mes_num,
            busca=v_busca,
            lotacao_sel=v_lotacao,
            cidade_sel=v_cidade,
            filtro_dias=v_dias
        )

        # Filtro por quantidade TOTAL de dias lançados no mês.
        if v_dias_mes > 0 and registros_banco:
            registros_banco = [
                r for r in registros_banco
                if dias_ferias_no_mes(r, v_ano, v_mes_num) == v_dias_mes
            ]

        col_acc1, col_acc2 = st.columns([3, 1.2])
        with col_acc2:
            if st.button("🗑️ Limpar Arquivos de Férias", type="secondary", use_container_width=True, key="p8_btn_limpar_v12"):
                ok_l, msg_l = limpar_todas_ferias_supabase(ano_alvo=v_ano)
                if ok_l:
                    st.success(msg_l)
                    st.rerun()
                else:
                    st.error(msg_l)

        # Exibição do Editor de Dados sem duplicados
        if registros_banco:
            df_exibicao = pd.DataFrame(registros_banco)

            # Resumo por militar: mostra quantos dias de férias estão lançados no mês.
            if v_mes_num:
                resumo = (
                    df_exibicao.groupby(
                        ["num_policia", "nome_militar"], dropna=False
                    )["dias_no_mes_consulta"]
                    .sum()
                    .reset_index()
                    .rename(columns={
                        "num_policia": "Nº Polícia",
                        "nome_militar": "Militar",
                        "dias_no_mes_consulta": "Dias lançados no mês"
                    })
                )
                st.markdown("### 📊 Resumo de dias de férias por militar")
                st.dataframe(resumo, use_container_width=True, hide_index=True)

            st.markdown(f"📋 **{len(df_exibicao)} registro(s) de período localizado(s):**")
            df_exibicao["Excluir"] = False

            cols_validos = [c for c in ["id", "num_policia", "nome_militar", "lotacao", "cidade", "dt_inicio", "dt_fim", "dias_qtd", "dias_no_mes_consulta", "nota_publicacao", "Excluir"] if c in df_exibicao.columns]

            df_editado = st.data_editor(
                df_exibicao[cols_validos],
                column_config={
                    "id": None,
                    "num_policia": st.column_config.TextColumn("Nº Polícia", disabled=True),
                    "nome_militar": st.column_config.TextColumn("Militar", disabled=True),
                    "lotacao": st.column_config.TextColumn("Lotação", disabled=True),
                    "cidade": st.column_config.TextColumn("Cidade", disabled=True),
                    "dt_inicio": st.column_config.TextColumn("Data Início (DD/MM/YYYY)"),
                    "dt_fim": st.column_config.TextColumn("Data Fim (DD/MM/YYYY)"),
                    "dias_qtd": st.column_config.NumberColumn("Dias"),
                    "dias_no_mes_consulta": st.column_config.NumberColumn("Dias no mês", disabled=True),
                    "nota_publicacao": st.column_config.TextColumn("Observação"),
                    "Excluir": st.column_config.CheckboxColumn("🗑️ Remover")
                },
                hide_index=True,
                use_container_width=True,
                key="p8_editor_ferias_v12"
            )

            if any(df_editado["Excluir"]):
                ids_del = df_editado[df_editado["Excluir"]]["id"].tolist()
                if supabase and ids_del:
                    supabase.table("plano_ferias_anual").delete().in_("id", ids_del).execute()
                    st.cache_data.clear()
                    st.success("Registro(s) removido(s) com sucesso!")
                    st.rerun()
        else:
            st.info("Nenhuma férias localizada com os filtros selecionados.")

    # --------------------------------------------------------------------------
    # BLOCO 2: UPLOAD E CARGA DE ARQUIVO (TXT SIRH OU PDF/TEXTO)
    # --------------------------------------------------------------------------
    with st.expander("📥 2. Importar Arquivo de Férias (TXT do SIRH, CSV ou PDF)", expanded=False):
        u_col1, u_col2 = st.columns(2)

        with u_col1:
            st.markdown("**Upload de Ficheiro (TXT / CSV / PDF):**")
            arq_up = st.file_uploader(
                "Selecione o relatório (.txt, .csv ou .pdf):",
                type=["txt", "csv", "pdf"],
                key="p8_file_up_v12"
            )

            if arq_up is not None:
                ext = arq_up.name.lower()
                if ext.endswith((".txt", ".csv")):
                    if st.button("🚀 Processar TXT/CSV (SIRH)", type="primary", use_container_width=True, key="btn_proc_sirh_v12"):
                        st.session_state.pop("p8_temp_ferias", None)
                        regs = deduplicar_registros_ferias(processar_txt_sirh(arq_up))
                        if regs:
                            st.session_state["p8_temp_ferias"] = regs
                            st.success(f"✅ {len(regs)} registro(s) identificados do SIRH!")
                        else:
                            st.warning("Nenhum registro no padrão SIRH foi localizado.")

                elif ext.endswith(".pdf"):
                    if st.button("🚀 Extrair do PDF", type="primary", use_container_width=True, key="btn_proc_pdf_v12"):
                        st.session_state.pop("p8_temp_ferias", None)
                        try:
                            import pypdf
                            reader = pypdf.PdfReader(arq_up)
                            txt_pdf = "".join([(p.extract_text() or "") + "\n" for p in reader.pages])
                            regs = deduplicar_registros_ferias(extrair_texto_ferias(txt_pdf))
                            if regs:
                                st.session_state["p8_temp_ferias"] = regs
                                st.success(f"✅ {len(regs)} registro(s) localizados no PDF!")
                            else:
                                st.warning("Nenhum padrão localizado no PDF.")
                        except Exception as ex:
                            st.error(f"Erro ao ler PDF: {ex}")

        with u_col2:
            st.markdown("**Ou Cole o Texto da Publicação:**")
            txt_copiado = st.text_area("Cole a nota aqui:", placeholder="Ex: 1337468 SD SILVA - 10 DIAS A PARTIR DE 10/02/2026", height=110, key="p8_txt_area_v12")
            if st.button("⚡ Processar Texto Copiado", use_container_width=True, key="btn_proc_txt_v12"):
                st.session_state.pop("p8_temp_ferias", None)
                regs = deduplicar_registros_ferias(extrair_texto_ferias(txt_copiado))
                if regs:
                    st.session_state["p8_temp_ferias"] = regs
                    st.success(f"✅ {len(regs)} registro(s) identificados!")
                else:
                    st.warning("Nenhum padrão reconhecido.")

        # Pré-visualização da Carga de Férias
        if st.session_state.get("p8_temp_ferias"):
            st.divider()
            st.markdown("##### 🔍 Confirmação dos Registros Extraídos:")
            df_temp = pd.DataFrame(st.session_state["p8_temp_ferias"])
            st.dataframe(df_temp, use_container_width=True, hide_index=True)

            if st.button("💾 Gravar Registros no Banco de Dados", type="primary", use_container_width=True, key="btn_salvar_db_v12"):
                ok, msg = salvar_ferias_supabase_lote(st.session_state["p8_temp_ferias"])
                if ok:
                    st.session_state.pop("p8_temp_ferias", None)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)