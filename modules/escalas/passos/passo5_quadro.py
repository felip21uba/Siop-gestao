# PAINEL DE AJUSTE RÁPIDO NO QUADRO (COM SELETOR DE CALENDÁRIO)
        with st.expander("⚡ Painel de Ajuste Rápido no Quadro (Lançamento em Lote)", expanded=False):
            if mils_ord and not quadro_travado:
                dict_mils = {f"[{m['equipe']}] {m['posto_grad']} {m['nome_guerra']} ({m['num_policia']})": m for m in mils_ord}
                
                c_f1, c_f2, c_f3 = st.columns([3, 2.5, 2])
                with c_f1:
                    mils_sel_lote = st.multiselect("Militar(es):", list(dict_mils.keys()), key="p5_lote_mils")
                with c_f2:
                    # SELETOR ESTILO CALENDÁRIO PARA SELEÇÃO DE PERÍODO / DATAS
                    dt_hoje = datetime.date(m_ano, m_mes, 1)
                    datas_sel = st.date_input(
                        "Selecione a(s) Data(s) no Calendário:",
                        value=(dt_hoje, dt_hoje),
                        min_value=datetime.date(m_ano, m_mes, 1),
                        max_value=datetime.date(m_ano, m_mes, calendar.monthrange(m_ano, m_mes)[1]),
                        key="p5_cal_picker",
                        help="Clique para abrir o calendário e selecione a data inicial e final do período."
                    )
                with c_f3:
                    tipo_ev = st.selectbox(
                        "Evento/Horário:", 
                        ["Horário Normal", "FE (Férias)", "LM (Licença)", "ATE (Atestado)", "D (Descanso)", "F (Folga)", "X (Outra Equipe)", "DN (Dia Neutro)", "DNT (Neutro Trab.)", "DIS (Dispensa)"], 
                        key="p5_tipo"
                    )

                c_h1, c_h2, c_btn = st.columns([2, 2, 2])
                if "Horário Normal" in tipo_ev or "DNT" in tipo_ev:
                    with c_h1: h_i = st.time_input("Início:", datetime.time(7, 0))
                    with c_h2: h_f = st.time_input("Fim:", datetime.time(19, 0))
                    val_final = f"{h_i.strftime('%H:%M')} às {h_f.strftime('%H:%M')}" + (" (DNT)" if "DNT" in tipo_ev else "")
                else:
                    with c_h1: st.caption("Afastamento/Legenda selecionado.")
                    with c_h2: pass
                    val_final = tipo_ev.split()[0]

                with c_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("⚡ Aplicar Alteração Direta", type="primary", use_container_width=True):
                        # EXTRAI OS DIAS NUMÉRICOS A PARTIR DA SELEÇÃO DO CALENDÁRIO
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
                                    if st_aud == "BLOQUEADO":
                                        bloq.append({"militar": it["nome_guerra"], "dia": d_a, "equipe": det.get("equipe"), "horario": det.get("horario")})
                                    elif st_aud == "AVISO":
                                        avisos.append({"militar": it["nome_guerra"], "dia": d_a, "mensagem": msg_aud})
                                    else:
                                        st.session_state["grade_escala_lancamentos"][f"{it['id']}_{it['equipe']}_{m_ano}_{m_mes:02d}_{d_a:02d}"] = val_final
                                        cnt += 1
                            if cnt:
                                st.session_state["quadro_versao"] = st.session_state.get("quadro_versao", 0) + 1
                                executar_auto_save_banco()
                            if bloq or avisos:
                                st.session_state["auditoria_pendente_popup"] = {"militar_nome": "Lote", "ignorados": bloq, "descanso": avisos, "val_final": val_final, "item_sel": {}, "m_ano": m_ano, "m_mes": m_mes}
                            st.rerun()
                        else:
                            st.warning("Selecione os militares e o período no calendário!")