import streamlit as st
import uuid
import pandas as pd
from utils.excel_importer import carregar_planilha_universal
from core.database import salvar_militares_supabase
from utils.file_validator import validar_planilha_upload, desarmar_csv_injection

OPCOES_PERFIL = ["TROPA", "ESCALANTE", "CMT_CIA", "ADMIN"]

def abrir_modal_editar_efetivo_tabela(padronizar_grad_func, pesos_dict):
    @st.dialog("✏️ Editar Efetivo e Permissões em Tabela", width="large")
    def _dialog():
        st.markdown("##### 📝 Edite graduações, nomes, matrículas, unidades e perfis de acesso:")
        st.caption("Altere os valores na tabela abaixo e clique em 'Salvar' para atualizar tudo no Supabase.")

        mils = st.session_state.get("lista_militares", [])
        if not mils:
            st.info("Nenhum militar cadastrado para editar.")
            return

        dados_tabela = []
        for m in mils:
            dados_tabela.append({
                "ID_INTERNO": str(m.get("id")),
                "Nº Polícia (com DV)": str(m.get("num_policia", "")),
                "Graduação": padronizar_grad_func(m.get("posto_grad", "SD")),
                "Nome Funcional": str(m.get("nome_guerra", "")),
                "Nome Completo": str(m.get("nome_completo", "")),
                "Unidade": str(m.get("unidade", "UNIDADE N/I")),
                "Cidade / Fração": str(m.get("cidade", "N/I")),
                "Perfil de Acesso": str(m.get("perfil", "TROPA")).upper()
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
                "Cidade / Fração": st.column_config.TextColumn("Cidade / Fração"),
                "Perfil de Acesso": st.column_config.SelectboxColumn("Perfil de Acesso", options=OPCOES_PERFIL, required=True)
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
                    perfil_val = str(row["Perfil de Acesso"]).strip().upper()

                    obj_m = mapa_existente.get(m_id, {"id": m_id})
                    obj_m["num_policia"] = num_p
                    obj_m["posto_grad"] = pg_f
                    obj_m["nome_guerra"] = nome_g
                    obj_m["nome_completo"] = nome_c if nome_c else f"{pg_f} {nome_g}"
                    obj_m["unidade"] = uni_val if uni_val else "UNIDADE N/I"
                    obj_m["cidade"] = cid_val if cid_val else "N/I"
                    obj_m["perfil"] = perfil_val
                    obj_m["peso"] = pesos_dict.get(pg_f, 99)

                    novos_mils.append(obj_m)

                salvar_militares_supabase(novos_mils)
                st.session_state["lista_militares"] = novos_mils
                st.session_state["militares_carregados"] = True
                st.success("✅ Efetivo, unidades e perfis de acesso salvos no Supabase com sucesso!")
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
                "Unidade": m.get('unidade', 'UNIDADE N/I'),
                "Cidade": m.get('cidade', 'N/I'),
                "Perfil": m.get('perfil', 'TROPA')
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

        arquivo_planilha = st.file_uploader("Selecione o arquivo XLSX ou CSV:", type=["xls", "xlsx", "csv"], key="uploader_efetivo_modal")
        
        if arquivo_planilha is not None:
            is_valido, msg_val = validar_planilha_upload(arquivo_planilha)
            if not is_valido:
                st.error(msg_val)
            else:
                if st.button("📥 Processar e Conferir Dados", type="primary", use_container_width=True):
                    try:
                        df_imp = carregar_planilha_universal(arquivo_planilha)
                        if df_imp is None or df_imp.empty:
                            st.error("🚨 Não foi possível extrair dados da planilha enviada.")
                            return

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

                            lista_temp.append({
                                "id": f"mili_{idx_row}_{uuid.uuid4().hex[:6]}",
                                "num_policia": mat_unificada,
                                "posto_grad": pg_sigla,
                                "nome_guerra": n_guerra_ext,
                                "nome_completo": nome_serv,
                                "cidade": extrair_cid(row),
                                "peso": pesos_dict.get(pg_sigla, 99),
                                "unidade": extrair_uni(row),
                                "perfil": "TROPA"
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
            
            c_m1, c_m2, c_m3 = st.columns(3)
            c_m1.metric("👥 Total Lido", f"{len(lista_temp)}")
            c_m2.metric("➕ Novos Militares", f"{novos_cnt}")
            c_m3.metric("🔄 Atualizações", f"{existentes_cnt}")

            df_temp = pd.DataFrame(lista_temp)[["num_policia", "posto_grad", "nome_guerra", "unidade", "perfil"]]
            df_temp.columns = ["Nº Polícia (DV)", "Graduação", "Nome Funcional", "Unidade", "Perfil de Acesso"]
            
            df_editado = st.data_editor(
                df_temp, num_rows="fixed", use_container_width=True, height=260, hide_index=True,
                column_config={
                    "Nº Polícia (DV)": st.column_config.TextColumn(disabled=True), 
                    "Graduação": st.column_config.TextColumn(disabled=True),
                    "Nome Funcional": st.column_config.TextColumn(disabled=True),
                    "Unidade": st.column_config.TextColumn(disabled=True),
                    "Perfil de Acesso": st.column_config.SelectboxColumn("Perfil de Acesso", options=OPCOES_PERFIL, required=True)
                }
            )
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                if st.button("✅ Confirmar e Salvar no Supabase", type="primary", use_container_width=True):
                    mils_memoria = st.session_state.get("lista_militares", [])
                    mapa_memoria = {str(m.get("num_policia", "")).strip().upper(): m for m in mils_memoria}
                    todos_salvar_banco = []
                    
                    for idx_r, row_e in df_editado.iterrows():
                        num_pol_e = str(row_e["Nº Polícia (DV)"]).strip().upper()
                        orig = next((item for item in lista_temp if str(item["num_policia"]).strip().upper() == num_pol_e), {})
                        
                        pg_e = orig.get("posto_grad", "SD")
                        nome_f_e = orig.get("nome_guerra", "MILITAR")
                        nome_c_e = orig.get("nome_completo", f"{pg_e} {nome_f_e}")
                        cidade_e = orig.get("cidade", "N/I")
                        unidade_e = orig.get("unidade", "UNIDADE N/I")
                        perfil_e = str(row_e["Perfil de Acesso"]).strip().upper()

                        if num_pol_e in mapa_memoria:
                            m_exist = mapa_memoria[num_pol_e]
                            m_exist["posto_grad"] = pg_e
                            m_exist["nome_guerra"] = nome_f_e
                            m_exist["nome_completo"] = nome_c_e
                            m_exist["cidade"] = cidade_e
                            m_exist["unidade"] = unidade_e
                            m_exist["perfil"] = perfil_e
                            m_exist["peso"] = pesos_dict.get(pg_e, 99)
                            todos_salvar_banco.append(m_exist)
                        else:
                            novo_obj = {
                                "id": f"mili_{idx_r}_{uuid.uuid4().hex[:6]}",
                                "num_policia": num_pol_e,
                                "posto_grad": pg_e,
                                "nome_guerra": nome_f_e,
                                "nome_completo": nome_c_e,
                                "cidade": cidade_e,
                                "peso": pesos_dict.get(pg_e, 99),
                                "unidade": unidade_e,
                                "perfil": perfil_e
                            }
                            mils_memoria.append(novo_obj)
                            todos_salvar_banco.append(novo_obj)

                    if todos_salvar_banco:
                        salvar_militares_supabase(todos_salvar_banco)

                    st.session_state["lista_militares"] = remover_dup(mils_memoria)
                    st.session_state["temp_importacao_lista"] = []
                    st.session_state["militares_carregados"] = True
                    st.success("✅ Efetivo atualizado com sucesso!")
                    st.rerun()

            with col_m2:
                if st.button("❌ Cancelar", use_container_width=True):
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
            unidade_in = st.text_input("Unidade / Lotação:", placeholder="Ex: 35 CIA PM / 21 BPM").strip().upper()
            cidade_in = st.text_input("Cidade / Fração:", placeholder="Ex: UBÁ, VISCONDE DO RIO BRANCO...").strip().upper()
            perfil_in = st.selectbox("Perfil / Nível de Acesso:", OPCOES_PERFIL, index=0)
            
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
                    unidade_final = unidade_in if unidade_in else "UNIDADE N/I"
                    
                    novo_m = {
                        "id": m_id_novo,
                        "num_policia": num_limpo,
                        "posto_grad": pg_abrev,
                        "nome_guerra": nome_f_upper,
                        "nome_completo": nome_comp_final,
                        "cidade": cidade_final,
                        "peso": pesos_dict.get(pg_abrev, 99),
                        "unidade": unidade_final,
                        "perfil": perfil_in
                    }
                    
                    st.session_state["lista_militares"].append(novo_m)
                    st.session_state["lista_militares"] = remover_dup_func(st.session_state["lista_militares"])
                    st.session_state["militares_carregados"] = True
                    salvar_militares_supabase([novo_m])
                    st.success(f"✅ Militar {nome_f_upper} cadastrado como '{perfil_in}' e salvo no Supabase!")
                    st.rerun()

    _dialog()