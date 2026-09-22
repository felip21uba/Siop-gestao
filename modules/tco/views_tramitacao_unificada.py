import streamlit as st
import pandas as pd
import datetime
from modules.tco.database import atualizar_material_supabase, registrar_log_supabase
from modules.tco.modais import abrir_modal_edicao_material
from modules.tco.views import obter_lista_creds_dinamica, injetar_css_cards_alternados, extrair_unidade_mae_creds

def renderizar_aba_custodia_tramitacao_unificada(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    """Módulo unificado de Custódia e Tramitação com padronização DD/MM/AAAA e controle estrito de visibilidade por hierarquia."""
    injetar_css_cards_alternados()

    usr_logado = st.session_state.get("usuario_dados", {})
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil_str = str(usr_logado.get("nivel_acesso") or usr_logado.get("perfil") or "").upper()
    perfil_creds_usr = str(usr_logado.get("perfil_creds", "TROPA")).upper()
    num_policia_usr = str(usr_logado.get("usuario_login") or usr_logado.get("num_policia") or "").strip()

    # PERMISSÕES DE ACESSO SOBERANO E GESTÃO
    eh_soberano = any(p in perfil_str for p in ["PROGRAMADOR", "DESENVOLVEDOR", "ADMIN", "TESTADOR"]) or \
                 any(p in cargo_str for p in ["PROGRAMADOR", "DESENVOLVEDOR", "COMANDANTE", "SUBCOMANDANTE", "P1"]) or \
                 perfil_creds_usr == "GESTOR_UNIDADE"

    eh_gestor_cia = perfil_creds_usr in ["GESTOR_CIA", "OPERADOR"] or \
                    any(p in cargo_str for p in ["COMANDANTE_CIA", "SARGENTIACAO", "CMT_CIA"]) or \
                    any(p in perfil_str for p in ["COMANDANTE_CIA", "SARGENTIACAO"])

    eh_cmt_pelotao = any(p in cargo_str for p in ["TENENTE", "TEN", "CMT_PELOTAO", "PELOTAO"]) or \
                     any(p in perfil_str for p in ["CMT_PELOTAO"])

    unidade_mae_usr = extrair_unidade_mae_creds(unidade_militar_atual) or unidade_militar_atual

    st.markdown(f"#### 🎒 Gestão de Custódia & Tramitação de Materiais TCO")

    # =========================================================================
    # 🔔 CAIXA DE ALERTA DO GESTOR DO CREDS (MATERIAIS RECENTES AGUARDANDO ACEITE)
    # =========================================================================
    materiais_pendentes_unidade = [
        b for b in all_bens_banco 
        if b.get("status_tramite") == "Pendente Aceite" and (
            unidade_militar_atual.lower() in str(b.get("unidade_destinatario_pendente", "")).lower() or
            unidade_militar_atual.lower() in str(b.get("destinatario_pendente", "")).lower() or
            nome_militar_atual.lower() in str(b.get("destinatario_pendente", "")).lower()
        )
    ]

    if materiais_pendentes_unidade:
        st.warning(
            f"🔔 **ALERTA DE TRAMITAÇÃO:** Você possui **{len(materiais_pendentes_unidade)} material(is) recente(s)** "
            f"encaminhado(s) aguardando conferência e aceite na sua unidade/escopo!"
        )

    st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)

    # =========================================================================
    # 🔀 DADOS E SELETOR DE ESCOPO DE VISUALIZAÇÃO POR HIERARQUIA
    # =========================================================================
    opcoes_visao = [f"🎒 Meus Materiais (Custódia Individual: {nome_militar_atual})"]

    if eh_soberano:
        opcoes_visao.append(f"🏛️ Acervo Geral da Unidade (21º BPM / Todas as Cias)")
        opcoes_visao.append(f"🏢 Acervo da minha Companhia ({unidade_mae_usr})")
        
    elif eh_gestor_cia:
        opcoes_visao.append(f"🏢 Acervo da Companhia ({unidade_mae_usr})")

    elif eh_cmt_pelotao:
        opcoes_visao.append(f"🛡️ Acervo do Pelotão / Fração ({unidade_militar_atual})")

    with st.container(border=True):
        col_rad1, col_rad2 = st.columns([3, 2])
        with col_rad1:
            visao_acervo = st.radio(
                "Selecione o Escopo do Acervo para Visualização:",
                opcoes_visao,
                horizontal=True,
                key="radio_visao_acervo_custodia_v2"
            )
        
        with col_rad2:
            # Se for soberano e selecionar acervo geral, permite escolher Cias específicas
            if eh_soberano and "Acervo Geral" in visao_acervo:
                lista_cias = ["TODAS AS COMPANHIAS"] + [u for u in obter_lista_creds_dinamica() if "✏️" not in u]
                cia_filtrada_soberano = st.selectbox("Filtrar Companhia/CREDS Específico:", lista_cias, key="sb_filtro_soberano_cia")
            else:
                cia_filtrada_soberano = None

    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

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

    # 2. FILTROS DE PESQUISA (PADRÃO BRASILEIRO DE DATA DD/MM/AAAA)
    with st.expander("🔍 **Filtros de Pesquisa na Custódia**", expanded=False):
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            q_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-000484967", key="f_uni_reds").strip()
        with c_f2:
            q_dest = st.text_input("Destinatário / Encaminhamento:", placeholder="Ex: CREDS ou PCMG", key="f_uni_dest").strip()
        with c_f3:
            q_data = st.date_input("Data de Ingestão / Tramitação (DD/MM/AAAA):", value=None, format="DD/MM/YYYY", key="f_uni_data")

    # 3. FILTRAGEM E RESTRIÇÃO DOS MATERIAIS CONFORME O ESCOPO HIERÁRQUICO
    if "Meus Materiais" in visao_acervo:
        meus_bens = [
            b for b in all_bens_banco 
            if b.get("fiel_depositario_atual") == nome_militar_atual or b.get("remetente_ultimo") == nome_militar_atual
        ]
    elif "Acervo Geral da Unidade" in visao_acervo:
        if cia_filtrada_soberano and cia_filtrada_soberano != "TODAS AS COMPANHIAS":
            unid_target = cia_filtrada_soberano.replace("CREDS TCO - ", "").strip().lower()
            meus_bens = [
                b for b in all_bens_banco
                if unid_target in str(b.get("unidade_posse_atual", "")).lower() or
                   unid_target in str(b.get("unidade_destinatario_pendente", "")).lower()
            ]
        else:
            meus_bens = list(all_bens_banco)
    elif "Acervo da Companhia" in visao_acervo or "Acervo da minha Companhia" in visao_acervo:
        unid_target = unidade_mae_usr.lower()
        meus_bens = [
            b for b in all_bens_banco
            if unid_target in str(b.get("unidade_posse_atual", "")).lower() or
               unid_target in str(b.get("unidade_destinatario_pendente", "")).lower() or
               unid_target in str(extrair_unidade_mae_creds(str(b.get("unidade_posse_atual", ""))) or "").lower()
        ]
    elif "Acervo do Pelotão" in visao_acervo:
        unid_target = unidade_militar_atual.lower()
        meus_bens = [
            b for b in all_bens_banco
            if unid_target in str(b.get("unidade_posse_atual", "")).lower() or
               unid_target in str(b.get("unidade_destinatario_pendente", "")).lower()
        ]
    else:
        meus_bens = [
            b for b in all_bens_banco 
            if b.get("fiel_depositario_atual") == nome_militar_atual
        ]

    # Aplicação dos Filtros Secundários
    bens_filtrados = []
    for b in meus_bens:
        if q_reds and q_reds.lower() not in str(b.get("num_reds", "")).lower():
            continue
        dest_str = f"{b.get('destinatario_pendente', '')} {b.get('fase_destinacao', '')} {b.get('unidade_posse_atual', '')}"
        if q_dest and q_dest.lower() not in dest_str.lower():
            continue
        if q_data:
            data_sel_fmt = q_data.strftime("%d/%m/%Y")
            data_item_raw = str(b.get("data_posse_atual", "")) + str(b.get("data_ingestao", ""))
            try:
                data_item_fmt = pd.to_datetime(data_item_raw[:10]).strftime("%d/%m/%Y") if len(data_item_raw) >= 10 else ""
            except Exception:
                data_item_fmt = ""
            if data_sel_fmt not in data_item_fmt and q_data.strftime("%Y-%m-%d") not in data_item_raw:
                continue
        bens_filtrados.append(b)

    if not bens_filtrados:
        st.info("Nenhum material localizado no escopo selecionado com os parâmetros informados.")
        return

    # Agrupamento por REDS
    reds_agrupados = {}
    for b in bens_filtrados:
        r_num = str(b.get("num_reds", "SEM REDS")).strip()
        if r_num not in reds_agrupados:
            reds_agrupados[r_num] = []
        reds_agrupados[r_num].append(b)

    reds_ordenados = sorted(
        reds_agrupados.items(),
        key=lambda x: max([b.get("data_ingestao") or b.get("data_posse_atual") or "" for b in x[1]]),
        reverse=True
    )[:10]

    st.caption(f"Exibindo **{len(reds_ordenados)} REDS(s)** no escopo ativo:")

    # 4. RENDERIZAÇÃO POR EXPANDERS DE REDS COM CARDS ALTERNADOS
    for idx_r, (reds_codigo, itens_reds) in enumerate(reds_ordenados):
        primeiro_item = itens_reds[0]
        
        data_bruta = primeiro_item.get("data_ingestao") or primeiro_item.get("data_posse_atual") or ""
        try:
            data_fmt = pd.to_datetime(data_bruta).strftime("%d/%m/%Y %H:%M") if data_bruta else "Data N/I"
        except Exception:
            data_fmt = str(data_bruta)[:16] if data_bruta else "Data N/I"

        autor_fmt = primeiro_item.get("autores") or "AUTOR NÃO INFORMADO"
        destinacao_fmt = primeiro_item.get("destinatario_pendente") or primeiro_item.get("fase_destinacao") or "Com Fiel Depositário"

        label_expander = f"📄 REDS: {reds_codigo}  |  🗓️ Data/Hora: {data_fmt}  |  👤 Autor: {autor_fmt}  |  🏛️ Status: {destinacao_fmt} ({len(itens_reds)} item/ns)"

        with st.expander(label_expander, expanded=(idx_r == 0)):
            st.markdown("##### 📦 Materiais Vinculados a este REDS:")

            chave_carrinho = f"carrinho_tramitacao_{reds_codigo}"
            if chave_carrinho not in st.session_state:
                st.session_state[chave_carrinho] = []

            ids_no_carrinho = [i["id_bem"] for bloco in st.session_state[chave_carrinho] for i in bloco["itens"]]
            itens_livres_para_envio = []

            # RENDERIZAÇÃO DA LISTA DOS ITENS EM CARDS ALTERNADOS
            for idx_i, item_bem in enumerate(itens_reds):
                id_bem_key = item_bem["id_bem"]
                midias = item_bem.get("midias_anexas") or []
                str_midias = f"📎 <b>{len(midias)} foto(s) anexa(s)</b>" if midias else "Sem mídias"
                
                status_tramite = item_bem.get("status_tramite", "Em Custódia")
                remetente_ult = item_bem.get("remetente_ultimo")
                dest_pendente = item_bem.get("destinatario_pendente")
                fiel_dep_atual = item_bem.get("fiel_depositario_atual")
                dt_envio_str = item_bem.get("data_envio_tramite")

                eh_pendente_aceite = (status_tramite == "Pendente Aceite")
                eh_ja_aceito = (status_tramite == "Em Custódia" and fiel_dep_atual != nome_militar_atual and remetente_ult == nome_militar_atual)

                pode_cancelar_24h = False
                horas_decorridas = 999
                if eh_pendente_aceite and remetente_ult == nome_militar_atual and dt_envio_str:
                    try:
                        dt_envio_obj = pd.to_datetime(dt_envio_str)
                        delta = datetime.datetime.now() - dt_envio_obj.to_pydatetime().replace(tzinfo=None)
                        horas_decorridas = delta.total_seconds() / 3600.0
                        if horas_decorridas <= 24.0:
                            pode_cancelar_24h = True
                    except Exception:
                        pass

                # ALTERNÂNCIA DE COR POR ITEM (AZUL VS BEGE/DOURADO)
                e_marrom = (idx_i % 2 != 0)
                classe_card = "card-brown" if e_marrom else "card-blue"

                if eh_pendente_aceite:
                    status_badge = f"⏳ <b>Aguardando Aceite de:</b> {dest_pendente}"
                elif eh_ja_aceito:
                    status_badge = f"🔒 <b>Aceito por:</b> {fiel_dep_atual} ({item_bem.get('unidade_posse_atual')})"
                elif id_bem_key in ids_no_carrinho:
                    status_badge = f"📌 <b>Selecionado para Envio</b>"
                else:
                    itens_livres_para_envio.append(item_bem)
                    status_badge = f"🎒 <b>Em Custódia de:</b> {fiel_dep_atual}"

                card_html = f"""
                <div class="{classe_card}">
                    📄 REDS: <b>{reds_codigo}</b> | Material: <b>{item_bem.get('descricao')}</b><br/>
                    <small>Lacre: <b>{item_bem.get('involucro_lacre', 'N/I')}</b> | Qtd: <b>{item_bem.get('quantidade', 1.0)} {item_bem.get('unidade_medida', 'UN')}</b> | {str_midias}</small><br/>
                    📍 Status: {status_badge}
                </div>
                """
                
                st.markdown(card_html, unsafe_allow_html=True)

                c_act_col1, c_act_col2 = st.columns([3.8, 1.2])
                with c_act_col2:
                    # BOTÃO DE ACEITAR MATERIAL SE FOR DESTINATÁRIO PENDENTE OU GESTOR DO ESCOPO
                    if eh_pendente_aceite and (
                        nome_militar_atual.lower() in str(dest_pendente).lower() or
                        unidade_militar_atual.lower() in str(dest_pendente).lower() or
                        unidade_militar_atual.lower() in str(item_bem.get("unidade_destinatario_pendente", "")).lower() or
                        eh_soberano or eh_gestor_cia
                    ):
                        if st.button("✅ Aceitar & Incorporar", key=f"btn_aceitar_{id_bem_key}_{idx_r}_{idx_i}", type="primary", use_container_width=True):
                            now_iso = datetime.datetime.now().isoformat()
                            upd_aceite = {
                                "status_tramite": "Em Custódia",
                                "fiel_depositario_atual": nome_militar_atual,
                                "unidade_posse_atual": unidade_militar_atual,
                                "destinatario_pendente": None,
                                "unidade_destinatario_pendente": None,
                                "data_posse_atual": now_iso
                            }
                            if atualizar_material_supabase(id_bem_key, upd_aceite):
                                registrar_log_supabase({
                                    "data_hora": now_iso,
                                    "num_reds": reds_codigo,
                                    "bem_id": id_bem_key,
                                    "web_origem": "SIOP_TCO",
                                    "acao": "ACEITE E INCORPORAÇÃO DE CUSTÓDIA",
                                    "origem": remetente_ult,
                                    "unidade_origem": item_bem.get("unidade_remetente", "N/I"),
                                    "destino": nome_militar_atual,
                                    "unidade_destino": unidade_militar_atual,
                                    "detalhe": f"Material '{item_bem.get('descricao')}' aceito e incorporado por {nome_militar_atual} ({unidade_militar_atual})."
                                })
                                st.toast("Material aceito e incorporado com sucesso!", icon="✅")
                                st.rerun()

                    elif eh_pendente_aceite and pode_cancelar_24h and remetente_ult == nome_militar_atual:
                        if st.button("↩️ Cancelar Envio", key=f"btn_canc_24h_{id_bem_key}_{idx_r}_{idx_i}", use_container_width=True):
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
                    elif not eh_ja_aceito and (fiel_dep_atual == nome_militar_atual or eh_soberano or eh_gestor_cia):
                        if st.button("✏️ Editar Material", key=f"btn_ed_uni_{id_bem_key}_{idx_r}_{idx_i}", use_container_width=True):
                            abrir_modal_edicao_material(item_bem, nome_militar_atual, unidade_militar_atual)

                st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)

            # QUADRO DE ENCAMINHAMENTO
            if itens_livres_para_envio:
                st.markdown("---")
                st.markdown("##### 🏛️ Encaminhar / Tramitar Materiais Disponíveis:")

                col_dest1, col_dest2 = st.columns([2, 2.5])

                with col_dest1:
                    destinatario_selecionado = st.selectbox(
                        "Selecione o Destinatário Final ou Unidade CREDS:",
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

            # CONFIRMAÇÃO DA TRAMITAÇÃO
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
                    placeholder="Ex: Encaminhado para o depósito CREDS TCO da Cia / Destino Final", 
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