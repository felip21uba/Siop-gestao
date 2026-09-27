import streamlit as st
import pandas as pd
import datetime
from core.database import supabase, carregar_militares_supabase
from modules.tco.database import registrar_log_tco, atualizar_posse_material

def carregar_lista_unidades_creds():
    """Carrega dinamicamente a lista de CIAs, Batalhões e Órgãos Externos para o CREDS-TC."""
    unidades_padrao = [
        "CREDS-TC / 35ª CIA PM (UBÁ)",
        "CREDS-TC / 111ª CIA PM (VRB)",
        "CREDS-TC / 285ª CIA TM (UBÁ)",
        "CREDS-TC / 21º BPM (SEÇÃO DE CUSTÓDIA)",
        "DELEGACIA DE POLÍCIA CIVIL (PCMG)",
        "PODER JUDICIÁRIO / TRIBUNAL DE JUSTIÇA",
        "PERÍCIA TÉCNICA / PERÍCIA OFICIAL",
        "MINISTÉRIO PÚBLICO (MPMG)",
        "OUTRO ÓRGÃO EXTERNO"
    ]
    if not supabase:
        return unidades_padrao

    try:
        res = supabase.table("usuarios").select("unidade").execute()
        if res.data:
            unidades_banco = sorted(list(set([
                f"CREDS-TC / {u.get('unidade').strip().upper()}" 
                for u in res.data if u.get("unidade")
            ])))
            for u in unidades_padrao:
                if u not in unidades_banco:
                    unidades_banco.append(u)
            return unidades_banco
        return unidades_padrao
    except Exception:
        return unidades_padrao


def renderizar_aba_custodia_tramitacao_unificada(all_bens, nome_militar_atual, unidade_militar_atual):
    """
    Renderiza a Aba de Custódia Física agrupada por REDS (+) com suporte a 
    múltiplas tramitações por seleção individual de destinos.
    """
    st.subheader("🎒 Custódia Física & Tramitação Unificada")
    st.caption("Gerencie os bens em sua posse, filtre por REDS e selecione os destinos individuais para cada item antes de confirmar o envio.")

    # Filtra os bens que estão em posse/custódia do operador/unidade
    usr_logado = st.session_state.get("usuario_dados", {})
    num_pm_logado = str(usr_logado.get("usuario_login") or usr_logado.get("usuario") or "").strip().upper()

    bens_posse = []
    for b in all_bens:
        posse_atual = str(b.get("fiel_depositario_atual") or b.get("unidade_posse_atual") or "").upper()
        if num_pm_logado in posse_atual or nome_militar_atual.upper() in posse_atual or unidade_militar_atual in posse_atual or "CUSTÓDIA" in posse_atual:
            bens_posse.append(b)

    # Se a lista filtrada estiver vazia, carrega todos os bens em custódia ativa como fallback
    if not bens_posse:
        bens_posse = [b for b in all_bens if b.get("status_tramite") != "Arquivado/Destinado"]

    if not bens_posse:
        st.info("ℹ️ Nenhum material sob sua custódia física no momento.")
        return

    st.markdown(f"##### 🎒 Seus Bens em Custódia Física ({len(bens_posse)} item/ns)")

    # Agrupamento dos bens pelo número do REDS
    df_bens = pd.DataFrame(bens_posse)
    grupos_reds = df_bens.groupby("num_reds")

    # Dicionário de estado para guardar seleções do operador
    if "itens_selecionados_tramite" not in st.session_state:
        st.session_state["itens_selecionados_tramite"] = {}

    # Listas de apoio para as caixas de seleção do formulário
    lista_militares = carregar_militares_supabase() or []
    opcoes_militares = [f"{m.get('posto_grad', 'PM')} {m.get('nome_guerra', 'MILITAR')} ({m.get('num_policia', '')})" for m in lista_militares]
    if not opcoes_militares:
        opcoes_militares = [f"{nome_militar_atual} ({num_pm_logado})"]

    lista_unidades_creds = carregar_lista_unidades_creds()

    fases_destinacao_opcoes = [
        "Com Fiel Depositário / Policial",
        "Encaminhado ao CREDS-TC / Custódia",
        "Encaminhado à Polícia Civil (PCMG)",
        "Entregue ao Poder Judiciário / Fórum",
        "Encaminhado para Perícia Técnica",
        "Devolvido ao Proprietário"
    ]

    # Renderização da lista agrupada por REDS (+)
    for num_reds, df_grupo in grupos_reds:
        qtd_itens_reds = len(df_grupo)
        
        with st.expander(f"➕ **REDS: {num_reds}** ({qtd_itens_reds} item/ns apreendido/s)", expanded=False):
            for idx, row in df_grupo.iterrows():
                id_bem = str(row.get("id_bem") or row.get("id"))
                desc = str(row.get("descricao", "SEMA DESCRIÇÃO")).strip()
                qtd = row.get("quantidade", 1)
                unid = row.get("unidade_medida", "UN")
                lacre = str(row.get("involucro_lacre", "SEM LACRE")).strip()
                autor = str(row.get("autores", "N/I")).strip()

                c_chk, c_info = st.columns([0.5, 9.5])
                
                with c_chk:
                    is_selected = st.checkbox(
                        "Tramitar", 
                        key=f"chk_tramite_{id_bem}",
                        label_visibility="collapsed"
                    )

                with c_info:
                    st.markdown(f"**Item:** {desc} | **Qtd:** {qtd} {unid} | **Lacre:** `{lacre}` | **Autor:** `{autor}`")

                # Se o item foi marcado com a checkbox, guarda no dicionário de tramitação ativa
                if is_selected:
                    st.session_state["itens_selecionados_tramite"][id_bem] = row.to_dict()
                else:
                    st.session_state["itens_selecionados_tramite"].pop(id_bem, None)

    st.markdown("---")

    # =========================================================================
    # 🔄 PAINEL DE DEFINIÇÃO DE DESTINOS PARA OS ITENS SELECIONADOS
    # =========================================================================
    selecionados_map = st.session_state["itens_selecionados_tramite"]
    qtd_sel = len(selecionados_map)

    if qtd_sel > 0:
        st.markdown(f"### 🔄 Tramitar {qtd_sel} item(ns) Selecionado(s)")
        
        with st.form("form_tramitacao_unificada_tco", clear_on_submit=False):
            st.caption("Escolha a forma de tramitação e o destino para os itens selecionados acima.")

            col_tipo, col_fase = st.columns(2)

            with col_tipo:
                tipo_destinatario = st.radio(
                    "Tipo de Destinatário:",
                    ["Policial Militar / Fiel Depositário", "Unidade / CREDS / Órgão Externo"],
                    horizontal=True
                )

            with col_fase:
                fase_destinacao_sel = st.selectbox(
                    "Atualizar Fase de Destinação:",
                    fases_destinacao_opcoes
                )

            col_dest, col_obs = st.columns(2)

            with col_dest:
                if tipo_destinatario == "Policial Militar / Fiel Depositário":
                    destinatario_final = st.selectbox(
                        "Selecione o Policial Destinatário:",
                        opcoes_militares
                    )
                    unidade_dest_final = unidade_militar_atual
                else:
                    destinatario_final = st.selectbox(
                        "Selecione a Unidade / CREDS-TC / Órgão Destinatário:",
                        lista_unidades_creds
                    )
                    unidade_dest_final = destinatario_final

            with col_obs:
                obs_tramite = st.text_input(
                    "Observações / Motivo da Transferência:",
                    placeholder="Ex: Encaminhado para contraperícia ou custódia no CREDS-TC"
                ).strip()

            st.markdown("<br>", unsafe_allow_html=True)
            btn_confirmar_envio = st.form_submit_button("🚀 Confirmar Envio / Tramitação", type="primary", use_container_width=True)

            if btn_confirmar_envio:
                agora_iso = datetime.datetime.now().isoformat()
                sucessos = 0

                for id_bem, dados_item in selecionados_map.items():
                    res_ok = atualizar_posse_material(
                        id_bem=id_bem,
                        novo_destinatario=destinatario_final,
                        nova_unidade_destinatario=unidade_dest_final,
                        nova_fase=fase_destinacao_sel,
                        status_tramite="Pendente de Aceite" if "Policial" in tipo_destinatario else "Em Tramitação"
                    )

                    if res_ok:
                        sucessos += 1
                        registrar_log_tco(
                            num_reds=dados_item.get("num_reds", "N/I"),
                            bem_id=id_bem,
                            acao="TRAMITACAO_ENVIADA",
                            origem=nome_militar_atual,
                            unidade_origem=unidade_militar_atual,
                            destino=destinatario_final,
                            unidade_destino=unidade_dest_final,
                            detalhe=f"Fase: {fase_destinacao_sel} | Obs: {obs_tramite or 'Sem obs'}"
                        )

                if sucessos > 0:
                    st.success(f"🎉 {sucessos} material(is) tramitado(s) com sucesso para **{destinatario_final}**!")
                    st.session_state["itens_selecionados_tramite"] = {}
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Ocorreu um erro ao atualizar os registros no Supabase.")
    else:
        st.info("💡 Abra o expander `➕ REDS` acima e marque a caixa de seleção dos itens que deseja tramitar.")