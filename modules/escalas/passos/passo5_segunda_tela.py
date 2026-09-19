import streamlit as st
import datetime
import calendar
import pandas as pd
import time
import re

from core.database import (
    supabase,
    carregar_militares_supabase,
)

from modules.escalas.passos.passo3_efetivo import (
    PESOS_HIERARQUIA,
    padronizar_graduacao,
)

from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS

# Siglas de afastamentos e dias neutros
SIGLAS_DIAS_NEUTROS = {
    "F", "D", "X", "FER", "DOM", "FERIADO", "LM", "ATE", "FE", "LUT", "NUP", "DN", "DNT"
}

SIGLAS_ABATEM_META = {
    "F", "D", "X", "FER", "DOM", "FERIADO", "LM", "ATE", "FE", "LUT", "NUP", "DN", "DNT"
}

def padronizar_entrada_espelho(valor):
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

def extrair_intervalos_horarios(texto_celula, data_ref):
    if not texto_celula or str(texto_celula).strip().upper() in SIGLAS_DIAS_NEUTROS:
        return []

    padrao = re.findall(r'(\d{1,2}:\d{2})\s*(?:ÀS|AS|-|A)\s*(\d{1,2}:\d{2})', str(texto_celula).upper())
    intervalos = []

    for h_ini_str, h_fim_str in padrao:
        try:
            h_ini_p = [int(x) for x in h_ini_str.split(':')]
            h_fim_p = [int(x) for x in h_fim_str.split(':')]

            dt_ini = datetime.datetime(data_ref.year, data_ref.month, data_ref.day, h_ini_p[0], h_ini_p[1])
            dt_fim = datetime.datetime(data_ref.year, data_ref.month, data_ref.day, h_fim_p[0], h_fim_p[1])

            if dt_fim <= dt_ini:
                dt_fim += datetime.timedelta(days=1)

            intervalos.append((dt_ini, dt_fim))
        except Exception:
            continue

    return intervalos

def calcular_horas_efetivas(texto_celula, data_ref, eh_supervisao=False):
    """Calcula as horas com ganho noturno (23h-05h: +10min/h) e sobreaviso de supervisão."""
    intervalos = extrair_intervalos_horarios(texto_celula, data_ref)
    if not intervalos:
        return 0.0

    horas_presenciais_efetivas = 0.0
    minutos_presenciais_reais = 0.0

    for dt_ini, dt_fim in intervalos:
        dt_curr = dt_ini
        while dt_curr < dt_fim:
            dt_next = dt_curr + datetime.timedelta(minutes=1)
            minutos_presenciais_reais += 1.0

            hora_atual = dt_curr.hour
            is_noturno = (hora_atual >= 23 or hora_atual < 5)

            fator_minuto = (70.0 / 60.0) if is_noturno else 1.0
            horas_presenciais_efetivas += (1.0 / 60.0) * fator_minuto

            dt_curr = dt_next

    if eh_supervisao or "SUPERVISÃO" in str(texto_celula).upper():
        horas_presenciais_reais = minutos_presenciais_reais / 60.0
        horas_sobreaviso_restantes = max(0.0, 24.0 - horas_presenciais_reais)
        credito_sobreaviso = horas_sobreaviso_restantes * 0.25
        return horas_presenciais_efetivas + credito_sobreaviso

    return horas_presenciais_efetivas

def carregar_escala_direto_supabase(m_ano, m_mes):
    """Lê do banco sem passar por autenticação de login ou st.session_state."""
    if not supabase:
        return {}, [], {}, {}
    try:
        res = supabase.table("escalas_mensais").select("matriz_dados").eq("ano", m_ano).eq("mes", m_mes).execute()
        if res and res.data:
            md = res.data[0].get("matriz_dados", {})
            grade = md.get("grade_escala_lancamentos", {})
            chaves_raw = md.get("militares_no_quadro_chaves", [])
            chaves = [
                (str(p[0]), str(p[1])) for p in chaves_raw if isinstance(p, (tuple, list)) and len(p) == 2
            ]
            bh_cfg = md.get("bh_configs", {})
            ordem_map = md.get("ordem_customizada_map", {})
            return grade, chaves, bh_cfg, ordem_map
    except Exception as ex:
        print(f"Erro ao carregar segunda tela: {ex}")
    return {}, [], {}, {}

def renderizar_segunda_tela_passo5():
    """Desenha a Segunda Tela totalmente independente."""
    st.set_page_config(page_title="SIOP - Espelho do Quadro (2ª Tela)", layout="wide")

    # Oculta menus padrão do Streamlit
    st.markdown(
        """
        <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container { padding: 0.5rem 1rem 0rem 1rem !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

    params = st.query_params

    try:
        m_mes = int(params.get("mes", datetime.date.today().month))
    except Exception:
        m_mes = datetime.date.today().month

    try:
        m_ano = int(params.get("ano", datetime.date.today().year))
    except Exception:
        m_ano = datetime.date.today().year

    # Leitura direta da nuvem
    grade, chaves_existentes, bh_configs, ordem_map = carregar_escala_direto_supabase(m_ano, m_mes)

    militares = carregar_militares_supabase() or []
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
            v = padronizar_entrada_espelho(grade.get(f"{m_id}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "F"))
            
            if v in ["F", "", None] and any(str(p[0]) == str(m_id) and p[1] != eq and grade.get(f"{m_id}_{p[1]}_{m_ano}_{m_mes:02d}_{d:02d}") not in ["F", "D", "", None] for p in chaves_existentes if isinstance(p, (tuple, list)) and len(p) == 2):
                v = "X"
            
            linha[col_name] = v
            v_str = str(v).upper().strip()
            tokens_dia = set(v_str.replace("/", " ").split())
            
            # TRATAMENTO ESPECIAL DO DNT
            if any(sig in tokens_dia for sig in SIGLAS_ABATEM_META if sig not in ["F", "D", "X"]): 
                neutros += 1

            if v_str not in ["", "F", "D", "X"] and (not any(sig in tokens_dia for sig in SIGLAS_ABATEM_META if sig not in ["F", "D", "X"]) or "DNT" in tokens_dia): 
                dt_ref_dia = datetime.date(m_ano, m_mes, d)
                eh_sup = (eq == "SUPERVISÃO" or "SUPERVISÃO" in v_str)
                tot_h += calcular_horas_efetivas(v_str, dt_ref_dia, eh_supervisao=eh_sup)

        cfg_m = bh_configs.get(str(m_id), {})
        carga_base_mes = 80.0 if cfg_m.get("reduzida") else 160.0
        taxa_diaria = carga_base_mes / float(num_dias)
        
        dias_efetivos = num_dias - neutros
        meta_efetiva = max(0.0, dias_efetivos * taxa_diaria)
        saldo_exc = tot_h - meta_efetiva

        linha["HORAS / META"] = f"{tot_h:.1f}h / {meta_efetiva:.1f}h ({saldo_exc:+.1f}h)"
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
        st.info("💡 Nenhuma escala salva encontrada para o período selecionado.")

    # Atualiza a tela a cada 3 segundos
    time.sleep(3)
    st.rerun()

if __name__ == "__main__":
    renderizar_segunda_tela_passo5()