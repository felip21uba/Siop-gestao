import streamlit as st
import re
import unicodedata
from core.database import supabase, salvar_militares_supabase, carregar_militares_supabase
from modules.escalas.passos.passo3_modais import (
    abrir_modal_editar_militar,
    abrir_modal_excluir_lote,
    abrir_modal_upload_planilha,
    abrir_modal_novo_militar
)
from modules.escalas.passos.passo3_afastamentos import renderizar_painel_afastamentos

PESOS_HIERARQUIA = {
    "CEL": 1, "TEN CEL": 2, "MAJ": 3, "CAP": 4, "1º TEN": 5, "2º TEN": 6, "ASP": 7,
    "CAD": 8, "AL OF": 9, "SUB TEN": 10, "1º SGT": 11, "2º SGT": 12, "3º SGT": 13,
    "CB": 14, "SD": 15, "SD AL": 16
}

def padronizar_graduacao(texto):
    """Padroniza postos e graduações da PMMG sem confundir sargentos com soldados."""
    if texto is None or str(texto).strip().upper() in ["NONE", "NAN", "NULL", "<NA>", ""]:
        return "SD"

    t_raw = str(texto).strip().upper()
    t_pre = re.sub(r"([123])\s*[º°ª]", r"\1 ", t_raw)
    t_norm = unicodedata.normalize("NFKD", t_pre).encode("ASCII", "ignore").decode("utf-8").upper().strip()
    t_clean = re.sub(r"[º°ª.\-]", " ", t_norm)
    t_clean = re.sub(r"\s+", " ", t_clean).strip()

    if (
        re.search(r"(^|\s)1\s*(SGT|SARGENTO|SARG|SARGTO)(\s|$)", t_clean)
        or re.search(r"(SGT|SARGENTO|SARG|SARGTO)\s*1(\s|$)", t_clean)
        or "PRIMEIRO SARGENTO" in t_clean
    ):
        return "1º SGT"

    if (
        re.search(r"(^|\s)2\s*(SGT|SARGENTO|SARG|SARGTO)(\s|$)", t_clean)
        or re.search(r"(SGT|SARGENTO|SARG|SARGTO)\s*2(\s|$)", t_clean)
        or "SEGUNDO SARGENTO" in t_clean
    ):
        return "2º SGT"

    if (
        re.search(r"(^|\s)3\s*(SGT|SARGENTO|SARG|SARGTO)(\s|$)", t_clean)
        or re.search(r"(SGT|SARGENTO|SARG|SARGTO)\s*3(\s|$)", t_clean)
        or "TERCEIRO SARGENTO" in t_clean
    ):
        return "3º SGT"

    if re.search(r"1\s*SGT", t_clean): return "1º SGT"
    if re.search(r"2\s*SGT", t_clean): return "2º SGT"
    if re.search(r"3\s*SGT", t_clean): return "3º SGT"

    if ("TEN" in t_clean and "CEL" in t_clean) or ("CORONEL" in t_clean and "TEN" in t_clean) or t_clean == "TC":
        return "TEN CEL"
    if "CEL" in t_clean or "CORONEL" in t_clean: return "CEL"
    if "MAJ" in t_clean or "MAJOR" in t_clean: return "MAJ"
    if "CAP" in t_clean or "CAPITAO" in t_clean: return "CAP"

    if "SUB TEN" in t_clean or "SUBTENENTE" in t_clean or t_clean in ("SUB", "ST"):
        return "SUB TEN"

    if ("1" in t_clean and ("TEN" in t_clean or "TENENTE" in t_clean)) or "PRIMEIRO TENENTE" in t_clean:
        return "1º TEN"
    if ("2" in t_clean and ("TEN" in t_clean or "TENENTE" in t_clean)) or "SEGUNDO TENENTE" in t_clean:
        return "2º TEN"
    if "TENENTE" in t_clean or re.search(r"(^|\s)TEN(\s|$)", t_clean):
        if "1" in t_clean or "PRIMEIRO" in t_clean: return "1º TEN"
        if "2" in t_clean or "SEGUNDO" in t_clean: return "2º TEN"
        return "2º TEN"

    if "ASP" in t_clean or "ASPIRANTE" in t_clean: return "ASP"
    if "CAD" in t_clean or "CADETE" in t_clean: return "CAD"
    if "AL OF" in t_clean or "ALUNO OFICIAL" in t_clean: return "AL OF"
    if "SD AL" in t_clean or "AL SD" in t_clean or "ALUNO SD" in t_clean or "ALUNO SOLDADO" in t_clean:
        return "SD AL"

    if "CABO" in t_clean or t_clean == "CB" or " CB " in f" {t_clean} ": return "CB"
    if "SOLDADO" in t_clean or t_clean == "SD" or " SD " in f" {t_clean} ": return "SD"

    return t_raw

def extrair_posto_grad_planilha(row):
    for k, v in row.items():
        k_norm = unicodedata.normalize('NFKD', str(k)).encode('ASCII', 'ignore').decode('utf-8').upper().strip()
        if k_norm in ["POSTO/GRADUACAO", "POSTO / GRADUACAO", "POSTO_GRADUACAO", "POSTO_GRAD", "POSTO GRADUACAO", "GRADUACAO", "POSTO", "P/G", "GRAD"]:
            if v and str(v).strip().upper() not in ["NONE", "NAN", "NULL", "<NA>", ""]:
                return str(v).strip().upper()
    if hasattr(row, 'iloc') and len(row) > 2:
        val_col_c = row.iloc[2]
        if val_col_c and str(val_col_c).strip().upper() not in ["NONE", "NAN", "NULL", "<NA>", ""]:
            return str(val_col_c).strip().upper()
    return "SD"

def extrair_cidade_planilha(row):
    for k, v in row.items():
        k_norm = unicodedata.normalize('NFKD', str(k)).encode('ASCII', 'ignore').decode('utf-8').upper().strip()
        if "MUNICIPIO" in k_norm or "CIDADE" in k_norm or "LOCALIDADE" in k_norm:
            if v and str(v).strip().upper() not in ["NONE", "NAN", "NULL", "<NA>", ""]:
                return str(v).strip().upper()
    val = row.get("NOME MUNICIPIO", row.get("NOME_MUNICIPIO", row.get("MUNICIPIO", row.get("CIDADE", ""))))
    val_str = str(val).strip().upper()
    return val_str if val_str and val_str not in ["NONE", "NAN", "NULL", "<NA>", ""] else "N/I"

def extrair_unidade_planilha(row):
    for k, v in row.items():
        k_norm = unicodedata.normalize('NFKD', str(k)).encode('ASCII', 'ignore').decode('utf-8').upper().strip()
        if "UNIDADE" in k_norm or "SUBUNIDADE" in k_norm or "OM" in k_norm:
            if v and str(v).strip().upper() not in ["NONE", "NAN", "NULL", "<NA>", ""]:
                return str(v).strip().upper()
    val = row.get("NOME UNIDADE", row.get("NOME_UNIDADE", row.get("UNIDADE", "")))
    val_str = str(val).strip().upper()
    return val_str if val_str and val_str not in ["NONE", "NAN", "NULL", "<NA>", ""] else "UNIDADE N/I"

def remover_duplicados_militares(lista):
    vistos = set()
    lista_unica = []
    for m in lista:
        num = str(m.get("num_policia", "")).strip().upper()
        if num and num not in vistos and num != "NAN":
            vistos.add(num)
            lista_unica.append(m)
    return lista_unica

def atualizar_militar_banco_e_memoria(militar_editado):
    m_id = str(militar_editado.get("id")).strip()
    num_pol = str(militar_editado.get("num_policia")).strip().upper()
    lista = st.session_state.get("lista_militares", [])
    for idx, m in enumerate(lista):
        if str(m.get("id")).strip() == m_id or str(m.get("num_policia")).strip().upper() == num_pol:
            lista[idx] = militar_editado
            break
    st.session_state["lista_militares"] = lista
    salvar_militares_supabase([militar_editado])

def excluir_militar_banco_e_memoria(m_id, num_policia):
    m_id_str, num_pol_str = str(m_id).strip(), str(num_policia).strip().upper()
    st.session_state["lista_militares"] = [m for m in st.session_state.get("lista_militares", []) if str(m.get("id")).strip() != m_id_str and str(m.get("num_policia")).strip().upper() != num_pol_str]
    st.session_state["militares_selecionados_ids"] = [i for i in st.session_state.get("militares_selecionados_ids", []) if str(i).strip() != m_id_str]
    if supabase:
        try: supabase.table("militares").delete().eq("num_policia", num_pol_str).execute()
        except Exception:
            try: supabase.table("militares").delete().eq("id", m_id_str).execute()
            except Exception: pass
        st.cache_data.clear()

def excluir_lote_banco_e_memoria(mils_para_excluir):
    ids_excluir = set(str(m.get("id")).strip() for m in mils_para_excluir)
    nums_excluir = set(str(m.get("num_policia")).strip().upper() for m in mils_para_excluir if m.get("num_policia"))
    st.session_state["lista_militares"] = [m for m in st.session_state.get("lista_militares", []) if str(m.get("id")).strip() not in ids_excluir and str(m.get("num_policia")).strip().upper() not in nums_excluir]
    st.session_state["militares_selecionados_ids"] = [m_id for m_id in st.session_state.get("militares_selecionados_ids", []) if str(m_id).strip() not in ids_excluir]
    if supabase:
        if nums_excluir:
            try: supabase.table("militares").delete().in_("num_policia", list(nums_excluir)).execute()
            except Exception: pass
        if ids_excluir:
            try: supabase.table("militares").delete().in_("id", list(ids_excluir)).execute()
            except Exception: pass
        st.cache_data.clear()

def tratar_num_policia_unificado(row):
    num_principal = str(row.get("NUMERO", row.get("NUMERO_POLICIA", row.get("MATRICULA", "")))).strip()
    digito = str(row.get("DV", row.get("DIGITO", row.get("VERIFICADOR", "")))).strip()
    if num_principal.endswith(".0"): num_principal = num_principal[:-2]
    if digito.endswith(".0"): digito = digito[:-2]
    num_clean, dv_clean = re.sub(r'\D', '', num_principal), re.sub(r'\D', '', digito)
    if not num_clean: return ""
    if dv_clean and dv_clean.upper() != "NAN":
        if "-" in num_principal and num_principal.endswith(f"-{dv_clean}"): return num_clean
        if len(num_clean) <= 5: return f"{num_clean}{dv_clean}"
        if len(num_clean) >= 6 and num_clean.endswith(dv_clean): return num_clean
        return f"{num_clean}{dv_clean}"
    return num_clean

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
            cidade_str, unidade_str = m.get('cidade', 'N/I'), m.get('unidade', 'N/I')
            
            label_card = f"{posto_abrev} {nome_str}\n\nNº {num_pol}"
            tipo_btn = "primary" if (modo_exclusao and prefixo_key == "col_sel") or is_sel else "secondary"
            tooltip_texto = f"🎖️ {nome_comp_str}\n📌 Posto/Grad: {posto_abrev}\n🔢 Matrícula: {num_pol}\n🏢 Unidade: {unidade_str}\n🏙️ Cidade: {cidade_str}"

            with cols[idx_col]:
                c_card1, c_card2 = st.columns([3.2, 1])
                with c_card1:
                    if st.button(label_card, key=f"btn_m_{prefixo_key}_{m_id}", type=tipo_btn, use_container_width=True, help=tooltip_texto):
                        if modo_exclusao and prefixo_key == "col_sel":
                            excluir_militar_banco_e_memoria(m_id, num_pol)
                            st.rerun()
                        else:
                            if is_sel: st.session_state["militares_selecionados_ids"].remove(m_id)
                            else: st.session_state["militares_selecionados_ids"].append(m_id)
                            st.session_state["atualizar_quadro_passo5"] = True
                            st.rerun()
                with c_card2:
                    if st.button("✏️", key=f"btn_edit_m_{prefixo_key}_{m_id}", help="Editar dados do militar"):
                        abrir_modal_editar_militar(m, padronizar_graduacao, atualizar_militar_banco_e_memoria, PESOS_HIERARQUIA)

@st.fragment
def renderizar_fragmento_passo3():
    militares = remover_duplicados_militares(st.session_state.get("lista_militares", []))
    st.session_state["lista_militares"] = militares

    c_uni, c_cid, c_busca = st.columns([1.5, 1.5, 2])
    with c_uni:
        unidades_unicas = sorted(list(set([str(m.get("unidade", "UNIDADE N/I")).upper() for m in militares if m.get("unidade")])))
        unidades_sel = st.multiselect("🏢 Filtrar por Unidade(s):", options=unidades_unicas, default=[], key="msel_unidade_filtro_p3_frag")
    with c_cid:
        cidades_unicas = sorted(list(set([str(m.get("cidade", "N/I")).upper() for m in militares if m.get("cidade")])))
        cidades_sel = st.multiselect("🏙️ Filtrar por Cidade(s):", options=cidades_unicas, default=[], key="msel_cidade_filtro_p3_frag")
    with c_busca:
        termo_busca = st.text_input("🔍 Busca Global:", key="txt_busca_militar_p3_frag").strip().upper()

    col_t1, col_t2 = st.columns([1.8, 3.2])
    with col_t1: modo_exclusao = st.toggle("🚨 Trava de Exclusão (Habilitar Exclusão)", value=False, key="toggle_modo_exclusao_frag")
    with col_t2:
        if modo_exclusao: st.warning("⚠️ **TRAVA DESBLOQUEADA:** Exclusão ativa no Quadro da Direita.")
        else: st.info("🔒 **TRAVA ATIVA (SEGURANÇA):** Exclusões bloqueadas.")

    st.markdown("<br>", unsafe_allow_html=True)

    c_m1, c_m2, c_m3 = st.columns([1, 1, 1.2])
    with c_m1:
        if st.button("✔ Marcar Visíveis", use_container_width=True, key="btn_marcar_todos_frag"):
            st.session_state["militares_selecionados_ids"] = list(set(st.session_state.get("militares_selecionados_ids", []) + [m["id"] for m in st.session_state.get("militares_ativos_render", [])]))
            st.session_state["atualizar_quadro_passo5"] = True
            st.rerun()
    with c_m2:
        if st.button("✖ Limpar Seleção", use_container_width=True, key="btn_desmarcar_todos_frag"):
            st.session_state["militares_selecionados_ids"] = []
            st.session_state["atualizar_quadro_passo5"] = True
            st.rerun()
    with c_m3:
        if modo_exclusao:
            if st.button("🗑️ Excluir Selecionados", type="primary", use_container_width=True, key="btn_excluir_lote_frag"):
                abrir_modal_excluir_lote(excluir_lote_banco_e_memoria)

    if not militares:
        st.info("💡 Nenhum militar cadastrado no momento.")
        return

    militares_filtrados = militares
    if unidades_sel: militares_filtrados = [m for m in militares_filtrados if str(m.get("unidade")).upper() in unidades_sel]
    if cidades_sel: militares_filtrados = [m for m in militares_filtrados if str(m.get("cidade")).upper() in cidades_sel]
    if termo_busca:
        militares_filtrados = [m for m in militares_filtrados if termo_busca in m.get("nome_guerra", "").upper() or termo_busca in m.get("nome_completo", "").upper() or termo_busca in m.get("num_policia", "").upper() or termo_busca in padronizar_graduacao(m.get("posto_grad", "")).upper()]

    st.session_state["militares_ativos_render"] = militares_filtrados
    sel_ids_set = set(st.session_state.get('militares_selecionados_ids', []))

    nao_selecionados_ord = sorted([m for m in militares_filtrados if m["id"] not in sel_ids_set], key=lambda x: (PESOS_HIERARQUIA.get(padronizar_graduacao(x.get("posto_grad", "SD")), 99), x.get("nome_guerra", "")))
    selecionados_ord = sorted([m for m in militares_filtrados if m["id"] in sel_ids_set], key=lambda x: (PESOS_HIERARQUIA.get(padronizar_graduacao(x.get("posto_grad", "SD")), 99), x.get("nome_guerra", "")))

    col_quadro_esq, col_quadro_dir = st.columns(2, gap="medium")
    with col_quadro_esq:
        st.markdown(f"##### ⚪ Efetivo Filtrado ({len(nao_selecionados_ord)}):")
        with st.container(height=420, border=True):
            if not nao_selecionados_ord: st.caption("Nenhum militar pendente de seleção.")
            else: renderizar_grade_cards_4_colunas(nao_selecionados_ord, sel_ids_set, modo_exclusao, prefixo_key="col_disp")

    with col_quadro_dir:
        st.markdown(f"##### 🟢 Selecionados para a Escala ({len(selecionados_ord)}):")
        with st.container(height=420, border=True):
            if not selecionados_ord: st.caption("Clique nos cards para mover para este quadro.")
            else: renderizar_grade_cards_4_colunas(selecionados_ord, sel_ids_set, modo_exclusao, prefixo_key="col_sel")

    st.divider()
    renderizar_painel_afastamentos(militares, padronizar_graduacao, PESOS_HIERARQUIA)

def renderizar_passo3():
    if not st.session_state.get("militares_carregados", False):
        m_banco = carregar_militares_supabase()
        if m_banco:
            m_banco_unico = remover_duplicados_militares(m_banco)
            for m_b in m_banco_unico:
                m_b["posto_grad"] = padronizar_graduacao(m_b.get("posto_grad", "SD"))
                m_b["peso"] = PESOS_HIERARQUIA.get(m_b["posto_grad"], 99)
                if not m_b.get("cidade"): m_b["cidade"] = extrair_cidade_planilha(m_b)
                if not m_b.get("unidade"): m_b["unidade"] = extrair_unidade_planilha(m_b)
            st.session_state["lista_militares"] = m_banco_unico
        else:
            if "lista_militares" not in st.session_state: st.session_state["lista_militares"] = []
        st.session_state["militares_carregados"] = True

    exp3 = st.expander("📌 PASSO 3: Gestão do Efetivo, Inserção e Seleção de Militares", expanded=True)
    with exp3:
        c_b1, c_b2, c_b3 = st.columns([1.5, 1.5, 1])
        with c_b1:
            if st.button("📥 Carregar Planilha", use_container_width=True):
                funcs_dict = {
                    "padronizar_graduacao": padronizar_graduacao,
                    "tratar_num_policia": tratar_num_policia_unificado,
                    "extrair_posto_grad": extrair_posto_grad_planilha,
                    "extrair_cidade": extrair_cidade_planilha,
                    "extrair_unidade": extrair_unidade_planilha,
                    "remover_duplicados": remover_duplicados_militares,
                    "pesos": PESOS_HIERARQUIA
                }
                abrir_modal_upload_planilha(funcs_dict)
        with c_b2:
            if st.button("🔄 Recarregar Banco (Supabase)", use_container_width=True):
                m_banco = carregar_militares_supabase()
                if m_banco:
                    m_banco_unico = remover_duplicados_militares(m_banco)
                    for m_b in m_banco_unico:
                        m_b["posto_grad"] = padronizar_graduacao(m_b.get("posto_grad", "SD"))
                        m_b["peso"] = PESOS_HIERARQUIA.get(m_b["posto_grad"], 99)
                        if not m_b.get("cidade"): m_b["cidade"] = extrair_cidade_planilha(m_b)
                        if not m_b.get("unidade"): m_b["unidade"] = extrair_unidade_planilha(m_b)
                    st.session_state["lista_militares"] = m_banco_unico
                    st.session_state["militares_carregados"] = True
                    st.success(f"✅ {len(m_banco_unico)} militar(es) recarregado(s) do Supabase!")
                    st.rerun()
        with c_b3:
            if st.button("➕ Militar", type="primary", use_container_width=True):
                abrir_modal_novo_militar(padronizar_graduacao, remover_duplicados_militares, PESOS_HIERARQUIA)

        st.divider()
        renderizar_fragmento_passo3()