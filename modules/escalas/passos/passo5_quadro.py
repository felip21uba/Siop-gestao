import streamlit as st
import datetime
import calendar
import pandas as pd
import copy
import re
from core.database import salvar_escala_mensal_supabase, supabase, carregar_militares_supabase
from modules.escalas.passos.passo3_efetivo import PESOS_HIERARQUIA, padronizar_graduacao
from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS
from utils.excel_escala_importer import processar_upload_escala_excel, escanear_legendas_unicas_excel, MAPA_CONVERSAO_LEGENDAS

SIGLAS_DIAS_NEUTROS = ["FER", "FERIAS", "FÉRIAS", "FE", "LTSP", "LM", "ATEST", "ATESTADO", "ATE", "LUTO", "NUPCIAS", "NÚPCIAS", "LUT", "NUP", "DN", "DNT"]

@st.dialog("🛡️ Auditoria de Lançamento de Escala", width="large")
def abrir_modal_auditoria_unificada(militar_nome, ignorados_bloqueados, pendentes_descanso, val_final, item_sel, m_ano, m_mes):
    st.markdown(f"### 👮‍♂️ Militar: **{militar_nome}**")
    if ignorados_bloqueados:
        st.error("🚨 **Lançamentos Ignorados (Sobreposição de Horários):**")
        st.caption("Os turnos abaixo NÃO foram aplicados devido a choque de horário:")
        for b in ignorados_bloqueados:
            st.markdown(f"• **Dia {b['dia']:02d}:** Já escalado na equipe **{b['equipe']}** ({b['horario']})")
        st.divider()

    if pendentes_descanso:
        st.warning("⚠️ **Aviso de Descanso Interjornada Insuficiente (< 8 Horas):**")
        for a in pendentes_descanso:
            st.markdown(f"• **Dia {a['dia']:02d}:** {a['mensagem']}")
        c_conf1, c_conf2 = st.columns(2)
        with c_conf1:
            if st.button("✅ Confirmar Lançamento com Descanso Reduzido", type="primary", use_container_width=True):
                salvar_estado_undo()
                m_id, eq = item_sel.get('id'), item_sel.get('equipe')
                for a in pendentes_descanso:
                    if m_id and eq:
                        st.session_state["grade_escala_lancamentos"][f"{m_id}_{eq}_{m_ano}_{m_mes:02d}_{a['dia']:02d}"] = val_final
                st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                registrar_log_auditoria("Descanso Reduzido Confirmado", f"Militar {militar_nome} escalado com descanso reduzido.")
                executar_auto_save_banco()
                st.rerun()
        with c_conf2:
            if st.button("❌ Manter Apenas os Dias Válidos", use_container_width=True):
                st.rerun()
    else:
        st.success("✅ Os dias válidos e sem conflito foram aplicados com sucesso!")
        if st.button("OK, Fechar", type="primary", use_container_width=True):
            st.rerun()

def salvar_estado_undo():
    st.session_state.setdefault("pilha_undo", []).append({
        "grade": copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {})),
        "chaves": copy.deepcopy(st.session_state.get("militares_no_quadro_chaves", [])),
        "ordem": copy.deepcopy(st.session_state.get("ordem_customizada_map", {})),
        "bh_configs": copy.deepcopy(st.session_state.get("bh_configs", {})),
        "ajuste_saldo_map": copy.deepcopy(st.session_state.get("ajuste_saldo_map", {})),
        "dias_avulsos": copy.deepcopy(st.session_state.get("dias_selecionados_passo4", []))
    })
    if len(st.session_state["pilha_undo"]) > 10: st.session_state["pilha_undo"].pop(0)

def desfazer_ultima_acao():
    if st.session_state.get("pilha_undo"):
        snap = st.session_state["pilha_undo"].pop()
        st.session_state["grade_escala_lancamentos"] = snap["grade"]
        st.session_state["militares_no_quadro_chaves"] = snap["chaves"]
        st.session_state["ordem_customizada_map"] = snap["ordem"]
        st.session_state["bh_configs"] = snap.get("bh_configs", {})
        st.session_state["ajuste_saldo_map"] = snap.get("ajuste_saldo_map", {})
        st.session_state["dias_selecionados_passo4"] = snap.get("dias_avulsos", [])
        st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
        registrar_log_auditoria("Desfazer Ação", "Operador reverteu a última alteração.")
        executar_auto_save_banco()
        return True
    return False

def registrar_log_auditoria(acao, detalhe):
    usr = st.session_state.get("usuario_dados", {})
    dt_agora = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M:%S")
    st.session_state.setdefault("logs_auditoria_lista", []).insert(0, {
        "data_hora": dt_agora,
        "usuario": f"{usr.get('cargo_funcao', usr.get('perfil', 'GESTOR'))} {usr.get('nome_guerra', usr.get('nome', 'OPERADOR'))}".strip(),
        "acao": acao, "detalhe": detalhe
    })

def padronizar_entrada_quadro(valor):
    if not valor: return "F"
    v = str(valor).strip().upper()
    return "D" if v in ["OFF", "DESCANSO"] else ("F" if v in ["FOLGA"] else valor)

def extrair_datetime_de_string_turno(ano, mes, dia, str_horario):
    if not str_horario or str(str_horario).strip().upper() in SIGLAS_DIAS_NEUTROS + ["F", "D", "X", "DIS", "OFF", "DESCANSO", "FOLGA", "NONE", "NAN"]:
        return None, None
    m = re.findall(r'\d+', str(str_horario).strip())
    if len(m) < 2: return None, None
    try:
        h_i, min_i = int(m[0]), int(m[1]) if len(m) > 1 else 0
        h_f, min_f = (int(m[-2]), int(m[-1])) if len(m) >= 4 else (int(m[1]) if len(m) == 2 else int(m[2]), int(m[2]) if len(m) == 3 else 0)
        dt_ini = datetime.datetime(ano, mes, dia, h_i, min_i)
        dt_fim = dt_ini + datetime.timedelta(days=1) if (h_f < h_i or (h_f == h_i and min_f <= min_i)) else dt_ini
        return dt_ini, dt_fim.replace(hour=h_f, minute=min_f)
    except Exception: return None, None

def auditar_escalacao_militar(m_id, m_ano, m_mes, d_alvo, val_novo, dict_grade, eq_alvo=None):
    dt_novo_ini, dt_novo_fim = extrair_datetime_de_string_turno(m_ano, m_mes, d_alvo, val_novo)
    if not dt_novo_ini: return "OK", "", {}
    prefixo = f"{m_id}_"
    for k, val_ex in dict_grade.items():
        if k.startswith(prefixo):
            parts = k[len(prefixo):].rsplit("_", 3)
            if len(parts) == 4 and not (eq_alvo and parts[0] == str(eq_alvo) and int(parts[3]) == d_alvo):
                eq_ex, a_ex, m_ex, d_ex = parts[0], int(parts[1]), int(parts[2]), int(parts[3])
                if a_ex == m_ano and m_ex == m_mes:
                    dt_ex_ini, dt_ex_fim = extrair_datetime_de_string_turno(m_ano, m_mes, d_ex, val_ex)
                    if dt_ex_ini and dt_novo_ini < dt_ex_fim and dt_novo_fim > dt_ex_ini:
                        return "BLOQUEADO", f"Choque de Horário no dia {d_ex:02d} ({val_ex}) na equipe {eq_ex}.", {"dia": d_ex, "equipe": eq_ex, "horario": val_ex}
                    if dt_ex_ini and d_ex == d_alvo:
                        desc = (dt_novo_ini - dt_ex_fim if dt_novo_ini >= dt_ex_fim else dt_ex_ini - dt_novo_fim).total_seconds() / 3600.0
                        if 0 <= desc < 8.0:
                            return "AVISO", f"Descanso reduzido para {desc:.1f}h na equipe {eq_ex}.", {"dia": d_ex, "equipe": eq_ex}
    return "OK", "", {}

def executar_auto_save_banco():
    m_mes, m_ano = st.session_state.get("mes_escala", datetime.date.today().month), st.session_state.get("ano_escala", datetime.date.today().year)
    usr = st.session_state.get("usuario_dados", {})
    salvar_escala_mensal_supabase(
        ano=m_ano, mes=m_mes, equipe_nome=st.session_state.get("equipe_ativa", "GERAL"),
        modalidade=st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso"),
        matriz_dados={
            "grade_escala_lancamentos": st.session_state.get("grade_escala_lancamentos", {}),
            "militares_no_quadro_chaves": [(str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", []) if len(p) == 2],
            "ordem_customizada_map": st.session_state.get("ordem_customizada_map", {}),
            "bh_configs": st.session_state.get("bh_configs", {}),
            "ajuste_saldo_map": st.session_state.get("ajuste_saldo_map", {}),
            "dias_selecionados_passo4": st.session_state.get("dias_selecionados_passo4", []),
            "horario_avulso_p2": st.session_state.get("horario_avulso_p2", "07:00 às 19:00")
        },
        elaborado_por=usr.get("nome_guerra") or "OPERADOR", homologado_por=usr.get("nome_guerra") or "OPERADOR", status="RASCUNHO"
    )
    st.session_state["exibir_toast_autosave"] = True

def carregar_escala_salva_banco():
    if not supabase: return
    m_mes, m_ano = st.session_state.get("mes_escala", datetime.date.today().month), st.session_state.get("ano_escala", datetime.date.today().year)
    try:
        res = supabase.table("escalas_mensais").select("matriz_dados").eq("ano", m_ano).eq("mes", m_mes).execute()
        if res and res.data:
            md = res.data[0].get("matriz_dados", {})
            st.session_state["grade_escala_lancamentos"] = md.get("grade_escala_lancamentos", {})
            st.session_state["ordem_customizada_map"] = md.get("ordem_customizada_map", {})
            st.session_state["bh_configs"] = md.get("bh_configs", {})
            st.session_state["ajuste_saldo_map"] = md.get("ajuste_saldo_map", {})
            st.session_state["dias_selecionados_passo4"] = md.get("dias_selecionados_passo4", [])
            st.session_state["horario_avulso_p2"] = md.get("horario_avulso_p2", "07:00 às 19:00")
            st.session_state["militares_no_quadro_chaves"] = [(str(p[0]), str(p[1])) for p in md.get("militares_no_quadro_chaves", []) if len(p) == 2]
        else:
            st.session_state["grade_escala_lancamentos"], st.session_state["militares_no_quadro_chaves"] = {}, []
        st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
    except Exception as ex: print(f"Aviso carregar: {ex}")

def recalcular_escala_matriz():
    m_mes, m_ano = st.session_state.get("mes_escala", datetime.date.today().month), st.session_state.get("ano_escala", datetime.date.today().year)
    mod_nome, eq_ativa = st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso"), str(st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))
    num_dias = calendar.monthrange(m_ano, m_mes)[1]
    grade = st.session_state.get("grade_escala_lancamentos", {})
    
    for pair in st.session_state.get("militares_no_quadro_chaves", []):
        if len(pair) == 2 and str(pair[1]) == eq_ativa:
            m_id_k = str(pair[0])
            for d_k in range(1, num_dias + 1):
                k_cell = f"{m_id_k}_{eq_ativa}_{m_ano}_{m_mes:02d}_{d_k:02d}"
                if not any(sig in str(grade.get(k_cell, "")).upper() for sig in SIGLAS_DIAS_NEUTROS): grade.pop(k_cell, None)

    h_avulso = st.session_state.get("horario_avulso_p2", "07:00 às 19:00")
    seq_36 = {"Dia (Trabalho)": [st.session_state.get("c36_h_dia", "07:00 às 19:00"), "D", st.session_state.get("c36_h_noite", "19:00 às 07:00"), "D", "F"]}.get(st.session_state.get("c36_fase_ini", "Dia (Trabalho)"), ["07:00 às 19:00", "D", "19:00 às 07:00", "D", "F"])
    seq_72 = {"Fase 1 (Dia)": [st.session_state.get("c72_h_dia", "06:00 às 18:00"), st.session_state.get("c72_h_noite", "18:00 às 06:00"), "D", "D", "F"]}.get(st.session_state.get("c72_fase_ini", "Fase 1 (Dia)"), ["06:00 às 18:00", "18:00 às 06:00", "D", "D", "F"])
    sem_iso_d1 = datetime.date(m_ano, m_mes, 1).isocalendar()[1]

    bloqueios = []
    for pair in st.session_state.get("militares_no_quadro_chaves", []):
        if len(pair) == 2 and str(pair[1]) == eq_ativa:
            m_id = str(pair[0])
            m_obj = next((m for m in st.session_state.get("lista_militares", []) if str(m.get("id")) == m_id), None)
            m_nome = f"{padronizar_graduacao(m_obj.get('posto_grad', 'SD'))} {m_obj.get('nome_guerra', 'MILITAR')}" if m_obj else "MILITAR"

            for d in range(1, num_dias + 1):
                k = f"{m_id}_{eq_ativa}_{m_ano}_{m_mes:02d}_{d:02d}"
                if any(sig in str(grade.get(k, "")).upper() for sig in SIGLAS_DIAS_NEUTROS): continue
                valor_dia = "F"
                if mod_nome == "Turno Único / Avulso": valor_dia = h_avulso if d in set(st.session_state.get("dias_selecionados_passo4", [])) else "F"
                elif mod_nome == "ADM (Seg-Sex)": valor_dia = (st.session_state.get("adm_h_qua", "08:30 às 13:00") if calendar.weekday(m_ano, m_mes, d) == 2 else st.session_state.get("adm_h_norm", "08:00 às 12:00\n13:30 às 17:00")) if calendar.weekday(m_ano, m_mes, d) < 5 else "F"
                elif mod_nome == "Ciclo 12x36": valor_dia = seq_36[(d - 1) % 5]
                elif mod_nome == "Ciclo 12x72 (5D)": valor_dia = seq_72[(d - 1) % 5]
                elif mod_nome == "Dobradinha (14D)":
                    w = calendar.weekday(m_ano, m_mes, d)
                    eh_sem_a = ((datetime.date(m_ano, m_mes, d).isocalendar()[1] - sem_iso_d1) % 2 == 0) if "SEMANA A" in st.session_state.get("dob_sem_ini", "SEMANA A") else ((datetime.date(m_ano, m_mes, d).isocalendar()[1] - sem_iso_d1) % 2 != 0)
                    valor_dia = (st.session_state.get("dob_h_sq", "14:00 às 00:00") if w in [0, 1, 2, 3] else (st.session_state.get("dob_h_ss", "18:00 às 04:00") if w in [4, 5] else st.session_state.get("dob_h_dom", "18:00 às 02:00"))) if ((eh_sem_a and w in [0, 2, 5, 6]) or (not eh_sem_a and w in [1, 3, 4])) else "F"

                status, _, det = auditar_escalacao_militar(m_id, m_ano, m_mes, d, valor_dia, grade, eq_alvo=eq_ativa)
                if status == "BLOQUEADO": 
                    valor_dia = "X"
                    bloqueios.append({"militar": m_nome, "dia": d, "equipe": det.get("equipe", "N/I"), "horario": det.get("horario", "N/I")})
                grade[k] = valor_dia

    st.session_state["grade_escala_lancamentos"] = grade
    if bloqueios: st.session_state["auditoria_pendente_popup"] = {"militar_nome": bloqueios[0]["militar"], "ignorados": bloqueios, "descanso": [], "val_final": "X", "item_sel": {}, "m_ano": m_ano, "m_mes": m_mes}

@st.dialog("📥 Importar Escala Pronta via Excel", width="large")
def abrir_modal_importar_escala_excel():
    arq = st.file_uploader("Selecione XLSX/XLS:", type=["xlsx", "xls"], key="uploader_escala_excel_modal")
    m_mes, m_ano = st.session_state.get("mes_escala", datetime.date.today().month), st.session_state.get("ano_escala", datetime.date.today().year)
    if arq:
        legendas = escanear_legendas_unicas_excel(arq, m_ano, m_mes)
        mapa_custom = {leg: st.text_input(f"Sigla '{leg}' = ", value=MAPA_CONVERSAO_LEGENDAS.get(leg, "07:00 às 19:00"), key=f"leg_{leg}") for leg in legendas}
        if st.button("🚀 Carregar no Quadro", type="primary", use_container_width=True):
            salvar_estado_undo()
            suc, msg, n_enc = processar_upload_escala_excel(arq, m_ano, m_mes, mapa_custom, st.checkbox("🧹 Limpar atual", value=True))
            if suc:
                st.success(msg)
                if n_enc: st.warning(f"⚠️ Não encontrados: {n_enc}")
                st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                executar_auto_save_banco()
                st.rerun()

def renderizar_passo5():
    if st.session_state.get("auditoria_pendente_popup"):
        p = st.session_state.pop("auditoria_pendente_popup")
        abrir_modal_auditoria_unificada(p["militar_nome"], p["ignorados"], p["descanso"], p["val_final"], p["item_sel"], p["m_ano"], p["m_mes"])

    m_mes, m_ano = st.session_state.get("mes_escala", datetime.date.today().month), st.session_state.get("ano_escala", datetime.date.today().year)
    if st.session_state.get("chave_escala_carregada") != f"{m_ano}_{m_mes:02d}":
        carregar_escala_salva_banco()
        st.session_state["chave_escala_carregada"] = f"{m_ano}_{m_mes:02d}"

    if st.session_state.get("atualizar_quadro_passo5", False):
        sel_ids, eq_ativa = set(str(mid) for mid in st.session_state.get("militares_selecionados_ids", [])), str(st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))
        st.session_state["militares_no_quadro_chaves"] = [(str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", []) if str(p[1]) != eq_ativa or str(p[0]) in sel_ids] + [(mid, eq_ativa) for mid in sel_ids if (mid, eq_ativa) not in set((str(p[0]), str(p[1])) for p in st.session_state.get("militares_no_quadro_chaves", []))]
        recalcular_escala_matriz()
        st.session_state["atualizar_quadro_passo5"] = False

    quadro_travado = st.session_state.get("toggle_trava_quadro", False)
    
    with st.expander("📌 PASSO 5: Quadro Mensal de Escalas e Carga Horária", expanded=True):
        c_i1, c_i2 = st.columns([3, 1])
        c_i1.info(f"👮‍♂️ **Linhas Ativas:** `{len(st.session_state.get('militares_no_quadro_chaves', []))}` | 💡 *Legenda `X` indica serviço ativo em outra equipe.*")
        if c_i2.button("📥 Importar Excel", type="primary", use_container_width=True): abrir_modal_importar_escala_excel()
        if st.button("⚡ Aplicar Lançamentos e Atualizar Quadro", type="primary", use_container_width=True):
            st.session_state["atualizar_quadro_passo5"] = True
            st.rerun()

        num_dias = calendar.monthrange(m_ano, m_mes)[1]
        mils_todos = st.session_state.get("lista_militares", [])
        mils_linhas = [{"id": str(p[0]), "equipe": str(p[1]), "posto_grad": m.get("posto_grad", "SD"), "nome_guerra": m.get("nome_guerra", "MILITAR"), "num_policia": m.get("num_policia", ""), "chave_linha": f"{p[0]}_{p[1]}"} for p in st.session_state.get("militares_no_quadro_chaves", []) if len(p) == 2 for m in [next((x for x in mils_todos if str(x.get("id")) == str(p[0])), {})] if m]

        st.session_state.setdefault("ordem_customizada_map", {})
        for idx, item in enumerate(mils_linhas): st.session_state["ordem_customizada_map"].setdefault(item["chave_linha"], idx + 1)
        mils_ord = sorted(mils_linhas, key=lambda x: (st.session_state["ordem_customizada_map"].get(x["chave_linha"], 99), PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99), x["nome_guerra"]))

        with st.expander("⚡ Painel de Ajuste Rápido no Quadro (Lançamento em Lote)", expanded=False):
            if mils_ord and not quadro_travado:
                dict_mils = {f"[{m['equipe']}] {m['posto_grad']} {m['nome_guerra']} ({m['num_policia']})": m for m in mils_ord}
                c_f1, c_f2, c_f3 = st.columns([3, 2.5, 2])
                mils_sel_lote = c_f1.multiselect("Militar(es):", list(dict_mils.keys()), key="p5_lote_mils")
                
                dt_hoje = datetime.date(m_ano, m_mes, 1)
                datas_sel = c_f2.date_input("Selecione a(s) Data(s) no Calendário:", value=(dt_hoje, dt_hoje), min_value=datetime.date(m_ano, m_mes, 1), max_value=datetime.date(m_ano, m_mes, calendar.monthrange(m_ano, m_mes)[1]), key="p5_cal_picker")
                tipo_ev = c_f3.selectbox("Evento/Horário:", ["Horário Normal", "FE (Férias)", "LM (Licença)", "ATE (Atestado)", "D (Descanso)", "F (Folga)", "X (Outra Equipe)", "DN (Dia Neutro)", "DNT (Neutro Trab.)", "DIS (Dispensa)"], key="p5_tipo")

                if "Horário Normal" in tipo_ev or "DNT" in tipo_ev:
                    h_i, h_f = st.time_input("Início:", datetime.time(7, 0)), st.time_input("Fim:", datetime.time(19, 0))
                    val_final = f"{h_i.strftime('%H:%M')} às {h_f.strftime('%H:%M')}" + (" (DNT)" if "DNT" in tipo_ev else "")
                else: val_final = tipo_ev.split()[0]

                if st.button("⚡ Aplicar Alteração Direta", type="primary", use_container_width=True):
                    dias_alvo = []
                    if isinstance(datas_sel, (tuple, list)):
                        d_start = datas_sel[0].day
                        d_end = datas_sel[1].day if len(datas_sel) > 1 else d_start
                        dias_alvo = list(range(d_start, d_end + 1))
                    elif isinstance(datas_sel, datetime.date):
                        dias_alvo = [datas_sel.day]

                    if mils_sel_lote and dias_alvo:
                        salvar_estado_undo()
                        bloq, avisos, cnt = [], [], 0
                        for label in mils_sel_lote:
                            it = dict_mils[label]
                            for d_a in dias_alvo:
                                st_aud, msg_aud, det = auditar_escalacao_militar(it["id"], m_ano, m_mes, d_a, val_final, st.session_state["grade_escala_lancamentos"], eq_alvo=it["equipe"])
                                if st_aud == "BLOQUEADO": bloq.append({"militar": it["nome_guerra"], "dia": d_a, "equipe": det.get("equipe"), "horario": det.get("horario")})
                                elif st_aud == "AVISO": avisos.append({"militar": it["nome_guerra"], "dia": d_a, "mensagem": msg_aud})
                                else:
                                    st.session_state["grade_escala_lancamentos"][f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d_a:02d}"] = val_final
                                    cnt += 1
                        if cnt:
                            st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                            executar_auto_save_banco()
                        if bloq or avisos:
                            st.session_state["auditoria_pendente_popup"] = {"militar_nome": "Lote", "ignorados": bloq, "descanso": avisos, "val_final": val_final, "item_sel": {}, "m_ano": m_ano, "m_mes": m_mes}
                        st.rerun()

        colunas_dias = [(d, f"{'🔴 ' if calendar.weekday(m_ano, m_mes, d) in [5,6] else ''}{d:02d} {DIAS_SEMANA_SIGLAS[calendar.weekday(m_ano, m_mes, d)]}") for d in range(1, num_dias + 1)]
        matriz = []
        for idx_r, item in enumerate(mils_ord):
            m_id, eq, pg, ng, np = item["id"], item["equipe"], padronizar_graduacao(item["posto_grad"]), item["nome_guerra"], item["num_policia"]
            linha = {"ORDEM": int(st.session_state["ordem_customizada_map"].get(item["chave_linha"], idx_r + 1)), "EQUIPE": eq, "Nº POLÍCIA": np, "MILITAR": f"{pg} {ng}"}
            tot_h, neutros = 0.0, 0

            for d, col_name in colunas_dias:
                v = padronizar_entrada_quadro(st.session_state["grade_escala_lancamentos"].get(f"{m_id}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "F"))
                if v in ["F", "", None] and any(str(p[0]) == str(m_id) and p[1] != eq and extrair_datetime_de_string_turno(m_ano, m_mes, d, st.session_state["grade_escala_lancamentos"].get(f"{m_id}_{p[1]}_{m_ano}_{m_mes:02d}_{d:02d}"))[0] for p in st.session_state.get("militares_no_quadro_chaves", [])): v = "X"
                linha[col_name] = v
                v_str = str(v).upper().strip()
                if any(sig in set(v_str.replace("/", " ").split()) for sig in SIGLAS_DIAS_NEUTROS): neutros += 1
                elif v_str not in ["", "F", "D", "X"]: tot_h += 12.0

            cfg_bh = st.session_state.get("bh_configs", {}).get(str(m_id), {})
            meta = max(0.0, (num_dias - neutros) * ((80.0 if cfg_bh.get("reduzida") else 160.0) / float(num_dias)))
            exc = (tot_h + float(st.session_state.get("ajuste_saldo_map", {}).get(str(m_id), 0.0))) - meta
            linha["HORAS / META"] = f"⚠️ {tot_h:.1f}h / {meta:.1f}h (+{exc:.1f}h)" if exc > 0 else f"{tot_h:.1f}h / {meta:.1f}h"
            matriz.append(linha)

        df_escala = pd.DataFrame(matriz)
        if not df_escala.empty and not quadro_travado:
            df_ed = st.data_editor(df_escala, use_container_width=True, hide_index=True, height=450, key=f"editor_v{st.session_state['quadro_versao']}")
            alt = False
            for idx_r, row in df_ed.iterrows():
                if idx_r < len(mils_ord):
                    it = mils_ord[idx_r]
                    if st.session_state["ordem_customizada_map"].get(it["chave_linha"]) != int(row.get("ORDEM", idx_r + 1)):
                        salvar_estado_undo(); st.session_state["ordem_customizada_map"][it["chave_linha"]] = int(row.get("ORDEM", idx_r + 1)); alt = True
                    for d, col_name in colunas_dias:
                        vp = padronizar_entrada_quadro(str(row.get(col_name, "")).strip())
                        ck = f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d:02d}"
                        if padronizar_entrada_quadro(st.session_state["grade_escala_lancamentos"].get(ck, "")) != vp:
                            st_aud, msg_aud, det = auditar_escalacao_militar(it['id'], m_ano, m_mes, d, vp, st.session_state["grade_escala_lancamentos"], eq_alvo=it['equipe'])
                            if st_aud != "OK":
                                st.session_state["auditoria_pendente_popup"] = {"militar_nome": f"{it['posto_grad']} {it['nome_guerra']}", "ignorados": [{"dia": d, "equipe": det.get("equipe"), "horario": det.get("horario")}] if st_aud == "BLOQUEADO" else [], "descanso": [{"dia": d, "mensagem": msg_aud}] if st_aud == "AVISO" else [], "val_final": vp, "item_sel": it, "m_ano": m_ano, "m_mes": m_mes}
                                alt = True; st.rerun()
                            else:
                                salvar_estado_undo(); st.session_state["grade_escala_lancamentos"][ck] = vp; alt = True
            if alt:
                st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                executar_auto_save_banco(); st.rerun()

        c_act1, c_act2 = st.columns(2)
        with c_act1:
            if st.button("🧹 Limpar Todo o Quadro", use_container_width=True, disabled=quadro_travado):
                salvar_estado_undo(); st.session_state["grade_escala_lancamentos"], st.session_state["militares_no_quadro_chaves"] = {}, []
                executar_auto_save_banco(); st.rerun()
        with c_act2:
            if st.button("💾 Salvar Rascunho no Banco", type="primary", use_container_width=True):
                executar_auto_save_banco(); st.success("✅ Salvo com sucesso!")