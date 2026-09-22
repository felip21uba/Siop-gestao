import streamlit as st
import pandas as pd
import datetime
from modules.tco.database import atualizar_material_supabase, registrar_log_supabase
from modules.tco.modais import abrir_modal_edicao_material
from modules.tco.views import obter_lista_creds_dinamica, injetar_css_cards_alternados

def renderizar_aba_custodia_tramitacao_unificada(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    """Módulo unificado de Custódia e Tramitação com cores alternadas e trava estrita de aceite."""
    injetar_css_cards_alternados()

    st.markdown(f"#### 🎒 Gestão de Custódia & Tramitação de: **{nome_militar_atual}**")

    # 1. LISTA COMPLETA DE DESTINATÁRIOS
    destinatarios_institucionais = [
        "🏛️ PCMG / DELEGACIA DE POLÍCIA CIVIL",
        "🔬 PERÍCIA TÉCNICA / PERITO",
        "⚖️ JECRIM / JUIZADO ESPECIAL / FÓRUM"
    ]
    
    unidades_creds_destino = obter_lista_creds_dinamica()
    mils_todos = st.session_state.get("lista_militares", [])
    nomes_mils_base = [f"{m.get('posto_grad')} {m.get('nome_guerra')}" for m in mils_todos] if mils_todos else []
    
    opcoes_destinatarios_todas = (
        destinatarios_institucionais + 
        [u for u in unidades_creds_destino if "✏️" not in u] + 
        [n for n in nomes_mils_base if n != nome_militar_atual]
    )

    # 2. FILTROS DE PESQUISA
    with st.expander("🔍 **Filtros de Pesquisa na Custódia**", expanded=False):
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            q_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-000484967", key="f_uni_reds").strip()
        with c_f2:
            q_dest = st.text_input("Destinatário / Encaminhamento:", placeholder="Ex: CREDS ou PCMG", key="f_uni_dest").strip()
        with c_f3:
            q_data = st.date_input("Data de Ingestão / Tramitação:", value=None, key="f_uni_data")

    # Filtra materiais relacionados ao militar ativo
    meus_bens = [
        b for b in all_bens_banco 
        if b.get("fiel_depositario_atual") == nome_militar_atual or b.get("remetente_ultimo") == nome_militar_atual
    ]

    # Aplicação dos Filtros
    bens_filtrados = []
    for b in meus_bens:
        if q_reds and q_reds.lower() not in str(b.get("num_reds", "")).lower():
            continue
        dest_str = f"{b.get('destinatario_pendente', '')} {b.get('fase_destinacao', '')} {b.get('unidade_posse_atual', '')}"
        if q_dest and q_dest.lower() not in dest_str.lower():
            continue
        if q_data:
            data_sel_str = q_data.strftime("%Y-%m-%d")
            data_item_str = str(b.get("data_posse_atual", "")) + str(b.get("data_ingestao", ""))
            if data_sel_str not in data_item_str:
                continue
        bens_filtrados.append(b)

    if not bens_filtrados:
        st.info("Nenhum material localizado sob sua custódia com os parâmetros informados.")
        return

    # Agrupamento por REDS
    reds_agrupados = {}
    for b in bens_filtrados:
        r_num = str(b.get("num_reds", "SEM REDS")).strip()
        if r_num not in reds_agrupados:
            reds_agrupados[r_num] = []
        reds_agrupados[r_num].append(b)

    # Ordena pelos últimos 10 REDSs mais recentes
    reds_ordenados = sorted(
        reds_agrupados.items(),
        key=lambda x: max([b.get("data_ingestao") or b.get("data_posse_atual") or "" for b in x[1]]),
        reverse=True
    )[:10]

    st.caption(f"Exibindo os **{len(reds_ordenados)} último(s) REDS** ativos:")

    # 3. RENDERIZAÇÃO POR EXPANDERS DE REDS COM CARDS ALTERNADOS
    for idx_r, (reds_codigo, itens_reds) in enumerate(reds_ordenados):
        primeiro_item = itens_reds[0]
        
        data_bruta = primeiro_item.get("data_ingestao") or primeiro_item.get("data_posse_atual") or ""
        try:
            data_fmt = pd.to_datetime(data_bruta).strftime("%d/%m/%Y") if data_bruta else "Data N/I"
        except Exception:
            data_fmt = str(data_bruta)[:10] if data_bruta else "Data N/I"

        autor_fmt = primeiro_item.get("autores") or "AUTOR NÃO INFORMADO"
        destinacao_fmt = primeiro_item.get("destinatario_pendente") or primeiro_item.get("fase_destinacao") or "Com Fiel Depositário"

        label_expander = f"📄 REDS: {reds_codigo}  |  🗓️ Data: {data_fmt}  |  👤 Autor: {autor_fmt}  |  🏛️ Status: {destinacao_fmt} ({len(itens_reds)} item/ns)"

        with st.expander(label_expander, expanded=(idx_r == 0)):
            st.markdown("##### 📦 Materiais Vinculados a este REDS:")

            chave_carrinho = f"carrinho_tramitacao_{reds_codigo}"
            if chave_carrinho not in st.session_state:
                st.session_state[chave_carrinho] = []

            ids_no_carrinho = [i["id_bem"] for bloco in st.session_state[chave_carrinho] for i in bloco["itens"]]
            itens_livres_para_envio = []

            # 4. RENDERIZAÇÃO DA LISTA DOS ITENS EM CARDS ALTERNADOS
            for idx_i, item_bem in enumerate(itens_reds):
                id_bem_key = item_bem["id_bem"]
                midias = item_bem.get("midias_anexas") or []
                str_midias = f"📎 <b>{len(midias)} foto(s) anexa(s)</b>" if midias else "Sem mídias"
                
                status_tramite = item_bem.get("status_tramite", "Em Custódia")
                remetente_ult = item_bem.get("remetente_ultimo")
                dest_pendente = item_bem.get("destinatario_pendente")
                dt_envio_str = item_bem.get("data_envio_tramite")

                eh_pendente_aceite = (status_tramite == "Pendente Aceite" and remetente_ult == nome_militar_atual)
                eh_ja_aceito = (status_tramite == "Em Custódia" and remetente_ult == nome_militar_atual and item_bem.get("fiel_depositario_atual") != nome_militar_atual)

                pode_cancelar_24h = False
                horas_decorridas = 999
                if eh_pendente_aceite and dt_envio_str:
                    try:
                        dt_envio_obj = pd.to_datetime(dt_envio_str)
                        delta = datetime.datetime.now() - dt_envio_obj.to_pydatetime().replace(tzinfo=None)
                        horas_decorridas = delta.total_seconds() / 3600.0
                        if horas_decorridas <= 24.0:
                            pode_cancelar_24h = True
                    except Exception:
                        pass

                # ALTERNÂNCIA DE COR POR ITEM
                e_marrom = (idx_i % 2 != 0)
                classe_card = "card-brown" if e_marrom else "card-blue"

                if eh_pendente_aceite:
                    status_badge = f"⏳ <b>Aguardando Aceite:</b> {dest_pendente}"
                elif eh_ja_aceito:
                    status_badge = f"🔒 <b>Aceito por:</b> {item_bem.get('fiel_depositario_atual')}"
                elif id_bem_key in ids_no_carrinho:
                    status_badge = f"📌 <b>Selecionado para Envio</b>"
                else:
                    itens_livres_para_envio.append(item_bem)
                    status_badge = f"🎒 <b>Em Custódia</b>"

                card_html = f"""
                <div class="{classe_card}">
                    📄 REDS: <b>{reds_codigo}</b> | Material: <b>{item_bem.get('descricao')}</b><br/>
                    <small>Lacre: <b>{item_bem.get('involucro_lacre', 'N/I')}</b> | Qtd: <b>{item_bem.get('quantidade', 1.0)} {item_bem.get('unidade_medida', 'UN')}</b> | {str_midias}</small><br/>
                    📍 Status: {status_badge}
                </div>
                """
                
                st.markdown(card_html, unsafe_allow_html=True)

                c_act_col1, c_act_col2 = st.columns([4, 1])
                with c_act_col2:
                    if eh_pendente_aceite:
                        if pode_cancelar_24h:
                            if st.button("↩️ Cancelar", key=f"btn_canc_24h_{id_bem_key}_{idx_r}_{idx_i}", use_container_width=True):
                                now_iso = datetime.datetime.now().isoformat()
                                upd_cancelar = {
                                    "status_tramite": "Em Custódia",
                                    "fiel_depositario_atual": nome_militar_atual,
                                    "unidade_posse_atual": unidade_militar_atual,
                                    "destinatario_pendente": None,
                                    "unidade_destinatario_pendente": None,
                                    "data_envio_tramite": None
                                }
                                if atualizar_material_supabase(id_bem_key, upd_cancelar):
                                    registrar_log_supabase({
                                        "data_hora": now_iso,
                                        "num_reds": reds_codigo,
                                        "bem_id": id_bem_key,
                                        "acao": "CANCELAMENTO DE TRAMITAÇÃO (24H)",
                                        "origem": nome_militar_atual,
                                        "unidade_origem": unidade_militar_atual,
                                        "destino": nome_militar_atual,
                                        "unidade_destino": unidade_militar_atual,
                                        "detalhe": f"Envio cancelado antes do aceite pelo remetente."
                                    })
                                    st.toast("Envio cancelado com sucesso!", icon="✅")
                                    st.rerun()
                    elif not eh_ja_aceito:
                        if st.button("✏️ Editar", key=f"btn_ed_uni_{id_bem_key}_{idx_r}_{idx_i}", use_container_width=True):
                            abrir_modal_edicao_material(item_bem, nome_militar_atual, unidade_militar_atual)

                st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)

            # 5. QUADRO DE ENCAMINHAMENTO
            if itens_livres_para_envio:
                st.markdown("---")
                st.markdown("##### 🏛️ Encaminhar Materiais Disponíveis:")

                col_dest1, col_dest2 = st.columns([2, 2.5])

                with col_dest1:
                    destinatario_selecionado = st.selectbox(
                        "Selecione o Destinatário:",
                        options=opcoes_destinatarios_todas,
                        key=f"sb_dest_sel_{reds_codigo}_{idx_r}"
                    )

                with col_dest2:
                    mapa_opcoes_mats = {
                        f"Item {itens_reds.index(b)+1}: {b['descricao']}": b 
                        for b in itens_livres_para_envio
                    }
                    mats_escolhidos_keys = st.multiselect(
                        "Selecione o(s) Material(is) para este destino:",
                        options=["-- TODOS OS MATERIAIS DISPONÍVEIS --"] + list(mapa_opcoes_mats.keys()),
                        key=f"ms_mats_sel_{reds_codigo}_{idx_r}"
                    )

                c_btn_add, _ = st.columns([2, 3])
                with c_btn_add:
                    if st.button("➕ Adicionar ao Quadro de Envio", key=f"btn_add_carrinho_{reds_codigo}_{idx_r}", use_container_width=True):
                        if not mats_escolhidos_keys:
                            st.warning("⚠️ Selecione ao menos um material para adicionar.")
                        else:
                            if "-- TODOS OS MATERIAIS DISPONÍVEIS --" in mats_escolhidos_keys:
                                objetos_alvo = list(itens_livres_para_envio)
                            else:
                                objetos_alvo = [mapa_opcoes_mats[k] for k in mats_escolhidos_keys if k in mapa_opcoes_mats]

                            st.session_state[chave_carrinho].append({
                                "destinatario": destinatario_selecionado,
                                "itens": objetos_alvo
                            })
                            st.toast("Materiais adicionados ao Quadro de Envio!", icon="✅")
                            st.rerun()

            # 6. CONFIRMAÇÃO DA TRAMITAÇÃO
            if st.session_state[chave_carrinho]:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("##### 📋 Quadro Resumo de Transferência deste REDS:")

                for idx_b, bloco in enumerate(st.session_state[chave_carrinho]):
                    with st.container(border=True):
                        col_quad1, col_quad2 = st.columns([4, 1])
                        with col_quad1:
                            st.markdown(f"🏛️ **Destino:** **{bloco['destinatario']}**")
                            for it_b in bloco["itens"]:
                                idx_orig = itens_reds.index(it_b) + 1
                                st.caption(f"• **Item {idx_orig}:** {it_b['descricao']} (Lacre: {it_b.get('involucro_lacre', 'N/I')})")
                        
                        with col_quad2:
                            if st.button("🗑️ Remover", key=f"btn_rem_blk_{reds_codigo}_{idx_r}_{idx_b}", use_container_width=True):
                                st.session_state[chave_carrinho].pop(idx_b)
                                st.rerun()

                st.markdown("<br>", unsafe_allow_html=True)
                obs_tram_reds = st.text_input(
                    "Observação Geral da Tramitação deste REDS:", 
                    placeholder="Ex: Encaminhado para o depósito CREDS TCO da Cia", 
                    key=f"obs_uni_{reds_codigo}_{idx_r}"
                )

                col_conf_b1, col_conf_b2 = st.columns([2, 1])
                with col_conf_b1:
                    btn_confirmar_tramitacao = st.button(
                        f"🚀 Confirmar Envio e Tramitar Materiais do REDS {reds_codigo}",
                        type="primary",
                        key=f"btn_conf_tram_{reds_codigo}_{idx_r}",
                        use_container_width=True
                    )

                with col_conf_b2:
                    if st.button("🧹 Limpar Quadro", key=f"btn_reset_carrinho_{reds_codigo}_{idx_r}", use_container_width=True):
                        st.session_state[chave_carrinho] = []
                        st.rerun()

                if btn_confirmar_tramitacao:
                    now_iso = datetime.datetime.now().isoformat()
                    sucessos_tram = 0

                    for bloco in st.session_state[chave_carrinho]:
                        destino_final = bloco["destinatario"]

                        for item_bem in bloco["itens"]:
                            id_bem_target = item_bem["id_bem"]

                            upd_data = {
                                "status_tramite": "Pendente Aceite",
                                "remetente_ultimo": nome_militar_atual,
                                "unidade_remetente": unidade_militar_atual,
                                "destinatario_pendente": destino_final,
                                "unidade_destinatario_pendente": unidade_militar_atual,
                                "data_envio_tramite": now_iso,
                                "obs_tramite": obs_tram_reds
                            }

                            if atualizar_material_supabase(id_bem_target, upd_data):
                                registrar_log_supabase({
                                    "data_hora": now_iso,
                                    "num_reds": reds_codigo,
                                    "bem_id": id_bem_target,
                                    "web_origem": "SIOP_TCO",
                                    "acao": "SOLICITAÇÃO DE TRAMITAÇÃO GRANULAR",
                                    "origem": nome_militar_atual,
                                    "unidade_origem": unidade_militar_atual,
                                    "destino": destino_final,
                                    "unidade_destino": unidade_militar_atual,
                                    "detalhe": f"Material '{item_bem.get('descricao')}' tramitado para {destino_final}. Obs: {obs_tram_reds}"
                                })
                                sucessos_tram += 1

                    if sucessos_tram > 0:
                        st.session_state[chave_carrinho] = []
                        st.success(f"✅ Envio confirmado! {sucessos_tram} material(is) do REDS {reds_codigo} foram encaminhados!")
                        st.rerun()