import streamlit as st
import datetime
import calendar
from core.database import carregar_militares_supabase
from modules.passos.passo3_efetivo import padronizar_graduacao, PESOS_HIERARQUIA
from modules.passos.passo1_unidade import renderizar_passo1
from modules.passos.passo2_turno import renderizar_passo2
from modules.passos.passo3_efetivo import renderizar_passo3
from modules.passos.passo4_calendario import renderizar_passo4
from modules.passos.passo5_quadro import renderizar_passo5
from modules.passos.passo6_exportar import renderizar_passo6
from modules.passos.passo7_banco_horas import renderizar_passo7

# NOVO: Importação do Mural
from modules.mural import renderizar_mural

def militar_tem_servico_em_outra_equipe(m_id, eq_atual, m_ano, m_mes, dia):
    for pair in st.session_state.get("militares_no_quadro_chaves", []):
        if isinstance(pair, (tuple, list)) and len(pair) == 2:
            m_k, eq_k = pair
            if str(m_k) == str(m_id) and eq_k != eq_atual:
                chave_outra = f"{m_id}_{eq_k}_{m_ano}_{m_mes:02d}_{dia:02d}"
                val = st.session_state["grade_escala_lancamentos"].get(chave_outra, "F")
                if val and val not in ["F", "D", "X", "", None]:
                    return val, eq_k
    return None, None

def aplicar_efetivo_ao_quadro():
    # Parâmetros de Auditoria e Permissões
    usr_logado = st.session_state.get("usuario_dados", {})
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil_str = str(usr_logado.get("perfil", "")).upper()
    eh_admin = "PROGRAMADOR" in cargo_str or "TESTADOR" in cargo_str or "ADMIN" in perfil_str or "DESENVOLVEDOR" in cargo_str
    
    escala_fechada = st.session_state.get("escala_fechada_auditoria", False)
    timezone_br = datetime.timezone(datetime.timedelta(hours=-3))
    hoje = datetime.datetime.now(timezone_br).date()

    st.session_state["lista_conflitos_pendentes"] = []
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    mod_ativa = st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso")
    eq_ativa = st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO")
    mils_sel = st.session_state.get("militares_selecionados_ids", [])
    dias_sel = set(st.session_state.get("dias_selecionados_passo4", []))
    num_dias = calendar.monthrange(m_ano, m_mes)[1]

    if not mils_sel:
        st.warning("⚠️ Selecione os militares da equipe atual no Passo 3 antes de aplicar!")
        return

    if "militares_no_quadro_chaves" not in st.session_state:
        st.session_state["militares_no_quadro_chaves"] = []

    conflitos_detectados = []
    dias_bloqueados_count = 0

    for m_id in mils_sel:
        m_obj = next((m for m in st.session_state.get("lista_militares", []) if str(m["id"]) == str(m_id)), None)
        nome_militar = f"{m_obj.get('posto_grad', '')} {m_obj.get('nome_guerra', '')}".strip() if m_obj else f"ID {m_id}"

        propostos = {}
        conflitos_militar = []
        dias_trabalho_validos = 0

        for d in range(1, num_dias + 1):
            try:
                data_alvo = datetime.date(m_ano, m_mes, d)
            except ValueError:
                continue
            
            if escala_fechada and not eh_admin and data_alvo < hoje:
                dias_bloqueados_count += 1
                continue 

            novo_val = None
            if mod_ativa == "Turno Único / Avulso":
                novo_val = st.session_state.get("horario_avulso_p2", "07:00 às 19:00") if d in dias_sel else "F"
            elif mod_ativa == "ADM (Seg-Sex)":
                h_norm = st.session_state.get("adm_h_norm", "08:00 às 12:00\n13:30 às 17:00")
                h_qua = st.session_state.get("adm_h_qua", "08:30 às 13:00")
                w = calendar.weekday(m_ano, m_mes, d)
                novo_val = (h_qua if w == 2 else h_norm) if (d in dias_sel and w < 5) else "F"
            elif mod_ativa == "Supervisão":
                h_dq = st.session_state.get("horario_sup_dom_qui", "15:00 às 21:00")
                h_ss = st.session_state.get("horario_sup_sex_sab", "18:00 às 00:00")
                w = calendar.weekday(m_ano, m_mes, d)
                novo_val = (h_ss if w in [4, 5] else h_dq) if d in dias_sel else "F"
            elif mod_ativa == "Ciclo 12x36":
                h_d = st.session_state.get("c36_h_dia", "07:00 às 19:00")
                h_n = st.session_state.get("c36_h_noite", "19:00 às 07:00")
                f_ini = st.session_state.get("c36_fase_ini", "Dia (Trabalho)")
                seq_map = {"Dia (Trabalho)": [h_d, "D", h_n, "D", "F"], "Descanso Pós-Dia": ["D", h_n, "D", "F", h_d], "Noite (Trabalho)": [h_n, "D", "F", h_d, "D"], "Descanso Pós-Noite": ["D", "F", h_d, "D", h_n], "Folga": ["F", h_d, "D", h_n, "D"]}
                val_c = seq_map.get(f_ini, [h_d, "D", h_n, "D", "F"])[(d - 1) % 5]
                novo_val = val_c if val_c in ["D", "F"] else (val_c if d in dias_sel else "F")
            elif mod_ativa == "Dobradinha (14D)":
                sem_ini = st.session_state.get("dob_sem_ini", "SEMANA A")
                h_sq = st.session_state.get("dob_h_sq", "14:00 às 00:00")
                h_ss = st.session_state.get("dob_h_ss", "18:00 às 04:00")
                h_dom = st.session_state.get("dob_h_dom", "18:00 às 02:00")
                eh_sem_a_ini = "SEMANA A" in sem_ini
                sem_iso_d1 = datetime.date(m_ano, m_mes, 1).isocalendar()[1]
                dt = datetime.date(m_ano, m_mes, d)
                w = dt.weekday()
                diff_s = dt.isocalendar()[1] - sem_iso_d1
                eh_sem_a = (diff_s % 2 == 0) if eh_sem_a_ini else (diff_s % 2 != 0)
                trabalha = (eh_sem_a and w in [0, 2, 5, 6]) or ((not eh_sem_a) and w in [1, 3, 4])
                h_app = h_sq if w in [0, 1, 2, 3] else (h_ss if w in [4, 5] else h_dom)
                novo_val = (h_app if d in dias_sel else "F") if trabalha else "F"
            elif mod_ativa == "Ciclo 12x72 (5D)":
                h_d = st.session_state.get("c72_h_dia", "06:00 às 18:00")
                h_n = st.session_state.get("c72_h_noite", "18:00 às 06:00")
                f_ini = st.session_state.get("c72_fase_ini", "Fase 1 (Dia)")
                seq_map = {"Fase 1 (Dia)": [h_d, h_n, "D", "D", "F"], "Fase 2 (Noite)": [h_n, "D", "D", "F", h_d], "Descanso 1": ["D", "D", "F", h_d, h_n], "Descanso 2": ["D", "F", h_d, h_n, "D"], "Folga": ["F", h_d, h_n, "D", "D"]}
                val_c = seq_map.get(f_ini, [h_d, h_n, "D", "D", "F"])[(d - 1) % 5]
                novo_val = val_c if val_c in ["D", "F"] else (val_c if d in dias_sel else "F")

            servico_outra, eq_outra = militar_tem_servico_em_outra_equipe(m_id, eq_ativa, m_ano, m_mes, d)

            if novo_val not in ["F", "D", None]:
                if servico_outra:
                    propostos[d] = "X"
                    conflitos_militar.append({"militar": nome_militar, "data": f"{d:02d}/{m_mes:02d}/{m_ano}", "servico_antigo": f"{servico_outra} ({eq_outra})", "tentativa": novo_val, "equipe_tentativa": eq_ativa})
                else:
                    propostos[d] = novo_val
                    dias_trabalho_validos += 1
            else:
                propostos[d] = novo_val

        if dias_trabalho_validos > 0 or not escala_fechada:
            par_militar_eq = (m_id, eq_ativa)
            if par_militar_eq not in st.session_state["militares_no_quadro_chaves"]:
                st.session_state["militares_no_quadro_chaves"].append(par_militar_eq)

            st.session_state["equipes_militar_map"][par_militar_eq] = eq_ativa

            for d, val_f in propostos.items():
                chave_equipe = f"{m_id}_{eq_ativa}_{m_ano}_{m_mes:02d}_{d:02d}"
                st.session_state["grade_escala_lancamentos"][chave_equipe] = val_f

            conflitos_detectados.extend(conflitos_militar)

    if dias_bloqueados_count > 0:
        st.info("🔒 Parte do lançamento ignorada: a escala está fechada e dias anteriores a hoje estão bloqueados.")

    st.session_state["militares_selecionados_ids"] = []
    for key in list(st.session_state.keys()):
        if "passo3" in key.lower() and isinstance(st.session_state[key], list):
            st.session_state[key] = []
    st.session_state["lista_conflitos_pendentes"] = conflitos_detectados

def exibir_modulo_escalas():
    st.markdown("""<style>div[data-testid="stContainer"] div[data-testid="stColumn"] button {height: 68px !important; min-height: 68px !important; padding: 4px !important; font-size: 13px !important; font-weight: 700 !important;}</style>""", unsafe_allow_html=True)
    st.title("📅 Módulo de Lançamento e Gestão de Escalas")
    st.caption("Montagem Incremental de Escalas com Auditoria Dinâmica Diária e Banco de Horas")
    st.divider()

    if "lista_equipes" not in st.session_state:
        st.session_state["lista_equipes"] = ["ADMINISTRAÇÃO", "SUPERVISÃO", "CPU", "RP", "TM ALPHA", "GEPAR"]
    if "equipe_ativa" not in st.session_state:
        st.session_state["equipe_ativa"] = "ADMINISTRAÇÃO"
    if "modalidade_turno_ativa" not in st.session_state:
        st.session_state["modalidade_turno_ativa"] = "Turno Único / Avulso"
    if "lista_militares" not in st.session_state:
        st.session_state["lista_militares"] = []
    if "militares_selecionados_ids" not in st.session_state:
        st.session_state["militares_selecionados_ids"] = []
    if "militares_no_quadro_chaves" not in st.session_state:
        st.session_state["militares_no_quadro_chaves"] = []
    if "dias_selecionados_passo4" not in st.session_state:
        st.session_state["dias_selecionados_passo4"] = []
    if "grade_escala_lancamentos" not in st.session_state:
        st.session_state["grade_escala_lancamentos"] = {}
    if "equipes_militar_map" not in st.session_state:
        st.session_state["equipes_militar_map"] = {}
    if "ordem_customizada_map" not in st.session_state:
        st.session_state["ordem_customizada_map"] = {}
    if "lista_conflitos_pendentes" not in st.session_state:
        st.session_state["lista_conflitos_pendentes"] = []

    if not st.session_state.get("lista_militares"):
        m_banco = carregar_militares_supabase()
        if m_banco:
            for m_b in m_banco:
                m_b["posto_grad"] = padronizar_graduacao(m_b.get("posto_grad", "SD"))
                m_b["peso"] = PESOS_HIERARQUIA.get(m_b["posto_grad"], 99)
            st.session_state["lista_militares"] = m_banco

    passo_sel = st.session_state.get("passo_escala_ativo", "VISUALIZAR TODOS")

    # Mapeamento do roteamento do Menu
    if passo_sel == "VISUALIZAR TODOS":
        renderizar_passo1()
        renderizar_passo2()
        renderizar_passo3()
        renderizar_passo4(aplicar_efetivo_ao_quadro)
        renderizar_passo5()
        renderizar_passo6()
        renderizar_passo7()
    elif passo_sel == "PASSO 1: Unidade & Equipes":
        renderizar_passo1()
    elif passo_sel == "PASSO 2: Turno & Horários":
        renderizar_passo2()
    elif passo_sel == "PASSO 3: Efetivo & Ausências":
        renderizar_passo3()
    elif passo_sel == "PASSO 4: Matriz Mensal":
        renderizar_passo4(aplicar_efetivo_ao_quadro)
    elif passo_sel == "PASSO 5: Quadro Geral":
        renderizar_passo5()
    elif passo_sel == "PASSO 6: Exportação & Auditoria":
        renderizar_passo6()
    elif passo_sel == "PASSO 7: Banco de Horas":
        renderizar_passo7()
    elif passo_sel == "🗣️ Mural & Trocas de Serviço":
        renderizar_mural()