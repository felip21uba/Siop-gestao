import streamlit as st
import datetime
import calendar
import pandas as pd
import copy
from modules.passos.passo3_efetivo import PESOS_HIERARQUIA, padronizar_graduacao
from modules.passos.passo4_calendario import DIAS_SEMANA_SIGLAS

# Siglas de afastamento institucional que abatem os dias úteis/efetivos do mês (sem DISP/DIS)
SIGLAS_DIAS_NEUTROS = [
    "FER", "FERIAS", "FÉRIAS", "FE",
    "LTSP", "LM",
    "CURSO", "ATEST", "ATESTADO",
    "LUTO", "NUPCIAS", "NÚPCIAS", "DN", "DNT"
]

# -----------------------------------------------------------------------------
# FUNÇÕES DE DESFAZER (UNDO) E HISTÓRICO DE MEMÓRIA
# -----------------------------------------------------------------------------
def salvar_estado_undo():
    """Salva um 'retrato' do quadro antes de qualquer alteração para permitir desfazer."""
    if "pilha_undo" not in st.session_state:
        st.session_state["pilha_undo"] = []
        
    snapshot = {
        "grade": copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {})),
        "chaves": copy.deepcopy(st.session_state.get("militares_no_quadro_chaves", [])),
        "ordem": copy.deepcopy(st.session_state.get("ordem_customizada_map", {}))
    }
    
    st.session_state["pilha_undo"].append(snapshot)
    
    # Mantém apenas as últimas 10 ações registradas
    if len(st.session_state["pilha_undo"]) > 10:
        st.session_state["pilha_undo"].pop(0)

def desfazer_ultima_acao():
    """Restaura o quadro para o estado imediatamente anterior."""
    if "pilha_undo" in st.session_state and st.session_state["pilha_undo"]:
        ultimo_snapshot = st.session_state["pilha_undo"].pop()
        
        st.session_state["grade_escala_lancamentos"] = ultimo_snapshot["grade"]
        st.session_state["militares_no_quadro_chaves"] = ultimo_snapshot["chaves"]
        st.session_state["ordem_customizada_map"] = ultimo_snapshot["ordem"]
        
        registrar_log_auditoria("Desfazer Ação", "O operador reverteu a última alteração no quadro.")
        executar_auto_save_banco()
        return True
    return False

# -----------------------------------------------------------------------------
# FUNÇÕES DE LOGS E PADRONIZAÇÃO
# -----------------------------------------------------------------------------
def registrar_log_auditoria(acao, detalhe):
    """Grava ações no histórico de auditoria do sistema."""
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
    if valor is None:
        return "F"
    v = str(valor).strip().upper()
    if v in ["OFF", "DESCANSO"]:
        return "D"
    elif v in ["FOLGA"]:
        return "F"
    return valor

def extrair_datetime_de_string_turno(ano, mes, dia, str_horario):
    try:
        if "AS" not in str_horario.upper() and "ÀS" not in str_horario.upper():
            return None, None
            
        partes = str_horario.lower().replace("as", "às").split("às")
        h_i, m_i = map(int, partes[0].strip().split(":"))
        h_f, m_f = map(int, partes[1].split("(")[0].strip().split(":"))

        dt_ini = datetime.datetime(ano, mes, dia, h_i, m_i)
        
        if (h_f < h_i) or (h_f == h_i and m_f <= m_i):
            dt_fim = dt_ini + datetime.timedelta(days=1)
            dt_fim = dt_fim.replace(hour=h_f, minute=m_f)
        else:
            dt_fim = dt_ini.replace(hour=h_f, minute=m_f)
            
        return dt_ini, dt_fim
    except Exception:
        return None, None

def auditar_escalacao_militar(m_id, m_ano, m_mes, d_alvo, val_novo, dict_grade):
    dt_novo_ini, dt_novo_fim = extrair_datetime_de_string_turno(m_ano, m_mes, d_alvo, val_novo)
    
    if not dt_novo_ini:
        return "OK", ""

    num_dias = calendar.monthrange(m_ano, m_mes)[1]
    
    for d_ex in range(1, num_dias + 1):
        prefixo_chave = f"{m_id}_"
        for key_grade, val_ex in dict_grade.items():
            if key_grade.startswith(prefixo_chave) and key_grade.endswith(f"_{m_ano}_{m_mes:02d}_{d_ex:02d}"):
                if d_ex == d_alvo and val_ex == val_novo:
                    continue
                    
                dt_ex_ini, dt_ex_fim = extrair_datetime_de_string_turno(m_ano, m_mes, d_ex, val_ex)
                if not dt_ex_ini:
                    continue
                    
                if dt_novo_ini < dt_ex_fim and dt_novo_fim > dt_ex_ini:
                    eq_ex = key_grade.split("_")[1]
                    return "BLOQUEADO", f"Choque de Horário: Já escalado no dia {d_ex:02d} ({val_ex}) pela equipe {eq_ex}."

                if dt_novo_ini >= dt_ex_fim:
                    descanso = (dt_novo_ini - dt_ex_fim).total_seconds() / 3600.0
                    if 0 <= descanso < 8.0:
                        return "AVISO", f"Descanso Reduzido ({descanso:.1f}h) após o serviço do dia {d_ex:02d}."
                        
                if dt_novo_fim <= dt_ex_ini:
                    descanso = (dt_ex_ini - dt_novo_fim).total_seconds() / 3600.0
                    if 0 <= descanso < 8.0:
                        return "AVISO", f"Descanso Reduzido ({descanso:.1f}h) antes do serviço do dia {d_ex:02d}."

    return "OK", ""

def executar_auto_save_banco():
    """Aciona o salvamento automático em background."""
    st.session_state["exibir_toast_autosave"] = True

# -----------------------------------------------------------------------------
# RENDERIZAÇÃO DO PASSO 5
# -----------------------------------------------------------------------------
def renderizar_passo5():
    if st.session_state.get("exibir_toast_autosave", False):
        st.toast("☁️ Rascunho salvo na nuvem com sucesso (Auto-Save)!", icon="✅")
        st.session_state["exibir_toast_autosave"] = False

    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    
    usr_logado = st.session_state.get("usuario_dados", {})
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil_str = str(usr_logado.get("perfil", "")).upper()
    eh_admin = "PROGRAMADOR" in cargo_str or "TESTADOR" in cargo_str or "ADMIN" in perfil_str or "DESENVOLVEDOR" in cargo_str
    
    escala_fechada = st.session_state.get("escala_fechada_auditoria", False)
    timezone_br = datetime.timezone(datetime.timedelta(hours=-3))
    hoje = datetime.datetime.now(timezone_br).date()
    
    exp5 = st.expander("📌 PASSO 5: Quadro Mensal de Escalas e Carga Horária", expanded=True)
    with exp5:
        if escala_fechada:
            if not eh_admin:
                st.warning("🔒 **ESCALA HOMOLOGADA:** Edição permitida **apenas de hoje em diante**. Dias retroativos estão bloqueados.")
            else:
                st.info("🛠️ **MODO PROGRAMADOR:** Escala fechada, mas você possui privilégios para editar dias retroativos.")

        chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
        
        c_info1, c_info2 = st.columns(2)
        c_info1.info(f"👮‍♂️ **Linhas de Escala Ativas no Quadro:** `{len(chaves_quadro)}`")
        c_info2.info("💡 *Legenda `X` indica serviço ativo em outra guarnição.*")

        num_dias_mes = calendar.monthrange(m_ano, m_mes)[1]
        mils_todos = st.session_state.get("lista_militares", [])

        mils_linhas_quadro = []
        for pair in chaves_quadro:
            if isinstance(pair, (tuple, list)) and len(pair) == 2:
                m_obj = next((m for m in mils_todos if str(m["id"]) == str(pair[0])), None)
                if m_obj:
                    mils_linhas_quadro.append({
                        "id": pair[0],
                        "equipe": pair[1],
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

        # 🗑️ PAINEL DE EXCLUSÃO DIRETA COM AUDITORIA E DESFAZER
        with st.expander("🗑️ Excluir Militar ou Equipe do Quadro"):
            if escala_fechada and not eh_admin:
                st.error("🔒 **Bloqueado:** Não é possível excluir linhas ou equipes inteiras com a escala homologada para não perder o histórico retroativo.")
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
                            par_del = (item_del["id"], item_del["equipe"])
                            
                            if par_del in st.session_state["militares_no_quadro_chaves"]:
                                st.session_state["militares_no_quadro_chaves"].remove(par_del)
                                
                            for d in range(1, num_dias_mes + 1):
                                st.session_state["grade_escala_lancamentos"].pop(f"{item_del['id']}_{item_del['equipe']}_{m_ano}_{m_mes:02d}_{d:02d}", None)
                            
                            registrar_log_auditoria("Remoção de Linha", f"Militar {item_del['posto_grad']} {item_del['nome_guerra']} removido da equipe {item_del['equipe']}.")
                            executar_auto_save_banco()
                            st.rerun()
                            
                with col_ex2:
                    st.markdown("**Excluir Equipe Inteira:**")
                    equipes_no_quadro = list(set([m["equipe"] for m in mils_escala_ord]))
                    if equipes_no_quadro:
                        eq_del_sel = st.selectbox("Selecione a equipe:", equipes_no_quadro, key="p5_del_eq_sel")
                        if st.button("🔥 Excluir Toda a Equipe", key="btn_del_eq_p5", use_container_width=True):
                            salvar_estado_undo()
                            chaves_manter = []
                            for pair in st.session_state["militares_no_quadro_chaves"]:
                                if isinstance(pair, (tuple, list)) and len(pair) == 2:
                                    if pair[1] == eq_del_sel:
                                        for d in range(1, num_dias_mes + 1):
                                            st.session_state["grade_escala_lancamentos"].pop(f"{pair[0]}_{pair[1]}_{m_ano}_{m_mes:02d}_{d:02d}", None)
                                    else:
                                        chaves_manter.append(pair)
                            st.session_state["militares_no_quadro_chaves"] = chaves_manter
                            registrar_log_auditoria("Exclusão de Equipe", f"Toda a equipe '{eq_del_sel}' foi excluída do quadro.")
                            executar_auto_save_banco()
                            st.rerun()

        # ⚡ PAINEL DE AJUSTE RÁPIDO COM AUDITORIA E DESFAZER
        with st.expander("⚡ Painel de Ajuste Rápido no Quadro (Força e Precedência de Sobrescrita)", expanded=False):
            if mils_escala_ord:
                dict_mils = {f"[{m['equipe']}] {m['posto_grad']} {m['nome_guerra']} ({m['num_policia']})": m for m in mils_escala_ord}
                
                c_f1, c_f2, c_f3 = st.columns([2.5, 2, 2])
                with c_f1:
                    mil_sel_label = st.selectbox("Selecione a Linha de Escala:", list(dict_mils.keys()), key="p5_painel_mil")
                    item_sel = dict_mils[mil_sel_label]
                with c_f2:
                    dias_lista = list(range(1, num_dias_mes + 1))
                    dias_alvo = st.multiselect("Selecione o(s) Dia(s):", dias_lista, default=[1], key="p5_painel_dias")
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
                    with c_h1:
                        h_ini_p = st.time_input("Hora Início:", datetime.time(7, 0), key="p5_p_h_ini")
                    with c_h2:
                        h_fim_p = st.time_input("Hora Fim:", datetime.time(19, 0), key="p5_p_h_fim")
                    str_horario = f"{h_ini_p.strftime('%H:%M')} às {h_fim_p.strftime('%H:%M')}"
                    val_final_p = f"{str_horario} (DNT)" if "DNT" in tipo_evento else str_horario
                else:
                    with c_h1:
                        st.caption("Legenda/Afastamento selecionado.")
                    with c_h2:
                        pass
                    
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
                            dias_aplicados = []
                            dias_bloq_retroativo = []
                            erros_sobreposicao = []
                            avisos_descanso = []
                            
                            for d_a in dias_alvo:
                                data_alvo = datetime.date(m_ano, m_mes, d_a)
                                if escala_fechada and not eh_admin and data_alvo < hoje:
                                    dias_bloq_retroativo.append(d_a)
                                    continue
                                
                                status_aud, msg_aud = auditar_escalacao_militar(
                                    item_sel["id"], m_ano, m_mes, d_a, val_final_p, 
                                    st.session_state["grade_escala_lancamentos"]
                                )

                                if status_aud == "BLOQUEADO":
                                    erros_sobreposicao.append(f"Dia {d_a:02d}: {msg_aud}")
                                    continue
                                elif status_aud == "AVISO":
                                    avisos_descanso.append(f"Dia {d_a:02d}: {msg_aud}")

                                chave = f"{item_sel['id']}_{item_sel['equipe']}_{m_ano}_{m_mes:02d}_{d_a:02d}"
                                st.session_state["grade_escala_lancamentos"][chave] = val_final_p
                                dias_aplicados.append(d_a)
                                
                            if dias_bloq_retroativo:
                                st.error(f"🔒 Dias ignorados (Retroativos bloqueados por auditoria): {dias_bloq_retroativo}")
                            if erros_sobreposicao:
                                st.error("🚨 **Lançamentos Negados (Sobreposição):**\n" + "\n".join(erros_sobreposicao))
                            if avisos_descanso:
                                st.warning("⚠️ **Aviso de Descanso Interjornada (<8h):**\n" + "\n".join(avisos_descanso))
                            
                            if dias_aplicados:
                                registrar_log_auditoria(
                                    "Ajuste Rápido de Turno", 
                                    f"Militar {item_sel['posto_grad']} {item_sel['nome_guerra']} dia(s) {dias_aplicados} alterado(s) para '{val_final_p}'."
                                )
                                st.success(f"✅ Alteração lançada nos dias: {dias_aplicados}")
                                executar_auto_save_banco()
                            
                            if dias_aplicados or erros_sobreposicao:
                                st.rerun()

        st.divider()

        # 📊 RENDERIZAÇÃO DO QUADRO E CABEÇALHO DE AÇÕES COM BOTÃO DESFAZER
        col_t1, col_t2, col_t3, col_t4 = st.columns([1.5, 1, 1, 1.5])
        with col_t1: 
            st.markdown("#### 📊 Quadro Mensal")
        with col_t2:
            qtd_undo = len(st.session_state.get("pilha_undo", []))
            pode_desfazer = qtd_undo > 0
            if st.button(f"↩️ Desfazer ({qtd_undo})", disabled=not pode_desfazer, use_container_width=True):
                if desfazer_ultima_acao():
                    st.toast("↩️ Alteração desfeita com sucesso!", icon="🔄")
                    st.rerun()
        with col_t3: 
            if st.button("🔄 Atualizar", use_container_width=True, type="primary"):
                st.rerun()
        with col_t4: 
            quadro_travado = st.toggle("🔒 Travar Quadro", value=True, key="toggle_trava_quadro")

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
            nome_g = item["nome_guerra"]
            num_pol = item["num_policia"]
            ordem_atual = st.session_state["ordem_customizada_map"].get(item["chave_linha"], idx_r + 1)

            linha = {
                "ORDEM": int(ordem_atual),
                "EQUIPE": eq_nome,
                "Nº POLÍCIA": num_pol,
                "MILITAR": f"{pg} {nome_g}"
            }

            total_horas = 0.0
            dias_neutros_cnt = 0
            
            for d, col_nome in colunas_dias_nomes:
                chave_celula = f"{m_id}_{eq_nome}_{m_ano}_{m_mes:02d}_{d:02d}"
                val_atual = st.session_state["grade_escala_lancamentos"].get(chave_celula, "F")
                val_atual = padronizar_entrada_quadro(val_atual)
                
                if val_atual in ["F", "", None]:
                    for pair_k in chaves_quadro:
                        if isinstance(pair_k, (tuple, list)) and len(pair_k) == 2:
                            if str(pair_k[0]) == str(m_id) and pair_k[1] != eq_nome:
                                val_outra = st.session_state["grade_escala_lancamentos"].get(f"{m_id}_{pair_k[1]}_{m_ano}_{m_mes:02d}_{d:02d}")
                                if val_outra and val_outra not in ["F", "D", "X", "", None]:
                                    val_atual = "X"
                                    break

                linha[col_nome] = val_atual
                
                # Identificação rigorosa por tokens de palavras
                val_str = str(val_atual).upper().strip() if val_atual else ""
                tokens_dia = set(val_str.replace("/", " ").split())
                
                if any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                    dias_neutros_cnt += 1
                
                if val_str and val_str not in ["", "F", "D", "X"] and not any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                    total_horas += 12.0

            cfg_bh = st.session_state.get("bh_configs", {}).get(str(m_id), {})
            eh_reduzida = cfg_bh.get("reduzida", False)
            carga_base_mes = 80.0 if eh_reduzida else 160.0
            
            # Sincronia Proporcional com Passo 7
            taxa_diaria = carga_base_mes / float(num_dias_mes)
            dias_efetivos = num_dias_mes - dias_neutros_cnt
            meta_efetiva = max(0.0, dias_efetivos * taxa_diaria)
            excesso_horas = total_horas - meta_efetiva

            if excesso_horas > 0:
                linha["HORAS / META"] = f"⚠️ {total_horas:.1f}h / {meta_efetiva:.1f}h (+{excesso_horas:.1f}h)"
            else:
                linha["HORAS / META"] = f"{total_horas:.1f}h / {meta_efetiva:.1f}h"
                
            matriz_dados.append(linha)

        df_escala = pd.DataFrame(matriz_dados)
        st.session_state["df_escala_consolidada"] = df_escala

        # MÉTRICA DE EFETIVO MÍNIMO DIÁRIO
        if not df_escala.empty:
            with st.expander("👥 Gráfico de Efetivo Diário (Prevenção de Desfalque)", expanded=False):
                st.caption("Visão operacional: quantidade de militares escalados (trabalhando) por dia.")
                
                contagem_diaria = {d: 0 for d, _ in colunas_dias_nomes}
                for linha in matriz_dados:
                    for d, col_nome in colunas_dias_nomes:
                        val = str(linha.get(col_nome, "")).strip().upper()
                        tokens_val = set(val.replace("/", " ").split())
                        if val and val not in ["F", "D", "X"] and not any(sigla in tokens_val for sigla in SIGLAS_DIAS_NEUTROS):
                            contagem_diaria[d] += 1
                
                col_chart, col_metric = st.columns([3, 1])
                with col_chart:
                    df_chart = pd.DataFrame({
                        "Dia": [f"{d:02d}" for d in contagem_diaria.keys()],
                        "Policiais na Rua": list(contagem_diaria.values())
                    }).set_index("Dia")
                    st.bar_chart(df_chart, height=180)
                
                with col_metric:
                    min_efetivo = st.number_input("Mínimo Aceitável / Dia:", min_value=1, max_value=20, value=2, help="Alerta se o efetivo cair abaixo disso.")
                    dias_criticos = [d for d, qtd in contagem_diaria.items() if qtd < min_efetivo]
                    
                    if dias_criticos:
                        dias_str = ", ".join([f"{d:02d}" for d in dias_criticos])
                        st.error(f"🚨 **ALERTA DE DESFALQUE:**\nDias **{dias_str}** possuem menos de {min_efetivo} militar(es) ativo(s)!")
                    else:
                        st.success(f"✅ Escala coberta!\nNenhum dia possui menos de {min_efetivo} militar(es).")

            config_colunas = {
                "ORDEM": st.column_config.NumberColumn("ORDEM", min_value=1, max_value=99, step=1),
                "EQUIPE": st.column_config.SelectboxColumn("EQUIPE", options=st.session_state.get("lista_equipes", ["ADMINISTRAÇÃO", "SUPERVISÃO", "CPU", "RP", "TM ALPHA", "GEPAR"]), required=True),
                "Nº POLÍCIA": st.column_config.TextColumn("Nº POLÍCIA", disabled=True),
                "MILITAR": st.column_config.TextColumn("MILITAR", disabled=True),
                "HORAS / META": st.column_config.TextColumn("HORAS / META", disabled=True),
            }

            if quadro_travado:
                st.dataframe(df_escala, column_config=config_colunas, use_container_width=True, hide_index=True, height=450)
            else:
                df_editado = st.data_editor(df_escala, column_config=config_colunas, num_rows="fixed", use_container_width=True, hide_index=True, height=450)

                houve_alteracao = False
                for idx_r, row in df_editado.iterrows():
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
                        val_anterior = st.session_state["grade_escala_lancamentos"].get(chave_cel, "")
                        
                        if val_anterior != v_padrao:
                            try:
                                data_alvo = datetime.date(m_ano, m_mes, d)
                            except ValueError:
                                data_alvo = hoje

                            if escala_fechada and not eh_admin and data_alvo < hoje:
                                st.error(f"🔒 O dia {d:02d} já passou e não pode ser editado. Altere pelo Banco de Horas.")
                                houve_alteracao = True
                            else:
                                status_aud, msg_aud = auditar_escalacao_militar(
                                    item['id'], m_ano, m_mes, d, v_padrao, st.session_state["grade_escala_lancamentos"]
                                )
                                
                                if status_aud == "BLOQUEADO":
                                    st.error(f"🚨 Não foi possível alterar o militar {item['nome_guerra']} no dia {d:02d}. {msg_aud}")
                                    houve_alteracao = True
                                else:
                                    salvar_estado_undo()
                                    if status_aud == "AVISO":
                                        st.warning(f"⚠️ Atenção ao militar {item['nome_guerra']} (Dia {d:02d}): {msg_aud}")
                                        
                                    st.session_state["grade_escala_lancamentos"][chave_cel] = v_padrao
                                    registrar_log_auditoria(
                                        "Edição Direta em Tabela", 
                                        f"Militar {item['nome_guerra']} dia {d:02d} alterado de '{val_anterior}' para '{v_padrao}'."
                                    )
                                    houve_alteracao = True
                            
                if houve_alteracao:
                    executar_auto_save_banco()
                    st.rerun()

        # 🛡️ PAINEL DE CONSULTA DO LOG DE AUDITORIA
        logs_atuais = st.session_state.get("logs_auditoria_lista", [])
        with st.expander(f"🛡️ Histórico de Auditoria e Alterações ({len(logs_atuais)} registros)", expanded=False):
            if logs_atuais:
                df_logs = pd.DataFrame(logs_atuais)
                df_logs.columns = ["Data / Hora", "Usuário Responsável", "Ação Realizada", "Detalhamento da Alteração"]
                st.dataframe(df_logs, use_container_width=True, hide_index=True, height=220)
            else:
                st.caption("Nenhum evento registrado nesta sessão.")

        st.markdown("<br>", unsafe_allow_html=True)
        col_act1, col_act2 = st.columns([1, 1])
        with col_act1:
            if not escala_fechada or eh_admin:
                if st.button("🧹 Limpar Todo o Quadro", use_container_width=True):
                    salvar_estado_undo()
                    st.session_state["grade_escala_lancamentos"] = {}
                    st.session_state["militares_no_quadro_chaves"] = []
                    st.session_state["ordem_customizada_map"] = {}
                    st.session_state["df_escala_consolidada"] = None
                    registrar_log_auditoria("Limpeza Total", "Todo o quadro mensal de escalas foi resetado pelo usuário.")
                    executar_auto_save_banco()
                    st.rerun()
            else:
                st.button("🧹 Limpar Todo o Quadro", use_container_width=True, disabled=True, help="Bloqueado: Escala Fechada.")
                
        with col_act2:
            if st.button("💾 Salvar Rascunho no Banco de Dados", type="primary", use_container_width=True):
                executar_auto_save_banco()
                registrar_log_auditoria("Salvamento Manual", "Escala gravada manualmente no banco de dados.")
                st.success("✅ Escala salva com sucesso!")