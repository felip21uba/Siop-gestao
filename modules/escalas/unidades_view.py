import streamlit as st
import pandas as pd
import io
from core.database import supabase, carregar_militares_supabase


def carregar_unidades_cadastradas() -> list[dict]:
    """Busca unidades salvas na tabela unidades_config. Se estiver vazia, gera fallback dinâmico."""
    unidades = []
    if supabase:
        try:
            res = supabase.table("unidades_config").select("*").order("batalhao", desc=False).execute()
            unidades = res.data or []
        except Exception:
            unidades = []

    # FALLBACK AUTOMÁTICO: Se o banco estiver zerado, extrai unidades dos militares/usuários
    if not unidades:
        militares = carregar_militares_supabase() or []
        unidades_set = set()
        for m in militares:
            unid_m = str(m.get("unidade") or m.get("nome_unidade") or "").strip().upper()
            if unid_m and unid_m != "NONE":
                unidades_set.add(unid_m)

        for idx, u_nome in enumerate(sorted(list(unidades_set))):
            unidades.append({
                "id": str(idx),
                "batalhao": u_nome,
                "companhia": "SEÇÃO / CIA",
                "pelotao": "N/A",
                "municipio": "UBÁ",
                "url_brasao": None
            })

    return unidades


def salvar_unidade_manual(batalhao: str, companhia: str, pelotao: str, municipio: str, url_brasao: str) -> bool:
    """Insere ou atualiza uma unidade na tabela unidades_config."""
    if not supabase:
        return False
    payload = {
        "batalhao": batalhao.strip().upper(),
        "companhia": companhia.strip().upper(),
        "pelotao": pelotao.strip().upper() if pelotao else "N/A",
        "municipio": municipio.strip().upper(),
        "url_brasao": url_brasao.strip() if url_brasao else None
    }
    try:
        supabase.table("unidades_config").upsert(payload, on_conflict="batalhao,companhia,pelotao,municipio").execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar unidade no Supabase: {e}")
        return False


def processar_planilha_unidades(file_bytes, filename: str) -> int:
    """Lê planilha Excel/CSV contendo Batalhao, Companhia, Pelotao, Municipio e Url_Brasao."""
    if not supabase or not file_bytes:
        return 0
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))

        df.columns = [str(c).strip().lower() for c in df.columns]

        col_bat = next((c for c in df.columns if "bat" in c or "unidade" in c), "batalhao")
        col_cia = next((c for c in df.columns if "cia" in c or "comp" in c), "companhia")
        col_pel = next((c for c in df.columns if "pel" in c), "pelotao")
        col_mun = next((c for c in df.columns if "mun" in c or "cidade" in c or "sede" in c), "municipio")
        col_brasao = next((c for c in df.columns if "bras" in c or "url" in c or "img" in c), "url_brasao")

        sucessos = 0
        for _, row in df.iterrows():
            bat_v = str(row.get(col_bat, "")).strip().upper()
            cia_v = str(row.get(col_cia, "")).strip().upper()
            pel_v = str(row.get(col_pel, "N/A")).strip().upper()
            mun_v = str(row.get(col_mun, "")).strip().upper()
            bras_v = str(row.get(col_brasao, "")).strip()

            if bat_v and cia_v and mun_v:
                payload = {
                    "batalhao": bat_v,
                    "companhia": cia_v,
                    "pelotao": pel_v if pel_v and pel_v != "NAN" else "N/A",
                    "municipio": mun_v,
                    "url_brasao": bras_v if bras_v and bras_v != "NAN" else None
                }
                supabase.table("unidades_config").upsert(payload, on_conflict="batalhao,companhia,pelotao,municipio").execute()
                sucessos += 1

        st.cache_data.clear()
        return sucessos
    except Exception as e:
        st.error(f"Erro ao processar planilha: {e}")
        return 0


def renderizar_seletor_programador(usr_logado: dict):
    """Exibe o seletor de modo de visualização para Programadores/Admins."""
    cargo = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil = str(usr_logado.get("nivel_acesso") or usr_logado.get("perfil") or "").upper()

    eh_programador = any(p in cargo or p in perfil for p in ["PROGRAMADOR", "DESENVOLVEDOR", "ADMIN"])

    if eh_programador:
        unidades_banco = carregar_unidades_cadastradas()

        lista_opcoes = ["🌐 VISÃO GLOBAL (TODAS AS UNIDADES)"]
        for u in unidades_banco:
            rotulo = f"{u['batalhao']} / {u['companhia']} - {u['municipio']}"
            if rotulo not in lista_opcoes:
                lista_opcoes.append(rotulo)

        with st.container(border=True):
            st.markdown("##### 🛠️ Seletor de Visualização (Modo Programador)")
            unidade_selecionada = st.selectbox("Selecione a Unidade para Filtrar/Leitura de Dados:", options=lista_opcoes, key="sb_modo_programador_unidade")
            st.session_state["unidade_visualizacao_ativa"] = unidade_selecionada


def renderizar_modulo_gestao_unidades(usr_logado: dict):
    """Renderiza a interface principal de cadastro de Unidades."""
    st.markdown("### 🏛️ Cadastro de Novas Unidades / Batalhões (Multi-Tenant)")
    st.caption("Cadastre manualmente ou importe uma planilha com a estrutura de Batalhões, Companhias, Pelotões e Municípios.")

    renderizar_seletor_programador(usr_logado)

    tab_manual, tab_planilha, tab_lista = st.tabs([
        "📝 Inclusão Manual",
        "📊 Importar Planilha em Lote",
        "📋 Unidades Cadastradas"
    ])

    # 1. FORMULÁRIO MANUAL COM MUNICÍPIO
    with tab_manual:
        with st.container(border=True):
            st.markdown("##### 🏛️️ Cadastro Manual de Unidade")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                batalhao_input = st.text_input("Nome do Batalhão / Unidade:", placeholder="Ex: 47º BPM / 4ª RPM", key="txt_bat_man").strip().upper()
                companhia_input = st.text_input("Companhia / Subunidade Principal:", placeholder="Ex: 75ª CIA PM", key="txt_cia_man").strip().upper()
                pelotao_input = st.text_input("Pelotão / Subseção (Opcional):", placeholder="Ex: 1º PELOTÃO", key="txt_pel_man").strip().upper()

            with c_m2 := col_m2:
                municipio_input = st.text_input("Município / Sede (OBRIGATÓRIO):", placeholder="Ex: CARANGOLA", key="txt_mun_man").strip().upper()
                brasao_url = st.text_input("URL do Brasão da Unidade (Opcional):", placeholder="https://link-da-imagem.png", key="txt_brasao_man").strip()

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🏛️ Cadastrar Nova Unidade no SIOP", type="primary", width="stretch", key="btn_salvar_unid_man"):
                if not batalhao_input or not companhia_input or not municipio_input:
                    st.error("⚠️ Preencha obrigatoriamente Batalhão, Companhia e Município.")
                else:
                    if salvar_unidade_manual(batalhao_input, companhia_input, pelotao_input, municipio_input, brasao_url):
                        st.success(f"✅ Unidade **{batalhao_input} / {companhia_input} ({municipio_input})** salva no Supabase!")
                        st.rerun()

    # 2. IMPORTAÇÃO POR PLANILHA
    with tab_planilha:
        with st.container(border=True):
            st.markdown("##### 📊 Leitura de Planilha (Excel ou CSV)")
            st.caption("A planilha deve conter as colunas: **Batalhao, Companhia, Pelotao, Municipio, Url_Brasao**.")
            
            file_upl = st.file_uploader("Selecione o arquivo Excel (.xlsx) ou CSV:", type=["xlsx", "xls", "csv"], key="upl_planilha_unidades")

            if file_upl:
                if st.button("⚡ Processar e Cadastrar Unidades em Lote", type="primary", width="stretch", key="btn_proc_lote_unid"):
                    with st.spinner("Gravando no banco..."):
                        qtd = processar_planilha_unidades(file_upl.getvalue(), file_upl.name)
                        if qtd > 0:
                            st.success(f"🎉 {qtd} unidade(s) importada(s) com sucesso!")
                            st.rerun()
                        else:
                            st.error("Nenhuma unidade válida foi importada. Verifique as colunas da planilha.")

    # 3. TABELA DE EXIBIÇÃO
    with tab_lista:
        unidades_cad = carregar_unidades_cadastradas()
        if unidades_cad:
            df_u = pd.DataFrame(unidades_cad)
            st.markdown(f"##### 📋 Unidades no Sistema ({len(unidades_cad)} registradas)")
            st.dataframe(
                df_u[["batalhao", "companhia", "pelotao", "municipio", "url_brasao"]],
                column_config={
                    "batalhao": "Batalhão / Unidade",
                    "companhia": "Companhia",
                    "pelotao": "Pelotão",
                    "municipio": "Município / Sede",
                    "url_brasao": st.column_config.LinkColumn("URL Brasão")
                },
                width="stretch",
                hide_index=True
            )
        else:
            st.info("Nenhuma unidade cadastrada.")