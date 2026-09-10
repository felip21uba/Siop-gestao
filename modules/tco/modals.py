import streamlit as st
import datetime
from modules.tco.parser_reds import gerar_hash_sha256
from modules.tco.database import atualizar_material_supabase, registrar_log_supabase

@st.dialog("✏️ Editar Dados e Anexar Mídias ao Material")
def abrir_modal_edicao_material(bem_obj, nome_militar_atual, unidade_militar_atual):
    st.markdown(f"**REDS:** <span style='font-size: 1.1rem; color: #60A5FA; font-weight: bold;'>{bem_obj['num_reds']}</span> | **Código:** <span style='font-size: 1.1rem; color: #F59E0B; font-weight: bold;'>{bem_obj['id_bem']}</span>", unsafe_allow_html=True)
    
    orig = bem_obj.get("dados_originais_pdf") or {}
    st.info("🔍 **Dados Originais do PDF:**\n\n"
            f"- **Descrição:** {orig.get('descricao', 'N/A')}\n"
            f"- **Quantidade:** {orig.get('quantidade', '1.0')} {orig.get('unidade', 'UN')}\n"
            f"- **Invólucro/Lacre:** {orig.get('involucro', 'N/A')}\n"
            f"- **Autor:** {orig.get('autores', 'N/A')}")

    with st.form("form_editar_material_custodia_v17", clear_on_submit=False):
        novo_autor = st.text_input("Autor Vinculado:", value=bem_obj.get("autores", "")).strip().upper()
        nova_desc = st.text_input("Descrição do Material:", value=bem_obj.get("descricao", "")).strip().upper()
        col_ed1, col_ed2 = st.columns(2)
        with col_ed1:
            nova_qtd = st.number_input("Quantidade:", min_value=0.1, value=float(bem_obj.get("quantidade", 1.0)), step=1.0)
        with col_ed2:
            nova_unid = st.text_input("Unidade de Medida:", value=bem_obj.get("unidade_medida", "UNIDADE")).strip().upper()
            
        novo_inv = st.text_input("Nº do Invólucro / Lacre:", value=bem_obj.get("involucro_lacre", "")).strip().upper()
        motivo_edicao = st.text_input("Motivo / Justificativa da Alteração:", placeholder="Ex: Ajuste na conferência física do lacre").strip()
        
        uploaded_midias = st.file_uploader("📷 Anexar Foto / Documento de Prova (Opcional):", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)

        if st.form_submit_button("💾 Salvar e Atualizar Auditoria", type="primary", use_container_width=True):
            if not nova_desc or len(motivo_edicao) < 5:
                st.error("A descrição e a justificativa (mínimo 5 caracteres) são obrigatórias.")
            else:
                now_iso = datetime.datetime.now().isoformat()
                now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                novas_midias_anexadas = []

                if uploaded_midias:
                    for f in uploaded_midias:
                        f_bytes = f.getvalue()
                        f_hash = gerar_hash_sha256(f_bytes)
                        novas_midias_anexadas.append({
                            "nome_arquivo": f.name,
                            "tipo": f.type,
                            "tamanho_bytes": len(f_bytes),
                            "hash_sha256": f_hash,
                            "enviado_por": nome_militar_atual,
                            "unidade": unidade_militar_atual,
                            "data_envio": now_str
                        })

                midias_existentes = bem_obj.get("midias_anexas") or []
                midias_existentes.extend(novas_midias_anexadas)

                detalhes_alteracao = (
                    f"EDIÇÃO OPERADOR ({nome_militar_atual} - {unidade_militar_atual}) | MOTIVO: {motivo_edicao} | "
                    f"ALTERAÇÕES: [Desc: '{bem_obj['descricao']}' ➔ '{nova_desc}'] "
                    f"[Qtd: '{bem_obj['quantidade']} {bem_obj.get('unidade_medida')}' ➔ '{nova_qtd} {nova_unid}'] "
                    f"[Lacre: '{bem_obj.get('involucro_lacre')}' ➔ '{novo_inv}'] "
                    f"[Mídias Novas: {len(novas_midias_anexadas)} arquivo(s)]"
                )
                
                upd_data = {
                    "autores": novo_autor,
                    "descricao": nova_desc,
                    "quantidade": nova_qtd,
                    "unidade_medida": nova_unid,
                    "involucro_lacre": novo_inv,
                    "editado_pelo_operador": True,
                    "midias_anexas": midias_existentes
                }
                
                if atualizar_material_supabase(bem_obj["id_bem"], upd_data):
                    registrar_log_supabase({
                        "data_hora": now_iso,
                        "num_reds": bem_obj["num_reds"],
                        "bem_id": bem_obj["id_bem"],
                        "acao": "EDIÇÃO E ANEXO DE MÍDIAS",
                        "origem": nome_militar_atual,
                        "unidade_origem": unidade_militar_atual,
                        "destino": nome_militar_atual,
                        "unidade_destino": unidade_militar_atual,
                        "detalhe": detalhes_alteracao
                    })
                    st.success("Dados salvos com sucesso no Supabase!")
                    st.rerun()

@st.dialog("🚨 Registrar Divergência / Recusa de Custódia")
def abrir_modal_divergencia(bem_obj, nome_militar_atual, unidade_militar_atual):
    st.warning(f"Material: **{bem_obj['descricao']}** (REDS: **{bem_obj['num_reds']}**)")
    
    motivo_sel = st.selectbox(
        "Selecione o Motivo da Divergência:",
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
        placeholder="Descreva a divergência observada na conferência...",
        height=120,
        key=f"txt_just_div_{bem_obj['id_bem']}"
    )
    
    if st.button("🚨 Confirmar Divergência e Emitir Alerta P1/CREDS", type="primary", use_container_width=True, key=f"btn_conf_div_{bem_obj['id_bem']}"):
        if not justificativa_txt or len(justificativa_txt.strip()) < 10:
            st.error("A justificativa detalhada é obrigatória (mínimo 10 caracteres).")
        else:
            now_iso = datetime.datetime.now().isoformat()
            now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            origem_remetente = bem_obj.get("remetente_ultimo") or bem_obj.get("fiel_depositario_atual")
            unidade_remetente = bem_obj.get("unidade_remetente") or bem_obj.get("unidade_posse_atual")
            
            dados_div = {
                "motivo": motivo_sel,
                "justificativa": justificativa_txt.strip(),
                "registrado_por": nome_militar_atual,
                "unidade": unidade_militar_atual,
                "data_hora": now_str,
                "remetente_origem": origem_remetente,
                "unidade_remetente": unidade_remetente
            }
            
            upd_data = {
                "status_tramite": "Divergência Registrada",
                "dados_divergencia": dados_div
            }
            
            if atualizar_material_supabase(bem_obj["id_bem"], upd_data):
                registrar_log_supabase({
                    "data_hora": now_iso,
                    "num_reds": bem_obj["num_reds"],
                    "bem_id": bem_obj["id_bem"],
                    "acao": "REGISTRO DE DIVERGÊNCIA / RECUSA",
                    "origem": origem_remetente,
                    "unidade_origem": unidade_remetente,
                    "destino": nome_militar_atual,
                    "unidade_destino": unidade_militar_atual,
                    "detalhe": f"MOTIVO: {motivo_sel} | JUSTIFICATIVA: {justificativa_txt.strip()}"
                })
                st.success("Divergência registrada com sucesso!")
                st.rerun()