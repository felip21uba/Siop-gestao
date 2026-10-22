"""
==============================================================================
Módulo do Passo 1 - Unidade Operacional, Escolha da Fração, Mês/Ano & Pré-Turno
Leitura Dinâmica e Genérica de Lotações para qualquer BPM, Cia, Pel, GP ou Seção da PMMG.
==============================================================================
"""

import streamlit as st
import datetime
import re
from core.database import (
    supabase, 
    carregar_militares_supabase
)


def extrair_padroes_lotacao_generica(texto_lotacao):
    """
    Analisa qualquer string de lotação da PMMG e extrai de forma genérica
    o Batalhão, Cia, Pelotão, GP ou Seção Administrativa.
    """
    txt = str(texto_lotacao or "").strip().upper()
    
    # 1. Identifica Seções do Estado-Maior / Administração
    secoes_encontradas = re.findall(r'\b(P1|P2|P3|P4|SADM|NJD|COPOM|EM|Ajudancia|Sargenteação)\b', txt, re.IGNORECASE)
    
    # 2. Identifica Companhia (ex: 35ª CIA, 111 CIA, 285 CIA TM, CIA IND)
    match_cia = re.search(r'(\d+\s*ª?\s*CIA(?:\s+[A-Z0-9]+)?|CIA\s+[A-Z0-9]+)', txt)
    cia_str = match_cia.group(0) if match_cia else None

    # 3. Identifica Pelotão (ex: 1º PEL, 2 PEL)
    match_pel = re.search(r'(\d+\s*º?\s*PEL)', txt)
    pel_str = match_pel.group(0) if match_pel else None

    # 4. Identifica Grupamento (ex: 1º GP, 2 GP)
    match_gp = re.search(r'(\d+\s*º?\s*GP)', txt)
    gp_str = match_gp.group(0) if match_gp else None

    return {
        "secoes": [s.upper() for s in secoes_encontradas],
        "cia": cia_str,
        "pelotao": pel_str,
        "grupamento": gp_str,
        "texto_raw": txt
    }


def obter_cias_disponiveis_unidade_generico():
    """
    Varre a base e monta dinamicamente todas as Cias/Subunidades do Batalhão ativo.
    """
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    lotacao_militar_raw = str(
        usr_dados.get("unidade")
        or usr_dados.get("lotacao")
        or usr_dados.get("subunidade")
        or "SEÇÃO / EM"
    ).strip().upper()

    subunidades_encontradas = set()

    # Leitura das configurações cadastradas
    if supabase:
        try:
            res_u = supabase.table("unidades_config").select("*").execute()
            for u in (res_u.data or []):
                sub = str(u.get("subunidade") or u.get("companhia") or u.get("nome") or "").strip().upper()
                if sub and sub not in ["NONE", "N/I", ""]:
                    subunidades_encontradas.add(sub)
        except Exception:
            pass

    # Leitura dinâmica das lotações dos militares do banco de dados
    militares = carregar_militares_supabase() or []
    for m in militares:
        lot = str(m.get("lotacao") or m.get("unidade") or "").strip().upper()
        info = extrair_padroes_lotacao_generica(lot)
        
        if info["cia"]:
            subunidades_encontradas.add(info["cia"])
        elif info["secoes"]:
            subunidades_encontradas.add("SEÇÕES / ESTADO-MAIOR")

    if not subunidades_encontradas:
        subunidades_encontradas.add(lotacao_militar_raw)

    lista_ordenada = sorted(list(subunidades_encontradas))
    return lotacao_militar_raw, lista_ordenada


def carregar_escala_selecionada_passo1():
    """Carrega no estado da sessão a escala da fração escolhida no Passo 1."""
    if not supabase:
        return False

    sub_ativa = str(st.session_state.get("cfg_subunidade") or "SUBUNIDADE").strip().upper()
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
            st.toast(f"📖 Escala da {sub_ativa} ({m_mes:02d}/{m_ano}) carregada!", icon="✅")
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

    lotacao_militar_real, cias_disponiveis_todas = obter_cias_disponiveis_unidade_generico()

    perfil_usr = str(usr_dados.get("nivel_acesso") or usr_dados.get("perfil_escala") or "").strip().upper()
    cargo_usr = str(usr_dados.get("cargo_funcao") or "").strip().upper()
    escopo_gestor = str(usr_dados.get("escopo_gestao") or "GLOBAL").strip().upper()

    info_lotacao = extrair_padroes_lotacao_generica(lotacao_militar_real)

    # -------------------------------------------------------------------------
    # REGRAS GENÉRICAS E DINÂMICAS DE ACESSO
    # -------------------------------------------------------------------------
    SECOES_CHEFE_GLOBAIS = ["P1", "P2", "P3", "P4", "SADM", "NJD", "CHEFE", "SARGENTEAÇÃO", "COPOM", "EM"]

    # 1. PROGRAMADOR / ADMIN: Acesso Total Irrestrito
    if perfil_usr in ["PROGRAMADOR", "ADMIN", "DESENVOLVEDOR"]:
        cias_permitidas = cias_disponiveis_todas
        desabilitar_seletor = False
        msg_permissao = "🚀 **Acesso Programador / Superuser:** Acesso irrestrito a todas as Unidades."
        tipo_msg = "info"

    # 2. CHEFES DE SEÇÃO / ESTADO-MAIOR: Acesso Global ao Batalhão
    elif any(sec in info_lotacao["secoes"] or sec in cargo_usr or sec in perfil_usr for sec in SECOES_CHEFE_GLOBAIS):
        cias_permitidas = cias_disponiveis_todas
        desabilitar_seletor = False
        msg_permissao = "🏛️ **Acesso Chefe de Seção / Estado-Maior:** Visão e gestão de todas as subunidades do Batalhão."
        tipo_msg = "info"

    # 3. GESTOR (Com Escopo Parametrizado)
    elif perfil_usr == "GESTOR":
        if escopo_gestor == "GLOBAL":
            cias_permitidas = cias_disponiveis_todas
        else:
            cias_permitidas = [c for c in cias_disponiveis_todas if escopo_gestor in c or c in escopo_gestor]
            if not cias_permitidas:
                cias_permitidas = [lotacao_militar_real]
        desabilitar_seletor = False
        msg_permissao = f"⚙️ **Acesso Gestor (Escopo: {escopo_gestor}):** Gerenciando frações atribuídas."
        tipo_msg = "info"

    # 4. COMANDANTE DE COMPANHIA / SARGENTEANTE
    elif perfil_usr in ["CMT_CIA", "SARGENTEANTE"] or "CMT" in cargo_usr or "COMANDANTE" in cargo_usr:
        cia_chave = info_lotacao["cia"] if info_lotacao["cia"] else lotacao_militar_real
        cias_permitidas = [c for c in cias_disponiveis_todas if cia_chave in c or c in cia_chave]
        if not cias_permitidas:
            cias_permitidas = [lotacao_militar_real]
        desabilitar_seletor = False
        msg_permissao = f"👮‍♂️ **Acesso Comando de Cia ({cia_chave}):** Gerenciando sua Cia e frações subordinadas."
        tipo_msg = "info"

    # 5. TROPA / DEMAIS MILITARES (Restrito)
    else:
        cias_permitidas = [lotacao_militar_real]
        desabilitar_seletor = True
        msg_permissao = f"🔒 **Acesso Restrito:** Acesso limitado à sua própria fração ({lotacao_militar_real})."
        tipo_msg = "warning"

    if "cfg_subunidade" not in st.session_state or st.session_state["cfg_subunidade"] not in cias_permitidas:
        st.session_state["cfg_subunidade"] = cias_permitidas[0] if cias_permitidas else lotacao_militar_real

    with st.expander("📌 PASSO 1: Unidade Operacional, Mês/Ano & Seleção da Escala", expanded=True):
        st.markdown("##### 🏛️ **Definição da Unidade Operacional & Período da Escala:**")

        col_u1, col_u2, col_u3, col_u4, col_u5, col_u6 = st.columns([2.2, 2.0, 1.2, 1.0, 1.8, 1.5], vertical_alignment="bottom")

        # 1. LOTAÇÃO REAL DO OPERADOR
        with col_u1:
            st.text_input(
                "🏢 Cia/Fração (Sua Lotação):",
                value=lotacao_militar_real,
                disabled=True
            )

        # 2. FRAÇÃO ALVO / ESCALA A PRODUZIR
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

        sub_nome = st.session_state.get("cfg_subunidade", lotacao_militar_real)
        m_num = st.session_state.get("mes_escala", datetime.date.today().month)
        a_num = st.session_state.get("ano_escala", datetime.date.today().year)
        pt_nome = st.session_state.get("pre_turno_opcao", "Pré-Turno 30 min (+0.5h)")

        if tipo_msg == "info":
            st.info(f"{msg_permissao} &nbsp;|&nbsp; 🎯 **Escala Ativa:** `{sub_nome}` (`{m_num:02d}/{a_num}`)")
        else:
            st.warning(f"{msg_permissao} &nbsp;|&nbsp; 🎯 **Escala Ativa:** `{sub_nome}` (`{m_num:02d}/{a_num}`)")