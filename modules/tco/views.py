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
    col_ing1, col_ing2 = st.columns(2)
    
    with col_ing1:
        with st.container(border=True):
            st.markdown("##### 📄 Importar Ocorrência (BO REDS)")
            arquivo_pdf = st.file_uploader("Selecione o PDF do REDS:", type=["pdf"], key="uploader_reds_pdf_v23")

            if arquivo_pdf is not None:
                valido_pdf, msg_pdf = validar_pdf_upload(arquivo_pdf)
                if not valido_pdf:
                    st.error(msg_pdf)
                else:
                    if st.button("⚡ Processar Recibo JECRIM", type="primary", key="btn_processar_pdf_recibo_v23", use_container_width=True):
                        with st.spinner("Mapeando recibo do JECRIM, relator, natureza e invólucro do material..."):
                            dados_reds = extrair_dados_reds_pdf(arquivo_pdf)
                            st.session_state["temp_reds_extraido"] = dados_reds
                            st.success("Leitura do REDS concluída!")
            else:
                st.caption("Aguardando arquivo PDF...")

    with col_ing2:
        with st.container(border=True):
            st.markdown("##### ➕ Inserção Manual de Material")
            st.caption("Cadastre itens sem recibo eletrônico do JECRIM.")
            with st.popover("📝 Cadastrar Material Avulso", use_container_width=True):
                with st.form("form_material_manual_v23", clear_on_submit=True):
                    man_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-001843571-001").strip()
                    man_autor = st.text_input("Nome do Autor:", placeholder="Ex: MARCIO DE ALMEIDA SOUZA").strip().upper()
                    man_desc = st.text_input("Descrição do Material:", placeholder="Ex: 02 papelotes de cocaína").strip().upper()
                    man_qtd = st.number_input("Quantidade:", min_value=0.1, value=1.0, step=1.0)
                    man_unid = st.selectbox("Unidade:", ["UNIDADE", "KG", "G", "DUZIA", "CAIXA", "PACOTE"])
                    man_inv = st.text_input("Nº do Invólucro / Lacre:", placeholder="Ex: A230767651").strip().upper()

                    btn_man = st.form_submit_button("💾 Salvar no Supabase", type="primary", use_container_width=True)
                    if btn_man and man_reds and man_desc:
                        now_iso = datetime.datetime.now().isoformat()
                        id_bem_man = f"BEM-{man_reds}-MAN-{uuid.uuid4().hex[:4]}"
                        inv_man_final = man_inv if man_inv else "SEM LACRE (INSERÇÃO MANUAL)"
                        
                        novo_b_man = {
                            "id_bem": id_bem_man,
                            "num_reds": man_reds,
                            "autores": man_autor if man_autor else "AUTOR NÃO INFORMADO",
                            "descricao": man_desc,
                            "quantidade": man_qtd,
                            "unidade_medida": man_unid,
                            "involucro_lacre": inv_man_final,
                            "fase_destinacao": "Com Fiel Depositário / Policial",
                            "fiel_depositario_atual": nome_militar_atual,
                            "unidade_posse_atual": unidade_militar_atual,
                            "data_posse_atual": now_iso,
                            "status_tramite": "Em Custódia",
                            "data_ingestao": now_iso,
                            "dados_originais_pdf": {
                                "autores": man_autor,
                                "descricao": man_desc,
                                "quantidade": man_qtd,
                                "unidade": man_unid,
                                "involucro": inv_man_final
                            },
                            "editado_pelo_operador": False,
                            "midias_anexas": []
                        }
                        if salvar_material_supabase(novo_b_man):
                            registrar_log_supabase({
                                "data_hora": now_iso,
                                "num_reds": man_reds,
                                "bem_id": id_bem_man,
                                "acao": "INSERÇÃO MANUAL / FIEL DEPÓSITO",
                                "origem": "Inclusão Manual",
                                "unidade_origem": unidade_militar_atual,
                                "destino": nome_militar_atual,
                                "unidade_destino": unidade_militar_atual,
                                "detalhe": f"Entrada manual de {man_qtd} {man_unid} - {man_desc} (Lacre: {inv_man_final})"
                            })
                            st.success("Material cadastrado sob sua custódia!")
                            st.rerun()

    if "temp_reds_extraido" in st.session_state:
        d = st.session_state["temp_reds_extraido"]
        st.divider()
        
        with st.container(border=True):
            st.markdown(f"#### 📄 Dados da Ocorrência — REDS Nº {d['num_reds']}")
            
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Data Registro", d['data_registro'])
            with m2:
                st.metric("Data/Hora Fato", d['data_fato'])
            with m3:
                st.metric("Unidade Destino", d['unidade_jecrim'])
            with m4:
                st.metric("Itens Identificados", len(d['materiais']))

            st.markdown(f"**Natureza Principal:** **{d['natureza']}**")
            st.markdown(f"**Relator:** **{d['redator']}** | **Autor(es):** **{', '.join(d['autores'])}**")
            st.markdown(f"**Local do Fato:** {d['local']}")
            st.caption(f"**Resumo Fático:** {d['resumo_fato']}")
            st.caption(f"🔐 **Hash SHA-256 PDF:** **{d['hash_pdf']}**")

        st.markdown(f"##### 📦 Conferência de Materiais ({len(d['materiais'])} item(ns)):")

        if d["materiais"]:
            df_mats = pd.DataFrame(d["materiais"])
            
            df_editado_ing = st.data_editor(
                df_mats[["item_num", "autor", "descricao", "quantidade", "unidade", "involucro"]],
                column_config={
                    "item_num": st.column_config.TextColumn("Item", disabled=True),
                    "autor": st.column_config.TextColumn("Autor"),
                    "descricao": st.column_config.TextColumn("Descrição do Material"),
                    "quantidade": st.column_config.NumberColumn("Qtd", min_value=0.1, step=1.0),
                    "unidade": st.column_config.TextColumn("Unidade"),
                    "involucro": st.column_config.TextColumn("Nº Invólucro / Lacre")
                },
                hide_index=True,
                use_container_width=True,
                key="editor_materiais_ingestao_v23"
            )

            photos_ingestao = st.file_uploader("📷 Anexar Mídias / Documentos de Prova:", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True, key="upl_photos_ingestao_v23")

            if st.button("💾 Confirmar Ingestão e Assumir Custódia", type="primary", key="btn_conf_fiel_dep_v23", use_container_width=True):
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
                
                for idx_row, row in df_editado_ing.iterrows():
                    id_bem_unico = f"BEM-{d['num_reds']}-{row['item_num']}-{uuid.uuid4().hex[:4]}"
                    orig_item = df_mats.iloc[idx_row]
                    
                    desc_final = str(row["descricao"]).strip()
                    qtd_final = float(row["quantidade"])
                    unid_final = str(row["unidade"]).strip()
                    inv_final = str(row["involucro"]).strip()
                    autor_final = str(row["autor"]).strip()

                    foi_editado = (
                        desc_final != str(orig_item["descricao"]).strip() or
                        qtd_final != float(orig_item["quantidade"]) or
                        unid_final != str(orig_item["unidade"]).strip() or
                        inv_final != str(orig_item["involucro"]).strip() or
                        autor_final != str(orig_item["autor"]).strip()
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
                            "autores": str(orig_item["autor"]).strip(),
                            "descricao": str(orig_item["descricao"]).strip(),
                            "quantidade": float(orig_item["quantidade"]),
                            "unidade": str(orig_item["unidade"]).strip(),
                            "involucro": str(orig_item["involucro"]).strip()
                        },
                        "editado_pelo_operador": foi_editado,
                        "midias_anexas": list(midias_iniciais)
                    }
                    salvar_material_supabase(novo_bem)
                    
                    detalhe_log = f"Ingestão inicial de {qtd_final} {unid_final} - {desc_final} (Lacre: {inv_final})"
                    if foi_editado:
                        detalhe_log += f" | EDITADO NA INGESTÃO (PDF Original: {orig_item['descricao']})"

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
                st.success("Materiais cadastrados com sucesso!")
                st.rerun()

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
                    st.markdown(f"**📦 {item_meu['id_bem']}** — {item_meu['descricao']} (Lacre: **{item_meu.get('involucro_lacre')}**)")
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

def renderizar_aba_transferencias(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    st.markdown("#### 🔄 Tramitação Multi-Unidades & Aceite Parcial")
    
    unidades_disponiveis = ["TODAS AS UNIDADES", "35ª CIA PM", "21º BPM", "111ª CIA PM", "112ª CIA PM", "CREDS CENTRAL"]
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
            f3_unidade = st.selectbox("Unidade Fiel Depósito:", unidades_disponiveis, key="f3_unidade")

    meus_bens_filtrados = aplicar_filtros_bens(meus_bens, f3_reds, f3_autor, f3_militar, f3_unidade)
    
    mils_todos = st.session_state.get("lista_militares", [])
    nomes_mils_base = [f"{m.get('posto_grad')} {m.get('nome_guerra')}" for m in mils_todos] if mils_todos else ["CB MORAES", "SD VINICIUS", "SGT SILVA"]
    
    opcoes_destinatario = [n for n in nomes_mils_base if n != nome_militar_atual]
    if not opcoes_destinatario:
        opcoes_destinatario = ["CREDS CENTRAL"]

    col_tr1, col_tr2 = st.columns(2)
    with col_tr1:
        with st.form("form_transferir_material_v23"):
            st.markdown("**1. Encaminhar Material**")
            bens_disp = {f"{b['id_bem']} - {b['descricao']} (Lacre: {b.get('involucro_lacre')})": b['id_bem'] for b in meus_bens_filtrados}
            
            if bens_disp:
                bem_sel_key = st.selectbox("Selecione o Material:", list(bens_disp.keys()), key="sel_material_transf_v23")
                destinatario_sel = st.selectbox("Selecione o Destinatário:", opcoes_destinatario, key="sel_destinatario_v23")
                unidade_dest_sel = st.selectbox("Unidade Destino:", ["35ª CIA PM", "21º BPM", "111ª CIA PM", "112ª CIA PM", "CREDS CENTRAL"], key="sel_unidade_dest_v23")
                obs_transf = st.text_input("Observações do Lacre / Estado:", key="txt_obs_transf_v23")
                
                if st.form_submit_button("📤 Tramitar Material", type="primary", use_container_width=True):
                    id_bem_alvo = bens_disp[bem_sel_key]
                    bem_obj = next(b for b in all_bens_banco if b["id_bem"] == id_bem_alvo)
                    
                    now_iso = datetime.datetime.now().isoformat()
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
                            "acao": "SOLICITAÇÃO DE TRAMITAÇÃO",
                            "origem": nome_militar_atual,
                            "unidade_origem": unidade_militar_atual,
                            "destino": destinatario_sel,
                            "unidade_destino": unidade_dest_sel,
                            "detalhe": f"Encaminhado para {destinatario_sel} ({unidade_dest_sel}). Obs: {obs_transf}"
                        })
                        st.success("Tramitação registrada no Supabase!")
                        st.rerun()
            else:
                st.info("Nenhum material disponível para tramitação com os filtros aplicados.")
                st.form_submit_button("Tramitar Material", disabled=True, use_container_width=True)

    with col_tr2:
        st.markdown("**2. Aguardando Seu Aceite**")
        pendentes_para_mim = [b for b in all_bens_banco if b.get("destinatario_pendente") == nome_militar_atual and b.get("status_tramite") == "Pendente Aceite"]
        pendentes_filtrados = aplicar_filtros_bens(pendentes_para_mim, f3_reds, f3_autor, f3_militar, f3_unidade)
        
        if pendentes_filtrados:
            for idx_p, p in enumerate(pendentes_filtrados):
                tempo_aguardando = calcular_tempo_decorrido(p.get("data_envio_tramite"))
                with st.container(border=True):
                    st.markdown(f"**Material:** {p['descricao']}")
                    st.caption(f"REDS: **{p['num_reds']}** | Remetente: **{p.get('remetente_ultimo')}** | Lacre: **{p.get('involucro_lacre')}** | Tempo: **{tempo_aguardando}**")

                    c_acc1, c_acc2 = st.columns(2)
                    with c_acc1:
                        if st.button("✅ Aceitar Custódia", key=f"btn_acc_tot_{p['id_bem']}_{idx_p}", type="primary", use_container_width=True):
                            orig = p.get('remetente_ultimo') or p.get('fiel_depositario_atual')
                            orig_unid = p.get('unidade_remetente') or p.get('unidade_posse_atual')
                            now_iso = datetime.datetime.now().isoformat()
                            
                            upd_data = {
                                "fiel_depositario_atual": nome_militar_atual,
                                "unidade_posse_atual": unidade_militar_atual,
                                "data_posse_atual": now_iso,
                                "status_tramite": "Em Custódia",
                                "destinatario_pendente": None,
                                "unidade_destinatario_pendente": None,
                                "data_envio_tramite": None
                            }
                            
                            if atualizar_material_supabase(p["id_bem"], upd_data):
                                registrar_log_supabase({
                                    "data_hora": now_iso,
                                    "num_reds": p["num_reds"],
                                    "bem_id": p["id_bem"],
                                    "acao": "ACEITE DE CUSTÓDIA",
                                    "origem": orig,
                                    "unidade_origem": orig_unid,
                                    "destino": nome_militar_atual,
                                    "unidade_destino": unidade_militar_atual,
                                    "detalhe": f"Aceite de custódia confirmado por {nome_militar_atual} na unidade {unidade_militar_atual}."
                                })
                                st.success("Material recebido no Supabase!")
                                st.rerun()

                    with c_acc2:
                        if st.button("⚠️ Recusar / Divergência", key=f"btn_acc_div_{p['id_bem']}_{idx_p}", use_container_width=True):
                            abrir_modal_divergencia(p, nome_militar_atual, unidade_militar_atual)
        else:
            st.info("Nenhuma transferência pendente para você no momento.")

def renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual):
    st.markdown("#### 🏛️ Painel do Gestor CREDS-TCO e Controle Geral de Custódia")
    unidades_disponiveis = ["TODAS AS UNIDADES", "35ª CIA PM", "21º BPM", "111ª CIA PM", "112ª CIA PM", "CREDS CENTRAL"]
    
    if not eh_gestor_creds:
        st.error("🔒 **Acesso Restrito:** Apenas o Gestor do CREDS-TCO, P1 ou Comandante podem gerenciar a custódia geral.")
    else:
        with st.expander("🔍 **Filtros de Pesquisa Geral da Custódia (CREDS)**", expanded=True):
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
        else:
            st.success("✅ Nenhuma divergência pendente na unidade.")

        st.divider()
        st.markdown(f"##### 📦 Acervo Geral sob Monitoramento ({len(all_bens_filtrados)} item(ns)):")
        
        opcoes_destinacao = [
            "Com Fiel Depositário / Policial",
            "Encaminhado à Delegacia de Polícia Civil (PCMG)",
            "Encaminhado ao JECRIM / Fórum",
            "Encaminhado para Perícia Técnica",
            "Guardado no Depósito (Aguardando Autorização Judicial)",
            "Autorizada Destruição (Aguardando Descarte)",
            "DESTRUÍDO / DESCARTADO"
        ]

        for idx_creds, bem in enumerate(all_bens_filtrados):
            tempo_no_sistema = calcular_tempo_decorrido(bem.get("data_ingestao"))
            fase_atual = bem.get("fase_destinacao")
            
            with st.container(border=True):
                c_cr1, c_cr2 = st.columns([3, 2])
                with c_cr1:
                    st.markdown(f"**Código:** **{bem['id_bem']}** | REDS: **{bem['num_reds']}**")
                    st.markdown(f"Material: **{bem['descricao']}** | Autor: **{bem['autores']}**")
                    st.caption(f"Lacre: **{bem.get('involucro_lacre')}** | Custódia: **{bem['fiel_depositario_atual']}** | Tempo: **{tempo_no_sistema}**")
                    if bem.get("pa_oficio_autorizador"):
                        st.caption(f"📑 P.A. / Ofício Autorizador: **{bem['pa_oficio_autorizador']}**")

                with c_cr2:
                    index_dest = opcoes_destinacao.index(fase_atual) if fase_atual in opcoes_destinacao else 0
                    nova_dest = st.selectbox(
                        "Fase / Destinação Final:",
                        options=opcoes_destinacao,
                        index=index_dest,
                        key=f"sel_dest_creds_{bem['id_bem']}_{idx_creds}"
                    )
                    
                    e_orgao_externo = nova_dest in [
                        "Encaminhado à Delegacia de Polícia Civil (PCMG)",
                        "Encaminhado ao JECRIM / Fórum",
                        "Encaminhado para Perícia Técnica",
                        "DESTRUÍDO / DESCARTADO"
                    ]

                    input_pa_oficio = ""
                    if e_orgao_externo and nova_dest != fase_atual:
                        input_pa_oficio = st.text_input(
                            "Nº do P.A. / Ofício Autorizador:",
                            placeholder="Ex: OFÍCIO 142/2026-35CIA",
                            key=f"pa_oficio_in_{bem['id_bem']}_{idx_creds}"
                        ).strip()

                    if nova_dest != fase_atual:
                        if st.button("💾 Confirmar Alteração", key=f"btn_salvar_fase_{bem['id_bem']}_{idx_creds}", type="primary", use_container_width=True):
                            if e_orgao_externo and not input_pa_oficio:
                                st.error("Informe o número do P.A. ou Ofício autorizador.")
                            else:
                                now_iso = datetime.datetime.now().isoformat()
                                upd_data = {"fase_destinacao": nova_dest}
                                if input_pa_oficio:
                                    upd_data["pa_oficio_autorizador"] = input_pa_oficio
                                
                                if atualizar_material_supabase(bem["id_bem"], upd_data):
                                    registrar_log_supabase({
                                        "data_hora": now_iso,
                                        "num_reds": bem["num_reds"],
                                        "bem_id": bem["id_bem"],
                                        "acao": "ALTERAÇÃO DE DESTINAÇÃO FINAL",
                                        "origem": "CREDS-TCO",
                                        "unidade_origem": unidade_militar_atual,
                                        "destino": nova_dest,
                                        "unidade_destino": "Órgão Externo / CREDS",
                                        "detalhe": f"Nova Fase: {nova_dest} | P.A./Ofício: {input_pa_oficio or 'N/A'}"
                                    })
                                    st.success("Fase atualizada!")
                                    st.rerun()

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