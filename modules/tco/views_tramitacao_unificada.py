import streamlit as st
import pandas as pd
import datetime
from core.database import supabase, carregar_militares_supabase
from core.permissions import usuario_eh_gestor_creds
from modules.tco.database import registrar_log_supabase, atualizar_material_supabase


def extrair_unidades_creds_banco(unidade_militar_atual=""):
    """
    Lê a coluna 'unidade' da tabela 'usuarios' no Supabase, divide fragmentos com '/'
    e monta dinamicamente os CREDS correspondentes.
    """
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
    """
    Renderiza a Aba de Custódia Física e o Histórico dos últimos 10 REDS agrupados por expansor (+).
    """
    st.subheader("🎒 Custódia Física & Tramitação Unificada")
    st.caption("Gerencie os bens sob sua posse, monte a fila de tramitação definindo o destino específico de cada item e consulte seu histórico.")

    usr_logado = st.session_state.get("usuario_dados", {})
    num_pm_logado = str(usr_logado.get("usuario_login") or usr_logado.get("usuario") or "").strip().upper()

    eh_gestor_creds = usuario_eh_gestor_creds(usr_logado) or any(
        p in str(usr_logado.get("perfil_creds", "")).upper() 
        for p in ["GESTOR", "ADMIN", "PROGRAMADOR"]
    )

    tab_pendentes, tab_historico = st.tabs([
        "📤 Tramitar Materiais",
        "📜 Histórico de Envios & Pendências (Últimos 10 REDS)"
    ])

    if "fila_tramitacao_mapeada" not in st.session_state:
        st.session_state["fila_tramitacao_mapeada"] = []

    # =========================================================================
    # ABA 1: TRAMITAR MATERIAIS
    # =========================================================================
    with tab_pendentes:
        bens_posse = []
        for b in all_bens:
            posse_atual = str(b.get("fiel_depositario_atual") or b.get("unidade_posse_atual") or "").upper()
            status_tr = str(b.get("status_tramite") or "").strip()
            
            if not b.get("destinatario_pendente") and status_tr not in ["Arquivado/Destinado"]:
                if num_pm_logado in posse_atual or nome_militar_atual.upper() in posse_atual or unidade_militar_atual in posse_atual or "CUSTÓDIA" in posse_atual:
                    bens_posse.append(b)

        if not bens_posse and not st.session_state["fila_tramitacao_mapeada"]:
            st.info("ℹ️ Nenhum material disponível para nova tramitação sob sua custódia física no momento.")
        else:
            if bens_posse:
                st.markdown(f"##### 🎒 Seus Bens em Custódia Física ({len(bens_posse)} item/ns)")

                df_bens = pd.DataFrame(bens_posse)
                grupos_reds = df_bens.groupby("num_reds")

                if "itens_selecionados_tramite" not in st.session_state:
                    st.session_state["itens_selecionados_tramite"] = {}

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
                        key="radio_tipo_destinatario_dynamic"
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
                                key="sb_destinatario_creds_selected"
                            )
                            unidade_dest_final = destinatario_final or "CREDS / ÓRGÃO EXTERNO"
                        else:
                            destinatario_final = st.selectbox(
                                "Selecione o Policial Destinatário:",
                                options=opcoes_militares,
                                index=None,
                                placeholder="Digite qualquer parte do nome do militar...",
                                key="sb_destinatario_policial_selected"
                            )
                            unidade_dest_final = unidade_militar_atual

                    with col_fase:
                        if eh_gestor_creds:
                            fase_destinacao_sel = st.selectbox(
                                "Atualizar Fase de Destinação (Acesso Gestor CREDS):",
                                [
                                    "Com Fiel Depositário / Policial",
                                    "Aguardando no CREDS-TC / Custódia",
                                    "Encaminhado à Polícia Civil (PCMG)",
                                    "Entregue ao Poder Judiciário / Fórum",
                                    "Encaminhado para Perícia Técnica",
                                    "Encaminhado para Destruição / Descarte Físico",
                                    "Devolvido ao Proprietário",
                                    "Outro Procedimento (Especificar nas Observações)"
                                ],
                                key="sb_fase_creds_form"
                            )
                        else:
                            if not eh_opcao_creds:
                                fase_destinacao_sel = "Com Fiel Depositário / Policial"
                            else:
                                fase_destinacao_sel = "Aguardando no CREDS-TC / Custódia"
                            
                            st.text_input("Fase de Destinação:", value=fase_destinacao_sel, disabled=True, key="txt_fase_readonly_form")

                    obs_tramite = st.text_input(
                        "Observações / Motivo da Transferência:",
                        placeholder="Ex: Passagem de serviço ou entrega na Seção de Custódia",
                        key="txt_obs_tramite_form"
                    ).strip()

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("➕ Adicionar à Fila de Tramitação", type="secondary", use_container_width=True):
                        if not destinatario_final:
                            st.error("⚠️ Selecione o destinatário antes de adicionar à fila.")
                        else:
                            for id_bem, dados_item in selecionados_map.items():
                                item_fila = {
                                    "id_bem": id_bem,
                                    "num_reds": dados_item.get("num_reds", "N/I"),
                                    "descricao": dados_item.get("descricao", "N/I"),
                                    "quantidade": dados_item.get("quantidade", 1),
                                    "unidade_medida": dados_item.get("unidade_medida", "UN"),
                                    "destinatario": destinatario_final,
                                    "unidade_destinatario": unidade_dest_final,
                                    "fase_destinacao": fase_destinacao_sel,
                                    "observacao": obs_tramite or "Sem obs",
                                    "eh_creds": eh_opcao_creds
                                }
                                st.session_state["fila_tramitacao_mapeada"] = [
                                    f for f in st.session_state["fila_tramitacao_mapeada"] if f["id_bem"] != id_bem
                                ]
                                st.session_state["fila_tramitacao_mapeada"].append(item_fila)

                            st.session_state["itens_selecionados_tramite"] = {}
                            st.toast("✅ Itens e destinos adicionados ao painel de confirmação!", icon="📋")
                            st.rerun()

            # PAINEL DA FILA DE ENVIOS
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
                                f"🏷️ **Fase:** `{item_f['fase_destinacao']}`"
                            )

                        with col_f_del:
                            if st.button("🗑️", key=f"btn_del_fila_{item_f['id_bem']}_{idx_f}", help="Remover da fila"):
                                st.session_state["fila_tramitacao_mapeada"].pop(idx_f)
                                st.rerun()

                    st.markdown("<br>", unsafe_allow_html=True)
                    col_cf1, col_cf2 = st.columns(2)
                    
                    with col_cf1:
                        btn_finalizar_tudo = st.button("🚀 Confirmar Envio / Tramitação da Fila", type="primary", use_container_width=True)
                    with col_cf2:
                        btn_limpar_fila = st.button("❌ Cancelar / Limpar Fila", use_container_width=True)

                    if btn_limpar_fila:
                        st.session_state["fila_tramitacao_mapeada"] = []
                        st.rerun()

                    if btn_finalizar_tudo:
                        agora_iso = datetime.datetime.now().isoformat()
                        sucessos = 0

                        for f_item in fila_atual:
                            payload_update = {
                                "destinatario_pendente": f_item["destinatario"],
                                "unidade_destinatario_pendente": f_item["unidade_destinatario"],
                                "data_envio_tramite": agora_iso,
                                "fase_destinacao": f_item["fase_destinacao"],
                                "status_tramite": "Pendente de Aceite"
                            }

                            if atualizar_material_supabase(f_item["id_bem"], payload_update):
                                sucessos += 1
                                registrar_log_supabase({
                                    "data_hora": agora_iso,
                                    "num_reds": f_item["num_reds"],
                                    "bem_id": f_item["id_bem"],
                                    "web_origem": "SIOP_TCO",
                                    "acao": "TRAMITACAO_ENVIADA",
                                    "origem": nome_militar_atual,
                                    "unidade_origem": unidade_militar_atual,
                                    "destino": f_item["destinatario"],
                                    "unidade_destino": f_item["unidade_destinatario"],
                                    "detalhe": f"Fase: {f_item['fase_destinacao']} | Obs: {f_item['observacao']}"
                                })

                        if sucessos > 0:
                            st.success(f"🎉 {sucessos} material(is) tramitado(s) com sucesso!")
                            st.session_state["fila_tramitacao_mapeada"] = []
                            st.session_state["itens_selecionados_tramite"] = {}
                            st.cache_data.clear()
                            st.rerun()

    # =========================================================================
    # ABA 2: HISTÓRICO DE ENVIOS (COM EXPANDER '+' RECOLHÍVEL POR REDS)
    # =========================================================================
    with tab_historico:
        st.markdown("##### 📜 Histórico de Tramitações Enviadas por Você")
        st.caption("Consulte os envios realizados, filtre por REDS/período e cancele tramitações para Policiais ou CREDS pendentes de aceite em até 72 horas.")

        with st.container(border=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                busca_reds_hist = st.text_input("🔍 Pesquisar por Nº do REDS:", placeholder="Ex: 2026-000484967", key="txt_busca_reds_hist").strip()
            with col_f2:
                dt_hoje = datetime.date.today()
                dt_30d = dt_hoje - datetime.timedelta(days=30)
                intervalo_datas = st.date_input("🗓️ Filtrar por Período de Envio:", value=(dt_30d, dt_hoje), format="DD/MM/YYYY", key="date_hist_envios")

        envios_militar = []
        for b in all_bens:
            remetente = str(b.get("fiel_depositario_atual") or b.get("unidade_posse_atual") or "").upper()
            dest_pendente = b.get("destinatario_pendente")
            
            if (num_pm_logado in remetente or nome_militar_atual.upper() in remetente) and dest_pendente:
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
            st.info("ℹ️ Nenhum envio localizado com os parâmetros pesquisados.")
        else:
            df_hist = pd.DataFrame(envios_militar)
            if "data_envio_tramite" in df_hist.columns:
                df_hist.sort_values(by="data_envio_tramite", ascending=False, inplace=True)
            
            # Limita aos 10 últimos REDS únicos
            reds_unicos_10 = list(df_hist["num_reds"].unique())[:10]
            df_10_reds = df_hist[df_hist["num_reds"].isin(reds_unicos_10)]

            agora_now = datetime.datetime.now()

            # RENDERIZAÇÃO EM FORMATO DE EXPANDER '+' POR REDS NO HISTÓRICO
            for num_reds_h, df_grupo_h in df_10_reds.groupby("num_reds", sort=False):
                qtd_h = len(df_grupo_h)
                
                with st.expander(f"➕ **REDS: {num_reds_h}** ({qtd_h} item/ns tramitado/s)", expanded=False):
                    for idx_h, item_h in df_grupo_h.iterrows():
                        id_bem_h = str(item_h.get("id_bem") or item_h.get("id"))
                        desc_h = item_h.get("descricao", "N/I")
                        qtd_h_val = item_h.get("quantidade", 1)
                        dest_h = item_h.get("destinatario_pendente") or "N/I"
                        status_h = item_h.get("status_tramite", "Pendente de Aceite")
                        dt_env_str = item_h.get("data_envio_tramite") or item_h.get("data_posse_atual")

                        pode_cancelar = False
                        tempo_restante_str = ""

                        if dest_h != "N/I" and status_h in ["Pendente de Aceite", "Em Tramitação"] and dt_env_str:
                            try:
                                dt_env_obj = pd.to_datetime(dt_env_str).to_pydatetime().replace(tzinfo=None)
                                horas_passadas = (agora_now - dt_env_obj).total_seconds() / 3600.0
                                if horas_passadas <= 72.0:
                                    pode_cancelar = True
                                    horas_restantes = max(0.0, 72.0 - horas_passadas)
                                    tempo_restante_str = f"⏱️ {int(horas_restantes)}h {int((horas_restantes % 1)*60)}m restantes para cancelamento"
                                else:
                                    tempo_restante_str = "⏱️ Prazo de 72h expirado"
                            except Exception:
                                pode_cancelar = False
                        else:
                            tempo_restante_str = "✅ Recebido pelo Destinatário (Imutável)"

                        col_info_h, col_act_h = st.columns([7, 3])
                        
                        with col_info_h:
                            st.markdown(
                                f"• **Material:** {desc_h} (Qtd: {qtd_h_val})  \n"
                                f"• **Destinatário:** `{dest_h}` | **Status:** `{status_h}`"
                            )
                            if tempo_restante_str:
                                st.caption(tempo_restante_str)

                        with col_act_h:
                            if pode_cancelar:
                                if st.button("❌ Cancelar Envio", key=f"btn_canc_{id_bem_h}_{idx_h}", type="primary", use_container_width=True):
                                    payload_canc = {
                                        "destinatario_pendente": None,
                                        "unidade_destinatario_pendente": None,
                                        "status_tramite": "Em Custódia",
                                        "fiel_depositario_atual": nome_militar_atual,
                                        "unidade_posse_atual": unidade_militar_atual
                                    }
                                    if atualizar_material_supabase(id_bem_h, payload_canc):
                                        registrar_log_supabase({
                                            "data_hora": agora_now.isoformat(),
                                            "num_reds": num_reds_h,
                                            "bem_id": id_bem_h,
                                            "web_origem": "SIOP_TCO",
                                            "acao": "CANCELAMENTO_TRAMITACAO_REMETER",
                                            "origem": nome_militar_atual,
                                            "unidade_origem": unidade_militar_atual,
                                            "destino": nome_militar_atual,
                                            "unidade_destino": unidade_militar_atual,
                                            "detalhe": f"Envio para {dest_h} cancelado pelo remetente dentro das 72h."
                                        })
                                        st.success("✅ Tramitação cancelada! O material retornou para sua custódia física.")
                                        st.cache_data.clear()
                                        st.rerun()
                            else:
                                st.caption("🔒 Registro Imutável (Somente Leitura)")