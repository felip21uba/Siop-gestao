"""
==============================================================================
Módulo do Passo 1 - Unidade Operacional, Escolha da Fração, Mês/Ano & Pré-Turno
Exibe todas as frações detalhadas (Cia, Pelotão, GP) ponto a ponto no seletor,
filtrando o acesso rigorosamente de acordo com o perfil/função do usuário.
==============================================================================
"""

import streamlit as st
import datetime
import re
import unicodedata
from core.database import (
    supabase, 
    carregar_militares_supabase
)


def normalizar_str_comparacao(texto):
    if not texto:
        return ""
    t_norm = unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8").upper().strip()
    return re.sub(r"\s+", " ", t_norm)


def obter_todas_fracoes_detalhadas_unidade():
    """
    Varre os militares e configurações gravadas para extrair ponto a ponto
    todas as Cias, Pelotões, GPs e Seções cadastradas.
    """
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    lotacao_militar_real = str(
        usr_dados.get("unidade")
        or usr_dados.get("lotacao")
        or usr_dados.get("subunidade")
        or "P3 / COPOM / EM"
    ).strip().upper()

    fracoes_encontradas = set()

    # 1. Busca no banco de dados de unidades
    if supabase:
        try:
            res_u = supabase.table("unidades_config").select("*").execute()
            for u in (res_u.data or []):
                sub = str(u.get("subunidade") or u.get("companhia") or u.get("nome") or "").strip().upper()
                if sub and sub not in ["NONE", "N/I", ""]:
                    fracoes_encontradas.add(sub)
        except Exception:
            pass

    # 2. Busca na lotação real de todos os militares cadastrados (sem simplificar/agrupar)
    militares = carregar_militares_supabase() or []
    for m in militares:
        lot = str(m.get("lotacao") or m.get("unidade") or m.get("subunidade") or "").strip().upper()
        if lot and lot not in ["NONE", "N/I", ""]:
            fracoes_encontradas.add(lot)

    # Adiciona a lotação do militar logado como garantia
    if lotacao_militar_real:
        fracoes_encontradas.add(lotacao_militar_real)

    # Se não houver dados, gera uma base detalhada padrão
    if not fracoes_encontradas:
        fracoes_encontradas = {
            "111ª CIA PM",
            "1 PEL / 111ª CIA PM",
            "1 GP / 1 PEL / 111ª CIA PM",
            "2 GP / 1 PEL / 111ª CIA PM",
            "2 PEL / 111ª CIA PM",
            "1 GP / 2 PEL / 111ª CIA PM",
            "35ª CIA PM",
            "1 PEL / 35ª CIA PM",
            "1 GP / 1 PEL / 35ª CIA PM",
            "285ª CIA TM",
            "P3 / EM / 21º BPM"
        }

    # Ordenação lógica
    def chave_ordem(item):
        nums = re.findall(r'\d+', item)
        val_num = int(nums[0]) if nums else 999
        return (val_num, item)

    lista_ordenada = sorted(list(fracoes_encontradas), key=chave_ordem)
    return lotacao_militar_real, lista_ordenada


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
            st.toast(f"📖 Escala da fração {sub_ativa} ({m_mes:02d}/{m_ano}) carregada!", icon="✅")
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

    lotacao_militar_real, lista_todas_fracoes_detalhadas = obter_todas_fracoes_detalhadas_unidade()

    perfil_usr = normalizar_str_comparacao(usr_dados.get("nivel_acesso") or usr_dados.get("perfil_escala") or usr_dados.get("perfil"))
    cargo_usr = normalizar_str_comparacao(usr_dados.get("cargo_funcao"))
    escopo_gestor = normalizar_str_comparacao(usr_dados.get("escopo_gestao") or "GLOBAL")

    SECOES_CHEFE_GLOBAIS = ["P1", "P2", "P3", "P4", "SADM", "NJD", "CHEFE", "SARGENTEACAO", "SARGENTIACAO", "COPOM", "EM", "PROGRAMADOR", "ADMIN", "DESENVOLVEDOR", "GESTOR_SISTEMA"]

    # -------------------------------------------------------------------------
    # FILTRO RIGOROSO E FLEXÍVEL DE SELEÇÃO POR FUNÇÃO / HIERARQUIA
    # -------------------------------------------------------------------------
    
    # 1. PROGRAMADOR / ADMIN / CHEFES DE SEÇÃO / SARGENTEAÇÃO (P1, P3, ETC): Permissão total
    if any(sec in lotacao_militar_real or sec in cargo_usr or sec in perfil_usr for sec in SECOES_CHEFE_GLOBAIS):
        fracoes_permitidas = lista_todas_fracoes_detalhadas
        desabilitar_seletor = False
        msg_permissao = "🚀 **Acesso de Gestão Geral / Sargenteação:** Permissão total para criar/editar escalas de todas as frações e GPs."
        tipo_msg = "info"

    # 2. GESTOR (Parametrizado por Escopo)
    elif "GESTOR" in perfil_usr or "GESTOR" in cargo_usr:
        if escopo_gestor == "GLOBAL" or "GLOBAL" in perfil_usr:
            fracoes_permitidas = lista_todas_fracoes_detalhadas
        else:
            fracoes_permitidas = [f for f in lista_todas_fracoes_detalhadas if escopo_gestor in f or f in escopo_gestor or lotacao_militar_real in f]
            if not fracoes_permitidas:
                fracoes_permitidas = lista_todas_fracoes_detalhadas
        desabilitar_seletor = False
        msg_permissao = f"⚙️ **Acesso Gestor:** Selecionando dentro das frações permitidas do seu escopo."
        tipo_msg = "info"

    # 3. COMANDANTE DE COMPANHIA
    # Vê a Cia e TODOS os Pelotões e GPs subordinados a ela
    elif any(term in perfil_usr or term in cargo_usr for term in ["CMT_CIA", "COMANDANTE DE CIA", "COMANDANTE_CIA", "CMT CIA"]):
        match_cia = re.search(r'(\d+)\s*ª?\s*CIA', lotacao_militar_real)
        cia_num = match_cia.group(1) if match_cia else lotacao_militar_real
        
        fracoes_permitidas = [f for f in lista_todas_fracoes_detalhadas if cia_num in f or lotacao_militar_real in f]
        if not fracoes_permitidas:
            fracoes_permitidas = [lotacao_militar_real]
        desabilitar_seletor = False
        msg_permissao = f"👮‍♂️ **Acesso Comando de Cia ({lotacao_militar_real}):** Gerenciando sua Cia e todas as frações/GPs subordinados."
        tipo_msg = "info"

    # 4. COMANDANTE DE PELOTÃO / GP
    # Vê o seu Pelotão/GP e todas as frações/GPs filhas subordinadas
    elif any(term in perfil_usr or term in cargo_usr for term in ["PELOTAO", "PELOTÃO", "CMT_PEL", "COMANDANTE DE PELOTAO", "COMANDANTE DE PELOTÃO / GP", "GP"]):
        match_pel = re.search(r'(\d+)\s*º?\s*PEL', lotacao_militar_real)
        pel_num = match_pel.group(1) if match_pel else None

        if pel_num:
            # Filtra todas as frações que contêm o número do Pelotão (ex: "3 PEL", "1 GP/3 PEL", etc.)
            fracoes_permitidas = [f for f in lista_todas_fracoes_detalhadas if f"{pel_num} PEL" in f or f"{pel_num}PEL" in f or lotacao_militar_real in f]
        else:
            fracoes_permitidas = [f for f in lista_todas_fracoes_detalhadas if lotacao_militar_real in f]

        if not fracoes_permitidas:
            fracoes_permitidas = [lotacao_militar_real]

        desabilitar_seletor = False
        msg_permissao = f"👮‍♂️ **Acesso Comando de Pelotão / GP ({lotacao_militar_real}):** Gerenciando seu Pelotão e todas as frações/GPs subordinados."
        tipo_msg = "info"

    # 5. TROPA (SEM FUNÇÃO DE COMANDO OU GESTÃO)
    else:
        fracoes_permitidas = [lotacao_militar_real]
        desabilitar_seletor = True
        msg_permissao = f"🔒 **Acesso Restrito:** Acesso limitado à sua fração exata ({lotacao_militar_real})."
        tipo_msg = "warning"

    if "cfg_subunidade" not in st.session_state or st.session_state["cfg_subunidade"] not in fracoes_permitidas:
        st.session_state["cfg_subunidade"] = fracoes_permitidas[0] if fracoes_permitidas else lotacao_militar_real

    with st.expander("📌 PASSO 1: Unidade Operacional, Mês/Ano & Seleção da Escala", expanded=True):
        st.markdown("##### 🏛️ **Definição da Unidade Operacional & Período da Escala:**")

        col_u1, col_u2, col_u3, col_u4, col_u5, col_u6 = st.columns([2.2, 2.3, 1.2, 1.0, 1.8, 1.5], vertical_alignment="bottom")

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
            if st.session_state["cfg_subunidade"] in fracoes_permitidas:
                idx_default = fracoes_permitidas.index(st.session_state["cfg_subunidade"])

            cia_selecionada = st.selectbox(
                "📋 Escala / Fração a Produzir:",
                options=fracoes_permitidas,
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

        if tipo_msg == "info":
            st.info(f"{msg_permissao} &nbsp;|&nbsp; 🎯 **Escala Ativa para Seleção:** `{sub_nome}` (`{m_num:02d}/{a_num}`)")
        else:
            st.warning(f"{msg_permissao} &nbsp;|&nbsp; 🎯 **Escala Ativa para Seleção:** `{sub_nome}` (`{m_num:02d}/{a_num}`)")