"""
==============================================================================
Módulo de Modais do Passo 3 - Importação e Edição em Tabela
Grava militares DIRETAMENTE na tabela 'usuarios' e sincroniza 'unidades_config'.
==============================================================================
"""

import streamlit as st
import uuid
import pandas as pd
from utils.excel_importer import carregar_planilha_universal
from core.database import supabase, extrair_bpm_mae, carregar_militares_supabase
from core.auth import gerar_hash_senha
from utils.file_validator import validar_planilha_upload, desarmar_csv_injection

def salvar_importacao_na_tabela_usuarios(lista_importada):
    """
    Grava os militares importados diretamente na tabela 'usuarios'.
    Elimina permanentemente a antiga tabela 'efetivo'.
    """
    if not supabase or not lista_importada:
        return False

    sucessos = 0
    for m in lista_importada:
        num_pol = str(m.get("num_policia")).strip().upper()
        if not num_pol or num_pol == "N/I":
            continue

        posto = str(m.get("posto_grad", "SD")).strip().upper()
        nome_g = str(m.get("nome_guerra", "MILITAR")).strip().upper()
        nome_c = str(m.get("nome_completo", nome_g)).strip().upper()
        cidade = str(m.get("cidade", "UBÁ")).strip().upper()
        lotacao_completa = str(m.get("lotacao") or m.get("unidade") or "21º BPM").strip().upper()
        bpm_mae = extrair_bpm_mae(lotacao_completa)

        payload_usuario = {
            "usuario_login": num_pol,
            "usuario": num_pol,
            "cargo_funcao": posto,
            "nome_guerra": nome_g,
            "nome_completo": nome_c,
            "unidade": lotacao_completa,
            "cidade": cidade,
            "nivel_acesso": "TROPA",
            "perfil_creds": "TROPA",
            "perfil_escala": "TROPA",
            "ativo": True
        }

        try:
            res = supabase.table("usuarios").select("usuario_login").eq("usuario_login", num_pol).execute()
            if res and res.data and len(res.data) > 0:
                supabase.table("usuarios").update(payload_usuario).eq("usuario_login", num_pol).execute()
            else:
                payload_usuario["senha"] = num_pol
                payload_usuario["senha_hash"] = gerar_hash_senha(num_pol)
                payload_usuario["primeiro_acesso"] = True
                supabase.table("usuarios").insert(payload_usuario).execute()

            # Registra a unidade na tabela unidades_config para atualizar a Sidebar
            supabase.table("unidades_config").upsert({
                "batalhao": bpm_mae,
                "companhia": lotacao_completa,
                "municipio": cidade
            }, on_conflict="batalhao,companhia,municipio").execute()

            sucessos += 1
        except Exception as ex:
            print(f"Erro ao salvar militar {num_pol} na tabela usuarios: {ex}")

    st.cache_data.clear()
    carregar_militares_supabase()
    return sucessos

def abrir_modal_editar_efetivo_tabela(padronizar_grad_func, pesos_dict):
    @st.dialog("✏️ Editar Efetivo em Tabela", width="large")
    def _dialog():
        st.markdown("##### 📝 Edite graduações, nomes, matrículas e unidades:")
        st.caption("Altere os valores na tabela abaixo e clique em 'Salvar' para atualizar diretamente na tabela 'usuarios' do Supabase.")

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
                "Unidade / Lotação": str(m.get("lotacao", m.get("unidade", "UNIDADE N/I"))),
                "Cidade / Fração": str(m.get("cidade", "N/I"))
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
                "Unidade / Lotação": st.column_config.TextColumn("Unidade / Lotação"),
                "Cidade / Fração": st.column_config.TextColumn("Cidade / Fração")
            }
        )

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("💾 Salvar Alterações no Supabase", type="primary", use_container_width=True):
                novos_mils = []
                mapa_existente = {str(m.get("id")): m for m in mils}

                for _, row in df_editado.iterrows():
                    m_id = str(row["ID_INTERNO"])
                    pg_f = padronizar_grad_func(row["Graduação"])
                    num_p = str(row["Nº Polícia (com DV)"]).strip()
                    nome_g = str(row["Nome Funcional"]).strip().upper()
                    nome_c = str(row["Nome Completo"]).strip().upper()
                    uni_val = str(row["Unidade / Lotação"]).strip().upper()
                    cid_val = str(row["Cidade / Fração"]).strip().upper()

                    obj_m = mapa_existente.get(m_id, {"id": m_id})
                    obj_m["num_policia"] = num_p
                    obj_m["posto_grad"] = pg_f
                    obj_m["nome_guerra"] = nome_g
                    obj_m["nome_completo"] = nome_c if nome_c else f"{pg_f} {nome_g}"
                    obj_m["lotacao"] = uni_val if uni_val else "UNIDADE N/I"
                    obj_m["unidade"] = extrair_bpm_mae(uni_val)
                    obj_m["cidade"] = cid_val if cid_val else "N/I"

                    novos_mils.append(obj_m)

                salvar_importacao_na_tabela_usuarios(novos_mils)
                st.session_state["lista_militares"] = novos_mils
                st.session_state["militares_carregados"] = True
                st.success("✅ Tabela de usuários atualizada com sucesso no Supabase!")
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

        st.error(f"⚠️ Você está prestes a excluir definitivamente **{len(mils_para_excluir)} militar(es)** da tabela de usuários.")
        
        df_exc = pd.DataFrame([
            {
                "Grad/Nome": f"{m.get('posto_grad')} {m.get('nome_guerra')}", 
                "Nº Polícia": m.get('num_policia'), 
                "Lotação": m.get('lotacao', m.get('unidade', 'UNIDADE N/I')),
                "Cidade": m.get('cidade', 'N/I')
            } 
            for m in mils_para_excluir
        ])
        st.dataframe(df_exc, use_container_width=True, hide_index=True, height=180)
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            if st.button("🚨 Confirmar Exclusão Definitiva", type="primary", use_container_width=True):
                with st.spinner("Excluindo do banco de dados..."):
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
        remover_dup = funcs_extracao["remover_duplicados"]

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

                            posto_raw = str(row.get("POSTO/GRADUACAO", row.get("POSTO/GRAD", row.get("GRADUAÇÃO", "SD")))).strip().upper()
                            pg_sigla = padronizar_grad(posto_raw)
                            
                            nome_serv = str(row.get("NOME SERVIDOR", row.get("NOME COMPLETO", row.get("NOME", "MILITAR")))).strip().upper()
                            
                            nome_guerra = str(row.get("NOME GUERRA", "")).strip().upper()
                            if not nome_guerra or nome_guerra == "MILITAR":
                                parts_nome = nome_serv.split()
                                nome_guerra = parts_nome[-1] if len(parts_nome) > 1 else nome_serv

                            unidade_raw = str(row.get("NOME UNIDADE", row.get("LOTAÇÃO", row.get("UNIDADE", "21º BPM")))).strip().upper()
                            cidade_raw = str(row.get("NOME MUNICIPIO", row.get("MUNICÍPIO", row.get("CIDADE", "UBÁ")))).strip().upper()

                            lista_temp.append({
                                "num_policia": mat_unificada,
                                "posto_grad": pg_sigla,
                                "nome_guerra": nome_guerra,
                                "nome_completo": nome_serv,
                                "cidade": cidade_raw,
                                "lotacao": unidade_raw,
                                "unidade": extrair_bpm_mae(unidade_raw)
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

            df_temp = pd.DataFrame(lista_temp)[["num_policia", "posto_grad", "nome_guerra", "nome_completo", "lotacao", "cidade"]]
            df_temp.columns = ["Nº Polícia (DV)", "Graduação", "Nome Funcional", "Nome Completo", "Lotação / Cia", "Município"]
            
            df_editado = st.data_editor(
                df_temp, num_rows="fixed", use_container_width=True, height=260, hide_index=True,
                column_config={
                    "Nº Polícia (DV)": st.column_config.TextColumn(disabled=True), 
                    "Graduação": st.column_config.TextColumn(disabled=True),
                    "Nome Funcional": st.column_config.TextColumn("Nome Funcional"),
                    "Nome Completo": st.column_config.TextColumn("Nome Completo"),
                    "Lotação / Cia": st.column_config.TextColumn(disabled=True),
                    "Município": st.column_config.TextColumn(disabled=True)
                }
            )
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                if st.button("✅ Confirmar e Salvar no Supabase", type="primary", use_container_width=True):
                    salvos = salvar_importacao_na_tabela_usuarios(lista_temp)
                    st.session_state["temp_importacao_lista"] = []
                    st.session_state["militares_carregados"] = True
                    st.success(f"✅ {salvos} militar(es) salvos com sucesso na tabela de usuários!")
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
            num_policia_in = st.text_input("Nº Polícia / Matrícula com DV:", placeholder="Ex: 1337468").strip().replace(".", "")
            posto_in = st.selectbox("Graduação:", ["SD AL", "SD", "CB", "3º SGT", "2º SGT", "1º SGT", "SUB TEN", "2º TEN", "1º TEN", "CAP", "MAJ", "TEN CEL"])
            nome_guerra_in = st.text_input("Nome de Guerra / Funcional:", placeholder="Ex: SILVA")
            nome_completo_in = st.text_input("Nome Completo:", placeholder="Ex: CARLOS EDUARDO SILVA")
            unidade_in = st.text_input("Unidade / Lotação Completa:", placeholder="Ex: 1 PEL / 31 CIA PM / 2 BPM").strip().upper()
            cidade_in = st.text_input("Cidade / Fração:", placeholder="Ex: JUIZ DE FORA").strip().upper()
            
            st.markdown("<br>", unsafe_allow_html=True)
            btn_cad_mil = st.form_submit_button("💾 Salvar Militar", type="primary", use_container_width=True)
            
            if btn_cad_mil and num_policia_in and nome_guerra_in:
                num_limpo = str(num_policia_in).strip()
                ja_existe = any(str(m.get("num_policia", "")).strip() == num_limpo for m in st.session_state.get("lista_militares", []))
                
                if ja_existe:
                    st.error("⚠️ Este Número de Polícia já está cadastrado no sistema!")
                else:
                    nome_f_upper = str(nome_guerra_in).strip().upper()
                    pg_abrev = padronizar_graduacao_func(posto_in)
                    nome_comp_final = str(nome_completo_in).strip().upper() if nome_completo_in else f"{pg_abrev} {nome_f_upper}"
                    cidade_final = cidade_in if cidade_in else "UBÁ"
                    unidade_final = unidade_in if unidade_in else "21º BPM"
                    
                    novo_m = {
                        "num_policia": num_limpo,
                        "posto_grad": pg_abrev,
                        "nome_guerra": nome_f_upper,
                        "nome_completo": nome_comp_final,
                        "cidade": cidade_final,
                        "lotacao": unidade_final,
                        "unidade": extrair_bpm_mae(unidade_final)
                    }
                    
                    salvar_importacao_na_tabela_usuarios([novo_m])
                    st.session_state["militares_carregados"] = True
                    st.success(f"✅ Militar {nome_f_upper} cadastrado e salvo no Supabase!")
                    st.rerun()

    _dialog()