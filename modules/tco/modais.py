"""
==============================================================================
Módulo de Modais e Janelas Suspensas do TCO (modules/tco/modais.py)
Contém os modais de edição de materiais, galeria de mídias e termos do TCO.
==============================================================================
"""

import datetime
import pandas as pd
import streamlit as st
from core.database import supabase
from modules.tco.database import registrar_log_supabase, atualizar_material_supabase
from modules.tco.storage import upload_midia_supabase, excluir_midia_supabase
from utils.file_validator import sanitizar_nome_arquivo


@st.dialog("📷 Edição de Material & Gestão de Mídias/Fotos", width="large")
def abrir_modal_edicao_material(dados_bem: dict, nome_operador: str, unidade_operador: str):
    """
    Modal suspenso para upload de fotos/mídias, visualização direta da galeria
    e edição dos metadados do material apreendido.
    """
    id_bem = str(dados_bem.get("id_bem") or dados_bem.get("id"))
    num_reds = str(dados_bem.get("num_reds", "N/I")).strip()
    desc_orig = str(dados_bem.get("descricao", "")).strip()
    qtd_orig = dados_bem.get("quantidade", 1)
    unid_orig = str(dados_bem.get("unidade_medida", "UN")).strip()
    lacre_orig = str(dados_bem.get("involucro_lacre", "SEM LACRE")).strip()
    autor_orig = str(dados_bem.get("autores", "N/I")).strip()

    st.markdown(f"#### 📄 REDS: `{num_reds}` | 🆔 ID do Bem: `{id_bem}`")
    st.caption("Adicione fotos/mídias da apreensão ou atualize as informações do material de custódia.")

    # =========================================================================
    # 🖼️ SEÇÃO 1: GALERIA E VISUALIZAÇÃO DIRETA DAS MÍDIAS / FOTOS
    # =========================================================================
    midias = dados_bem.get("midias_anexas") or []
    if isinstance(midias, str):
        midias = []

    st.markdown("---")
    st.markdown(f"##### 🖼️ Fotos & Documentos Anexados ({len(midias)})")

    if midias:
        cols_m = st.columns(2)
        for idx_m, item_m in enumerate(midias):
            url_p = item_m.get("url_publica")
            nome_a = item_m.get("nome_arquivo", "Arquivo Anexo")
            tipo_m = str(item_m.get("tipo_mime") or item_m.get("tipo", "")).lower()
            caminho_st = item_m.get("caminho_storage", "")

            with cols_m[idx_m % 2]:
                with st.container(border=True):
                    st.caption(f"📎 **{nome_a}**")
                    if any(ext in tipo_m or ext in nome_a.lower() for ext in ["jpg", "jpeg", "png", "webp", "gif"]):
                        if url_p:
                            st.image(url_p, caption=nome_a, use_container_width=True)
                        else:
                            st.warning("⚠️ URL da imagem indisponível.")
                    else:
                        if url_p:
                            st.link_button(f"📄 Abrir Documento ({nome_a[:18]}...)", url_p, use_container_width=True)

                    c_m_del, c_m_link = st.columns([1, 1])
                    with c_m_del:
                        if st.button("🗑️ Excluir", key=f"btn_del_midia_modal_{id_bem}_{idx_m}", type="secondary", use_container_width=True):
                            if excluir_midia_supabase(id_bem, caminho_st):
                                st.success("Mídia removida!")
                                st.cache_data.clear()
                                st.rerun()
                    with c_m_link:
                        if url_p:
                            st.link_button("🔗 Link", url_p, use_container_width=True)
    else:
        st.info("ℹ️ Nenhuma mídia ou foto anexada a este material até o momento.")

    # =========================================================================
    # 📤 SEÇÃO 2: UPLOAD DE NOVAS FOTOS / DOCUMENTOS
    # =========================================================================
    st.markdown("---")
    st.markdown("##### 📤 Anexar Nova Foto ou Mídia ao Material")
    
    arquivo_upload = st.file_uploader(
        "Selecione uma foto (JPG, PNG) ou documento (PDF) da apreensão:",
        type=["jpg", "jpeg", "png", "pdf", "webp"],
        key=f"upl_modal_file_{id_bem}"
    )

    if arquivo_upload:
        if st.button("💾 Enviar Mídia para o Storage", key=f"btn_confirm_upload_{id_bem}", type="primary", use_container_width=True):
            with st.spinner("Enviando arquivo e atualizando custódia..."):
                res_anexo = upload_midia_supabase(
                    file_bytes=arquivo_upload.getvalue(),
                    file_name=sanitizar_nome_arquivo(arquivo_upload.name),
                    file_type=arquivo_upload.type,
                    num_reds=num_reds,
                    id_bem=id_bem
                )

                if res_anexo:
                    agora_iso = datetime.datetime.now().isoformat()
                    registrar_log_supabase({
                        "data_hora": agora_iso,
                        "num_reds": num_reds,
                        "bem_id": f"{desc_orig} (ID: {id_bem})",
                        "web_origem": "SIOP_TCO",
                        "acao": "MIDIA_ANEXADA",
                        "origem": nome_operador,
                        "unidade_origem": unidade_operador,
                        "destino": "CUSTÓDIA TCO",
                        "unidade_destino": unidade_operador,
                        "detalhe": f"Mídia '{arquivo_upload.name}' anexada ao bem {id_bem}."
                    })
                    st.success("✅ Mídia enviada e vinculada com sucesso!")
                    st.cache_data.clear()
                    st.rerun()

    # =========================================================================
    # 📝 SEÇÃO 3: EDIÇÃO DE METADADOS DO MATERIAL
    # =========================================================================
    st.markdown("---")
    st.markdown("##### 📝 Editar Dados Cadastrais do Bem")

    with st.form(key=f"form_edicao_material_{id_bem}"):
        nova_desc = st.text_area("Descrição do Material:", value=desc_orig, height=90)
        
        c_e1, c_e2 = st.columns(2)
        with c_e1:
            nova_qtd = st.number_input("Quantidade:", value=float(qtd_orig) if qtd_orig else 1.0, min_value=0.1, step=1.0)
        with c_e2:
            nova_unid = st.text_input("Unidade de Medida:", value=unid_orig)

        c_e3, c_e4 = st.columns(2)
        with c_e3:
            novo_lacre = st.text_input("Nº do Invólucro / Lacre:", value=lacre_orig)
        with c_e4:
            novo_autor = st.text_input("Autor / Envolvido:", value=autor_orig)

        btn_salvar_dados = st.form_submit_button("💾 Salvar Alterações no Material", type="primary", use_container_width=True)

        if btn_salvar_dados:
            payload_update = {
                "descricao": nova_desc.strip(),
                "quantidade": nova_qtd,
                "unidade_medida": nova_unid.strip(),
                "involucro_lacre": novo_lacre.strip(),
                "autores": novo_autor.strip()
            }

            if atualizar_material_supabase(id_bem, payload_update):
                agora_iso = datetime.datetime.now().isoformat()
                registrar_log_supabase({
                    "data_hora": agora_iso,
                    "num_reds": num_reds,
                    "bem_id": f"{nova_desc} (ID: {id_bem})",
                    "web_origem": "SIOP_TCO",
                    "acao": "MATERIAL_EDITADO",
                    "origem": nome_operador,
                    "unidade_origem": unidade_operador,
                    "destino": "CUSTÓDIA TCO",
                    "unidade_destino": unidade_operador,
                    "detalhe": f"Dados do material {id_bem} atualizados por {nome_operador}."
                })
                st.success("✅ Informações do material salvas com sucesso!")
                st.cache_data.clear()
                st.rerun()