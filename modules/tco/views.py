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
from modules.tco.estilo_tco import (
    renderizar_card_material_canva,
    injetar_estilo_canva_oficial,
    formatar_matricula_pm
)
from utils.file_validator import validar_pdf_upload, validar_imagem_upload, sanitizar_nome_arquivo

# ==============================================================================
# 🔍 FUNÇÕES AUXILIARES DE BANCO DE DADOS DO TCO
# ==============================================================================

def verificar_existencia_reds_banco(num_reds: str):
    """
    Verifica se um número de REDS já está registrado na base de dados.
    Retorna a tupla: (existe: bool, data_cadastro: str, operador_cadastro: str)
    """
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
    """Modal de aviso para REDS já existente no sistema."""
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
    elif "285" in str_u and ("CIA" in str_u or "TM" in str_u or "TÁTICO" in str_u or "TATIC" in str_u):
        return "285ª CIA TM"
    elif "21" in str_u and ("BPM" in str_u or "EM" in str_u or "BATALHAO" in str_u or "BATALHÃO" in str_u):
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


def obter_status_gargalo_e_tempo(bem):
    status_tr = bem.get("status_tramite", "Em Custódia")
    fase_dest = bem.get("fase_destinacao", "Com Fiel Depositário / Policial")
    dt_ref = bem.get("data_envio_tramite") or bem.get("data_posse_atual") or bem.get("data_ingestao")
    dest_pend = bem.get("destinatario_pendente")
    ultimo_op = bem.get("ultimo_gestor_movimentou") or bem.get("fiel_depositario_atual") or "N/I"
    
    texto_tempo, e_alerta_4dias, dias_num = calcular_tempo_decorrido_detalhado(dt_ref)
    
    if dest_pend and status_tr in ["Pendente de Aceite", "Pendente Aceite"]:
        ponto_cadeia = f"⏳ <b>Aguardando Aceite por:</b> <b>{dest_pend}</b>"
    elif status_tr == "Transferido Definitivo":
        ponto_cadeia = f"🔒 <b>Transferência Definitiva:</b> Encaminhado para <b>{fase_dest}</b>"
    elif "Perícia" in fase_dest:
        ponto_cadeia = f"🔬 <b>Em Perícia Técnica</b>"
    elif "PCMG" in fase_dest or "Delegacia" in fase_dest:
        ponto_cadeia = f"🏛️ <b>Encaminhado à Polícia Civil</b>"
    elif "JECRIM" in fase_dest or "Fórum" in fase_dest:
        ponto_cadeia = f"⚖️ <b>Entregue no JECRIM / Fórum</b>"
    elif "Destruição" in fase_dest or "Descarte" in fase_dest:
        ponto_cadeia = f"🔥 <b>Aguardando Destruição no Depósito</b>"
    elif "DESTRUÍDO" in fase_dest or "ENCERRADO" in status_tr.upper():
        ponto_cadeia = f"🔒 <b>Material Destruído / Encerrado</b>"
    elif "Aguardando no CREDS-TC" in fase_dest:
        ponto_cadeia = f"🏛️ <b>Aguardando no CREDS-TC / Custódia</b>"
    else:
        ponto_cadeia = f"🎒 <b>Em Custódia de:</b> <b>{bem.get('fiel_depositario_atual', 'N/I')}</b>"
        
    return ponto_cadeia, texto_tempo, e_alerta_4dias, dias_num


def gerar_excel_panoramico_tco(lista_bens_filtrados):
    buffer = io.BytesIO()
    dados_excel = []
    
    for b in lista_bens_filtrados:
        _, _, alerta_4d, dias_num = calcular_tempo_decorrido_detalhado(
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

# =============================================================================
# ABA 1: IMPORTAÇÃO E UPLOAD
# =============================================================================
def renderizar_aba_importacao(nome_militar_atual, unidade_militar_atual):
    injetar_estilo_canva_oficial()
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
            df_editado_ing = st.data_editor(
                df_mats[["remover", "item_num", "descricao", "quantidade", "unidade", "involucro", "autor"]],
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
# ABA 3: PAINEL DO CREDS INTEGRADO COM CARDS CANVA E STATUS DE LOCALIZAÇÃO
# =============================================================================
def renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual):
    injetar_estilo_canva_oficial()
    st.markdown("#### 🏛️ Painel do Gestor CREDS-TCO & Rastreamento de Custódia")
    
    if not eh_gestor_creds:
        st.error("🔒 **Acesso Restrito:** Apenas Gestores do CREDS-TCO têm acesso às funções deste painel.")
        return

    st.caption(f"⚙ **Gestão Institucional Ativa:** Operando como **CREDS TCO - {unidade_militar_atual}** | Gestor: **{nome_militar_atual}**")

    if "itens_selecionados_creds_painel" not in st.session_state:
        st.session_state["itens_selecionados_creds_painel"] = {}

    if "filtro_card_ativo" not in st.session_state:
        st.session_state["filtro_card_ativo"] = "TODOS"

    # Seleção de Filtros Superiores
    with st.container(border=True):
        c_exp1, c_exp2, c_exp3 = st.columns([1.5, 1.5, 1])
        with c_exp1:
            lista_creds_opts = ["TODOS OS CREDS (ACERVO GERAL)"] + [u for u in obter_lista_creds_dinamica() if "✏️" not in u]
            creds_selecionado = st.selectbox("Selecione o CREDS / Unidade:", lista_creds_opts, key="sb_creds_filtro_main")

        with c_exp2:
            dt_hoje = datetime.date.today()
            dt_30d = dt_hoje - datetime.timedelta(days=30)
            periodo_datas = st.date_input(
                "Período de Entrada (DD/MM/AAAA):",
                value=(dt_30d, dt_hoje),
                format="DD/MM/YYYY",
                key="range_datas_creds"
            )

        bens_filtrados_painel = all_bens_banco.copy() if all_bens_banco else []

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
                st.caption("Sem dados para exportação.")

    # Distribuição dos grupos operacionais
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

    for b in bens_filtrados_painel:
        ponto_cad, tempo_str, alerta_4d, dias_num = obter_status_gargalo_e_tempo(b)
        b_copy = dict(b)
        b_copy["_ponto_cadeia"] = ponto_cad
        b_copy["_tempo_str"] = tempo_str
        b_copy["_alerta_4dias"] = alerta_4d

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
        elif "PERÍCIA" in fase_d or status_t == "Transferido Definitivo" or any(term in dest_p or term in fase_d for term in ["DELEGACIA", "PCMG", "JECRIM", "FÓRUM", "TRIBUNAL"]):
            if "PERÍCIA" in fase_d:
                reds_pericia.add(num_r)
            bens_orgao_externo_tramite.append(b_copy)
        elif dest_p and ("CREDS" in dest_p or unidade_militar_atual in dest_p) and status_t in ["Pendente de Aceite", "Pendente Aceite"]:
            bens_pendentes_aceite_creds.append(b_copy)
        elif "CREDS" in fiel_atual or "CUSTÓDIA" in fiel_atual or "AGUARDANDO NO CREDS" in fase_d:
            reds_custodia_creds.add(num_r)
            bens_custodia_ativa_creds.append(b_copy)
        else:
            reds_custodia_policial.add(num_r)

    # Métricas
    kp1, kp2, kp3, kp4, kp5, kp6 = st.columns(6)
    with kp1:
        st.metric("🎒 No CREDS", len(reds_custodia_creds))
        if st.button("Filtrar CREDS", key="btn_f_creds", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "CREDS"
            st.rerun()
    with kp2:
        st.metric("🔬 Em Perícia", len(reds_pericia))
        if st.button("Filtrar Perícia", key="btn_f_pericia", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "PERICIA"
            st.rerun()
    with kp3:
        st.metric("🔥 Incineração", len(reds_destruicao))
        if st.button("Filtrar Incineração", key="btn_f_destruicao", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "DESTRUICAO"
            st.rerun()
    with kp4:
        st.metric("👮 Policial", len(reds_custodia_policial))
        if st.button("Filtrar Policial", key="btn_f_policial", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "POLICIAL"
            st.rerun()
    with kp5:
        st.metric("🚨 > 4 Dias", len(reds_parados))
        if st.button("Filtrar Parados", key="btn_f_parados", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "PARADOS"
            st.rerun()
    with kp6:
        st.metric("🔒 Encerrados", len(reds_destruidos_encerrados))
        if st.button("Filtrar Arquivo", key="btn_f_arquivo", use_container_width=True):
            st.session_state["filtro_card_ativo"] = "ARQUIVO"
            st.rerun()

    filtro_card = st.session_state.get("filtro_card_ativo", "TODOS")
    st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # RENDERIZAÇÃO DOS MATERIAIS COM CARDS ALTERNADOS
    # =========================================================================
    usr_dados = st.session_state.get("usuario_dados", {})
    mat_op = str(usr_dados.get("num_policia") or usr_dados.get("usuario_login") or "1764921")

    with st.container(border=True):
        st.markdown("##### 📦 Lista de Materiais — Rastreabilidade & Custódia")

        bens_exibicao = bens_custodia_ativa_creds
        if filtro_card == "DESTRUICAO":
            bens_exibicao = bens_aguardando_destruicao
        elif filtro_card == "PERICIA":
            bens_exibicao = [b for b in bens_orgao_externo_tramite if "PERÍCIA" in str(b.get("fase_destinacao", "")).upper()]
        elif filtro_card == "ARQUIVO":
            bens_exibicao = bens_destruidos_encerrados
        elif filtro_card == "PARADOS":
            bens_exibicao = [b for b in bens_filtrados_painel if b.get("_alerta_4dias")]

        if not bens_exibicao:
            st.info("ℹ️ Nenhum material localizado nesta categoria.")
        else:
            for idx_c, bem_item in enumerate(bens_exibicao):
                def _ao_movimentar(item_alvo):
                    id_alvo = str(item_alvo.get("id_bem") or item_alvo.get("id"))
                    st.session_state["itens_selecionados_creds_painel"][id_alvo] = item_alvo
                    st.toast(f"Item {item_alvo.get('descricao')} selecionado para tramitação!", icon="📦")
                    st.rerun()

                renderizar_card_material_canva(
                    bem=bem_item,
                    idx_chave=idx_c,
                    nome_operador=nome_militar_atual,
                    mat_operador=mat_op,
                    unid_operador=unidade_militar_atual,
                    callback_movimentar=_ao_movimentar
                )

    # =========================================================================
    # SEÇÃO DE DESTINAÇÃO FORMAL / MOVIMENTAÇÃO COM DEFINIÇÃO DE LOCAL
    # =========================================================================
    sel_map = st.session_state["itens_selecionados_creds_painel"]
    if sel_map:
        st.markdown("---")
        st.markdown(f"### 🎯 Atualizar Localização / Trâmite ({len(sel_map)} selecionado(s))")

        with st.form("form_despacho_painel_creds", clear_on_submit=False):
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                tipo_destino = st.selectbox(
                    "Selecione o Destino / Órgão:",
                    [
                        "Aguardando no CREDS-TC / Custódia",
                        "PERÍCIA TÉCNICA / PERÍCIA OFICIAL",
                        "DELEGACIA DE POLÍCIA CIVIL (PCMG)",
                        "PODER JUDICIÁRIO / TRIBUNAL DE JUSTIÇA (JECRIM)",
                        "DEPÓSITO DE CUSTÓDIA / AGUARDANDO DESTRUIÇÃO",
                        "Policial Militar / Fiel Depositário",
                        "Devolvido ao Proprietário"
                    ]
                )
            with col_d2:
                recebedor_txt = st.text_input("Nome e Matrícula de quem recebeu (OBRIGATÓRIO):", placeholder="Ex: INVESTIGADOR PCMG MAT. 123456").strip()

            if st.form_submit_button("🚀 Confirmar Movimentação", type="primary", use_container_width=True):
                if not recebedor_txt:
                    st.error("Informe o recebedor e matrícula para validação da cadeia.")
                else:
                    agora_iso = datetime.datetime.now().isoformat()
                    for id_b, d_item in sel_map.items():
                        eh_ext = any(t in tipo_destino for t in ["PERÍCIA", "PCMG", "JECRIM", "DESTRUIÇÃO"])
                        payload = {
                            "destinatario_pendente": None if not eh_ext else tipo_destino,
                            "unidade_destinatario_pendente": tipo_destino,
                            "fase_destinacao": tipo_destino,
                            "status_tramite": "Transferido Definitivo" if "DESTRUIÇÃO" in tipo_destino else "Em Custódia",
                            "ultimo_gestor_movimentou": nome_militar_atual,
                            "data_posse_atual": agora_iso
                        }
                        atualizar_material_supabase(id_b, payload)
                        registrar_log_supabase({
                            "data_hora": agora_iso,
                            "num_reds": d_item.get("num_reds", "N/I"),
                            "bem_id": f"{d_item.get('descricao')} (Lacre: {d_item.get('involucro_lacre')})",
                            "acao": "TRAMITACAO_DESTINO",
                            "origem": nome_militar_atual,
                            "unidade_origem": unidade_militar_atual,
                            "destino": tipo_destino,
                            "unidade_destino": tipo_destino,
                            "detalhe": f"Fase atualizada para '{tipo_destino}'. Recebido por: {recebedor_txt}"
                        })
                    st.session_state["itens_selecionados_creds_painel"] = {}
                    st.success("Materiais movimentados com sucesso!")
                    st.rerun()


# =============================================================================
# ABA 4: AUDITORIA
# =============================================================================
def renderizar_aba_logs(all_logs_banco):
    st.markdown("### 📜 Trilha de Auditoria Imutável (Supabase)")
    if all_logs_banco:
        df_l = pd.DataFrame(all_logs_banco)
        st.dataframe(df_l, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum registro de log encontrado.")


# =============================================================================
# ABA 5: GESTORES CREDS
# =============================================================================
def renderizar_aba_gestores_creds(nome_operador="OPERADOR", unidade_operador="21º BPM", cargo_operador="MILITAR", perfil_operador="GESTOR"):
    st.markdown("### 👥 Gestores CREDS Designados")
    st.info("Painel administrativo para controle das permissões do TCO.")


renderizar_aba_painel_creds = renderizar_aba_creds