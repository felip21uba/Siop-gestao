import streamlit as st
import pandas as pd
import datetime
import uuid
from modules.tco.parser_reds import extrair_dados_reds_pdf

def calcular_tempo_decorrido(str_data_hora):
    if not str_data_hora or str_data_hora in ["N/A", "Data N/I", "N/I"]:
        return "N/A"
    try:
        dt_evento = datetime.datetime.strptime(str_data_hora, "%d/%m/%Y %H:%M")
        delta = datetime.datetime.now() - dt_evento
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

def aplicar_filtros_bens(lista_bens, reds_q="", autor_q="", militar_q="", data_q=None):
    resultado = []
    for b in lista_bens:
        if reds_q and reds_q.lower() not in str(b.get("num_reds", "")).lower():
            continue
        if autor_q and autor_q.lower() not in str(b.get("autores", "")).lower():
            continue
        militares_vinculados = f"{b.get('fiel_depositario_atual', '')} {b.get('remetente_ultimo', '')} {b.get('destinatario_pendente', '')}"
        if militar_q and militar_q.lower() not in militares_vinculados.lower():
            continue
        if data_q:
            data_str = data_q.strftime("%d/%m/%Y")
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
            data_str = data_q.strftime("%d/%m/%Y")
            if data_str not in str(l.get("data_hora", "")):
                continue
        resultado.append(l)
    return resultado

@st.dialog("✏️ Editar e Comparar Dados do Material sob Custódia")
def abrir_modal_edicao_material(bem_obj, nome_militar_atual):
    st.markdown(f"**REDS:** `{bem_obj['num_reds']}` | **Código Bem:** `{bem_obj['id_bem']}`")
    
    orig = bem_obj.get("dados_originais_pdf", {})
    st.info("🔍 **Dados Originais Extraídos do PDF:**\n\n"
            f"- **Descrição PDF:** {orig.get('descricao', 'N/A')}\n"
            f"- **Qtd PDF:** {orig.get('quantidade', '1.0')} {orig.get('unidade', 'UN')}\n"
            f"- **Lacre PDF:** {orig.get('involucro', 'N/A')}\n"
            f"- **Autor PDF:** {orig.get('autores', 'N/A')}")
    st.divider()

    with st.form("form_editar_material_custodia_v14", clear_on_submit=False):
        novo_autor = st.text_input("Autor Vinculado (Editável):", value=bem_obj.get("autores", "")).strip().upper()
        nova_desc = st.text_input("Descrição do Material (Editável):", value=bem_obj.get("descricao", "")).strip().upper()
        col_ed1, col_ed2 = st.columns(2)
        with col_ed1:
            nova_qtd = st.number_input("Quantidade:", min_value=0.1, value=float(bem_obj.get("quantidade", 1.0)), step=1.0)
        with col_ed2:
            nova_unid = st.text_input("Unidade:", value=bem_obj.get("unidade", "UNIDADE")).strip().upper()
            
        novo_inv = st.text_input("Nº do Invólucro / Lacre (Editável):", value=bem_obj.get("involucro", "")).strip().upper()
        motivo_edicao = st.text_input("Motivo/Justificativa da Alteração:", placeholder="Ex: Ajuste no lacre verificado na conferência física").strip()
        
        if st.form_submit_button("💾 Salvar Alterações e Atualizar Tramitação", type="primary", use_container_width=True):
            if not nova_desc or len(motivo_edicao) < 5:
                st.error("A descrição e uma justificativa com no mínimo 5 caracteres são obrigatórias.")
            else:
                now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                
                detalhes_alteracao = (
                    f"EDIÇÃO OPERADOR ({nome_militar_atual}) | MOTIVO: {motivo_edicao} | "
                    f"ALTERAÇÕES: [Desc: '{bem_obj['descricao']}' ➔ '{nova_desc}'] "
                    f"[Qtd: '{bem_obj['quantidade']} {bem_obj['unidade']}' ➔ '{nova_qtd} {nova_unid}'] "
                    f"[Lacre: '{bem_obj['involucro']}' ➔ '{novo_inv}'] "
                    f"[Autor: '{bem_obj['autores']}' ➔ '{novo_autor}']"
                )
                
                bem_obj["autores"] = novo_autor
                bem_obj["descricao"] = nova_desc
                bem_obj["quantidade"] = nova_qtd
                bem_obj["unidade"] = nova_unid
                bem_obj["involucro"] = novo_inv
                bem_obj["editado_pelo_operador"] = True
                bem_obj["ultima_edicao"] = {"por": nome_militar_atual, "data": now_str, "motivo": motivo_edicao}
                
                st.session_state["custodia_logs"].append({
                    "data_hora": now_str,
                    "num_reds": bem_obj["num_reds"],
                    "bem_id": bem_obj["id_bem"],
                    "acao": "EDIÇÃO DE DADOS PELO OPERADOR",
                    "origem": nome_militar_atual,
                    "destino": nome_militar_atual,
                    "detalhe": detalhes_alteracao
                })
                st.success("Dados alterados! A tramitação e o painel do CREDS foram atualizados com a versão editada.")
                st.rerun()

@st.dialog("🚨 Registrar Divergência / Recusa de Custódia")
def abrir_modal_divergencia(bem_obj, nome_militar_atual):
    st.warning(f"Material: **{bem_obj['descricao']}** (REDS: {bem_obj['num_reds']})")
    
    motivo_sel = st.selectbox(
        "Selecione o Motivo Principal da Divergência:",
        [
            "Invólucro / Lacre Violado ou Rompido",
            "Quantidade do Material Menor que a Declarada no REDS",
            "Material Avariado / Danificado",
            "Objeto Incompatível com a Descrição",
            "Material Ausente / Não Entregue pelo Remetente",
            "Outro Motivo Operacional"
        ],
        key=f"sel_motivo_div_{bem_obj['id_bem']}"
    )
    
    justificativa_txt = st.text_area(
        "Justificativa Detalhada (Obrigatório):",
        placeholder="Descreva a divergência observada durante a conferência física...",
        height=120,
        key=f"txt_just_div_{bem_obj['id_bem']}"
    )
    
    if st.button("🚨 Confirmar Divergência e Emitir Alerta P1/CREDS", type="primary", use_container_width=True, key=f"btn_conf_div_{bem_obj['id_bem']}"):
        if not justificativa_txt or len(justificativa_txt.strip()) < 10:
            st.error("⚠️ A justificativa detalhada é obrigatória (mínimo de 10 caracteres).")
        else:
            now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            origem_remetente = bem_obj["fiel_depositario_atual"]
            
            bem_obj["status_tramite"] = "Divergência Registrada"
            bem_obj["dados_divergencia"] = {
                "motivo": motivo_sel,
                "justificativa": justificativa_txt.strip(),
                "registrado_por": nome_militar_atual,
                "data_hora": now_str,
                "remetente_origem": origem_remetente
            }
            
            st.session_state["custodia_logs"].append({
                "data_hora": now_str,
                "num_reds": bem_obj["num_reds"],
                "bem_id": bem_obj["id_bem"],
                "acao": "REGISTRO DE DIVERGÊNCIA / RECUSA",
                "origem": origem_remetente,
                "destino": nome_militar_atual,
                "detalhe": f"MOTIVO: {motivo_sel} | JUSTIFICATIVA: {justificativa_txt.strip()}"
            })
            
            st.success("Divergência registrada! O material foi travado em alerta e a P1/CREDS notificada.")
            st.rerun()

def renderizar_modulo_tco():
    st.title("📋 Custódia de Materiais TCO / JECRIM & Cadeia de Custódia")
    st.caption("Ingestão baseada em recibo oficial, identificação inteligente de invólucro/lacre, transferência auditada e gestão do CREDS.")
    st.divider()

    usr_logado = st.session_state.get("usuario_dados", {})
    nome_militar_atual = f"{usr_logado.get('cargo_funcao', 'CB PM')} {usr_logado.get('nome_guerra', 'OPERADOR')}"
    perfil_usuario = str(usr_logado.get("nivel_acesso", "TROPA")).upper()
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    
    eh_gestor_creds = "PROGRAMADOR" in cargo_str or "ADMIN" in perfil_usuario or "P1" in perfil_usuario or "COMANDANTE" in cargo_str or "CREDS" in perfil_usuario

    if "custodia_bens" not in st.session_state:
        st.session_state["custodia_bens"] = []
    if "custodia_logs" not in st.session_state:
        st.session_state["custodia_logs"] = []

    aba_ingestao, aba_meus_bens, aba_transferir, aba_creds, aba_logs = st.tabs([
        "📥 1. Ingestão REDS (PDF)",
        "🎒 2. Meus Materiais sob Custódia",
        "🔄 3. Transferência & Aceite / Prazos",
        "🏛️ 4. Painel CREDS-TCO (Gestor Geral)",
        "📜 5. Trilha Imutável de Auditoria"
    ])

    # =========================================================================
    # ABA 1: INGESTÃO REDS
    # =========================================================================
    with aba_ingestao:
        col_ing1, col_ing2 = st.columns([2.5, 1.5])
        
        with col_ing1:
            st.markdown("#### Importar Boletim de Ocorrência (REDS)")
            arquivo_pdf = st.file_uploader("Selecione o arquivo PDF do REDS:", type=["pdf"], key="uploader_reds_pdf_v14")

            if arquivo_pdf is not None:
                if st.button("⚡ Processar e Ler Recibo JECRIM", type="primary", key="btn_processar_pdf_recibo_v14"):
                    with st.spinner("Mapeando recibo do JECRIM, relator e invólucro do material..."):
                        dados_reds = extrair_dados_reds_pdf(arquivo_pdf)
                        st.session_state["temp_reds_extraido"] = dados_reds
                        st.success("Leitura concluída!")

        with col_ing2:
            st.markdown("#### ➕ Inserção Manual de Material")
            with st.popover("📝 Cadastrar Material Avulso / Manual", use_container_width=True):
                with st.form("form_material_manual_v14", clear_on_submit=True):
                    man_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-001843571-001").strip()
                    man_autor = st.text_input("Nome do Autor do Fato:", placeholder="Ex: MARCIO DE ALMEIDA SOUZA").strip().upper()
                    man_desc = st.text_input("Descrição do Material:", placeholder="Ex: 02 papelotes de cocaína").strip().upper()
                    man_qtd = st.number_input("Quantidade:", min_value=0.1, value=1.0, step=1.0)
                    man_unid = st.selectbox("Unidade:", ["UNIDADE", "KG", "G", "DUZIA", "CAIXA", "PACOTE"])
                    man_inv = st.text_input("Nº do Invólucro / Lacre:", placeholder="Ex: A230767651").strip().upper()
                    
                    btn_man = st.form_submit_button("💾 Salvar na Minha Custódia", type="primary", use_container_width=True)
                    if btn_man and man_reds and man_desc:
                        now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                        id_bem_man = f"BEM-{man_reds}-MAN-{uuid.uuid4().hex[:4]}"
                        inv_man_final = man_inv if man_inv else "SEM LACRE (INSERÇÃO MANUAL)"
                        
                        novo_b_man = {
                            "id_bem": id_bem_man,
                            "num_reds": man_reds,
                            "autores": man_autor if man_autor else "AUTOR NÃO INFORMADO",
                            "descricao": man_desc,
                            "quantidade": man_qtd,
                            "unidade": man_unid,
                            "involucro": inv_man_final,
                            "fase_destinacao": "Com Fiel Depositário / Policial",
                            "fiel_depositario_atual": nome_militar_atual,
                            "data_posse_atual": now_str,
                            "status_tramite": "Em Custódia",
                            "data_ingestao": now_str,
                            "dados_originais_pdf": {
                                "autores": man_autor,
                                "descricao": man_desc,
                                "quantidade": man_qtd,
                                "unidade": man_unid,
                                "involucro": inv_man_final
                            },
                            "editado_pelo_operador": False,
                            "remetente_ultimo": None,
                            "destinatario_pendente": None,
                            "data_envio_tramite": None,
                            "obs_tramite": None,
                            "dados_divergencia": None
                        }
                        st.session_state["custodia_bens"].append(novo_b_man)
                        st.session_state["custodia_logs"].append({
                            "data_hora": now_str,
                            "num_reds": man_reds,
                            "bem_id": id_bem_man,
                            "acao": "INSERÇÃO MANUAL / FIEL DEPÓSITO",
                            "origem": "Inclusão Manual pelo Operador",
                            "destino": nome_militar_atual,
                            "detalhe": f"Entrada manual de {man_qtd} {man_unid} - {man_desc} (Lacre: {inv_man_final})"
                        })
                        st.success("Material cadastrado manualmente sob sua custódia!")
                        st.rerun()

        if "temp_reds_extraido" in st.session_state:
            d = st.session_state["temp_reds_extraido"]
            st.divider()
            
            with st.container(border=True):
                st.markdown(f"### 📄 REDS Nº {d['num_reds']}")
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.markdown(f"**📅 Data Registro:** `{d['data_registro']}`")
                with c2: st.markdown(f"**⏱️ Data/Hora Fato:** `{d['data_fato']}`")
                with c3: st.markdown(f"**🚨 Natureza Principal:** `{d['natureza']}`")
                with c4: st.markdown(f"**🏛️ Destino:** `{d['unidade_jecrim']}`")
                
                autores_str = ", ".join(d["autores"])
                st.markdown(f"✍️ **Militar Relator:** `{d['redator']}`")
                st.markdown(f"👤 **Autor(es) no Recibo JECRIM:** `{autores_str}`")
                st.markdown(f"📍 **Local:** {d['local']}")
                st.markdown(f"📝 **Resumo Fático:** *{d['resumo_fato']}*")

            st.markdown(f"##### 📦 Materiais Transcritos do REDS ({len(d['materiais'])} item(ns) identificado(s)):")
            st.caption("✏️ **Tabela Editável:** Você pode alterar qualquer dado do material diretamente abaixo antes de confirmar o recebimento.")

            if d["materiais"]:
                df_mats = pd.DataFrame(d["materiais"])
                
                df_editado_ing = st.data_editor(
                    df_mats[["item_num", "autor", "descricao", "quantidade", "unidade", "involucro"]],
                    column_config={
                        "item_num": st.column_config.TextColumn("Item", disabled=True),
                        "autor": st.column_config.TextColumn("Autor (via ENVOLV. NR)"),
                        "descricao": st.column_config.TextColumn("Descrição do Material"),
                        "quantidade": st.column_config.NumberColumn("Qtd", min_value=0.1, step=1.0),
                        "unidade": st.column_config.TextColumn("Unidade"),
                        "involucro": st.column_config.TextColumn("Nº Invólucro / Lacre")
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_materiais_ingestao_v14"
                )

                if st.button("💾 Confirmar Ingestão e Assumir Fiel Depósito", type="primary", key="btn_conf_fiel_dep_v14"):
                    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    
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
                            "unidade": unid_final,
                            "involucro": inv_final,
                            "fase_destinacao": "Com Fiel Depositário / Policial",
                            "fiel_depositario_atual": nome_militar_atual,
                            "data_posse_atual": now_str,
                            "status_tramite": "Em Custódia",
                            "data_ingestao": now_str,
                            "dados_originais_pdf": {
                                "autores": str(orig_item["autor"]).strip(),
                                "descricao": str(orig_item["descricao"]).strip(),
                                "quantidade": float(orig_item["quantidade"]),
                                "unidade": str(orig_item["unidade"]).strip(),
                                "involucro": str(orig_item["involucro"]).strip()
                            },
                            "editado_pelo_operador": foi_editado,
                            "remetente_ultimo": None,
                            "destinatario_pendente": None,
                            "data_envio_tramite": None,
                            "obs_tramite": None,
                            "dados_divergencia": None
                        }
                        st.session_state["custodia_bens"].append(novo_bem)
                        
                        detalhe_log = f"Carga inicial de {qtd_final} {unid_final} - {desc_final} (Lacre: {inv_final} | Autor: {autor_final})"
                        if foi_editado:
                            detalhe_log += f" | ⚠️ EDITADO NA INGESTÃO (PDF Original: {orig_item['descricao']} - Lacre: {orig_item['involucro']})"

                        st.session_state["custodia_logs"].append({
                            "data_hora": now_str,
                            "num_reds": d["num_reds"],
                            "bem_id": id_bem_unico,
                            "acao": "INGESTÃO / FIEL DEPÓSITO INICIAL",
                            "origem": f"REDS JECRIM (Relator: {d['redator']})",
                            "destino": nome_militar_atual,
                            "detalhe": detalhe_log
                        })

                    del st.session_state["temp_reds_extraido"]
                    st.success("Materiais vinculados à sua custódia com sucesso!")
                    st.rerun()
            else:
                st.warning("Nenhum material destinado ao JECRIM foi identificado no recibo deste REDS.")

    # =========================================================================
    # ABA 2: MEUS MATERIAIS SOB CUSTÓDIA
    # =========================================================================
    with aba_meus_bens:
        st.markdown(f"#### 🎒 Materiais Atualmente sob Custódia de: `{nome_militar_atual}`")
        meus_bens = [b for b in st.session_state["custodia_bens"] if b["fiel_depositario_atual"] == nome_militar_atual and b["status_tramite"] == "Em Custódia"]
        
        if meus_bens:
            for mb in meus_bens:
                mb["tempo_posse"] = calcular_tempo_decorrido(mb.get("data_posse_atual"))
                mb["tempo_total"] = calcular_tempo_decorrido(mb.get("data_ingestao"))
                mb["status_edicao"] = "✏️ Editado" if mb.get("editado_pelo_operador") else "📄 Original PDF"

            df_mb = pd.DataFrame(meus_bens)
            st.dataframe(
                df_mb[["id_bem", "num_reds", "autores", "descricao", "quantidade", "unidade", "involucro", "data_posse_atual", "tempo_posse", "status_edicao"]],
                column_config={
                    "id_bem": "Código Bem",
                    "num_reds": "Nº REDS",
                    "autores": "Autor(es)",
                    "descricao": "Descrição",
                    "quantidade": "Qtd",
                    "unidade": "Unid",
                    "involucro": "Nº Invólucro / Lacre",
                    "data_posse_atual": "Posse Desde",
                    "tempo_posse": "Tempo na Posse",
                    "status_edicao": "Origem Dados"
                },
                hide_index=True, use_container_width=True
            )
            
            st.markdown("##### ⚙️ Ações e Edição de Dados Pessoais:")
            for idx_m, item_meu in enumerate(meus_bens):
                col_m1, col_m2 = st.columns([4, 1])
                with col_m1:
                    lbl_ed = " [✏️ Alterado pelo Operador]" if item_meu.get("editado_pelo_operador") else ""
                    st.caption(f"📦 **{item_meu['id_bem']}** - {item_meu['descricao']} (Lacre: `{item_meu['involucro']}`){lbl_ed}")
                with col_m2:
                    if st.button("✏️ Editar Material", key=f"btn_edit_meu_bem_{item_meu['id_bem']}_{idx_m}", type="secondary", use_container_width=True):
                        abrir_modal_edicao_material(item_meu, nome_militar_atual)
        else:
            st.info("Você não possui nenhum material sob sua custódia no momento.")

    # =========================================================================
    # ABA 3: TRANSFERÊNCIA E FILTROS DE PESQUISA
    # =========================================================================
    with aba_transferir:
        st.markdown("#### 🔄 Tramitação de Materiais & Conferência de Recebimento")
        
        with st.expander("🔍 **Filtros de Pesquisa na Tramitação**", expanded=True):
            f3_col1, f3_col2, f3_col3, f3_col4 = st.columns(4)
            with f3_col1:
                f3_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-000484967", key="f3_reds").strip()
            with f3_col2:
                f3_autor = st.text_input("Nome do Autor:", placeholder="Ex: DOUGLAS", key="f3_autor").strip()
            with f3_col3:
                f3_militar = st.text_input("Militar / Custodiante:", placeholder="Ex: ALEXANDRINO", key="f3_militar").strip()
            with f3_col4:
                usar_f3_data = st.checkbox("Filtrar por Data", key="f3_chk_data")
                f3_data = st.date_input("Data do Evento/Ingestão:", datetime.date.today(), key="f3_data") if usar_f3_data else None

        meus_bens_filtrados = aplicar_filtros_bens(meus_bens, f3_reds, f3_autor, f3_militar, f3_data)
        
        mils_todos = st.session_state.get("lista_militares", [])
        nomes_mils = [f"{m.get('posto_grad')} {m.get('nome_guerra')}" for m in mils_todos] if mils_todos else ["CB MORAES", "SD VINICIUS", "CREDS-TCO SEÇÃO"]

        col_tr1, col_tr2 = st.columns(2)
        with col_tr1:
            with st.form("form_transferir_material_v14"):
                st.markdown("**1. Enviar Material para Outro Militar / CREDS**")
                bens_disp = {f"{b['id_bem']} - {b['descricao']} (Lacre: {b['involucro']})": b['id_bem'] for b in meus_bens_filtrados}
                
                if bens_disp:
                    bem_sel_key = st.selectbox("Selecione o Material para Tramitar:", list(bens_disp.keys()), key="sel_material_transf_v14")
                    destinatario_sel = st.selectbox("Selecione o Destinatário:", [n for n in nomes_mils if n != nome_militar_atual], key="sel_destinatario_v14")
                    obs_transf = st.text_input("Observação / Estado do Lacre:", key="txt_obs_transf_v14")
                    
                    if st.form_submit_button("📤 Tramitar Material", type="primary"):
                        id_bem_alvo = bens_disp[bem_sel_key]
                        bem_obj = next(b for b in st.session_state["custodia_bens"] if b["id_bem"] == id_bem_alvo)
                        
                        now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                        bem_obj["status_tramite"] = "Pendente Aceite"
                        bem_obj["remetente_ultimo"] = nome_militar_atual
                        bem_obj["destinatario_pendente"] = destinatario_sel
                        bem_obj["data_envio_tramite"] = now_str
                        bem_obj["obs_tramite"] = obs_transf
                        
                        st.session_state["custodia_logs"].append({
                            "data_hora": now_str,
                            "num_reds": bem_obj["num_reds"],
                            "bem_id": id_bem_alvo,
                            "acao": "SOLICITAÇÃO DE TRAMITAÇÃO",
                            "origem": nome_militar_atual,
                            "destino": destinatario_sel,
                            "detalhe": f"Encaminhado para {destinatario_sel} em {now_str}. Obs: {obs_transf}"
                        })
                        st.success("Tramitação iniciada! Aguardando conferência do destinatário.")
                        st.rerun()
                else:
                    st.caption("Nenhum material sob sua custódia atende aos filtros atuais para transferência.")
                    st.form_submit_button("Tramitar Material", disabled=True)

        with col_tr2:
            st.markdown("**2. Materiais Aguardando SEU Aceite**")
            pendentes_para_mim = [b for b in st.session_state["custodia_bens"] if b.get("destinatario_pendente") == nome_militar_atual and b["status_tramite"] == "Pendente Aceite"]
            pendentes_filtrados = aplicar_filtros_bens(pendentes_para_mim, f3_reds, f3_autor, f3_militar, f3_data)
            
            if pendentes_filtrados:
                for idx_p, p in enumerate(pendentes_filtrados):
                    tempo_aguardando = calcular_tempo_decorrido(p.get("data_envio_tramite"))
                    with st.container(border=True):
                        st.markdown(f"**Material:** {p['descricao']}")
                        st.caption(f"REDS: {p['num_reds']} | **Remetente:** `{p['remetente_ultimo']}` em `{p['data_envio_tramite']}`")
                        st.caption(f"⏱️ **Aguardando confirmação há:** `{tempo_aguardando}` | **Lacre:** `{p['involucro']}`")
                        if p.get("editado_pelo_operador"):
                            st.warning("⚠️ **Material com alterações feitas pelo remetente.**")
                        
                        c_acc1, c_acc2 = st.columns(2)
                        with c_acc1:
                            if st.button("✅ Aceite Total", key=f"btn_acc_tot_{p['id_bem']}_{idx_p}", type="primary"):
                                orig = p['remetente_ultimo'] or p['fiel_depositario_atual']
                                now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                                
                                p['fiel_depositario_atual'] = nome_militar_atual
                                p['data_posse_atual'] = now_str
                                p['status_tramite'] = "Em Custódia"
                                p['destinatario_pendente'] = None
                                p['data_envio_tramite'] = None
                                
                                st.session_state["custodia_logs"].append({
                                    "data_hora": now_str,
                                    "num_reds": p["num_reds"],
                                    "bem_id": p["id_bem"],
                                    "acao": "ACEITE TOTAL EFETUADO",
                                    "origem": orig,
                                    "destino": nome_militar_atual,
                                    "detalhe": f"Transferência aceita por {nome_militar_atual} em {now_str}."
                                })
                                st.success("Material recebido com sucesso!")
                                st.rerun()

                        with c_acc2:
                            if st.button("⚠️ Recusar / Divergência", key=f"btn_acc_div_{p['id_bem']}_{idx_p}"):
                                abrir_modal_divergencia(p, nome_militar_atual)
            else:
                st.info("Nenhuma transferência pendente atende aos filtros de pesquisa.")

    # =========================================================================
    # ABA 4: PAINEL CREDS-TCO
    # =========================================================================
    with aba_creds:
        st.markdown("#### 🏛️ Painel do Gestor CREDS-TCO e Controle de Custódia Geral")
        
        if not eh_gestor_creds:
            st.error("🔒 **Acesso Restrito:** Apenas o Gestor do CREDS-TCO, P1 ou Comandante podem gerenciar a custódia geral.")
        else:
            all_bens = st.session_state["custodia_bens"]
            
            with st.expander("🔍 **Filtros de Pesquisa Geral da Custódia (CREDS)**", expanded=True):
                f4_col1, f4_col2, f4_col3, f4_col4 = st.columns(4)
                with f4_col1:
                    f4_reds = st.text_input("Filtrar Nº REDS:", placeholder="Ex: 2026-000484967", key="f4_reds").strip()
                with f4_col2:
                    f4_autor = st.text_input("Filtrar Autor:", placeholder="Ex: DOUGLAS", key="f4_autor").strip()
                with f4_col3:
                    f4_militar = st.text_input("Filtrar Militar Responsável:", placeholder="Ex: ALEXANDRINO", key="f4_militar").strip()
                with f4_col4:
                    usar_f4_data = st.checkbox("Filtrar por Data ", key="f4_chk_data")
                    f4_data = st.date_input("Data Ingestão/Posse:", datetime.date.today(), key="f4_data") if usar_f4_data else None

            all_bens_filtrados = aplicar_filtros_bens(all_bens, f4_reds, f4_autor, f4_militar, f4_data)

            # Alertas de Divergência
            bens_divergentes = [b for b in all_bens_filtrados if b.get("status_tramite") == "Divergência Registrada"]
            if bens_divergentes:
                st.error(f"🚨 **ALERTA CRÍTICO:** Existem {len(bens_divergentes)} material(is) com divergência registrada aguardando apuração!")
                for idx_div, bd in enumerate(bens_divergentes):
                    div = bd.get("dados_divergencia", {})
                    with st.expander(f"⚠️ DIVERGÊNCIA: {bd['id_bem']} (REDS: {bd['num_reds']})", expanded=True):
                        st.markdown(f"**Material:** {bd['descricao']}")
                        st.markdown(f"**Remetente:** {div.get('remetente_origem')} ➔ **Recusado por:** {div.get('registrado_por')}")
                        st.markdown(f"**Motivo:** `{div.get('motivo')}`")
                        st.error(f"**Justificativa do Policial:** {div.get('justificativa')}")
                        
                        if st.button("✅ Marcar Divergência como Resolvida", key=f"btn_res_div_{bd['id_bem']}_{idx_div}"):
                            bd["status_tramite"] = "Em Custódia"
                            now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            st.session_state["custodia_logs"].append({
                                "data_hora": now_str,
                                "num_reds": bd["num_reds"],
                                "bem_id": bd["id_bem"],
                                "acao": "RESOLUÇÃO DE DIVERGÊNCIA",
                                "origem": "CREDS-TCO",
                                "destino": bd["fiel_depositario_atual"],
                                "detalhe": "Divergência apurada e resolvida pelo Gestor do CREDS."
                            })
                            st.success("Divergência marcada como resolvida!")
                            st.rerun()
            else:
                st.success("✅ Nenhuma divergência pendente de apuração na unidade.")

            st.divider()
            st.markdown(f"##### 📦 Acervo Encontrado ({len(all_bens_filtrados)} item(ns)):")
            
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
                tempo_na_posse = calcular_tempo_decorrido(bem.get("data_posse_atual"))
                tempo_no_sistema = calcular_tempo_decorrido(bem.get("data_ingestao"))
                orig_pdf = bem.get("dados_originais_pdf", {})
                
                with st.container(border=True):
                    c_cr1, c_cr2, c_cr3 = st.columns([2.5, 2.5, 2])
                    
                    with c_cr1:
                        st.markdown(f"**Código:** `{bem['id_bem']}` | REDS: `{bem['num_reds']}`")
                        st.markdown(f"**Material Tramitando:** {bem['descricao']}")
                        st.caption(f"👤 Autor: **{bem['autores']}** | Lacre: **{bem['involucro']}**")
                        
                        if bem.get("editado_pelo_operador"):
                            st.warning(
                                "✏️ **DADOS ALTERADOS PELO OPERADOR:**\n\n"
                                f"- **Descrição Original (PDF):** {orig_pdf.get('descricao')}\n"
                                f"- **Lacre Original (PDF):** {orig_pdf.get('involucro')}\n"
                                f"- **Autor Original (PDF):** {orig_pdf.get('autores')}\n"
                                f"- **Qtd Original (PDF):** {orig_pdf.get('quantidade')} {orig_pdf.get('unidade')}"
                            )
                        else:
                            st.caption("📄 *Dados fiéis ao PDF original (sem alterações).*")
                            
                        st.caption(f"⏱️ **Tempo no Sistema:** `{tempo_no_sistema}` (Desde {bem.get('data_ingestao', 'N/I')})")
                    
                    with c_cr2:
                        if bem.get("status_tramite") == "Pendente Aceite":
                            tempo_tramite = calcular_tempo_decorrido(bem.get("data_envio_tramite"))
                            st.warning("🟡 **PROCESSO DE ACEITE PENDENTE**")
                            st.markdown(f"**Enviado por:** {bem.get('remetente_ultimo')}")
                            st.markdown(f"**Aguardando Aceite de:** {bem.get('destinatario_pendente')}")
                            st.caption(f"📅 Envio: {bem.get('data_envio_tramite')} | ⏱️ Em trânsito há: `{tempo_tramite}`")
                        
                        elif bem.get("status_tramite") == "Divergência Registrada":
                            st.error("🚨 **EM DIVERGÊNCIA**")
                            st.markdown(f"**Possuidor:** {bem['fiel_depositario_atual']}")
                        
                        else:
                            st.success("🟢 **EM POSSE CONFIRMADA**")
                            st.markdown(f"**Fiel Depositário:** `{bem['fiel_depositario_atual']}`")
                            st.caption(f"📅 Aceite: {bem.get('data_posse_atual', 'N/I')} | ⏱️ Na posse há: `{tempo_na_posse}`")

                    with c_cr3:
                        nova_dest = st.selectbox(
                            "Destinação Final (CREDS):",
                            options=opcoes_destinacao,
                            index=opcoes_destinacao.index(bem["fase_destinacao"]) if bem["fase_destinacao"] in opcoes_destinacao else 0,
                            key=f"sel_dest_creds_{bem['id_bem']}_{idx_creds}"
                        )
                        if nova_dest != bem["fase_destinacao"]:
                            bem["fase_destinacao"] = nova_dest
                            now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            st.session_state["custodia_logs"].append({
                                "data_hora": now_str,
                                "num_reds": bem["num_reds"],
                                "bem_id": bem["id_bem"],
                                "acao": "ALTERAÇÃO DE DESTINAÇÃO FINAL",
                                "origem": "CREDS-TCO",
                                "destino": nova_dest,
                                "detalhe": f"Fase alterada para: {nova_dest} por Gestor CREDS"
                            })
                            st.success(f"Destinação atualizada!")
                            st.rerun()

    # =========================================================================
    # ABA 5: AUDITORIA IMUTÁVEL
    # =========================================================================
    with aba_logs:
        st.markdown("#### 📜 Trilha de Auditoria Imutável da Custódia")
        
        with st.expander("🔍 **Filtros de Pesquisa na Trilha de Auditoria**", expanded=True):
            f5_col1, f5_col2, f5_col3, f5_col4 = st.columns(4)
            with f5_col1:
                f5_reds = st.text_input("REDS:", placeholder="Ex: 2026-000484967", key="f5_reds").strip()
            with f5_col2:
                f5_busca = st.text_input("Palavra-chave / Detalhes:", placeholder="Ex: Edição, Maconha, Lacre", key="f5_busca").strip()
            with f5_col3:
                f5_militar = st.text_input("Militar Envolvido:", placeholder="Ex: ALEXANDRINO", key="f5_militar").strip()
            with f5_col4:
                usar_f5_data = st.checkbox("Filtrar por Data  ", key="f5_chk_data")
                f5_data = st.date_input("Data do Evento:", datetime.date.today(), key="f5_data") if usar_f5_data else None

        logs_todos = st.session_state["custodia_logs"]
        logs_filtrados = aplicar_filtros_logs(logs_todos, f5_reds, f5_busca, f5_militar, f5_data)
        
        if logs_filtrados:
            df_l = pd.DataFrame(logs_filtrados)
            st.dataframe(df_l, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum registro encontrado com os parâmetros de pesquisa selecionados.")