"""
==============================================================================
Módulo do Passo 5 - Espelho da Escala (2ª Tela em Tempo Real)
Sincronizado diretamente com a Cia/Fração e o período ativo selecionado.
==============================================================================
"""

import streamlit as st
import datetime
import calendar
import pandas as pd
import urllib.parse
import streamlit.components.v1 as components

from core.database import supabase, carregar_militares_supabase
from modules.escalas.passos.passo3_efetivo import PESOS_HIERARQUIA, padronizar_graduacao
from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS

SIGLAS_DIAS_NEUTROS = {"F", "D", "X", "FER", "DOM", "FERIADO", "LM", "ATE", "FE", "LUT", "NUP", "DN", "DNT"}


def padronizar_entrada_espelho(valor):
    if valor is None or pd.isna(valor):
        return ""
    v = str(valor).strip().upper()
    if not v or v in ["F", "FOLGA"]:
        return "F"
    if v in ["D", "DOM", "DOMINGO", "DESCANSO", "OFF"]:
        return "D"
    if v in ["X", "FER", "FERIADO"]:
        return "X"
    return str(valor).strip()


def carregar_dados_espelho_supabase(subunidade, m_ano, m_mes):
    """
    Consulta o Supabase garantindo isolamento por subunidade/fração, ano e mês.
    """
    if not supabase:
        return {}, [], {}, {}

    sub_str = str(subunidade).strip().upper()
    mes_int = int(m_mes)
    ano_int = int(m_ano)

    try:
        res = supabase.table("escalas_mensais").select("*").eq("ano", ano_int).eq("mes", mes_int).order("id", desc=True).execute()
        
        row_alvo = None
        if res and res.data:
            for r in res.data:
                eq_nome = str(r.get("equipe_nome") or "").strip().upper()
                if sub_str in eq_nome or eq_nome in sub_str or eq_nome == "GERAL":
                    row_alvo = r
                    break
            if not row_alvo and len(res.data) > 0:
                row_alvo = res.data[0]

        if row_alvo:
            md = row_alvo.get("matriz_dados", {})
            grade = md.get("grade_escala_lancamentos", {})
            chaves_raw = md.get("militares_no_quadro_chaves", [])

            chaves = []
            vistas = set()
            for p in chaves_raw:
                if isinstance(p, (tuple, list)) and len(p) == 2:
                    pair_str = f"{p[0]}_{p[1]}"
                    if pair_str not in vistas:
                        vistas.add(pair_str)
                        chaves.append((str(p[0]), str(p[1])))

            bh_cfg = md.get("bh_configs", {})
            ordem_map = md.get("ordem_customizada_map", {})
            return grade, chaves, bh_cfg, ordem_map
    except Exception as ex:
        print(f"Erro ao carregar dados do espelho no Supabase: {ex}")

    return {}, [], {}, {}


def renderizar_modo_segunda_tela():
    """
    Renderiza a 2ª Tela (Espelho) de forma autônoma lendo os parâmetros da URL
    e atualizando automaticamente a cada sincronização.
    """
    st.markdown(
        """
        <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stSidebar"] {display: none !important;}
        .block-container { padding: 0.5rem 1rem 0rem 1rem !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

    params = st.query_params

    raw_sub = params.get("subunidade", st.session_state.get("cfg_subunidade", "111ª CIA PM"))
    raw_mes = params.get("mes", st.session_state.get("mes_escala", datetime.date.today().month))
    raw_ano = params.get("ano", st.session_state.get("ano_escala", datetime.date.today().year))

    if isinstance(raw_sub, list):
        raw_sub = raw_sub[0]
    if isinstance(raw_mes, list):
        raw_mes = raw_mes[0]
    if isinstance(raw_ano, list):
        raw_ano = raw_ano[0]

    subunidade = urllib.parse.unquote(str(raw_sub)).strip().upper()

    try:
        m_mes = int(raw_mes)
    except (ValueError, TypeError):
        m_mes = datetime.date.today().month

    try:
        m_ano = int(raw_ano)
    except (ValueError, TypeError):
        m_ano = datetime.date.today().year

    st.markdown(f"### 🖥️ ESPELHO DA ESCALA — {subunidade} ({m_mes:02d}/{m_ano})")

    # Lê primeiro da memória viva se existir no mesmo processo ou busca do Supabase
    grade = st.session_state.get("grade_escala_lancamentos")
    chaves_existentes = st.session_state.get("militares_no_quadro_chaves")
    ordem_map = st.session_state.get("ordem_customizada_map", {})

    if not grade or not chaves_existentes:
        grade, chaves_existentes, _, ordem_map = carregar_dados_espelho_supabase(subunidade, m_ano, m_mes)

    militares = st.session_state.get("lista_militares") or carregar_militares_supabase() or []
    num_dias = calendar.monthrange(m_ano, m_mes)[1]

    mils_linhas = []
    mats_vistas = set()

    for p in chaves_existentes:
        if isinstance(p, (tuple, list)) and len(p) == 2:
            chave_uniqua = f"{p[0]}_{p[1]}"
            if chave_uniqua not in mats_vistas:
                m_obj = next((x for x in militares if str(x.get("id")) == str(p[0])), None)
                if m_obj:
                    mats_vistas.add(chave_uniqua)
                    mils_linhas.append({
                        "id": str(p[0]),
                        "equipe": str(p[1]),
                        "posto_grad": m_obj.get("posto_grad", "SD"),
                        "nome_guerra": m_obj.get("nome_guerra", "MILITAR"),
                        "num_policia": m_obj.get("num_policia", ""),
                        "chave_linha": chave_uniqua
                    })

    mils_ord = sorted(
        mils_linhas, 
        key=lambda x: (
            ordem_map.get(x["chave_linha"], 99), 
            PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99), 
            x["nome_guerra"]
        )
    )

    colunas_dias = [
        (d, f"{'🔴 ' if calendar.weekday(m_ano, m_mes, d) in [5,6] else ''}{d:02d} {DIAS_SEMANA_SIGLAS[calendar.weekday(m_ano, m_mes, d)]}") 
        for d in range(1, num_dias + 1)
    ]
    
    matriz = []

    for idx_r, item in enumerate(mils_ord):
        m_id, eq, pg, ng, np = item["id"], item["equipe"], padronizar_graduacao(item["posto_grad"]), item["nome_guerra"], item["num_policia"]
        linha = {
            "ORDEM": int(ordem_map.get(item["chave_linha"], idx_r + 1)), 
            "EQUIPE": eq, 
            "Nº POLÍCIA": np, 
            "MILITAR": f"{pg} {ng}"
        }

        for d, col_name in colunas_dias:
            val_bruto = grade.get(f"{m_id}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "F")
            linha[col_name] = padronizar_entrada_espelho(val_bruto) if val_bruto != "" else "F"

        matriz.append(linha)

    df_escala = pd.DataFrame(matriz)

    if not df_escala.empty:
        st.dataframe(
            df_escala,
            use_container_width=True,
            hide_index=True,
            height=820
        )
    else:
        st.info(f"💡 Nenhuma linha ativa no Quadro 5 para {subunidade} ({m_mes:02d}/{m_ano}).")

    # Listener do BroadcastChannel do navegador (Atualiza na hora em que o botão Aplicar é clicado)
    components.html(
        """
        <script>
        const bc = new BroadcastChannel('SIOP_ESCALA_UPDATES');
        bc.onmessage = function(ev) {
            if (ev.data && ev.data.action === 'RELOAD_ESPELHO') {
                window.parent.location.reload();
            }
        };
        </script>
        """,
        height=0
    )