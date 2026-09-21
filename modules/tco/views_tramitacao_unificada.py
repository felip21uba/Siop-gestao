import streamlit as st
import pandas as pd
import datetime
from modules.tco.database import atualizar_material_supabase, registrar_log_supabase
from modules.tco.modais import abrir_modal_edicao_material
from modules.tco.views import obter_lista_creds_dinamica, injetar_css_cards_alternados

def renderizar_aba_custodia_tramitacao_unificada(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    """Módulo unificado de Custódia e Tramitação Granular por REDS."""
    injetar_css_cards_alternados()

    st.markdown(f"#### 🎒 Gestão de Custódia & Tramitação de: **{nome_militar_atual}**")

    # Lista de Destinatários Elegíveis
    unidades_creds_destino = obter_lista_creds_dinamica()
    mils_todos = st.session_state.get("lista_militares", [])
    nomes_mils_base = [f"{m.get('posto_grad')} {m.get('nome_guerra')}" for m in mils_todos] if mils_todos else []
    
    opcoes_destinatarios_todas = ["Manter em Minha Custódia"] + unidades_creds_destino + [n for n in nomes_mils_base if n != nome_militar_atual]

    # 1. FILTROS DE PESQUISA
    with st.expander("🔍 **Filtros de Pesquisa na Custódia**", expanded=False):
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            q_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-000484967", key="f_uni_reds").strip()
        with c_f2:
            q_dest = st.text_input("Destinatário / Encaminhamento:", placeholder="Ex: CREDS TCO", key="f_uni_dest").strip()
        with c_f3:
            q_data = st.date_input("Data de Ingestão / Tramitação:", value=None, key="f_uni_data")

    # Filtra materiais que estão sob posse do militar ou enviados por ele
    meus_bens = [
        b for b in all_bens_banco 
        if b.get("fiel_depositario_atual") == nome_militar_atual or b.get("remetente_ultimo") == nome_militar_atual
    ]

    # Aplica os filtros
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

    # Ordena pelos últimos 10 REDSs
    reds_ordenados = sorted(
        reds_agrupados.items(),
        key=lambda x: max([b.get("data_ingestao") or b.get("data_posse_atual") or "" for b in x[1]]),
        reverse=True
    )[:10]

    st.caption(f"Exibindo os **{len(reds_ordenados)} último(s) REDS** ativos para tramitação:")

    # 2. RENDERIZAÇÃO POR EXPANDERS DE REDS
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
            st.caption("Você pode desempenhar a destinação **individual por item** ou aplicar para **todos do REDS**.")

            # Atalho de Aplicação em Bloco para todo o REDS
            c_blk1, c_blk2 = st.columns([3, 1.5])
            with c_blk1:
                destino_bloco = st.selectbox(
                    "Aplicar mesmo destino para TODOS os itens deste REDS:",
                    options=["-- Selecionar Destino em Bloco --"] + opcoes_destinatarios_todas[1:],
                    key=f"sb_bloco_dest_{reds_codigo}_{idx_r}"
                )
            with c_blk2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                btn_aplicar_bloco = st.button("⚡ Aplicar ao REDS", key=f"btn_blk_{reds_codigo}_{idx_r}", use_container_width=True)

            if btn_aplicar_bloco and destino_bloco != "-- Selecionar Destino em Bloco --":
                for item in itens_reds:
                    st.session_state[f"dest_item_{item['id_bem']}"] = destino_bloco
                st.toast("Destino em bloco selecionado para a lista abaixo!", icon="✅")

            st.divider()

            # Renderização Granular Item por Item
            destinos_finais_mapeados = {}
            
            for idx_i, item_bem in enumerate(itens_reds):
                id_bem_key = item_bem["id_bem"]
                midias = item_bem.get("midias_anexas") or []
                str_midias = f"📎 <b>{len(midias)} foto(s) anexa(s)</b>" if midias else "Sem mídias"

                c_item1, c_item2, c_item3 = st.columns([3, 2, 1])

                with c_item1:
                    st.markdown(f"**Item {idx_i+1}:** {item_bem.get('descricao')}  \n"
                                f"<small>Lacre: **{item_bem.get('involucro_lacre', 'SEM LACRE')}** | Qtd: **{item_bem.get('quantidade', 1.0)} {item_bem.get('unidade_medida', 'UN')}** | {str_midias}</small>", 
                                unsafe_allow_html=True)

                with c_item2:
                    # Chave de estado individual para cada material
                    key_dest_item = f"dest_item_{id_bem_key}"
                    dest_atual_item = st.session_state.get(key_dest_item, "Manter em Minha Custódia")

                    idx_pref = opcoes_destinatarios_todas.index(dest_atual_item) if dest_atual_item in opcoes_destinatarios_todas else 0

                    dest_escolhido = st.selectbox(
                        "Destino deste material:",
                        options=opcoes_destinatarios_todas,
                        index=idx_pref,
                        key=key_dest_item,
                        label_visibility="collapsed"
                    )
                    destinos_finais_mapeados[id_bem_key] = dest_escolhido

                with c_item3:
                    if st.button("✏️ Editar", key=f"btn_ed_uni_{id_bem_key}_{idx_r}_{idx_i}", use_container_width=True):
                        abrir_modal_edicao_material(item_bem, nome_militar_atual, unidade_militar_atual)

                st.markdown("<hr style='margin: 6px 0; border-color: #334155;'>", unsafe_allow_html=True)

            # Botão Único de Confirmação de Tramitação do REDS
            st.markdown("<br>", unsafe_allow_html=True)
            obs_tram_reds = st.text_input("Observação da Tramitação deste REDS:", placeholder="Ex: Encaminhado para o depósito CREDS TCO da Cia", key=f"obs_uni_{reds_codigo}_{idx_r}")
            
            btn_confirmar_tramitacao = st.button(
                f"🚀 Confirmar Envio e Tramitar Materiais do REDS {reds_codigo}",
                type="primary",
                key=f"btn_conf_tram_{reds_codigo}_{idx_r}",
                use_container_width=True
            )

            if btn_confirmar_tramitacao:
                now_iso = datetime.datetime.now().isoformat()
                sucessos_tram = 0

                for item_bem in itens_reds:
                    id_bem_target = item_bem["id_bem"]
                    destino_definido = destinos_finais_mapeados.get(id_bem_target, "Manter em Minha Custódia")

                    if destino_definido != "Manter em Minha Custódia":
                        upd_data = {
                            "status_tramite": "Pendente Aceite",
                            "remetente_ultimo": nome_militar_atual,
                            "unidade_remetente": unidade_militar_atual,
                            "destinatario_pendente": destino_definido,
                            "unidade_destinatario_pendente": unidade_militar_atual,
                            "data_envio_tramite": now_iso,
                            "obs_tramite": obs_tram_reds
                        }

                        if atualizar_material_supabase(id_bem_target, upd_data):
                            registrar_log_supabase({
                                "data_hora": now_iso,
                                "num_reds": reds_codigo,
                                "bem_id": id_bem_target,
                                "acao": "SOLICITAÇÃO DE TRAMITAÇÃO GRANULAR",
                                "origem": nome_militar_atual,
                                "unidade_origem": unidade_militar_atual,
                                "destino": destino_definido,
                                "unidade_destino": unidade_militar_atual,
                                "detalhe": f"Material '{item_bem.get('descricao')}' tramitado para {destino_definido}. Obs: {obs_tram_reds}"
                            })
                            sucessos_tram += 1

                if sucessos_tram > 0:
                    st.success(f"✅ Tramitação de {sucessos_tram} material(is) do REDS {reds_codigo} confirmada com sucesso!")
                    st.rerun()
                else:
                    st.warning("Nenhum material do REDS teve destino alterado para tramitação.")