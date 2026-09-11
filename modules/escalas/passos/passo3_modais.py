import streamlit as st
import uuid
import pandas as pd
from utils.excel_importer import carregar_planilha_universal
from core.database import salvar_militares_supabase
from utils.file_validator import validar_planilha_upload, desarmar_csv_injection

def abrir_modal_editar_efetivo_tabela(padronizar_grad_func, pesos_dict):
    @st.dialog("✏️ Editar Efetivo em Tabela (Estilo Planilha)", width="large")
    def _dialog():
        st.markdown("##### 📝 Edite graduações, nomes, matrículas e cidades diretamente na planilha:")
        st.caption("Altere os valores na tabela abaixo e clique em 'Salvar' para atualizar tudo no Supabase.")

        mils = st.session_state.get("lista_militares", [])
        if not mils:
            st.info("Nenhum militar cadastrado para editar.")
            return

        dados_tabela = []
        for m in mils:
            dados_tabela.append({
                "ID_INTERNO": m.get("id"),
                "Nº Polícia (com DV)": str(m.get("num_policia", "")),
                "Graduação": padronizar_grad_func(m.get("posto_grad", "SD")),
                "Nome Funcional": str(m.get("nome_guerra", "")),
                "Nome Completo": str(m.get("nome_completo", "")),
                "Unidade": str(m.get("unidade", "")),
                "Cidade / Fração": str(m.get("cidade", ""))
            })

        df_mils = pd.DataFrame(dados_tabela)
        opcoes_grad = ["SD AL", "SD", "CB", "3º SGT", "2º SGT", "1º SGT", "SUB TEN", "2º TEN", "1º TEN", "CAP", "MAJ", "TEN CEL", "CEL"]

        df_editado = st.data_editor(
            df_mils,
            num_rows="fixed",
            use_container_width=True,
            height=380,
            hide_index=True,
            column_config={
                "ID_INTERNO": None,
                "Nº Polícia (com DV)": st.column_config.TextColumn("Nº Polícia (com DV)", required=True),
                "Graduação": st.column_config.SelectboxColumn("Graduação", options=opcoes_grad, required=True),
                "Nome Funcional": st.column_config.TextColumn("Nome Funcional", required=True),
                "Nome Completo": st.column_config.TextColumn("Nome Completo"),
                "Unidade": st.column_config.TextColumn("Unidade"),
                "Cidade / Fração": st.column_config.TextColumn("Cidade / Fração")
            }
        )

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("💾 Salvar Alterações no SIOP & Supabase", type="primary", use_container_width=True):
                novos_mils = []
                mapa_existente = {str(m.get("id")): m for m in mils}

                for _, row in df_editado.iterrows():
                    m_id = str(row["ID_INTERNO"])
                    pg_f = padronizar_grad_func(row["Graduação"])
                    num_p = str(row["Nº Polícia (com DV)"]).strip()
                    nome_g = str(row["Nome Funcional"]).strip().upper()
                    nome_c = str(row["Nome Completo"]).strip().upper()
                    uni_val = str(row["Unidade"]).strip().upper()
                    cid_val = str(row["Cidade / Fração"]).strip().upper()

                    obj_m = mapa_existente.get(m_id, {"id": m_id})
                    obj_m["num_policia"] = num_p
                    obj_m["posto_grad"] = pg_f
                    obj_m["nome_guerra"] = nome_g
                    obj_m["nome_completo"] = nome_c if nome_c else f"{pg_f} {nome_g}"
                    obj_m["unidade"] = uni_val if uni_val else "UNIDADE N/I"
                    obj_m["cidade"] = cid_val if cid_val else "N/I"
                    obj_m["peso"] = pesos_dict.get(pg_f, 99)

                    novos_mils.append(obj_m)

                salvar_militares_supabase(novos_mils)
                st.session_state["lista_militares"] = novos_mils
                st.session_state["militares_carregados"] = True
                st.success("✅ Efetivo e cidades salvos no Supabase com sucesso!")
                st.rerun()

        with col_s2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.rerun()

    _dialog()

def abrir_modal_excluir_lote(excluir_lote_func):
    @st.dialog("🚨 Confirmar Exclusão dos Militares Selecionados")
    def _dialog():
        sel_ids = set(str(i) for i in st.session_state.get("militares_selecionados_ids", []))
        mils_todos = st.session_state.get("lista_militares", [])
        mils_para_excluir = [m for m in mils_todos if str(m["id"]) in sel_ids]
        
        if not mils_para_excluir:
            st.warning("⚠️ Nenhum militar está presente no Quadro da Direita para ser excluído.")
            if st.button("Entendido", use_container_width=True):
                st.rerun()
            return

        st.error(f"⚠️ Você está prestes a excluir definitivamente **{len(mils_para_excluir)} militar(es)** do Quadro da Direita.")
        
        df_exc = pd.DataFrame([
            {
                "Grad/Nome": f"{m.get('posto_grad')} {m.get('nome_guerra')}", 
                "Nº Polícia (com DV)": m.get('num_policia'), 
                "Unidade": m.get('unidade'),
                "Cidade": m.get('cidade')
            } 
            for m in mils_para_excluir
        ])
        st.dataframe(df_exc, use_container_width=True, hide_index=True, height=180)
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            if st.button("🚨 Confirmar Exclusão Definitiva", type="primary", use_container_width=True):
                with st.spinner("Excluindo do banco de dados e limpando memória..."):
                    excluir_lote_func(mils_para_excluir)
                st.success(f"✅ {len(mils_para_excluir)} militar(es) excluído(s) com sucesso!")
                st.rerun()
        with col_d2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.rerun()

    _dialog()

def abrir_modal_upload_planilha(funcs_extracao):
    @st.dialog("📥 Importar Efetivo via Planilha", width="large")
    def _dialog():
        padronizar_grad = funcs_extracao["padronizar_graduacao"]
        tratar_num = funcs_extracao["tratar_num_policia"]
        extrair_pg = funcs_extracao["extrair_posto_grad"]
        extrair_cid = funcs_extracao["extrair_cidade"]
        extrair_uni = funcs_extracao["extrair_unidade"]
        remover_dup = funcs_extracao["remover_duplicados"]
        pesos_dict = funcs_extracao["pesos"]

        st.markdown("##### 📁 Selecione o arquivo Excel ou CSV contendo a relação dos militares:")
        arquivo_planilha = st.file_uploader("Selecione o arquivo XLSX/CSV:", type=["xls", "xlsx", "csv"], key="uploader_efetivo_modal")
        
        if arquivo_planilha is not None:
            # Validação de Segurança do Arquivo
            is_valido, msg_val = validar_planilha_upload(arquivo_planilha)
            if not is_valido:
                st.error(msg_val)
            else:
                if st.button("📥 Processar e Conferir Dados", type="primary", use_container_width=True):
                    try:
                        df_imp = carregar_planilha_universal(arquivo_planilha)
                        # Neutraliza potenciais formulas injeções maliciosas
                        df_imp = desarmar_csv_injection(df_imp)
                        df_imp.columns = [str(c).strip().upper() for c in df_imp.columns]

                        lista_temp = []
                        for idx_row, row in df_imp.iterrows():
                            mat_unificada = tratar_num(row)
                            if not mat_unificada or mat_unificada.upper() == "NAN":
                                continue

                            posto_raw = extrair_pg(row)
                            pg_sigla = padronizar_grad(posto_raw)
                            
                            nome_serv = str(row.get("NOME SERVIDOR", row.get("NOME_COMPLETO", row.get("NOME", "MILITAR")))).strip().upper()
                            parts_nome = nome_serv.split()
                            n_guerra_ext = parts_nome[-1] if len(parts_nome) > 1 else nome_serv
                            
                            cidade_val = extrair_cid(row)
                            unidade_val = extrair_uni(row)

                            lista_temp.append({
                                "id": f"mili_{idx_row}_{uuid.uuid4().hex[:6]}",
                                "num_policia": mat_unificada,
                                "posto_grad": pg_sigla,
                                "nome_guerra": n_guerra_ext,
                                "nome_completo": nome_serv,
                                "cidade": cidade_val,
                                "peso": pesos_dict.get(pg_sigla, 99),
                                "unidade": unidade_val
                            })
                        
                        st.session_state["temp_importacao_lista"] = remover_dup(lista_temp)
                    except Exception as ex:
                        st.error(f"Erro ao processar planilha: {ex}")

        if st.session_state.get("temp_importacao_lista"):
            st.divider()
            lista_temp = st.session_state.get("temp_importacao_lista", [])
            
            numeros_existentes = {str(m.get("num_policia", "")).strip().upper() for m in st.session_state.get("lista_militares", [])}
            novos_cnt = sum(1 for item in lista_temp if str(item.get("num_policia", "")).strip().upper() not in numeros_existentes)
            existentes_cnt = len(lista_temp) - novos_cnt
            
            st.markdown(f"📊 **Resumo da Importação ({len(lista_temp)} militares identificados):**")
            st.info(f"• 👥 **{novos_cnt} novos militares** serão inseridos.\n• 🔄 **{existentes_cnt} militares existentes** terão suas graduações e cidades atualizadas no Supabase.")

            df_temp = pd.DataFrame(lista_temp)[["num_policia", "posto_grad", "nome_completo", "nome_guerra", "unidade", "cidade"]]
            df_temp.columns = ["Nº Polícia (com DV)", "Graduação", "Nome Completo", "Nome Funcional", "Unidade", "Cidade / Município"]
            
            df_editado = st.data_editor(
                df_temp, num_rows="fixed", use_container_width=True, height=250,
                column_config={
                    "Nº Polícia (com DV)": st.column_config.TextColumn(disabled=True), 
                    "Graduação": st.column_config.TextColumn(disabled=False),
                    "Cidade / Município": st.column_config.TextColumn(disabled=False)
                }
            )
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                if st.button("✅ Confirmar e Atualizar Efetivo no SIOP & Supabase", type="primary", use_container_width=True):
                    mils_memoria = st.session_state.get("lista_militares", [])
                    mapa_memoria = {str(m.get("num_policia", "")).strip().upper(): m for m in mils_memoria}
                    
                    todos_salvar_banco = []
                    
                    for idx_r, row_e in df_editado.iterrows():
                        num_pol_e = str(row_e["Nº Polícia (com DV)"]).strip()
                        num_pol_key = num_pol_e.upper()
                        pg_e = padronizar_grad(row_e["Graduação"])
                        nome_f_e = str(row_e["Nome Funcional"]).strip().upper()
                        nome_c_e = str(row_e["Nome Completo"]).strip().upper()
                        cidade_e = str(row_e["Cidade / Município"]).strip().upper()
                        unidade_e = str(row_e["Unidade"]).strip().upper()
                        peso_e = pesos_dict.get(pg_e, 99)

                        if num_pol_key in mapa_memoria:
                            m_exist = mapa_memoria[num_pol_key]
                            m_exist["posto_grad"] = pg_e
                            m_exist["nome_guerra"] = nome_f_e
                            m_exist["nome_completo"] = nome_c_e
                            m_exist["cidade"] = cidade_e if cidade_e else "N/I"
                            m_exist["unidade"] = unidade_e if unidade_e else "UNIDADE N/I"
                            m_exist["peso"] = peso_e
                            todos_salvar_banco.append(m_exist)
                        else:
                            m_id_novo = f"mili_{idx_r}_{uuid.uuid4().hex[:6]}"
                            novo_obj = {
                                "id": m_id_novo,
                                "num_policia": num_pol_e,
                                "posto_grad": pg_e,
                                "nome_guerra": nome_f_e,
                                "nome_completo": nome_c_e,
                                "cidade": cidade_e if cidade_e else "N/I",
                                "peso": peso_e,
                                "unidade": unidade_e if unidade_e else "UNIDADE N/I"
                            }
                            mils_memoria.append(novo_obj)
                            todos_salvar_banco.append(novo_obj)

                    if todos_salvar_banco:
                        salvar_militares_supabase(todos_salvar_banco)

                    st.session_state["lista_militares"] = remover_dup(mils_memoria)
                    st.session_state["temp_importacao_lista"] = []
                    st.session_state["militares_carregados"] = True
                    st.success("✅ Efetivo e cidades atualizados no Supabase com sucesso!")
                    st.rerun()

            with col_m2:
                if st.button("❌ Cancelar Importação", use_container_width=True):
                    st.session_state["temp_importacao_lista"] = []
                    st.rerun()

    _dialog()

def abrir_modal_novo_militar(padronizar_graduacao_func, remover_dup_func, pesos_dict):
    @st.dialog("➕ Cadastrar Novo Militar", width="medium")
    def _dialog():
        with st.form("form_novo_militar_modal", clear_on_submit=True):
            num_policia_in = st.text_input("Nº Polícia / Matrícula com DV:", placeholder="Ex: 1337468").strip().replace("-", "").replace(".", "")
            posto_in = st.selectbox("Graduação:", ["SD AL", "SD", "CB", "3º SGT", "2º SGT", "1º SGT", "SUB TEN", "2º TEN", "1º TEN", "CAP", "MAJ", "TEN CEL"])
            nome_guerra_in = st.text_input("Nome de Guerra / Funcional:", placeholder="Ex: SILVA")
            nome_completo_in = st.text_input("Nome Completo:", placeholder="Ex: SILVA JUNIOR")
            unidade_in = st.text_input("Unidade (Ex: 35 CIA PM):", placeholder="Ex: 35 CIA PM").strip().upper()
            cidade_in = st.text_input("Cidade / Fração:", placeholder="Ex: UBÁ, VISCONDE DO RIO BRANCO...").strip().upper()
            
            st.markdown("<br>", unsafe_allow_html=True)
            btn_cad_mil = st.form_submit_button("💾 Salvar Militar", type="primary", use_container_width=True)
            
            if btn_cad_mil and num_policia_in and nome_guerra_in:
                num_limpo = str(num_policia_in).strip()
                ja_existe = any(str(m.get("num_policia", "")).strip() == num_limpo for m in st.session_state.get("lista_militares", []))
                
                if ja_existe:
                    st.error("⚠️ Este Número de Polícia já está cadastrado no sistema!")
                else:
                    m_id_novo = f"mili_{uuid.uuid4().hex[:6]}"
                    nome_f_upper = str(nome_guerra_in).strip().upper()
                    pg_abrev = padronizar_graduacao_func(posto_in)
                    nome_comp_final = str(nome_completo_in).strip().upper() if nome_completo_in else f"{pg_abrev} {nome_f_upper}"
                    cidade_final = cidade_in if cidade_in else "N/I"
                    unidade_final = unidade_in if unidade_in else st.session_state.get("cfg_subunidade", "UNIDADE N/I")
                    
                    novo_m = {
                        "id": m_id_novo,
                        "num_policia": num_limpo,
                        "posto_grad": pg_abrev,
                        "nome_guerra": nome_f_upper,
                        "nome_completo": nome_comp_final,
                        "cidade": cidade_final,
                        "peso": pesos_dict.get(pg_abrev, 99),
                        "unidade": unidade_final
                    }
                    
                    st.session_state["lista_militares"].append(novo_m)
                    st.session_state["lista_militares"] = remover_dup_func(st.session_state["lista_militares"])
                    st.session_state["militares_carregados"] = True
                    salvar_militares_supabase([novo_m])
                    st.success(f"✅ Militar {nome_f_upper} cadastrado e salvo no Supabase!")
                    st.rerun()

    _dialog()