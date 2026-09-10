import streamlit as st
import pandas as pd
import datetime
import calendar
from modules.escalas.passos.passo3_efetivo import padronizar_graduacao, PESOS_HIERARQUIA
from core.database import registrar_log_banco, buscar_logs_banco

MESES_MAP = {
    "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, 
    "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8, 
    "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12
}

# Siglas de afastamento institucional sincronizadas com o Passo 5
SIGLAS_DIAS_NEUTROS = [
    "FER", "FERIAS", "FÉRIAS", "FE",
    "LTSP", "LM",
    "ATEST", "ATESTADO", "ATE",
    "LUTO", "NUPCIAS", "NÚPCIAS", "LUT", "NUP", "DN", "DNT"
]

def registrar_log_auditoria_local(acao, detalhe):
    """Função local para registrar ações no histórico."""
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

def executar_auto_save_banco_local():
    """Aciona a notificação de auto-save."""
    st.session_state["exibir_toast_autosave"] = True

def renderizar_passo7():
    if st.session_state.get("exibir_toast_autosave", False):
        st.toast("☁️ Banco de Horas salvo na nuvem!", icon="✅")
        st.session_state["exibir_toast_autosave"] = False

    usr_logado = st.session_state.get("usuario_dados", {})
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil_str = str(usr_logado.get("perfil", "")).upper()
    eh_admin = "PROGRAMADOR" in cargo_str or "TESTADOR" in cargo_str or "ADMIN" in perfil_str or "DESENVOLVEDOR" in cargo_str

    m_mes_atual = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    lista_meses_nomes = list(MESES_MAP.keys())
    
    escala_fechada = st.session_state.get("escala_fechada_auditoria", False)
    timezone_br = datetime.timezone(datetime.timedelta(hours=-3))
    hoje = datetime.datetime.now(timezone_br).date()

    mils_todos = st.session_state.get("lista_militares", [])
    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
    grade = st.session_state.get("grade_escala_lancamentos", {})

    if "bh_configs" not in st.session_state: 
        st.session_state["bh_configs"] = {}
        
    if "bh_lancamentos_avulsos" not in st.session_state: 
        st.session_state["bh_lancamentos_avulsos"] = []

    exp7 = st.expander("📌 PASSO 7: Banco de Horas Consolidado e Gestão de Carga", expanded=True)
    with exp7:
        if escala_fechada and not eh_admin:
            st.warning("🔒 **ESCALA HOMOLOGADA:** Eventos avulsos para dias do passado estão bloqueados pela Auditoria.")

        if not mils_todos:
            st.warning("⚠️ Nenhum militar encontrado na base de dados.")
            return

        mils_ordenados = sorted(mils_todos, key=lambda x: (
            PESOS_HIERARQUIA.get(padronizar_graduacao(x.get("posto_grad", "SD")), 99), 
            x.get("nome_guerra", "")
        ))
        
        equipes_por_militar = {}
        for pair in chaves_quadro:
            if isinstance(pair, (tuple, list)) and len(pair) == 2:
                m_id_str = str(pair[0])
                if m_id_str not in equipes_por_militar: 
                    equipes_por_militar[m_id_str] = []
                if pair[1] not in equipes_por_militar[m_id_str]: 
                    equipes_por_militar[m_id_str].append(pair[1])

        # PAINEL 1: LANÇAMENTOS AVULSOS
        with st.expander("➕ 1. Registrar Serviço Extra / Lançamento Avulso (Fórum, Instrução)", expanded=False):
            mapa_select_mils = {f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')} ({m.get('num_policia', '')})": str(m["id"]) for m in mils_ordenados}
            
            with st.form("form_avulsos_auto"):
                c_av1, c_av2, c_av3, c_av4 = st.columns([3, 2, 2, 2])
                with c_av1: 
                    mil_label_sel = st.selectbox("Selecione o Militar:", list(mapa_select_mils.keys()))
                with c_av2: 
                    data_av = st.date_input("Data do Evento:", datetime.date.today())
                with c_av3: 
                    tipo_av = st.selectbox("Tipo de Evento:", ["Fórum / Audiência", "Instrução / Curso", "Reunião Operacional", "Operação Extra", "Outros"])
                with c_av4: 
                    horas_av = st.number_input("Qtd. Horas:", min_value=0.5, step=0.5, value=4.0)
                
                obs_av = st.text_input("Descrição / NPU / Motivo:")
                
                if st.form_submit_button("📥 Creditar Horas Avulsas", type="primary"):
                    if data_av.month != m_mes_atual:
                        st.warning(f"⚠️ Atenção: Você está lançando horas no mês de {data_av.strftime('%m/%Y')}, que é diferente da escala atual ({m_mes_atual:02d}/{m_ano}).")

                    if escala_fechada and not eh_admin and data_av < hoje:
                        st.error("🔒 Eventos passados não podem ser inseridos pois a escala já está homologada.")
                    else:
                        st.session_state["bh_lancamentos_avulsos"].append({
                            "id_militar": mapa_select_mils[mil_label_sel], 
                            "nome_militar": mil_label_sel, 
                            "data": data_av.strftime("%d/%m/%Y"), 
                            "tipo": tipo_av, 
                            "horas": float(horas_av), 
                            "obs": obs_av
                        })
                        registrar_log_auditoria_local("Banco de Horas", f"Lançamento Avulso: {horas_av}h adicionadas para {mil_label_sel} no dia {data_av.strftime('%d/%m/%Y')}.")
                        executar_auto_save_banco_local()
                        st.success("Adicionado!")
                        st.rerun()

            if st.session_state["bh_lancamentos_avulsos"]:
                df_av = pd.DataFrame(st.session_state["bh_lancamentos_avulsos"])
                df_av["Excluir"] = False
                
                if "id_militar" in df_av.columns:
                    df_visual_av = df_av.drop(columns=["id_militar"])
                else:
                    df_visual_av = df_av
                
                df_edit_av = st.data_editor(
                    df_visual_av, 
                    column_config={
                        "nome_militar": st.column_config.TextColumn("Militar", disabled=True),
                        "data": st.column_config.TextColumn("Data", disabled=True),
                        "tipo": st.column_config.TextColumn("Tipo", disabled=True),
                        "horas": st.column_config.NumberColumn("Horas", disabled=True, format="%.1f h"),
                        "obs": st.column_config.TextColumn("Descrição", disabled=True),
                        "Excluir": st.column_config.CheckboxColumn("🗑️ Remover", default=False)
                    },
                    hide_index=True, 
                    width="stretch", 
                    key="editor_del_avulsos_auto"
                )
                
                if any(df_edit_av["Excluir"]):
                    indices_manter = []
                    teve_bloqueio = False
                    
                    for i in range(len(df_edit_av)):
                        if df_edit_av.iloc[i]["Excluir"]:
                            try: 
                                data_l = datetime.datetime.strptime(st.session_state["bh_lancamentos_avulsos"][i]["data"], "%d/%m/%Y").date()
                            except: 
                                data_l = hoje
                                
                            if escala_fechada and not eh_admin and data_l < hoje:
                                teve_bloqueio = True
                                indices_manter.append(i)
                            else:
                                mil_removido = st.session_state["bh_lancamentos_avulsos"][i]["nome_militar"]
                                data_removida = st.session_state["bh_lancamentos_avulsos"][i]["data"]
                                registrar_log_auditoria_local("Banco de Horas", f"Exclusão de Lançamento Avulso do militar {mil_removido} do dia {data_removida}.")
                        else:
                            indices_manter.append(i)
                            
                    if teve_bloqueio: 
                        st.error("🔒 A exclusão de lançamentos do passado foi bloqueada pela Auditoria.")
                        
                    st.session_state["bh_lancamentos_avulsos"] = [st.session_state["bh_lancamentos_avulsos"][idx] for idx in indices_manter]
                    executar_auto_save_banco_local()
                    st.rerun()

        # PAINEL 2: CONFIGURAÇÃO DE CARGA REDUZIDA E SALDO ANTERIOR
        with st.expander("⚙️ 2. Parâmetros Especiais e Saldo Anterior (Carga Reduzida)", expanded=False):
            dados_input = []
            for m in mils_ordenados:
                m_id = str(m["id"])
                cfg = st.session_state["bh_configs"].get(m_id, {})
                dados_input.append({
                    "ID": m_id,
                    "Nº PM": m.get("num_policia", ""),
                    "MILITAR": f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')}",
                    "Carga Reduzida (80h)": cfg.get("reduzida", False),
                    "Saldo Anterior (h)": float(cfg.get("saldo_anterior", 0.0))
                })
            
            df_input = pd.DataFrame(dados_input)
            
            if not df_input.empty:
                df_input.set_index("ID", inplace=True)
            
            df_editado = st.data_editor(
                df_input, 
                column_config={
                    "Nº PM": st.column_config.TextColumn("Nº PM", disabled=True),
                    "MILITAR": st.column_config.TextColumn("MILITAR", disabled=True),
                    "Carga Reduzida (80h)": st.column_config.CheckboxColumn("Carga Reduzida (80h)", help="Altera meta base para 80h"),
                    "Saldo Anterior (h)": st.column_config.NumberColumn("Saldo Anterior (h)", step=1.0, format="%.1f h")
                },
                hide_index=True,
                width="stretch", 
                key="editor_bh_auto"
            )
            
            houve_mudanca = False
            for m_id, row in df_editado.iterrows():
                m_id = str(m_id)
                nova_cfg = {
                    "reduzida": bool(row["Carga Reduzida (80h)"]), 
                    "saldo_anterior": float(row["Saldo Anterior (h)"])
                }
                
                if st.session_state["bh_configs"].get(m_id) != nova_cfg:
                    st.session_state["bh_configs"][m_id] = nova_cfg
                    houve_mudanca = True
                    
            if houve_mudanca: 
                executar_auto_save_banco_local()
                st.rerun()

        # PAINEL 3: EXTRATO FINAL E APURAÇÃO MÚLTIPLA
        with st.expander("📊 3. Apuração e Extrato Consolidado do Banco de Horas", expanded=True):
            
            c_filtro1, c_filtro2 = st.columns([1, 1])
            with c_filtro1:
                meses_selecionados_nomes = st.multiselect(
                    "📅 Selecione o(s) Mês(es):", 
                    options=lista_meses_nomes, 
                    default=[lista_meses_nomes[m_mes_atual - 1]]
                )
                meses_selecionados_num = [MESES_MAP[m] for m in meses_selecionados_nomes]
                
            with c_filtro2:
                mils_filtrados = st.multiselect(
                    "🔍 Filtrar Militares Específicos:", 
                    options=[f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')}" for m in mils_ordenados], 
                    default=[]
                )
                
            st.divider()

            if meses_selecionados_num:
                qtd_meses = len(meses_selecionados_num)
                
                if qtd_meses == 1: tipo_apuracao = "APURAÇÃO MENSAL" 
                elif qtd_meses == 2: tipo_apuracao = "APURAÇÃO BIMESTRAL"
                elif qtd_meses == 3: tipo_apuracao = "APURAÇÃO TRIMESTRAL"
                else: tipo_apuracao = f"APURAÇÃO DE {qtd_meses} MESES"
                    
                st.markdown(f"<h4 style='text-align: center; color: #1e3a8a; margin-bottom: 2px;'>📊 {tipo_apuracao}</h4>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; font-weight: bold; color: #475569; margin-top: 0px;'>Período: {', '.join(meses_selecionados_nomes)} de {m_ano}</p>", unsafe_allow_html=True)
                
                extrato_dados = []
                for m in mils_ordenados:
                    nome_formatado = f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')}"
                    
                    if mils_filtrados and nome_formatado not in mils_filtrados: 
                        continue

                    m_id = str(m["id"])
                    cfg = st.session_state["bh_configs"].get(m_id, {})
                    eh_reduzida = cfg.get("reduzida", False)
                    saldo_ant = cfg.get("saldo_anterior", 0.0)
                    
                    horas_avulsas_totais = 0.0
                    for l in st.session_state["bh_lancamentos_avulsos"]:
                        if str(l["id_militar"]) == m_id:
                            try:
                                mes_lanc = int(l["data"].split("/")[1])
                                if mes_lanc in meses_selecionados_num:
                                    horas_avulsas_totais += l["horas"]
                            except:
                                pass
                                
                    total_trabalhado_escala = 0.0
                    meta_efetiva_acumulada = 0.0
                    dias_neutros_total = 0
                    
                    for mes_calc in meses_selecionados_num:
                        dias_no_mes = calendar.monthrange(m_ano, mes_calc)[1]
                        carga_base_mes = 80.0 if eh_reduzida else 160.0
                        taxa_diaria = carga_base_mes / float(dias_no_mes)
                        
                        dias_neutros_mes = 0
                        
                        for d in range(1, dias_no_mes + 1):
                            dia_neutro = False
                            horas_no_dia = 0.0
                            
                            # Avalia globalmente o dia para este militar em todas as suas equipes
                            for eq in equipes_por_militar.get(m_id, []):
                                val = grade.get(f"{m_id}_{eq}_{m_ano}_{mes_calc:02d}_{d:02d}", "F")
                                val_str = str(val).upper().strip() if val else ""
                                tokens_dia = set(val_str.replace("/", " ").split())
                                
                                if any(sigla in tokens_dia for sigla in SIGLAS_DIAS_NEUTROS):
                                    dia_neutro = True
                                elif val_str and val_str not in ["", "F", "D", "X"]:
                                    horas_no_dia += 12.0
                                    
                            if dia_neutro:
                                dias_neutros_mes += 1
                                
                            total_trabalhado_escala += horas_no_dia
                        
                        # Cálculo Proporcional: (Dias do Mês - Dias Neutros Unificados) * Taxa Diária
                        dias_efetivos_mes = dias_no_mes - dias_neutros_mes
                        meta_efetiva_acumulada += (dias_efetivos_mes * taxa_diaria)
                        dias_neutros_total += dias_neutros_mes
                    
                    saldo_periodo = (total_trabalhado_escala + horas_avulsas_totais) - meta_efetiva_acumulada
                    
                    extrato_dados.append({
                        "Nº PM": m.get("num_policia", ""), 
                        "MILITAR": nome_formatado, 
                        "CARGA/MÊS": "80h" if eh_reduzida else "160h", 
                        "META APURADA": f"{meta_efetiva_acumulada:.1f}h", 
                        "ESCALA (P5)": f"{total_trabalhado_escala:.0f}h", 
                        "AVULSAS": f"{horas_avulsas_totais:.1f}h", 
                        "SALDO PERÍODO": f"{saldo_periodo:+.1f}h", 
                        "SALDO ANTERIOR": f"{saldo_ant:+.1f}h", 
                        "SALDO GERAL FINAL": f"{saldo_ant + saldo_periodo:+.1f}h"
                    })

                df_extrato = pd.DataFrame(extrato_dados)
                
                def colorir_saldo(val):
                    try: 
                        num_val = float(val.replace("h", "").replace("+", ""))
                        if num_val > 0:
                            return 'color: #059669; font-weight: bold;'
                        elif num_val < 0:
                            return 'color: #dc2626; font-weight: bold;'
                        else:
                            return 'color: #475569;'
                    except: 
                        return ''
                        
                if not df_extrato.empty: 
                    st.dataframe(df_extrato.style.map(colorir_saldo, subset=['SALDO PERÍODO', 'SALDO ANTERIOR', 'SALDO GERAL FINAL']), hide_index=True, width="stretch")
                
                # HTML para Impressão do Banco de Horas
                html_extrato_pdf = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; background-color: #ffffff; padding: 20px; }}
                        h3, h4 {{ text-align: center; margin: 5px 0; }}
                        table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; margin-top: 20px; }}
                        th, td {{ border: 1px solid black; padding: 6px; }}
                        th {{ background-color: #e2e8f0; font-weight: bold; }}
                        @media print {{ @page {{ size: A4 portrait; }} }}
                    </style>
                </head>
                <body>
                    <h3>POLÍCIA MILITAR DE MINAS GERAIS</h3>
                    <h4>EXTRATO DO BANCO DE HORAS - {tipo_apuracao}</h4>
                    <h4>Período: {', '.join(meses_selecionados_nomes)} de {m_ano}</h4>
                    {df_extrato.to_html(index=False, justify='center', border=1)}
                    
                    <p style="text-align: right; font-size: 10px; margin-top: 20px;">
                        Documento gerado pelo SIOP em {datetime.datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}
                    </p>
                </body>
                </html>
                """

                c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1])
                with c_btn1: 
                    st.download_button("📥 Exportar Extrato (CSV)", data=df_extrato.to_csv(index=False).encode('utf-8'), file_name=f"Banco_Horas_{m_ano}.csv", mime="text/csv", width="stretch")
                with c_btn2: 
                    if st.button("🖨️ Imprimir / PDF Oficial", width="stretch"):
                        st.html(f"{html_extrato_pdf}<script>window.print();</script>")
                with c_btn3: 
                    if st.button("💾 Fechar Período e Salvar", type="primary", width="stretch"): 
                        registrar_log_auditoria_local("Banco de Horas", "Gestor salvou o fechamento da apuração do banco de horas.")
                        executar_auto_save_banco_local()
                        st.success("Salvo com sucesso!")