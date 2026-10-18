"""
==============================================================================
Módulo do Passo 1 - Unidade Operacional, Escolha da Fração, Mês/Ano & Pré-Turno
Aplica o filtro definitivo de acesso e permissão com trava por hierarquia e lotação.
==============================================================================
"""

import streamlit as st
import datetime
import re
from core.database import (
    supabase, 
    carregar_militares_supabase
)


def obter_cias_disponiveis_unidade():
    """
    Retorna a lotação do militar logado e uma lista limpa e sem duplicidades
    das Companhias/Subunidades do Batalhão.
    """
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    lotacao_militar = str(
        usr_dados.get("unidade")
        or usr_dados.get("lotacao")
        or usr_dados.get("subunidade")
        or "P3/EM/21 BPM/4 RPM"
    ).strip().upper()

    cias_base_padrao = ["111ª CIA PM", "35ª CIA PM", "285ª CIA PM", "P3 / COPOM / EM"]
    cias_extraidas = set()

    # Busca subunidades cadastradas no banco
    if supabase:
        try:
            res_u = supabase.table("unidades_config").select("*").execute()
            for u in (res_u.data or []):
                sub = str(u.get("subunidade") or u.get("companhia") or u.get("nome") or "").strip().upper()
                if sub and sub not in ["NONE", "N/I", ""]:
                    cias_extraidas.add(sub)
        except Exception:
            pass

    # Extrai e simplifica nomes de Cia da lotação dos militares
    militares = carregar_militares_supabase() or []
    for m in militares:
        lot = str(m.get("lotacao") or m.get("unidade") or "").strip().upper()
        
        match_cia = re.search(r'(\d+)\s*ª?\s*CIA', lot)
        if match_cia:
            num_cia = match_cia.group(1)
            cias_extraidas.add(f"{num_cia}ª CIA PM")
        elif any(k in lot for k in ["P3", "COPOM", "EM", "P2", "SADM"]):
            cias_extraidas.add("P3 / COPOM / EM")

    todas_cias = list(set(cias_base_padrao + list(cias_extraidas)))
    
    def chave_ordenacao(item):
        m = re.search(r'\d+', item)
        return int(m.group(0)) if m else 999

    lista_limpa = sorted(todas_cias, key=chave_ordenacao)
    return lotacao_militar, lista_limpa


def carregar_escala_selecionada_passo1():
    """Busca no Supabase se existe rascunho/escala gravada para a Fração, Ano e Mês ativos."""
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
            st.toast(f"📖 Rascunho da {sub_ativa} ({m_mes:02d}/{m_ano}) carregado!", icon="✅")
            return True
        else:
            st.session_state["grade_escala_lancamentos"] = {}
            st.session_state["militares_no_quadro_chaves"] = []
            st.session_state["ordem_customizada_map"] = {}
            st.session_state["status_escala_ativo"] = "RASCUNHO"
            st.session_state["toggle_trava_quadro"] = False
            st.session_state["escala_fechada_auditoria"] = False
            st.session_state["chave_escala_carregada"] = f"{sub_ativa}_{m_ano}_{m_mes:02d}"
            st.toast(f"✨ Nova escala inicializada para {sub_ativa} ({m_mes:02d}/{m_ano})!", icon="🆕")
            return False
    except Exception as ex:
        st.error(f"Erro ao consultar banco de dados: {ex}")
        return False


def renderizar_passo1():
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    lotacao_militar_real, cias_disponiveis_todas = obter_cias_disponiveis_unidade()

    perfil_usr = str(usr_dados.get("nivel_acesso") or usr_dados.get("perfil_escala") or "").strip().upper()
    cargo_usr = str(usr_dados.get("cargo_funcao") or "").strip().upper()

    # -------------------------------------------------------------------------
    # REGRA DEFINITIVA DE PERMISSÃO E FILTRO DE SEGURANÇA
    # -------------------------------------------------------------------------
    SECOES_GLOBAL = ["P2", "P3", "SADM", "ADMIN", "PROGRAMADOR", "DESENVOLVEDOR", "CMT_BPM"]

    eh_gestor_global = any(
        sec in lotacao_militar_real or sec in perfil_usr or sec in cargo_usr 
        for sec in SECOES_GLOBAL
    )

    if eh_gestor_global:
        # P2, P3, SADM, ADMIN: Vê e seleciona TODAS as escalas
        cias_permitidas = cias_disponiveis_todas
        desabilitar_seletor = False
        msg_permissao = "💡 **Acesso Gestor Global (P2/P3/SADM):** Permissão para visualizar e criar escalas de qualquer fração do Batalhão."
        tipo_msg = "info"
    elif "CMT" in cargo_usr or "COMANDANTE" in cargo_usr or "CMT_CIA" in perfil_usr:
        # Cmt de Cia / Cmt de Pel: Vê sua companhia e frações subordinadas
        cias_permitidas = [c for c in cias_disponiveis_todas if lotacao_militar_real in c or c in lotacao_militar_real]
        if not cias_permitidas:
            cias_permitidas = [lotacao_militar_real]
        desabilitar_seletor = False
        msg_permissao = f"👮‍♂️ **Acesso Comando ({lotacao_militar_real}):** Visualizando e editando frações sob seu comando."
        tipo_msg = "info"
    else:
        # Demais militares / Tropa: Estritamente restrito à sua lotação exata
        cias_permitidas = [lotacao_militar_real]
        desabilitar_seletor = True
        msg_permissao = f"🔒 **Acesso Restrito:** Suas permissões estão limitadas à sua lotação ({lotacao_militar_real})."
        tipo_msg = "warning"

    if "cfg_subunidade" not in st.session_state or st.session_state["cfg_subunidade"] not in cias_permitidas:
        st.session_state["cfg_subunidade"] = cias_permitidas[0] if cias_permitidas else "111ª CIA PM"

    with st.expander("📌 PASSO 1: Unidade Operacional, Mês/Ano & Seleção da Escala", expanded=True):
        st.markdown("##### 🏛️ **Definição da Unidade Operacional & Período da Escala:**")

        col_u1, col_u2, col_u3, col_u4, col_u5, col_u6 = st.columns([2.2, 2.0, 1.2, 1.0, 1.8, 1.5], vertical_alignment="bottom")

        # 1. LOTAÇÃO REAL DO OPERADOR (FIXA)
        with col_u1:
            st.text_input(
                "🏢 Cia/Fração (Sua Lotação):",
                value=lotacao_militar_real,
                disabled=True
            )

        # 2. FRAÇÃO ALVO / ESCALA A PRODUZIR (COM TRAVA DE SEGURANÇA)
        with col_u2:
            idx_default = 0
            if st.session_state["cfg_subunidade"] in cias_permitidas:
                idx_default = cias_permitidas.index(st.session_state["cfg_subunidade"])

            cia_selecionada = st.selectbox(
                "📋 Escala / Fração a Produzir:",
                options=cias_permitidas,
                index=idx_default,
                disabled=desabilitar_seletor,
                key="sb_selecionar_cia_escala_passo1"
            )
            st.session_state["cfg_subunidade"] = cia_selecionada

        # 3. MÊS
        with col_u3:
            m_meses_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            mes_atual = st.session_state.get("mes_escala", datetime.date.today().month)

            sel_mes_nome = st.selectbox(
                "📅 Mês:",
                options=m_meses_nomes,
                index=mes_atual - 1,
                key="sb_passo1_mes_escala"
            )
            st.session_state["mes_escala"] = m_meses_nomes.index(sel_mes_nome) + 1

        # 4. ANO
        with col_u4:
            ano_atual = st.session_state.get("ano_escala", datetime.date.today().year)
            st.session_state["ano_escala"] = st.number_input(
                "📆 Ano:",
                min_value=2024,
                max_value=2035,
                value=ano_atual,
                key="num_passo1_ano_escala"
            )

        # 5. PRÉ-TURNO DE APRESENTAÇÃO
        with col_u5:
            st.session_state["pre_turno_opcao"] = st.selectbox(
                "⏰ Pré-Turno de Apresentação:",
                options=[
                    "Sem Pré-Turno (0 min)",
                    "Pré-Turno 15 min (+0.25h)",
                    "Pré-Turno 30 min (+0.5h)",
                    "Pré-Turno 45 min (+0.75h)"
                ],
                index=2,
                key="sb_passo1_pre_turno"
            )

        # 6. BOTÃO DE CRIAR / CARREGAR
        with col_u6:
            if st.button("💾 Criar / Carregar Escala", type="primary", use_container_width=True, key="btn_criar_carregar_escala_p1"):
                carregar_escala_selecionada_passo1()
                st.rerun()

        sub_nome = st.session_state.get("cfg_subunidade", "111ª CIA PM")
        m_num = st.session_state.get("mes_escala", datetime.date.today().month)
        a_num = st.session_state.get("ano_escala", datetime.date.today().year)
        pt_nome = st.session_state.get("pre_turno_opcao", "Pré-Turno 30 min (+0.5h)")

        if tipo_msg == "info":
            st.info(f"{msg_permissao} &nbsp;|&nbsp; 🎯 **Escala Ativa:** `{sub_nome}` (`{m_num:02d}/{a_num}`)")
        else:
            st.warning(f"{msg_permissao} &nbsp;|&nbsp; 🎯 **Escala Ativa:** `{sub_nome}` (`{m_num:02d}/{a_num}`)")