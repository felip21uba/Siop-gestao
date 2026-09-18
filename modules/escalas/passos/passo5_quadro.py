def renderizar_passo5():
    # 1. VERIFICAÇÃO IMEDIATA DE MODO SEGUNDA TELA / POP-OUT VIA PARÂMETRO DA URL
    query_params = st.query_params
    if query_params.get("modo_monitor") == "segunda_tela":
        renderizar_modo_segunda_tela()
        return

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
        # CABEÇALHO COMPACTO EM LINHA ÚNICA (TEXTO + APLICAR + SEGUNDA TELA)
        col_inf, col_btn_app, col_btn_pop = st.columns([2.5, 2.5, 1.5])
        
        with col_inf:
            st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
            st.caption(f"👮‍♂️ **Linhas Ativas:** `{len(st.session_state.get('militares_no_quadro_chaves', []))}` | 💡 *Legenda `X` = serviço em outra equipe.*")
            
        with col_btn_app:
            if st.button("⚡ Aplicar Lançamentos e Atualizar Quadro", type="primary", use_container_width=True, key="btn_atualizar_quadro_p5_linha"):
                st.session_state["atualizar_quadro_passo5"] = True
                st.rerun()
                
        with col_btn_pop:
            if st.button("🖥️ Segunda Tela (Pop-out)", type="secondary", use_container_width=True, key="btn_popout_2tela"):
                token_atual = st.session_state.get("token_sessao_local", "sessao_valida")
                js_popout = f"""
                <script>
                    var baseUrl = window.top.location.href.split('?')[0];
                    var popoutUrl = baseUrl + '?modo_monitor=segunda_tela&token={token_atual}';
                    window.top.open(popoutUrl, 'QuadroGeralPopOut', 'width=1280,height=800,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes');
                </script>
                """
                components.html(js_popout, height=0)

        num_dias = calendar.monthrange(m_ano, m_mes)[1]
        mils_todos = st.session_state.get("lista_militares", [])
        mils_linhas = [{"id": str(p[0]), "equipe": str(p[1]), "posto_grad": m.get("posto_grad", "SD"), "nome_guerra": m.get("nome_guerra", "MILITAR"), "num_policia": m.get("num_policia", ""), "chave_linha": f"{p[0]}_{p[1]}"} for p in st.session_state.get("militares_no_quadro_chaves", []) if len(p) == 2 for m in [next((x for x in mils_todos if str(x.get("id")) == str(p[0])), {})] if m]

        st.session_state.setdefault("ordem_customizada_map", {})
        for idx, item in enumerate(mils_linhas): st.session_state["ordem_customizada_map"].setdefault(item["chave_linha"], idx + 1)
        mils_ord = sorted(mils_linhas, key=lambda x: (st.session_state["ordem_customizada_map"].get(x["chave_linha"], 99), PESOS_HIERARQUIA.get(padronizar_graduacao(x["posto_grad"]), 99), x["nome_guerra"]))

        # PAINEL DE AJUSTE RÁPIDO COMPACTADO EM LINHA ÚNICA
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
                    max_value=datetime.date(m_ano, m_mes, calendar.monthrange(m_ano, m_mes)[1]), 
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
                    
                    val_final = f"{h_i.strftime('%H:%M')} às {h_f.strftime('%H:%M')}" + (" (DNT)" if "DNT" in tipo_ev else "")
                else:
                    val_final = tipo_ev.split()[0]
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