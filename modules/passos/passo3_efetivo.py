import streamlit as st
import uuid
import re
import unicodedata
import datetime
import pandas as pd
from core.database import (
    supabase, 
    salvar_militares_supabase, 
    carregar_militares_supabase
)
from utils.excel_importer import carregar_planilha_universal

PESOS_HIERARQUIA = {
    "CEL": 1, "TEN CEL": 2, "MAJ": 3, "CAP": 4, "1º TEN": 5, "2º TEN": 6, "ASP": 7,
    "CAD": 8, "AL OF": 9, "SUB TEN": 10, "1º SGT": 11, "2º SGT": 12, "3º SGT": 13,
    "CB": 14, "SD": 15, "SD AL": 16
}

def padronizar_graduacao(texto):
    if not texto:
        return "SD"
    t = str(texto).strip().upper()
    if "SOLDADO DE 1" in t or "SOLDADO 1" in t or "SD 1" in t or "1 CLASSE" in t or "1ª CLASSE" in t or t == "SOLDADO":
        return "SD"
    elif "ALUNO" in t or "SD AL" in t or "AL SD" in t:
        return "SD AL"
    elif "CABO" in t or t == "CB":
        return "CB"
    elif "3" in t and "SGT" in t or "TERCEIRO" in t:
        return "3º SGT"
    elif "2" in t and "SGT" in t or "SEGUNDO" in t:
        return "2º SGT"
    elif "1" in t and "SGT" in t or "PRIMEIRO" in t:
        return "1º SGT"
    elif "SUB" in t or "ST" in t:
        return "SUB TEN"
    elif "2" in t and "TEN" in t or "SEGUNDO TENENTE" in t:
        return "2º TEN"
    elif "1" in t and "TEN" in t or "PRIMEIRO TENENTE" in t:
        return "1º TEN"
    elif "CAP" in t:
        return "CAP"
    elif "MAJ" in t or "MAJOR" in t:
        return "MAJ"
    elif "TEN CEL" in t or "TENENTE CORONEL" in t or "TC" in t:
        return "TEN CEL"
    elif "CEL" in t or "CORONEL" in t:
        return "CEL"
    elif "ASP" in t:
        return "ASP"
    elif "CAD" in t:
        return "CAD"
    return "SD"

def extrair_cidade_planilha(row):
    """Lê diretamente a coluna NOME MUNICIPIO da planilha."""
    val = row.get("NOME MUNICIPIO", row.get("NOME_MUNICIPIO", row.get("MUNICIPIO", row.get("CIDADE", ""))))
    val_str = str(val).strip().upper()
    if val_str and val_str not in ["NONE", "NAN", "NULL", "<NA>", ""]:
        return val_str
    return "N/I"

def extrair_unidade_planilha(row):
    """Lê diretamente a coluna NOME UNIDADE da planilha."""
    val = row.get("NOME UNIDADE", row.get("NOME_UNIDADE", row.get("UNIDADE", "")))
    val_str = str(val).strip().upper()
    if val_str and val_str not in ["NONE", "NAN", "NULL", "<NA>", ""]:
        return val_str
    return "UNIDADE N/I"

def remover_duplicados_militares(lista):
    """Garante a unicidade estrita do efetivo filtrando pelo número unificado de polícia."""
    vistos = set()
    lista_unica = []
    for m in lista:
        num = str(m.get("num_policia", "")).strip().upper()
        if num and num not in vistos and num != "NAN":
            vistos.add(num)
            lista_unica.append(m)
    return lista_unica

def excluir_militar_banco_e_memoria(m_id, num_policia):
    """
    Remove o militar da memória garantindo duplo alinhamento
    (ID e Nº Polícia) para impedir que ele retorne ao quadro da esquerda.
    """
    m_id_str = str(m_id).strip()
    num_pol_str = str(num_policia).strip().upper()

    st.session_state["lista_militares"] = [
        m for m in st.session_state.get("lista_militares", [])
        if str(m.get("id")).strip() != m_id_str 
        and str(m.get("num_policia")).strip().upper() != num_pol_str
    ]
    
    st.session_state["militares_selecionados_ids"] = [
        i for i in st.session_state.get("militares_selecionados_ids", [])
        if str(i).strip() != m_id_str
    ]
        
    if supabase:
        try:
            supabase.table("militares").delete().eq("num_policia", num_pol_str).execute()
        except Exception:
            try:
                supabase.table("militares").delete().eq("id", m_id_str).execute()
            except Exception:
                pass

def excluir_lote_banco_e_memoria(mils_para_excluir):
    """Exclui em lote apagando definitivamente do SIOP e Supabase."""
    ids_excluir = set(str(m.get("id")).strip() for m in mils_para_excluir)
    nums_excluir = set(str(m.get("num_policia")).strip().upper() for m in mils_para_excluir if m.get("num_policia"))

    st.session_state["lista_militares"] = [
        m for m in st.session_state.get("lista_militares", [])
        if str(m.get("id")).strip() not in ids_excluir
        and str(m.get("num_policia")).strip().upper() not in nums_excluir
    ]
    
    st.session_state["militares_selecionados_ids"] = [
        m_id for m_id in st.session_state.get("militares_selecionados_ids", [])
        if str(m_id).strip() not in ids_excluir
    ]

    if supabase and nums_excluir:
        try:
            supabase.table("militares").delete().in_("num_policia", list(nums_excluir)).execute()
        except Exception:
            try:
                supabase.table("militares").delete().in_("id", list(ids_excluir)).execute()
            except Exception:
                pass

def tratar_num_policia_unificado(row):
    """Unifica Número (Matrícula) e Dígito (DV)."""
    num_principal = str(row.get("NUMERO", row.get("NUMERO_POLICIA", row.get("MATRICULA", "")))).strip()
    digito = str(row.get("DV", row.get("DIGITO", row.get("VERIFICADOR", "")))).strip()
    
    if num_principal.endswith(".0"):
        num_principal = num_principal[:-2]
    if digito.endswith(".0"):
        digito = digito[:-2]
        
    num_clean = re.sub(r'\D', '', num_principal)
    dv_clean = re.sub(r'\D', '', digito)
    
    if not num_clean:
        return ""

    if dv_clean and dv_clean.upper() != "NAN":
        if "-" in num_principal and num_principal.endswith(f"-{dv_clean}"):
            return num_clean
            
        if len(num_clean) <= 5:
            return f"{num_clean}{dv_clean}"
            
        if len(num_clean) >= 6 and num_clean.endswith(dv_clean):
            return num_clean
        else:
            return f"{num_clean}{dv_clean}"
    else:
        return num_clean

@st.dialog("🚨 Confirmar Exclusão dos Militares Selecionados")
def abrir_modal_excluir_lote():
    sel_ids = set(str(i) for i in st.session_state.get("militares_selecionados_ids", []))
    mils_todos = st.session_state.get("lista_militares", [])
    mils_para_excluir = [m for m in mils_todos if str(m["id"]) in sel_ids]
    
    if not mils_para_excluir:
        st.warning("⚠️ Nenhum militar está presente no Quadro da Direita para ser excluído.")
        if st.button("Entendido", width="stretch"):
            st.rerun()
        return

    st.error(f"⚠️ **Atenção:** Você está prestes a excluir definitivamente **{len(mils_para_excluir)} militar(es)** do Quadro da Direita (Selecionados).")
    st.caption("Esta ação removerá estes registros do SIOP e do banco Supabase.")
    
    df_exc = pd.DataFrame([
        {
            "Grad/Nome": f"{m.get('posto_grad')} {m.get('nome_guerra')}", 
            "Nº Polícia (com DV)": m.get('num_policia'), 
            "Unidade": m.get('unidade'),
            "Cidade": m.get('cidade')
        } 
        for m in mils_para_excluir
    ])
    st.dataframe(df_exc, width="stretch", hide_index=True, height=180)
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        if st.button("🚨 Confirmar Exclusão Definitiva", type="primary", width="stretch"):
            with st.spinner("Excluindo do banco de dados..."):
                excluir_lote_banco_e_memoria(mils_para_excluir)
            st.success(f"✅ {len(mils_para_excluir)} militar(es) excluído(s) com sucesso!")
            st.rerun()
    with col_d2:
        if st.button("❌ Cancelar", width="stretch"):
            st.rerun()

@st.dialog("📥 Importar Efetivo via Planilha", width="large")
def abrir_modal_upload_planilha():
    st.markdown("##### 📁 Selecione o arquivo Excel ou CSV contendo a relação dos militares:")
    st.caption("Cabeçalhos buscados: NUMERO, DV, POSTO/GRADUACAO, NOME SERVIDOR, NOME UNIDADE, NOME MUNICIPIO")
    
    arquivo_planilha = st.file_uploader("Selecione o arquivo XLSX/CSV:", type=["xls", "xlsx", "csv"], key="uploader_efetivo_modal")
    
    if arquivo_planilha is not None:
        if st.button("📥 Processar e Conferir Dados", type="primary", width="stretch"):
            try:
                df_imp = carregar_planilha_universal(arquivo_planilha)
                df_imp.columns = [str(c).strip().upper() for c in df_imp.columns]

                lista_temp = []
                for idx_row, row in df_imp.iterrows():
                    mat_unificada = tratar_num_policia_unificado(row)
                    if not mat_unificada or mat_unificada.upper() == "NAN":
                        continue

                    posto_raw = str(row.get("POSTO/GRADUACAO", row.get("POSTO_GRAD", "SD"))).strip().upper()
                    pg_sigla = padronizar_graduacao(posto_raw)
                    nome_serv = str(row.get("NOME SERVIDOR", row.get("NOME_COMPLETO", "MILITAR"))).strip().upper()
                    parts_nome = nome_serv.split()
                    n_guerra_ext = parts_nome[-1] if len(parts_nome) > 1 else nome_serv
                    
                    cidade_val = extrair_cidade_planilha(row)
                    unidade_val = extrair_unidade_planilha(row)

                    lista_temp.append({
                        "id": f"mili_{idx_row}_{uuid.uuid4().hex[:6]}",
                        "num_policia": mat_unificada,
                        "posto_grad": pg_sigla,
                        "nome_guerra": n_guerra_ext,
                        "nome_completo": nome_serv,
                        "cidade": cidade_val,
                        "peso": PESOS_HIERARQUIA.get(pg_sigla, 99),
                        "unidade": unidade_val
                    })
                
                st.session_state["temp_importacao_lista"] = remover_duplicados_militares(lista_temp)
            except Exception as ex:
                st.error(f"Erro ao processar planilha: {ex}")

    if st.session_state.get("temp_importacao_lista"):
        st.divider()
        lista_temp = st.session_state.get("temp_importacao_lista", [])
        
        numeros_existentes = {str(m.get("num_policia", "")).strip().upper() for m in st.session_state.get("lista_militares", [])}
        novos_para_importar = [item for item in lista_temp if str(item.get("num_policia", "")).strip().upper() not in numeros_existentes]
        
        if not novos_para_importar:
            st.info("ℹ️ Todos os militares desta planilha já estão cadastrados no SIOP.")
            if st.button("❌ Fechar Janela", type="primary", width="stretch"):
                st.session_state["temp_importacao_lista"] = []
                st.rerun()
            return
            
        st.markdown(f"**{len(novos_para_importar)} novo(s) militar(es) identificado(s).** Confira e edite os dados:")
        df_temp = pd.DataFrame(novos_para_importar)[["num_policia", "posto_grad", "nome_completo", "nome_guerra", "unidade", "cidade"]]
        df_temp.columns = ["Nº Polícia (com DV)", "Graduação", "Nome Completo", "Nome Funcional", "Unidade", "Cidade / Município"]
        
        df_editado = st.data_editor(
            df_temp, num_rows="fixed", width="stretch", height=250,
            column_config={
                "Nº Polícia (com DV)": st.column_config.TextColumn(disabled=True), 
                "Graduação": st.column_config.TextColumn(disabled=True)
            }
        )
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("✅ Confirmar e Salvar no SIOP & Supabase", type="primary", width="stretch"):
                novos_salvar = []
                for idx_r, row_e in df_editado.iterrows():
                    pg = padronizar_graduacao(row_e["Graduação"])
                    m_id = f"mili_{idx_r}_{uuid.uuid4().hex[:6]}"
                    novos_salvar.append({
                        "id": m_id,
                        "num_policia": str(row_e["Nº Polícia (com DV)"]).strip(),
                        "posto_grad": pg,
                        "nome_guerra": str(row_e["Nome Funcional"]).strip().upper(),
                        "nome_completo": str(row_e["Nome Completo"]).strip().upper(),
                        "cidade": str(row_e["Cidade / Município"]).strip().upper(),
                        "peso": PESOS_HIERARQUIA.get(pg, 99),
                        "unidade": str(row_e["Unidade"]).strip().upper()
                    })
                
                salvar_militares_supabase(novos_salvar)
                st.session_state["lista_militares"] = remover_duplicados_militares(
                    st.session_state.get("lista_militares", []) + novos_salvar
                )
                st.session_state["temp_importacao_lista"] = []
                st.success("✅ Carga gravada no Supabase com sucesso!")
                st.rerun()
        with col_m2:
            if st.button("❌ Cancelar Importação", width="stretch"):
                st.session_state["temp_importacao_lista"] = []
                st.rerun()

@st.dialog("➕ Cadastrar Novo Militar", width="medium")
def abrir_modal_novo_militar():
    with st.form("form_novo_militar_modal", clear_on_submit=True):
        num_policia_in = st.text_input("Nº Polícia / Matrícula com DV:", placeholder="Ex: 1337468").strip().replace("-", "").replace(".", "")
        posto_in = st.selectbox("Graduação:", ["SD AL", "SD", "CB", "3º SGT", "2º SGT", "1º SGT", "SUB TEN", "2º TEN", "1º TEN", "CAP", "MAJ", "TEN CEL"])
        nome_guerra_in = st.text_input("Nome de Guerra / Funcional:", placeholder="Ex: SILVA")
        nome_completo_in = st.text_input("Nome Completo:", placeholder="Ex: SILVA JUNIOR")
        unidade_in = st.text_input("Unidade (Ex: 35 CIA PM):", placeholder="Ex: 35 CIA PM").strip().upper()
        cidade_in = st.text_input("Cidade / Fração:", value="UBÁ", placeholder="Ex: UBÁ, VISCONDE DO RIO BRANCO...").strip().upper()
        
        st.markdown("<br>", unsafe_allow_html=True)
        btn_cad_mil = st.form_submit_button("💾 Salvar Militar", type="primary", width="stretch")
        
        if btn_cad_mil and num_policia_in and nome_guerra_in:
            num_limpo = str(num_policia_in).strip()
            ja_existe = any(str(m.get("num_policia", "")).strip() == num_limpo for m in st.session_state.get("lista_militares", []))
            
            if ja_existe:
                st.error("⚠️ Este Número de Polícia já está cadastrado no sistema!")
            else:
                m_id_novo = f"mili_{uuid.uuid4().hex[:6]}"
                nome_f_upper = str(nome_guerra_in).strip().upper()
                pg_abrev = padronizar_graduacao(posto_in)
                nome_comp_final = str(nome_completo_in).strip().upper() if nome_completo_in else f"{pg_abrev} {nome_f_upper}"
                cidade_final = cidade_in if cidade_in else "N/I"
                unidade_final = unidade_in if unidade_in else st.session_state.get("cfg_subunidade", "UNIDADE N/I")
                
                novo_m = {
                    "id": m_id_novo,
                    "num_policia": num_limpo,
                    "posto_grad": pg_abrev,
                    "nome_guerra": nome_f_upper,
                    "nome_completo": nome_comp_final,
                    "cidade": cidade_final,
                    "peso": PESOS_HIERARQUIA.get(pg_abrev, 99),
                    "unidade": unidade_final
                }
                
                st.session_state["lista_militares"].append(novo_m)
                st.session_state["lista_militares"] = remover_duplicados_militares(st.session_state["lista_militares"])
                salvar_militares_supabase([novo_m])
                st.success(f"✅ Militar {nome_f_upper} cadastrado e salvo no Supabase!")
                st.rerun()

def renderizar_grade_cards_4_colunas(lista_mils, sel_ids_set, modo_exclusao, prefixo_key):
    max_colunas = 4
    for i in range(0, len(lista_mils), max_colunas):
        grupo_4 = lista_mils[i:i + max_colunas]
        cols = st.columns(max_colunas)
        for idx_col, m in enumerate(grupo_4):
            m_id = m["id"]
            num_pol = m.get('num_policia', 'N/I')
            is_sel = m_id in sel_ids_set
            posto_abrev = padronizar_graduacao(m.get('posto_grad', 'SD'))
            nome_str = m.get('nome_guerra', 'MILITAR')
            nome_comp_str = m.get('nome_completo', f"{posto_abrev} {nome_str}")
            cidade_str = m.get('cidade', 'N/I')
            unidade_str = m.get('unidade', 'N/I')
            
            label_card = f"{posto_abrev} {nome_str}\n\nNº {num_pol}"
            
            if modo_exclusao and prefixo_key == "col_sel":
                tipo_btn = "primary"
            else:
                tipo_btn = "primary" if is_sel else "secondary"
                
            tooltip_texto = (
                f"🎖️ {nome_comp_str}\n"
                f"📌 Posto/Grad: {posto_abrev}\n"
                f"🔢 Matrícula: {num_pol}\n"
                f"🏢 Unidade: {unidade_str}\n"
                f"🏙️ Cidade: {cidade_str}"
            )

            with cols[idx_col]:
                if st.button(label_card, key=f"btn_m_{prefixo_key}_{m_id}", type=tipo_btn, width="stretch", help=tooltip_texto):
                    if modo_exclusao and prefixo_key == "col_sel":
                        excluir_militar_banco_e_memoria(m_id, num_pol)
                        st.rerun()
                    else:
                        if is_sel:
                            st.session_state["militares_selecionados_ids"].remove(m_id)
                        else:
                            st.session_state["militares_selecionados_ids"].append(m_id)
                        st.session_state["atualizar_quadro_passo5"] = True
                        st.rerun()

@st.fragment
def renderizar_fragmento_passo3():
    st.markdown("""
    <style>
    div[data-baseweb="tooltip"] {
        font-size: 13px !important;
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid #475569 !important;
        border-radius: 6px !important;
        padding: 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    militares = remover_duplicados_militares(st.session_state.get("lista_militares", []))
    st.session_state["lista_militares"] = militares

    c_uni, c_cid, c_busca = st.columns([1.5, 1.5, 2])
    
    with c_uni:
        unidades_unicas = sorted(list(set([str(m.get("unidade", "UNIDADE N/I")).upper() for m in militares if m.get("unidade")])))
        unidades_sel = st.multiselect(
            "🏢 Filtrar por Unidade(s):", 
            options=unidades_unicas,
            default=[],
            placeholder="Todas as Unidades",
            key="msel_unidade_filtro_p3_frag"
        )

    with c_cid:
        cidades_unicas = sorted(list(set([str(m.get("cidade", "N/I")).upper() for m in militares if m.get("cidade")])))
        cidades_sel = st.multiselect(
            "🏙️ Filtrar por Cidade(s) / Município(s):", 
            options=cidades_unicas,
            default=[],
            placeholder="Todas as Cidades",
            key="msel_cidade_filtro_p3_frag"
        )

    with c_busca:
        termo_busca = st.text_input(
            "🔍 Busca Global:", 
            placeholder="Nome, Matrícula com DV, Graduação...", 
            key="txt_busca_militar_p3_frag"
        ).strip().upper()

    col_t1, col_t2 = st.columns([1.8, 3.2])
    
    with col_t1:
        modo_exclusao = st.toggle("🚨 Trava de Exclusão (Habilitar Exclusão)", value=False, key="toggle_modo_exclusao_frag")
    with col_t2:
        if modo_exclusao:
            st.warning("⚠️ **TRAVA DESBLOQUEADA:** A exclusão é realizada **exclusivamente no Quadro da Direita (Selecionados)**. Clicar em qualquer card do quadro da direita irá excluí-lo individualmente ou use o botão '🗑️ Excluir Selecionados'.")
        else:
            st.info("🔒 **TRAVA ATIVA (SEGURANÇA):** Exclusões bloqueadas. Para excluir militares, habilite a trava ao lado e mova-os para o Quadro da Direita.")

    st.markdown("<br>", unsafe_allow_html=True)

    c_m1, c_m2, c_m3 = st.columns([1, 1, 1.2])
    with c_m1:
        if st.button("✔ Marcar Visíveis", width="stretch", key="btn_marcar_todos_frag"):
            st.session_state["militares_selecionados_ids"] = list(set(
                st.session_state.get("militares_selecionados_ids", []) + [m["id"] for m in st.session_state.get("militares_ativos_render", [])]
            ))
            st.session_state["atualizar_quadro_passo5"] = True
            st.rerun()
    with c_m2:
        if st.button("✖ Limpar Seleção", width="stretch", key="btn_desmarcar_todos_frag"):
            st.session_state["militares_selecionados_ids"] = []
            st.session_state["atualizar_quadro_passo5"] = True
            st.rerun()
    with c_m3:
        if modo_exclusao:
            if st.button("🗑️ Excluir Selecionados", type="primary", width="stretch", key="btn_excluir_lote_frag"):
                abrir_modal_excluir_lote()
        else:
            if st.button("🗑️ Excluir Selecionados", type="secondary", width="stretch", key="btn_excluir_lote_frag_blocked"):
                st.toast("🔒 Trava de Exclusão ativada! Habilite-a primeiro na chave acima.", icon="🔒")

    st.markdown("<br>", unsafe_allow_html=True)

    if not militares:
        st.info("💡 Nenhum militar cadastrado no momento. Importe a planilha ou recarregue do Supabase.")
        return

    militares_filtrados = militares

    if unidades_sel:
        militares_filtrados = [m for m in militares_filtrados if str(m.get("unidade")).upper() in unidades_sel]
        
    if cidades_sel:
        militares_filtrados = [m for m in militares_filtrados if str(m.get("cidade")).upper() in cidades_sel]

    if termo_busca:
        militares_filtrados = [
            m for m in militares_filtrados
            if termo_busca in m.get("nome_guerra", "").upper()
            or termo_busca in m.get("nome_completo", "").upper()
            or termo_busca in m.get("num_policia", "").upper()
            or termo_busca in padronizar_graduacao(m.get("posto_grad", "")).upper()
        ]

    st.session_state["militares_ativos_render"] = militares_filtrados
    sel_ids_set = set(st.session_state.get('militares_selecionados_ids', []))

    nao_selecionados = [m for m in militares_filtrados if m["id"] not in sel_ids_set]
    nao_selecionados_ord = sorted(nao_selecionados, key=lambda x: (PESOS_HIERARQUIA.get(padronizar_graduacao(x.get("posto_grad", "SD")), 99), x.get("nome_guerra", "")))

    selecionados = [m for m in militares_filtrados if m["id"] in sel_ids_set]
    selecionados_ord = sorted(selecionados, key=lambda x: (PESOS_HIERARQUIA.get(padronizar_graduacao(x.get("posto_grad", "SD")), 99), x.get("nome_guerra", "")))

    col_quadro_esq, col_quadro_dir = st.columns(2, gap="medium")

    with col_quadro_esq:
        st.markdown(f"##### ⚪ Efetivo Filtrado ({len(nao_selecionados_ord)}):")
        with st.container(height=420, border=True):
            if not nao_selecionados_ord:
                st.caption("Nenhum militar pendente de seleção.")
            else:
                renderizar_grade_cards_4_colunas(nao_selecionados_ord, sel_ids_set, modo_exclusao, prefixo_key="col_disp")

    with col_quadro_dir:
        st.markdown(f"##### 🟢 Selecionados para a Escala ({len(selecionados_ord)}):")
        with st.container(height=420, border=True):
            if not selecionados_ord:
                st.caption("Clique nos cards do quadro ao lado para mover os militares para este quadro.")
            else:
                renderizar_grade_cards_4_colunas(selecionados_ord, sel_ids_set, modo_exclusao, prefixo_key="col_sel")

    # =========================================================================
    # PAINEL DE LANÇAMENTO DE AFASTAMENTOS E DIAS NEUTROS
    # =========================================================================
    st.divider()
    if "afastamentos_militares" not in st.session_state:
        st.session_state["afastamentos_militares"] = []

    with st.expander("🏖️ Lançamento de Afastamentos & Dias Neutros (Férias, LM, Atestados)", expanded=False):
        st.caption("Cadastre afastamentos regulamentares para abater a meta mensal proporcional no Quadro (Passo 5) e Banco de Horas (Passo 7).")
        
        mils_ordenados_afast = sorted(militares, key=lambda x: (
            PESOS_HIERARQUIA.get(padronizar_graduacao(x.get("posto_grad", "SD")), 99),
            x.get("nome_guerra", "")
        ))
        
        mapa_select_mils_afast = {
            f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')} ({m.get('num_policia', '')})": str(m["id"]) 
            for m in mils_ordenados_afast
        }

        with st.form("form_lancar_afastamento_p3"):
            c_af1, c_af2, c_af3, c_af4 = st.columns([3, 2, 2, 2])
            
            with c_af1:
                mil_sel_label = st.selectbox("Militar:", list(mapa_select_mils_afast.keys()) if mapa_select_mils_afast else ["Nenhum militar cadastrado"])
            with c_af2:
                tipo_afastamento = st.selectbox(
                    "Tipo de Afastamento:",
                    [
                        "FE (Férias Regulamentares)", 
                        "LM (Licença Médica)", 
                        "ATE (Atestado Médico)", 
                        "LUT (Luto / Falecimento)", 
                        "NUP (Núpcias / Casamento)", 
                        "DN (Dia Neutro Institucional)", 
                        "DNT (Dia Neutro Trabalhado)"
                    ]
                )
            with c_af3:
                dt_inicio = st.date_input("Data Início:", datetime.date.today())
            with c_af4:
                dt_fim = st.date_input("Data Fim:", datetime.date.today())

            obs_afast = st.text_input("Observação / Publicação BG / Nota do Comando:")

            btn_salvar_afast = st.form_submit_button("📥 Creditar Afastamento / Dias Neutros", type="primary", width="stretch")

            if btn_salvar_afast and mapa_select_mils_afast:
                if dt_fim < dt_inicio:
                    st.error("🚨 A Data Fim não pode ser anterior à Data Início!")
                else:
                    sigla_codigo = tipo_afastamento.split()[0]
                    m_id_alvo = mapa_select_mils_afast[mil_sel_label]
                    
                    novo_afast = {
                        "id": uuid.uuid4().hex[:8],
                        "id_militar": m_id_alvo,
                        "nome_militar": mil_sel_label,
                        "sigla": sigla_codigo,
                        "tipo_extenso": tipo_afastamento,
                        "dt_inicio": dt_inicio.strftime("%d/%m/%Y"),
                        "dt_fim": dt_fim.strftime("%d/%m/%Y"),
                        "obs": obs_afast
                    }
                    
                    st.session_state["afastamentos_militares"].append(novo_afast)
                    
                    # Preenchimento automático na matriz de lançamento do Quadro (Passo 5)
                    grade = st.session_state.get("grade_escala_lancamentos", {})
                    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
                    
                    dt_atual = dt_inicio
                    while dt_atual <= dt_fim:
                        ano_c = dt_atual.year
                        mes_c = dt_atual.month
                        dia_c = dt_atual.day
                        
                        for pair in chaves_quadro:
                            if isinstance(pair, (tuple, list)) and str(pair[0]) == str(m_id_alvo):
                                eq_nome = pair[1]
                                chave_celula = f"{m_id_alvo}_{eq_nome}_{ano_c}_{mes_c:02d}_{dia_c:02d}"
                                grade[chave_celula] = sigla_codigo

                        dt_atual += datetime.timedelta(days=1)

                    st.session_state["grade_escala_lancamentos"] = grade
                    st.toast(f"✅ Afastamento ({sigla_codigo}) registrado para {mil_sel_label}!", icon="🎉")
                    st.rerun()

        if st.session_state["afastamentos_militares"]:
            st.markdown("##### 📋 Afastamentos Cadastrados na Sessão:")
            df_afast = pd.DataFrame(st.session_state["afastamentos_militares"])
            df_afast["Excluir"] = False
            
            df_visual = df_afast[["nome_militar", "sigla", "dt_inicio", "dt_fim", "obs", "Excluir"]]
            
            df_edit_afast = st.data_editor(
                df_visual,
                column_config={
                    "nome_militar": st.column_config.TextColumn("Militar", disabled=True),
                    "sigla": st.column_config.TextColumn("Código", disabled=True),
                    "dt_inicio": st.column_config.TextColumn("Início", disabled=True),
                    "dt_fim": st.column_config.TextColumn("Fim", disabled=True),
                    "obs": st.column_config.TextColumn("Observação", disabled=True),
                    "Excluir": st.column_config.CheckboxColumn("🗑️ Remover", default=False)
                },
                hide_index=True,
                width="stretch",
                key="editor_remover_afastamentos_p3"
            )

            if any(df_edit_afast["Excluir"]):
                indices_manter = [i for i in range(len(df_edit_afast)) if not df_edit_afast.iloc[i]["Excluir"]]
                st.session_state["afastamentos_militares"] = [st.session_state["afastamentos_militares"][idx] for idx in indices_manter]
                st.toast("🗑️ Afastamento removido!", icon="✅")
                st.rerun()

def renderizar_passo3():
    if "lista_militares" not in st.session_state or not st.session_state["lista_militares"]:
        m_banco = carregar_militares_supabase()
        if m_banco:
            m_banco_unico = remover_duplicados_militares(m_banco)
            for m_b in m_banco_unico:
                m_b["posto_grad"] = padronizar_graduacao(m_b.get("posto_grad", "SD"))
                m_b["peso"] = PESOS_HIERARQUIA.get(m_b["posto_grad"], 99)
                if not m_b.get("cidade"):
                    m_b["cidade"] = extrair_cidade_planilha(m_b)
                if not m_b.get("unidade"):
                    m_b["unidade"] = extrair_unidade_planilha(m_b)
            st.session_state["lista_militares"] = m_banco_unico

    exp3 = st.expander("📌 PASSO 3: Gestão do Efetivo, Inserção e Seleção de Militares", expanded=True)
    with exp3:
        c_b1, c_b2, c_b3 = st.columns([1.5, 1.5, 1])
        with c_b1:
            if st.button("📥 Carregar Planilha", width="stretch"):
                abrir_modal_upload_planilha()
        with c_b2:
            if st.button("🔄 Recarregar Banco (Supabase)", width="stretch"):
                m_banco = carregar_militares_supabase()
                if m_banco:
                    m_banco_unico = remover_duplicados_militares(m_banco)
                    for m_b in m_banco_unico:
                        m_b["posto_grad"] = padronizar_graduacao(m_b.get("posto_grad", "SD"))
                        m_b["peso"] = PESOS_HIERARQUIA.get(m_b["posto_grad"], 99)
                        if not m_b.get("cidade"):
                            m_b["cidade"] = extrair_cidade_planilha(m_b)
                        if not m_b.get("unidade"):
                            m_b["unidade"] = extrair_unidade_planilha(m_b)
                    st.session_state["lista_militares"] = m_banco_unico
                    st.success(f"✅ {len(m_banco_unico)} militar(es) recarregado(s) do Supabase!")
                    st.rerun()
                else:
                    st.warning("Nenhum registro encontrado no Supabase.")
        with c_b3:
            if st.button("➕ Militar", type="primary", width="stretch"):
                abrir_modal_novo_militar()

        st.divider()
        renderizar_fragmento_passo3()