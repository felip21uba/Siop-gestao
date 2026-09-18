import streamlit as st
import datetime
import calendar
import pandas as pd
import copy

from core.database import (
    supabase,
    carregar_militares_supabase,
)

from modules.escalas.passos.passo3_efetivo import (
    PESOS_HIERARQUIA,
    padronizar_graduacao,
)

from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS

SIGLAS_DIAS_NEUTROS = {
    "F", "D", "X", "FER", "DOM", "FERIADO", "LM", "ATE", "FE", "LUT", "NUP", "DN", "DNT"
}

def padronizar_entrada_quadro_espelho(valor):
    if valor is None or pd.isna(valor):
        return "F"
    v = str(valor).strip().upper()
    if not v or v in ["F", "FOLGA"]:
        return "F"
    if v in ["D", "DOM", "DOMINGO", "DESCANSO", "OFF"]:
        return "D"
    if v in ["X", "FER", "FERIADO"]:
        return "X"
    return str(valor).strip()

def carregar_dados_banco_espelho(m_ano, m_mes):
    """Leitura autônoma e segura diretamente do Supabase sem alterar sessão principal."""
    if not supabase:
        return {}, []
    try:
        res = supabase.table("escalas_mensais").select("matriz_dados").eq("ano", m_ano).eq("mes", m_mes).execute()
        if res and res.data:
            md = res.data[0].get("matriz_dados", {})
            grade = md.get("grade_escala_lancamentos", {})
            chaves_raw = md.get("militares_no_quadro_chaves", [])
            chaves = [
                (str(p[0]), str(p[1])) for p in chaves_raw if isinstance(p, (tuple, list)) and len(p) == 2
            ]
            return grade, chaves
    except Exception as ex:
        print(f"Aviso Segunda Tela (Banco): {ex}")
    return {}, []

def renderizar_segunda_tela_passo5():
    """Módulo 100% Autônomo para Espelhamento e Visualização Expandida do Passo 5."""
    st.set_page_config(page_title="SIOP - Espelho da Escala (Segunda Tela)", layout="wide")
    
    # Injeção de estilo para maximizar visualização em telas secundárias
    st.markdown(
        """
        <style>
        .stApp { margin: 0; padding: 0; }
        div[data-testid="stToolbar"] { visibility: hidden; }
        footer { visibility: hidden; }
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        </style>
        """,
        unsafe_allow_html=True
    )

    # BARRA SUPERIOR DE CONTROLE AUTÔNOMO
    c_t1, c_t2, c_t3, c_t4 = st.columns([2.5, 1.5, 1.5, 1.5], vertical_alignment="center")
    
    with c_t1:
        st.markdown("### 🖥️ SIOP - Painel de Monitoramento (Segunda Tela)")
    
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    
    with c_t2:
        fonte_dados = st.radio("Fonte dos Dados:", ["Memória Viva (Sessão)", "Supabase (Nuvem)"], horizontal=True, key="p5_espelho_fonte")
    
    with c_t3:
        auto_refresh = st.toggle("🔄 Auto-Atualizar (5s)", value=False, key="p5_espelho_refresh")

    with c_t4:
        if st.button("⚡ Atualizar Agora", type="primary", use_container_width=True):
            st.rerun()

    st.divider()

    # OBTER DADOS SEGUNDO A FONTE ESCOLHIDA
    if "Supabase" in fonte_dados:
        grade, chaves_existentes = carregar_dados_banco_espelho(m_ano, m_mes)
    else:
        grade = st.session_state.get("grade_escala_lancamentos", {})
        chaves_existentes = st.session_state.get("militares_no_quadro_chaves", [])

    militares = st.session_state.get("lista_militares") or carregar_militares_supabase() or []
    num_dias = calendar.monthrange(m_ano, m_mes)[1]

    mils_linhas = [
        {
            "id": str(p[0]),
            "equipe": str(p[1]),
            "posto_grad": m.get("posto_grad", "SD"),
            "nome_guerra": m.get("nome_guerra", "MILITAR"),
            "num_policia": m.get("num_policia", ""),
            "chave_linha": f"{p[0]}_{p[1]}"
        }
        for p in chaves_existentes if isinstance(p, (tuple, list)) and len(p) == 2
        for m in [next((x for x in militares if str(x.get("id")) == str(p[0])), {})] if m
    ]

    ordem_map = st.session_state.get("ordem_customizada_map", {})
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
        tot_h, neutros = 0.0, 0

        for d, col_name in colunas_dias:
            v = padronizar_entrada_quadro_espelho(grade.get(f"{m_id}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "F"))
            
            if v in ["F", "", None] and any(str(p[0]) == str(m_id) and p[1] != eq and grade.get(f"{m_id}_{p[1]}_{m_ano}_{m_mes:02d}_{d:02d}") not in ["F", "D", "", None] for p in chaves_existentes if isinstance(p, (tuple, list)) and len(p) == 2):
                v = "X"
            
            linha[col_name] = v
            v_str = str(v).upper().strip()
            if any(sig in set(v_str.replace("/", " ").split()) for sig in SIGLAS_DIAS_NEUTROS): 
                neutros += 1
            elif v_str not in ["", "F", "D", "X"]: 
                tot_h += 12.0

        cfg_bh = st.session_state.get("bh_configs", {}).get(str(m_id), {})
        meta = max(0.0, (num_dias - neutros) * ((80.0 if cfg_bh.get("reduzida") else 160.0) / float(num_dias)))
        exc = (tot_h + float(st.session_state.get("ajuste_saldo_map", {}).get(str(m_id), 0.0))) - meta
        linha["HORAS / META"] = f"⚠️ {tot_h:.1f}h / {meta:.1f}h (+{exc:.1f}h)" if exc > 0 else f"{tot_h:.1f}h / {meta:.1f}h"
        matriz.append(linha)

    df_escala = pd.DataFrame(matriz)

    if not df_escala.empty:
        # Exibição otimizada para monitor secundário (apenas leitura de alto contraste)
        st.dataframe(
            df_escala,
            use_container_width=True,
            hide_index=True,
            height=680
        )
    else:
        st.info("💡 Nenhuma escala ativa carregada para exibição no momento.")

    # REFRESH AUTOMÁTICO SE ATIVADO
    if auto_refresh:
        import time
        time.sleep(5)
        st.rerun()

if __name__ == "__main__":
    renderizar_segunda_tela_passo5()