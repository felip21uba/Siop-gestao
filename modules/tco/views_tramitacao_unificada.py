import streamlit as st
import pandas as pd
import datetime
import re
from core.database import supabase, carregar_militares_supabase
from core.permissions import usuario_eh_gestor_creds
from modules.tco.database import registrar_log_supabase, atualizar_material_supabase


def extrair_partes_unidade(str_unidade):
    """Extrai partes de Cia, Batalhão e Seções a partir da string cadastrada no banco."""
    if not str_unidade or str_unidade == "None":
        return []
    
    partes_encontradas = set()
    raw = str(str_unidade).strip().upper()

    # Separa por barra '/' caso esteja cadastrado como '21º BPM / 35ª CIA PM'
    fragmentos = [p.strip() for p in raw.split('/') if p.strip()]
    for frag in fragmentos:
        if "BPM" in frag or "CIA" in frag or "TM" in frag or "PEL" in frag:
            partes_encontradas.add(f"CREDS {frag}")
        elif frag:
            partes_encontradas.add(f"CREDS {frag}")

    return list(partes_encontradas)


def carregar_lista_unidades_creds_dinamica(unidade_militar_atual=""):
    """
    Lê a coluna 'unidade' da tabela 'usuarios' no Supabase e gera a lista
    de CREDS-TC e Órgãos Externos dinamicamente.
    """
    orgaos_externos = [
        "DELEGACIA DE POLÍCIA CIVIL (PCMG)",
        "PODER JUDICIÁRIO / TRIBUNAL DE JUSTIÇA (JECRIM)",
        "PERÍCIA TÉCNICA / PERÍCIA OFICIAL",
        "MINISTÉRIO PÚBLICO (MPMG)",
        "OUTRO ÓRGÃO EXTERNO (ESPECIFICAR NAS OBSERVAÇÕES)"
    ]

    unidades_creds_set = set()

    # Adiciona a unidade do operador logado
    if unidade_militar_atual:
        for u_fmt in extrair_partes_unidade(unidade_militar_atual):
            unidades_creds_set.add(u_fmt)

    # Consulta a tabela 'usuarios' no Supabase
    if supabase:
        try:
            res_u = supabase.table("usuarios").select("unidade").execute()
            if res_u.data:
                for row in res_u.data:
                    u_db = row.get("unidade")
                    if u_db:
                        for u_fmt in extrair_partes_unidade(u_db):
                            unidades_creds_set.add(u_fmt)
        except Exception as e_db:
            print(f"Aviso ao consultar unidades da tabela usuarios: {e_db}")

    # Fallback com unidades padrão caso o banco não retorne registros
    if not unidades_creds_set:
        unidades_creds_set.add("CREDS 35ª CIA PM")
        unidades_creds_set.add("CREDS 111ª CIA PM")
        unidades_creds_set.add("CREDS 285ª CIA TM")
        unidades_creds_set.add("CREDS 21º BPM")

    lista_creds_ordenada = sorted(list(unidades_creds_set))
    return lista_creds_ordenada + orgaos_externos


def renderizar_aba_custodia_tramitacao_unificada(all_bens, nome_militar_atual, unidade_militar_atual):
    """
    Renderiza a Aba de Custódia Física com alternância garantida de rótulos e listas
    de destinatários entre Policial Militar vs CREDS/Órgão Externo.
    """
    st.subheader("🎒 Custódia Física & Tramitação Unificada")
    st.caption("Gerencie os bens em sua posse, envie materiais para outros militares/CREDS e consulte seu histórico de envios.")

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

    # =========================================================================
    # ABA 1: TRAMITAR MATERIAIS
    # =========================================================================
    with tab_pendentes:
        bens_posse = []
        for b in all_bens:
            posse_atual = str(b.get("fiel_depositario_atual") or b.get("unidade_posse_atual") or "").upper()
            if num_pm_logado in posse_atual or nome_militar_atual.upper() in posse_atual or unidade_militar_atual in posse_atual or "CUSTÓDIA" in posse_atual:
                bens_posse.append(b)

        if not bens_posse:
            bens_posse = [b for b in all_bens if b.get("status_tramite") != "Arquivado/Destinado"]

        if not bens_posse:
            st.info("ℹ️ Nenhum material sob sua custódia física no momento.")
        else:
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

            # Carrega dinamicamente a lista de CREDS a partir da tabela 'usuarios'
            lista_unidades_creds = carregar_lista_unidades_creds_dinamica(unidade_militar_atual)

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
                                "Tramitar", 
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

            # FORMULÁRIO DE ENVIO
            selecionados_map = st.session_state["itens_selecionados_tramite"]
            qtd_sel = len(selecionados_map)

            if qtd_sel > 0:
                st.markdown(f"### 🔄 Tramitar {qtd_sel} item(ns) Selecionado(s)")
                
                with st.form("form_tramitacao_unificada_tco", clear_on_submit=False):
                    st.caption("Escolha o tipo de destinatário e selecione o destino dos itens selecionados acima.")

                    col_tipo, col_fase = st.columns([1.2, 1])

                    with col_tipo:
                        tipo_destinatario = st.radio(
                            "Tipo de Destinatário:",
                            ["Policial Militar / Fiel Depositário", "Seção de Custódia (CREDS-TC / Órgão)"],
                            horizontal=True
                        )

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
                                ]
                            )
                        else:
                            if "Policial" in tipo_destinatario:
                                fase_destinacao_sel = "Com Fiel Depositário / Policial"
                            else:
                                fase_destinacao_sel = "Aguardando no CREDS-TC / Custódia"
                            
                            st.text_input("Fase de Destinação:", value=fase_destinacao_sel, disabled=True)

                    col_dest, col_obs = st.columns(2)

                    # ALTERNÂNCIA ESTRITA DA CAIXA DE SELEÇÃO:
                    # Avalia explicitamente se a opção 'Seção de Custódia' está selecionada
                    eh_opcao_creds = "Seção" in tipo_destinatario or "CREDS" in tipo_destinatario or "Órgão" in tipo_destinatario

                    with col_dest:
                        if eh_opcao_creds:
                            destinatario_final = st.selectbox(
                                "Selecione a Unidade / CREDS Destinatário:",
                                lista_unidades_creds,
                                index=None,
                                placeholder="Escolha a unidade CREDS-TC ou órgão..."
                            )
                            unidade_dest_final = destinatario_final or "CREDS / ÓRGÃO EXTERNO"
                        else:
                            destinatario_final = st.selectbox(
                                "Selecione o Policial Destinatário:",
                                opcoes_militares,
                                index=None,
                                placeholder="Digite qualquer parte do nome do militar..."
                            )
                            unidade_dest_final = unidade_militar_atual

                    with col_obs:
                        obs_tramite = st.text_input(
                            "Observações / Motivo da Transferência:",
                            placeholder="Ex: Passagem de serviço ou entrega na Seção de Custódia"
                        ).strip()

                    st.markdown("<br>", unsafe_allow_html=True)
                    btn_confirmar_envio = st.form_submit_button("🚀 Confirmar Envio / Tramitação", type="primary", use_container_width=True)

                    if btn_confirmar_envio:
                        if not destinatario_final:
                            st.error("⚠️ Por favor, selecione um destinatário antes de confirmar o envio.")
                        else:
                            agora_iso = datetime.datetime.now().isoformat()
                            sucessos = 0

                            for id_bem, dados_item in selecionados_map.items():
                                payload_update = {
                                    "destinatario_pendente": destinatario_final,
                                    "unidade_destinatario_pendente": unidade_dest_final,
                                    "data_envio_tramite": agora_iso,
                                    "fase_destinacao": fase_destinacao_sel,
                                    "remetente_ultimo": nome_militar_atual,
                                    "unidade_remetente": unidade_militar_atual,
                                    "status_tramite": "Pendente de Aceite" if not eh_opcao_creds else "Em Tramitação"
                                }

                                if atualizar_material_supabase(id_bem, payload_update):
                                    sucessos += 1
                                    registrar_log_supabase({
                                        "data_hora": agora_iso,
                                        "num_reds": dados_item.get("num_reds", "N/I"),
                                        "bem_id": id_bem,
                                        "web_origem": "SIOP_TCO",
                                        "acao": "TRAMITACAO_ENVIADA",
                                        "origem": nome_militar_atual,
                                        "unidade_origem": unidade_militar_atual,
                                        "destino": destinatario_final,
                                        "unidade_destino": unidade_dest_final,
                                        "detalhe": f"Fase: {fase_destinacao_sel} | Detalhes/Obs: {obs_tramite or 'Sem obs'}"
                                    })

                            if sucessos > 0:
                                st.success(f"🎉 {sucessos} material(is) tramitado(s) com sucesso para **{destinatario_final}**!")
                                st.session_state["itens_selecionados_tramite"] = {}
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("❌ Ocorreu um erro ao atualizar os registros no Supabase.")

    # =========================================================================
    # ABA 2: HISTÓRICO DE ENVIOS & CANCELAMENTO (REGRA DAS 72H)
    # =========================================================================
    with tab_historico:
        st.markdown("##### 📜 Histórico de Tramitações Enviadas por Você")
        st.caption("Consulte os envios realizados, filtre por REDS/período e cancele tramitações pendentes de aceite em até 72 horas.")

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
            remetente = str(b.get("remetente_ultimo") or b.get("fiel_depositario_atual") or "").upper()
            if num_pm_logado in remetente or nome_militar_atual.upper() in remetente or b.get("destinatario_pendente"):
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
            
            reds_unicos_10 = list(df_hist["num_reds"].unique())[:10]
            df_10_reds = df_hist[df_hist["num_reds"].isin(reds_unicos_10)]

            agora_now = datetime.datetime.now()

            for num_reds_h, df_grupo_h in df_10_reds.groupby("num_reds", sort=False):
                qtd_h = len(df_grupo_h)
                
                with st.container(border=True):
                    st.markdown(f"📄 **REDS: {num_reds_h}** ({qtd_h} item/ns)")
                    
                    for idx_h, item_h in df_grupo_h.iterrows():
                        id_bem_h = str(item_h.get("id_bem") or item_h.get("id"))
                        desc_h = item_h.get("descricao", "N/I")
                        qtd_h_val = item_h.get("quantidade", 1)
                        dest_h = item_h.get("destinatario_pendente") or item_h.get("fiel_depositario_atual") or "N/I"
                        status_h = item_h.get("status_tramite", "Em Tramitação")
                        dt_env_str = item_h.get("data_envio_tramite") or item_h.get("data_posse_atual")

                        pode_cancelar = False
                        tempo_restante_str = ""

                        if dt_env_str and status_h == "Pendente de Aceite":
                            try:
                                dt_env_obj = pd.to_datetime(dt_env_str).to_pydatetime().replace(tzinfo=None)
                                horas_passadas = (agora_now - dt_env_obj).total_seconds() / 3600.0
                                if horas_passadas <= 72.0:
                                    pode_cancelar = True
                                    horas_restantes = max(0.0, 72.0 - horas_passadas)
                                    tempo_restante_str = f"{int(horas_restantes)}h {int((horas_restantes % 1)*60)}m restantes para cancelamento"
                                else:
                                    tempo_restante_str = "Prazo de 72h expirado"
                            except Exception:
                                pode_cancelar = False

                        col_info_h, col_act_h = st.columns([7, 3])
                        
                        with col_info_h:
                            st.markdown(
                                f"• **Material:** {desc_h} (Qtd: {qtd_h_val})  \n"
                                f"• **Destinatário:** `{dest_h}` | **Status:** `{status_h}`"
                            )
                            if tempo_restante_str:
                                st.caption(f"⏱️ {tempo_restante_str}")

                        with col_act_h:
                            if pode_cancelar:
                                if st.button("❌ Cancelar Envio", key=f"btn_canc_{id_bem_h}", type="primary", use_container_width=True):
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