import streamlit as st
import pandas as pd
import datetime
from core.database import supabase, carregar_militares_supabase, registrar_audit_log
from modules.tco.database import salvar_material_supabase, registrar_log_supabase

def obter_unidades_disponiveis():
    """Retorna lista de unidades e CREDS para seleção no envio de materiais."""
    unidades_base = [
        "35ª CIA PM",
        "111ª CIA PM",
        "285ª CIA TM",
        "21º BPM",
        "CENTRAL DE CUSTÓDIA",
        "CREDS TCO - 35ª CIA PM",
        "CREDS TCO - 111ª CIA PM",
        "CREDS TCO - 285ª CIA TM",
        "CREDS TCO - 21º BPM",
        "POLÍCIA CIVIL / DELEGACIA",
        "PERÍCIA TÉCNICA",
        "JECRIM / FÓRUM"
    ]
    return unidades_base

def renderizar_aba_custodia_tramitacao_unificada(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    st.markdown("#### 🎒 Meus Materiais & Tramitação de Custódia")
    st.caption("Gerencie seus bens em custódia física, confirme recebimentos pendentes ou cancele envios antes do aceite.")

    if not all_bens_banco:
        st.info("Nenhum material em custódia localizado no banco de dados.")
        return

    # Separação dos bens por status em relação ao militar logado
    bens_em_posse = []
    bens_aguardando_meu_aceite = []
    bens_enviados_aguardando_aceite = []

    militar_clean = nome_militar_atual.upper().strip()

    for b in all_bens_banco:
        custodiante = str(b.get("fiel_depositario_atual", "")).upper().strip()
        destinatario = str(b.get("destinatario_pendente", "")).upper().strip()
        status_tr = str(b.get("status_tramite", ""))

        # 1. Bens em minha posse direta
        if custodiante in militar_clean or militar_clean in custodiante:
            if status_tr == "Pendente Aceite":
                bens_enviados_aguardando_aceite.append(b)
            else:
                bens_em_posse.append(b)
        # 2. Bens enviados para mim aguardando meu aceite
        elif status_tr == "Pendente Aceite" and (destinatario in militar_clean or militar_clean in destinatario):
            bens_aguardando_meu_aceite.append(b)

    # 📌 ABA 1: MATERIAIS ENVIADOS AGUARDANDO ACEITE (COM BOTÃO DE CANCELAR)
    if bens_enviados_aguardando_aceite:
        st.warning(f"⏳ **Envios Pendentes de Aceite pelo Destinatário ({len(bens_enviados_aguardando_aceite)} item/ns):**")
        st.caption("Você pode cancelar o envio destes materiais enquanto o destinatário não confirmar o recebimento.")

        for bem_p in bens_enviados_aguardando_aceite:
            with st.container(border=True):
                col_p1, col_p2 = st.columns([3, 1])
                with col_p1:
                    st.markdown(f"📄 REDS: **{bem_p.get('num_reds')}** | Material: **{bem_p.get('descricao')}**")
                    st.caption(
                        f"📦 Qtd: **{bem_p.get('quantidade')} {bem_p.get('unidade_medida')}** | "
                        f"🏷️ Lacre: **{bem_p.get('involucro_lacre')}** | "
                        f"👤 Destinatário Pendente: **{bem_p.get('destinatario_pendente')}** ({bem_p.get('unidade_destinatario_pendente')})"
                    )
                with col_p2:
                    if st.button("❌ Cancelar Envio", key=f"btn_canc_envio_{bem_p.get('id_bem')}", type="primary", use_container_width=True):
                        now_iso = datetime.datetime.now().isoformat()
                        now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

                        destinatario_cancelado = bem_p.get("destinatario_pendente", "Destinatário")

                        # Restaura a posse ao remetente e cancela a pendência
                        bem_p["status_tramite"] = "Em Custódia"
                        bem_p["destinatario_pendente"] = None
                        bem_p["unidade_destinatario_pendente"] = None
                        bem_p["data_envio_tramite"] = None

                        salvar_material_supabase(bem_p)

                        # Registo de Log de Cancelamento
                        registrar_log_supabase({
                            "data_hora": now_iso,
                            "num_reds": bem_p.get("num_reds"),
                            "bem_id": bem_p.get("id_bem"),
                            "web_origem": "SIOP_TCO",
                            "acao": "CANCELAMENTO DE TRAMITAÇÃO (PRÉ-ACEITE)",
                            "origem": nome_militar_atual,
                            "unidade_origem": unidade_militar_atual,
                            "destino": nome_militar_atual,
                            "unidade_destino": unidade_militar_atual,
                            "detalhe": f"Envio para {destinatario_cancelado} cancelado pelo remetente antes do aceite. Posse mantida com {nome_militar_atual}."
                        })

                        st.success(f"✅ Tramitação do material '{bem_p.get('descricao')}' cancelada com sucesso!")
                        st.rerun()

        st.divider()

    # 📌 ABA 2: MATERIAIS RECEBIDOS AGUARDANDO MEU ACEITE
    if bens_aguardando_meu_aceite:
        st.error(f"📥 **Materiais Aguarando Seu Aceite de Custódia ({len(bens_aguardando_meu_aceite)} item/ns):**")
        for bem_rec in bens_aguardando_meu_aceite:
            with st.container(border=True):
                col_r1, col_r2 = st.columns([3, 1])
                with col_r1:
                    st.markdown(f"📄 REDS: **{bem_rec.get('num_reds')}** | Material: **{bem_rec.get('descricao')}**")
                    st.caption(
                        f"📦 Qtd: **{bem_rec.get('quantidade')} {bem_rec.get('unidade_medida')}** | "
                        f"🏷️ Lacre: **{bem_rec.get('involucro_lacre')}** | "
                        f"👤 Remetente: **{bem_rec.get('fiel_depositario_atual')}** ({bem_rec.get('unidade_posse_atual')})"
                    )
                with col_r2:
                    if st.button("✅ Confirmar Aceite", key=f"btn_aceitar_{bem_rec.get('id_bem')}", type="primary", use_container_width=True):
                        now_iso = datetime.datetime.now().isoformat()
                        
                        remetente_orig = bem_rec.get("fiel_depositario_atual")
                        unidade_orig = bem_rec.get("unidade_posse_atual")

                        bem_rec["status_tramite"] = "Em Custódia"
                        bem_rec["fiel_depositario_atual"] = nome_militar_atual
                        bem_rec["unidade_posse_atual"] = unidade_militar_atual
                        bem_rec["data_posse_atual"] = now_iso
                        bem_rec["destinatario_pendente"] = None
                        bem_rec["unidade_destinatario_pendente"] = None

                        salvar_material_supabase(bem_rec)

                        registrar_log_supabase({
                            "data_hora": now_iso,
                            "num_reds": bem_rec.get("num_reds"),
                            "bem_id": bem_rec.get("id_bem"),
                            "web_origem": "SIOP_TCO",
                            "acao": "ACEITE DE CUSTÓDIA FÍSICA",
                            "origem": remetente_orig,
                            "unidade_origem": unidade_orig,
                            "destino": nome_militar_atual,
                            "unidade_destino": unidade_militar_atual,
                            "detalhe": f"Aceite de custódia física confirmado por {nome_militar_atual} na unidade {unidade_militar_atual}."
                        })

                        st.success("✅ Custódia aceita e atualizada no Supabase!")
                        st.rerun()

        st.divider()

    # 📌 ABA 3: MINHA CUSTÓDIA ATIVA & FORMULÁRIO DE TRAMITAÇÃO
    st.markdown(f"##### 🎒 Seus Bens em Custódia Física ({len(bens_em_posse)} item/ns)")

    if not bens_em_posse:
        st.info("Você não possui materiais em sua custódia física no momento.")
        return

    # Tabela com seleção para tramitação
    df_posse = pd.DataFrame(bens_em_posse)
    df_posse.insert(0, "selecionar", False)

    df_edit = st.data_editor(
        df_posse[["selecionar", "num_reds", "descricao", "quantidade", "unidade_medida", "involucro_lacre", "autores", "fase_destinacao"]],
        column_config={
            "selecionar": st.column_config.CheckboxColumn("Tramitar", default=False),
            "num_reds": st.column_config.TextColumn("REDS", disabled=True),
            "descricao": st.column_config.TextColumn("Descrição", disabled=True),
            "quantidade": st.column_config.NumberColumn("Qtd", disabled=True),
            "unidade_medida": st.column_config.TextColumn("Unid", disabled=True),
            "involucro_lacre": st.column_config.TextColumn("Lacre / Invólucro", disabled=True),
            "autores": st.column_config.TextColumn("Autor Vinculado", disabled=True),
            "fase_destinacao": st.column_config.TextColumn("Fase Atual", disabled=True)
        },
        hide_index=True,
        use_container_width=True,
        key="editor_tramitacao_posse_v1"
    )

    itens_selecionados = df_edit[df_edit["selecionar"] == True]

    if len(itens_selecionados) > 0:
        st.markdown(f"##### 🔄 Tramitar {len(itens_selecionados)} item(ns) Selecionado(s)")
        
        with st.form("form_tramitar_materiais_lote", clear_on_submit=True):
            col_t1, col_t2 = st.columns(2)
            
            with col_t1:
                tipo_destino = st.radio("Tipo de Destinatário:", ["Policial Militar / Fiel Depositário", "Unidade / CREDS / Órgão Externo"])
                
                if "Policial" in tipo_destino:
                    militares_m = carregar_militares_supabase() or []
                    opts_mil = {f"{m.get('posto_grad')} {m.get('nome_guerra')} ({m.get('num_policia')})": m for m in militares_m}
                    dest_mil_key = st.selectbox("Selecione o Policial Destinatário:", list(opts_mil.keys()) if opts_mil else ["Nenhum militar localizado"])
                    dest_final_nome = dest_mil_key
                    dest_final_unid = opts_mil[dest_mil_key].get("unidade", unidade_militar_atual) if opts_mil and dest_mil_key in opts_mil else unidade_militar_atual
                else:
                    dest_final_nome = st.selectbox("Selecione a Unidade / CREDS / Órgão:", obter_unidades_disponiveis())
                    dest_final_unid = dest_final_nome

            with col_t2:
                nova_fase = st.selectbox(
                    "Atualizar Fase de Destinação:",
                    [
                        "Com Fiel Depositário / Policial",
                        "Encaminhado ao CREDS / Depósito",
                        "Encaminhado para Perícia Técnica",
                        "Entregue na PCMG / Delegacia",
                        "Entregue no JECRIM / Fórum",
                        "Aguardando Destruição / Descarte"
                    ]
                )
                obs_tramite = st.text_input("Observações / Motivo da Transferência:", placeholder="Ex: Encaminhado para contraperícia").strip()

            btn_enviar_tramite = st.form_submit_button("🚀 Confirmar Envio / Tramitação", type="primary", use_container_width=True)

            if btn_enviar_tramite:
                now_iso = datetime.datetime.now().isoformat()

                for idx_s, row_s in itens_selecionados.iterrows():
                    bem_orig = next((b for b in bens_em_posse if b.get("num_reds") == row_s["num_reds"] and b.get("descricao") == row_s["descricao"]), None)
                    if bem_orig:
                        bem_orig["status_tramite"] = "Pendente Aceite"
                        bem_orig["destinatario_pendente"] = dest_final_nome
                        bem_orig["unidade_destinatario_pendente"] = dest_final_unid
                        bem_orig["data_envio_tramite"] = now_iso
                        bem_orig["fase_destinacao"] = nova_fase

                        salvar_material_supabase(bem_orig)

                        detalhe_txt = f"Encaminhado para {dest_final_nome} ({dest_final_unid}). Fase: {nova_fase}."
                        if obs_tramite:
                            detalhe_txt += f" Obs: {obs_tramite}"

                        registrar_log_supabase({
                            "data_hora": now_iso,
                            "num_reds": bem_orig.get("num_reds"),
                            "bem_id": bem_orig.get("id_bem"),
                            "web_origem": "SIOP_TCO",
                            "acao": "SOLICITAÇÃO DE TRAMITAÇÃO EM LOTE",
                            "origem": nome_militar_atual,
                            "unidade_origem": unidade_militar_atual,
                            "destino": dest_final_nome,
                            "unidade_destino": dest_final_unid,
                            "detalhe": detalhe_txt
                        })

                st.success(f"✅ Tramitação de {len(itens_selecionados)} item(ns) enviada com sucesso! Aguardando aceite de {dest_final_nome}.")
                st.rerun()