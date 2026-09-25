import streamlit as st
import datetime
import calendar

from core.database import supabase, carregar_militares_supabase, salvar_escala_mensal_supabase
from modules.escalas.passos.passo3_efetivo import padronizar_graduacao, PESOS_HIERARQUIA
from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS

SIGLAS_DIAS_NEUTROS = [
    "FER", "FERIAS", "FÉRIAS", "FE",
    "LTSP", "LM", "LMM",
    "ATEST", "ATESTADO", "ATE",
    "LUTO", "NUPCIAS", "NÚPCIAS", "LUT", "NUP", "DN", "DNT"
]

CORES_EQUIPES = {
    "CPU": "#a16207", 
    "RP": "#1e293b", 
    "SUPERVISÃO": "#b91c1c", 
    "ADMINISTRAÇÃO": "#0f766e", 
    "TM ALPHA": "#0369a1", 
    "GEPAR": "#047857",
    "A": "#1e3a8a",
    "B": "#065f46",
    "C": "#9a3412"
}

def obter_cor_equipe(eq):
    return CORES_EQUIPES.get(str(eq).upper().strip(), "#475569")

def calcular_duracao_turno_texto(val_str):
    """Calcula a duração do turno diretamente pelo código da legenda ou horário extenso."""
    v = str(val_str).upper().strip()
    if not v or v in ["F", "D", "X", "NAN", "NONE", "0"] or any(sigla in v for sigla in SIGLAS_DIAS_NEUTROS):
        return 0.0
    if "24" in v or "24X72" in v:
        return 24.0
    if "18" in v:
        return 18.0
    if "8" in v or "08" in v or "EXPEDIENTE" in v:
        return 8.0
    # Padrão para plantões de 12 horas (1, 2, RH, TPB, etc.)
    return 12.0

def verificar_trava_sobreposicao():
    st.session_state["lista_bloqueios_auditoria"] = []
    st.session_state["lista_avisos_descanso"] = []

def executar_auto_save_banco():
    """Salva a matriz de lançamentos no Supabase automaticamente."""
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
    grade_lancamentos = st.session_state.get("grade_escala_lancamentos", {})
    usr_logado = st.session_state.get("usuario_dados", {})
    
    operador = usr_logado.get("nome_guerra", "GESTOR")
    
    matriz_salvar = {
        "chaves_quadro": chaves_quadro,
        "grade_lancamentos": grade_lancamentos
    }
    
    salvar_escala_mensal_supabase(
        ano=m_ano,
        mes=m_mes,
        equipe_nome="GERAL",
        modalidade="GERAL",
        matriz_dados=matriz_salvar,
        elaborado_por=operador,
        homologado_por=operador,
        status="RASCUNHO"
    )

def renderizar_passo5():
    st.subheader("📋 PASSO 5: Quadro Geral de Lançamentos da Escala")
    st.caption("Insira os turnos/legendas (1, 2, RH) ou folgas (F, D). O saldo de horas é atualizado automaticamente.")

    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    num_dias_mes = calendar.monthrange(m_ano, m_mes)[1]

    mils_todos = st.session_state.get("lista_militares", []) or carregar_militares_supabase() or []
    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
    grade_lancamentos = st.session_state.get("grade_escala_lancamentos", {})

    # --- INSERIR MILITAR AO QUADRO ---
    with st.expander("➕ Adicionar Militar / Equipe ao Quadro Geral", expanded=False):
        c_add1, c_add2, c_add3 = st.columns([2, 2, 1])
        with c_add1:
            opts_mils = {str(m.get("id")): f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')} ({m.get('num_policia')})" for m in mils_todos}
            mil_sel_id = st.selectbox("Selecione o Militar:", options=list(opts_mils.keys()), format_func=lambda x: opts_mils[x], key="p5_sel_mil_add")
        with c_add2:
            equipe_sel = st.selectbox("Equipe / Subunidade:", options=["CPU", "RP", "A", "B", "C", "SUPERVISÃO", "ADMINISTRAÇÃO", "TM ALPHA", "GEPAR"], key="p5_sel_eq_add")
        with c_add3:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.button("➕ Inserir no Quadro", type="primary", use_container_width=True):
                pair = (mil_sel_id, equipe_sel)
                if pair not in chaves_quadro:
                    chaves_quadro.append(pair)
                    st.session_state["militares_no_quadro_chaves"] = chaves_quadro
                    executar_auto_save_banco()
                    st.success("Militar adicionado ao quadro!")
                    st.rerun()

    if not chaves_quadro:
        st.info("💡 Nenhum militar foi adicionado ao Quadro Geral. Adicione militares acima ou importe a escala no Passo 6.")
        return

    # --- ORDENAÇÃO E PREPARAÇÃO DOS DADOS ---
    mils_linhas_quadro = []
    for pair in chaves_quadro:
        if isinstance(pair, (tuple, list)) and len(pair) == 2:
            m_obj = next((m for m in mils_todos if str(m.get("id")).strip() == str(pair[0]).strip()), None)
            if m_obj:
                mils_linhas_quadro.append({
                    "id": str(pair[0]).strip(), 
                    "equipe": pair[1], 
                    "posto_grad": padronizar_graduacao(m_obj.get("posto_grad")), 
                    "nome_guerra": m_obj.get("nome_guerra", "MILITAR"), 
                    "num_policia": m_obj.get("num_policia", ""), 
                    "chave_linha": f"{pair[0]}_{pair[1]}"
                })

    mils_escala_ord = sorted(mils_linhas_quadro, key=lambda x: (
        st.session_state.get("ordem_customizada_map", {}).get(x["chave_linha"], 99), 
        PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99), 
        x["nome_guerra"]
    ))

    # --- MATRIZ INTERATIVA DE LANÇAMENTOS DO PASSO 5 ---
    st.markdown("### 🗓️ Matriz de Lançamentos Mensais")

    equipes_unicas = list(dict.fromkeys([m["equipe"] for m in mils_escala_ord]))

    for eq_nome in equipes_unicas:
        st.markdown(f"#### 🛡️ Equipe: **{eq_nome}**")
        mils_da_eq = [m for m in mils_escala_ord if m["equipe"] == eq_nome]

        for item in mils_da_eq:
            m_id = item["id"]
            pg = item["posto_grad"]
            ng = item["nome_guerra"]
            num_pol = item["num_policia"]
            
            c_info, c_dias, c_tot = st.columns([2.5, 9, 2])
            
            with c_info:
                st.markdown(f"**{pg} {ng}**\n\n`Nº {num_pol}`")
                if st.button("🗑️", key=f"btn_del_{m_id}_{eq_nome}", help="Remover militar"):
                    chaves_quadro = [p for p in chaves_quadro if not (str(p[0]) == str(m_id) and str(p[1]) == str(eq_nome))]
                    st.session_state["militares_no_quadro_chaves"] = chaves_quadro
                    executar_auto_save_banco()
                    st.rerun()

            total_horas = 0.0
            dias_neutros_cnt = 0

            with c_dias:
                cols_d = st.columns(num_dias_mes)
                for d in range(1, num_dias_mes + 1):
                    dia_sem_idx = calendar.weekday(m_ano, m_mes, d)
                    sigla_sem = DIAS_SEMANA_SIGLAS[dia_sem_idx]
                    key_cel = f"{m_id}_{eq_nome}_{m_ano}_{m_mes:02d}_{d:02d}"
                    val_atual = str(grade_lancamentos.get(key_cel, "F")).strip()

                    with cols_d[d - 1]:
                        st.caption(f"{d} {sigla_sem[:1]}")
                        novo_val = st.text_input(
                            f"D{d}", 
                            value=val_atual, 
                            key=f"inp_{key_cel}", 
                            label_visibility="collapsed"
                        ).strip().upper()

                        if novo_val != val_atual:
                            grade_lancamentos[key_cel] = novo_val
                            st.session_state["grade_escala_lancamentos"] = grade_lancamentos
                            executar_auto_save_banco()

                        # Computa horas prestadas e abate de dias neutros
                        v_str = str(novo_val).upper()
                        total_horas += calcular_duracao_turno_texto(v_str)

                        tokens_dia = set(v_str.replace("/", " ").split())
                        if any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                            dias_neutros_cnt += 1

            with c_tot:
                cfg_bh = st.session_state.get("bh_configs", {}).get(str(m_id), {})
                eh_reduzida = cfg_bh.get("reduzida", False)
                carga_base_mes = 80.0 if eh_reduzida else 160.0

                taxa_diaria = carga_base_mes / float(num_dias_mes)
                dias_efetivos = num_dias_mes - dias_neutros_cnt
                meta_efetiva = max(0.0, dias_efetivos * taxa_diaria)
                saldo_horas = total_horas - meta_efetiva

                st.markdown(f"**{total_horas:.0f}h / {meta_efetiva:.1f}h**")
                if saldo_horas >= 0:
                    st.markdown(f"<span style='color:green; font-weight:bold;'>+{saldo_horas:.1f}h</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span style='color:red; font-weight:bold;'>{saldo_horas:.1f}h</span>", unsafe_allow_html=True)
            st.divider()

    st.success("💾 As alterações no Quadro Geral são salvas automaticamente.")