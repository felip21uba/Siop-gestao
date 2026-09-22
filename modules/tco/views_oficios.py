import streamlit as st
import pandas as pd
import datetime
from core.database import supabase
from modules.tco.database import registrar_log_supabase, atualizar_material_supabase
from modules.tco.storage import upload_oficio_pdf_supabase, deletar_arquivo_storage_supabase
from modules.tco.pdf_generator import gerar_pdf_oficio
from modules.tco.docx_generator import gerar_docx_oficio

def renderizar_aba_gerador_oficios(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    """Renderiza o módulo de Ofícios com navegação padronizada por rádio, bordas destacadas e salvamento do modelo de texto."""
    
    # 🎨 INJEÇÃO DE CSS PARA BORDAS MAIS GROSSAS E SOMBRAS NOS CONTAINERS
    st.markdown("""
    <style>
        div[data-testid="stVerticalBlock"] > div[data-testid="stBlock"] > div[data-testid="element-container"] + div[data-testid="stVerticalBlock"] {
            border: 2px solid #334155 !important;
            border-radius: 10px !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4) !important;
            background-color: #0f172a !important;
            padding: 16px !important;
            margin-bottom: 18px !important;
        }
        .box-divisoria-reforcada {
            border: 2px solid #3b82f6 !important;
            box-shadow: 0 4px 14px rgba(59, 130, 246, 0.25) !important;
            border-radius: 10px !important;
            padding: 16px !important;
            margin-bottom: 18px !important;
            background-color: #0f172a !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("#### 📄 Gerador Oficial de Ofícios de Encaminhamento & Repositório Digital")

    # =========================================================================
    # 🔀 BOTÃO DE SELEÇÃO SUPERIOR NO MESMO ESTILO DO PASSO 1 (RADIO HORIZONTAL)
    # =========================================================================
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    
    modo_selecionado = st.radio(
        "Selecione a Funcionalidade:",
        ["📝 Emitir Novo Ofício (PDF / Word)", "📜 Repositório de Ofícios Expedidos"],
        horizontal=True,
        key="radio_submodo_oficios"
    )

    st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

    # =========================================================================
    # FUNÇÃO 1: EMISSÃO DE OFÍCIO
    # =========================================================================
    if "Emitir Novo Ofício" in modo_selecionado:
        st.caption("Emita expedientes oficiais contendo materiais de um único REDS ou múltiplos REDSs unificados.")

        if not all_bens_banco:
            st.info("Nenhum material cadastrado no banco para gerar ofício.")
        else:
            # 🔲 RETÂNGULO 1: SELEÇÃO DE MATERIAIS
            with st.container(border=True):
                st.markdown("##### 📦 1. Seleção dos Materiais Relacionados")
                
                modo_selecao = st.radio(
                    "Como deseja selecionar os materiais?",
                    ["📦 Envio em Bloco (Todos os materiais de um REDS)", "🔀 Seleção Múltipla Livre (Vários REDSs / Materiais Avulsos)"],
                    horizontal=True,
                    key="radio_modo_sel_oficio"
                )

                materiais_selecionados = []

                if "Envio em Bloco" in modo_selecao:
                    reds_unicos = sorted(list(set([str(b.get("num_reds", "")) for b in all_bens_banco if b.get("num_reds")])))
                    reds_escolhido = st.selectbox("Selecione o Número do REDS:", reds_unicos, key="sb_reds_oficio_bloc")
                    
                    if reds_escolhido:
                        materiais_selecionados = [b for b in all_bens_banco if str(b.get("num_reds")) == reds_escolhido]
                        st.success(f"Encontrado(s) **{len(materiais_selecionados)}** material(is) vinculado(s) ao REDS **{reds_escolhido}**.")
                else:
                    bens_map = {
                        f"REDS: {b['num_reds']} | {b['descricao']} (Lacre: {b.get('involucro_lacre', 'N/I')} - Autor: {b.get('autores', 'N/I')})": b 
                        for b in all_bens_banco
                    }
                    chaves_sel = st.multiselect("Selecione um ou mais materiais (pode ser de REDSs diferentes):", list(bens_map.keys()), key="ms_mats_oficio_free")
                    materiais_selecionados = [bens_map[k] for k in chaves_sel]

                if materiais_selecionados:
                    st.markdown("**Pré-visualização da Tabela do Ofício:**")
                    df_prev = pd.DataFrame(materiais_selecionados)
                    st.dataframe(
                        df_prev[["num_reds", "descricao", "involucro_lacre", "autores"]],
                        column_config={
                            "num_reds": "Nº REDS",
                            "descricao": "Descrição do Material",
                            "involucro_lacre": "Nº Lacre / Invólucro",
                            "autores": "Nome do Autor"
                        },
                        hide_index=True, use_container_width=True
                    )

            # 🔲 RETÂNGULO 2: DADOS DO DESTINATÁRIO
            with st.container(border=True):
                st.markdown("##### 🏛️ 2. Dados do Destinatário / Autoridade")
                
                preset_dest = st.selectbox(
                    "Selecione um destinatário predefinido ou digite o seu:",
                    [
                        "EXCELENTÍSSIMO(A) SENHOR(A) JUIZ(A) DE DIREITO",
                        "ILUSTRÍSSIMO(A) SENHOR(A) DELEGADO(A) REGIONAL DA POLÍCIA CIVIL",
                        "✏️ Outra Autoridade / Digitação Livre"
                    ],
                    key="sb_preset_dest_oficio"
                )

                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    if preset_dest == "✏️ Outra Autoridade / Digitação Livre":
                        destinatario_cargo = st.text_input("Cargo da Autoridade:", placeholder="Ex: PROMOTOR(A) DE JUSTIÇA", key="txt_cargo_dest_free").strip().upper()
                    else:
                        destinatario_cargo = preset_dest

                    destinatario_nome = st.text_input("Nome da Autoridade / Destinatário:", placeholder="Ex: DR. MARCO ANTÔNIO SILVA", key="txt_nome_dest_oficio").strip().upper()

                with col_d2:
                    if "JUIZ" in destinatario_cargo:
                        orgao_padrao = "JUIZADO ESPECIAL CRIMINAL (JECRIM) / FÓRUM"
                    elif "DELEGADO" in destinatario_cargo:
                        orgao_padrao = "DELEGACIA REGIONAL DE POLÍCIA CIVIL (PCMG)"
                    else:
                        orgao_padrao = "ÓRGÃO JUDICIÁRIO / POLICIAL"

                    orgao_destino = st.text_input("Órgão / Destino:", value=orgao_padrao, key="txt_orgao_dest_oficio").strip().upper()

            # 🔲 RETÂNGULO 3: DADOS DO OFÍCIO E TEXTO DO EXPEDIENTE (COM BOTÃO SALVAR)
            with st.container(border=True):
                st.markdown("##### 📝 3. Dados do Ofício e Texto do Expediente")
                
                c_of1, c_of2 = st.columns(2)
                with c_of1:
                    val_num_oficio = f"OFÍCIO {datetime.datetime.now().strftime('%Y%m%d')}-35CIA"
                    num_oficio = st.text_input("Nº do Ofício:", value=val_num_oficio, key="txt_num_oficio_gen").strip().upper()
                with c_of2:
                    pa_oficio = st.text_input("Referência:", placeholder="Ex: P.A. 104/2026, Processo nº 00123/2026...", key="txt_pa_oficio_gen").strip().upper()

                # Extração automática dos REDSs selecionados
                lista_reds_unicos = sorted(list(set([str(m['num_reds']) for m in materiais_selecionados if m.get('num_reds')])))
                reds_listados_str = ", ".join(lista_reds_unicos) if lista_reds_unicos else "[SELECIONE OS MATERIAIS NO PASSO 1]"

                # Modelo Padrão com a Tag {REDS}
                if "modelo_texto_oficio_padrao" not in st.session_state:
                    st.session_state["modelo_texto_oficio_padrao"] = (
                        "Cumprimentando-o(a) cordialmente, encaminho a Vossa Excelência/Senhoria o(s) material(is) apreendido(s) "
                        "vinculado(s) ao(s) REDS Nº {REDS}, conforme discriminado na tabela acima, para as providências "
                        "de praxe relativas ao procedimento em epígrafe.\n\n"
                        "Ressalta-se que o(s) referido(s) bem(ns) encontra(m)-se devidamente acondicionado(s) em invólucro(s) inspecionado(s) "
                        "e registrado(s), garantindo a preservação da Cadeia de Custódia nos termos do Artigo 158-A e seguintes do Código de Processo Penal."
                    )

                texto_base = st.session_state["modelo_texto_oficio_padrao"].replace("{REDS}", reds_listados_str)

                corpo_texto = st.text_area(
                    "Teor do Expediente (Editável para este documento):",
                    value=texto_base,
                    height=150,
                    key="txt_corpo_oficio_gen"
                )

                c_save1, c_save2 = st.columns([2.8, 1.2])
                with c_save1:
                    st.caption("💡 *Dica: Use `{REDS}` no texto para que os números de BO sejam substituídos automaticamente.*")
                with c_save2:
                    if st.button("💾 Salvar Modelo Padrão", key="btn_salvar_modelo_padrao", type="secondary", use_container_width=True):
                        novo_modelo = corpo_texto.replace(reds_listados_str, "{REDS}")
                        st.session_state["modelo_texto_oficio_padrao"] = novo_modelo
                        st.toast("✅ Novo modelo padrão salvo na sessão!", icon="💾")
                        st.rerun()

            # 🔲 RETÂNGULO 4: EMISSOR E OPÇÕES DE EXPORTAÇÃO
            with st.container(border=True):
                st.markdown("##### ✍️ 4. Emissor & Opções de Exportação")
                
                c_em1, c_em2 = st.columns(2)
                with c_em1:
                    emissor_nome = st.text_input("Nome Completo do Emissor:", value=str(nome_militar_atual), key="txt_emissor_nome_oficio").strip().upper()
                with c_em2:
                    emissor_cargo = st.text_input("Cargo / Função:", value="RESPONSÁVEL PELA CUSTÓDIA / CREDS", key="txt_emissor_cargo_oficio").strip().upper()

                st.markdown("<br>", unsafe_allow_html=True)
                
                col_exp1, col_exp2 = st.columns(2)

                with col_exp1:
                    btn_gerar_pdf = st.button("📄 Gerar e Baixar em PDF (Oficial)", type="primary", disabled=(not materiais_selecionados), key="btn_gerar_oficio_pdf", use_container_width=True)

                with col_exp2:
                    btn_gerar_docx = st.button("📝 Gerar e Baixar em DOCX (Word Editável)", disabled=(not materiais_selecionados), key="btn_gerar_oficio_docx", use_container_width=True)

                if btn_gerar_pdf:
                    if not destinatario_nome or not destinatario_cargo or not corpo_texto:
                        st.error("⚠️ Preencha os campos de Destinatário e Teor do Expediente.")
                    else:
                        pdf_bytes, hash_sha = gerar_pdf_oficio(
                            num_oficio=num_oficio,
                            destinatario_nome=destinatario_nome,
                            destinatario_cargo=destinatario_cargo,
                            orgao_destino=orgao_destino,
                            lista_materiais=materiais_selecionados,
                            pa_oficio=pa_oficio,
                            corpo_texto=corpo_texto,
                            emissor_nome=emissor_nome,
                            emissor_cargo=emissor_cargo,
                            emissor_unidade=unidade_militar_atual
                        )

                        now_iso = datetime.datetime.now().isoformat()
                        first_reds = materiais_selecionados[0]["num_reds"] if materiais_selecionados else "N/I"
                        
                        res_storage = upload_oficio_pdf_supabase(pdf_bytes, num_oficio, first_reds)
                        url_pdf = res_storage.get("url_publica") if res_storage else None

                        for m_item in materiais_selecionados:
                            atualizar_material_supabase(m_item["id_bem"], {
                                "fase_destinacao": f"Encaminhado ({orgao_destino})",
                                "pa_oficio_autorizador": num_oficio
                            })
                            
                            registrar_log_supabase({
                                "data_hora": now_iso,
                                "num_reds": m_item["num_reds"],
                                "bem_id": m_item["id_bem"],
                                "web_origem": "SIOP_TCO",
                                "acao": "EMISSÃO DE OFÍCIO DE ENCAMINHAMENTO (PDF)",
                                "origem": nome_militar_atual,
                                "unidade_origem": unidade_militar_atual,
                                "destino": orgao_destino,
                                "unidade_destino": "Órgão Externo",
                                "detalhe": f"GERADO {num_oficio} | Dest: {destinatario_nome} | SHA-256: {hash_sha} | URL: {url_pdf or 'N/I'}"
                            })

                        st.success("✅ Ofício PDF gerado com sucesso!")
                        st.download_button(
                            label="📥 Clique para Baixar o PDF Oficial",
                            data=pdf_bytes,
                            file_name=f"{num_oficio.replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            type="primary",
                            key="btn_dl_oficio_pdf_out",
                            use_container_width=True
                        )

                if btn_gerar_docx:
                    if not destinatario_nome or not destinatario_cargo or not corpo_texto:
                        st.error("⚠️ Preencha os campos de Destinatário e Teor do Expediente.")
                    else:
                        docx_bytes = gerar_docx_oficio(
                            num_oficio=num_oficio,
                            destinatario_nome=destinatario_nome,
                            destinatario_cargo=destinatario_cargo,
                            orgao_destino=orgao_destino,
                            lista_materiais=materiais_selecionados,
                            pa_oficio=pa_oficio,
                            corpo_texto=corpo_texto,
                            emissor_nome=emissor_nome,
                            emissor_cargo=emissor_cargo,
                            emissor_unidade=unidade_militar_atual
                        )

                        st.success("✅ Minuta em Word (.docx) gerada com sucesso!")
                        st.download_button(
                            label="📥 Clique para Baixar o Arquivo Word (.docx)",
                            data=docx_bytes,
                            file_name=f"{num_oficio.replace(' ', '_')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="btn_dl_oficio_docx_out",
                            use_container_width=True
                        )

    # =========================================================================
    # FUNÇÃO 2: REPOSITÓRIO DE OFÍCIOS (RETÂNGULOS DELIMITADOS)
    # =========================================================================
    else:
        st.caption("Resgate a segunda via em PDF exata de qualquer ofício expedido ou realize a exclusão do expediente se necessário.")

        logs_oficios = []
        if supabase:
            try:
                res_of = supabase.table("tco_logs").select("*").ilike("acao", "%OFÍCIO%").order("data_hora", desc=True).execute()
                logs_oficios = res_of.data or []
            except Exception as e:
                st.warning(f"Erro ao consultar repositório no Supabase: {e}")

        if logs_oficios:
            for idx_of, log_item in enumerate(logs_oficios):
                detalhe_txt = str(log_item.get("detalhe", ""))
                
                url_pdf = None
                path_st = None
                if "URL: " in detalhe_txt:
                    url_pdf = detalhe_txt.split("URL: ")[1].split(" |")[0].strip()
                if "ST_PATH: " in detalhe_txt:
                    path_st = detalhe_txt.split("ST_PATH: ")[1].strip()

                if url_pdf == "N/I":
                    url_pdf = None

                dt_raw = log_item.get("data_hora", "")
                try:
                    dt_fmt = pd.to_datetime(dt_raw).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    dt_fmt = str(dt_raw)[:16]

                with st.container(border=True):
                    c_rep1, c_rep2 = st.columns([3.5, 1.5])
                    
                    with c_rep1:
                        st.markdown(f"📄 REDS: **{log_item.get('num_reds')}**")
                        st.markdown(f"✍️ **Emissor:** {log_item.get('origem')} | 🏛️ **Destino:** {log_item.get('destino')}")
                        st.caption(f"⏱️ **Data/Hora Emissão (DD/MM/AAAA):** {dt_fmt}")
                        st.caption(f"📝 **Detalhes:** {detalhe_txt}")

                    with c_rep2:
                        if url_pdf:
                            st.link_button("📥 Baixar Segunda Via (PDF)", url_pdf, use_container_width=True)
                        else:
                            st.caption("⚠️ PDF original não gravado no storage.")

                        with st.popover("🗑️ Excluir Ofício"):
                            st.warning("Atenção: A exclusão removerá o registro e a cópia em PDF do backup.")
                            chk_conf = st.checkbox("Confirmar exclusão?", key=f"chk_del_of_{log_item.get('id')}_{idx_of}")
                            if st.button("🔥 Confirmar Exclusão", key=f"btn_del_of_{log_item.get('id')}_{idx_of}", type="primary", use_container_width=True):
                                if not chk_conf:
                                    st.error("Marque a caixa de confirmação.")
                                else:
                                    if path_st and path_st != "N/I":
                                        deletar_arquivo_storage_supabase(path_st)
                                    
                                    if supabase:
                                        supabase.table("tco_logs").delete().eq("id", log_item.get("id")).execute()
                                    st.success("Expediente removido do repositório!")
                                    st.rerun()
        else:
            st.info("Nenhum registro de ofício expedido localizado no repositório.")