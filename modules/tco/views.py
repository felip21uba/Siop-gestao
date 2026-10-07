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
from modules.tco.estilo_tco import modal_cadeia_custodia_timeline, modal_guia_termo_oficial
from utils.file_validator import validar_pdf_upload, validar_imagem_upload, sanitizar_nome_arquivo

# ==============================================================================
# 🎨 CAMADA CSS MATTE SUAVE (IDÊNTICA AO HTML APROVADO)
# ==============================================================================

def injetar_css_painel_creds_matte():
    """Injeta a folha de estilos matte com baixo brilho e cards alternados suaves."""
    st.markdown("""
    <style>
    :root {
        --bg-card-dark: #26272b;
        --border-card-dark: #373940;
        --text-card-dark: #dedfe3;
        --box-data-dark: #323338;

        --bg-card-soft: #383630;
        --border-card-soft: #4d4a42;
        --text-card-soft: #e2dfd7;
        --box-data-soft: #47443d;
        
        --accent-sand: #b8ab91;
        --border-header: #47433b;
        --badge-border: #807765;
    }

    /* Cards Alternados */
    .card-material-item {
        border-radius: 6px;
        padding: 14px 18px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-bottom: 12px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .card-material-item.card-dark {
        background-color: var(--bg-card-dark);
        border: 1px solid var(--border-card-dark);
        color: var(--text-card-dark);
    }
    .card-material-item.card-dark b, 
    .card-material-item.card-dark strong { color: #ffffff; }

    .card-material-item.card-dark .caixa-data-tramite {
        background-color: var(--box-data-dark);
        border: 1px solid #43454d;
        color: #f0ede6;
    }

    .card-material-item.card-dark .linha-auditoria-pontilhada {
        border-top: 1px dashed #3e4047;
        color: #a8a59e;
    }
    .card-material-item.card-dark .linha-auditoria-pontilhada strong { color: #ffffff; }

    .card-material-item.card-soft {
        background-color: var(--bg-card-soft);
        border: 1px solid var(--border-card-soft);
        color: var(--text-card-soft);
    }
    .card-material-item.card-soft b, 
    .card-material-item.card-soft strong { color: #ffffff; }

    .card-material-item.card-soft .caixa-data-tramite {
        background-color: var(--box-data-soft);
        border: 1px solid #575349;
        color: #f7f5f0;
    }

    .card-material-item.card-soft .linha-auditoria-pontilhada {
        border-top: 1px dashed #524f46;
        color: #d1cdc5;
    }
    .card-material-item.card-soft .linha-auditoria-pontilhada strong { color: #ffffff; }

    .card-topo-flex {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
    }

    .card-dados-texto {
        line-height: 1.6;
        font-size: 0.92rem;
    }

    .badge-creds-ativo {
        border: 1px solid #6b665a;
        background-color: #2b2a26;
        color: var(--accent-sand);
        border-radius: 4px;
        padding: 3px 10px;
        font-size: 0.76rem;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        white-space: nowrap;
        text-transform: uppercase;
    }

    .caixa-data-tramite {
        border-radius: 4px;
        padding: 2px 8px;
        font-weight: 600;
        font-size: 0.84rem;
        display: inline-block;
        margin-top: 3px;
        font-family: monospace;
    }

    .linha-auditoria-pontilhada {
        margin-top: 6px;
        padding-top: 8px;
        font-size: 0.82rem;
        display: flex;
        align-items: center;
        gap: 16px;
    }

    .badge-alert-pulse {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background-color: #331f20;
        border: 1px solid #c95757;
        color: #deb6b6;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.70rem;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)


# ==============================================================================
# 🔍 FUNÇÕES AUXILIARES DE SUPABASE
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


def gerar_excel_panoramico_tco(lista_bens_filtrados):
    buffer = io.BytesIO()
    dados_excel = []
    
    for b in lista_bens_filtrados:
        _, _, _, dias_num = calcular_tempo_decorrido_detalhado(
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
            "Destinatário Pendente": str(b.get("destinatario_pendente", "NENHUM")),
            "Unidade / Posse Atual": str(b.get("unidade_posse_atual", "N/A")),
            "Fase / Destinação Final": str(b.get("fase_destinacao", "N/I")),
            "Status do Trâmite": str(b.get("status_tramite", "N/I")),
            "Tempo Imóvel (Dias)": dias_num,
            "Data Importação REDS": dt_ing_fmt
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
    injetar_css_painel_creds_matte()
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
# ABA 3: PAINEL DO CREDS (LAYOUT MATTE COM CARDS ALTERNADOS E LOCALIZAÇÃO)
# =============================================================================
def renderizar_aba_creds(all_bens_banco, eh_gestor_creds, nome_militar_atual, unidade_militar_atual):
    injetar_css_painel_creds_matte()
    
    st.markdown("#### 🏛️ Painel do Gestor CREDS-TCO & Rastreamento de Custódia")
    
    if not eh_gestor_creds:
        st.error("🔒 **Acesso Restrito:** Apenas Gestores do CREDS-TCO têm acesso às funções deste painel.")
        return

    st.caption(f"⚙ **Gestão Institucional Ativa:** Operando como **CREDS TCO - {unidade_militar_atual}** | Gestor: **{nome_militar_atual}**")

    if "filtro_kpi_painel_ativo" not in st.session_state:
        st.session_state["filtro_kpi_painel_ativo"] = "TODOS"

    if "material_selecionado_mov" not in st.session_state:
        st.session_state["material_selecionado_mov"] = None

    # Filtro Superior de Unidade e Exportação
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

    # Mapeamento dos grupos por localização e status
    bens_no_creds = []
    bens_em_pericia = []
    bens_incineracao = []
    bens_policial = []
    bens_parados_4d = []
    bens_encerrados = []

    for b in bens_filtrados_painel:
        dt_ref = b.get("data_envio_tramite") or b.get("data_posse_atual") or b.get("data_ingestao")
        _, alerta_4d, dias_num = calcular_tempo_decorrido_detalhado(dt_ref)
        b_c = dict(b)
        b_c["_alerta_4dias"] = alerta_4d
        b_c["_dias_num"] = dias_num

        fase = str(b.get("fase_destinacao") or "").upper()
        status_tr = str(b.get("status_tramite") or "").upper()
        custod = str(b.get("fiel_depositario_atual") or "").upper()
        dest_p = str(b.get("destinatario_pendente") or "").upper()

        if alerta_4d and status_tr not in ["DESTRUÍDO / ENCERRADO", "TRANSFERIDO DEFINITIVO"]:
            bens_parados_4d.append(b_c)

        if "DESTRUÍDO" in fase or "ENCERRADO" in status_tr:
            bens_encerrados.append(b_c)
        elif "INCINERAÇÃO" in fase or "DESTRUIÇÃO" in fase or "DESCARTE" in fase:
            bens_incineracao.append(b_c)
        elif "PERÍCIA" in fase or "PERÍCIA" in dest_p:
            bens_em_pericia.append(b_c)
        elif "POLICIAL" in fase or "FIEL DEPOSITÁRIO" in fase:
            bens_policial.append(b_c)
        elif "CREDS" in custod or "CUSTÓDIA" in custod or "AGUARDANDO NO CREDS" in fase:
            bens_no_creds.append(b_c)
        else:
            bens_no_creds.append(b_c)

    # =========================================================================
    # BARRA DE MÉTRICAS (KPIS MATTE COM CONTADORES E FILTROS DIRETOS)
    # =========================================================================
    st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        st.metric("🏛️ No CREDS-TC", len(bens_no_creds))
        if st.button("Filtrar CREDS", key="kpi_btn_creds", use_container_width=True):
            st.session_state["filtro_kpi_painel_ativo"] = "CREDS"
            st.rerun()

    with k2:
        st.metric("🎒 Custódia Policial", len(bens_policial))
        if st.button("Filtrar Policial", key="kpi_btn_policial", use_container_width=True):
            st.session_state["filtro_kpi_painel_ativo"] = "POLICIAL"
            st.rerun()

    with k3:
        st.metric("🔬 Em Perícia", len(bens_em_pericia))
        if st.button("Filtrar Perícia", key="kpi_btn_pericia", use_container_width=True):
            st.session_state["filtro_kpi_painel_ativo"] = "PERICIA"
            st.rerun()

    with k4:
        st.metric("🔥 Aguard. Incineração", len(bens_incineracao))
        if st.button("Filtrar Incineração", key="kpi_btn_incineracao", use_container_width=True):
            st.session_state["filtro_kpi_painel_ativo"] = "INCINERACAO"
            st.rerun()

    with k5:
        st.metric("🚨 Parados > 4 Dias", len(bens_parados_4d))
        if st.button("Filtrar Parados", key="kpi_btn_parados", use_container_width=True):
            st.session_state["filtro_kpi_painel_ativo"] = "PARADOS"
            st.rerun()

    with k6:
        st.metric("🔒 Encerrados", len(bens_encerrados))
        if st.button("Filtrar Encerrados", key="kpi_btn_encerrados", use_container_width=True):
            st.session_state["filtro_kpi_painel_ativo"] = "ENCERRADOS"
            st.rerun()

    filtro_ativo = st.session_state.get("filtro_kpi_painel_ativo", "TODOS")
    if filtro_ativo != "TODOS":
        col_st1, col_st2 = st.columns([4, 1])
        with col_st1:
            st.info(f"Filtro ativo: **{filtro_ativo}**")
        with col_st2:
            if st.button("Mostrar Todos", key="btn_limpar_kpi_painel", use_container_width=True):
                st.session_state["filtro_kpi_painel_ativo"] = "TODOS"
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # LISTA DE MATERIAIS COM OS CARDS ALTERNADOS E AÇÕES CONECTADAS
    # =========================================================================
    bens_para_exibir = bens_filtrados_painel
    if filtro_ativo == "CREDS":
        bens_para_exibir = bens_no_creds
    elif filtro_ativo == "POLICIAL":
        bens_para_exibir = bens_policial
    elif filtro_ativo == "PERICIA":
        bens_para_exibir = bens_em_pericia
    elif filtro_ativo == "INCINERACAO":
        bens_para_exibir = bens_incineracao
    elif filtro_ativo == "PARADOS":
        bens_para_exibir = bens_parados_4d
    elif filtro_ativo == "ENCERRADOS":
        bens_para_exibir = bens_encerrados

    with st.container(border=True):
        st.markdown(f"##### 📦 Acervo e Materiais Registrados ({len(bens_para_exibir)} itens)")

        if not bens_para_exibir:
            st.info("Nenhum material encontrado com os critérios de filtro atuais.")
        else:
            usr_dados = st.session_state.get("usuario_dados", {})
            mat_op = str(usr_dados.get("num_policia") or usr_dados.get("usuario_login") or "1764921")

            for idx, item in enumerate(bens_para_exibir):
                id_bem = str(item.get("id_bem") or item.get("id"))
                num_reds = str(item.get("num_reds") or "N/I").strip()
                desc = str(item.get("descricao") or "N/I").strip()
                qtd = item.get("quantidade", 1)
                unid = item.get("unidade_medida", "UN")
                lacre = str(item.get("involucro_lacre") or "SEM LACRE").strip()
                autor = str(item.get("autores") or "N/I").strip()
                
                # Identificação precisa da Localização do Material
                custodiante_local = str(
                    item.get("destinatario_pendente") 
                    or item.get("fiel_depositario_atual") 
                    or item.get("fase_destinacao") 
                    or "CREDS TCO"
                ).strip()

                dt_mov = formatar_data_hora_exata(
                    item.get("data_envio_tramite") or item.get("data_posse_atual") or item.get("data_ingestao")
                )

                responsavel = str(item.get("ultimo_gestor_movimentou") or f"{nome_militar_atual} - MAT. {formatar_matricula_pm(mat_op)}")
                dias_sem_tramite = item.get("_dias_num", 0)

                # Definição do Badge de Local/Status
                fase_u = str(item.get("fase_destinacao") or "").upper()
                status_u = str(item.get("status_tramite") or "").upper()

                if "DESTRUÍDO" in fase_u or "ENCERRADO" in status_u:
                    badge_texto = "🔒 ENCERRADO"
                elif "INCINERAÇÃO" in fase_u or "DESTRUIÇÃO" in fase_u:
                    badge_texto = "🔥 INCINERAÇÃO"
                elif "PERÍCIA" in fase_u:
                    badge_texto = "🔬 EM PERÍCIA"
                elif "PCMG" in fase_u or "DELEGACIA" in fase_u:
                    badge_texto = "🏛️ POLÍCIA CIVIL"
                elif "JECRIM" in fase_u or "FÓRUM" in fase_u:
                    badge_texto = "⚖️ JECRIM / FÓRUM"
                elif "POLICIAL" in fase_u:
                    badge_texto = "🎒 CUSTÓDIA POLICIAL"
                else:
                    badge_texto = "📇 CREDS ATIVO"

                # Alternância idêntica ao HTML: Par = card-dark | Ímpar = card-soft
                classe_card = "card-dark" if (idx % 2 == 0) else "card-soft"

                alerta_html = f'<div style="margin-top:4px;"><span class="badge-alert-pulse">⚠️ {dias_sem_tramite} DIAS SEM TRÂMITE</span></div>' if dias_sem_tramite >= 4 else ''

                html_card = f"""
                <div class="card-material-item {classe_card}">
                    <div class="card-topo-flex">
                        <div class="card-dados-texto">
                            📄 REDS: <b>{num_reds}</b> | Material: <b>{desc}</b> (Qtd: {qtd} {unid})<br/>
                            🏷️ Lacre: <b style="font-family: monospace;">{lacre}</b> | Autor: <b>{autor}</b><br/>
                            📍 Custodiante / Local: <b>{custodiante_local}</b><br/>
                            ⏱️ Data/Hora do Trâmite: <span class="caixa-data-tramite">{dt_mov}</span>
                        </div>
                        <div style="display: flex; flex-direction: column; align-items: flex-end;">
                            <div class="badge-creds-ativo">{badge_texto}</div>
                            {alerta_html}
                        </div>
                    </div>
                    <div class="linha-auditoria-pontilhada">
                        <div>🛡️ <b>Responsável:</b> {responsavel}</div>
                        <div>🗺️ <b>Art. 158-B CPP:</b> Rastreabilidade Asseverada</div>
                    </div>
                </div>
                """
                st.markdown(html_card, unsafe_allow_html=True)

                # Ações de cada material conectadas aos modais do sistema
                c_esp, c_cad, c_guia, c_mov = st.columns([5.2, 1.6, 1.6, 1.6])
                with c_cad:
                    if st.button("🔗 Cadeia", key=f"btn_cad_pnl_{id_bem}_{idx}", use_container_width=True):
                        modal_cadeia_custodia_timeline(item)
                with c_guia:
                    if st.button("🖨️ Guia / Termo", key=f"btn_guia_pnl_{id_bem}_{idx}", use_container_width=True):
                        modal_guia_termo_oficial(item, nome_militar_atual, mat_op, unidade_militar_atual)
                with c_mov:
                    if st.button("🛒 Movimentar", key=f"btn_mov_pnl_{id_bem}_{idx}", type="primary", use_container_width=True):
                        st.session_state["material_selecionado_mov"] = item
                        st.toast(f"Material {desc} selecionado para definição de destino abaixo!", icon="📦")

    # =========================================================================
    # FORMULÁRIO DE MOVIMENTAÇÃO / DESTINAÇÃO FORMAL
    # =========================================================================
    mat_mov = st.session_state.get("material_selecionado_mov")
    if mat_mov:
        st.markdown("---")
        st.markdown(f"### 🎯 Movimentar / Definir Local de Destino: `{mat_mov.get('descricao')}`")
        st.caption(f"REDS: `{mat_mov.get('num_reds')}` | Lacre: `{mat_mov.get('involucro_lacre')}`")

        with st.form("form_tramitar_painel_creds_v2", clear_on_submit=False):
            col_t1, col_t2 = st.columns(2)
            
            with col_t1:
                destino_final = st.selectbox(
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
                recebedor_nome_mat = st.text_input(
                    "Nome Completo e Matrícula de quem recebeu (OBRIGATÓRIO):",
                    placeholder="Ex: INVESTIGADOR PCMG MAT. 123456"
                ).strip()

            c_sub1, c_sub2 = st.columns(2)
            with c_sub1:
                btn_confirmar_mov = st.form_submit_button("🚀 Confirmar Movimentação do CREDS", type="primary", use_container_width=True)
            with c_sub2:
                btn_cancelar_mov = st.form_submit_button("❌ Cancelar", use_container_width=True)

            if btn_cancelar_mov:
                st.session_state["material_selecionado_mov"] = None
                st.rerun()

            if btn_confirmar_mov:
                if not recebedor_nome_mat:
                    st.error("Informe o Nome Completo e Matrícula de quem recebeu para garantir a cadeia de custódia.")
                else:
                    agora_iso = datetime.datetime.now().isoformat()
                    eh_definitivo = any(t in destino_final for t in ["PERÍCIA", "PCMG", "JECRIM", "DESTRUIÇÃO", "Devolvido"])
                    
                    status_novo = "Transferido Definitivo" if eh_definitivo else "Em Custódia"
                    dest_pend = destino_final if eh_definitivo else None

                    payload_upd = {
                        "destinatario_pendente": dest_pend,
                        "unidade_destinatario_pendente": destino_final,
                        "fase_destinacao": destino_final,
                        "fiel_depositario_atual": destino_final if eh_definitivo else f"CREDS TCO - {unidade_militar_atual}",
                        "status_tramite": status_novo,
                        "ultimo_gestor_movimentou": nome_militar_atual,
                        "data_posse_atual": agora_iso,
                        "data_envio_tramite": agora_iso
                    }

                    id_bem_mov = str(mat_mov.get("id_bem") or mat_mov.get("id"))
                    
                    if atualizar_material_supabase(id_bem_mov, payload_upd):
                        registrar_log_supabase({
                            "data_hora": agora_iso,
                            "num_reds": mat_mov.get("num_reds", "N/I"),
                            "bem_id": f"{mat_mov.get('descricao')} (Lacre: {mat_mov.get('involucro_lacre')})",
                            "acao": "MOVIMENTACAO_GESTOR_CREDS",
                            "origem": f"CREDS TCO - {unidade_militar_atual}",
                            "unidade_origem": unidade_militar_atual,
                            "destino": destino_final,
                            "unidade_destino": destino_final,
                            "detalhe": f"Destino atualizado para '{destino_final}'. Recebedor: {recebedor_nome_mat} | Gestor: {nome_militar_atual}"
                        })
                        st.session_state["material_selecionado_mov"] = None
                        st.success("✅ Movimentação confirmada e registrada com sucesso!")
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