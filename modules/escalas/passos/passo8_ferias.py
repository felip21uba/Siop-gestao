import streamlit as st
import datetime
import re
import pandas as pd
from core.database import supabase, carregar_militares_supabase

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

# ==============================================================================
# 1. HIGIENIZAÇÃO E CHAVES ÚNICAS (ANTI-DUPLICIDADE)
# ==============================================================================

def extrair_apenas_digitos(valor):
    """Extrai estritamente os dígitos da matrícula para normalização."""
    if not valor:
        return ""
    return re.sub(r'\D', '', str(valor)).lstrip("0")

def extrair_dias_inteiro(valor):
    """Converte valores de dias (ex: '010', '15 dias') para inteiro numérico."""
    try:
        val_str = str(valor).upper().replace("DIAS", "").strip()
        return int(float(val_str))
    except (ValueError, TypeError):
        return 0

def normalizar_texto(valor):
    """Normaliza strings para comparação unificada."""
    if valor is None:
        return ""
    return re.sub(r"\s+", " ", str(valor).strip()).upper()

def chave_ferias_unica(reg):
    """Gera chave estável para impedir registros repetidos de um mesmo período."""
    numero = extrair_apenas_digitos(reg.get("num_policia", ""))
    dt_i = normalizar_texto(reg.get("dt_inicio", ""))
    dt_f = normalizar_texto(reg.get("dt_fim", ""))
    return f"{numero}|{dt_i}|{dt_f}"

def deduplicar_registros_ferias(registros):
    """Remove ocorrências duplicadas mantendo apenas a primeira."""
    unicos = []
    chaves = set()
    for reg in registros or []:
        chave = chave_ferias_unica(reg)
        if not chave or chave in chaves:
            continue
        chaves.add(chave)
        unicos.append(reg)
    return unicos

# ==============================================================================
# 2. PARSING DE ARQUIVOS (SIRH TXT/CSV E PDF)
# ==============================================================================

def processar_txt_sirh(file_bytes):
    """Lê TXT/CSV do SIRH extraindo a LOTAÇÃO DETALHADA (pela posição exata da coluna)."""
    try:
        try:
            df = pd.read_csv(file_bytes, sep=';', dtype=str, encoding='latin1')
        except Exception:
            file_bytes.seek(0)
            df = pd.read_csv(file_bytes, sep=';', dtype=str, encoding='utf-8')

        lista_ferias = []

        for _, row in df.iterrows():
            # Converte as chaves das colunas da linha para maiúsculas sem espaços
            row_dict = {str(k).strip().upper(): str(v).strip() for k, v in row.items()}
            
            num_pm = row_dict.get("NUMERO", "")
            dv = row_dict.get("DV", "")
            
            if not num_pm or num_pm.upper() in ["NAN", "NONE", ""]:
                continue

            num_policia_raw = f"{num_pm}-{dv}" if dv and dv.upper() != "NAN" else num_pm
            num_policia_digitos = extrair_apenas_digitos(num_policia_raw)

            posto = row_dict.get("POSTO", "")
            nome = row_dict.get("NOME SERVIDOR", "")
            
            # 🟢 CAPTURA DA LOTAÇÃO COMPLETA / FRAÇÃO DETALHADA:
            # No arquivo SIRH, a lotação completa está na 2ª ocorrência
            # de "NOME UNIDADE", que o pandas transforma em "NOME UNIDADE.1".
            # Ex.: "1 PEL/35 CIA PM/21 BPM/4 RPM"
            lotacao_detalhada = "N/I"

            candidatos_lotacao = [
                row_dict.get("NOME UNIDADE.1", ""),
                row_dict.get("UNIDADE", ""),
            ]

            for candidato in candidatos_lotacao:
                candidato = normalizar_texto(candidato)
                if candidato and candidato not in ["NAN", "NONE", "N/I"]:
                    lotacao_detalhada = candidato
                    break

            # Fallback pela posição física da coluna, caso o SIRH altere os nomes.
            if lotacao_detalhada == "N/I" and len(row) >= 10:
                val_col9 = normalizar_texto(row.iloc[9])
                if val_col9 and val_col9 not in ["NAN", "NONE"]:
                    lotacao_detalhada = val_col9

            # Remove somente eventual código que tenha vindo junto do valor.
            if ";" in lotacao_detalhada:
                lotacao_detalhada = normalizar_texto(lotacao_detalhada.split(";")[-1])

            dt_inicio = row_dict.get("DT INICIO FERIAS", "")
            dt_fim = row_dict.get("DT TERMINO FERIAS", "")
            dias_qtd = extrair_dias_inteiro(row_dict.get("NUM DIAS", 0))

            if dt_inicio and dt_fim and num_policia_digitos:
                lista_ferias.append({
                    "num_policia": num_policia_raw,
                    "posto_grad": posto,
                    "nome_militar": f"{posto} {nome}".strip(),
                    "nome_servidor": nome,
                    "unidade": lotacao_detalhada,
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
    """Extrai férias a partir de notas, textos copiados ou PDFs."""
    lista_ferias = []
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
            lista_ferias.append({
                "num_policia": num_pol_digitos,
                "nome_militar": l_clean[:60],
                "nome_servidor": l_clean[:60],
                "unidade": "S/I",
                "dt_inicio": dt_i.strftime("%d/%m/%Y"),
                "dt_fim": dt_f.strftime("%d/%m/%Y"),
                "dias_qtd": qtd_dias,
                "ano": dt_i.year,
                "mes": dt_i.month,
                "nota_publicacao": l_clean
            })

    return deduplicar_registros_ferias(lista_ferias)

# ==============================================================================
# 3. INTERAÇÃO BANCO DE DADOS (SUPABASE)
# ==============================================================================

def salvar_ferias_supabase_lote(lista_dados):
    """Salva no Supabase garantindo que nenhum item duplicado seja inserido."""
    if not supabase or not lista_dados:
        return False, "Dados ou conexão indisponíveis."
    try:
        lista_dados = deduplicar_registros_ferias(lista_dados)

        existentes = supabase.table("plano_ferias_anual").select(
            "num_policia,dt_inicio,dt_fim"
        ).execute().data or []

        chaves_existentes = {chave_ferias_unica(r) for r in existentes}
        payload = []

        for reg in lista_dados:
            chave_reg = chave_ferias_unica(reg)
            if chave_reg in chaves_existentes:
                continue
            chaves_existentes.add(chave_reg)

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

        if not payload:
            return True, "⚠️ Todos os registros já estavam gravados no banco de dados."

        supabase.table("plano_ferias_anual").insert(payload).execute()
        st.cache_data.clear()
        return True, f"✅ {len(payload)} registro(s) salvos no banco de dados com sucesso!"
    except Exception as e:
        return False, f"Erro ao gravar no Supabase: {e}"

def limpar_todas_ferias_supabase(ano_alvo=None):
    """Limpa a tabela de férias no Supabase."""
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

def carregar_ferias_supabase(ano=None, mes=None, busca="", lotacao_sel="Todas", filtro_dias="Todos"):
    """Consulta férias com desduplicação rígida em memória por número e datas."""
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

            # Trava absoluta contra registros duplicados no retorno
            chave_unq = f"{num_p_key}|{normalizar_texto(dt_i_raw)}|{normalizar_texto(dt_f_raw)}"
            if chave_unq in processados:
                continue
            processados.add(chave_unq)

            # Formata datas
            if "-" in dt_i_raw:
                row["dt_inicio"] = datetime.datetime.strptime(dt_i_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
            if "-" in dt_f_raw:
                row["dt_fim"] = datetime.datetime.strptime(dt_f_raw, "%Y-%m-%d").strftime("%d/%m/%Y")

            cad_militar = mapa_militares.get(num_p_key, {})
            # Mantém a LOTAÇÃO/FRAÇÃO COMPLETA gravada no registro de férias.
            # O cadastro do militar só é usado como fallback.
            row["lotacao"] = normalizar_texto(
                row.get("unidade") or cad_militar.get("unidade") or "N/I"
            )

            # 🟢 FILTRO 1: LOTAÇÃO / FRAÇÃO COMPLETA
            if lotacao_sel and lotacao_sel != "Todas":
                if normalizar_texto(row.get("lotacao", "")) != normalizar_texto(lotacao_sel):
                    continue

            # 🟢 FILTRO 2: DURAÇÃO (DIAS DE FÉRIAS)
            qtd_dias_row = extrair_dias_inteiro(row.get("dias_qtd", 0))
            row["dias_qtd"] = qtd_dias_row

            if filtro_dias != "Todos":
                val_dias_esperado = extrair_dias_inteiro(filtro_dias)
                if qtd_dias_row != val_dias_esperado:
                    continue

            # 🟢 FILTRO 3: BUSCA POR MILITAR (NOME OU Nº POLÍCIA OU LOTAÇÃO)
            if busca:
                termo = busca.upper()
                num_match = termo in num_p_raw.upper() or termo in num_p_key
                nome_match = termo in str(row.get("nome_militar", "")).upper() or termo in str(row.get("nome_servidor", "")).upper()
                lot_match = termo in str(row.get("lotacao", "")).upper()
                nota_match = termo in str(row.get("nota_publicacao", "")).upper()

                if not (num_match or nome_match or lot_match or nota_match):
                    continue

            dados_filtrados.append(row)

        return deduplicar_registros_ferias(dados_filtrados)
    except Exception as e:
        print(f"Erro na consulta de férias: {e}")
        return []

# ==============================================================================
# 4. SOBRESCRIÇÃO AUTOMÁTICA NO PASSO 5 (QUADRO GERAL)
# ==============================================================================

def aplicar_sobrescricao_ferias_no_quadro(grade_escala, ano_escala, mes_escala):
    """Função utilitária invocada pelo Passo 5 para forçar a sigla FE nas férias."""
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
# 5. ESTRUTURA DA INTERFACE (PASSO 8)
# ==============================================================================

def renderizar_modulo_ferias_anual():
    st.subheader("📌 PASSO 8: Mapeamento Anual de Férias & Indisponibilidade")
    st.caption("Cadastre ou consulte o plano anual de férias. O sistema verifica estes dados e sobrescreve na escala mensal (Passo 5).")

    # --------------------------------------------------------------------------
    # BLOCO 1: PAINEL DE CONSULTA E FILTROS COMPLETO
    # --------------------------------------------------------------------------
    with st.expander("🔍 1. Consulta e Gestão de Férias Cadastradas", expanded=True):
        
        # 🟢 BUSCA TODAS AS FRAÇÕES / LOTAÇÕES GRAVADAS NO BANCO DE FÉRIAS
        opcoes_lotacao = ["Todas"]
        if supabase:
            try:
                res_unid = supabase.table("plano_ferias_anual").select("unidade").execute()
                if res_unid and res_unid.data:
                    unids_extraidas = {
                        normalizar_texto(item.get("unidade", ""))
                        for item in res_unid.data
                        if item.get("unidade")
                        and normalizar_texto(item.get("unidade", "")) not in ["NONE", "NAN", "N/I", ""]
                    }
                    opcoes_lotacao += sorted(unids_extraidas)
            except Exception:
                pass

        st.markdown("**🎯 Painel de Filtros de Busca:**")
        
        c1, c2, c3, c4 = st.columns([1.1, 1.3, 1.4, 2.2])

        with c1:
            v_ano = st.number_input("Ano:", min_value=2024, max_value=2035, value=st.session_state.get("ano_escala", datetime.date.today().year), key="p8_f_ano_v17")
        with c2:
            m_nomes = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            v_mes_nome = st.selectbox("Mês de Referência:", m_nomes, key="p8_f_mes_v17")
            v_mes_num = m_nomes.index(v_mes_nome)
        with c3:
            v_dias = st.selectbox("Duração (Dias):", ["Todos", "10 dias", "15 dias", "20 dias", "25 dias", "30 dias"], key="p8_f_dias_v17")
        with c4:
            # 🟢 SELETOR DROPDOWN COM TODAS AS FRAÇÕES DETALHADAS
            v_lotacao = st.selectbox("Lotação / Fração Completa:", opcoes_lotacao, key="p8_f_lot_v17")

        v_busca = st.text_input("🔎 Buscar Militar (Nome de Guerra, Servidor ou Nº Polícia):", placeholder="Digite o nome ou a matrícula...", key="p8_f_busca_v17").strip().upper()

        registros_banco = carregar_ferias_supabase(
            ano=v_ano,
            mes=v_mes_num,
            busca=v_busca,
            lotacao_sel=v_lotacao,
            filtro_dias=v_dias
        )

        col_limp1, col_limp2 = st.columns([3, 1.2])
        with col_limp2:
            if st.button("🗑️ Limpar Arquivos de Férias", type="secondary", use_container_width=True, key="p8_btn_limpar_v17"):
                ok_l, msg_l = limpar_todas_ferias_supabase(ano_alvo=v_ano)
                if ok_l:
                    st.success(msg_l)
                    st.rerun()
                else:
                    st.error(msg_l)

        if registros_banco:
            df_exibicao = pd.DataFrame(registros_banco)
            st.markdown(f"📊 **{len(df_exibicao)} período(s) de férias localizado(s):**")
            df_exibicao["Excluir"] = False

            cols_validos = [c for c in ["id", "num_policia", "nome_militar", "lotacao", "dt_inicio", "dt_fim", "dias_qtd", "nota_publicacao", "Excluir"] if c in df_exibicao.columns]

            df_editado = st.data_editor(
                df_exibicao[cols_validos],
                column_config={
                    "id": None,
                    "num_policia": st.column_config.TextColumn("Nº Polícia", disabled=True),
                    "nome_militar": st.column_config.TextColumn("Militar", disabled=True),
                    "lotacao": st.column_config.TextColumn("Lotação / Fração Detalhada", disabled=True),
                    "dt_inicio": st.column_config.TextColumn("Data Início (DD/MM/YYYY)"),
                    "dt_fim": st.column_config.TextColumn("Data Fim (DD/MM/YYYY)"),
                    "dias_qtd": st.column_config.NumberColumn("Dias"),
                    "nota_publicacao": st.column_config.TextColumn("Observação / Publicação"),
                    "Excluir": st.column_config.CheckboxColumn("🗑️ Remover")
                },
                hide_index=True,
                use_container_width=True,
                key="p8_editor_ferias_v17"
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
    # BLOCO 2: IMPORTAÇÃO E UPLOAD DE ARQUIVOS
    # --------------------------------------------------------------------------
    with st.expander("📥 2. Importar Arquivo de Férias (TXT do SIRH, CSV ou PDF)", expanded=False):
        u_col1, u_col2 = st.columns(2)

        with u_col1:
            st.markdown("**Upload de Ficheiro (TXT / CSV / PDF):**")
            arq_up = st.file_uploader(
                "Selecione o relatório (.txt, .csv ou .pdf):",
                type=["txt", "csv", "pdf"],
                key="p8_file_up_v17"
            )

            if arq_up is not None:
                ext = arq_up.name.lower()
                if ext.endswith((".txt", ".csv")):
                    if st.button("🚀 Processar TXT/CSV (SIRH)", type="primary", use_container_width=True, key="btn_proc_sirh_v17"):
                        st.session_state.pop("p8_temp_ferias", None)
                        regs = processar_txt_sirh(arq_up)
                        if regs:
                            st.session_state["p8_temp_ferias"] = regs
                            st.success(f"✅ {len(regs)} período(s) de férias identificados do SIRH!")
                        else:
                            st.warning("Nenhum registro no padrão SIRH foi localizado.")

                elif ext.endswith(".pdf"):
                    if st.button("🚀 Extrair do PDF", type="primary", use_container_width=True, key="btn_proc_pdf_v17"):
                        st.session_state.pop("p8_temp_ferias", None)
                        try:
                            import pypdf
                            reader = pypdf.PdfReader(arq_up)
                            txt_pdf = "".join([(p.extract_text() or "") + "\n" for p in reader.pages])
                            regs = extrair_texto_ferias(txt_pdf)
                            if regs:
                                st.session_state["p8_temp_ferias"] = regs
                                st.success(f"✅ {len(regs)} período(s) de férias localizados no PDF!")
                            else:
                                st.warning("Nenhum padrão localizado no PDF.")
                        except Exception as ex:
                            st.error(f"Erro ao ler PDF: {ex}")

        with u_col2:
            st.markdown("**Ou Cole o Texto da Publicação:**")
            txt_copiado = st.text_area("Cole a nota aqui:", placeholder="Ex: 1337468 SD SILVA - 10 DIAS A PARTIR DE 10/02/2026", height=110, key="p8_txt_area_v17")
            if st.button("⚡ Processar Texto Copiado", use_container_width=True, key="btn_proc_txt_v17"):
                st.session_state.pop("p8_temp_ferias", None)
                regs = extrair_texto_ferias(txt_copiado)
                if regs:
                    st.session_state["p8_temp_ferias"] = regs
                    st.success(f"✅ {len(regs)} período(s) identificados!")
                else:
                    st.warning("Nenhum padrão reconhecido.")

        if st.session_state.get("p8_temp_ferias"):
            st.divider()
            st.markdown("##### 🔍 Confirmação dos Registros Extraídos:")
            df_temp = pd.DataFrame(st.session_state["p8_temp_ferias"])
            st.dataframe(df_temp, use_container_width=True, hide_index=True)

            if st.button("💾 Gravar Registros no Banco de Dados", type="primary", use_container_width=True, key="btn_salvar_db_v17"):
                ok, msg = salvar_ferias_supabase_lote(st.session_state["p8_temp_ferias"])
                if ok:
                    st.session_state.pop("p8_temp_ferias", None)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)