import streamlit as st
import datetime
import calendar
import pandas as pd
import re
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

def carregar_escala_direto_supabase(m_ano, m_mes):
    if not supabase:
        return {}, [], {}, {}
    try:
        # Tenta a busca convertendo o mês para inteiro e garantindo compatibilidade
        mes_int = int(m_mes)
        ano_int = int(m_ano)
        
        res = supabase.table("escalas_mensais").select("matriz_dados").eq("ano", ano_int).eq("mes", mes_int).execute()
        
        if res and res.data and len(res.data) > 0:
            md = res.data[0].get("matriz_dados", {})
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
        st.error(f"Erro ao ler banco no Espelho: {ex}")
    return {}, [], {}, {}

def renderizar_modo_segunda_tela():
    """Renderiza a 2ª tela autônoma em tela cheia com atualização em tempo real."""
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
    
    # Tratamento rigoroso de conversão de query_params para inteiros
    raw_mes = params.get("mes", datetime.date.today().month)
    raw_ano = params.get("ano", datetime.date.today().year)

    if isinstance(raw_mes, list):
        raw_mes = raw_mes[0]
    if isinstance(raw_ano, list):
        raw_ano = raw_ano[0]

    try:
        m_mes = int(raw_mes)
    except (ValueError, TypeError):
        m_mes = datetime.date.today().month

    try:
        m_ano = int(raw_ano)
    except (ValueError, TypeError):
        m_ano = datetime.date.today().year

    st.markdown(f"### 🖥️ ESPELHO DA ESCALA - QUADRO 5 ({m_mes:02d}/{m_ano})")

    grade, chaves_existentes, bh_configs, ordem_map = carregar_escala_direto_supabase(m_ano, m_mes)
    militares = carregar_militares_supabase() or []
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

    colunas_dias = [(d, f"{'🔴 ' if calendar.weekday(m_ano, m_mes, d) in [5,6] else ''}{d:02d} {DIAS_SEMANA_SIGLAS[calendar.weekday(m_ano, m_mes, d)]}") for d in range(1, num_dias + 1)]
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
            val_bruto = grade.get(f"{m_id}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "")
            linha[col_name] = padronizar_entrada_espelho(val_bruto) if val_bruto != "" else ""

        matriz.append(linha)

    df_escala = pd.DataFrame(matriz)

    if not df_escala.empty:
        st.dataframe(
            df_escala,
            use_container_width=True,
            hide_index=True,
            height=800
        )
    else:
        st.info("💡 Nenhuma escala localizada no Supabase para este período.")

    components.html(
        """
        <script>
        setTimeout(function(){
            window.parent.location.reload();
        }, 3000);
        </script>
        """,
        height=0
    )