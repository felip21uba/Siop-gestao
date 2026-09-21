import streamlit as st
import pandas as pd
import datetime
import uuid
import io
import openpyxl
import re
from core.database import (
    supabase,
    carregar_militares_supabase,
    atualizar_usuario_supabase,
    registrar_audit_log
)
from core.permissions import usuario_eh_gestor_creds
from modules.tco.parser_reds import extrair_dados_reds_pdf
from modules.tco.storage import upload_midia_supabase
from modules.tco.database import salvar_material_supabase, atualizar_material_supabase, registrar_log_supabase
from modules.tco.modais import abrir_modal_edicao_material, abrir_modal_divergencia
from modules.tco.compliance import gerar_pdf_termo_compliance, obter_ou_registrar_aceite_compliance
from utils.file_validator import validar_pdf_upload, validar_imagem_upload, sanitizar_nome_arquivo

# =============================================================================
# INJEÇÃO DO CSS PERSONALIZADO (AZUL E MARROM COM TEXTO AJUSTADO)
# =============================================================================
def injetar_css_cards_alternados():
    st.markdown("""
    <style>
    .card-content { color: #e2e8f0; }
    .card-content strong, .card-content b { color: #ffffff; }

    .card-blue {
      background-color: #0c1938;
      border: 2px solid #1e6091;
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 12px;
      color: #e2e8f0 !important;
    }
    .card-blue b, .card-blue strong { color: #ffffff !important; }

    .card-brown {
      background-color: #9e8652;
      border: 2px solid #7a663b;
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 12px;
      color: #000000 !important;
    }
    .card-brown .card-title,
    .card-brown .status-text,
    .card-brown strong,
    .card-brown b,
    .card-brown small,
    .card-brown i { color: #000000 !important; }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# HELPER DE EXTRAÇÃO E MONTAGEM DINÂMICA DE CREDS POR CIA / BATALHÃO
# =============================================================================
def extrair_unidade_mae_creds(str_unidade):
    if not str_unidade or not isinstance(str_unidade, str):
        return None
    str_u = str_unidade.upper().strip()

    if "35" in str_u and ("CIA" in str_u or "COMPANHIA" in str_u):
        return "35ª CIA PM"
    elif "111" in str_u and ("CIA" in str_u or "COMPANHIA" in str_u):
        return "111ª CIA PM"
    elif "285" in str_u and ("CIA" in str_u or "TM" in str_u or "TÁTICO" in str_u or "TATIC" in str_u):
        return "285ª CIA TM"
    elif "21" in str_u and ("BPM" in str_u or "EM" in str_u or "BATALHAO" in str_u or "BATALHÃO" in str_u or "SECT" in str_u or "GAB" in str_u or "COPOM" in str_u or "SADM" in str_u or "CTPM" in str_u):
        return "21º BPM"

    m_cia = re.search(r'(\d+)\s*ª?\s*CIA', str_u)
    if m_cia:
        return f"{m_cia.group(1)}ª CIA PM"
        
    m_bpm = re.search(r'(\d+)\s*º?\s*BPM', str_u)
    if m_bpm:
        return f"{m_bpm.group(1)}º BPM"

    if "CENTRAL" in str_u and "CUSTODIA" in str_u:
        return "CENTRAL DE CUSTÓDIA"

    return None

def obter_lista_creds_dinamica():
    unidades_set = set()
    all_m = carregar_militares_supabase()
    
    for m in all_m:
        for col in ["unidade", "nome_unidade", "lotacao", "secao"]:
            unid_bruta = str(m.get(col) or "").strip()
            unid_mae = extrair_unidade_mae_creds(unid_bruta)
            if unid_mae:
                unidades_set.add(unid_mae)

    if supabase:
        try:
            res_u = supabase.table("usuarios").select("unidade").or_("perfil_creds.eq.GESTOR_CIA,perfil_creds.eq.GESTOR_UNIDADE,nivel_acesso.eq.CREDS").execute()
            if res_u and res_u.data:
                for u in res_u.data:
                    u_manual = str(u.get("unidade") or "").strip().upper()
                    if u_manual and u_manual != "NONE":
                        unidades_set.add(u_manual)
        except Exception:
            pass

    unidades_base = {"35ª CIA PM", "111ª CIA PM", "285ª CIA TM", "21º BPM"}
    unidades_set.update(unidades_base)

    lista = [f"CREDS TCO - {u}" for u in sorted(list(unidades_set)) if "CENTRAL" not in u]
    if "CREDS TCO - CENTRAL DE CUSTÓDIA" not in lista:
        lista.append("CREDS TCO - CENTRAL DE CUSTÓDIA")
    
    lista.append("✏️ Outro CREDS / Digitar Manualmente")
    return lista

def gerar_excel_panoramico_tco(lista_bens_filtrados):
    buffer = io.BytesIO()
    dados_excel = []
    
    for b in lista_bens_filtrados:
        _, _, alerta_4d, dias_num = obter_status_gargalo_e_tempo(b, e_marrom=False)
        dt_ing = b.get("data_ingestao") or b.get("data_posse_atual") or ""
        if dt_ing:
            try:
                dt_ing_fmt = pd.to_datetime(dt_ing).strftime("%d/%m/%Y %H:%M")
            except Exception:
                dt_ing_fmt = str(dt_ing)[:16]
        else:
            dt_ing_fmt = "N/I"

        dados_excel.append({
            "Nº REDS": str(b.get("num_reds", "N/I")),
            "Código Bem": str(b.get("id_bem", "N/I")),
            "Descrição do Material": str(b.get("descricao", "N/I")),
            "Qtd": b.get("quantidade", 1.0),
            "Unidade Medida": str(b.get("unidade_medida", "UN")),
            "Nº Lacre / Invólucro": str(b.get("involucro_lacre", "N/I")),
            "Autor(es) Vinculado(s)": str(b.get("autores", "N/I")),
            "Custodiante Atual": str(b.get("fiel_depositario_atual", "N/I")),
            "Unidade / Posse Atual": str(b.get("unidade_posse_atual", "N/I")),
            "Fase / Destinação Final": str(b.get("fase_destinacao", "N/I")),
            "Status do Trâmite": str(b.get("status_tramite", "N/I")),
            "Tempo Imóvel (Dias)": dias_num,
            "Alerta Gargalo (>4d)": "SIM (RETIDO)" if (alerta_4d and "DESTRUÍDO" not in str(b.get("fase_destinacao", ""))) else "NÃO",
            "Data Importação REDS": dt_ing_fmt,
            "P.A. / Ofício Autorizador": str(b.get("pa_oficio_autorizador", "N/A"))
        })

    df_exp = pd.DataFrame(dados_excel)
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_exp.to_excel(writer, index=False, sheet_name="Panorama_Custodia_TCO")
    buffer.seek(0)
    return buffer.getvalue()

def calcular_tempo_decorrido_detalhado(str_data_hora):
    if not str_data_hora or str_data_hora in ["N/A", "Data N/I", "N/I", "None"]:
        return "N/A", False, 0
    try:
        dt_evento = pd.to_datetime(str_data_hora)
        delta = datetime.datetime.now() - dt_evento.to_pydatetime().replace(tzinfo=None)
        dias = delta.days
        horas = delta.seconds // 3600
        minutos = (delta.seconds % 3600) // 60
        
        alerta_4dias = (dias >= 4)
        
        if dias > 0:
            texto = f"{dias}d {horas}h"
        elif horas > 0:
            texto = f"{horas}h {minutos}m"
        else:
            texto = f"{minutos} min"
            
        return texto, alerta_4dias, dias
    except Exception:
        return "N/A", False, 0

def obter_status_gargalo_e_tempo(bem, e_marrom=False):
    status_tr = bem.get("status_tramite", "Em Custódia")
    fase_dest = bem.get("fase_destinacao", "Com Fiel Depositário / Policial")
    dt_ref = bem.get("data_envio_tramite") or bem.get("data_posse_atual") or bem.get("data_ingestao")
    
    texto_tempo, e_alerta_4dias, dias_num = calcular_tempo_decorrido_detalhado(dt_ref)
    
    def tag_destaque(txt):
        if e_marrom:
            return f"<strong style='color: #000000;'>{txt}</strong>"
        return f"<span style='color: #4ADE80; font-weight: bold;'>{txt}</span>"

    if status_tr == "Pendente Aceite":
        ponto_cadeia = f"⏳ <b>Aguardando Aceite:</b> {tag_destaque(bem.get('destinatario_pendente', 'N/I'))} ({bem.get('unidade_destinatario_pendente', 'N/I')})"
    elif status_tr == "Divergência Registrada":
        ponto_cadeia = f"🚨 <b>Divergência Registrada:</b> Pendente de Apuração pelo Gestor CREDS"
    elif "Perícia" in fase_dest:
        ponto_cadeia = f"🔬 <b>Em Perícia Técnica:</b> Responsável: {tag_destaque(bem.get('fiel_depositario_atual', 'N/I'))}"
    elif "PCMG" in fase_dest or "Delegacia" in fase_dest:
        ponto_cadeia = f"🏛️ <b>Encaminhado à Polícia Civil:</b> Responsável: {tag_destaque(bem.get('fiel_depositario_atual', 'N/I'))}"
    elif "JECRIM" in fase_dest or "Fórum" in fase_dest:
        ponto_cadeia = f"⚖️ <b>Entregue no JECRIM / Fórum:</b> Responsável: {tag_destaque(bem.get('fiel_depositario_atual', 'N/I'))}"
    elif "Destruição" in fase_dest or "Descarte" in fase_dest:
        ponto_cadeia = f"🔥 <b>Aguardando Destruição / Descarte Físico no Depósito</b>"
    elif "DESTRUÍDO" in fase_dest or "ENCERRADO" in fase_dest:
        ponto_cadeia = f"🔒 <b>Processo Encerrado / Material Destruído</b>"
    else:
        ponto_cadeia = f"🎒 <b>Em Custódia Física de:</b> {tag_destaque(bem.get('fiel_depositario_atual', 'N/I'))} ({bem.get('unidade_posse_atual', 'N/I')})"
        
    return ponto_cadeia, texto_tempo, e_alerta_4dias, dias_num

def aplicar_filtros_bens(lista_bens, reds_q="", autor_q="", militar_q="", unidade_q="", data_q=None):
    resultado = []
    for b in lista_bens:
        if reds_q and reds_q.lower() not in str(b.get("num_reds", "")).lower():
            continue
        if autor_q and autor_q.lower() not in str(b.get("autores", "")).lower():
            continue
        militares_vinculados = f"{b.get('fiel_depositario_atual', '')} {b.get('remetente_ultimo', '')} {b.get('destinatario_pendente', '')}"
        if militar_q and militar_q.lower() not in militares_vinculados.lower():
            continue
        unidades_vinculadas = f"{b.get('unidade_posse_atual', '')} {b.get('unidade_remetente', '')} {b.get('unidade_destinatario_pendente', '')}"
        if unidade_q and unidade_q != "TODAS AS UNIDADES" and unidade_q.lower() not in unidades_vinculadas.lower():
            continue
        if data_q:
            data_str = data_q.strftime("%Y-%m-%d")
            datas_item = f"{b.get('data_ingestao', '')} {b.get('data_posse_atual', '')} {b.get('data_envio_tramite', '')}"
            if data_str not in datas_item:
                continue
        resultado.append(b)
    return resultado

def aplicar_filtros_logs(lista_logs, reds_q="", busca_txt="", militar_q="", periodo_q=None):
    resultado = []
    d_ini, d_fim = None, None
    if isinstance(periodo_q, tuple) and len(periodo_q) == 2:
        d_ini, d_fim = periodo_q

    for l in lista_logs:
        if reds_q and reds_q.lower() not in str(l.get("num_reds", "")).lower():
            continue
        if busca_txt and busca_txt.lower() not in str(l.get("detalhe", "")).lower() and busca_txt.lower() not in str(l.get("acao", "")).lower():
            continue
        militares_log = f"{l.get('origem', '')} {l.get('destino', '')}"
        if militar_q and militar_q.lower() not in militares_log.lower():
            continue
        if d_ini and d_fim:
            str_dh = str(l.get("data_hora", ""))
            if str_dh:
                try:
                    dt_log = pd.to_datetime(str_dh).date()
                    if not (d_ini <= dt_log <= d_fim):
                        continue
                except Exception:
                    pass
        resultado.append(l)
    return resultado

# =============================================================================
# ABA 1: IMPORTAR REDS & MÍDIAS
# =============================================================================
def renderizar_aba_importacao(nome_militar_atual, unidade_militar_atual):
    injetar_css_cards_alternados()
    if "temp_reds_extraido" not in st.session_state:
        st.session_state["temp_reds_extraido"] = None

    col_ing1, col_ing2 = st.columns(2)
    
    with col_ing1:
        with st.container(border=True):
            st.markdown("##### 📄 Importar Ocorrência (BO REDS)")
            arquivo_pdf = st.file_uploader("Selecione o PDF do REDS:", type=["pdf"], key="uploader_reds_pdf_v35")

            if arquivo_pdf is not None:
                valido_pdf, msg_pdf = validar_pdf_upload(arquivo_pdf)
                if not valido_pdf:
                    st.error(msg_pdf)
                else:
                    if st.button("⚡ Processar Recibo JECRIM", type="primary", key="btn_processar_pdf_recibo_v35", use_container_width=True):
                        with st.spinner("Mapeando recibo do JECRIM, relator, natureza e invólucro do material..."):
                            dados_reds = extrair_dados_reds_pdf(arquivo_pdf)
                            st.session_state["temp_reds_extraido"] = dados_reds
                            st.success("Leitura do REDS concluída!")
            else:
                st.caption("Aguardando upload de arquivo PDF...")

    with col_ing2:
        with st.container(border=True):
            st.markdown("##### ➕ Inserção Manual de Material")
            st.caption("Adicione itens avulsos para conferência unificada.")
            with st.popover("📝 Cadastrar Material Avulso", use_container_width=True):
                with st.form("form_material_manual_v35", clear_on_submit=True):
                    man_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-001843571-001").strip()
                    man_autor = st.text_input("Nome do Autor:", placeholder="Ex: MARCIO DE ALMEIDA SOUZA").strip().upper()
                    man_desc = st.text_input("Descrição do Material:", placeholder="Ex: 02 papelotes de cocaína").strip().upper()
                    man_qtd = st.number_input("Quantidade:", min_value=0.1, value=1.0, step=1.0)
                    man_unid = st.selectbox("Unidade:", ["UNIDADE", "KG", "G", "DUZIA", "CAIXA", "PACOTE"])
                    man_inv = st.text_input("Nº do Invólucro / Lacre:", placeholder="Ex: A230767651").strip().upper()

                    btn_man = st.form_submit_button("➕ Adicionar à Lista", type="primary", use_container_width=True)
                    if btn_man:
                        if not man_reds or not man_desc:
                            st.error("⚠️ Preencha o Nº do REDS e a Descrição do Material.")
                        else:
                            if not st.session_state["temp_reds_extraido"]:
                                st.session_state["temp_reds_extraido"] = {
                                    "num_reds": man_reds,
                                    "data_registro": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                                    "data_fato": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                                    "natureza": "INSERÇÃO MANUAL / TCO",
                                    "local": "N/I",
                                    "redator": nome_militar_atual,
                                    "unidade_jecrim": unidade_militar_atual,
                                    "autores": [man_autor] if man_autor else ["AUTOR NÃO INFORMADO"],
                                    "resumo_fato": "Material incluído manualmente pelo operador.",
                                    "materiais": [],
                                    "hash_pdf": "INSERÇÃO MANUAL"
                                }

                            str_item_num = str(len(st.session_state["temp_reds_extraido"]["materiais"]) + 1)
                            inv_final = man_inv if man_inv else f"SEM LACRE (ITEM {str_item_num})"

                            st.session_state["temp_reds_extraido"]["materiais"].append({
                                "remover": False,
                                "item_num": str_item_num,
                                "env_nr": "1",
                                "autor": man_autor if man_autor else "AUTOR NÃO INFORMADO",
                                "situacao": "APREENDIDO",
                                "descricao": man_desc,
                                "quantidade": man_qtd,
                                "unidade": man_unid,
                                "involucro": inv_final,
                                "destinatario_reds": "JECRIM"
                            })
                            st.success(f"Item '{man_desc}' adicionado!")
                            st.rerun()

    if st.session_state.get("temp_reds_extraido"):
        d = st.session_state["temp_reds_extraido"]
        st.divider()
        
        with st.container(border=True):
            st.markdown(f"#### 📄 Dados da Ocorrência — REDS Nº {d['num_reds']}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"• **Data Registro:** {d['data_registro']}")
                st.markdown(f"• **Data/Hora Fato:** {d['data_fato']}")
                st.markdown(f"• **Unidade Destino:** {d['unidade_jecrim']}")
            with c2:
                st.markdown(f"• **Natureza:** {d['natureza']}")
                st.markdown(f"• **Relator:** {d['redator']}")
                st.markdown(f"• **Autor(es):** {', '.join(d['autores'])}")

            st.caption(f"**Local do Fato:** {d['local']}")
            
            with st.expander("📝 **Ver Resumo Fático & Hash SHA-256 do PDF**"):
                st.write(d['resumo_fato'])
                st.caption(f"🔐 Chancela SHA-256: `{d['hash_pdf']}`")

        st.markdown("##### 📦 Conferência e Seleção de Materiais")
        st.caption("Marque a caixa na coluna 'Excluir' para os itens que deseja retirar e clique no botão 'Excluir Marcados'.")

        if d["materiais"]:
            df_mats = pd.DataFrame(d["materiais"])
            if "remover" not in df_mats.columns:
                df_mats.insert(0, "remover", False)
            
            df_editado_ing = st.data_editor(
                df_mats[["remover", "item_num", "descricao", "quantidade", "unidade", "involucro", "autor"]],
                column_config={
                    "remover": st.column_config.CheckboxColumn("🗑️ Excluir", default=False, width="small"),
                    "item_num": st.column_config.TextColumn("Item", disabled=True, width="small"),
                    "descricao": st.column_config.TextColumn("Descrição do Material", width="large"),
                    "quantidade": st.column_config.NumberColumn("Qtd", min_value=0.1, step=1.0, width="small"),
                    "unidade": st.column_config.TextColumn("Unid", width="small"),
                    "involucro": st.column_config.TextColumn("Nº Lacre / Invólucro", width="medium"),
                    "autor": st.column_config.TextColumn("Autor Vinculado", width="medium")
                },
                hide_index=True,
                use_container_width=True,
                key="editor_materiais_importacao_v35"
            )

            qtd_marcados = len(df_editado_ing[df_editado_ing["remover"] == True])

            photos_ingestao = st.file_uploader(
                "📷 Anexar Mídias / Fotos da Apreensão (Opcional):", 
                type=["jpg", "jpeg", "png", "pdf"], 
                accept_multiple_files=True, 
                key="upl_photos_importacao_v35"
            )

            col_b1, col_b2, col_b3 = st.columns([2, 1.5, 1])
            with col_b1:
                # 📌 BOTÃO RENOMEADO EXATAMENTE PARA "Confirmar Materiais"
                btn_confirmar = st.button("💾 Confirmar Materiais", type="primary", key="btn_conf_fiel_dep_v35", use_container_width=True)
            with col_b2:
                btn_excluir_marcados = st.button(f"🗑️ Excluir Marcados ({qtd_marcados})", disabled=(qtd_marcados == 0), key="btn_excluir_marcados_v35", use_container_width=True)
            with col_b3:
                btn_limpar = st.button("❌ Descartar REDS", key="btn_limpar_importacao_v35", use_container_width=True)

            if btn_excluir_marcados:
                manter = df_editado_ing[df_editado_ing["remover"] == False]
                novos_mats = []
                for idx_m, row in manter.iterrows():
                    novos_mats.append({
                        "remover": False,
                        "item_num": str(row["item_num"]),
                        "env_nr": "1",
                        "autor": str(row["autor"]),
                        "situacao": "APREENDIDO",
                        "descricao": str(row["descricao"]),
                        "quantidade": float(row["quantidade"]),
                        "unidade": str(row["unidade"]),
                        "involucro": str(row["involucro"]),
                        "destinatario_reds": "JECRIM"
                    })
                st.session_state["temp_reds_extraido"]["materiais"] = novos_mats
                st.success(f"{qtd_marcados} item(ns) removido(s) da lista!")
                st.rerun()

            if btn_limpar:
                st.session_state["temp_reds_extraido"] = None
                st.rerun()

            if btn_confirmar:
                itens_validos = df_editado_ing[df_editado_ing["remover"] == False]
                now_iso = datetime.datetime.now().isoformat()
                now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                midias_iniciais = []

                if photos_ingestao:
                    for p_file in photos_ingestao:
                        ext_p = p_file.name.lower()
                        if ext_p.endswith(".pdf"):
                            valido_p, msg_p = validar_pdf_upload(p_file)
                        else:
                            valido_p, msg_p = validar_imagem_upload(p_file)

                        if not valido_p:
                            st.error(f"Arquivo '{p_file.name}': {msg_p}")
                            return

                        nome_p_seguro = sanitizar_nome_arquivo(p_file.name)
                        p_bytes = p_file.getvalue()
                        
                        resultado_storage = upload_midia_supabase(
                            file_bytes=p_bytes,
                            file_name=nome_p_seguro,
                            file_type=p_file.type,
                            num_reds=d["num_reds"],
                            id_bem=f"IMPORTACAO-{d['num_reds']}"
                        )
                        if resultado_storage:
                            resultado_storage["enviado_por"] = nome_militar_atual
                            resultado_storage["unidade"] = unidade_militar_atual
                            resultado_storage["data_envio"] = now_str
                            midias_iniciais.append(resultado_storage)
                
                for idx_row, row in itens_validos.iterrows():
                    id_bem_unico = f"BEM-{d['num_reds']}-{row['item_num']}-{uuid.uuid4().hex[:4]}"
                    orig_item = df_mats.iloc[idx_row]
                    
                    desc_final = str(row["descricao"]).strip()
                    qtd_final = float(row["quantidade"])
                    unid_final = str(row["unidade"]).strip()
                    inv_final = str(row["involucro"]).strip()
                    autor_final = str(row["autor"]).strip()

                    foi_editado = (
                        desc_final != str(orig_item.get("descricao", "")).strip() or
                        qtd_final != float(orig_item.get("quantidade", 1.0)) or
                        unid_final != str(orig_item.get("unidade", "")).strip() or
                        inv_final != str(orig_item.get("involucro", "")).strip() or
                        autor_final != str(orig_item.get("autor", "")).strip()
                    )
                    
                    novo_bem = {
                        "id_bem": id_bem_unico,
                        "num_reds": d["num_reds"],
                        "autores": autor_final,
                        "descricao": desc_final,
                        "quantidade": qtd_final,
                        "unidade_medida": unid_final,
                        "involucro_lacre": inv_final,
                        "fase_destinacao": "Com Fiel Depositário / Policial",
                        "fiel_depositario_atual": nome_militar_atual,
                        "unidade_posse_atual": unidade_militar_atual,
                        "data_posse_atual": now_iso,
                        "status_tramite": "Em Custódia",
                        "data_ingestao": now_iso,
                        "dados_originais_pdf": {
                            "autores": str(orig_item.get("autor", "")).strip(),
                            "descricao": str(orig_item.get("descricao", "")).strip(),
                            "quantidade": float(orig_item.get("quantidade", 1.0)),
                            "unidade": str(orig_item.get("unidade", "")).strip(),
                            "involucro": str(orig_item.get("involucro", "")).strip()
                        },
                        "editado_pelo_operador": foi_editado,
                        "midias_anexas": list(midias_iniciais)
                    }
                    salvar_material_supabase(novo_bem)
                    
                    detalhe_log = f"Importação de {qtd_final} {unid_final} - {desc_final} (Lacre: {inv_final})"
                    if foi_editado:
                        detalhe_log += f" | EDITADO NA IMPORTAÇÃO"

                    registrar_log_supabase({
                        "data_hora": now_iso,
                        "num_reds": d["num_reds"],
                        "bem_id": id_bem_unico,
                        "acao": "IMPORTAÇÃO / CUSTÓDIA INICIAL",
                        "origem": f"REDS JECRIM (Relator: {d['redator']})",
                        "unidade_origem": unidade_militar_atual,
                        "destino": nome_militar_atual,
                        "unidade_destino": unidade_militar_atual,
                        "detalhe": detalhe_log
                    })

                del st.session_state["temp_reds_extraido"]
                st.success("Materiais selecionados salvos com sucesso no Supabase!")
                st.rerun()

renderizar_aba_ingestao = renderizar_aba_importacao

# =============================================================================
# ABA 2: MEUS MATERIAIS EM CUSTÓDIA
# =============================================================================
def renderizar_aba_meus_bens(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    injetar_css_cards_alternados()
    usr_logado = st.session_state.get("usuario_dados", {})
    num_pm = str(usr_logado.get("usuario_login") or usr_logado.get("num_policia") or usr_logado.get("id") or "").strip().upper()
    cargo_f = str(usr_logado.get("cargo_funcao", "POLICIAL MILITAR")).strip().upper()

    col_tit1, col_tit2 = st.columns([3, 1.2])
    with col_tit1:
        st.markdown(f"#### 🎒 Materiais sob Fiel Depósito de: **{nome_militar_atual}**")
    
    with col_tit2:
        _, data_aceite_fixa = obter_ou_registrar_aceite_compliance(num_pm, nome_militar_atual, cargo_f, unidade_militar_atual)
        
        pdf_comp = gerar_pdf_termo_compliance(
            nome_militar=nome_militar_atual,
            cargo_funcao=cargo_f,
            unidade=unidade_militar_atual,
            num_policia=num_pm,
            data_aceite_str=data_aceite_fixa,
            data_impressao_str=datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )
        st.download_button(
            label="🖨️ Imprimir Termo Compliance",
            data=pdf_comp,
            file_name=f"Termo_Compliance_PM_{num_pm}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    meus_bens = [b for b in all_bens_banco if b.get("fiel_depositario_atual") == nome_militar_atual and b.get("status_tramite") == "Em Custódia"]
    
    if meus_bens:
        for mb in meus_bens:
            dt_posse_m = mb.get("data_posse_atual") or mb.get("data_ingestao")
            txt_t, alert_m, _ = calcular_tempo_decorrido_detalhado(dt_posse_m)
            mb["tempo_posse"] = f"🚨 {txt_t}" if alert_m else txt_t
            mb["status_edicao"] = "Editado" if mb.get("editado_pelo_operador") else "Original"

        df_mb = pd.DataFrame(meus_bens)
        st.dataframe(
            df_mb[["id_bem", "num_reds", "autores", "descricao", "quantidade", "unidade_medida", "involucro_lacre", "tempo_posse", "status_edicao"]],
            column_config={
                "id_bem": "Código Bem",
                "num_reds": "Nº REDS",
                "autores": "Autor(es)",
                "descricao": "Descrição",
                "quantidade": "Qtd",
                "unidade_medida": "Unid",
                "involucro_lacre": "Invólucro / Lacre",
                "tempo_posse": "Tempo na Posse",
                "status_edicao": "Origem"
            },
            hide_index=True, use_container_width=True
        )
        
        st.divider()
        st.markdown("##### ⚙️ Ações e Mídias Anexas:")
        for idx_m, item_meu in enumerate(meus_bens):
            e_marrom = (idx_m % 2 != 0)
            classe_card = "card-brown" if e_marrom else "card-blue"
            
            midias = item_meu.get("midias_anexas") or []
            str_midias = f"📎 <b>{len(midias)} arquivo(s) anexo(s)</b>" if midias else "Nenhuma mídia anexa"

            html_card = f"""
            <div class="{classe_card}">
                📄 REDS: <b>{item_meu.get('num_reds', 'N/I')}</b> | Código: <b>{item_meu.get('id_bem', 'N/I')}</b><br/>
                📦 Material: <b>{item_meu.get('descricao', 'N/I')}</b><br/>
                👤 Autor: <b>{item_meu.get('autores', 'AUTOR NÃO INFORMADO')}</b><br/>
                <small>🔒 Lacre: <b>{item_meu.get('involucro_lacre', 'N/I')}</b> | Qtd: <b>{item_meu.get('quantidade', '1.0')} {item_meu.get('unidade_medida', 'UN')}</b> | {str_midias}</small>
            </div>
            """
            st.markdown(html_card, unsafe_allow_html=True)
            
            c_act1, c_act2 = st.columns([4, 1])
            with c_act2:
                if st.button("✏️ Editar / Anexar", key=f"btn_edit_meu_bem_{item_meu['id_bem']}_{idx_m}", use_container_width=True):
                    abrir_modal_edicao_material(item_meu, nome_militar_atual, unidade_militar_atual)
    else:
        st.info("Você não possui nenhum material sob sua custódia no momento.")

# =============================================================================
# ABA 3: TRAMITAÇÃO COM DESTINO AO CREDS TCO DA COMPANHIA
# =============================================================================
def renderizar_aba_transferencias(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    injetar_css_cards_alternados()
    st.markdown("#### 🔄 Tramitação Multi-Unidades & Aceite Parcial")
    
    unidades_creds_destino = obter_lista_creds_dinamica()
    meus_bens = [b for b in all_bens_banco if b.get("fiel_depositario_atual") == nome_militar_atual and b.get("status_tramite") == "Em Custódia"]

    with st.expander("🔍 **Filtros de Pesquisa na Tramitação**", expanded=True):
        f3_col1, f3_col2, f3_col3, f3_col4 = st.columns(4)
        with f3_col1:
            f3_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-000484967", key="f3_reds").strip()
        with f3_col2:
            f3_autor = st.text_input("Nome do Autor:", placeholder="Ex: DOUGLAS", key="f3_autor").strip()
        with f3_col3:
            f3_militar = st.text_input("Militar / Custodiante:", placeholder="Ex: ALEXANDRINO", key="f3_militar").strip()
        with f3_col4:
            f3_unidade = st.selectbox("Unidade Fiel Depósito:", ["TODAS AS UNIDADES"] + [u for u in unidades_creds_destino if "✏️" not in u], key="f3_unidade")

    meus_bens_filtrados = aplicar_filtros_bens(meus_bens, f3_reds, f3_autor, f3_militar, f3_unidade)
    
    mils_todos = carregar_militares_supabase()
    nomes_mils_base = [f"{m.get('posto_grad')} {m.get('nome_guerra')}" for m in mils_todos] if mils_todos else ["CB MORAES", "SD VINICIUS", "SGT SILVA"]
    opcoes_destinatarios_geral = unidades_creds_destino + [n for n in nomes_mils_base if n != nome_militar_atual]

    with st.container(border=True):
        st.markdown("##### 📤 1. Encaminhar Materiais em LOTE")
        st.caption("Envie um ou múltiplos materiais para o CREDS TCO da Companhia/Batalhão ou para outro militar específico.")

        bens_disp = {
            f"{b['id_bem']} | REDS: {b['num_reds']} - {b['descricao']} (Lacre: {b.get('involucro_lacre', 'N/I')})": b['id_bem'] 
            for b in meus_bens_filtrados
        }

        if bens_disp:
            itens_selecionados_keys = st.multiselect(
                "Selecione o(s) Material(is) para Tramitar:",
                options=list(bens_disp.keys()),
                key="ms_materiais_transf_v35"
            )
            
            c_tr1, c_tr2 = st.columns(2)
            with c_tr1:
                destinatario_sel = st.selectbox("Selecione o Destino (CREDS Cia ou Militar):", opcoes_destinatarios_geral, key="sel_destinatario_v35")
                destino_final_tram = destinatario_sel
                if destinatario_sel == "✏️ Outro CREDS / Digitar Manualmente":
                    destino_final_tram = st.text_input("Digite o Nome do CREDS de Destino:", placeholder="Ex: CREDS TCO - 285ª CIA TM").strip().upper()

            with c_tr2:
                unidade_dest_sel = st.text_input("Unidade Responsável:", value=unidade_militar_atual).strip().upper()
            
            obs_transf = st.text_input("Observações Gerais da Tramitação:", key="txt_obs_transf_v35", placeholder="Ex: Encaminhado para o depósito do CREDS TCO da Cia")
            qtd_sel_envio = len(itens_selecionados_keys)
            
            btn_tramitar = st.button(
                f"📤 Tramitar {qtd_sel_envio} Material(is) Selecionado(s)", 
                type="primary", 
                disabled=(qtd_sel_envio == 0),
                key="btn_tramitar_lote_v35",
                use_container_width=True
            )

            if btn_tramitar:
                now_iso = datetime.datetime.now().isoformat()
                sucessos = 0
                
                for key_item in itens_selecionados_keys:
                    id_bem_alvo = bens_disp[key_item]
                    bem_obj = next(b for b in all_bens_banco if b["id_bem"] == id_bem_alvo)
                    
                    upd_data = {
                        "status_tramite": "Pendente Aceite",
                        "remetente_ultimo": nome_militar_atual,
                        "unidade_remetente": unidade_militar_atual,
                        "destinatario_pendente": destino_final_tram,
                        "unidade_destinatario_pendente": unidade_dest_sel,
                        "data_envio_tramite": now_iso,
                        "obs_tramite": obs_transf
                    }
                    
                    if atualizar_material_supabase(id_bem_alvo, upd_data):
                        registrar_log_supabase({
                            "data_hora": now_iso,
                            "num_reds": bem_obj["num_reds"],
                            "bem_id": id_bem_alvo,
                            "acao": "SOLICITAÇÃO DE TRAMITAÇÃO EM LOTE",
                            "origem": nome_militar_atual,
                            "unidade_origem": unidade_militar_atual,
                            "destino": destino_final_tram,
                            "unidade_destino": unidade_dest_sel,
                            "detalhe": f"Encaminhado para {destino_final_tram} ({unidade_dest_sel}). Obs: {obs_transf}"
                        })
                        sucessos += 1

                st.success(f"Tramitação de {sucessos} material(is) registrada com sucesso!")
                st.rerun()
        else:
            st.info("Nenhum material sob sua custódia disponível para tramitação com os filtros atuais.")

    st.divider()

    usr_logado = st.session_state.get("usuario_dados", {})
    perfil_creds_usr = str(usr_logado.get("perfil_creds", "TROPA")).upper()
    perfil_usr = str(usr_logado.get("nivel_acesso", "TROPA")).upper()
    cargo_usr = str(usr_logado.get("cargo_funcao", "")).upper()
    
    eh_gestor_creds = perfil_creds_usr in ["GESTOR_UNIDADE", "GESTOR_CIA", "OPERADOR"] or "CREDS" in perfil_usr or "PROGRAMADOR" in cargo_usr or "ADMIN" in perfil_usr

    with st.container(border=True):
        st.markdown("##### 📥 2. Recebimento de Custódia")
        st.caption("Confira os materiais direcionados a você ou à caixa do CREDS TCO da sua Companhia.")

        pendentes_para_mim = []
        for b in all_bens_banco:
            if b.get("status_tramite") == "Pendente Aceite":
                dest_p = str(b.get("destinatario_pendente", ""))
                if dest_p == nome_militar_atual or (eh_gestor_creds and "CREDS" in dest_p):
                    pendentes_para_mim.append(b)

        pendentes_filtrados = aplicar_filtros_bens(pendentes_para_mim, f3_reds, f3_autor, f3_militar, f3_unidade)

        if pendentes_filtrados:
            df_pend = pd.DataFrame(pendentes_filtrados)
            if "receber" not in df_pend.columns:
                df_pend.insert(0, "receber", True)

            df_editado_rec = st.data_editor(
                df_pend[["receber", "id_bem", "num_reds", "descricao", "involucro_lacre", "remetente_ultimo", "unidade_remetente", "obs_tramite"]],
                column_config={
                    "receber": st.column_config.CheckboxColumn("✅ Receber?", default=True, width="small"),
                    "id_bem": st.column_config.TextColumn("Código Bem", disabled=True, width="small"),
                    "num_reds": st.column_config.TextColumn("Nº REDS", disabled=True, width="medium"),
                    "descricao": st.column_config.TextColumn("Descrição do Material", disabled=True, width="large"),
                    "involucro_lacre": st.column_config.TextColumn("Nº Lacre", disabled=True, width="medium"),
                    "remetente_ultimo": st.column_config.TextColumn("Remetente", disabled=True, width="medium"),
                    "unidade_remetente": st.column_config.TextColumn("Unidade Origem", disabled=True, width="medium"),
                    "obs_tramite": st.column_config.TextColumn("Obs Envio", disabled=True, width="medium")
                },
                hide_index=True,
                use_container_width=True,
                key="editor_pendentes_rec_v35"
            )

            itens_aceitar = df_editado_rec[df_editado_rec["receber"] == True]
            itens_recusar = df_editado_rec[df_editado_rec["receber"] == False]

            qtd_aceitar = len(itens_aceitar)
            qtd_recusar = len(itens_recusar)

            col_acc1, col_acc2 = st.columns(2)
            with col_acc1:
                btn_aceitar_selecionados = st.button(
                    f"✅ Confirmar Recebimento ({qtd_aceitar} item/ns)",
                    type="primary",
                    disabled=(qtd_aceitar == 0),
                    use_container_width=True,
                    key="btn_acc_sel_v35"
                )

            with col_acc2:
                btn_recusar_desmarcados = st.button(
                    f"⚠️ Registrar Divergência / Recusa nos Não Marcados ({qtd_recusar} item/ns)",
                    disabled=(qtd_recusar == 0),
                    use_container_width=True,
                    key="btn_rec_des_v35"
                )

            if btn_aceitar_selecionados:
                now_iso = datetime.datetime.now().isoformat()
                sucessos_acc = 0

                for idx_a, row_a in itens_aceitar.iterrows():
                    id_bem_acc = str(row_a["id_bem"])
                    p_orig = next(b for b in pendentes_filtrados if b["id_bem"] == id_bem_acc)
                    
                    orig = p_orig.get('remetente_ultimo') or p_orig.get('fiel_depositario_atual')
                    orig_unid = p_orig.get('unidade_remetente') or p_orig.get('unidade_posse_atual')

                    upd_data = {
                        "fiel_depositario_atual": nome_militar_atual,
                        "unidade_posse_atual": unidade_militar_atual,
                        "data_posse_atual": now_iso,
                        "status_tramite": "Em Custódia",
                        "destinatario_pendente": None,
                        "unidade_destinatario_pendente": None,
                        "data_envio_tramite": None
                    }

                    if atualizar_material_supabase(id_bem_acc, upd_data):
                        registrar_log_supabase({
                            "data_hora": now_iso,
                            "num_reds": p_orig["num_reds"],
                            "bem_id": id_bem_acc,
                            "acao": "ACEITE DE CUSTÓDIA FÍSICA",
                            "origem": orig,
                            "unidade_origem": orig_unid,
                            "destino": nome_militar_atual,
                            "unidade_destino": unidade_militar_atual,
                            "detalhe": f"Aceite de custódia confirmado por {nome_militar_atual} na unidade {unidade_militar_atual}."
                        })
                        sucessos_acc += 1

                st.success(f"{sucessos_acc} material(is) incorporado(s) à sua custódia física!")
                st.rerun()

            if btn_recusar_desmarcados:
                st.warning("⚠️ Informe o motivo e a justificativa para a recusa dos itens desmarcados:")
                with st.form("form_motivo_recusa_lote_v35"):
                    motivo_lote = st.selectbox(
                        "Motivo da Divergência:",
                        [
                            "Invólucro / Lacre Violado ou Rompido",
                            "Quantidade do Material Menor que a Declarada",
                            "Material Avariado / Danificado",
                            "Objeto Incompatível com a Descrição",
                            "Material Ausente / Não Entregue pelo Remetente"
                        ]
                    )
                    justificativa_lote = st.text_area("Justificativa Detalhada (Mínimo 10 caracteres):", placeholder="Descreva o motivo da não aceitação deste material...")
                    btn_confirmar_recusa_lote = st.form_submit_button("🚨 Confirmar Recusa/Divergência", type="primary", use_container_width=True)

                    if btn_confirmar_recusa_lote:
                        if not justificativa_lote or len(justificativa_lote.strip()) < 10:
                            st.error("A justificativa detalhada é obrigatória.")
                        else:
                            now_iso = datetime.datetime.now().isoformat()
                            now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                            sucessos_div = 0

                            for idx_r, row_r in itens_recusar.iterrows():
                                id_bem_rec = str(row_r["id_bem"])
                                p_orig = next(b for b in pendentes_filtrados if b["id_bem"] == id_bem_rec)
                                
                                origem_remetente = p_orig.get("remetente_ultimo") or p_orig.get("fiel_depositario_atual")
                                unidade_remetente = p_orig.get("unidade_remetente") or p_orig.get("unidade_posse_atual")

                                dados_div = {
                                    "motivo": motivo_lote,
                                    "justificativa": justificativa_lote.strip(),
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

                                if atualizar_material_supabase(id_bem_rec, upd_data):
                                    registrar_log_supabase({
                                        "data_hora": now_iso,
                                        "num_reds": p_orig["num_reds"],
                                        "bem_id": id_bem_rec,
                                        "acao": "REGISTRO DE DIVERGÊNCIA / RECUSA",
                                        "origem": origem_remetente,
                                        "unidade_origem": unidade_remetente,
                                        "destino": nome_militar_atual,
                                        "unidade_destino": unidade_militar_atual,
                                        "detalhe": f"MOTIVO: {motivo_lote} | JUSTIFICATIVA: {justificativa_lote.strip()}"
                                    })
                                    sucessos_div += 1

                            st.success(f"Divergência registrada para {sucessos_div} material(is)!")
                            st.rerun()

        else:
            st.info("Nenhuma transferência pendente de aceite para você ou para o CREDS TCO da sua Cia.")

# =============================================================================
# ABA 5: PAINEL CREDS-TCO
# =============================================================================
def renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual):
    injetar_css_cards_alternados()
    st.markdown("#### 🏛️ Painel do Gestor CREDS-TCO & Rastreamento de Custódia")
    
    if not eh_gestor_creds:
        st.error("🔒 **Acesso Restrito:** Apenas Gestores do CREDS-TCO, P1, Comandantes ou Administradores têm acesso a esta área.")
        return

    with st.container(border=True):
        st.markdown("##### 📊 Relatório Panorâmico (Excel) & Filtro de Período")
        c_exp1, c_exp2, c_exp3 = st.columns([1.5, 1.5, 1])
        
        with c_exp1:
            lista_creds_opts = ["TODOS OS CREDS (ACERVO GERAL)"] + [u for u in obter_lista_creds_dinamica() if "✏️" not in u]
            creds_selecionado = st.selectbox("Selecione o CREDS / Unidade:", lista_creds_opts, key="sb_creds_filtro_main")

        with c_exp2:
            dt_hoje = datetime.date.today()
            dt_30d = dt_hoje - datetime.timedelta(days=30)
            periodo_datas = st.date_input(
                "Período de Entrada (Início e Fim):",
                value=(dt_30d, dt_hoje),
                key="range_datas_creds"
            )

        bens_filtrados_painel = all_bens_banco.copy()

        if creds_selecionado != "TODOS OS CREDS (ACERVO GERAL)":
            unid_str = creds_selecionado.replace("CREDS TCO - ", "").strip()
            bens_filtrados_painel = [
                b for b in bens_filtrados_painel
                if unid_str.lower() in str(b.get("unidade_posse_atual", "")).lower() or
                   unid_str.lower() in str(b.get("destinatario_pendente", "")).lower() or
                   unid_str.lower() in str(extrair_unidade_mae_creds(str(b.get("unidade_posse_atual", ""))) or "").lower()
            ]

        if isinstance(periodo_datas, tuple) and len(periodo_datas) == 2:
            d_ini, d_fim = periodo_datas
            bens_periodo = []
            for b in bens_filtrados_painel:
                dt_str = b.get("data_ingestao") or b.get("data_posse_atual")
                if dt_str:
                    try:
                        dt_obj = pd.to_datetime(dt_str).date()
                        if d_ini <= dt_obj <= d_fim:
                            bens_periodo.append(b)
                    except Exception:
                        bens_periodo.append(b)
                else:
                    bens_periodo.append(b)
            bens_filtrados_painel = bens_periodo

        with c_exp3:
            st.markdown("<br>", unsafe_allow_html=True)
            if bens_filtrados_painel:
                excel_bytes = gerar_excel_panoramico_tco(bens_filtrados_painel)
                st.download_button(
                    label=f"📥 Baixar Excel ({len(bens_filtrados_painel)} itens)",
                    data=excel_bytes,
                    file_name=f"Relatorio_TCO_{creds_selecionado.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            else:
                st.warning("Nenhum item encontrado.")

    st.divider()

    bens_processados = []
    q_parados = 0
    q_custodia = 0
    q_pericia = 0
    q_destruicao = 0

    for b in bens_filtrados_painel:
        ponto_cad, tempo_str, alerta_4d, dias_num = obter_status_gargalo_e_tempo(b, e_marrom=False)
        b_copy = dict(b)
        b_copy["_ponto_cadeia"] = ponto_cad
        b_copy["_tempo_str"] = tempo_str
        b_copy["_alerta_4dias"] = alerta_4d
        bens_processados.append(b_copy)

        if alerta_4d:
            q_parados += 1
        if b.get("fase_destinacao") == "Com Fiel Depositário / Policial":
            q_custodia += 1
        if "Perícia" in str(b.get("fase_destinacao", "")):
            q_pericia += 1
        if "Destruição" in str(b.get("fase_destinacao", "")) or "DESTRUÍDO" in str(b.get("fase_destinacao", "")):
            q_destruicao += 1

    kp1, kp2, kp3, kp4 = st.columns(4)
    with kp1:
        st.metric("📦 Em Custódia", q_custodia)
    with kp2:
        st.metric("🔬 Em Perícia", q_pericia)
    with kp3:
        st.metric("🔥 Destruição", q_destruicao)
    with kp4:
        st.metric("🚨 Parados > 4 Dias", q_parados)

    st.markdown(f"##### 📦 Acervo Exibido ({len(bens_processados)} item/ns):")
    
    for idx_creds, bem in enumerate(bens_processados):
        e_marrom = (idx_creds % 2 != 0)
        classe_card = "card-brown" if e_marrom else "card-blue"
        ponto_cad_card, tempo_str_card, alerta_4d_card, _ = obter_status_gargalo_e_tempo(bem, e_marrom=e_marrom)

        if e_marrom:
            tempo_html = f"<strong style='color: #991B1B;'>{tempo_str_card} (PARADO > 4 DIAS)</strong>" if alerta_4d_card else f"<strong style='color: #000000;'>{tempo_str_card}</strong>"
        else:
            tempo_html = f"<span style='color: #F87171; font-weight: bold;'>{tempo_str_card} (PARADO > 4 DIAS)</span>" if alerta_4d_card else f"<span style='color: #4ADE80; font-weight: bold;'>{tempo_str_card}</span>"

        html_item = f"""
        <div class="{classe_card}">
            📄 REDS: <b>{bem['num_reds']}</b> | Código Bem: <b>{bem['id_bem']}</b> | Material: <b>{bem['descricao']}</b><br/>
            📍 Status: {ponto_cad_card}<br/>
            ⏱️ Tempo Imóvel na Etapa: {tempo_html}
        </div>
        """
        st.markdown(html_item, unsafe_allow_html=True)

# =============================================================================
# ABA 6: TRILHA DE AUDITORIA
# =============================================================================
def renderizar_aba_logs(all_logs_banco):
    st.markdown("#### 📜 Trilha de Auditoria Imutável da Custódia (Supabase)")
    
    with st.expander("🔍 **Filtros de Pesquisa na Trilha de Auditoria**", expanded=True):
        f5_col1, f5_col2, f5_col3, f5_col4 = st.columns(4)
        with f5_col1:
            f5_reds = st.text_input("REDS:", placeholder="Ex: 2026-000484967", key="f5_reds").strip()
        with f5_col2:
            f5_busca = st.text_input("Palavra-chave / Detalhes:", placeholder="Ex: Edição, Lacre, SHA-256", key="f5_busca").strip()
        with f5_col3:
            f5_militar = st.text_input("Militar Envolvido:", placeholder="Ex: ALEXANDRINO", key="f5_militar").strip()
        with f5_col4:
            usar_f5_data = st.checkbox("Filtrar por Período de Data", key="f5_chk_data")
            if usar_f5_data:
                dt_hoje = datetime.date.today()
                dt_30d = dt_hoje - datetime.timedelta(days=30)
                f5_periodo = st.date_input("Período (Início e Fim):", value=(dt_30d, dt_hoje), key="f5_periodo_logs")
            else:
                f5_periodo = None

    logs_filtrados = aplicar_filtros_logs(all_logs_banco, f5_reds, f5_busca, f5_militar, f5_periodo)
    
    if logs_filtrados:
        df_l = pd.DataFrame(logs_filtrados)
        if "data_hora" in df_l.columns and not df_l.empty:
            df_l["data_hora"] = df_l["data_hora"].apply(
                lambda x: pd.to_datetime(x).strftime("%d/%m/%Y %H:%M") if pd.notna(x) and str(x).strip() not in ["", "None", "NaT"] else "N/I"
            )

        cols_exibicao = ["data_hora", "num_reds", "bem_id", "acao", "origem", "unidade_origem", "destino", "unidade_destino", "detalhe"]
        cols_reais = [c for c in cols_exibicao if c in df_l.columns]
        st.dataframe(df_l[cols_reais], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum registro de auditoria encontrado com os parâmetros selecionados.")

# =============================================================================
# ABA 7: DESIGNAÇÃO DE GESTORES
# =============================================================================
def renderizar_aba_gestores_creds(nome_operador, unidade_operador, cargo_operador, perfil_operador):
    usr_logado = st.session_state.get("usuario_dados", {})
    eh_autorizado = usuario_eh_gestor_creds(usr_logado)

    if not eh_autorizado:
        st.error("🔒 **Acesso Restrito:** Apenas Gestores do CREDS, Comandantes de Cia ou Administradores do SIOP podem gerenciar funções do TCO.")
        return

    perfil_creds_usr = usr_logado.get("perfil_creds", "TROPA")
    perfil_geral_usr = usr_logado.get("nivel_acesso", "TROPA")
    eh_gestor_unidade = (perfil_creds_usr == "GESTOR_UNIDADE" or perfil_geral_usr in ["ADMIN", "PROGRAMADOR"])

    st.markdown("#### 👥 Designação e Estrutura de Gestores do CREDS / TCO")
    if eh_gestor_unidade:
        st.caption("🌐 **Visão Global (Batalhão):** Você possui permissão para gerenciar a função CREDS de **todas as Companhias**.")
    else:
        st.caption(f"🏢 **Visão Restrita:** Atribuição de permissão CREDS limitada à **{unidade_operador}**.")

    all_milit = carregar_militares_supabase()
    if not eh_gestor_unidade:
        all_milit = [m for m in all_milit if str(m.get("unidade", "")).strip().upper() == str(unidade_operador).strip().upper()]

    mapa_graduacoes = {}
    for m in all_milit:
        pm_num = str(m.get("num_policia") or m.get("usuario_login") or "").strip().upper()
        grad = m.get("posto_grad") or m.get("graduacao") or m.get("cargo_funcao")
        if pm_num and grad:
            mapa_graduacoes[pm_num] = str(grad).strip().upper()

    usuarios_banco = []
    if supabase:
        try:
            query = supabase.table("usuarios").select("*")
            if not eh_gestor_unidade:
                query = query.eq("unidade", unidade_operador)
            res_u = query.execute()
            usuarios_banco = res_u.data or []
        except Exception as e:
            st.warning(f"Aviso ao consultar lista de usuários: {e}")

    df_u = pd.DataFrame(usuarios_banco) if usuarios_banco else pd.DataFrame()
    col_des1, col_des2 = st.columns([2, 2.2])

    with col_des1:
        with st.container(border=True):
            st.markdown("##### ➕ Alternar Função CREDS do Militar")
            
            opcoes_militar = {
                f"{m.get('posto_grad') or m.get('graduacao', 'PM')} {m.get('nome_guerra')} (PM: {m.get('num_policia')}) - Lotação: {m.get('unidade', 'N/I')}": m
                for m in all_milit
            }

            if opcoes_militar:
                militar_sel_key = st.selectbox("Selecione o Policial Militar:", list(opcoes_militar.keys()), key="sel_mil_creds_aba7")
                militar_obj = opcoes_militar[militar_sel_key]
                num_pm = str(militar_obj.get("num_policia", "")).strip()

                u_cadastrado = next((u for u in usuarios_banco if str(u.get("usuario_login") or u.get("usuario")).upper() == num_pm.upper()), {})
                perfil_creds_atual = u_cadastrado.get("perfil_creds", "TROPA")

                opcoes_perfis = {
                    "GESTOR_UNIDADE": "Gestor CREDS Unidade (Acesso Global 21º BPM)",
                    "GESTOR_CIA": "Gestor CREDS Cia (Tramita, Despacha e Destina)",
                    "OPERADOR": "Operador CREDS (Preenchimento e Relatora)",
                    "TROPA": "Tropa em Campo (Registro e Upload Ordinário)"
                }

                chaves_disponiveis = list(opcoes_perfis.keys())
                if not eh_gestor_unidade:
                    chaves_disponiveis.remove("GESTOR_UNIDADE")

                index_default = chaves_disponiveis.index(perfil_creds_atual) if perfil_creds_atual in chaves_disponiveis else len(chaves_disponiveis) - 1

                novo_perfil_creds = st.selectbox(
                    "Selecione a Função no Módulo CREDS/TCO:",
                    options=chaves_disponiveis,
                    format_func=lambda x: opcoes_perfis[x],
                    index=index_default,
                    key="sel_novo_perfil_creds_aba7"
                )

                if st.button("💾 Salvar Função CREDS", type="primary", use_container_width=True, key="btn_add_creds_aba7"):
                    if atualizar_usuario_supabase(num_pm, {"perfil_creds": novo_perfil_creds}):
                        registrar_audit_log(
                            operador_pm=str(usr_logado.get("usuario_login") or usr_logado.get("num_policia")),
                            alvo_pm=num_pm,
                            tipo_acao="ALTERAÇÃO_FUNÇÃO_CREDS",
                            descricao=f"Função CREDS do militar {militar_obj.get('nome_guerra')} ({num_pm}) alterada para {novo_perfil_creds}."
                        )
                        st.success(f"Função CREDS de **{militar_obj.get('nome_guerra')}** atualizada para **{opcoes_perfis[novo_perfil_creds]}**!")
                        st.rerun()
            else:
                st.info("Nenhum militar localizado no seu escopo de lotação.")

    with col_des2:
        with st.container(border=True):
            st.markdown("##### 🏛️ Gestores e Operadores CREDS Ativos")
            
            gestores_creds = []
            if not df_u.empty and "perfil_creds" in df_u.columns:
                gestores_creds = df_u[df_u["perfil_creds"].isin(["GESTOR_UNIDADE", "GESTOR_CIA", "OPERADOR"])].to_dict("records")

            if gestores_creds:
                grupos_creds = {}
                for g in gestores_creds:
                    unid_g = str(g.get("unidade", "35ª CIA PM")).strip().upper()
                    if unid_g not in grupos_creds:
                        grupos_creds[unid_g] = []
                    grupos_creds[unid_g].append(g)

                for unid_nome, lista_gestores in grupos_creds.items():
                    with st.expander(f"🏢 **CREDS TCO - {unid_nome}** ({len(lista_gestores)} Integrante/s)", expanded=True):
                        for idx_g, g in enumerate(lista_gestores):
                            pm_key = str(g.get("usuario_login") or g.get("usuario") or "").strip().upper()
                            grad_correta = (
                                mapa_graduacoes.get(pm_key) or 
                                g.get("posto_grad") or 
                                g.get("graduacao") or 
                                g.get("cargo_funcao") or 
                                "PM"
                            )
                            with st.container(border=True):
                                c_g1, c_g2 = st.columns([3, 1.5])
                                with c_g1:
                                    st.markdown(f"**👤 {grad_correta} {g.get('nome_guerra', 'OPERADOR')}**")
                                    st.caption(f"Nº Polícia: **{pm_key}** | Função: `{g.get('perfil_creds')}`")
                                with c_g2:
                                    if st.button("🔻 Retornar a Tropa", key=f"btn_revogar_creds_{pm_key}_{idx_g}", use_container_width=True):
                                        if atualizar_usuario_supabase(pm_key, {"perfil_creds": "TROPA"}):
                                            registrar_audit_log(
                                                operador_pm=str(usr_logado.get("usuario_login") or usr_logado.get("num_policia")),
                                                alvo_pm=pm_key,
                                                tipo_acao="REVOGAÇÃO_FUNÇÃO_CREDS",
                                                descricao=f"Função CREDS do militar {pm_key} retornada para TROPA."
                                            )
                                            st.success("Função alterada para TROPA!")
                                            st.rerun()
            else:
                st.info("Nenhum gestor ou operador elevado cadastrado nesta lotação.")