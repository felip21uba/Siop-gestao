"""
==============================================================================
Módulo do Passo 1 - Unidade Operacional, Mês/Ano & Seleção da Escala
Fonte Única de Verdade para definição da Cia/Fração, Mês e Ano de Operação.
Salva/Carrega o rascunho no Supabase mantendo isolamento rígido entre Companhias.
==============================================================================
"""

import streamlit as st
import datetime
from core.database import (
    supabase, 
    carregar_militares_supabase, 
    obter_unidades_config_supabase
)


def obter_cias_disponiveis_unidade():
    """Retorna a lotação do militar logado e a lista de Cias permitidas no Batalhão."""
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    lotacao_militar = str(
        usr_dados.get("unidade")
        or usr_dados.get("lotacao")
        or usr_dados.get("subunidade")
        or "111ª CIA PM"
    ).strip().upper()

    cias_padrao = ["111ª CIA PM", "35ª CIA PM", "285ª CIA PM", "P3 / COPOM / EM"]

    unidades_db = obter_unidades_config_supabase()
    cias_banco = set()
    for u in unidades_db:
        sub = str(u.get("subunidade") or u.get("nome") or "").strip().upper()
        if sub and sub not in ["NONE", "N/I", ""]:
            cias_banco.add(sub)

    militares = carregar_militares_supabase() or []
    for m in militares:
        lot = str(m.get("lotacao") or m.get("unidade") or "").strip().upper()
        if "CIA" in lot:
            cias_banco.add(lot)

    lista_completa = sorted(list(set(cias_padrao + list(cias_banco))))

    return lotacao_militar, lista_completa


def carregar_escala_selecionada_passo1():
    """Busca no Supabase se existe rascunho/escala gravada para a Cia, Ano e Mês ativos."""
    if not supabase:
        return False

    sub_ativa = str(st.session_state.get("cfg_subunidade") or "111ª CIA PM").strip().upper()
    m_ano = int(st.session_state.get("ano_escala", datetime.date.today().year))
    m_mes = int(st.session_state.get("mes_escala", datetime.date.today().month))

    try:
        res = supabase.table("escalas_mensais").select("*").eq("ano", m_ano).eq("mes", m_mes).eq("equipe_nome", sub_ativa).execute()

        if res and res.data and len(res.data) > 0:
            row_escala = res.data[0]
            md = row_escala.get("matriz_dados", {})

            st.session_state["grade_escala_lancamentos"] = md.get("grade_escala_lancamentos", {})
            chaves_raw = md.get("militares_no_quadro_chaves", [])
            st.session_state["militares_no_quadro_chaves"] = [
                (str(p[0]), str(p[1]))
                for p in chaves_raw
                if isinstance(p, (tuple, list)) and len(p) == 2
            ]
            st.session_state["ordem_customizada_map"] = md.get("ordem_customizada_map", {})
            st.session_state["bh_configs"] = md.get("bh_configs", {})
            st.session_state["ajuste_saldo_map"] = md.get("ajuste_saldo_map", {})
            st.session_state["dias_selecionados_passo4"] = md.get("dias_selecionados_passo4", [])

            status_banco = str(row_escala.get("status", "RASCUNHO")).upper()
            st.session_state["status_escala_ativo"] = status_banco
            st.session_state["toggle_trava_quadro"] = (status_banco == "HOMOLOGADA")
            st.session_state["escala_fechada_auditoria"] = (status_banco == "HOMOLOGADA")

            st.session_state["p5_elaborador_sel"] = row_escala.get("elaborado_por")
            st.session_state["p5_homologador_sel"] = row_escala.get("homologado_por")

            st.session_state["chave_escala_carregada"] = f"{sub_ativa}_{m_ano}_{m_mes:02d}"
            st.toast(f"📖 Rascunho existente da {sub_ativa} ({m_mes:02d}/{m_ano}) carregado do banco!", icon="✅")
            return True
        else:
            # Novo arquivo zerado para a fração selecionada
            st.session_state["grade_escala_lancamentos"] = {}
            st.session_state["militares_no_quadro_chaves"] = []
            st.session_state["ordem_customizada_map"] = {}
            st.session_state["status_escala_ativo"] = "RASCUNHO"
            st.session_state["toggle_trava_quadro"] = False
            st.session_state["escala_fechada_auditoria"] = False
            st.session_state["chave_escala_carregada"] = f"{sub_ativa}_{m_ano}_{m_mes:02d}"
            st.toast(f"✨ Nova escala inicializada (zerada) para {sub_ativa} ({m_mes:02d}/{m_ano})!", icon="🆕")
            return False
    except Exception as ex:
        st.error(f"Erro ao consultar banco de dados: {ex}")
        return False


def renderizar_passo1():
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    perfil_usr = str(usr_dados.get("nivel_acesso") or usr_dados.get("perfil_escala") or usr_dados.get("perfil") or "TROPA").upper()
    cargo_usr = str(usr_dados.get("cargo_funcao") or "").upper()

    eh_programador_p3 = any(p in perfil_usr or p in cargo_usr for p in ["PROGRAMADOR", "ADMIN", "DESENVOLVEDOR", "P3", "CHEFE_P3"])

    lotacao_militar_real, cias_disponiveis = obter_cias_disponiveis_unidade()

    if "cfg_subunidade" not in st.session_state or not st.session_state["cfg_subunidade"]:
        st.session_state["cfg_subunidade"] = lotacao_militar_real

    with st.expander("📌 PASSO 1: Unidade Operacional, Mês/Ano & Seleção da Escala", expanded=True):
        st.markdown("##### 🏛️ **Definição da Unidade Operacional & Período da Escala:**")

        col_u1, col_u2, col_u3, col_u4 = st.columns([2.2, 1.2, 1.0, 1.6], vertical_alignment="bottom")

        with col_u1:
            if eh_programador_p3:
                idx_default = 0
                if st.session_state["cfg_subunidade"] in cias_disponiveis:
                    idx_default = cias_disponiveis.index(st.session_state["cfg_subunidade"])

                cia_selecionada = st.selectbox(
                    "🏢 Cia/Fração a Produzir Escala:",
                    options=cias_disponiveis,
                    index=idx_default,
                    key="sb_selecionar_cia_escala_passo1"
                )
                st.session_state["cfg_subunidade"] = cia_selecionada
            else:
                st.text_input(
                    "🏢 Cia/Fração (Sua Lotação):",
                    value=lotacao_militar_real,
                    disabled=True
                )
                st.session_state["cfg_subunidade"] = lotacao_militar_real

        with col_u2:
            m_meses_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            mes_atual = st.session_state.get("mes_escala", datetime.date.today().month)

            sel_mes_nome = st.selectbox(
                "📅 Mês:",
                options=m_meses_nomes,
                index=mes_atual - 1,
                key="sb_passo1_mes_escala"
            )
            st.session_state["mes_escala"] = m_meses_nomes.index(sel_mes_nome) + 1

        with col_u3:
            ano_atual = st.session_state.get("ano_escala", datetime.date.today().year)
            st.session_state["ano_escala"] = st.number_input(
                "📆 Ano:",
                min_value=2024,
                max_value=2035,
                value=ano_atual,
                key="num_passo1_ano_escala"
            )

        with col_u4:
            if st.button("💾 Criar / Carregar Escala", type="primary", use_container_width=True, key="btn_criar_carregar_escala_p1"):
                carregar_escala_selecionada_passo1()
                st.rerun()

        sub_nome = st.session_state.get("cfg_subunidade", "111ª CIA PM")
        m_num = st.session_state.get("mes_escala", datetime.date.today().month)
        a_num = st.session_state.get("ano_escala", datetime.date.today().year)

        st.info(f"🎯 **Escala Selecionada para Produção:** `{sub_nome}` | **Período:** `{m_num:02d}/{a_num}`")

        st.divider()

        # GESTÃO DAS EQUIPES / EMPREGOS OPERACIONAIS DA UNIDADE
        st.markdown("##### 👥 **Equipes e Empregos Operacionais da Fração:**")

        if "lista_equipes_unidade" not in st.session_state:
            st.session_state["lista_equipes_unidade"] = ["CPU", "RP", "SUPERVISÃO", "ADMINISTRAÇÃO", "TM ALPHA", "GEPAR"]

        if "equipe_ativa" not in st.session_state:
            st.session_state["equipe_ativa"] = "ADMINISTRAÇÃO"

        c_eq1, c_eq2 = st.columns([3, 1.5])

        with c_eq1:
            eq_sel = st.selectbox(
                "Equipe / Emprego Operacional em Edição:",
                options=st.session_state["lista_equipes_unidade"],
                index=0 if st.session_state["equipe_ativa"] not in st.session_state["lista_equipes_unidade"] else st.session_state["lista_equipes_unidade"].index(st.session_state["equipe_ativa"]),
                key="sb_equipe_ativa_passo1"
            )
            st.session_state["equipe_ativa"] = eq_sel

        with c_eq2:
            nova_eq_nome = st.text_input("➕ Criar Nova Equipe:", placeholder="Ex: TÁTICO MÓVEL", key="txt_nova_eq_passo1").strip().upper()
            if st.button("➕ Adicionar Equipe", use_container_width=True, key="btn_add_eq_passo1"):
                if nova_eq_nome and nova_eq_nome not in st.session_state["lista_equipes_unidade"]:
                    st.session_state["lista_equipes_unidade"].append(nova_eq_nome)
                    st.session_state["equipe_ativa"] = nova_eq_nome
                    st.success(f"✅ Equipe '{nova_eq_nome}' adicionada!")
                    st.rerun()

        st.markdown(f"🟢 **Equipe Selecionada para Lançamento:** `{st.session_state['equipe_ativa']}`")