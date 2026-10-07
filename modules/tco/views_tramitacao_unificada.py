import streamlit as st
import pandas as pd
import datetime
from core.database import supabase, carregar_militares_supabase
from core.permissions import usuario_eh_gestor_creds
from modules.tco.database import registrar_log_supabase, atualizar_material_supabase
from modules.tco.storage import upload_midia_supabase
from utils.file_validator import sanitizar_nome_arquivo


def extrair_unidades_creds_banco(unidade_militar_atual=""):
    orgaos_externos = [
        "DELEGACIA DE POLÍCIA CIVIL (PCMG)",
        "PODER JUDICIÁRIO / TRIBUNAL DE JUSTIÇA (JECRIM)",
        "PERÍCIA TÉCNICA / PERÍCIA OFICIAL",
        "MINISTÉRIO PÚBLICO (MPMG)",
        "OUTRO ÓRGÃO EXTERNO (ESPECIFICAR NAS OBSERVAÇÕES)"
    ]

    unidades_set = set()

    if supabase:
        try:
            res = supabase.table("usuarios").select("unidade").execute()
            if res and res.data:
                for row in res.data:
                    unid_raw = str(row.get("unidade") or "").strip().upper()
                    if unid_raw and unid_raw != "NONE":
                        fragmentos = [f.strip() for f in unid_raw.split("/") if f.strip()]
                        for frag in fragmentos:
                            if not frag.startswith("CREDS"):
                                unidades_set.add(f"CREDS {frag}")
                            else:
                                unidades_set.add(frag)
        except Exception as e:
            print(f"Aviso ao consultar unidades para o CREDS: {e}")

    if unidade_militar_atual:
        unid_op = str(unidade_militar_atual).strip().upper()
        fragmentos_op = [f.strip() for f in unid_op.split("/") if f.strip()]
        for frag in fragmentos_op:
            if not frag.startswith("CREDS"):
                unidades_set.add(f"CREDS {frag}")
            else:
                unidades_set.add(frag)

    if not unidades_set:
        unidades_set.add("CREDS 35ª CIA PM")
        unidades_set.add("CREDS 111ª CIA PM")
        unidades_set.add("CREDS 285ª CIA TM")
        unidades_set.add("CREDS 21º BPM")

    return sorted(list(unidades_set)) + orgaos_externos


def renderizar_aba_custodia_tramitacao_unificada(all_bens, nome_militar_atual, unidade_militar_atual):
    usr_logado = st.session_state.get("usuario_dados", {})
    num_pm_logado = str(usr_logado.get("usuario_login") or usr_logado.get("usuario") or "").strip().upper()

    eh_gestor_creds = usuario_eh_gestor_creds(usr_logado) or any(
        p in str(usr_logado.get("perfil_creds", "")).upper() 
        for p in ["GESTOR", "ADMIN", "PROGRAMADOR"]
    )

    if "subaba_tramitacao_ativa" not in st.session_state:
        st.session_state["subaba_tramitacao_ativa"] = "TRAMITAR"

    aba_atual = st.session_state["subaba_tramitacao_ativa"]

    st.markdown("""
    <style>
    .painel-tramitacao-container {
        background: linear-gradient(135deg, #7d6539 0%, #63502c 100%);
        border: 2px solid #c5a059;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 18px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.45);
    }
    .painel-tramitacao-titulo {
        font-size: 1.25rem !important;
        font-weight: 800 !important;
        color: #ffffff !important;
        margin: 0 0 4px 0 !important;
        display: flex;
        align-items: center;
        gap: 8px;
        text-shadow: 0 1px 2px rgba(0,0,0,0.4);
    }
    .painel-tramitacao-subtitulo {
        font-size: 0.84rem;
        color: #f5ebe0;
        margin-bottom: 14px;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("""
        <div class="painel-tramitacao-container">
            <div class="painel-tramitacao-titulo">
                🎒 Custódia Física & Tramitação Unificada
            </div>
            <div class="painel-tramitacao-subtitulo">
                Gerencie os bens sob sua posse, realize remessas para policiais/órgãos e consulte o histórico imutável das movimentações.
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_btn1, col_btn2, col_btn3 = st.columns(3)

        with col_btn1:
            btn_tipo1 = "primary" if aba_atual == "TRAMITAR" else "secondary"
            if st.button("📤 Tramitar Materiais / REDS", key="nav_btn_tramitar_v9", type=btn_tipo1, use_container_width=True):
                st.session_state["subaba_tramitacao_ativa"] = "TRAMITAR"
                st.rerun()

        with col_btn2:
            btn_tipo2 = "primary" if aba_atual == "EXTERNO" else "secondary"
            if st.button("🏛️ Receber / Confirmar Retorno de Órgão Externo", key="nav_btn_externo_v9", type=btn_tipo2, use_container_width=True):
                st.session_state["subaba_tramitacao_ativa"] = "EXTERNO"
                st.rerun()

        with col_btn3:
            btn_tipo3 = "primary" if aba_atual == "HISTORICO" else "secondary"
            if st.button("📜 Histórico Permanente de Envios & Ocorrência", key="nav_btn_hist_v9", type=btn_tipo3, use_container_width=True):
                st.session_state["subaba_tramitacao_ativa"] = "HISTORICO"
                st.rerun()

    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

    if "fila_tramitacao_mapeada" not in st.session_state:
        st.session_state["fila_tramitacao_mapeada"] = []

    if "itens_selecionados_tramite" not in st.session_state:
        st.session_state["itens_selecionados_tramite"] = {}

    # =========================================================================
    # ABA 1: TRAMITAR MATERIAIS OU REDS SEM MATERIAIS
    # =========================================================================
    if aba_atual == "TRAMITAR":
        bens_posse = []
        reds_sem_materiais = set()

        for b in all_bens or []:
            posse_atual = str(b.get("fiel_depositario_atual") or b.get("unidade_posse_atual") or "").upper()
            status_tr = str(b.get("status_tramite") or "").strip()
            num_r = str(b.get("num_reds", "")).strip()

            if not b.get("destinatario_pendente") and status_tr not in ["Arquivado/Destinado", "Transferido Definitivo", "Destruído / Encerrado"]:
                if num_pm_logado in posse_atual or nome_militar_atual.upper() in posse_atual or unidade_militar_atual in posse_atual or "CUSTÓDIA" in posse_atual:
                    bens_posse.append(b)

            if b.get("descricao") == "SEM MATERIAL APREENDIDO" or str(b.get("quantidade")) == "0":
                reds_sem_materiais.add(num_r)

        if not bens_posse and not reds_sem_materiais and not st.session_state["fila_tramitacao_mapeada"]:
            st.info("ℹ️ Nenhum material ativo pendente de nova tramitação na sua custódia individual no momento.")
        else:
            if reds_sem_materiais:
                with st.expander("📄 **REDS sem Materiais Apreendidos (Tramitar Apenas Procedimento/Autos)**", expanded=False):
                    st.caption("Selecione um REDS sem apreensão física para registrar o encaminhamento dos autos ao Judiciário/CREDS.")
                    reds_avulso_sel = st.selectbox("Selecione o REDS:", list(reds_sem_materiais), key="sb_reds_sem_mat_tramite")
                    if st.button("➕ Tramitar Autos deste REDS", key="btn_add_reds_sem_mat", width="stretch"):
                        id_fake = f"AUTOS-{reds_avulso_sel}"
                        st.session_state["fila_tramitacao_mapeada"].append({
                            "id_bem": id_fake,
                            "num_reds": reds_avulso_sel,
                            "descricao": "AUTOS DO PROCEDIMENTO (SEM MATERIAL FÍSICO)",
                            "quantidade": 1,
                            "unidade_medida": "UN",
                            "destinatario": "PODER JUDICIÁRIO / TRIBUNAL DE JUSTIÇA (JECRIM)",
                            "unidade_destinatario": "JECRIM / FÓRUM",
                            "fase_destinacao": "Entregue ao Poder Judiciário / Fórum",
                            "observacao": "Encaminhamento ordinário do Termo Circunstanciado de Ocorrência",
                            "eh_creds": True
                        })
                        st.success(f"REDS {reds_avulso_sel} adicionado à fila de confirmação!")
                        st.rerun()

            if bens_posse:
                st.markdown(f"##### 🎒 Seus Bens em Custódia Física ({len(bens_posse)} item/ns)")

                df_bens = pd.DataFrame(bens_posse)
                grupos_reds = df_bens.groupby("num_reds")

                lista_militares = carregar_militares_supabase() or []
                opcoes_militares = []
                
                for m in lista_militares:
                    posto = str(m.get('posto_grad') or m.get('cargo_funcao') or 'PM').strip().upper()
                    nome_comp = str(m.get('nome_completo') or m.get('nome_guerra') or 'MILITAR').strip().upper()
                    nome_guerra = str(m.get('nome_guerra') or '').strip().upper()
                    num_pol = str(m.get('num_policia') or m.get('usuario_login') or '').strip().upper()
                    
                    if nome_guerra and nome_guerra not in nome_comp:
                        label_mil = f"{posto} {nome_comp} ({nome_guerra} - {num_pol})"
                    else:
                        label_mil = f"{posto} {nome_comp} ({num_pol})"
                        
                    opcoes_militares.append(label_mil)

                if not opcoes_militares:
                    opcoes_militares = [f"{nome_militar_atual} ({num_pm_logado})"]

                lista_unidades_creds = extrair_unidades_creds_banco(unidade_militar_atual)

                for num_reds, df_grupo in grupos_reds:
                    qtd_itens_reds = len(df_grupo)
                    
                    with st.expander(f"➕ **REDS: {num_reds}** ({qtd_itens_reds} item/ns apreendido/s)", expanded=False):
                        for idx, row in df_grupo.iterrows():
                            id_bem = str(row.get("id_bem") or row.get("id"))
                            desc = str(row.get("descricao", "SEM DESCRIÇÃO")).strip()
                            qtd = row.get("quantidade", 1)
                            unid = row.get("unidade_medida", "UN")
                            lacre = str(row.get("involucro_lacre", "SEM LACRE")).strip()
                            autor = str(row.get("autores", "N/I")).strip()

                            c_chk, c_info = st.columns([0.6, 9.4])
                            
                            with c_chk:
                                is_selected = st.checkbox(
                                    "Selecionar", 
                                    key=f"chk_tramite_{id_bem}",
                                    label_visibility="collapsed"
                                )

                            with c_info:
                                st.markdown(
                                    f"<div style='font-size: 0.95rem; font-weight: 500; color: #E2E8F0; line-height: 1.5;'>"
                                    f"<b>Item:</b> {desc} | <b>Qtd:</b> {qtd} {unid} | <b>Lacre:</b> {lacre} | <b>Autor:</b> {autor}"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                            if is_selected:
                                st.session_state["itens_selecionados_tramite"][id_bem] = row.to_dict()
                            else:
                                st.session_state["itens_selecionados_tramite"].pop(id_bem, None)

                st.markdown("---")

                selecionados_map = st.session_state["itens_selecionados_tramite"]
                qtd_sel = len(selecionados_map)

                if qtd_sel > 0:
                    st.markdown(f"### 🎯 Definir Destino para {qtd_sel} item(ns) Selecionado(s)")
                    
                    tipo_destinatario = st.radio(
                        "Tipo de Destinatário:",
                        ["Policial Militar / Fiel Depositário", "Seção de Custódia (CREDS-TC / Órgão)"],
                        horizontal=True,
                        key="radio_tipo_destinatario_unificado_v8"
                    )

                    eh_opcao_creds = (tipo_destinatario == "Seção de Custódia (CREDS-TC / Órgão)")

                    col_dest, col_fase = st.columns([1.2, 1])

                    with col_dest:
                        if eh_opcao_creds:
                            destinatario_final = st.selectbox(
                                "Selecione a Unidade / CREDS Destinatário:",
                                options=lista_unidades_creds,
                                index=None,
                                placeholder="Escolha o CREDS da Cia, Batalhão ou Órgão...",
                                key="sb_destinatario_creds_unificado_v8"
                            )
                            unidade_dest_final = destinatario_final or "CREDS / ÓRGÃO EXTERNO"
                        else:
                            destinatario_final = st.selectbox(
                                "Selecione o Policial Destinatário:",
                                options=opcoes_militares,
                                index=None,
                                placeholder="Digite qualquer parte do nome do militar...",
                                key="sb_destinatario_policial_unificado_v8"
                            )
                            unidade_dest_final = unidade_militar_atual

                    with col_fase:
                        if not eh_opcao_creds:
                            fase_destinacao_sel = st.selectbox(
                                "Atualizar Fase de Destinação (Automático):",
                                options=["Com Fiel Depositário / Policial"],
                                index=0,
                                disabled=True,
                                key="sb_fase_policial_locked_v8"
                            )
                        else:
                            if eh_gestor_creds:
                                fase_destinacao_sel = st.selectbox(
                                    "Atualizar Fase de Destinação (Acesso Gestor CREDS):",
                                    [
                                        "Aguardando no CREDS-TC / Custódia",
                                        "Encaminhado à Polícia Civil (PCMG)",
                                        "Entregue ao Poder Judiciário / Fórum",
                                        "Encaminhado para Perícia Técnica",
                                        "Encaminhado para Destruição / Descarte Físico",
                                        "Devolvido ao Proprietário"
                                    ],
                                    key="sb_fase_creds_unificado_enabled_v8"
                                )
                            else:
                                fase_destinacao_sel = "Aguardando no CREDS-TC / Custódia"
                                st.selectbox(
                                    "Fase de Destinação:",
                                    options=["Aguardando no CREDS-TC / Custódia"],
                                    index=0,
                                    disabled=True,
                                    key="sb_fase_creds_unificado_readonly_v8"
                                )

                    eh_orgao_ext_unid = eh_opcao_creds and any(term in str(destinatario_final) for term in ["JUDICIÁRIO", "PERÍCIA", "POLÍCIA CIVIL", "OUTRO"])

                    if eh_orgao_ext_unid:
                        st.warning("🏛️ **Entrega em Órgão Externo:** Defina a modalidade de envio e registre a documentação.")
                        col_ext1, col_ext2 = st.columns(2)
                        with col_ext1:
                            nat_envio_unid = st.radio(
                                "Natureza da Transferência para Órgão Externo:",
                                ["🔄 Com Retorno (Aguardando Devolução / Em Tramitação)", "🔒 Definitiva (Procedimento Encerrado / Sem Retorno)"],
                                key="radio_nat_unificado_v8"
                            )
                            eh_definitivo_val = ("Definitiva" in nat_envio_unid)
                        with col_ext2:
                            num_oficio_unid = st.text_input("Nº do Ofício / Protocolo de Entrega (OBRIGATÓRIO):", placeholder="Ex: Ofício 123/2026", key="txt_ofic_unificado_v8").strip()
                        
                        recibo_unid_file = st.file_uploader("Foto ou PDF do Recibo Assinado / Termo de Aceite (OPCIONAL):", type=["jpg", "jpeg", "png", "pdf"], key="upl_rec_unificado_v8")
                    else:
                        eh_definitivo_val = False
                        num_oficio_unid = ""
                        recibo_unid_file = None

                    # PLACEHOLDER PLACEBO ATUALIZADO SEM DADOS REAIS
                    recebedor_info = st.text_input(
                        "Informe Nome Completo e Matrícula de quem recebeu (OBRIGATÓRIO):", 
                        placeholder="nome e matricula", 
                        key="txt_recebedor_info_v11"
                    ).strip()

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("➕ Adicionar à Fila de Tramitação", type="secondary", width="stretch"):
                        if not destinatario_final:
                            st.error("⚠️ Selecione o destinatário antes de adicionar à fila.")
                        elif not recebedor_info:
                            st.error("⚠️ O preenchimento do Nome Completo e Matrícula de quem recebeu é OBRIGATÓRIO.")
                        elif eh_orgao_ext_unid and not num_oficio_unid:
                            st.error("⚠️ O preenchimento do Nº do Ofício / Protocolo é OBRIGATÓRIO para órgãos externos.")
                        else:
                            for id_bem, dados_item in selecionados_map.items():
                                item_fila = {
                                    "id_bem": id_bem,
                                    "num_reds": dados_item.get("num_reds", "N/I"),
                                    "descricao": dados_item.get("descricao", "N/I"),
                                    "involucro_lacre": dados_item.get("involucro_lacre", "SEM LACRE"),
                                    "quantidade": dados_item.get("quantidade", 1),
                                    "unidade_medida": dados_item.get("unidade_medida", "UN"),
                                    "destinatario": destinatario_final,
                                    "unidade_destinatario": unidade_dest_final,
                                    "fase_destinacao": fase_destinacao_sel,
                                    "observacao": recebedor_info,
                                    "eh_creds": eh_opcao_creds,
                                    "eh_orgao_ext": eh_orgao_ext_unid,
                                    "eh_definitivo": eh_definitivo_val,
                                    "num_oficio": num_oficio_unid,
                                    "recibo_file": recibo_unid_file
                                }
                                st.session_state["fila_tramitacao_mapeada"] = [
                                    f for f in st.session_state["fila_tramitacao_mapeada"] if f["id_bem"] != id_bem
                                ]
                                st.session_state["fila_tramitacao_mapeada"].append(item_fila)

                            st.session_state["itens_selecionados_tramite"] = {}
                            st.toast("✅ Itens adicionados à fila de confirmação!", icon="📋")
                            st.rerun()

            fila_atual = st.session_state["fila_tramitacao_mapeada"]
            if fila_atual:
                st.markdown("---")
                st.markdown(f"#### 📋 Retângulo de Confirmação: Fila de Envio ({len(fila_atual)} item/ns)")
                st.caption("Confira os materiais selecionados e seus respetivos destinos antes de efetivar a transferência.")

                with st.container(border=True):
                    for idx_f, item_f in enumerate(fila_atual):
                        col_f_desc, col_f_dest, col_f_del = st.columns([5, 4, 1])
                        
                        with col_f_desc:
                            st.markdown(
                                f"📦 **Material:** {item_f['descricao']} (Qtd: {item_f['quantidade']} {item_f['unidade_medida']})  \n"
                                f"📄 **REDS:** `{item_f['num_reds']}`"
                            )

                        with col_f_dest:
                            st.markdown(
                                f"🎯 **Destino:** `{item_f['destinatario']}`  \n"
                                f"🏷️ **Fase:** `{item_f['fase_destinacao']}`  \n"
                                f"👤 **Recebedor:** `{item_f['observacao']}`"
                            )

                        with col_f_del:
                            if st.button("🗑️", key=f"btn_del_fila_{item_f['id_bem']}_{idx_f}", help="Remover da fila"):
                                st.session_state["fila_tramitacao_mapeada"].pop(idx_f)
                                st.rerun()

                    st.markdown("<br>", unsafe_allow_html=True)
                    col_cf1, col_cf2 = st.columns(2)
                    
                    with col_cf1:
                        btn_finalizar_tudo = st.button("🚀 Confirmar Envio / Tramitação da Fila", type="primary", width="stretch")
                    with col_cf2:
                        btn_limpar_fila = st.button("❌ Cancelar / Limpar Fila", width="stretch")

                    if btn_limpar_fila:
                        st.session_state["fila_tramitacao_mapeada"] = []
                        st.rerun()

                    if btn_finalizar_tudo:
                        agora_iso = datetime.datetime.now().isoformat()
                        sucessos = 0

                        for f_item in fila_atual:
                            rec_f = f_item.get("recibo_file")
                            if rec_f:
                                upload_midia_supabase(
                                    file_bytes=rec_f.getvalue(),
                                    file_name=sanitizar_nome_arquivo(rec_f.name),
                                    file_type=rec_f.type,
                                    num_reds=f_item["num_reds"],
                                    id_bem=f_item["id_bem"]
                                )

                            if f_item.get("eh_orgao_ext"):
                                status_tr_f = "Transferido Definitivo" if f_item.get("eh_definitivo") else "Em Tramitação"
                                dest_p_f = None
                                fiel_f = f_item["destinatario"]
                                fase_f = f"Entregue ao {f_item['destinatario']} (Ofício: {f_item.get('num_oficio')})"
                            else:
                                status_tr_f = "Pendente de Aceite"
                                dest_p_f = f_item["destinatario"]
                                fiel_f = nome_militar_atual
                                fase_f = f_item["fase_destinacao"]

                            payload_update = {
                                "destinatario_pendente": dest_p_f,
                                "unidade_destinatario_pendente": f_item["unidade_destinatario"] if dest_p_f else None,
                                "fiel_depositario_atual": fiel_f,
                                "data_envio_tramite": agora_iso,
                                "fase_destinacao": fase_f,
                                "status_tramite": status_tr_f,
                                "ultimo_gestor_movimentou": nome_militar_atual
                            }

                            if atualizar_material_supabase(f_item["id_bem"], payload_update):
                                sucessos += 1
                                desc_item_log = f"{f_item['descricao']} (Lacre: {f_item.get('involucro_lacre', 'N/I')})"
                                detalhe_txt = f"Material: {f_item['descricao']} | Fase: {fase_f} | Recebido por: {f_item['observacao']}"
                                
                                if f_item.get("num_oficio"):
                                    detalhe_txt += f" | Ofício/Protocolo: {f_item['num_oficio']}"

                                registrar_log_supabase({
                                    "data_hora": agora_iso,
                                    "num_reds": f_item["num_reds"],
                                    "bem_id": desc_item_log,
                                    "web_origem": "SIOP_TCO",
                                    "acao": "TRAMITACAO_ENVIADA",
                                    "origem": nome_militar_atual,
                                    "unidade_origem": unidade_militar_atual,
                                    "destino": f_item["destinatario"],
                                    "unidade_destino": f_item["unidade_destinatario"],
                                    "detalhe": detalhe_txt
                                })

                        if sucessos > 0:
                            st.success(f"🎉 {sucessos} material(is) tramitado(s) com sucesso!")
                            st.session_state["fila_tramitacao_mapeada"] = []
                            st.session_state["itens_selecionados_tramite"] = {}
                            st.cache_data.clear()
                            st.rerun()

    # =========================================================================
    # ABA 2: CONFIRMAR RETORNO / DEVOLUÇÃO DE ÓRGÃO EXTERNO
    # =========================================================================
    elif aba_atual == "EXTERNO":
        st.markdown("##### 🏛️ Materiais em Tramitação Externa (PCMG, JECRIM, Perícia, MP)")
        st.caption("Como usuários de órgãos externos não possuem acesso ao SIOP, o Operador/Militar do TCO dá o aceite de retorno quando o material for devolvido à unidade.")

        TERMOS_EXTERNOS = [
            "DELEGACIA", "POLÍCIA CIVIL", "PCMG", "JECRIM", "JUDICIÁRIO", 
            "PERÍCIA", "MINISTÉRIO PÚBLICO", "MPMG", "ÓRGÃO EXTERNO", "FÓRUM", "TRIBUNAL"
        ]

        bens_em_orgao_externo = []
        for b in all_bens or []:
            dest_p = str(b.get("destinatario_pendente") or "").upper()
            fase_d = str(b.get("fase_destinacao") or "").upper()
            status_t = str(b.get("status_tramite") or "").strip()
            
            if status_t != "Transferido Definitivo" and any(term in dest_p or term in fase_d for term in TERMOS_EXTERNOS):
                bens_em_orgao_externo.append(b)

        if not bens_em_orgao_externo:
            st.info("ℹ️ Nenhum material atualmente localizado em trâmite temporário de órgãos externos.")
        else:
            df_ext = pd.DataFrame(bens_em_orgao_externo)
            for num_reds_e, df_grupo_e in df_ext.groupby("num_reds", sort=False):
                with st.expander(f"🏛️ **REDS: {num_reds_e}** ({len(df_grupo_e)} item/ns em órgão externo)", expanded=True):
                    for idx_e, item_e in df_grupo_e.iterrows():
                        id_bem_e = str(item_e.get("id_bem") or item_e.get("id"))
                        desc_e = item_e.get("descricao", "N/I")
                        qtd_e_val = item_e.get("quantidade", 1)
                        dest_e = item_e.get("destinatario_pendente") or item_e.get("fase_destinacao") or "Órgão Externo"

                        col_e1, col_e2 = st.columns([7, 3])
                        with col_e1:
                            st.markdown(
                                f"• **Material:** {desc_e} (Qtd: {qtd_e_val})  \n"
                                f"• **Órgão/Destino Atual:** <code class='st-emotion-cache-znj1k1'>{dest_e}</code>",
                                unsafe_allow_html=True
                            )

                        with col_e2:
                            if st.button("📥 Aceitar Retorno / Devolução", key=f"btn_aceite_ext_{id_bem_e}_{idx_e}", type="primary", width="stretch"):
                                agora_iso_ext = datetime.datetime.now().isoformat()
                                payload_retorno = {
                                    "destinatario_pendente": None,
                                    "unidade_destinatario_pendente": None,
                                    "status_tramite": "Em Custódia",
                                    "fiel_depositario_atual": nome_militar_atual,
                                    "unidade_posse_atual": unidade_militar_atual,
                                    "fase_destinacao": "Com Fiel Depositário / Policial"
                                }
                                if atualizar_material_supabase(id_bem_e, payload_retorno):
                                    registrar_log_supabase({
                                        "data_hora": agora_iso_ext,
                                        "num_reds": num_reds_e,
                                        "bem_id": f"{desc_e} (ID: {id_bem_e})",
                                        "web_origem": "SIOP_TCO",
                                        "acao": "ACEITE_DEVOLUCAO_ORGAO_EXTERNO",
                                        "origem": dest_e,
                                        "unidade_origem": "Órgão Externo",
                                        "destino": nome_militar_atual,
                                        "unidade_destino": unidade_militar_atual,
                                        "detalhe": f"Aceite de retorno do material {desc_e} confirmado na guarda de {nome_militar_atual}."
                                    })
                                    st.success("✅ Retorno confirmado! O material foi reincorporado à sua custódia individual.")
                                    st.cache_data.clear()
                                    st.rerun()

    # =========================================================================
    # ABA 3: HISTÓRICO PERMANENTE DE ENVIOS & OCORRÊNCIAS (PADRÃO TÁTICO)
    # =========================================================================
    elif aba_atual == "HISTORICO":
        from modules.tco.estilo_tco import modal_cadeia_custodia_timeline, modal_guia_termo_oficial

        st.markdown("<h5 style='color: #ffe0b2;'>📜 Histórico Permanente de Envios & Ocorrências</h5>", unsafe_allow_html=True)
        st.caption("Consulte todas as tramitações, visualize a cadeia de custódia imutável ou emita a guia oficial de depósito.")

        st.markdown("""
        <style>
        @keyframes pulseAlert {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
            70% { box-shadow: 0 0 0 7px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .badge-animado-alerta {
            background-color: #7f1d1d !important;
            color: #fecaca !important;
            border: 1px solid #ef4444 !important;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.76rem;
            font-weight: 800;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            animation: pulseAlert 2s infinite;
        }
        .badge-fase-status {
            background-color: #8c7343 !important;
            color: #ffffff !important;
            border: 1px solid #c5a059 !important;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
        }
        .caixa-filtro-tatico {
            background: linear-gradient(135deg, #2b231d 0%, #1e1814 100%);
            border: 1.5px solid #6b5735;
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 16px;
        }
        .tag-info-retangulo {
            background-color: #140f0d;
            border: 1px solid #54432a;
            border-radius: 6px;
            padding: 3px 8px;
            color: #ffe0b2;
            font-family: monospace;
            font-size: 0.82rem;
            font-weight: 700;
            display: inline-block;
            margin-right: 4px;
        }
        </style>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="caixa-filtro-tatico">', unsafe_allow_html=True)
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                busca_reds_hist = st.text_input("🔍 Pesquisar por Nº do REDS (Busca Geral):", placeholder="Ex: 2026-000484967", key="txt_busca_reds_hist_v8").strip()
            with col_f2:
                dt_hoje = datetime.date.today()
                dt_30d = dt_hoje - datetime.timedelta(days=90)
                intervalo_datas = st.date_input("🗓️ Filtrar por Período:", value=(dt_30d, dt_hoje), format="DD/MM/YYYY", key="date_hist_envios_v8")
            st.markdown('</div>', unsafe_allow_html=True)

        envios_militar = []
        for b in all_bens or []:
            remetente = str(b.get("fiel_depositario_atual") or b.get("unidade_posse_atual") or b.get("ultimo_gestor_movimentou") or "").upper()
            dest_pendente = b.get("destinatario_pendente")
            status_t = str(b.get("status_tramite", ""))

            if (num_pm_logado in remetente or nome_militar_atual.upper() in remetente or unidade_militar_atual in remetente) or dest_pendente or status_t == "Transferido Definitivo":
                envios_militar.append(b)

        if busca_reds_hist:
            envios_militar = [b for b in envios_militar if busca_reds_hist.lower() in str(b.get("num_reds", "")).lower()]

        if isinstance(intervalo_datas, tuple) and len(intervalo_datas) == 2:
            d_ini, d_fim = intervalo_datas
            filtrados_data = []
            for b in envios_militar:
                dt_env = b.get("data_envio_tramite") or b.get("data_posse_atual") or b.get("data_ingestao")
                if dt_env:
                    try:
                        dt_obj = pd.to_datetime(dt_env).date()
                        if d_ini <= dt_obj <= d_fim:
                            filtrados_data.append(b)
                    except Exception:
                        filtrados_data.append(b)
                else:
                    filtrados_data.append(b)
            envios_militar = filtrados_data

        if not envios_militar:
            st.info("ℹ️ Nenhum registro de histórico localizado com os parâmetros de pesquisa selecionados.")
        else:
            df_hist = pd.DataFrame(envios_militar)
            if "data_envio_tramite" in df_hist.columns:
                df_hist.sort_values(by="data_envio_tramite", ascending=False, inplace=True)
            
            reds_unicos = list(df_hist["num_reds"].unique())
            agora_now = datetime.datetime.now()

            for num_reds_h in reds_unicos:
                df_grupo_h = df_hist[df_hist["num_reds"] == num_reds_h]
                qtd_h = len(df_grupo_h)
                
                with st.expander(f"📄 **REDS: {num_reds_h}** ({qtd_h} item/ns no histórico do procedimento)", expanded=False):
                    for idx_h, item_h in df_grupo_h.iterrows():
                        id_bem_h = str(item_h.get("id_bem") or item_h.get("id"))
                        desc_h = item_h.get("descricao", "N/I")
                        qtd_h_val = item_h.get("quantidade", 1)
                        unid_med = item_h.get("unidade_medida", "UN")
                        lacre_h = item_h.get("involucro_lacre", "SEM LACRE")
                        autor_h = item_h.get("autores", "N/I")
                        custod_h = item_h.get("fiel_depositario_atual", "N/I")
                        dest_h = item_h.get("destinatario_pendente") or item_h.get("fase_destinacao") or "N/I"
                        status_h = item_h.get("status_tramite", "Em Custódia")
                        dt_env_str = item_h.get("data_envio_tramite") or item_h.get("data_posse_atual") or item_h.get("data_ingestao")

                        dias_parado = 0
                        dt_fmt_exata = "Data N/I"
                        if dt_env_str:
                            try:
                                dt_obj_item = pd.to_datetime(dt_env_str)
                                dt_fmt_exata = dt_obj_item.strftime("%d/%m/%Y às %H:%M")
                                dias_parado = (agora_now - dt_obj_item.to_pydatetime().replace(tzinfo=None)).days
                            except Exception:
                                dt_fmt_exata = str(dt_env_str)[:16]

                        fase_u = str(dest_h).upper()
                        if "INCINERAÇÃO" in fase_u or "DESTRUIÇÃO" in fase_u:
                            fase_tag_txt = "🔥 INCINERAÇÃO"
                        elif "PERÍCIA" in fase_u:
                            fase_tag_txt = "🔬 PERÍCIA"
                        elif "PCMG" in fase_u or "DELEGACIA" in fase_u:
                            fase_tag_txt = "🏛️ POLÍCIA CIVIL"
                        elif "JECRIM" in fase_u or "JUDICIÁRIO" in fase_u:
                            fase_tag_txt = "⚖️ JECRIM"
                        else:
                            fase_tag_txt = f"📦 {dest_h[:18]}"

                        col_card_info, col_card_lateral = st.columns([7.2, 2.8])
                        
                        with col_card_info:
                            html_card_mat = f"""
                            <div style="background: linear-gradient(135deg, #2b231d 0%, #1e1814 100%); border: 1.5px solid #6b5735; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;">
                                📄 REDS: <strong style="color: #ffffff;">{num_reds_h}</strong> | Material: <strong style="color: #ffe0b2;">{desc_h}</strong> (Qtd: {qtd_h_val} {unid_med})<br/>
                                🏷️ Lacre: <strong style="color: #ffffff;">{lacre_h}</strong> | Autor: <strong style="color: #ffe0b2;">{autor_h}</strong><br/>
                                📍 Custodiante: <strong style="color: #c5a059;">{custod_h}</strong><br/>
                                <div style="margin-top: 8px;">
                                    🎯 Destino: <span class="tag-info-retangulo">{dest_h}</span>
                                    📊 Status: <span class="tag-info-retangulo">{status_h}</span>
                                    ⏱️ Data/Hora: <span class="tag-info-retangulo">{dt_fmt_exata}</span>
                                </div>
                            </div>
                            """
                            st.markdown(html_card_mat, unsafe_allow_html=True)

                        with col_card_lateral:
                            html_badges = f"""
                            <div style="display: flex; flex-direction: column; gap: 6px; align-items: flex-end; margin-bottom: 8px;">
                                <div class="badge-fase-status">{fase_tag_txt}</div>
                                {'<div class="badge-animado-alerta">⚠️ ' + str(dias_parado) + ' DIAS SEM TRÂMITE</div>' if dias_parado >= 4 else ''}
                            </div>
                            """
                            st.markdown(html_badges, unsafe_allow_html=True)

                            col_b1, col_b2 = st.columns(2)
                            with col_b1:
                                if st.button("🔗 Cadeia", key=f"btn_cad_{id_bem_h}_{idx_h}", help="Ver histórico imutável (Art. 158-B CPP)", use_container_width=True):
                                    modal_cadeia_custodia_timeline(item_h.to_dict())
                            with col_b2:
                                if st.button("📄 Guia", key=f"btn_guia_{id_bem_h}_{idx_h}", help="Gerar Termo de Depósito e Apreensão", use_container_width=True):
                                    modal_guia_termo_oficial(item_h.to_dict(), nome_militar_atual, num_pm_logado, unidade_militar_atual)