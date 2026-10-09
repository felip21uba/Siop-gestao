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
from modules.tco.database import salvar_material_supabase, atualizar_material_supabase, registrar_log_supabase, carregar_logs_supabase
from modules.tco.estilo_tco import (
    injetar_estilo_passo3_tco,
    formatar_matricula_pm,
    modal_cadeia_custodia_timeline,
    modal_guia_termo_oficial
)
from utils.file_validator import validar_pdf_upload, validar_imagem_upload, sanitizar_nome_arquivo

# ==============================================================================
# 🔍 FUNÇÕES AUXILIARES DE BANCO DE DADOS DO TCO
# ==============================================================================

def verificar_existencia_reds_banco(num_reds: str):
    if not supabase or not num_reds:
        return False, None, None

    num_clean = str(num_reds).strip().upper()
    try:
        res = supabase.table("tco_registros").select("created_at, operador_cadastro").eq("num_reds", num_clean).execute()
        if res and res.data and len(res.data) > 0:
            reg = res.data[0]
            return True, reg.get("created_at", "Data N/I"), reg.get("operador_cadastro", "Operador N/I")
            
        res_m = supabase.table("tco_materiais").select("created_at, fiel_depositario_atual").eq("num_reds", num_clean).limit(1).execute()
        if res_m and res_m.data and len(res_m.data) > 0:
            reg_m = res_m.data[0]
            return True, reg_m.get("created_at", "Data N/I"), reg_m.get("fiel_depositario_atual", "Operador N/I")
    except Exception as e:
        print(f"Aviso ao verificar existência do REDS {num_clean}: {e}")

    return False, None, None


def modal_alerta_reds_duplicado(num_reds, dt_cad, op_cad):
    @st.dialog("⚠️ Atenção: REDS Já Registrado")
    def _dialog():
        st.warning(f"O REDS **{num_reds}** já foi importado anteriormente.")
        st.write(f"📅 **Data de Registro:** {dt_cad}")
        st.write(f"👮‍♂️ **Operador:** {op_cad}")
        st.info("Caso prossiga, as informações serão atualizadas na base de dados.")

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("🔄 Sobrescrever / Atualizar", type="primary", use_container_width=True):
                st.session_state["confirmou_duplicidade_reds"] = True
                st.rerun()
        with col_c2:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.pop("temp_reds_extraido", None)
                st.session_state["confirmou_duplicidade_reds"] = False
                st.rerun()

    _dialog()


def extrair_unidade_mae_creds(str_unidade):
    if not str_unidade or not isinstance(str_unidade, str):
        return None
    str_u = str_unidade.upper().strip()

    if "35" in str_u and ("CIA" in str_u or "COMPANHIA" in str_u):
        return "35ª CIA PM"
    elif "111" in str_u and ("CIA" in str_u or "COMPANHIA" in str_u):
        return "111ª CIA PM"
    elif "285" in str_u and ("CIA" in str_u or "TM" in str_u or "TÁTICO" in str_u):
        return "285ª CIA TM"
    elif "21" in str_u and ("BPM" in str_u or "EM" in str_u or "BATALHAO" in str_u):
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


def formatar_data_hora_exata(str_dh):
    if not str_dh or str_dh in ["N/I", "N/A", "None", "", "nan"]:
        return "Data N/I"
    try:
        return pd.to_datetime(str_dh).strftime("%d/%m/%Y às %H:%M")
    except Exception:
        return str(str_dh)[:16]


def obter_lista_creds_dinamica():
    unidades_set = set()
    all_m = carregar_militares_supabase() or []
    
    for m in all_m:
        for col in ["unidade", "nome_unidade", "lotacao", "secao"]:
            unid_bruta = str(m.get(col) or "").strip()
            unid_mae = extrair_unidade_mae_creds(unid_bruta)
            if unid_mae:
                unidades_set.add(unid_mae)

    unidades_base = {"35ª CIA PM", "111ª CIA PM", "285ª CIA TM", "21º BPM"}
    unidades_set.update(unidades_base)

    lista = [f"CREDS TCO - {u}" for u in sorted(list(unidades_set)) if "CENTRAL" not in u]
    if "CREDS TCO - CENTRAL DE CUSTÓDIA" not in lista:
        lista.append("CREDS TCO - CENTRAL DE CUSTÓDIA")
    
    return lista


def calcular_tempo_decorrido_detalhado(str_data_hora):
    if not str_data_hora or str_data_hora in ["N/A", "Data N/I", "N/I", "None", "nan"]:
        return "N/A", False, 0
    try:
        dt_evento = pd.to_datetime(str_data_hora)
        delta = datetime.datetime.now() - dt_evento.to_pydatetime().replace(tzinfo=None)
        dias = delta.days
        horas = delta.seconds // 3600
        minutos = (delta.seconds % 3600) // 60
        
        alerta_4dias = (dias >= 4)
        texto = f"{dias}d {horas}h" if dias > 0 else (f"{horas}h {minutos}m" if horas > 0 else f"{minutos} min")
        return texto, alerta_4dias, dias
    except Exception:
        return "N/A", False, 0


def obter_status_gargalo_e_tempo(bem, e_marrom=False):
    status_tr = bem.get("status_tramite", "Em Custódia")
    fase_dest = bem.get("fase_destinacao", "Com Fiel Depositário / Policial")
    dt_ref = bem.get("data_envio_tramite") or bem.get("data_posse_atual") or bem.get("data_ingestao")
    dest_pend = bem.get("destinatario_pendente")
    ultimo_op = bem.get("ultimo_gestor_movimentou") or bem.get("fiel_depositario_atual") or "N/I"
    
    texto_tempo, e_alerta_4dias, dias_num = calcular_tempo_decorrido_detalhado(dt_ref)
    
    def tag_destaque(txt):
        return f"<b style='color: #ffe0b2;'>{txt}</b>"

    if dest_pend and status_tr in ["Pendente de Aceite", "Pendente Aceite"]:
        ponto_cadeia = f"⏳ <b>Aguardando Aceite por:</b> {tag_destaque(dest_pend)} ({bem.get('unidade_destinatario_pendente', 'N/I')})"
    elif status_tr == "Transferido Definitivo":
        ponto_cadeia = f"🔒 <b>Transferência Definitiva:</b> Encaminhado por {tag_destaque(ultimo_op)} para {tag_destaque(fase_dest)}"
    elif "Perícia" in fase_dest:
        ponto_cadeia = f"🔬 <b>Em Perícia Técnica:</b> Encaminhado por {tag_destaque(ultimo_op)}"
    elif "PCMG" in fase_dest or "Delegacia" in fase_dest:
        ponto_cadeia = f"🏛️ <b>Encaminhado à Polícia Civil:</b> Encaminhado por {tag_destaque(ultimo_op)}"
    elif "JECRIM" in fase_dest or "Fórum" in fase_dest:
        ponto_cadeia = f"⚖️ <b>Entregue no JECRIM / Fórum:</b> Encaminhado por {tag_destaque(ultimo_op)}"
    elif "Destruição" in fase_dest or "Descarte" in fase_dest:
        ponto_cadeia = f"🔥 <b>Aguardando Destruição no Depósito:</b> Separado por {tag_destaque(ultimo_op)}"
    elif "DESTRUÍDO" in fase_dest or "ENCERRADO" in status_tr.upper():
        ponto_cadeia = f"🔒 <b>Material Destruído / Processo Encerrado por:</b> {tag_destaque(ultimo_op)}"
    else:
        ponto_cadeia = f"🎒 <b>Em Custódia de:</b> {tag_destaque(bem.get('fiel_depositario_atual', 'N/I'))} ({bem.get('unidade_posse_atual', 'N/I')})"
        
    return ponto_cadeia, texto_tempo, e_alerta_4dias, dias_num


def gerar_excel_panoramico_tco(lista_bens_filtrados):
    buffer = io.BytesIO()
    dados_excel = []
    
    for b in lista_bens_filtrados:
        _, _, dias_num = calcular_tempo_decorrido_detalhado(
            b.get("data_envio_tramite") or b.get("data_posse_atual") or b.get("data_ingestao")
        )
        dt_ing = b.get("data_ingestao") or b.get("data_posse_atual") or ""
        dt_ing_fmt = formatar_data_hora_exata(dt_ing)

        dados_excel.append({
            "Nº REDS": str(b.get("num_reds", "N/I")),
            "Descrição do Material": str(b.get("descricao", "N/I")),
            "Qtd": b.get("quantidade", 1.0),
            "Unidade Medida": str(b.get("unidade_medida", "UN")),
            "Nº Lacre / Invólucro": str(b.get("involucro_lacre", "N/I")),
            "Autor(es) Vinculado(s)": str(b.get("autores", "N/I")),
            "Custodiante Atual": str(b.get("fiel_depositario_atual", "N/I")),
            "Último Gestor / Operador": str(b.get("ultimo_gestor_movimentou", "N/I")),
            "Destinatário Pendente": str(b.get("destinatario_pendente", "NENHUM (CUSTÓDIA CONFIRMADA)")),
            "Unidade / Posse Atual": str(b.get("unidade_posse_atual", "N/A")),
            "Fase / Destinação Final": str(b.get("fase_destinacao", "N/I")),
            "Status do Trâmite": str(b.get("status_tramite", "N/I")),
            "Tempo Imóvel (Dias)": dias_num,
            "Data Importação REDS (DD/MM/AAAA)": dt_ing_fmt
        })

    df_exp = pd.DataFrame(dados_excel)
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_exp.to_excel(writer, index=False, sheet_name="Panorama_Custodia_TCO")
    buffer.seek(0)
    return buffer.getvalue()


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
# ABA 1: IMPORTAÇÃO E UPLOAD
# =============================================================================
def renderizar_aba_importacao(nome_militar_atual, unidade_militar_atual):
    injetar_estilo_passo3_tco()
    st.markdown("### 📄 Importação e Registro Individual de Ocorrência")
    st.markdown(f"👤 **Fiel Depositário Inicial:** `{nome_militar_atual}` ({unidade_militar_atual})")

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
                            
                            existe_reds, dt_cad, op_cad = verificar_existencia_reds_banco(dados_reds["num_reds"])
                            if existe_reds and not st.session_state.get("confirmou_duplicidade_reds", False):
                                modal_alerta_reds_duplicado(dados_reds["num_reds"], dt_cad, op_cad)
                            else:
                                st.success("Leitura do REDS concluída!")

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
            with c2:
                st.markdown(f"• **Natureza:** {d['natureza']}")
                st.markdown(f"• **Autor(es):** {', '.join(d['autores'])}")

        if d["materiais"]:
            df_mats = pd.DataFrame(d["materiais"])
            
            # Garante a existência de todas as colunas necessárias sem KeyError
            if "remover" not in df_mats.columns:
                df_mats.insert(0, "remover", False)
            if "item_num" not in df_mats.columns:
                df_mats["item_num"] = [str(i + 1) for i in range(len(df_mats))]
            if "descricao" not in df_mats.columns:
                df_mats["descricao"] = "MATERIAL DIVERSO"
            if "quantidade" not in df_mats.columns:
                df_mats["quantidade"] = 1.0
            if "unidade" not in df_mats.columns:
                df_mats["unidade"] = "UNIDADE"
            if "involucro" not in df_mats.columns:
                df_mats["involucro"] = "SEM LACRE"
            if "autor" not in df_mats.columns:
                df_mats["autor"] = "AUTOR NÃO INFORMADO"
            
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

            col_b1, col_b2 = st.columns(2)
            with col_b1:
                btn_confirmar = st.button("💾 Confirmar na Minha Custódia Pessoal", type="primary", use_container_width=True)
            with col_b2:
                btn_limpar = st.button("❌ Descartar REDS", use_container_width=True)

            if btn_limpar:
                st.session_state["temp_reds_extraido"] = None
                st.rerun()

            if btn_confirmar:
                itens_validos = df_editado_ing[df_editado_ing["remover"] == False]
                now_iso = datetime.datetime.now().isoformat()
                
                for idx_row, row in itens_validos.iterrows():
                    id_bem_unico = f"BEM-{d['num_reds']}-{row['item_num']}-{uuid.uuid4().hex[:4]}"
                    novo_bem = {
                        "id_bem": id_bem_unico,
                        "num_reds": d["num_reds"],
                        "autores": str(row["autor"]).strip(),
                        "descricao": str(row["descricao"]).strip(),
                        "quantidade": float(row["quantidade"]),
                        "unidade_medida": str(row["unidade"]).strip(),
                        "involucro_lacre": str(row["involucro"]).strip(),
                        "fase_destinacao": "Aguardando no CREDS-TC / Custódia",
                        "fiel_depositario_atual": nome_militar_atual,
                        "unidade_posse_atual": unidade_militar_atual,
                        "ultimo_gestor_movimentou": nome_militar_atual,
                        "data_posse_atual": now_iso,
                        "status_tramite": "Em Custódia",
                        "data_ingestao": now_iso
                    }
                    salvar_material_supabase(novo_bem)

                del st.session_state["temp_reds_extraido"]
                st.success("Materiais cadastrados com sucesso!")
                st.rerun()

renderizar_aba_ingestao = renderizar_aba_importacao


# =============================================================================
# ABA 3: PAINEL DO CREDS (CARDS IDÊNTICOS ÀS FOTOS COM TODAS AS FUNÇÕES)
# =============================================================================
def renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual):
    injetar_estilo_passo3_tco()
    st.markdown("#### 🏛️ Painel do Gestor CREDS-TCO & Rastreamento de Custódia")
    
    if not eh_gestor_creds:
        st.error("🔒 **Acesso Restrito:** Apenas Gestores do CREDS-TCO têm acesso às funções deste painel.")
        return

    st.caption(f"⚙ **Gestão Institucional Ativa:** Operando como **CREDS TCO - {unidade_militar_atual}** | Assinatura digital do Gestor: **{nome_militar_atual}**")

    if "itens_selecionados_creds_painel" not in st.session_state:
        st.session_state["itens_selecionados_creds_painel"] = {}

    if "filtro_card_ativo" not in st.session_state:
        st.session_state["filtro_card_ativo"] = "TODOS"

    if "material_selecionado_mov" not in st.session_state:
        st.session_state["material_selecionado_mov"] = None

    # =========================================================================
    # BARRA SUPERIOR: FILTRO DE UNIDADE, PERÍODO E BUSCA POR REDS / AUTOR
    # =========================================================================
    with st.container(border=True):
        st.markdown("##### 🔍 Filtros & Pesquisa Geral do Acervo")
        c_exp1, c_exp2, c_exp3 = st.columns([1.5, 1.5, 1])
        
        with c_exp1:
            lista_creds_opts = ["TODOS OS CREDS (ACERVO GERAL)"] + [u for u in obter_lista_creds_dinamica() if "✏️" not in u]
            creds_selecionado = st.selectbox("Selecione o CREDS / Unidade:", lista_creds_opts, key="sb_creds_filtro_main")

        with c_exp2:
            dt_hoje = datetime.date.today()
            dt_inicio_padrao = dt_hoje - datetime.timedelta(days=90)
            periodo_datas = st.date_input(
                "Filtrar por Período de Data:",
                value=(dt_inicio_padrao, dt_hoje),
                format="DD/MM/YYYY",
                key="range_datas_creds_painel"
            )

        with c_exp3:
            st.markdown("<br>", unsafe_allow_html=True)
            bens_filtrados_painel = all_bens_banco.copy() if all_bens_banco else []
            if bens_filtrados_painel:
                excel_bytes = gerar_excel_panoramico_tco(bens_filtrados_painel)
                st.download_button(
                    label=f"📥 Baixar Excel ({len(bens_filtrados_painel)})",
                    data=excel_bytes,
                    file_name=f"Relatorio_TCO_{creds_selecionado.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )

        busca_reds_ou_autor = st.text_input(
            "🔎 Pesquisar por Nº do REDS, Nome do Autor ou Lacre:",
            placeholder="Ex: 2026-000484968-001, CARLOS EDUARDO SILVA ou B981234112...",
            key="txt_busca_creds_reds_autor"
        ).strip().lower()

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

    if busca_reds_ou_autor:
        bens_filtrados_painel = [
            b for b in bens_filtrados_painel
            if busca_reds_ou_autor in str(b.get("num_reds", "")).lower()
            or busca_reds_ou_autor in str(b.get("autores", "")).lower()
            or busca_reds_ou_autor in str(b.get("involucro_lacre", "")).lower()
            or busca_reds_ou_autor in str(b.get("descricao", "")).lower()
        ]

    bens_custodia_ativa_creds = []
    bens_aguardando_destruicao = []
    bens_pendentes_aceite_creds = []
    bens_orgao_externo_tramite = []
    bens_destruidos_encerrados = []

    reds_custodia_policial = set()
    reds_pericia = set()
    reds_destruicao = set()
    reds_custodia_creds = set()
    reds_parados = set()
    reds_destruidos_encerrados = set()

    TERMOS_EXTERNOS = [
        "DELEGACIA", "POLÍCIA CIVIL", "PCMG", "JECRIM", "JUDICIÁRIO", 
        "PERÍCIA", "MINISTÉRIO PÚBLICO", "MPMG", "ÓRGÃO EXTERNO", "FÓRUM", "TRIBUNAL"
    ]

    for b in bens_filtrados_painel:
        ponto_cad, tempo_str, alerta_4d, dias_num = obter_status_gargalo_e_tempo(b, e_marrom=False)
        b_copy = dict(b)
        b_copy["_ponto_cadeia"] = ponto_cad
        b_copy["_tempo_str"] = tempo_str
        b_copy["_alerta_4dias"] = alerta_4d
        b_copy["_dias_num"] = dias_num

        num_r = str(b.get("num_reds", "")).strip()
        dest_p = str(b.get("destinatario_pendente") or "").strip().upper()
        fase_d = str(b.get("fase_destinacao") or "").upper()
        status_t = str(b.get("status_tramite") or "").strip()
        fiel_atual = str(b.get("fiel_depositario_atual") or "").upper()

        if alerta_4d:
            reds_parados.add(num_r)

        if "DESTRUÍDO" in fase_d or "ENCERRADO" in status_t.upper():
            reds_destruidos_encerrados.add(num_r)
            bens_destruidos_encerrados.append(b_copy)
        elif "DESTRUIÇÃO" in fase_d or "DESCARTE" in fase_d:
            reds_destruicao.add(num_r)
            bens_aguardando_destruicao.append(b_copy)
        elif "PERÍCIA" in fase_d or "PERÍCIA" in dest_p or status_t == "Transferido Definitivo" or any(term in dest_p or term in fase_d for term in TERMOS_EXTERNOS):
            if "PERÍCIA" in fase_d or "PERÍCIA" in dest_p:
                reds_pericia.add(num_r)
            bens_orgao_externo_tramite.append(b_copy)
        elif dest_p and ("CREDS" in dest_p or unidade_militar_atual in dest_p) and status_t in ["Pendente de Aceite", "Pendente Aceite"]:
            bens_pendentes_aceite_creds.append(b_copy)
        elif "CREDS" in fiel_atual or "CUSTÓDIA" in fiel_atual or unidade_militar_atual in fiel_atual or "AGUARDANDO NO CREDS" in fase_d:
            reds_custodia_creds.add(num_r)
            bens_custodia_ativa_creds.append(b_copy)
        else:
            reds_custodia_policial.add(num_r)

    # =========================================================================
    # MÉTRICAS COM ESTILO PADRÃO ESCALAS
    # =========================================================================
    kp1, kp2, kp3, kp4, kp5, kp6 = st.columns(6)
    with kp1:
        st.metric("🏛️ No CREDS-TC", len(reds_custodia_creds))
        if st.button("Filtrar CREDS", key="btn_f_creds", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "CREDS"
            st.rerun()

    with kp2:
        st.metric("🎒 Custódia Policial", len(reds_custodia_policial))
        if st.button("Filtrar Policial", key="btn_f_policial", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "POLICIAL"
            st.rerun()

    with kp3:
        st.metric("🔬 Em Perícia", len(reds_pericia))
        if st.button("Filtrar Perícia", key="btn_f_pericia", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "PERICIA"
            st.rerun()

    with kp4:
        st.metric("🔥 Aguard. Incineração", len(reds_destruicao))
        if st.button("Filtrar Incineração", key="btn_f_destruicao", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "DESTRUICAO"
            st.rerun()

    with kp5:
        st.metric("🚨 Parados > 4 Dias", len(reds_parados))
        if st.button("Filtrar Parados", key="btn_f_parados", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "PARADOS"
            st.rerun()

    with kp6:
        st.metric("🔒 Encerrados", len(reds_destruidos_encerrados))
        if st.button("Filtrar Arquivo", key="btn_f_arquivo", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "ARQUIVO"
            st.rerun()

    if st.session_state.get("filtro_card_ativo") != "TODOS":
        st.markdown("<br>", unsafe_allow_html=True)
        col_fl1, col_fl2 = st.columns([4, 1])
        with col_fl1:
            st.info(f"Filtro ativo por métrica: **{st.session_state['filtro_card_ativo']}**")
        with col_fl2:
            if st.button("Limpar Filtro", type="secondary", use_container_width=True):
                st.session_state["filtro_card_ativo"] = "TODOS"
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    filtro_card = st.session_state.get("filtro_card_ativo", "TODOS")

    todos_logs_banco = carregar_logs_supabase() or []
    usr_dados = st.session_state.get("usuario_dados", {})
    mat_op = str(usr_dados.get("num_policia") or usr_dados.get("usuario_login") or "1764921")

    # =========================================================================
    # RETÂNGULO 1: 🎒 ACERVO ATIVO (CARDS COM DADOS EXATOS DAS FOTOS)
    # =========================================================================
    if filtro_card in ["TODOS", "CREDS", "PARADOS"]:
        with st.container(border=True):
            bens_r1 = bens_custodia_ativa_creds.copy()
            if filtro_card == "PARADOS":
                bens_r1 = [b for b in bens_r1 if b.get("_alerta_4dias")]

            df_disp_reds = pd.DataFrame(bens_r1) if bens_r1 else pd.DataFrame()
            qtd_reds_disponiveis = df_disp_reds["num_reds"].nunique() if not df_disp_reds.empty else 0

            st.markdown(f"##### 🎒 1. Acervo Ativo no Depósito do CREDS ({qtd_reds_disponiveis} REDS)")
            st.caption("Materiais sob custódia oficial. Acesse a FAV ou gere a Guia Oficial de Depósito.")

            if bens_r1:
                grupos_creds_reds = df_disp_reds.groupby("num_reds", sort=False)
                idx_global_card = 0

                for num_reds_c, df_grupo_c in grupos_creds_reds:
                    with st.expander(f"📦 **CARD REDS: {num_reds_c}** ({len(df_grupo_c)} item/ns sob custódia oficial do CREDS)", expanded=False):
                        for _, bem in df_grupo_c.iterrows():
                            idx_global_card += 1
                            id_bem = str(bem.get("id_bem") or bem.get("id"))
                            dt_mov_exata = formatar_data_hora_exata(bem.get("data_envio_tramite") or bem.get("data_posse_atual") or bem.get("data_ingestao"))
                            desc_b = bem.get("descricao", "N/I")
                            qtd_b = bem.get("quantidade", 1)
                            unid_b = bem.get("unidade_medida", "UN")
                            lacre_b = bem.get("involucro_lacre", "SEM LACRE")
                            autor_b = bem.get("autores", "N/I")
                            custod_b = bem.get("fiel_depositario_atual", "CREDS TCO")
                            resp_b = bem.get("ultimo_gestor_movimentou") or f"{nome_militar_atual} - MAT. {formatar_matricula_pm(mat_op)}"

                            logs_item = [
                                l for l in todos_logs_banco
                                if str(l.get("num_reds", "")).strip() == num_reds_c
                                or id_bem in str(l.get("bem_id", ""))
                            ]
                            qtd_etapas = len(logs_item) if logs_item else 1

                            classe_card = "card-par" if (idx_global_card % 2 == 0) else "card-impar"

                            col_chk_b, col_card_b = st.columns([0.5, 9.5])
                            with col_chk_b:
                                is_sel_creds = st.checkbox("Selecionar", key=f"chk_creds_card_{id_bem}_{idx_global_card}", label_visibility="collapsed")

                            with col_card_b:
                                # RENDERIZAÇÃO IDÊNTICA ÀS FOTOS
                                html_item = f"""
                                <div class="card-material-item {classe_card}">
                                    📄 REDS: <b>{num_reds_c}</b> | Material: <b>{desc_b}</b> (Qtd: {qtd_b} {unid_b})<br/>
                                    🏷️ Lacre: <b style="font-family: monospace;">{lacre_b}</b> | Autor: <b>{autor_b}</b><br/>
                                    📍 Custodiante: <b>{custod_b}</b><br/>
                                    ⏱️ Data/Hora do Trâmite: <span class="caixa-data-destaque">{dt_mov_exata}</span>
                                    <div class="linha-auditoria-div">
                                        <div>🛡️ <b>Responsável:</b> {resp_b}</div>
                                        <div>🗺️ <b>Etapas na Cadeia:</b> {qtd_etapas} evento(s)</div>
                                    </div>
                                </div>
                                """
                                st.markdown(html_item, unsafe_allow_html=True)

                                # Barra com os 3 botões funcionais
                                c_sp, c_btn_cad, c_btn_guia, c_btn_mov = st.columns([4.6, 1.8, 1.8, 1.8])
                                with c_btn_cad:
                                    if st.button("🔗 FAV (Cadeia)", key=f"btn_cad_r1_{id_bem}_{idx_global_card}", use_container_width=True):
                                        modal_cadeia_custodia_timeline(bem.to_dict())
                                with c_btn_guia:
                                    if st.button("🖨️ Guia / Termo", key=f"btn_guia_r1_{id_bem}_{idx_global_card}", use_container_width=True):
                                        modal_guia_termo_oficial(dict(bem), nome_militar_atual, mat_op, unidade_militar_atual)
                                with c_btn_mov:
                                    if st.button("🛒 Movimentar", key=f"btn_mov_r1_{id_bem}_{idx_global_card}", type="primary", use_container_width=True):
                                        st.session_state["material_selecionado_mov"] = bem.to_dict()
                                        st.toast(f"Material '{desc_b}' selecionado para trâmite!", icon="📦")

                            if is_sel_creds:
                                st.session_state["itens_selecionados_creds_painel"][id_bem] = bem.to_dict()
                            else:
                                st.session_state["itens_selecionados_creds_painel"].pop(id_bem, None)
            else:
                st.info("ℹ️ Nenhum material ativo no acervo oficial do CREDS no momento.")

            selecionados_creds_map = st.session_state["itens_selecionados_creds_painel"]
            qtd_creds_sel = len(selecionados_creds_map)

            if qtd_creds_sel > 0:
                st.markdown("---")
                st.markdown(f"### 🎯 Atualizar Status / Destinação em Lote ({qtd_creds_sel} itens)")
                
                tipo_dest_creds = st.radio(
                    "Selecione a Operação do Gestor:",
                    ["🔥 Autorizar Destruição / Incineração no Depósito", "🏛️ Enviar para Órgão Externo (PCMG / Perícia / JECRIM / Outros)", "👤 Transferir para Policial / Fiel Depositário", "🏢 Aguardando no CREDS-TC / Custódia"],
                    horizontal=True,
                    key="radio_tipo_destinatario_creds_v4"
                )

                eh_policial_dest = ("Policial" in tipo_dest_creds)

                with st.form("form_destinar_creds_v4", clear_on_submit=False):
                    col_f1, col_f2 = st.columns(2)

                    with col_f1:
                        if "Destruição" in tipo_dest_creds:
                            st.warning("🔥 Os materiais selecionados serão colocados em **Aguardando Incineração / Descarte Físico**.")
                            destinatario_final = "DEPÓSITO DE CUSTÓDIA / AGUARDANDO DESTRUIÇÃO"
                            eh_definitiva_ext = False
                        elif "Órgão Externo" in tipo_dest_creds:
                            destinatario_final = st.selectbox(
                                "Selecione o Órgão Destinatário:",
                                ["PERÍCIA TÉCNICA / PERÍCIA OFICIAL", "DELEGACIA DE POLÍCIA CIVIL (PCMG)", "PODER JUDICIÁRIO / TRIBUNAL DE JUSTIÇA (JECRIM)", "MINISTÉRIO PÚBLICO (MPMG)", "OUTROS ÓRGÃOS"],
                                key="sb_orgao_ext_v4"
                            )
                            tipo_ret = st.radio("Natureza da Transferência:", ["🔄 Com Retorno (Em Tramitação)", "🔒 Definitiva (Procedimento Encerrado/Sem Retorno)"], key="radio_def_v4")
                            eh_definitiva_ext = ("Definitiva" in tipo_ret)
                        elif "Aguardando no CREDS" in tipo_dest_creds:
                            destinatario_final = f"CREDS TCO - {unidade_militar_atual}"
                            eh_definitiva_ext = False
                        else:
                            lista_m = carregar_militares_supabase() or []
                            opcoes_mil = [f"{m.get('posto_grad','PM')} {m.get('nome_completo','MILITAR')} ({m.get('num_policia','')})" for m in lista_m]
                            destinatario_final = st.selectbox("Selecione o Policial Destinatário:", opcoes_mil, key="sb_mil_v4")
                            eh_definitiva_ext = False

                    with col_f2:
                        if eh_policial_dest:
                            fase_final = st.selectbox(
                                "Atualizar Fase de Destinação:",
                                options=["Com Fiel Depositário / Policial"],
                                index=0,
                                disabled=True,
                                key="sb_fase_orgao_v4_disabled"
                            )
                        elif "Destruição" in tipo_dest_creds:
                            fase_final = "Aguardando Destruição / Descarte Físico"
                            st.selectbox(
                                "Atualizar Fase de Destinação:",
                                options=["Aguardando Destruição / Descarte Físico"],
                                index=0,
                                disabled=True,
                                key="sb_fase_destruicao_disabled"
                            )
                        elif "Aguardando no CREDS" in tipo_dest_creds:
                            fase_final = "Aguardando no CREDS-TC / Custódia"
                            st.selectbox(
                                "Atualizar Fase de Destinação:",
                                options=["Aguardando no CREDS-TC / Custódia"],
                                index=0,
                                disabled=True,
                                key="sb_fase_creds_ret_disabled"
                            )
                        else:
                            fase_final = st.selectbox(
                                "Atualizar Fase de Destinação Final (Acesso Gestor CREDS):",
                                options=["Encaminhado para Perícia Técnica", "Encaminhado à Polícia Civil (PCMG)", "Entregue ao Poder Judiciário / Fórum", "Devolvido ao Proprietário"],
                                key="sb_fase_orgao_v4_enabled"
                            )

                    obs_creds = st.text_input("Nome Completo e Matrícula de quem recebeu (OBRIGATÓRIO):", placeholder="nome e matricula", key="txt_obs_desp_v4").strip()
                    btn_confirmar = st.form_submit_button("🚀 Confirmar Movimentação do CREDS", type="primary", use_container_width=True)

                    if btn_confirmar:
                        if not obs_creds:
                            st.error("⚠️ O preenchimento do Nome Completo e Matrícula de quem recebeu é OBRIGATÓRIO.")
                        else:
                            agora_iso = datetime.datetime.now().isoformat()
                            sucessos = 0

                            for id_bem_c, dados_c in selecionados_creds_map.items():
                                status_final = "Transferido Definitivo" if eh_definitiva_ext else ("Pendente de Aceite" if eh_policial_dest else "Em Custódia")
                                
                                payload = {
                                    "destinatario_pendente": destinatario_final if eh_policial_dest else None,
                                    "unidade_destinatario_pendente": unidade_militar_atual if eh_policial_dest else destinatario_final,
                                    "data_envio_tramite": agora_iso,
                                    "fase_destinacao": fase_final,
                                    "status_tramite": status_final,
                                    "ultimo_gestor_movimentou": nome_militar_atual
                                }

                                if atualizar_material_supabase(id_bem_c, payload):
                                    sucessos += 1
                                    registrar_log_supabase({
                                        "data_hora": agora_iso,
                                        "num_reds": dados_c.get("num_reds", "N/I"),
                                        "bem_id": f"{dados_c.get('descricao')} (Lacre: {dados_c.get('involucro_lacre')})",
                                        "web_origem": "SIOP_TCO",
                                        "acao": "MOVIMENTACAO_GESTOR_CREDS",
                                        "origem": f"CREDS TCO - {unidade_militar_atual}",
                                        "unidade_origem": unidade_militar_atual,
                                        "destino": destinatario_final,
                                        "unidade_destino": unidade_militar_atual,
                                        "detalhe": f"Despachado por: {nome_militar_atual} | Fase: {fase_final} | Recebido por: {obs_creds}"
                                    })

                            if sucessos > 0:
                                st.success(f"🎉 {sucessos} material(is) movimentado(s) pelo CREDS com sucesso!")
                                st.session_state["itens_selecionados_creds_painel"] = {}
                                st.cache_data.clear()
                                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # FORMULÁRIO RÁPIDO AO CLICAR EM "🛒 MOVIMENTAR" NO CARD INDIVIDUAL
    # =========================================================================
    mat_mov_indiv = st.session_state.get("material_selecionado_mov")
    if mat_mov_indiv:
        st.markdown("---")
        st.markdown(f"### 🎯 Movimentar Material: `{mat_mov_indiv.get('descricao')}`")
        st.caption(f"REDS: `{mat_mov_indiv.get('num_reds')}` | Lacre: `{mat_mov_indiv.get('involucro_lacre')}`")

        with st.form("form_tramitar_indiv_painel_creds", clear_on_submit=False):
            col_t1, col_t2 = st.columns(2)
            
            with col_t1:
                destino_final_indiv = st.selectbox(
                    "Informar onde o material está / para onde vai:",
                    [
                        "Aguardando no CREDS-TC / Custódia",
                        "PERÍCIA TÉCNICA / PERÍCIA OFICIAL",
                        "DELEGACIA DE POLÍCIA CIVIL (PCMG)",
                        "PODER JUDICIÁRIO / TRIBUNAL DE JUSTIÇA (JECRIM)",
                        "DEPÓSITO DE CUSTÓDIA / AGUARDANDO DESTRUIÇÃO",
                        "Com Fiel Depositário / Policial Militar",
                        "Devolvido ao Proprietário"
                    ]
                )

            with col_t2:
                recebedor_indiv_txt = st.text_input(
                    "Nome Completo e Matrícula de quem recebeu (OBRIGATÓRIO):",
                    placeholder="Ex: INVESTIGADOR PCMG MAT. 123456"
                ).strip()

            c_sub1, c_sub2 = st.columns(2)
            with c_sub1:
                btn_conf_indiv = st.form_submit_button("🚀 Confirmar Movimentação do CREDS", type="primary", use_container_width=True)
            with c_sub2:
                btn_canc_indiv = st.form_submit_button("❌ Cancelar", use_container_width=True)

            if btn_canc_indiv:
                st.session_state["material_selecionado_mov"] = None
                st.rerun()

            if btn_conf_indiv:
                if not recebedor_indiv_txt:
                    st.error("Informe o Nome Completo e Matrícula de quem recebeu.")
                else:
                    agora_iso = datetime.datetime.now().isoformat()
                    eh_definitivo_indiv = any(t in destino_final_indiv for t in ["PERÍCIA", "PCMG", "JECRIM", "DESTRUIÇÃO", "Devolvido"])
                    
                    status_novo_indiv = "Transferido Definitivo" if eh_definitivo_indiv else "Em Custódia"
                    dest_pend_indiv = destino_final_indiv if eh_definitivo_indiv else None

                    payload_upd_indiv = {
                        "destinatario_pendente": dest_pend_indiv,
                        "unidade_destinatario_pendente": destino_final_indiv,
                        "fase_destinacao": destino_final_indiv,
                        "fiel_depositario_atual": destino_final_indiv if eh_definitivo_indiv else f"CREDS TCO - {unidade_militar_atual}",
                        "status_tramite": status_novo_indiv,
                        "ultimo_gestor_movimentou": nome_militar_atual,
                        "data_posse_atual": agora_iso,
                        "data_envio_tramite": agora_iso
                    }

                    id_bem_indiv = str(mat_mov_indiv.get("id_bem") or mat_mov_indiv.get("id"))
                    
                    if atualizar_material_supabase(id_bem_indiv, payload_upd_indiv):
                        registrar_log_supabase({
                            "data_hora": agora_iso,
                            "num_reds": mat_mov_indiv.get("num_reds", "N/I"),
                            "bem_id": f"{mat_mov_indiv.get('descricao')} (Lacre: {mat_mov_indiv.get('involucro_lacre')})",
                            "acao": "MOVIMENTACAO_GESTOR_CREDS",
                            "origem": f"CREDS TCO - {unidade_militar_atual}",
                            "unidade_origem": unidade_militar_atual,
                            "destino": destino_final_indiv,
                            "unidade_destino": destino_final_indiv,
                            "detalhe": f"Destino atualizado para '{destino_final_indiv}'. Recebido por: {recebedor_indiv_txt} | Gestor: {nome_militar_atual}"
                        })
                        st.session_state["material_selecionado_mov"] = None
                        st.success("✅ Movimentação confirmada e registrada com sucesso!")
                        st.cache_data.clear()
                        st.rerun()

    # =========================================================================
    # RETÂNGULO 2: 🔥 MATERIAIS AGUARDANDO DESTRUÍÇÃO / INCINERAÇÃO
    # =========================================================================
    if filtro_card in ["TODOS", "DESTRUICAO"]:
        with st.container(border=True):
            df_dest_reds = pd.DataFrame(bens_aguardando_destruicao) if bens_aguardando_destruicao else pd.DataFrame()
            qtd_reds_dest = df_dest_reds["num_reds"].nunique() if not df_dest_reds.empty else 0

            st.markdown(f"##### 🔥 2. Materiais Autorizados Aguardando Incineração ({qtd_reds_dest} REDS)")
            st.caption("Materiais autorizados para destruição física. Para dar a baixa e encerramento definitivo, informe o BOS/Auto de Incineração.")

            if bens_aguardando_destruicao:
                for num_reds_d, df_grupo_d in df_dest_reds.groupby("num_reds", sort=False):
                    with st.expander(f"🔥 **CARD REDS: {num_reds_d}** ({len(df_grupo_d)} item/ns autorizados para destruição)", expanded=True):
                        for idx_d, item_d in df_grupo_d.iterrows():
                            id_bem_d = str(item_d.get("id_bem") or item_d.get("id"))
                            desc_d = item_d.get("descricao", "N/I")
                            qtd_d_val = item_d.get("quantidade", 1)
                            lacre_d = item_d.get("involucro_lacre", "N/I")
                            gestor_sep = item_d.get("ultimo_gestor_movimentou", "Gestor CREDS")
                            dt_d_exata = formatar_data_hora_exata(item_d.get("data_envio_tramite") or item_d.get("data_posse_atual"))

                            col_d1, col_d2 = st.columns([6, 4])
                            with col_d1:
                                html_fire = f"""
                                <div class="card-material-item card-par">
                                    🔥 <b>Material Autorizado para Incineração:</b> {desc_d} (Qtd: {qtd_d_val})<br/>
                                    🏷️ <b>Lacre:</b> {lacre_d} | 👤 <b>Autorizado por:</b> {gestor_sep}<br/>
                                    ⏱️ <b>Data/Hora:</b> <span class="caixa-data-destaque">{dt_d_exata}</span>
                                </div>
                                """
                                st.markdown(html_fire, unsafe_allow_html=True)

                            with col_d2:
                                with st.popover("🔥 Confirmar Baixa Definitiva", use_container_width=True):
                                    bos_ordem = st.text_input("Nº do BOS / Auto de Incineração (OBRIGATÓRIO):", placeholder="Ex: BOS 2026-000123", key=f"txt_bos_{id_bem_d}").strip()
                                    if st.button("🔒 Confirmar Destruído / Encerrado", key=f"btn_baixa_dest_{id_bem_d}_{idx_d}", type="primary", use_container_width=True):
                                        if not bos_ordem:
                                            st.error("Informe o Nº do BOS ou Auto de Incineração.")
                                        else:
                                            payload_baixa = {
                                                "destinatario_pendente": None,
                                                "fase_destinacao": "DESTRUÍDO / ENCERRADO (Baixa Definitiva por Incineração)",
                                                "status_tramite": "Destruído / Encerrado",
                                                "ultimo_gestor_movimentou": nome_militar_atual
                                            }
                                            if atualizar_material_supabase(id_bem_d, payload_baixa):
                                                registrar_log_supabase({
                                                    "data_hora": datetime.datetime.now().isoformat(),
                                                    "num_reds": num_reds_d,
                                                    "bem_id": f"{desc_d} (Lacre: {lacre_d})",
                                                    "web_origem": "SIOP_TCO",
                                                    "acao": "BAIXA_DESTRUICAO_DEFINITIVA",
                                                    "origem": f"CREDS TCO - {unidade_militar_atual}",
                                                    "unidade_origem": unidade_militar_atual,
                                                    "destino": "DESTRUIÇÃO / INCINERAÇÃO",
                                                    "unidade_destino": unidade_militar_atual,
                                                    "detalhe": f"Incineração confirmada por {nome_militar_atual}. Auto/BOS: {bos_ordem}"
                                                })
                                                st.success("✅ Material destruído definitivamente!")
                                                st.cache_data.clear()
                                                st.rerun()

                                if st.button("🔄 Cancelar Autorização", key=f"btn_canc_dest_{id_bem_d}_{idx_d}", use_container_width=True):
                                    payload_canc_d = {
                                        "fase_destinacao": "Aguardando no CREDS-TC / Custódia",
                                        "status_tramite": "Em Custódia",
                                        "ultimo_gestor_movimentou": nome_militar_atual
                                    }
                                    if atualizar_material_supabase(id_bem_d, payload_canc_d):
                                        st.warning("Material retornado para o acervo ativo do CREDS.")
                                        st.cache_data.clear()
                                        st.rerun()
            else:
                st.info("ℹ️ Nenhum material aguardando destruição/incineração no momento.")

    st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # RETÂNGULO 3: ⏳ MATERIAIS PENDENTES DE ACEITE PELO CREDS
    # =========================================================================
    if filtro_card in ["TODOS", "CREDS"]:
        with st.container(border=True):
            df_pend_creds = pd.DataFrame(bens_pendentes_aceite_creds) if bens_pendentes_aceite_creds else pd.DataFrame()
            qtd_reds_pend = df_pend_creds["num_reds"].nunique() if not df_pend_creds.empty else 0

            st.markdown(f"##### ⏳ 3. Materiais Pendentes de Aceite pelo CREDS ({qtd_reds_pend} REDS)")
            st.caption("Materiais encaminhados por policiais aguardando conferência e aceite do CREDS.")

            if bens_pendentes_aceite_creds:
                for num_reds_p, df_grupo_p in df_pend_creds.groupby("num_reds", sort=False):
                    with st.expander(f"📥 **REDS: {num_reds_p}** ({len(df_grupo_p)} item/ns pendentes)", expanded=True):
                        for idx_p, item_p in df_grupo_p.iterrows():
                            id_bem_p = str(item_p.get("id_bem") or item_p.get("id"))
                            desc_p = item_p.get("descricao", "N/I")
                            qtd_p_val = item_p.get("quantidade", 1)
                            lacre_p = item_p.get("involucro_lacre", "N/I")
                            remetente_p = item_p.get("remetente_ultimo") or item_p.get("fiel_depositario_atual") or "Policial Remetente"
                            dt_p_exata = formatar_data_hora_exata(item_p.get("data_envio_tramite") or item_p.get("data_posse_atual"))

                            col_pa1, col_pa2 = st.columns([6, 4])
                            with col_pa1:
                                st.markdown(
                                    f"📦 **Material:** {desc_p} (Qtd: {qtd_p_val}) | **Lacre:** `{lacre_p}`  \n"
                                    f"👤 **Enviado por:** `{remetente_p}` (`{item_p.get('unidade_remetente', 'N/I')}`)  \n"
                                    f"⏱️ **Data/Hora do Envio:** `{dt_p_exata}`"
                                )

                            with col_pa2:
                                col_bt_a, col_bt_r = st.columns(2)
                                with col_bt_a:
                                    if st.button("✅ Aceitar Custódia", key=f"btn_aceitar_item_indiv_{id_bem_p}_{idx_p}", type="primary", use_container_width=True):
                                        payload_aceite = {
                                            "destinatario_pendente": None,
                                            "unidade_destinatario_pendente": None,
                                            "fiel_depositario_atual": f"CREDS TCO - {unidade_militar_atual}",
                                            "unidade_posse_atual": unidade_militar_atual,
                                            "status_tramite": "Em Custódia",
                                            "fase_destinacao": "Aguardando no CREDS-TC / Custódia",
                                            "ultimo_gestor_movimentou": nome_militar_atual,
                                            "data_posse_atual": datetime.datetime.now().isoformat()
                                        }
                                        if atualizar_material_supabase(id_bem_p, payload_aceite):
                                            registrar_log_supabase({
                                                "data_hora": datetime.datetime.now().isoformat(),
                                                "num_reds": num_reds_p,
                                                "bem_id": f"{desc_p} (Lacre: {lacre_p})",
                                                "web_origem": "SIOP_TCO",
                                                "acao": "ACEITE_CUSTODIA_CREDS",
                                                "origem": remetente_p,
                                                "unidade_origem": item_p.get("unidade_remetente", "N/I"),
                                                "destino": f"CREDS TCO - {unidade_militar_atual}",
                                                "unidade_destino": unidade_militar_atual,
                                                "detalhe": f"Aceite de custódia confirmado pelo operador {nome_militar_atual}."
                                            })
                                            st.success("✅ Aceite de custódia registrado com sucesso!")
                                            st.cache_data.clear()
                                            st.rerun()

                                with col_bt_r:
                                    with st.popover("❌ Recusar", use_container_width=True):
                                        motivo_recusa = st.text_input("Motivo da Recusa:", placeholder="Ex: Lacre violado", key=f"txt_motivo_rec_{id_bem_p}").strip()
                                        if st.button("Confirmar Recusa", key=f"btn_confirm_recusa_{id_bem_p}_{idx_p}", type="primary", use_container_width=True):
                                            if not motivo_recusa:
                                                st.error("Informe o motivo.")
                                            else:
                                                payload_recusa = {
                                                    "destinatario_pendente": None,
                                                    "unidade_destinatario_pendente": None,
                                                    "status_tramite": "Em Custódia",
                                                    "ultimo_gestor_movimentou": nome_militar_atual
                                                }
                                                if atualizar_material_supabase(id_bem_p, payload_recusa):
                                                    st.warning("Material recusado e retornado ao remetente.")
                                                    st.cache_data.clear()
                                                    st.rerun()
            else:
                st.info("ℹ️ Nenhum material pendente de aceite pelo CREDS no momento.")

    st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # RETÂNGULO 4: 🏛️ MATERIAIS EM ÓRGÃOS EXTERNOS / ARQUIVO FINAL
    # =========================================================================
    if filtro_card in ["TODOS", "PERICIA", "PARADOS", "ARQUIVO"]:
        with st.container(border=True):
            bens_r4 = bens_orgao_externo_tramite.copy()
            if filtro_card == "ARQUIVO":
                bens_r4 = bens_destruidos_encerrados.copy()

            df_ext_reds = pd.DataFrame(bens_r4) if bens_r4 else pd.DataFrame()
            qtd_reds_ext = df_ext_reds["num_reds"].nunique() if not df_ext_reds.empty else 0

            st.markdown(f"##### 🏛️ 4. Materiais em Órgãos Externos / Arquivo Definitivo ({qtd_reds_ext} REDS)")
            st.caption("Acompanhamento de materiais remetidos para PCMG, Perícia, JECRIM ou arquivados definitivamente.")

            if bens_r4:
                for num_reds_ext, df_grupo_ext in df_ext_reds.groupby("num_reds", sort=False):
                    with st.expander(f"🏛️ **CARD REDS: {num_reds_ext}** ({len(df_grupo_ext)} item/ns)", expanded=False):
                        for idx_e, item_e in df_grupo_ext.iterrows():
                            id_bem_e = str(item_e.get("id_bem") or item_e.get("id"))
                            desc_e = item_e.get("descricao", "N/I")
                            qtd_e_val = item_e.get("quantidade", 1)
                            dest_e = item_e.get("destinatario_pendente") or item_e.get("fase_destinacao") or "Órgão Externo"
                            lacre_e = item_e.get("involucro_lacre", "N/I")
                            remetente_orig = item_e.get("ultimo_gestor_movimentou") or "Gestor CREDS"
                            status_tr_e = str(item_e.get("status_tramite") or "")
                            dt_ext_exata = formatar_data_hora_exata(item_e.get("data_envio_tramite") or item_e.get("data_posse_atual"))

                            e_destruido = ("Destruído" in status_tr_e or "DESTRUÍDO" in str(item_e.get("fase_destinacao","")))
                            e_confirmado_orgao = (status_tr_e == "Transferido Definitivo")

                            if e_destruido:
                                tag_situacao = "<strong style='color: #ef4444;'>🔒 MATERIAL DESTRUÍDO / ENCERRADO</strong>"
                            elif e_confirmado_orgao:
                                tag_situacao = "<strong style='color: #22c55e;'>✅ RECEBIMENTO CONFIRMADO PELO ÓRGÃO EXTERNO</strong>"
                            else:
                                tag_situacao = "<strong style='color: #38bdf8;'>🔄 EM TRÂMITE / AGUARDANDO DEVOLUÇÃO OU OFÍCIO</strong>"

                            col_e1, col_e2 = st.columns([6, 4])
                            with col_e1:
                                html_ext = f"""
                                <div class="card-material-item card-par">
                                    📦 <b>Material:</b> {desc_e} (Qtd: {qtd_e_val}) | 🏷️ <b>Lacre:</b> {lacre_e}<br/>
                                    📍 <b>Destino / Fase:</b> {dest_e}<br/>
                                    📊 Situação: {tag_situacao}<br/>
                                    👤 <b>Movimentado por:</b> {remetente_orig}<br/>
                                    ⏱️ <b>Data/Hora da Transferência:</b> <span class="tag-data-destaque">{dt_ext_exata}</span>
                                </div>
                                """
                                st.markdown(html_ext, unsafe_allow_html=True)

                                c_sp_e, c_cad_e, c_guia_e = st.columns([6, 2, 2])
                                with c_cad_e:
                                    if st.button("🔗 FAV", key=f"btn_cad_ext_{id_bem_e}_{idx_e}", use_container_width=True):
                                        modal_cadeia_custodia_timeline(item_e.to_dict())
                                with c_guia_e:
                                    if st.button("🖨️ Guia", key=f"btn_guia_ext_{id_bem_e}_{idx_e}", use_container_width=True):
                                        modal_guia_termo_oficial(item_e.to_dict(), nome_militar_atual, mat_op, unidade_militar_atual)

                            with col_e2:
                                if not e_destruido and not e_confirmado_orgao:
                                    if st.button("📥 Confirmar Devolução ao CREDS", key=f"btn_devolucao_creds_{id_bem_e}_{idx_e}", type="primary", use_container_width=True):
                                        agora_iso_r = datetime.datetime.now().isoformat()
                                        payload_ret = {
                                            "destinatario_pendente": None,
                                            "unidade_destinatario_pendente": None,
                                            "fiel_depositario_atual": f"CREDS TCO - {unidade_militar_atual}",
                                            "unidade_posse_atual": unidade_militar_atual,
                                            "status_tramite": "Em Custódia",
                                            "fase_destinacao": "Aguardando no CREDS-TC / Custódia",
                                            "ultimo_gestor_movimentou": nome_militar_atual,
                                            "data_posse_atual": agora_iso_r
                                        }
                                        if atualizar_material_supabase(id_bem_e, payload_ret):
                                            registrar_log_supabase({
                                                "data_hora": agora_iso_r,
                                                "num_reds": item_e.get("num_reds", "N/I"),
                                                "bem_id": f"{desc_e} (Lacre: {lacre_e})",
                                                "web_origem": "SIOP_TCO",
                                                "acao": "RETORNO_ORGAO_EXTERNO_PARA_CREDS",
                                                "origem": dest_e,
                                                "unidade_origem": dest_e,
                                                "destino": f"CREDS TCO - {unidade_militar_atual}",
                                                "unidade_destino": unidade_militar_atual,
                                                "detalhe": f"Devolução confirmada por {nome_militar_atual}. Material reincorporado ao acervo."
                                            })
                                            st.success("✅ Material devolvido ao Acervo do CREDS!")
                                            st.cache_data.clear()
                                            st.rerun()

                                    with st.popover("📄 Encerrar Procedimento / Definitivo", use_container_width=True):
                                        num_oficio_rec = st.text_input("Nº do Ofício / Protocolo / Laudo (OBRIGATÓRIO):", placeholder="Ex: Ofício 45/2026-PCMG", key=f"txt_ofic_{id_bem_e}").strip()
                                        foto_recibo = st.file_uploader("Foto ou PDF do Recibo/Laudo (OPCIONAL):", type=["jpg", "jpeg", "png", "pdf"], key=f"upl_rec_{id_bem_e}")
                                        
                                        if st.button("🔒 Confirmar Encerramento Definitivo", key=f"btn_conf_ext_manual_{id_bem_e}_{idx_e}", type="primary", use_container_width=True):
                                            if not num_oficio_rec:
                                                st.error("⚠️ O preenchimento do Nº do Ofício / Protocolo é OBRIGATÓRIO.")
                                            else:
                                                now_iso_c = datetime.datetime.now().isoformat()
                                                midia_recibo_obj = None

                                                if foto_recibo:
                                                    f_bytes = foto_recibo.getvalue()
                                                    nome_seguro = sanitizar_nome_arquivo(foto_recibo.name)
                                                    midia_recibo_obj = upload_midia_supabase(
                                                        file_bytes=f_bytes,
                                                        file_name=nome_seguro,
                                                        file_type=foto_recibo.type,
                                                        num_reds=item_e.get("num_reds", "N/I"),
                                                        id_bem=id_bem_e
                                                    )

                                                payload_conf_ext = {
                                                    "destinatario_pendente": None,
                                                    "fiel_depositario_atual": dest_e,
                                                    "status_tramite": "Transferido Definitivo",
                                                    "fase_destinacao": f"Entregue ao {dest_e} (Ofício: {num_oficio_rec})",
                                                    "ultimo_gestor_movimentou": nome_militar_atual
                                                }
                                                
                                                if atualizar_material_supabase(id_bem_e, payload_conf_ext):
                                                    detalhe_audit = f"Entrega definitiva confirmada por {nome_militar_atual}. Ofício/Protocolo: {num_oficio_rec}"
                                                    if midia_recibo_obj:
                                                        detalhe_audit += " | Recibo/Laudo digitalizado anexado"

                                                    registrar_log_supabase({
                                                        "data_hora": now_iso_c,
                                                        "num_reds": item_e.get("num_reds", "N/I"),
                                                        "bem_id": f"{desc_e} (Lacre: {lacre_e})",
                                                        "web_origem": "SIOP_TCO",
                                                        "acao": "CONFIRMACAO_ENTREGA_ORGAO_EXTERNO",
                                                        "origem": nome_militar_atual,
                                                        "unidade_origem": unidade_militar_atual,
                                                        "destino": dest_e,
                                                        "unidade_destino": dest_e,
                                                        "detalhe": detalhe_audit
                                                    })
                                                    st.success("✅ Entrega definitiva e encerramento registrados com sucesso!")
                                                    st.cache_data.clear()
                                                    st.rerun()

                                    if st.button("❌ Cancelar Envio (72h)", key=f"btn_canc_ext_72h_{id_bem_e}_{idx_e}", use_container_width=True):
                                        payload_canc_ext = {
                                            "destinatario_pendente": None,
                                            "status_tramite": "Em Custódia",
                                            "fase_destinacao": "Aguardando no CREDS-TC / Custódia",
                                            "fiel_depositario_atual": f"CREDS TCO - {unidade_militar_atual}",
                                            "ultimo_gestor_movimentou": nome_militar_atual
                                        }
                                        if atualizar_material_supabase(id_bem_e, payload_canc_ext):
                                            st.warning("Envio cancelado! Material retornado para o acervo ativo do CREDS.")
                                            st.cache_data.clear()
                                            st.rerun()
            else:
                st.info("ℹ️ Nenhum material nesta categoria no momento.")


# =============================================================================
# ABA 4: TRILHA DE AUDITORIA
# =============================================================================
def renderizar_aba_logs(all_logs_banco):
    st.markdown("### 📜 Trilha de Auditoria Imutável da Custódia (Supabase)")
    
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
                f5_periodo = st.date_input("Período (DD/MM/AAAA):", value=(dt_30d, dt_hoje), format="DD/MM/YYYY", key="f5_periodo_logs")
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
        
        st.dataframe(
            df_l[cols_reais],
            column_config={
                "data_hora": "Data/Hora",
                "num_reds": "Nº REDS",
                "bem_id": "Material / Identificador",
                "acao": "Ação Realizada",
                "origem": "Remetente / Origem",
                "unidade_origem": "Unid. Origem",
                "destino": "Destinatário",
                "unidade_destino": "Unid. Destino",
                "detalhe": "Detalhamento Auditoria"
            },
            use_container_width=True, 
            hide_index=True
        )

        st.markdown("<br>", unsafe_allow_html=True)
        col_exp_log1, col_exp_log2 = st.columns(2)

        with col_exp_log1:
            buffer_log_xls = io.BytesIO()
            with pd.ExcelWriter(buffer_log_xls, engine='openpyxl') as writer:
                df_l[cols_reais].to_excel(writer, index=False, sheet_name="Auditoria_TCO")
            buffer_log_xls.seek(0)

            st.download_button(
                label=f"📊 Baixar Trilha de Auditoria em Excel ({len(df_l)} registros)",
                data=buffer_log_xls.getvalue(),
                file_name=f"Auditoria_TCO_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
                key="btn_dl_logs_excel"
            )

        with col_exp_log2:
            csv_bytes = df_l[cols_reais].to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📄 Baixar Trilha de Auditoria em CSV",
                data=csv_bytes,
                file_name=f"Auditoria_TCO_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="btn_dl_logs_csv"
            )
    else:
        st.info("Nenhum registro de auditoria encontrado com os parâmetros selecionados.")


# =============================================================================
# ABA 5: GESTORES CREDS
# =============================================================================
def renderizar_aba_gestores_creds(nome_operador="OPERADOR", unidade_operador="21º BPM", cargo_operador="MILITAR", perfil_operador="GESTOR"):
    usr_logado = st.session_state.get("usuario_dados", {})
    eh_autorizado = usuario_eh_gestor_creds(usr_logado)

    if not eh_autorizado:
        st.error("🔒 **Acesso Restrito:** Apenas Gestores do CREDS, Comandantes de Cia ou Administradores do SIOP podem gerenciar funções do TCO.")
        return

    perfil_creds_usr = usr_logado.get("perfil_creds", "TROPA")
    perfil_geral_usr = usr_logado.get("nivel_acesso", "TROPA")
    eh_gestor_unidade = (perfil_creds_usr == "GESTOR_UNIDADE" or perfil_geral_usr in ["ADMIN", "PROGRAMADOR"])

    st.markdown("### 👥 Designação e Estrutura de Gestores do CREDS / TCO")
    if eh_gestor_unidade:
        st.caption("🌐 **Visão Global (Batalhão):** Você possui permissão para gerenciar a função CREDS de **todas as Companhias**.")
    else:
        st.caption(f"🏢 **Visão Restrita:** Atribuição de permissão CREDS limitada à **{unidade_operador}**.")

    all_milit = carregar_militares_supabase() or []
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
                militar_sel_key = st.selectbox("Selecione o Policial Militar:", list(opcoes_militar.keys()), key="sel_novo_perfil_creds_aba7")
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
                if not eh_gestor_unidade and "GESTOR_UNIDADE" in chaves_disponiveis:
                    chaves_disponiveis.remove("GESTOR_UNIDADE")

                index_default = chaves_disponiveis.index(perfil_creds_atual) if perfil_creds_atual in chaves_disponiveis else len(chaves_disponiveis) - 1

                novo_perfil_creds = st.selectbox(
                    "Selecione a Função no Módulo CREDS/TCO:",
                    options=chaves_disponiveis,
                    format_func=lambda x: opcoes_perfis[x],
                    index=index_default,
                    key="sel_novo_perfil_creds_aba7_select"
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


# =============================================================================
# ALIASES DE RETROCOMPATIBILIDADE
# =============================================================================
renderizar_aba_importar_reds = renderizar_aba_importacao

def renderizar_aba_painel_creds(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    usr_logado = st.session_state.get("usuario_dados", {})
    eh_gestor = usuario_eh_gestor_creds(usr_logado)
    return renderizar_aba_creds(all_bens_banco, eh_gestor, nome_militar_atual, unidade_militar_atual)