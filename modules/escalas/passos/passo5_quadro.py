import streamlit as st
import datetime
import calendar
import pandas as pd
import copy
import re

from core.database import (
    salvar_escala_mensal_supabase,
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

# ============================================================
# UTILITÁRIOS E PADRONIZAÇÃO
# ============================================================

def padronizar_entrada_quadro(valor):
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

def salvar_estado_undo():
    st.session_state.setdefault("pilha_undo", []).append({
        "grade": copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {})),
        "chaves": copy.deepcopy(st.session_state.get("militares_no_quadro_chaves", [])),
        "ordem": copy.deepcopy(st.session_state.get("ordem_customizada_map", {}))
    })
    if len(st.session_state["pilha_undo"]) > 10:
        st.session_state["pilha_undo"].pop(0)

# ============================================================
# PERSISTÊNCIA NO BANCO DE DADOS
# ============================================================

def executar_auto_save_banco():
    try:
        m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
        m_mes = st.session_state.get("mes_escala", datetime.date.today().month)

        chaves_norm = [
            (str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", [])
            if isinstance(p, (tuple, list)) and len(p) == 2
        ]

        matriz_dados = {
            "grade_escala_lancamentos": copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {})),
            "militares_no_quadro_chaves": chaves_norm,
            "ordem_customizada_map": copy.deepcopy(st.session_state.get("ordem_customizada_map", {})),
            "bh_configs": copy.deepcopy(st.session_state.get("bh_configs", {})),
            "ajuste_saldo_map": copy.deepcopy(st.session_state.get("ajuste_saldo_map", {})),
            "dias_selecionados_passo4": copy.deepcopy(st.session_state.get("dias_selecionados_passo4", [])),
        }

        salvar_escala_mensal_supabase(
            ano=m_ano,
            mes=m_mes,
            equipe_nome=st.session_state.get("equipe_ativa", "GERAL"),
            modalidade=st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso"),
            matriz_dados=matriz_dados,
            elaborado_por="GESTOR",
            homologado_por="GESTOR",
            status="RASCUNHO"
        )
        st.session_state["ultima_gravacao"] = datetime.datetime.now()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco de dados: {e}")
        return False

def carregar_escala_salva_banco():
    if not supabase:
        return False
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)

    try:
        res = supabase.table("escalas_mensais").select("matriz_dados").eq("ano", m_ano).eq("mes", m_mes).execute()
        if res and res.data:
            md = res.data[0].get("matriz_dados", {})
            st.session_state["grade_escala_lancamentos"] = md.get("grade_escala_lancamentos", {})
            chaves_raw = md.get("militares_no_quadro_chaves", [])
            st.session_state["militares_no_quadro_chaves"] = [
                (str(p[0]), str(p[1])) for p in chaves_raw if isinstance(p, (tuple, list)) and len(p) == 2
            ]
            st.session_state["ordem_customizada_map"] = md.get("ordem_customizada_map", {})
            st.session_state["bh_configs"] = md.get("bh_configs", {})
            st.session_state["ajuste_saldo_map"] = md.get("ajuste_saldo_map", {})
            st.session_state["dias_selecionados_passo4"] = md.get("dias_selecionados_passo4", [])
            st.session_state["chave_escala_carregada"] = f"{m_ano}_{m_mes:02d}"
            return True
        else:
            return False
    except Exception as ex:
        print(f"Aviso ao carregar do banco: {ex}")
        return False

# ============================================================
# CÁLCULO DA MATRIZ DA ESCALA (PASSO 1, 2, 3 E 4)
# ============================================================

def recalcular_escala_matriz():
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    mod_nome = st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso")
    eq_ativa = str(st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))
    num_dias = calendar.monthrange(m_ano, m_mes)[1]
    
    grade = st.session_state.get("grade_escala_lancamentos", {})
    dias_ativos = set(st.session_state.get("dias_selecionados_passo4", []))
    
    h_avulso = st.session_state.get("horario_avulso_p2", "07:00 às 19:00")
    h_adm_norm = st.session_state.get("adm_h_norm", "08:00 às 12:00\n13:30 às 17:00")
    h_adm_qua = st.session_state.get("adm_h_qua", "08:30 às 13:00")
    
    seq_36 = {"Dia (Trabalho)": [st.session_state.get("c36_h_dia", "07:00 às 19:00"), "D", st.session_state.get("c36_h_noite", "19:00 às 07:00"), "D", "F"]}.get(
        st.session_state.get("c36_fase_ini", "Dia (Trabalho)"), ["07:00 às 19:00", "D", "19:00 às 07:00", "D", "F"]
    )
    seq_72 = {"Fase 1 (Dia)": [st.session_state.get("c72_h_dia", "06:00 às 18:00"), st.session_state.get("c72_h_noite", "18:00 às 06:00"), "D", "D", "F"]}.get(
        st.session_state.get("c72_fase_ini", "Fase 1 (Dia)"), ["06:00 às 18:00", "18:00 às 06:00", "D", "D", "F"]
    )
    sem_iso_d1 = datetime.date(m_ano, m_mes, 1).isocalendar()[1]

    for pair in st.session_state.get("militares_no_quadro_chaves", []):
        if isinstance(pair, (tuple, list)) and len(pair) == 2 and str(pair[1]) == eq_ativa:
            m_id = str(pair[0])

            for d in range(1, num_dias + 1):
                k = f"{m_id}_{eq_ativa}_{m_ano}_{m_mes:02d}_{d:02d}"
                
                if any(sig in str(grade.get(k, "")).upper() for sig in SIGLAS_DIAS_NEUTROS if sig not in ["F", "D", "X"]):
                    continue

                valor_dia = "F"

                if mod_nome == "Turno Único / Avulso":
                    valor_dia = h_avulso if d in dias_ativos else "F"

                elif mod_nome == "ADM (Seg-Sex)":
                    w = calendar.weekday(m_ano, m_mes, d)
                    if w < 5 and d in dias_ativos:
                        valor_dia = h_adm_qua if w == 2 else h_adm_norm
                    else:
                        valor_dia = "F"

                elif mod_nome == "Ciclo 12x36":
                    val_c = seq_36[(d - 1) % 5]
                    valor_dia = val_c if (d in dias_ativos or val_c in ["D", "F"]) else "F"

                elif mod_nome == "Ciclo 12x72 (5D)":
                    val_c = seq_72[(d - 1) % 5]
                    valor_dia = val_c if (d in dias_ativos or val_c in ["D", "F"]) else "F"

                elif mod_nome == "Dobradinha (14D)":
                    w = calendar.weekday(m_ano, m_mes, d)
                    eh_sem_a = ((datetime.date(m_ano, m_mes, d).isocalendar()[1] - sem_iso_d1) % 2 == 0) if "SEMANA A" in st.session_state.get("dob_sem_ini", "SEMANA A") else ((datetime.date(m_ano, m_mes, d).isocalendar()[1] - sem_iso_d1) % 2 != 0)
                    trabalha = ((eh_sem_a and w in [0, 2, 5, 6]) or (not eh_sem_a and w in [1, 3, 4]))
                    if trabalha and d in dias_ativos:
                        valor_dia = (st.session_state.get("dob_h_sq", "14:00 às 00:00") if w in [0, 1, 2, 3] else (st.session_state.get("dob_h_ss", "18:00 às 04:00") if w in [4, 5] else st.session_state.get("dob_h_dom", "18:00 às 02:00")))
                    else:
                        valor_dia = "F"

                grade[k] = valor_dia

    st.session_state["grade_escala_lancamentos"] = grade

# ============================================================
# TELA PRINCIPAL (PASSO 5)
# ============================================================

def renderizar_passo5():
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)

    chave_periodo = f"{m_ano}_{m_mes:02d}"
    if st.session_state.get("chave_escala_carregada") != chave_periodo:
        carregar_escala_salva_banco()
        st.session_state["chave_escala_carregada"] = chave_periodo

    if st.session_state.get("atualizar_quadro_passo5", False):
        sel_ids = set(str(mid) for mid in st.session_state.get("militares_selecionados_ids", []))
        eq_ativa = str(st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))
        
        st.session_state["militares_no_quadro_chaves"] = [
            (str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", []) 
            if isinstance(p, (tuple, list)) and len(p) == 2 and (str(p[1]) != eq_ativa or str(p[0]) in sel_ids)
        ] + [(mid, eq_ativa) for mid in sel_ids if (mid, eq_ativa) not in set((str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", []) if isinstance(p, (tuple, list)) and len(p) == 2)]
        
        recalcular_escala_matriz()
        executar_auto_save_banco()
        st.session_state["atualizar_quadro_passo5"] = False

    militares = st.session_state.get("lista_militares") or carregar_militares_supabase() or []
    st.session_state["lista_militares"] = militares

    quadro_travado = st.session_state.get("toggle_trava_quadro", False)

    with st.expander("📌 PASSO 5: Quadro Mensal de Escalas e Carga Horária", expanded=True):
        # BARRA DE TOPO COMPACTA E OTIMIZADA
        c1, c2 = st.columns([1.8, 1.2], vertical_alignment="center")
        
        with c1:
            cnt_linhas = len(st.session_state.get('militares_no_quadro_chaves', []))
            st.markdown(f"👮‍♂️ **Linhas Ativas:** `{cnt_linhas}` &nbsp;|&nbsp; 💡 *Legenda `X` = serviço em outra equipe.*")
        
        with c2:
            if st.button("⚡ Aplicar Lançamentos e Atualizar Quadro", type="primary", use_container_width=True):
                st.session_state["atualizar_quadro_passo5"] = True
                st.rerun()

        st.markdown("<div style='margin-top: -8px;'></div>", unsafe_allow_html=True)
        st.divider()

        num_dias = calendar.monthrange(m_ano, m_mes)[1]
        chaves_existentes = st.session_state.get("militares_no_quadro_chaves", [])
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

        st.session_state.setdefault("ordem_customizada_map", {})
        for idx, item in enumerate(mils_linhas):
            st.session_state["ordem_customizada_map"].setdefault(item["chave_linha"], idx + 1)

        mils_ord = sorted(mils_linhas, key=lambda x: (st.session_state["ordem_customizada_map"].get(x["chave_linha"], 99), PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99), x["nome_guerra"]))

        # ============================================================
        # ⚡ PAINEL DE AJUSTE RÁPIDO / LANÇAMENTO EM LOTE
        # ============================================================
        with st.expander("⚡ Painel de Ajuste Rápido no Quadro (Lançamento em Lote)", expanded=False):
            if mils_ord and not quadro_travado:
                dict_mils = {f"[{m['equipe']}] {m['posto_grad']} {m['nome_guerra']} ({m['num_policia']})": m for m in mils_ord}
                
                c_f1, c_f2, c_f3 = st.columns([3, 2.5, 2])
                mils_sel_lote = c_f1.multiselect("Militar(es):", list(dict_mils.keys()), key="p5_lote_mils")
                
                dt_hoje = datetime.date(m_ano, m_mes, 1)
                datas_sel = c_f2.date_input(
                    "Selecione a(s) Data(s) no Calendário:", 
                    value=(dt_hoje, dt_hoje), 
                    min_value=datetime.date(m_ano, m_mes, 1), 
                    max_value=datetime.date(m_ano, m_mes, num_dias), 
                    format="DD/MM/YYYY", 
                    key="p5_cal_picker"
                )
                tipo_ev = c_f3.selectbox("Evento/Horário:", ["Horário Normal", "FE (Férias)", "LM (Licença)", "ATE (Atestado)", "D (Descanso)", "F (Folga)", "X (Outra Equipe)", "DN (Dia Neutro)", "DNT (Neutro Trab.)", "DIS (Dispensa)"], key="p5_tipo")

                if "Horário Normal" in tipo_ev or "DNT" in tipo_ev:
                    c_h1, c_h2, c_btn = st.columns([1.5, 1.5, 3])
                    with c_h1:
                        h_i = st.time_input("Início:", datetime.time(7, 0), key="p5_h_ini")
                    with c_h2:
                        h_f = st.time_input("Fim:", datetime.time(19, 0), key="p5_h_fim")
                    with c_btn:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        btn_aplicar_lote = st.button("⚡ Aplicar Alteração Direta", type="primary", use_container_width=True, key="btn_aplicar_lote_norm")
                    
                    val_final_lote = f"{h_i.strftime('%H:%M')} às {h_f.strftime('%H:%M')}" + (" (DNT)" if "DNT" in tipo_ev else "")
                else:
                    val_final_lote = tipo_ev.split()[0]
                    btn_aplicar_lote = st.button("⚡ Aplicar Alteração Direta", type="primary", use_container_width=True, key="btn_aplicar_lote_sigla")

                if btn_aplicar_lote:
                    dias_alvo = []
                    if isinstance(datas_sel, (tuple, list)):
                        d_start = datas_sel[0].day
                        d_end = datas_sel[1].day if len(datas_sel) > 1 else d_start
                        dias_alvo = list(range(d_start, d_end + 1))
                    elif isinstance(datas_sel, datetime.date):
                        dias_alvo = [datas_sel.day]

                    if mils_sel_lote and dias_alvo:
                        salvar_estado_undo()
                        grade_tmp = st.session_state.get("grade_escala_lancamentos", {})
                        cnt = 0
                        for label in mils_sel_lote:
                            it = dict_mils[label]
                            for d_a in dias_alvo:
                                ck = f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d_a:02d}"
                                grade_tmp[ck] = val_final_lote
                                cnt += 1
                        if cnt:
                            st.session_state["grade_escala_lancamentos"] = grade_tmp
                            executar_auto_save_banco()
                            st.success(f"✅ Alteração aplicada a {cnt} célula(s) com sucesso!")
                            st.rerun()

        # ============================================================
        # DATA EDITOR PRINCIPAL
        # ============================================================
        colunas_dias = [(d, f"{'🔴 ' if calendar.weekday(m_ano, m_mes, d) in [5,6] else ''}{d:02d} {DIAS_SEMANA_SIGLAS[calendar.weekday(m_ano, m_mes, d)]}") for d in range(1, num_dias + 1)]
        matriz = []
        grade = st.session_state.get("grade_escala_lancamentos", {})

        for idx_r, item in enumerate(mils_ord):
            m_id, eq, pg, ng, np = item["id"], item["equipe"], padronizar_graduacao(item["posto_grad"]), item["nome_guerra"], item["num_policia"]
            linha = {"ORDEM": int(st.session_state["ordem_customizada_map"].get(item["chave_linha"], idx_r + 1)), "EQUIPE": eq, "Nº POLÍCIA": np, "MILITAR": f"{pg} {ng}"}
            tot_h, neutros = 0.0, 0

            for d, col_name in colunas_dias:
                v = padronizar_entrada_quadro(grade.get(f"{m_id}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "F"))
                
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
            df_ed = st.data_editor(
                df_escala,
                use_container_width=True,
                hide_index=True,
                height=450,
                key="editor_escala_principal"
            )
            alt = False
            for idx_r, row in df_ed.iterrows():
                if idx_r < len(mils_ord):
                    it = mils_ord[idx_r]
                    
                    if st.session_state["ordem_customizada_map"].get(it["chave_linha"]) != int(row.get("ORDEM", idx_r + 1)):
                        salvar_estado_undo()
                        st.session_state["ordem_customizada_map"][it["chave_linha"]] = int(row.get("ORDEM", idx_r + 1))
                        alt = True

                    for d, col_name in colunas_dias:
                        vp = padronizar_entrada_quadro(str(row.get(col_name, "")).strip())
                        ck = f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d:02d}"
                        if padronizar_entrada_quadro(grade.get(ck, "")) != vp:
                            salvar_estado_undo()
                            grade[ck] = vp
                            alt = True

            if alt:
                st.session_state["grade_escala_lancamentos"] = grade
                executar_auto_save_banco()
                st.rerun()
        else:
            st.info("💡 Clique em '⚡ Aplicar Lançamentos e Atualizar Quadro' para montar a escala com os militares selecionados.")

        # ============================================================
        # BOTÕES DE AÇÃO
        # ============================================================
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        c_act1, c_act2 = st.columns(2)
        
        with c_act1:
            if st.button("🧹 Limpar Todo o Quadro", use_container_width=True, disabled=quadro_travado):
                salvar_estado_undo()
                st.session_state["grade_escala_lancamentos"] = {}
                st.session_state["militares_no_quadro_chaves"] = []
                executar_auto_save_banco()
                st.success("🧹 Quadro limpo com sucesso!")
                st.rerun()

        with c_act2:
            if st.button("💾 Salvar Rascunho no Banco", type="primary", use_container_width=True):
                if executar_auto_save_banco():
                    st.success("✅ Rascunho da escala salvo no Supabase com sucesso!")