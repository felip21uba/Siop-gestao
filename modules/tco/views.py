import streamlit as st
import pandas as pd
import datetime
import uuid
from modules.tco.parser_reds import extrair_dados_reds_pdf
from modules.tco.storage import upload_midia_supabase
from modules.tco.database import salvar_material_supabase, atualizar_material_supabase, registrar_log_supabase
from modules.tco.modais import abrir_modal_edicao_material, abrir_modal_divergencia
from modules.tco.compliance import gerar_pdf_termo_compliance
from utils.file_validator import validar_pdf_upload, validar_imagem_upload, sanitizar_nome_arquivo
from core.database import (
    carregar_militares_supabase,
    atualizar_usuario_supabase,
    supabase,
    registrar_audit_log
)

def calcular_tempo_decorrido(str_data_hora):
    if not str_data_hora or str_data_hora in ["N/A", "Data N/I", "N/I", "None"]:
        return "N/A"
    try:
        dt_evento = pd.to_datetime(str_data_hora)
        delta = datetime.datetime.now() - dt_evento.to_pydatetime().replace(tzinfo=None)
        dias = delta.days
        horas = delta.seconds // 3600
        minutos = (delta.seconds % 3600) // 60
        
        if dias > 0:
            return f"{dias}d {horas}h"
        elif horas > 0:
            return f"{horas}h {minutos}m"
        else:
            return f"{minutos} min"
    except Exception:
        return "N/A"

def aplicar_filtros_bens(lista_bens, reds_q="", autor_q="", militar_q="", unidade_q="", data_q=None):
    resultado = []
    for b in lista_bens:
        if reds_q and reds_q.lower() not in str(b.get("num_reds", "")).lower():
            continue
        if autor_q and autor_q.lower() not in str(b.get("autores", "")).lower():
            continue
        militares_vinculados = f"{b.get('fiel_depositario_atual', '')} {b.get('remetente_ultimo', '')} {b.get('destinatario_pendente', '')}"
        if militar_q and militar_q.lower() not in militares_vinculados.lower():
            continue
        unidades_vinculadas = f"{b.get('unidade_posse_atual', '')} {b.get('unidade_remetente', '')} {b.get('unidade_destinatario_pendente', '')}"
        if unidade_q and unidade_q != "TODAS AS UNIDADES" and unidade_q.lower() not in unidades_vinculadas.lower():
            continue
        if data_q:
            data_str = data_q.strftime("%Y-%m-%d")
            datas_item = f"{b.get('data_ingestao', '')} {b.get('data_posse_atual', '')} {b.get('data_envio_tramite', '')}"
            if data_str not in datas_item:
                continue
        resultado.append(b)
    return resultado

def aplicar_filtros_logs(lista_logs, reds_q="", busca_txt="", militar_q="", data_q=None):
    resultado = []
    for l in lista_logs:
        if reds_q and reds_q.lower() not in str(l.get("num_reds", "")).lower():
            continue
        if busca_txt and busca_txt.lower() not in str(l.get("detalhe", "")).lower() and busca_txt.lower() not in str(l.get("acao", "")).lower():
            continue
        militares_log = f"{l.get('origem', '')} {l.get('destino', '')}"
        if militar_q and militar_q.lower() not in militares_log.lower():
            continue
        if data_q:
            data_str = data_q.strftime("%Y-%m-%d")
            if data_str not in str(l.get("data_hora", "")):
                continue
        resultado.append(l)
    return resultado

# =============================================================================
# ABA 1: INGESTÃO REDS & MÍDIAS
# =============================================================================
def renderizar_aba_ingestao(nome_militar_atual, unidade_militar_atual):
    if "temp_reds_extraido" not in st.session_state:
        st.session_state["temp_reds_extraido"] = None

    col_ing1, col_ing2 = st.columns(2)
    
    with col_ing1:
        with st.container(border=True):
            st.markdown("##### 📄 Importar Ocorrência (BO REDS)")
            arquivo_pdf = st.file_uploader("Selecione o PDF do REDS:", type=["pdf"], key="uploader_reds_pdf_v31")

            if arquivo_pdf is not None:
                valido_pdf, msg_pdf = validar_pdf_upload(arquivo_pdf)
                if not valido_pdf:
                    st.error(msg_pdf)
                else:
                    if st.button("⚡ Processar Recibo JECRIM", type="primary", key="btn_processar_pdf_recibo_v31", use_container_width=True):
                        with st.spinner("Mapeando recibo do JECRIM, relator, natureza e invólucro do material..."):
                            dados_reds = extrair_dados_reds_pdf(arquivo_pdf)
                            st.session_state["temp_reds_extraido"] = dados_reds
                            st.success("Leitura do REDS concluída!")
            else:
                st.caption("Aguardando upload de arquivo PDF...")

    with col_ing2:
        with st.container(border=True):
            st.markdown("##### ➕ Inserção Manual de Material")
            st.caption("Adicione itens avulsos para conferência unificada.")
            with st.popover("📝 Cadastrar Material Avulso", use_container_width=True):
                with st.form("form_material_manual_v31", clear_on_submit=True):
                    man_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-001843571-001").strip()
                    man_autor = st.text_input("Nome do Autor:", placeholder="Ex: MARCIO DE ALMEIDA SOUZA").strip().upper()
                    man_desc = st.text_input("Descrição do Material:", placeholder="Ex: 02 papelotes de cocaína").strip().upper()
                    man_qtd = st.number_input("Quantidade:", min_value=0.1, value=1.0, step=1.0)
                    man_unid = st.selectbox("Unidade:", ["UNIDADE", "KG", "G", "DUZIA", "CAIXA", "PACOTE"])
                    man_inv = st.text_input("Nº do Invólucro / Lacre:", placeholder="Ex: A230767651").strip().upper()

                    btn_man = st.form_submit_button("➕ Adicionar à Lista", type="primary", use_container_width=True)
                    if btn_man:
                        if not man_reds or not man_desc:
                            st.error("⚠️ Preencha o Nº do REDS e a Descrição do Material.")
                        else:
                            if not st.session_state["temp_reds_extraido"]:
                                st.session_state["temp_reds_extraido"] = {
                                    "num_reds": man_reds,
                                    "data_registro": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                                    "data_fato": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                                    "natureza": "INSERÇÃO MANUAL / TCO",
                                    "local": "N/I",
                                    "redator": nome_militar_atual,
                                    "unidade_jecrim": unidade_militar_atual,
                                    "autores": [man_autor] if man_autor else ["AUTOR NÃO INFORMADO"],
                                    "resumo_fato": "Material incluído manualmente pelo operador.",
                                    "materiais": [],
                                    "hash_pdf": "INSERÇÃO MANUAL"
                                }

                            str_item_num = str(len(st.session_state["temp_reds_extraido"]["materiais"]) + 1)
                            inv_final = man_inv if man_inv else f"SEM LACRE (ITEM {str_item_num})"

                            st.session_state["temp_reds_extraido"]["materiais"].append({
                                "remover": False,
                                "item_num": str_item_num,
                                "env_nr": "1",
                                "autor": man_autor if man_autor else "AUTOR NÃO INFORMADO",
                                "situacao": "APREENDIDO",
                                "descricao": man_desc,
                                "quantidade": man_qtd,
                                "unidade": man_unid,
                                "involucro": inv_final,
                                "destinatario_reds": "JECRIM"
                            })
                            st.success(f"Item '{man_desc}' adicionado!")
                            st.rerun()

    if st.session_state.get("temp_reds_extraido"):
        d = st.session_state["temp_reds_extraido"]
        st.divider()
        
        with st.container(border=True):
            st.markdown(f"#### 📄 Dados da Ocorrência — REDS Nº {d['num_reds']}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"• **Data Registro:** {d['data_registro']}")
                st.markdown(f"• **Data/Hora Fato:** {d['data_fato']}")
                st.markdown(f"• **Unidade Destino:** {d['unidade_jecrim']}")
            with c2:
                st.markdown(f"• **Natureza:** {d['natureza']}")
                st.markdown(f"• **Relator:** {d['redator']}")
                st.markdown(f"• **Autor(es):** {', '.join(d['autores'])}")

            st.caption(f"**Local do Fato:** {d['local']}")
            
            with st.expander("📝 **Ver Resumo Fático & Hash SHA-256 do PDF**"):
                st.write(d['resumo_fato'])
                st.caption(f"🔐 Chancela SHA-256: `{d['hash_pdf']}`")

        st.markdown("##### 📦 Conferência e Seleção de Materiais")
        st.caption("Marque a caixa na coluna 'Excluir' para os itens que deseja retirar e clique no botão 'Excluir Marcados'.")

        if d["materiais"]:
            df_mats = pd.DataFrame(d["materiais"])
            if "remover" not in df_mats.columns:
                df_mats.insert(0, "remover", False)
            
            df_editado_ing = st.data_editor(
                df_mats[["remover", "item_num", "descricao", "quantidade", "unidade", "involucro", "autor"]],
                column_config={
                    "remover": st.column_config.CheckboxColumn("🗑️ Excluir", default=False, width="small"),
                    "item_num": st.column_config.TextColumn("Item", disabled=True, width="small"),
                    "descricao": st.column_config.TextColumn("Descrição do Material", width="large"),
                    "quantidade": st.column_config.NumberColumn("Qtd", min_value=0.1, step=1.0, width="small"),
                    "unidade": st.column_config.TextColumn("Unid", width="small"),
                    "involucro": st.column_config.TextColumn("Nº Lacre / Invólucro", width="medium"),
                    "autor": st.column_config.TextColumn("Autor Vinculado", width="medium")
                },
                hide_index=True,
                use_container_width=True,
                key="editor_materiais_ingestao_v31"
            )

            qtd_marcados = len(df_editado_ing[df_editado_ing["remover"] == True])

            photos_ingestao = st.file_uploader(
                "📷 Anexar Mídias / Fotos da Apreensão (Opcional):", 
                type=["jpg", "jpeg", "png", "pdf"], 
                accept_multiple_files=True, 
                key="upl_photos_ingestao_v31"
            )

            col_b1, col_b2, col_b3 = st.columns([2, 1.5, 1])
            with col_b1:
                btn_confirmar = st.button(
                    "💾 Salvar Materiais no Supabase", 
                    type="primary", 
                    key="btn_conf_fiel_dep_v31", 
                    use_container_width=True
                )
            with col_b2:
                btn_excluir_marcados = st.button(
                    f"🗑️ Excluir Marcados ({qtd_marcados})", 
                    disabled=(qtd_marcados == 0),
                    key="btn_excluir_marcados_v31", 
                    use_container_width=True
                )
            with col_b3:
                btn_limpar = st.button("❌ Descartar REDS", key="btn_limpar_ingestao_v31", use_container_width=True)

            if btn_excluir_marcados:
                manter = df_editado_ing[df_editado_ing["remover"] == False]
                novos_mats = []
                for idx_m, row in manter.iterrows():
                    novos_mats.append({
                        "remover": False,
                        "item_num": str(row["item_num"]),
                        "env_nr": "1",
                        "autor": str(row["autor"]),
                        "situacao": "APREENDIDO",
                        "descricao": str(row["descricao"]),
                        "quantidade": float(row["quantidade"]),
                        "unidade": str(row["unidade"]),
                        "involucro": str(row["involucro"]),
                        "destinatario_reds": "JECRIM"
                    })
                st.session_state["temp_reds_extraido"]["materiais"] = novos_mats
                st.success(f"{qtd_marcados} item(ns) removido(s) da lista!")
                st.rerun()

            if btn_limpar:
                st.session_state["temp_reds_extraido"] = None
                st.rerun()

            if btn_confirmar:
                itens_validos = df_editado_ing[df_editado_ing["remover"] == False]
                now_iso = datetime.datetime.now().isoformat()
                now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                midias_iniciais = []

                if photos_ingestao:
                    for p_file in photos_ingestao:
                        ext_p = p_file.name.lower()
                        if ext_p.endswith(".pdf"):
                            valido_p, msg_p = validar_pdf_upload(p_file)
                        else:
                            valido_p, msg_p = validar_imagem_upload(p_file)

                        if not valido_p:
                            st.error(f"Arquivo '{p_file.name}': {msg_p}")
                            return

                        nome_p_seguro = sanitizar_nome_arquivo(p_file.name)
                        p_bytes = p_file.getvalue()
                        
                        resultado_storage = upload_midia_supabase(
                            file_bytes=p_bytes,
                            file_name=nome_p_seguro,
                            file_type=p_file.type,
                            num_reds=d["num_reds"],
                            id_bem=f"INGESTAO-{d['num_reds']}"
                        )
                        if resultado_storage:
                            resultado_storage["enviado_por"] = nome_militar_atual
                            resultado_storage["unidade"] = unidade_militar_atual
                            resultado_storage["data_envio"] = now_str
                            midias_iniciais.append(resultado_storage)
                
                for idx_row, row in itens_validos.iterrows():
                    id_bem_unico = f"BEM-{d['num_reds']}-{row['item_num']}-{uuid.uuid4().hex[:4]}"
                    orig_item = df_mats.iloc[idx_row]
                    
                    desc_final = str(row["descricao"]).strip()
                    qtd_final = float(row["quantidade"])
                    unid_final = str(row["unidade"]).strip()
                    inv_final = str(row["involucro"]).strip()
                    autor_final = str(row["autor"]).strip()

                    foi_editado = (
                        desc_final != str(orig_item.get("descricao", "")).strip() or
                        qtd_final != float(orig_item.get("quantidade", 1.0)) or
                        unid_final != str(orig_item.get("unidade", "")).strip() or
                        inv_final != str(orig_item.get("involucro", "")).strip() or
                        autor_final != str(orig_item.get("autor", "")).strip()
                    )
                    
                    novo_bem = {
                        "id_bem": id_bem_unico,
                        "num_reds": d["num_reds"],
                        "autores": autor_final,
                        "descricao": desc_final,
                        "quantidade": qtd_final,
                        "unidade_medida": unid_final,
                        "involucro_lacre": inv_final,
                        "fase_destinacao": "Com Fiel Depositário / Policial",
                        "fiel_depositario_atual": nome_militar_atual,
                        "unidade_posse_atual": unidade_militar_atual,
                        "data_posse_atual": now_iso,
                        "status_tramite": "Em Custódia",
                        "data_ingestao": now_iso,
                        "dados_originais_pdf": {
                            "autores": str(orig_item.get("autor", "")).strip(),
                            "descricao": str(orig_item.get("descricao", "")).strip(),
                            "quantidade": float(orig_item.get("quantidade", 1.0)),
                            "unidade": str(orig_item.get("unidade", "")).strip(),
                            "involucro": str(orig_item.get("involucro", "")).strip()
                        },
                        "editado_pelo_operador": foi_editado,
                        "midias_anexas": list(midias_iniciais)
                    }
                    salvar_material_supabase(novo_bem)
                    
                    detalhe_log = f"Ingestão de {qtd_final} {unid_final} - {desc_final} (Lacre: {inv_final})"
                    if foi_editado:
                        detalhe_log += f" | EDITADO NA INGESTÃO"

                    registrar_log_supabase({
                        "data_hora": now_iso,
                        "num_reds": d["num_reds"],
                        "bem_id": id_bem_unico,
                        "acao": "INGESTÃO / CUSTÓDIA INICIAL",
                        "origem": f"REDS JECRIM (Relator: {d['redator']})",
                        "unidade_origem": unidade_militar_atual,
                        "destino": nome_militar_atual,
                        "unidade_destino": unidade_militar_atual,
                        "detalhe": detalhe_log
                    })

                del st.session_state["temp_reds_extraido"]
                st.success("Materiais selecionados salvos com sucesso no Supabase!")
                st.rerun()

# =============================================================================
# ABA 2: MEUS MATERIAIS EM CUSTÓDIA
# =============================================================================
def renderizar_aba_meus_bens(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    usr_logado = st.session_state.get("usuario_dados", {})
    usr_id = str(usr_logado.get("id") or usr_logado.get("usuario_login") or "").strip()
    cargo_f = str(usr_logado.get("cargo_funcao", "POLICIAL MILITAR")).strip()

    col_tit1, col_tit2 = st.columns([3, 1.2])
    with col_tit1:
        st.markdown(f"#### 🎒 Materiais sob Fiel Depósito de: **{nome_militar_atual}**")
    
    with col_tit2:
        pdf_comp = gerar_pdf_termo_compliance(
            nome_militar=nome_militar_atual,
            cargo_funcao=cargo_f,
            unidade=unidade_militar_atual,
            usuario_id=usr_id,
            data_aceite_str=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        )
        st.download_button(
            label="🖨️ Imprimir Termo Compliance",
            data=pdf_comp,
            file_name=f"Termo_Compliance_{usr_id}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    meus_bens = [b for b in all_bens_banco if b.get("fiel_depositario_atual") == nome_militar_atual and b.get("status_tramite") == "Em Custódia"]
    
    if meus_bens:
        for mb in meus_bens:
            mb["tempo_posse"] = calcular_tempo_decorrido(mb.get("data_posse_atual"))
            mb["status_edicao"] = "Editado" if mb.get("editado_pelo_operador") else "Original"

        df_mb = pd.DataFrame(meus_bens)
        st.dataframe(
            df_mb[["id_bem", "num_reds", "autores", "descricao", "quantidade", "unidade_medida", "involucro_lacre", "tempo_posse", "status_edicao"]],
            column_config={
                "id_bem": "Código Bem",
                "num_reds": "Nº REDS",
                "autores": "Autor(es)",
                "descricao": "Descrição",
                "quantidade": "Qtd",
                "unidade_medida": "Unid",
                "involucro_lacre": "Invólucro / Lacre",
                "tempo_posse": "Tempo na Posse",
                "status_edicao": "Origem"
            },
            hide_index=True, use_container_width=True
        )
        
        st.divider()
        st.markdown("##### ⚙️ Ações e Mídias Anexas:")
        for idx_m, item_meu in enumerate(meus_bens):
            with st.container(border=True):
                c_meu1, c_meu2 = st.columns([3.5, 1.5])
                with c_meu1:
                    st.markdown(f"📄 **Nº REDS:** **{item_meu.get('num_reds', 'N/I')}** | **Código:** **{item_meu.get('id_bem', 'N/I')}**")
                    st.markdown(f"📦 **Descrição do Material:** **{item_meu.get('descricao', 'N/I')}**")
                    st.markdown(f"👤 **Nome do Autor:** **{item_meu.get('autores', 'AUTOR NÃO INFORMADO')}**")
                    st.caption(f"🔒 Lacre/Invólucro: **{item_meu.get('involucro_lacre', 'N/I')}** | Qtd: **{item_meu.get('quantidade', '1.0')} {item_meu.get('unidade_medida', 'UN')}**")
                    
                    midias = item_meu.get("midias_anexas") or []
                    if midias:
                        st.caption(f"📎 **{len(midias)} arquivo(s) anexo(s):**")
                        for m_anexa in midias:
                            url = m_anexa.get("url_publica")
                            nome_f = m_anexa.get("nome_arquivo", "Arquivo")
                            if url:
                                st.markdown(f"• [{nome_f}]({url})")
                    else:
                        st.caption("Nenhuma mídia anexa registrada.")
                with c_meu2:
                    if st.button("✏️ Editar / Anexar Mídias", key=f"btn_edit_meu_bem_{item_meu['id_bem']}_{idx_m}", use_container_width=True):
                        abrir_modal_edicao_material(item_meu, nome_militar_atual, unidade_militar_atual)
    else:
        st.info("Você não possui nenhum material sob sua custódia no momento.")

# =============================================================================
# ABA 3: TRAMITAÇÃO COM DESTINO AO CREDS TCO DA COMPANHIA
# =============================================================================
def renderizar_aba_transferencias(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    st.markdown("#### 🔄 Tramitação Multi-Unidades & Aceite Parcial")
    
    # Destinos institucionais dinâmicos por Cia
    unidades_creds_destino = [
        "CREDS TCO - 35ª CIA PM",
        "CREDS TCO - 111ª CIA PM",
        "CREDS TCO - 112ª CIA PM",
        "CREDS TCO - 21º BPM",
        "CREDS TCO - CENTRAL DE CUSTÓDIA"
    ]

    meus_bens = [b for b in all_bens_banco if b.get("fiel_depositario_atual") == nome_militar_atual and b.get("status_tramite") == "Em Custódia"]

    with st.expander("🔍 **Filtros de Pesquisa na Tramitação**", expanded=True):
        f3_col1, f3_col2, f3_col3, f3_col4 = st.columns(4)
        with f3_col1:
            f3_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-000484967", key="f3_reds").strip()
        with f3_col2:
            f3_autor = st.text_input("Nome do Autor:", placeholder="Ex: DOUGLAS", key="f3_autor").strip()
        with f3_col3:
            f3_militar = st.text_input("Militar / Custodiante:", placeholder="Ex: ALEXANDRINO", key="f3_militar").strip()
        with f3_col4:
            f3_unidade = st.selectbox("Unidade Fiel Depósito:", ["TODAS AS UNIDADES"] + unidades_creds_destino, key="f3_unidade")

    meus_bens_filtrados = aplicar_filtros_bens(meus_bens, f3_reds, f3_autor, f3_militar, f3_unidade)
    
    mils_todos = st.session_state.get("lista_militares", [])
    nomes_mils_base = [f"{m.get('posto_grad')} {m.get('nome_guerra')}" for m in mils_todos] if mils_todos else ["CB MORAES", "SD VINICIUS", "SGT SILVA"]
    
    opcoes_destinatarios_geral = unidades_creds_destino + [n for n in nomes_mils_base if n != nome_militar_atual]

    # SEÇÃO 1: ENCAMINHAR MATERIAIS EM LOTE
    with st.container(border=True):
        st.markdown("##### 📤 1. Encaminhar Materiais em LOTE")
        st.caption("Envie um ou múltiplos materiais para o CREDS TCO da Companhia ou para outro militar específico.")

        bens_disp = {
            f"{b['id_bem']} | REDS: {b['num_reds']} - {b['descricao']} (Lacre: {b.get('involucro_lacre', 'N/I')})": b['id_bem'] 
            for b in meus_bens_filtrados
        }

        if bens_disp:
            itens_selecionados_keys = st.multiselect(
                "Selecione o(s) Material(is) para Tramitar:",
                options=list(bens_disp.keys()),
                key="ms_materiais_transf_v31"
            )
            
            c_tr1, c_tr2 = st.columns(2)
            with c_tr1:
                destinatario_sel = st.selectbox("Selecione o Destino (CREDS Cia ou Militar):", opcoes_destinatarios_geral, key="sel_destinatario_v31")
            with c_tr2:
                unidade_dest_sel = st.selectbox("Unidade Responsável:", ["35ª CIA PM", "21º BPM", "111ª CIA PM", "112ª CIA PM", "CREDS CENTRAL"], key="sel_unidade_dest_v31")
            
            obs_transf = st.text_input("Observações Gerais da Tramitação:", key="txt_obs_transf_v31", placeholder="Ex: Encaminhado para o depósito do CREDS TCO da Cia")

            qtd_sel_envio = len(itens_selecionados_keys)
            
            btn_tramitar = st.button(
                f"📤 Tramitar {qtd_sel_envio} Material(is) Selecionado(s)", 
                type="primary", 
                disabled=(qtd_sel_envio == 0),
                key="btn_tramitar_lote_v31",
                use_container_width=True
            )

            if btn_tramitar:
                now_iso = datetime.datetime.now().isoformat()
                sucessos = 0
                
                for key_item in itens_selecionados_keys:
                    id_bem_alvo = bens_disp[key_item]
                    bem_obj = next(b for b in all_bens_banco if b["id_bem"] == id_bem_alvo)
                    
                    upd_data = {
                        "status_tramite": "Pendente Aceite",
                        "remetente_ultimo": nome_militar_atual,
                        "unidade_remetente": unidade_militar_atual,
                        "destinatario_pendente": destinatario_sel,
                        "unidade_destinatario_pendente": unidade_dest_sel,
                        "data_envio_tramite": now_iso,
                        "obs_tramite": obs_transf
                    }
                    
                    if atualizar_material_supabase(id_bem_alvo, upd_data):
                        registrar_log_supabase({
                            "data_hora": now_iso,
                            "num_reds": bem_obj["num_reds"],
                            "bem_id": id_bem_alvo,
                            "acao": "SOLICITAÇÃO DE TRAMITAÇÃO EM LOTE",
                            "origem": nome_militar_atual,
                            "unidade_origem": unidade_militar_atual,
                            "destino": destinatario_sel,
                            "unidade_destino": unidade_dest_sel,
                            "detalhe": f"Encaminhado para {destinatario_sel} ({unidade_dest_sel}). Obs: {obs_transf}"
                        })
                        sucessos += 1

                st.success(f"Tramitação de {sucessos} material(is) registrada com sucesso!")
                st.rerun()
        else:
            st.info("Nenhum material sob sua custódia disponível para tramitação com os filtros atuais.")

    st.divider()

    # SEÇÃO 2: RECEBIMENTO DE CUSTÓDIA (INDIVIDUAL OU CAIXA DO CREDS DA CIA)
    usr_logado = st.session_state.get("usuario_dados", {})
    perfil_usr = str(usr_logado.get("nivel_acesso", "TROPA")).upper()
    cargo_usr = str(usr_logado.get("cargo_funcao", "")).upper()
    
    eh_gestor_creds = "CREDS" in perfil_usr or "PROGRAMADOR" in cargo_usr or "ADMIN" in perfil_usr or "P1" in perfil_usr or "COMANDANTE" in cargo_usr

    with st.container(border=True):
        st.markdown("##### 📥 2. Recebimento de Custódia")
        st.caption("Confira os materiais direcionados a você ou à caixa do CREDS TCO da sua Companhia.")

        pendentes_para_mim = []
        for b in all_bens_banco:
            if b.get("status_tramite") == "Pendente Aceite":
                dest_p = str(b.get("destinatario_pendente", ""))
                # Se for diretamente para o militar ou direcionado ao CREDS da Cia do gestor
                if dest_p == nome_militar_atual or (eh_gestor_creds and "CREDS" in dest_p):
                    pendentes_para_mim.append(b)

        pendentes_filtrados = aplicar_filtros_bens(pendentes_para_mim, f3_reds, f3_autor, f3_militar, f3_unidade)

        if pendentes_filtrados:
            df_pend = pd.DataFrame(pendentes_filtrados)
            if "receber" not in df_pend.columns:
                df_pend.insert(0, "receber", True)

            df_editado_rec = st.data_editor(
                df_pend[["receber", "id_bem", "num_reds", "descricao", "involucro_lacre", "remetente_ultimo", "unidade_remetente", "obs_tramite"]],
                column_config={
                    "receber": st.column_config.CheckboxColumn("✅ Receber?", default=True, width="small"),
                    "id_bem": st.column_config.TextColumn("Código Bem", disabled=True, width="small"),
                    "num_reds": st.column_config.TextColumn("Nº REDS", disabled=True, width="medium"),
                    "descricao": st.column_config.TextColumn("Descrição do Material", disabled=True, width="large"),
                    "involucro_lacre": st.column_config.TextColumn("Nº Lacre", disabled=True, width="medium"),
                    "remetente_ultimo": st.column_config.TextColumn("Remetente", disabled=True, width="medium"),
                    "unidade_remetente": st.column_config.TextColumn("Unidade Origem", disabled=True, width="medium"),
                    "obs_tramite": st.column_config.TextColumn("Obs Envio", disabled=True, width="medium")
                },
                hide_index=True,
                use_container_width=True,
                key="editor_pendentes_rec_v31"
            )

            itens_aceitar = df_editado_rec[df_editado_rec["receber"] == True]
            itens_recusar = df_editado_rec[df_editado_rec["receber"] == False]

            qtd_aceitar = len(itens_aceitar)
            qtd_recusar = len(itens_recusar)

            col_acc1, col_acc2 = st.columns(2)
            with col_acc1:
                btn_aceitar_selecionados = st.button(
                    f"✅ Confirmar Recebimento ({qtd_aceitar} item/ns)",
                    type="primary",
                    disabled=(qtd_aceitar == 0),
                    use_container_width=True,
                    key="btn_acc_sel_v31"
                )

            with col_acc2:
                btn_recusar_desmarcados = st.button(
                    f"⚠️ Registrar Divergência / Recusa nos Não Marcados ({qtd_recusar} item/ns)",
                    disabled=(qtd_recusar == 0),
                    use_container_width=True,
                    key="btn_rec_des_v31"
                )

            if btn_aceitar_selecionados:
                now_iso = datetime.datetime.now().isoformat()
                sucessos_acc = 0

                for idx_a, row_a in itens_aceitar.iterrows():
                    id_bem_acc = str(row_a["id_bem"])
                    p_orig = next(b for b in pendentes_filtrados if b["id_bem"] == id_bem_acc)
                    
                    orig = p_orig.get('remetente_ultimo') or p_orig.get('fiel_depositario_atual')
                    orig_unid = p_orig.get('unidade_remetente') or p_orig.get('unidade_posse_atual')

                    upd_data = {
                        "fiel_depositario_atual": nome_militar_atual,
                        "unidade_posse_atual": unidade_militar_atual,
                        "data_posse_atual": now_iso,
                        "status_tramite": "Em Custódia",
                        "destinatario_pendente": None,
                        "unidade_destinatario_pendente": None,
                        "data_envio_tramite": None
                    }

                    if atualizar_material_supabase(id_bem_acc, upd_data):
                        registrar_log_supabase({
                            "data_hora": now_iso,
                            "num_reds": p_orig["num_reds"],
                            "bem_id": id_bem_acc,
                            "acao": "ACEITE DE CUSTÓDIA FÍSICA",
                            "origem": orig,
                            "unidade_origem": orig_unid,
                            "destino": nome_militar_atual,
                            "unidade_destino": unidade_militar_atual,
                            "detalhe": f"Aceite de custódia confirmado por {nome_militar_atual} na unidade {unidade_militar_atual}."
                        })
                        sucessos_acc += 1

                st.success(f"{sucessos_acc} material(is) incorporado(s) à sua custódia física!")
                st.rerun()

            if btn_recusar_desmarcados:
                st.warning("⚠️ Informe o motivo e a justificativa para a recusa dos itens desmarcados:")
                with st.form("form_motivo_recusa_lote_v31"):
                    motivo_lote = st.selectbox(
                        "Motivo da Divergência:",
                        [
                            "Invólucro / Lacre Violado ou Rompido",
                            "Quantidade do Material Menor que a Declarada",
                            "Material Avariado / Danificado",
                            "Objeto Incompatível com a Descrição",
                            "Material Ausente / Não Entregue pelo Remetente"
                        ]
                    )
                    justificativa_lote = st.text_area("Justificativa Detalhada (Mínimo 10 caracteres):", placeholder="Descreva o motivo da não aceitação deste material...")
                    btn_confirmar_recusa_lote = st.form_submit_button("🚨 Confirmar Recusa/Divergência", type="primary", use_container_width=True)

                    if btn_confirmar_recusa_lote:
                        if not justificativa_lote or len(justificativa_lote.strip()) < 10:
                            st.error("A justificativa detalhada é obrigatória.")
                        else:
                            now_iso = datetime.datetime.now().isoformat()
                            now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            sucessos_div = 0

                            for idx_r, row_r in itens_recusar.iterrows():
                                id_bem_rec = str(row_r["id_bem"])
                                p_orig = next(b for b in pendentes_filtrados if b["id_bem"] == id_bem_rec)
                                
                                origem_remetente = p_orig.get("remetente_ultimo") or p_orig.get("fiel_depositario_atual")
                                unidade_remetente = p_orig.get("unidade_remetente") or p_orig.get("unidade_posse_atual")

                                dados_div = {
                                    "motivo": motivo_lote,
                                    "justificativa": justificativa_lote.strip(),
                                    "registrado_por": nome_militar_atual,
                                    "unidade": unidade_militar_atual,
                                    "data_hora": now_str,
                                    "remetente_origem": origem_remetente,
                                    "unidade_remetente": unidade_remetente
                                }

                                upd_data = {
                                    "status_tramite": "Divergência Registrada",
                                    "dados_divergencia": dados_div
                                }

                                if atualizar_material_supabase(id_bem_rec, upd_data):
                                    registrar_log_supabase({
                                        "data_hora": now_iso,
                                        "num_reds": p_orig["num_reds"],
                                        "bem_id": id_bem_rec,
                                        "acao": "REGISTRO DE DIVERGÊNCIA / RECUSA",
                                        "origem": origem_remetente,
                                        "unidade_origem": unidade_remetente,
                                        "destino": nome_militar_atual,
                                        "unidade_destino": unidade_militar_atual,
                                        "detalhe": f"MOTIVO: {motivo_lote} | JUSTIFICATIVA: {justificativa_lote.strip()}"
                                    })
                                    sucessos_div += 1

                            st.success(f"Divergência registrada para {sucessos_div} material(is)!")
                            st.rerun()

        else:
            st.info("Nenhuma transferência pendente de aceite para você ou para o CREDS TCO da sua Cia.")

# =============================================================================
# ABA 5: PAINEL CREDS-TCO (GESTOR, PERÍCIA, DESTRUIÇÃO & DESIGNAÇÃO DE OPERADORES)
# =============================================================================
def renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual):
    st.markdown("#### 🏛️ Painel do Gestor CREDS-TCO & Controle Geral de Custódia")
    unidades_disponiveis = ["TODAS AS UNIDADES", "35ª CIA PM", "21º BPM", "111ª CIA PM", "112ª CIA PM", "CREDS CENTRAL"]
    
    if not eh_gestor_creds:
        st.error("🔒 **Acesso Restrito:** Apenas Gestores do CREDS-TCO, P1, Comandantes ou Administradores podem gerenciar a custódia geral.")
    else:
        # INDICADORES EM TEMPO REAL (KPIs)
        q_custodia = len([b for b in all_bens_banco if b.get("fase_destinacao") == "Com Fiel Depositário / Policial" and b.get("status_tramite") == "Em Custódia"])
        q_pericia = len([b for b in all_bens_banco if "Perícia" in str(b.get("fase_destinacao", ""))])
        q_jecrim = len([b for b in all_bens_banco if "JECRIM" in str(b.get("fase_destinacao", "")) or "Fórum" in str(b.get("fase_destinacao", ""))])
        q_destruicao = len([b for b in all_bens_banco if "Destruição" in str(b.get("fase_destinacao", "")) or "DESTRUÍDO" in str(b.get("fase_destinacao", ""))])

        kp1, kp2, kp3, kp4 = st.columns(4)
        with kp1:
            st.metric("📦 Em Custódia", q_custodia)
        with kp2:
            st.metric("🔬 Em Perícia", q_pericia)
        with kp3:
            st.metric("🏛️ No JECRIM/Fórum", q_jecrim)
        with kp4:
            st.metric("🔥 Destruição/Descarte", q_destruicao)

        st.divider()

        with st.expander("🔍 **Filtros de Pesquisa do Acervo Geral**", expanded=True):
            f4_col1, f4_col2, f4_col3, f4_col4 = st.columns(4)
            with f4_col1:
                f4_reds = st.text_input("Nº REDS:", placeholder="Ex: 2026-000484967", key="f4_reds").strip()
            with f4_col2:
                f4_autor = st.text_input("Autor:", placeholder="Ex: DOUGLAS", key="f4_autor").strip()
            with f4_col3:
                f4_militar = st.text_input("Militar Responsável:", placeholder="Ex: ALEXANDRINO", key="f4_militar").strip()
            with f4_col4:
                f4_unidade = st.selectbox("Filtrar Unidade Policial:", unidades_disponiveis, key="f4_unidade")

        all_bens_filtrados = aplicar_filtros_bens(all_bens_banco, f4_reds, f4_autor, f4_militar, f4_unidade)

        bens_divergentes = [b for b in all_bens_filtrados if b.get("status_tramite") == "Divergência Registrada"]
        if bens_divergentes:
            st.error(f"🚨 **ALERTA CRÍTICO:** Existem {len(bens_divergentes)} material(is) com divergência registrada aguardando apuração!")
            for idx_div, bd in enumerate(bens_divergentes):
                div = bd.get("dados_divergencia") or {}
                with st.container(border=True):
                    st.markdown(f"**🚨 DIVERGÊNCIA:** **{bd['id_bem']}** (REDS: **{bd['num_reds']}**)")
                    st.markdown(f"Material: **{bd['descricao']}** | Recusado por: **{div.get('registrado_por')}**")
                    st.caption(f"Motivo: {div.get('motivo')} | Justificativa: {div.get('justificativa')}")
                    
                    if st.button("✅ Resolver Divergência e Restaurar Custódia", key=f"btn_res_div_{bd['id_bem']}_{idx_div}", use_container_width=True):
                        now_iso = datetime.datetime.now().isoformat()
                        upd_data = {"status_tramite": "Em Custódia"}
                        
                        if atualizar_material_supabase(bd["id_bem"], upd_data):
                            registrar_log_supabase({
                                "data_hora": now_iso,
                                "num_reds": bd["num_reds"],
                                "bem_id": bd["id_bem"],
                                "acao": "RESOLUÇÃO DE DIVERGÊNCIA",
                                "origem": "CREDS-TCO",
                                "unidade_origem": unidade_militar_atual,
                                "destino": bd["fiel_depositario_atual"],
                                "unidade_destino": bd.get("unidade_posse_atual"),
                                "detalhe": "Divergência apurada e resolvida pelo Gestor do CREDS."
                            })
                            st.success("Divergência resolvida com sucesso!")
                            st.rerun()

        st.markdown(f"##### 📦 Acervo Geral sob Monitoramento ({len(all_bens_filtrados)} item(ns)):")
        
        opcoes_destinacao = [
            "Com Fiel Depositário / Policial",
            "Encaminhado para Perícia Técnica",
            "Retornado da Perícia (Em Custódia)",
            "Encaminhado à Delegacia de Polícia Civil (PCMG)",
            "Encaminhado ao JECRIM / Fórum",
            "Guardado no Depósito (Aguardando Autorização Judicial)",
            "Autorizada Destruição (Aguardando Descarte)",
            "DESTRUÍDO / DESCARTADO (ENCERRADO)"
        ]

        for idx_creds, bem in enumerate(all_bens_filtrados):
            tempo_no_sistema = calcular_tempo_decorrido(bem.get("data_ingestao"))
            fase_atual = bem.get("fase_destinacao")
            eh_encerrado = "DESTRUÍDO" in str(fase_atual) or "ENCERRADO" in str(fase_atual)
            
            with st.container(border=True):
                c_cr1, c_cr2 = st.columns([3, 2])
                with c_cr1:
                    st.markdown(f"📄 REDS: **{bem['num_reds']}** | Code: **{bem['id_bem']}**")
                    st.markdown(f"📦 Material: **{bem['descricao']}** | Autor: **{bem['autores']}**")
                    st.caption(f"🔒 Lacre: **{bem.get('involucro_lacre')}** | Custódia: **{bem['fiel_depositario_atual']}** | Tempo: **{tempo_no_sistema}**")
                    if bem.get("pa_oficio_autorizador"):
                        st.caption(f"📑 P.A. / Ofício Autorizador: **{bem['pa_oficio_autorizador']}**")
                    if eh_encerrado:
                        st.error("🔒 STATUS: MATERIAL ENCERRADO / DESTRUÍDO (REGISTRO CONGELADO)")

                with c_cr2:
                    index_dest = opcoes_destinacao.index(fase_atual) if fase_atual in opcoes_destinacao else 0
                    nova_dest = st.selectbox(
                        "Fase / Destinação Final:",
                        options=opcoes_destinacao,
                        index=index_dest,
                        disabled=eh_encerrado,
                        key=f"sel_dest_creds_{bem['id_bem']}_{idx_creds}"
                    )
                    
                    e_orgao_externo = nova_dest in [
                        "Encaminhado à Delegacia de Polícia Civil (PCMG)",
                        "Encaminhado ao JECRIM / Fórum",
                        "Encaminhado para Perícia Técnica",
                        "DESTRUÍDO / DESCARTADO (ENCERRADO)"
                    ]

                    input_pa_oficio = ""
                    if e_orgao_externo and nova_dest != fase_atual and not eh_encerrado:
                        input_pa_oficio = st.text_input(
                            "Nº do P.A. / Auto / Ofício:",
                            placeholder="Ex: OFÍCIO 142/2026-35CIA",
                            key=f"pa_oficio_in_{bem['id_bem']}_{idx_creds}"
                        ).strip()

                    if nova_dest != fase_atual and not eh_encerrado:
                        if st.button("💾 Confirmar Alteração", key=f"btn_salvar_fase_{bem['id_bem']}_{idx_creds}", type="primary", use_container_width=True):
                            if e_orgao_externo and not input_pa_oficio:
                                st.error("Informe o número do P.A., Auto de Destruição ou Ofício.")
                            else:
                                now_iso = datetime.datetime.now().isoformat()
                                upd_data = {"fase_destinacao": nova_dest}
                                if input_pa_oficio:
                                    upd_data["pa_oficio_autorizador"] = input_pa_oficio
                                
                                # Se retornou da perícia, reativa a custódia normal
                                if nova_dest == "Retornado da Perícia (Em Custódia)":
                                    upd_data["status_tramite"] = "Em Custódia"
                                    upd_data["fase_destinacao"] = "Com Fiel Depositário / Policial"

                                if atualizar_material_supabase(bem["id_bem"], upd_data):
                                    registrar_log_supabase({
                                        "data_hora": now_iso,
                                        "num_reds": bem["num_reds"],
                                        "bem_id": bem["id_bem"],
                                        "acao": "ALTERAÇÃO DE DESTINAÇÃO FINAL / PERÍCIA",
                                        "origem": "CREDS-TCO",
                                        "unidade_origem": unidade_militar_atual,
                                        "destino": nova_dest,
                                        "unidade_destino": "Órgão Externo / CREDS",
                                        "detalhe": f"Nova Fase: {nova_dest} | Doc Autorizador: {input_pa_oficio or 'N/A'}"
                                    })
                                    st.success("Fase e histórico atualizados!")
                                    st.rerun()

# =============================================================================
# ABA 6: TRILHA DE AUDITORIA
# =============================================================================
def renderizar_aba_logs(all_logs_banco):
    st.markdown("#### 📜 Trilha de Auditoria Imutável da Custódia (Supabase)")
    
    with st.expander("🔍 **Filtros de Pesquisa na Trilha de Auditoria**", expanded=True):
        f5_col1, f5_col2, f5_col3, f5_col4 = st.columns(4)
        with f5_col1:
            f5_reds = st.text_input("REDS:", placeholder="Ex: 2026-000484967", key="f5_reds").strip()
        with f5_col2:
            f5_busca = st.text_input("Palavra-chave / Detalhes:", placeholder="Ex: Edição, Lacre, SHA-256", key="f5_busca").strip()
        with f5_col3:
            f5_militar = st.text_input("Militar Envolvido:", placeholder="Ex: ALEXANDRINO", key="f5_militar").strip()
        with f5_col4:
            usar_f5_data = st.checkbox("Filtrar por Data", key="f5_chk_data")
            f5_data = st.date_input("Data do Evento:", datetime.date.today(), key="f5_data") if usar_f5_data else None

    logs_filtrados = aplicar_filtros_logs(all_logs_banco, f5_reds, f5_busca, f5_militar, f5_data)
    
    if logs_filtrados:
        df_l = pd.DataFrame(logs_filtrados)
        cols_exibicao = ["data_hora", "num_reds", "bem_id", "acao", "origem", "unidade_origem", "destino", "unidade_destino", "detalhe"]
        cols_reais = [c for c in cols_exibicao if c in df_l.columns]
        st.dataframe(df_l[cols_reais], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum registro de auditoria encontrado com os parâmetros selecionados.")
        # =============================================================================
# ABA 7: DESIGNAÇÃO DE GESTORES DO CREDS TCO (100% RECLUSA NO MÓDULO TCO)
# =============================================================================

def renderizar_aba_gestores_creds(nome_operador, unidade_operador, cargo_operador, perfil_operador):
    """Aba de uso exclusivo da P1/Comandante para nomear e revogar Gestores CREDS-TCO."""
    eh_autorizado = any(k in f"{cargo_operador} {perfil_operador}".upper() for k in ["PROGRAMADOR", "ADMIN", "P1", "COMANDANTE"])

    if not eh_autorizado:
        st.error("🔒 **Acesso Restrito:** Apenas P1, Comandante ou Administradores do SIOP podem nomear Gestores do CREDS-TCO.")
        return

    st.markdown("#### 👥 Gestão e Nomeação de Gestores CREDS-TCO")
    st.caption("Conceda ou revogue a função de Gestor do CREDS-TCO para militares da unidade. Gestores possuem acesso ao acervo geral, à caixa coletiva do setor e ao controle de perícias/descarte.")

    all_milit = carregar_militares_supabase()
    
    usuarios_banco = []
    if supabase:
        try:
            res_u = supabase.table("usuarios").select("*").execute()
            usuarios_banco = res_u.data or []
        except Exception as e:
            st.warning(f"Aviso ao consultar lista de usuários: {e}")

    df_u = pd.DataFrame(usuarios_banco) if usuarios_banco else pd.DataFrame()

    col_des1, col_des2 = st.columns(2)

    with col_des1:
        with st.container(border=True):
            st.markdown("##### ➕ Nomear Novo Gestor CREDS")
            
            mils_unidade = [m for m in all_milit if "PROGRAMADOR" in cargo_operador or "ADMIN" in perfil_operador or m.get("unidade") == unidade_operador]
            
            opcoes_militar = {
                f"{m.get('posto_grad')} {m.get('nome_guerra')} (PM: {m.get('num_policia')}) - {m.get('unidade')}": m
                for m in mils_unidade
            }

            if opcoes_militar:
                militar_sel_key = st.selectbox("Selecione o Militar para Atribuir a Função:", list(opcoes_militar.keys()), key="sel_mil_creds_aba7")
                militar_obj = opcoes_militar[militar_sel_key]
                num_pm = str(militar_obj.get("num_policia", "")).strip()

                if st.button("✅ Conceder Função CREDS-TCO", type="primary", use_container_width=True, key="btn_add_creds_aba7"):
                    if atualizar_usuario_supabase(num_pm, {
                        "nivel_acesso": "CREDS",
                        "unidade": militar_obj.get("unidade")
                    }):
                        registrar_audit_log(
                            operador_pm=f"{cargo_operador} {nome_operador}",
                            alvo_pm=num_pm,
                            tipo_acao="DESIGNAÇÃO GESTOR CREDS",
                            descricao=f"Função de Gestor CREDS TCO atribuída ao militar {militar_obj.get('nome_guerra')} ({num_pm}) na unidade {militar_obj.get('unidade')}."
                        )
                        st.success(f"Função de Gestor CREDS-TCO concedida com sucesso ao militar {militar_obj.get('nome_guerra')}!")
                        st.rerun()
            else:
                st.info("Nenhum militar encontrado para nomeação na unidade atual.")

    with col_des2:
        with st.container(border=True):
            st.markdown("##### 📜 Gestores CREDS Ativos")
            
            gestores_creds = []
            if not df_u.empty and "nivel_acesso" in df_u.columns:
                gestores_creds = df_u[df_u["nivel_acesso"] == "CREDS"].to_dict("records")

            if gestores_creds:
                for idx_g, g in enumerate(gestores_creds):
                    with st.container(border=True):
                        st.markdown(f"**👤 {g.get('cargo_funcao', 'PM')} {g.get('nome_guerra', 'OPERADOR')}**")
                        st.caption(f"PM: **{g.get('usuario_login')}** | Unidade: **{g.get('unidade', '35ª CIA PM')}**")
                        
                        if st.button("🔻 Revogar Função CREDS", key=f"btn_revogar_creds_aba7_{g.get('usuario_login')}_{idx_g}", use_container_width=True):
                            num_pm_rev = str(g.get("usuario_login")).strip()
                            if atualizar_usuario_supabase(num_pm_rev, {"nivel_acesso": "TROPA"}):
                                registrar_audit_log(
                                    operador_pm=f"{cargo_operador} {nome_operador}",
                                    alvo_pm=num_pm_rev,
                                    tipo_acao="REVOGAÇÃO GESTOR CREDS",
                                    descricao=f"Função de Gestor CREDS TCO revogada para o militar {num_pm_rev}."
                                )
                                st.success("Função CREDS revogada!")
                                st.rerun()
            else:
                st.info("Nenhum gestor CREDS ativo cadastrado na unidade.")