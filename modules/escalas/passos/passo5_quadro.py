import streamlit as st
import datetime
import calendar
import pandas as pd
import copy
import re
from core.database import salvar_escala_mensal_supabase, supabase, carregar_militares_supabase
from modules.escalas.passos.passo3_efetivo import PESOS_HIERARQUIA, padronizar_graduacao
from modules.escalas.passos.passo4_calendario import DIAS_SEMANA_SIGLAS
from utils.excel_escala_importer import (
    processar_upload_escala_excel, 
    escanear_legendas_unicas_excel, 
    MAPA_CONVERSAO_LEGENDAS
)

SIGLAS_DIAS_NEUTROS = [
    "FER", "FERIAS", "FÉRIAS", "FE",
    "LTSP", "LM",
    "ATEST", "ATESTADO", "ATE",
    "LUTO", "NUPCIAS", "NÚPCIAS", "LUT", "NUP", "DN", "DNT"
]

@st.dialog("🛡️ Auditoria de Lançamento de Escala", width="large")
def abrir_modal_auditoria_unificada(militar_nome, ignorados_bloqueados, pendentes_descanso, val_final, item_sel, m_ano, m_mes):
    """Pop-up unificado para informar sobreposições ignoradas e confirmar descanso reduzido."""
    st.markdown(f"### 👮‍♂️ Militar: **{militar_nome}**")
    
    # 1. Exibição de Bloqueios/Sobreposições (Ignorados e mantidos com a escala original)
    if ignorados_bloqueados:
        st.error("🚨 **Lançamentos Ignorados (Sobreposição de Horários):**")
        st.caption("Os turnos abaixo NÃO foram aplicados pois o policial já possui serviço ativo no mesmo horário na outra equipe:")
        for b in ignorados_bloqueados:
            st.markdown(f"• **Dia {b['dia']:02d}:** Já escalado na equipe **{b['equipe']}** ({b['horario']})")
        st.divider()

    # 2. Exibição de Alertas de Descanso Reduzido (Exige Confirmação)
    if pendentes_descanso:
        st.warning("⚠️ **Aviso de Descanso Interjornada Insuficiente (< 8 Horas):**")
        st.caption("O lançamento gera intervalo de descanso reduzido nas seguintes datas:")
        for a in pendentes_descanso:
            st.markdown(f"• **Dia {a['dia']:02d}:** {a['mensagem']}")
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Deseja confirmar o lançamento mesmo com o descanso reduzido nestes dias?**")
        
        c_conf1, c_conf2 = st.columns(2)
        with c_conf1:
            if st.button("✅ Confirmar Lançamento com Descanso Reduzido", type="primary", use_container_width=True):
                salvar_estado_undo()
                for a in pendentes_descanso:
                    d_a = a['dia']
                    chave = f"{item_sel['id']}_{item_sel['equipe']}_{m_ano}_{m_mes:02d}_{d_a:02d}"
                    st.session_state["grade_escala_lancamentos"][chave] = val_final
                
                st.session_state.pop("auditoria_pendente_popup", None)
                st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                registrar_log_auditoria("Descanso Reduzido Confirmado", f"Militar {militar_nome} escalado com descanso reduzido nos dias {[a['dia'] for a in pendentes_descanso]}.")
                executar_auto_save_banco()
                st.rerun()
                
        with c_conf2:
            if st.button("❌ Manter Apenas os Dias Válidos", use_container_width=True):
                st.session_state.pop("auditoria_pendente_popup", None)
                st.rerun()
    else:
        st.success("✅ Os dias válidos e sem conflito foram aplicados com sucesso no quadro!")
        if st.button("OK, Fechar", type="primary", use_container_width=True):
            st.session_state.pop("auditoria_pendente_popup", None)
            st.rerun()

def salvar_estado_undo():
    if "pilha_undo" not in st.session_state:
        st.session_state["pilha_undo"] = []
        
    snapshot = {
        "grade": copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {})),
        "chaves": copy.deepcopy(st.session_state.get("militares_no_quadro_chaves", [])),
        "ordem": copy.deepcopy(st.session_state.get("ordem_customizada_map", {})),
        "bh_configs": copy.deepcopy(st.session_state.get("bh_configs", {})),
        "ajuste_saldo_map": copy.deepcopy(st.session_state.get("ajuste_saldo_map", {})),
        "dias_avulsos": copy.deepcopy(st.session_state.get("dias_selecionados_passo4", []))
    }
    
    st.session_state["pilha_undo"].append(snapshot)
    if len(st.session_state["pilha_undo"]) > 10:
        st.session_state["pilha_undo"].pop(0)

def desfazer_ultima_acao():
    if "pilha_undo" in st.session_state and st.session_state["pilha_undo"]:
        ultimo_snapshot = st.session_state["pilha_undo"].pop()
        st.session_state["grade_escala_lancamentos"] = ultimo_snapshot["grade"]
        st.session_state["militares_no_quadro_chaves"] = ultimo_snapshot["chaves"]
        st.session_state["ordem_customizada_map"] = ultimo_snapshot["ordem"]
        st.session_state["bh_configs"] = ultimo_snapshot.get("bh_configs", {})
        st.session_state["ajuste_saldo_map"] = ultimo_snapshot.get("ajuste_saldo_map", {})
        st.session_state["dias_selecionados_passo4"] = ultimo_snapshot.get("dias_avulsos", [])
        st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
        registrar_log_auditoria("Desfazer Ação", "O operador reverteu a última alteração no quadro.")
        executar_auto_save_banco()
        return True
    return False

def registrar_log_auditoria(acao, detalhe):
    usr_logado = st.session_state.get("usuario_dados", {})
    nome_usuario = usr_logado.get("nome_guerra", usr_logado.get("nome", "OPERADOR"))
    cargo_usuario = usr_logado.get("cargo_funcao", usr_logado.get("perfil", "GESTOR"))
    timezone_br = datetime.timezone(datetime.timedelta(hours=-3))
    dt_agora = datetime.datetime.now(timezone_br).strftime("%d/%m/%Y %H:%M:%S")

    log_entry = {
        "data_hora": dt_agora,
        "usuario": f"{cargo_usuario} {nome_usuario}".strip(),
        "acao": acao,
        "detalhe": detalhe
    }

    if "logs_auditoria_lista" not in st.session_state:
        st.session_state["logs_auditoria_lista"] = []
    st.session_state["logs_auditoria_lista"].insert(0, log_entry)

def padronizar_entrada_quadro(valor):
    if valor is None: return "F"
    v = str(valor).strip().upper()
    if v in ["OFF", "DESCANSO"]: return "D"
    elif v in ["FOLGA"]: return "F"
    return valor

def extrair_datetime_de_string_turno(ano, mes, dia, str_horario):
    """Parser universal de horários para auditoria de sobreposição (suporta ADM e turnos compostos)."""
    if not str_horario or str(str_horario).strip().upper() in ["F", "D", "X", "DN", "FE", "LM", "DIS", "OFF", "DESCANSO", "FOLGA", "NONE", "NAN"]:
        return None, None

    s = str(str_horario).upper().strip()
    m = re.findall(r'\d+', s)
    if len(m) < 2:
        return None, None

    try:
        h_i = int(m[0])
        min_i = int(m[1]) if len(m) > 1 else 0

        if len(m) >= 4:
            h_f = int(m[-2])
            min_f = int(m[-1])
        elif len(m) >= 2:
            h_f = int(m[1]) if len(m) == 2 else int(m[2])
            min_f = int(m[2]) if len(m) == 3 else 0
        else:
            return None, None

        dt_ini = datetime.datetime(ano, mes, dia, h_i, min_i)
        if (h_f < h_i) or (h_f == h_i and min_f <= min_i):
            dt_fim = dt_ini + datetime.timedelta(days=1)
            dt_fim = dt_fim.replace(hour=h_f, minute=min_f)
        else:
            dt_fim = dt_ini.replace(hour=h_f, minute=min_f)
            
        return dt_ini, dt_fim
    except Exception:
        return None, None

def auditar_escalacao_militar(m_id, m_ano, m_mes, d_alvo, val_novo, dict_grade):
    dt_novo_ini, dt_novo_fim = extrair_datetime_de_string_turno(m_ano, m_mes, d_alvo, val_novo)
    if not dt_novo_ini: return "OK", "", {}

    prefixo_chave = f"{m_id}_"
    for key_grade, val_ex in dict_grade.items():
        if key_grade.startswith(prefixo_chave):
            partes_k = key_grade.split("_")
            if len(partes_k) >= 5:
                try:
                    d_ex = int(partes_k[-1])
                    m_ex = int(partes_k[-2])
                    a_ex = int(partes_k[-3])
                    eq_ex = "_".join(partes_k[1:-3])
                except ValueError:
                    continue

                if a_ex == m_ano and m_ex == m_mes:
                    if d_ex == d_alvo and val_ex == val_novo: 
                        continue
                        
                    dt_ex_ini, dt_ex_fim = extrair_datetime_de_string_turno(m_ano, m_mes, d_ex, val_ex)
                    if not dt_ex_ini: 
                        continue
                        
                    # Checagem de sobreposição de horário (mesmo parcial)
                    if dt_novo_ini < dt_ex_fim and dt_novo_fim > dt_ex_ini:
                        return "BLOQUEADO", f"Choque de Horário: Já escalado no dia {d_ex:02d} ({val_ex}) na equipe {eq_ex}.", {"dia": d_ex, "equipe": eq_ex, "horario": val_ex}

                    # Checagem de descanso interjornada reduzido (<8h)
                    if dt_novo_ini >= dt_ex_fim and d_ex == d_alvo:
                        descanso = (dt_novo_ini - dt_ex_fim).total_seconds() / 3600.0
                        if 0 <= descanso < 8.0:
                            return "AVISO", f"Descanso reduzido para {descanso:.1f}h após o serviço na equipe {eq_ex}.", {"dia": d_ex, "equipe": eq_ex}
                            
                    if dt_novo_fim <= dt_ex_ini and d_ex == d_alvo:
                        descanso = (dt_ex_ini - dt_novo_fim).total_seconds() / 3600.0
                        if 0 <= descanso < 8.0:
                            return "AVISO", f"Descanso reduzido para {descanso:.1f}h antes do serviço na equipe {eq_ex}.", {"dia": d_ex, "equipe": eq_ex}

    return "OK", "", {}

def executar_auto_save_banco():
    """Salva a matriz inteira, ordem, horas avulsas e ajustes de saldo no Supabase."""
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    eq_ativa = st.session_state.get("equipe_ativa", "GERAL")
    mod_nome = st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso")
    
    usr = st.session_state.get("usuario_dados", {})
    usr_nome = usr.get("nome_guerra") or usr.get("usuario_login") or "OPERADOR"

    raw_chaves = st.session_state.get("militares_no_quadro_chaves", [])
    chaves_sanitizadas = [
        (str(p[0]), str(p[1])) for p in raw_chaves if isinstance(p, (tuple, list)) and len(p) == 2
    ]

    matriz_payload = {
        "grade_escala_lancamentos": st.session_state.get("grade_escala_lancamentos", {}),
        "militares_no_quadro_chaves": chaves_sanitizadas,
        "ordem_customizada_map": st.session_state.get("ordem_customizada_map", {}),
        "bh_configs": st.session_state.get("bh_configs", {}),
        "ajuste_saldo_map": st.session_state.get("ajuste_saldo_map", {}),
        "dias_selecionados_passo4": st.session_state.get("dias_selecionados_passo4", []),
        "horario_avulso_p2": st.session_state.get("horario_avulso_p2", "07:00 às 19:00")
    }

    salvar_escala_mensal_supabase(
        ano=m_ano,
        mes=m_mes,
        equipe_nome=eq_ativa,
        modalidade=mod_nome,
        matriz_dados=matriz_payload,
        elaborado_por=usr_nome,
        homologado_por=usr_nome,
        status="RASCUNHO"
    )
    st.session_state["exibir_toast_autosave"] = True

def carregar_escala_salva_banco():
    """Busca a escala e configurações completas do mês selecionado no Supabase."""
    if not supabase: return
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)

    try:
        res = supabase.table("escalas_mensais").select("matriz_dados").eq("ano", m_ano).eq("mes", m_mes).execute()
        if res and res.data and len(res.data) > 0:
            m_dados = res.data[0].get("matriz_dados", {})
            if isinstance(m_dados, dict):
                st.session_state["grade_escala_lancamentos"] = m_dados.get("grade_escala_lancamentos", {})
                st.session_state["ordem_customizada_map"] = m_dados.get("ordem_customizada_map", {})
                st.session_state["bh_configs"] = m_dados.get("bh_configs", {})
                st.session_state["ajuste_saldo_map"] = m_dados.get("ajuste_saldo_map", {})
                st.session_state["dias_selecionados_passo4"] = m_dados.get("dias_selecionados_passo4", [])
                st.session_state["horario_avulso_p2"] = m_dados.get("horario_avulso_p2", "07:00 às 19:00")
                raw_chaves = m_dados.get("militares_no_quadro_chaves", [])
                st.session_state["militares_no_quadro_chaves"] = [
                    (str(p[0]), str(p[1])) for p in raw_chaves if isinstance(p, (tuple, list)) and len(p) == 2
                ]
        else:
            st.session_state["grade_escala_lancamentos"] = {}
            st.session_state["militares_no_quadro_chaves"] = []
            st.session_state["ordem_customizada_map"] = {}
            st.session_state["ajuste_saldo_map"] = {}
            
        st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
    except Exception as ex:
        print(f"Aviso ao carregar escala salva: {ex}")

def recalcular_escala_matriz():
    """Calcula a sequência teórica apenas quando o comando de aplicação é acionado."""
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    mod_nome = st.session_state.get("modalidade_turno_ativa", "Turno Único / Avulso")
    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
    dias_marcados_p4 = set(st.session_state.get("dias_selecionados_passo4", []))
    
    num_dias = calendar.monthrange(m_ano, m_mes)[1]
    grade = st.session_state.get("grade_escala_lancamentos", {})
    
    h_avulso = st.session_state.get("horario_avulso_p2", "07:00 às 19:00")
    h_adm_norm = st.session_state.get("adm_h_norm", "08:00 às 12:00\n13:30 às 17:00")
    h_adm_qua = st.session_state.get("adm_h_qua", "08:30 às 13:00")
    
    h_36_dia = st.session_state.get("c36_h_dia", "07:00 às 19:00")
    h_36_noite = st.session_state.get("c36_h_noite", "19:00 às 07:00")
    fase_36 = st.session_state.get("c36_fase_ini", "Dia (Trabalho)")
    
    seq_36_map = {
        "Dia (Trabalho)": [h_36_dia, "D", h_36_noite, "D", "F"],
        "Descanso Pós-Dia": ["D", h_36_noite, "D", "F", h_36_dia],
        "Noite (Trabalho)": [h_36_noite, "D", "F", h_36_dia, "D"],
        "Descanso Pós-Noite": ["D", "F", h_36_dia, "D", h_36_noite],
        "Folga": ["F", h_36_dia, "D", h_36_noite, "D"]
    }
    
    h_72_dia = st.session_state.get("c72_h_dia", "06:00 às 18:00")
    h_72_noite = st.session_state.get("c72_h_noite", "18:00 às 06:00")
    fase_72 = st.session_state.get("c72_fase_ini", "Fase 1 (Dia)")
    
    seq_72_map = {
        "Fase 1 (Dia)": [h_72_dia, h_72_noite, "D", "D", "F"],
        "Fase 2 (Noite)": [h_72_noite, "D", "D", "F", h_72_dia],
        "Descanso 1": ["D", "D", "F", h_72_dia, h_72_noite],
        "Descanso 2": ["D", "F", h_72_dia, h_72_noite, "D"],
        "Folga": ["F", h_72_dia, h_72_noite, "D", "D"]
    }
    
    h_dob_sq = st.session_state.get("dob_h_sq", "14:00 às 00:00")
    h_dob_ss = st.session_state.get("dob_h_ss", "18:00 às 04:00")
    h_dob_dom = st.session_state.get("dob_h_dom", "18:00 às 02:00")
    sem_dob_ini = st.session_state.get("dob_sem_ini", "SEMANA A")
    eh_sem_a_ini = "SEMANA A" in sem_dob_ini
    sem_iso_d1 = datetime.date(m_ano, m_mes, 1).isocalendar()[1]
    
    for pair in chaves_quadro:
        if not (isinstance(pair, (tuple, list)) and len(pair) == 2): continue
        m_id, eq_nome = str(pair[0]), pair[1]
        
        for d in range(1, num_dias + 1):
            chave = f"{m_id}_{eq_nome}_{m_ano}_{m_mes:02d}_{d:02d}"
            val_atual = grade.get(chave)
            if val_atual and val_atual not in ["F", "", None]: continue
            
            valor_dia = "F"
            if mod_nome == "Turno Único / Avulso":
                valor_dia = h_avulso if d in dias_marcados_p4 else "F"
            elif mod_nome == "ADM (Seg-Sex)":
                w = calendar.weekday(m_ano, m_mes, d)
                valor_dia = (h_adm_qua if w == 2 else h_adm_norm) if w < 5 else "F"
            elif mod_nome == "Ciclo 12x36":
                padr = seq_36_map.get(fase_36, [h_36_dia, "D", h_36_noite, "D", "F"])
                valor_dia = padr[(d - 1) % 5]
            elif mod_nome == "Ciclo 12x72 (5D)":
                padr = seq_72_map.get(fase_72, [h_72_dia, h_72_noite, "D", "D", "F"])
                valor_dia = padr[(d - 1) % 5]
            elif mod_nome == "Dobradinha (14D)":
                dt = datetime.date(m_ano, m_mes, d)
                w = dt.weekday()
                diff_s = dt.isocalendar()[1] - sem_iso_d1
                eh_sem_a = (diff_s % 2 == 0) if eh_sem_a_ini else (diff_s % 2 != 0)
                trabalha = (eh_sem_a and w in [0, 2, 5, 6]) or ((not eh_sem_a) and w in [1, 3, 4])
                if trabalha:
                    valor_dia = h_dob_sq if w in [0, 1, 2, 3] else (h_dob_ss if w in [4, 5] else h_dob_dom)
                else: valor_dia = "F"
            elif mod_nome == "Supervisão":
                if d in dias_marcados_p4:
                    w = calendar.weekday(m_ano, m_mes, d)
                    valor_dia = st.session_state.get("horario_sup_sex_sab", "18:00 às 00:00") if w in [4, 5] else st.session_state.get("horario_sup_dom_qui", "15:00 às 21:00")
                else: valor_dia = "F"

            status_aud, _, _ = auditar_escalacao_militar(m_id, m_ano, m_mes, d, valor_dia, grade)
            if status_aud == "BLOQUEADO": valor_dia = "X"
            grade[chave] = valor_dia

    st.session_state["grade_escala_lancamentos"] = grade

@st.dialog("📥 Importar Escala Pronta via Excel", width="large")
def abrir_modal_importar_escala_excel():
    st.markdown("##### 📁 Envie a planilha Excel para preenchimento automático do Quadro:")
    st.caption("O leitor identifica automaticamente colunas de MATRÍCULA/MILITAR, EQUIPE e colunas dos dias (1 a 31).")
    
    arq_escala = st.file_uploader("Selecione o arquivo XLSX ou XLS:", type=["xlsx", "xls"], key="uploader_escala_excel_modal")
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)

    if arq_escala is not None:
        legendas_detectadas = escanear_legendas_unicas_excel(arq_escala, m_ano, m_mes)
        st.divider()
        st.markdown("**Mapeamento Dinâmico de Legendas:**")
        mapa_custom = {}
        if legendas_detectadas:
            st.info(f"💡 Foram identificadas `{len(legendas_detectadas)}` legenda(s) na planilha: {legendas_detectadas}")
            cols = st.columns(2)
            for idx_leg, leg_code in enumerate(legendas_detectadas):
                val_padrao = MAPA_CONVERSAO_LEGENDAS.get(leg_code, "07:00 às 19:00")
                with cols[idx_leg % 2]:
                    mapa_custom[leg_code] = st.text_input(f"Sigla '{leg_code}' equivale a:", value=val_padrao, key=f"inp_leg_dyn_{leg_code}")
        limpar_antes = st.checkbox("🧹 Limpar o quadro atual antes de importar", value=True)

        if st.button("🚀 Processar e Carregar no Quadro Mensal", type="primary", use_container_width=True):
            salvar_estado_undo()
            sucesso, msg, nao_encontrados = processar_upload_escala_excel(arq_escala, m_ano, m_mes, mapa_custom, limpar_antes)
            if sucesso:
                st.success(msg)
                if nao_encontrados: st.warning(f"⚠️ {len(nao_encontrados)} militar(es) não cadastrados: {nao_encontrados}")
                registrar_log_auditoria("Importação via Excel", f"Escala carregada de '{arq_escala.name}'.")
                st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                executar_auto_save_banco()
                st.rerun()
            else: st.error(msg)

def renderizar_passo5():
    # Renderização da Janela Unificada de Auditoria caso existam pendências
    if "auditoria_pendente_popup" in st.session_state and st.session_state["auditoria_pendente_popup"]:
        p = st.session_state["auditoria_pendente_popup"]
        abrir_modal_auditoria_unificada(
            p["militar_nome"], 
            p["ignorados"], 
            p["descanso"], 
            p["val_final"], 
            p["item_sel"], 
            p["m_ano"], 
            p["m_mes"]
        )

    if "militares_selecionados_ids" not in st.session_state: st.session_state["militares_selecionados_ids"] = []
    if "grade_escala_lancamentos" not in st.session_state: st.session_state["grade_escala_lancamentos"] = {}
    if "militares_no_quadro_chaves" not in st.session_state: st.session_state["militares_no_quadro_chaves"] = []
    if "quadro_versao" not in st.session_state: st.session_state["quadro_versao"] = 0
    if "lista_militares" not in st.session_state or not st.session_state["lista_militares"]:
        st.session_state["lista_militares"] = carregar_militares_supabase() or []

    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    chave_mes_atual = f"{m_ano}_{m_mes:02d}"

    if st.session_state.get("chave_escala_carregada") != chave_mes_atual:
        carregar_escala_salva_banco()
        st.session_state["chave_escala_carregada"] = chave_mes_atual

    raw_existentes = st.session_state.get("militares_no_quadro_chaves", [])
    chaves_existentes = [
        (str(p[0]), str(p[1])) for p in raw_existentes if isinstance(p, (tuple, list)) and len(p) == 2
    ]
    st.session_state["militares_no_quadro_chaves"] = chaves_existentes

    if st.session_state.get("atualizar_quadro_passo5", False):
        sel_ids = set(str(mid) for mid in st.session_state.get("militares_selecionados_ids", []))
        eq_ativa = str(st.session_state.get("equipe_ativa", "ADMINISTRAÇÃO"))
        
        novas_chaves = []
        for pair in chaves_existentes:
            if isinstance(pair, (tuple, list)) and len(pair) == 2:
                m_id_s, eq_s = str(pair[0]), str(pair[1])
                if eq_s == eq_ativa:
                    if m_id_s in sel_ids: novas_chaves.append((m_id_s, eq_s))
                else: novas_chaves.append((m_id_s, eq_s))

        chaves_set = set(novas_chaves)
        for m_id_str in sel_ids:
            par = (m_id_str, eq_ativa)
            if par not in chaves_set:
                novas_chaves.append(par)
                chaves_set.add(par)

        st.session_state["militares_no_quadro_chaves"] = novas_chaves
        recalcular_escala_matriz()
        st.session_state["atualizar_quadro_passo5"] = False

    if st.session_state.get("exibir_toast_autosave", False):
        st.toast("☁️ Rascunho salvo na nuvem com sucesso (Auto-Save)!", icon="✅")
        st.session_state["exibir_toast_autosave"] = False

    usr_logado = st.session_state.get("usuario_dados", {})
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil_str = str(usr_logado.get("perfil", "")).upper()
    eh_admin = "PROGRAMADOR" in cargo_str or "TESTADOR" in cargo_str or "ADMIN" in perfil_str or "DESENVOLVEDOR" in cargo_str
    
    escala_fechada = st.session_state.get("escala_fechada_auditoria", False)
    quadro_travado = st.session_state.get("toggle_trava_quadro", False)
    timezone_br = datetime.timezone(datetime.timedelta(hours=-3))
    hoje = datetime.datetime.now(timezone_br).date()
    
    exp5 = st.expander("📌 PASSO 5: Quadro Mensal de Escalas e Carga Horária", expanded=True)
    with exp5:
        if escala_fechada:
            if not eh_admin: st.warning("🔒 **ESCALA HOMOLOGADA:** Edição permitida **apenas de hoje em diante**.")
            else: st.info("🛠️ **MODO PROGRAMADOR:** Escala fechada com permissão total de edição.")

        chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
        c_info1, c_info2 = st.columns([3, 1])
        with c_info1:
            st.info(f"👮‍♂️ **Linhas de Escala Ativas no Quadro:** `{len(chaves_quadro)}` | 💡 *Legenda `X` indica serviço ativo em outra guarnição.*")
        with c_info2:
            if st.button("📥 Importar Escala (Excel)", type="primary", use_container_width=True):
                abrir_modal_importar_escala_excel()

        if st.button("⚡ Aplicar Lançamentos e Atualizar Quadro", type="primary", use_container_width=True):
            st.session_state["atualizar_quadro_passo5"] = True
            st.rerun()

        num_dias_mes = calendar.monthrange(m_ano, m_mes)[1]
        mils_todos = st.session_state.get("lista_militares", [])

        mils_linhas_quadro = []
        for pair in chaves_quadro:
            if isinstance(pair, (tuple, list)) and len(pair) == 2:
                m_obj = next((m for m in mils_todos if str(m.get("id")) == str(pair[0])), None)
                if m_obj:
                    mils_linhas_quadro.append({
                        "id": str(pair[0]),
                        "equipe": str(pair[1]),
                        "posto_grad": m_obj.get("posto_grad", "SD"),
                        "nome_guerra": m_obj.get("nome_guerra", "MILITAR"),
                        "num_policia": m_obj.get("num_policia", ""),
                        "chave_linha": f"{pair[0]}_{pair[1]}"
                    })

        if "ordem_customizada_map" not in st.session_state:
            st.session_state["ordem_customizada_map"] = {}
            
        for idx_pos, item in enumerate(mils_linhas_quadro):
            if item["chave_linha"] not in st.session_state["ordem_customizada_map"]:
                st.session_state["ordem_customizada_map"][item["chave_linha"]] = idx_pos + 1

        mils_escala_ord = sorted(mils_linhas_quadro, key=lambda x: (
            st.session_state["ordem_customizada_map"].get(x["chave_linha"], 99),
            PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99),
            x["nome_guerra"]
        ))

        # EXCLUSÃO DE MILITAR OU EQUIPE DO QUADRO
        with st.expander("🗑️ Excluir Militar ou Equipe do Quadro"):
            if quadro_travado: st.warning("🔒 Desative a chave 'Travar Quadro' para permitir exclusões.")
            elif escala_fechada and not eh_admin: st.error("🔒 Não é possível excluir linhas com a escala homologada.")
            else:
                col_ex1, col_ex2 = st.columns(2)
                with col_ex1:
                    st.markdown("**Excluir Linha Específica:**")
                    if mils_escala_ord:
                        dict_del_mil = {f"[{m['equipe']}] {m['posto_grad']} {m['nome_guerra']} ({m['num_policia']})": m for m in mils_escala_ord}
                        mil_del_sel = st.selectbox("Selecione para remover:", list(dict_del_mil.keys()), key="p5_del_mil_sel")
                        if st.button("❌ Remover Linha Selecionada", key="btn_del_linha_p5", use_container_width=True):
                            salvar_estado_undo()
                            item_del = dict_del_mil[mil_del_sel]
                            m_id_str, eq_del_str = str(item_del["id"]), str(item_del["equipe"])
                            par_del = (m_id_str, eq_del_str)
                            
                            st.session_state["militares_no_quadro_chaves"] = [
                                (str(p[0]), str(p[1])) for p in st.session_state["militares_no_quadro_chaves"]
                                if (str(p[0]), str(p[1])) != par_del
                            ]
                            
                            ainda_em_outra_eq = any(str(p[0]) == m_id_str for p in st.session_state["militares_no_quadro_chaves"])
                            if not ainda_em_outra_eq and "militares_selecionados_ids" in st.session_state:
                                st.session_state["militares_selecionados_ids"] = [
                                    str(mid) for mid in st.session_state["militares_selecionados_ids"] if str(mid) != m_id_str
                                ]
                                
                            for d in range(1, num_dias_mes + 1):
                                chave_pop = f"{m_id_str}_{eq_del_str}_{m_ano}_{m_mes:02d}_{d:02d}"
                                st.session_state["grade_escala_lancamentos"].pop(chave_pop, None)
                                
                            st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                            registrar_log_auditoria("Remoção de Linha", f"Militar {item_del['posto_grad']} {item_del['nome_guerra']} removido da equipe {item_del['equipe']}.")
                            executar_auto_save_banco()
                            st.rerun()
                with col_ex2:
                    st.markdown("**Excluir Equipe Inteira:**")
                    equipes_no_quadro = sorted(list(set([m["equipe"] for m in mils_escala_ord])))
                    if equipes_no_quadro:
                        eq_del_sel = st.selectbox("Selecione a equipe:", equipes_no_quadro, key="p5_del_eq_sel")
                        if st.button("🔥 Excluir Toda a Equipe", key="btn_del_eq_p5", use_container_width=True):
                            salvar_estado_undo()
                            eq_alvo = str(eq_del_sel)
                            chaves_manter = []
                            for pair in st.session_state["militares_no_quadro_chaves"]:
                                if isinstance(pair, (tuple, list)) and len(pair) == 2:
                                    m_id_s, eq_n_s = str(pair[0]), str(pair[1])
                                    if eq_n_s == eq_alvo:
                                        for d in range(1, num_dias_mes + 1):
                                            chave_pop = f"{m_id_s}_{eq_n_s}_{m_ano}_{m_mes:02d}_{d:02d}"
                                            st.session_state["grade_escala_lancamentos"].pop(chave_pop, None)
                                    else: chaves_manter.append((m_id_s, eq_n_s))
                                        
                            st.session_state["militares_no_quadro_chaves"] = chaves_manter
                            ids_restantes = set(str(p[0]) for p in chaves_manter)
                            if "militares_selecionados_ids" in st.session_state:
                                st.session_state["militares_selecionados_ids"] = [
                                    str(mid) for mid in st.session_state["militares_selecionados_ids"] if str(mid) in ids_restantes
                                ]
                                
                            st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                            registrar_log_auditoria("Exclusão de Equipe", f"Toda a equipe '{eq_alvo}' foi excluída do quadro.")
                            executar_auto_save_banco()
                            st.rerun()

        # PAINEL DE AJUSTE RÁPIDO NO QUADRO
        with st.expander("⚡ Painel de Ajuste Rápido no Quadro", expanded=False):
            if quadro_travado:
                st.warning("🔒 Desative a chave 'Travar Quadro' abaixo para efetuar lançamentos diretos.")
            elif mils_escala_ord:
                dict_mils = {f"[{m['equipe']}] {m['posto_grad']} {m['nome_guerra']} ({m['num_policia']})": m for m in mils_escala_ord}
                
                c_f1, c_f2, c_f3 = st.columns([2.5, 2, 2])
                with c_f1:
                    mil_sel_label = st.selectbox("Selecione a Linha de Escala:", list(dict_mils.keys()), key="p5_painel_mil")
                    item_sel = dict_mils[mil_sel_label]
                with c_f2:
                    dias_lista = list(range(1, num_dias_mes + 1))
                    dias_alvo = st.multiselect("Selecione o(s) Dia(s):", dias_lista, default=[], key="p5_painel_dias")
                with c_f3:
                    tipo_evento = st.selectbox(
                        "Tipo de Evento / Horário:",
                        [
                            "Horário Normal (Escolher Início/Fim)", "D (Descanso Pós-Turno)", "F (Folga)", 
                            "X (Empenhado em outra Equipe)", "DN (Dia Neutro - Abate Meta sem trabalhar)", 
                            "DNT (Dia Neutro Trabalhado - Abate Meta + Horas)", "FE (Férias)", "LM (Licença Médica)", "DIS (Dispensa)"
                        ],
                        key="p5_painel_tipo"
                    )

                c_h1, c_h2, c_btn = st.columns([2, 2, 2])
                if "Horário Normal" in tipo_evento or "DNT" in tipo_evento:
                    with c_h1: h_ini_p = st.time_input("Hora Início:", datetime.time(7, 0), key="p5_p_h_ini")
                    with c_h2: h_fim_p = st.time_input("Hora Fim:", datetime.time(19, 0), key="p5_p_h_fim")
                    str_horario = f"{h_ini_p.strftime('%H:%M')} às {h_fim_p.strftime('%H:%M')}"
                    val_final_p = f"{str_horario} (DNT)" if "DNT" in tipo_evento else str_horario
                else:
                    with c_h1: st.caption("Legenda/Afastamento selecionado.")
                    with c_h2: pass
                    
                    if "D (" in tipo_evento: val_final_p = "D"
                    elif "F (" in tipo_evento: val_final_p = "F"
                    elif "X (" in tipo_evento: val_final_p = "X"
                    elif "DN (" in tipo_evento: val_final_p = "DN"
                    elif "FE" in tipo_evento: val_final_p = "FE"
                    elif "LM" in tipo_evento: val_final_p = "LM"
                    elif "DIS" in tipo_evento: val_final_p = "DIS"
                    else: val_final_p = "F"

                with c_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("⚡ Aplicar Alteração Direta", type="primary", use_container_width=True):
                        if not dias_alvo:
                            st.warning("Selecione ao menos um dia!")
                        else:
                            salvar_estado_undo()
                            dias_aplicados, ignorados_bloqueados, pendentes_descanso = [], [], []
                            
                            for d_a in dias_alvo:
                                data_alvo = datetime.date(m_ano, m_mes, d_a)
                                if escala_fechada and not eh_admin and data_alvo < hoje:
                                    continue
                                
                                status_aud, msg_aud, detalhe_conf = auditar_escalacao_militar(item_sel["id"], m_ano, m_mes, d_a, val_final_p, st.session_state["grade_escala_lancamentos"])

                                # IGNORA a sobreposição no segundo lançamento mantendo a escala original intacta
                                if status_aud == "BLOQUEADO":
                                    ignorados_bloqueados.append({
                                        "dia": d_a,
                                        "equipe": detalhe_conf.get("equipe", "N/I"),
                                        "horario": detalhe_conf.get("horario", "N/I")
                                    })
                                    continue
                                
                                # CAPTURA aviso de descanso interjornada para pedir confirmação
                                elif status_aud == "AVISO":
                                    pendentes_descanso.append({
                                        "dia": d_a,
                                        "mensagem": msg_aud
                                    })
                                    continue

                                # LANÇA os dias perfeitamente válidos imediatamente
                                chave = f"{item_sel['id']}_{item_sel['equipe']}_{m_ano}_{m_mes:02d}_{d_a:02d}"
                                st.session_state["grade_escala_lancamentos"][chave] = val_final_p
                                dias_aplicados.append(d_a)
                                
                            if dias_aplicados:
                                st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                                registrar_log_auditoria("Ajuste Rápido de Turno", f"Militar {item_sel['nome_guerra']} dia(s) {dias_aplicados} alterado(s) para '{val_final_p}'.")
                                executar_auto_save_banco()

                            # Dispara janela modal única se houver sobreposições ignoradas ou descanso para confirmar
                            if ignorados_bloqueados or pendentes_descanso:
                                st.session_state["auditoria_pendente_popup"] = {
                                    "militar_nome": f"{item_sel['posto_grad']} {item_sel['nome_guerra']}",
                                    "ignorados": ignorados_bloqueados,
                                    "descanso": pendentes_descanso,
                                    "val_final": val_final_p,
                                    "item_sel": item_sel,
                                    "m_ano": m_ano,
                                    "m_mes": m_mes
                                }
                            st.rerun()

        st.divider()

        col_t1, col_t2, col_t3, col_t4 = st.columns([1.5, 1, 1, 1.5])
        with col_t1: st.markdown("#### 📊 Quadro Mensal")
        with col_t2:
            qtd_undo = len(st.session_state.get("pilha_undo", []))
            pode_desfazer = (qtd_undo > 0) and not quadro_travado
            if st.button(f"↩️ Desfazer ({qtd_undo})", disabled=not pode_desfazer, use_container_width=True):
                if desfazer_ultima_acao(): st.rerun()
        with col_t3: 
            if st.button("🔄 Restaurar Ciclo Padrão", use_container_width=True, type="primary"):
                st.session_state["grade_escala_lancamentos"] = {}
                recalcular_escala_matriz()
                st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                registrar_log_auditoria("Restauração do Ciclo Padrão", "A escala foi restaurada para a sequência automática teórica.")
                executar_auto_save_banco()
                st.rerun()
        with col_t4: 
            quadro_travado_toggle = st.toggle("🔒 Travar Quadro", value=quadro_travado, key="toggle_trava_quadro")
            if quadro_travado_toggle != quadro_travado: st.rerun()

        colunas_dias_nomes = []
        for d in range(1, num_dias_mes + 1):
            dia_semana_idx = calendar.weekday(m_ano, m_mes, d)
            sigla_sem = DIAS_SEMANA_SIGLAS[dia_semana_idx]
            prefixo_col = "🔴 " if dia_semana_idx in [5, 6] else ""
            colunas_dias_nomes.append((d, f"{prefixo_col}{d:02d} {sigla_sem}"))

        matriz_dados = []
        for idx_r, item in enumerate(mils_escala_ord):
            m_id = item["id"]
            eq_nome = item["equipe"]
            pg = padronizar_graduacao(item["posto_grad"])
            nome_guerra = item["nome_guerra"]
            num_pol = item["num_policia"]
            ordem_atual = st.session_state["ordem_customizada_map"].get(item["chave_linha"], idx_r + 1)

            linha = {
                "ORDEM": int(ordem_atual),
                "EQUIPE": eq_nome,
                "Nº POLÍCIA": num_pol,
                "MILITAR": f"{pg} {nome_guerra}"
            }

            total_horas = 0.0
            dias_neutros_cnt = 0
            
            for d, col_nome in colunas_dias_nomes:
                chave_celula = f"{m_id}_{eq_nome}_{m_ano}_{m_mes:02d}_{d:02d}"
                val_atual = st.session_state["grade_escala_lancamentos"].get(chave_celula, "F")
                val_atual = padronizar_entrada_quadro(val_atual)
                
                # Leitura Cruzada de Empenho: Se estiver em branco/folga nesta equipe, checa se tem serviço ativo em outra
                if val_atual in ["F", "", None]:
                    for pair_k in chaves_quadro:
                        if isinstance(pair_k, (tuple, list)) and len(pair_k) == 2:
                            if str(pair_k[0]) == str(m_id) and pair_k[1] != eq_nome:
                                val_outra = st.session_state["grade_escala_lancamentos"].get(f"{m_id}_{pair_k[1]}_{m_ano}_{m_mes:02d}_{d:02d}")
                                dt_o_i, dt_o_f = extrair_datetime_de_string_turno(m_ano, m_mes, d, val_outra)
                                if dt_o_i is not None:
                                    val_atual = "X"
                                    break

                linha[col_nome] = val_atual
                val_str = str(val_atual).upper().strip() if val_atual else ""
                tokens_dia = set(val_str.replace("/", " ").split())
                
                if any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                    dias_neutros_cnt += 1
                
                if val_str and val_str not in ["", "F", "D", "X"] and not any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                    total_horas += 12.0

            cfg_bh = st.session_state.get("bh_configs", {}).get(str(m_id), {})
            eh_reduzida = cfg_bh.get("reduzida", False)
            carga_base_mes = 80.0 if eh_reduzida else 160.0
            taxa_diaria = carga_base_mes / float(num_dias_mes)
            meta_efetiva = max(0.0, (num_dias_mes - dias_neutros_cnt) * taxa_diaria)
            
            ajuste_manual = float(st.session_state.get("ajuste_saldo_map", {}).get(str(m_id), 0.0))
            total_horas_com_ajuste = total_horas + ajuste_manual
            excesso_horas = total_horas_com_ajuste - meta_efetiva

            if excesso_horas > 0:
                linha["HORAS / META"] = f"⚠️ {total_horas_com_ajuste:.1f}h / {meta_efetiva:.1f}h (+{excesso_horas:.1f}h)"
            else:
                linha["HORAS / META"] = f"{total_horas_com_ajuste:.1f}h / {meta_efetiva:.1f}h"
                
            matriz_dados.append(linha)

        df_escala = pd.DataFrame(matriz_dados)
        st.session_state["df_escala_consolidada"] = df_escala

        if not df_escala.empty:
            with st.expander("👥 Gráfico de Efetivo Diário Detalhado (Por Equipe e Turno)", expanded=False):
                dados_grafico = []
                contagem_total_diaria = {f"{d:02d}": 0 for d, _ in colunas_dias_nomes}
                
                for linha in matriz_dados:
                    eq_nome = linha.get("EQUIPE", "GERAL")
                    for d, col_nome in colunas_dias_nomes:
                        dia_str = f"{d:02d}"
                        val = str(linha.get(col_nome, "")).strip().upper()
                        tokens_val = set(val.replace("/", " ").split())
                        
                        if val and val not in ["F", "D", "X"] and not any(sigla in tokens_val for sigla in SIGLAS_DIAS_NEUTROS):
                            contagem_total_diaria[dia_str] += 1
                            dados_grafico.append({
                                "Dia": dia_str, 
                                "Equipe/Turno": f"{eq_nome} ({val})"
                            })
                
                col_chart, col_metric = st.columns([3, 1])
                with col_chart:
                    df_g = pd.DataFrame(dados_grafico)
                    if not df_g.empty:
                        df_count = df_g.groupby(["Dia", "Equipe/Turno"]).size().unstack(fill_value=0)
                        dias_index = [f"{d:02d}" for d, _ in colunas_dias_nomes]
                        df_count = df_count.reindex(dias_index, fill_value=0)
                        df_count.columns = [str(c).replace(":", "h") for c in df_count.columns]
                        df_count.columns.name = None
                        df_count.index.name = "Dia"
                        st.bar_chart(df_count, height=350)
                    else: st.info("Nenhum serviço escalado ainda.")
                
                with col_metric:
                    min_efetivo = st.number_input("Mínimo Aceitável (Total/Dia):", min_value=1, max_value=50, value=2)
                    dias_criticos = [d for d, qtd in contagem_total_diaria.items() if qtd < min_efetivo]
                    if dias_criticos: st.error(f"🚨 **ALERTA DE DESFALQUE:** Dias **{', '.join(dias_criticos)}** abaixo do mínimo.")
                    else: st.success("✅ Escala coberta!")

            equipes_cadastradas = st.session_state.get("lista_equipes", ["ADMINISTRAÇÃO", "SUPERVISÃO", "CPU", "RP", "TM ALPHA", "GEPAR"])
            equipes_presentes_df = list(df_escala["EQUIPE"].unique()) if "EQUIPE" in df_escala.columns else []
            equipes_opcoes = sorted(list(set(equipes_cadastradas + equipes_presentes_df)))

            config_colunas = {
                "ORDEM": st.column_config.NumberColumn("ORDEM", min_value=1, max_value=99, step=1),
                "EQUIPE": st.column_config.SelectboxColumn("EQUIPE", options=equipes_opcoes, required=True),
                "Nº POLÍCIA": st.column_config.TextColumn("Nº POLÍCIA", disabled=True),
                "MILITAR": st.column_config.TextColumn("MILITAR", disabled=True),
                "HORAS / META": st.column_config.TextColumn("HORAS / META", disabled=True),
            }

            if quadro_travado:
                st.dataframe(df_escala, column_config=config_colunas, use_container_width=True, hide_index=True, height=450)
            else:
                chave_editor = f"editor_quadro_v{st.session_state['quadro_versao']}"
                df_editado = st.data_editor(
                    df_escala, 
                    column_config=config_colunas, 
                    num_rows="fixed", 
                    use_container_width=True, 
                    hide_index=True, 
                    height=450,
                    key=chave_editor
                )

                houve_alteracao = False
                for idx_r, row in df_editado.iterrows():
                    if idx_r < len(mils_escala_ord):
                        item = mils_escala_ord[idx_r]
                        nova_ordem = int(row.get("ORDEM", idx_r + 1))
                        if st.session_state["ordem_customizada_map"].get(item["chave_linha"]) != nova_ordem:
                            salvar_estado_undo()
                            st.session_state["ordem_customizada_map"][item["chave_linha"]] = nova_ordem
                            houve_alteracao = True

                        for d, col_nome in colunas_dias_nomes:
                            dia_str = f"{d:02d}"
                            v_padrao = padronizar_entrada_quadro(str(row.get(col_nome, "")).strip())
                            chave_cel = f"{item['id']}_{item['equipe']}_{m_ano}_{m_mes:02d}_{dia_str}"
                            val_anterior = padronizar_entrada_quadro(st.session_state["grade_escala_lancamentos"].get(chave_cel, ""))
                            
                            if val_anterior != v_padrao:
                                try: data_alvo = datetime.date(m_ano, m_mes, d)
                                except ValueError: data_alvo = hoje

                                if escala_fechada and not eh_admin and data_alvo < hoje:
                                    st.error(f"🔒 O dia {d:02d} já passou e não pode ser editado.")
                                    houve_alteracao = True
                                else:
                                    status_aud, msg_aud, detalhe_conf = auditar_escalacao_militar(item['id'], m_ano, m_mes, d, v_padrao, st.session_state["grade_escala_lancamentos"])
                                    
                                    if status_aud == "BLOQUEADO":
                                        st.session_state["auditoria_pendente_popup"] = {
                                            "militar_nome": f"{item['posto_grad']} {item['nome_guerra']}",
                                            "ignorados": [{"dia": d, "equipe": detalhe_conf.get("equipe", "N/I"), "horario": detalhe_conf.get("horario", "N/I")}],
                                            "descanso": [],
                                            "val_final": v_padrao,
                                            "item_sel": item,
                                            "m_ano": m_ano,
                                            "m_mes": m_mes
                                        }
                                        houve_alteracao = True
                                        st.rerun()
                                    elif status_aud == "AVISO":
                                        st.session_state["auditoria_pendente_popup"] = {
                                            "militar_nome": f"{item['posto_grad']} {item['nome_guerra']}",
                                            "ignorados": [],
                                            "descanso": [{"dia": d, "mensagem": msg_aud}],
                                            "val_final": v_padrao,
                                            "item_sel": item,
                                            "m_ano": m_ano,
                                            "m_mes": m_mes
                                        }
                                        houve_alteracao = True
                                        st.rerun()
                                    else:
                                        salvar_estado_undo()
                                        st.session_state["grade_escala_lancamentos"][chave_cel] = v_padrao
                                        registrar_log_auditoria("Edição Direta em Tabela", f"Militar {item['nome_guerra']} dia {d:02d} alterado de '{val_anterior}' para '{v_padrao}'.")
                                        houve_alteracao = True
                            
                if houve_alteracao:
                    st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                    executar_auto_save_banco()
                    st.rerun()

        logs_atuais = st.session_state.get("logs_auditoria_lista", [])
        with st.expander(f"🛡️ Histórico de Auditoria e Alterações ({len(logs_atuais)} registros)", expanded=False):
            if logs_atuais:
                df_logs = pd.DataFrame(logs_atuais)
                df_logs.columns = ["Data / Hora", "Usuário Responsável", "Ação Realizada", "Detalhamento da Alteração"]
                st.dataframe(df_logs, use_container_width=True, hide_index=True, height=220)
            else: st.caption("Nenhum evento registrado nesta sessão.")

        st.markdown("<br>", unsafe_allow_html=True)
        col_act1, col_act2 = st.columns([1, 1])
        with col_act1:
            if not quadro_travado and (not escala_fechada or eh_admin):
                if st.button("🧹 Limpar Todo o Quadro", use_container_width=True):
                    salvar_estado_undo()
                    st.session_state["grade_escala_lancamentos"] = {}
                    st.session_state["militares_no_quadro_chaves"] = []
                    st.session_state["militares_selecionados_ids"] = []
                    st.session_state["ordem_customizada_map"] = {}
                    st.session_state["df_escala_consolidada"] = None
                    st.session_state["ajuste_saldo_map"] = {}
                    st.session_state["dias_selecionados_passo4"] = []
                    st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                    registrar_log_auditoria("Limpeza Total", "Todo o quadro mensal de escalas foi resetado pelo usuário.")
                    executar_auto_save_banco()
                    st.rerun()
            else: st.button("🧹 Limpar Todo o Quadro", use_container_width=True, disabled=True)
                
        with col_act2:
            if st.button("💾 Salvar Rascunho no Banco de Dados", type="primary", use_container_width=True):
                executar_auto_save_banco()
                registrar_log_auditoria("Salvamento Manual", "Escala gravada manualmente no banco de dados.")
                st.success("✅ Escala salva com sucesso no Supabase!")