import streamlit as st
import pandas as pd
import datetime
from modules.tco.database import atualizar_material_supabase, registrar_log_supabase
from modules.tco.modais import abrir_modal_edicao_material

def renderizar_aba_meus_bens(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    """Renderiza a aba 'Meus Materiais' com visual expansível por REDS e lista limpa de itens."""
    st.markdown(f"#### 🎒 Materiais em Custódia de: **{nome_militar_atual}**")

    # 1. FILTROS DE PESQUISA
    with st.expander("🔍 **Filtros de Pesquisa na Custódia**", expanded=False):
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            q_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-000484967", key="f_meus_reds").strip()
        with c_f2:
            q_dest = st.text_input("Destinatário / Encaminhamento:", placeholder="Ex: CREDS TCO - 35ª CIA", key="f_meus_dest").strip()
        with c_f3:
            q_data = st.date_input("Data de Ingestão / Encaminhamento:", value=None, key="f_meus_data")

    # Filtra materiais do militar ativo
    meus_bens = [
        b for b in all_bens_banco 
        if b.get("fiel_depositario_atual") == nome_militar_atual or b.get("remetente_ultimo") == nome_militar_atual
    ]

    # Aplica os filtros de pesquisa
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

    # Agrupa por REDS
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

    # 2. RENDERIZAÇÃO DOS EXPANDERS POR REDS
    for idx_r, (reds_codigo, itens_reds) in enumerate(reds_ordenados):
        primeiro_item = itens_reds[0]
        
        # Data do REDS
        data_bruta = primeiro_item.get("data_ingestao") or primeiro_item.get("data_posse_atual") or ""
        try:
            data_fmt = pd.to_datetime(data_bruta).strftime("%d/%m/%Y") if data_bruta else "Data N/I"
        except Exception:
            data_fmt = str(data_bruta)[:10] if data_bruta else "Data N/I"

        autor_fmt = primeiro_item.get("autores") or "AUTOR NÃO INFORMADO"
        destinacao_fmt = primeiro_item.get("destinatario_pendente") or primeiro_item.get("fase_destinacao") or "Com Fiel Depositário"
        
        dt_envio_raw = primeiro_item.get("data_envio_tramite") or primeiro_item.get("data_posse_atual") or ""
        try:
            dt_envio_fmt = pd.to_datetime(dt_envio_raw).strftime("%d/%m/%Y %H:%M") if dt_envio_raw else ""
        except Exception:
            dt_envio_fmt = str(dt_envio_raw)[:16] if dt_envio_raw else ""

        encaminhamento_str = f"{destinacao_fmt}" + (f" em {dt_envio_fmt}" if dt_envio_fmt else "")

        # Cabeçalho do Expander com as Informações Principais
        label_expander = f"📄 REDS: {reds_codigo}  |  🗓️ Data: {data_fmt}  |  👤 Autor: {autor_fmt}  |  🏛️ Encaminhado: {encaminhamento_str} ({len(itens_reds)} item/ns)"

        with st.expander(label_expander, expanded=(idx_r == 0)):
            # Monta a tabela limpa dos materiais
            df_itens = pd.DataFrame(itens_reds)
            
            # Adiciona colunas amigáveis
            df_itens["midias_count"] = df_itens["midias_anexas"].apply(lambda x: len(x) if isinstance(x, list) else 0)
            df_itens["midias_txt"] = df_itens["midias_count"].apply(lambda x: f"📎 {x} foto(s)" if x > 0 else "Sem mídias")

            # Tabela Limpa de Materiais
            df_exibicao = st.data_editor(
                df_itens[["descricao", "quantidade", "unidade_medida", "involucro_lacre", "midias_txt"]],
                column_config={
                    "descricao": st.column_config.TextColumn("Descrição do Material", disabled=True, width="large"),
                    "quantidade": st.column_config.NumberColumn("Qtd", disabled=True, width="small"),
                    "unidade_medida": st.column_config.TextColumn("Unid", disabled=True, width="small"),
                    "involucro_lacre": st.column_config.TextColumn("Nº Invólucro / Lacre", disabled=True, width="medium"),
                    "midias_txt": st.column_config.TextColumn("Mídias / Anexos", disabled=True, width="medium")
                },
                hide_index=True,
                use_container_width=True,
                key=f"editor_meus_mats_{reds_codigo}_{idx_r}"
            )

            # Botão individual de edição alinhado
            st.caption("⚙️ **Ações Individuais do Material:**")
            col_sel, col_btn = st.columns([3, 1.5])
            
            with col_sel:
                opcoes_itens_reds = {
                    f"{b['descricao']} (Qtd: {b['quantidade']} {b.get('unidade_medida', 'UN')}) - Lacre: {b.get('involucro_lacre', 'N/I')}": b
                    for b in itens_reds
                }
                item_sel_key = st.selectbox(
                    "Selecione o material para editar ou anexar mídias:",
                    options=list(opcoes_itens_reds.keys()),
                    key="sb_item_edit_" + str(reds_codigo) + "_" + str(idx_r),
                    label_visibility="collapsed"
                )
            
            with col_btn:
                if st.button("✏️ Editar / Anexar Mídias", key=f"btn_edit_item_{reds_codigo}_{idx_r}", use_container_width=True):
                    bem_alvo = opcoes_itens_reds[item_sel_key]
                    abrir_modal_edicao_material(bem_alvo, nome_militar_atual, unidade_militar_atual)