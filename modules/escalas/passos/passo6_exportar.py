def renderizar_passo6():
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    num_dias_mes = calendar.monthrange(m_ano, m_mes)[1]
    
    unidade = st.session_state.get("cfg_unidade", "UNIDADE OPERACIONAL")
    subunidade = st.session_state.get("cfg_subunidade", "PEL/COMPANHIA")
    
    img_brasao_cfg = st.session_state.get("cfg_brasao_url", URL_BRASAO_PADRAO)
    img_brasao = obter_brasao_base64(img_brasao_cfg)
    
    mils_todos = st.session_state.get("lista_militares", [])
    usr_logado = st.session_state.get("usuario_dados", {})
    
    mat_usr = str(usr_logado.get("usuario_login") or usr_logado.get("usuario") or "").strip().upper()
    mil_usr_obj = next((m for m in mils_todos if str(m.get("num_policia")).strip().replace("-", "") == mat_usr.replace("-", "")), None)
    
    if mil_usr_obj:
        pg_usr = padronizar_graduacao(mil_usr_obj.get("posto_grad"))
        ng_usr = mil_usr_obj.get("nome_guerra", "OPERADOR").strip().upper()
        nome_resp_escala = f"{pg_usr} {ng_usr}"
    else:
        cargo_raw = usr_logado.get('cargo_funcao') or usr_logado.get('posto_grad') or 'ESCALANTE'
        ng_usr = usr_logado.get('nome_guerra', 'OPERADOR').strip().upper()
        nome_resp_escala = f"{padronizar_graduacao(cargo_raw)} {ng_usr}"

    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil_str = str(usr_logado.get("perfil", "")).upper()
    eh_programador_ou_admin = "PROGRAMADOR" in cargo_str or "TESTADOR" in cargo_str or "ADMIN" in perfil_str or "DESENVOLVEDOR" in cargo_str

    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
    grade_lancamentos = st.session_state.get("grade_escala_lancamentos", {})
    escala_fechada = st.session_state.get("escala_fechada_auditoria", False)

    with st.expander("📌 PASSO 6: Visualização da Escala e Exportação Oficial", expanded=True):
        
        with st.expander("➕ ⚙️ Configurações de Emissão, Assinaturas e Importação Externa", expanded=False):
            c_cfg1, c_cfg2 = st.columns([2, 2], gap="large")
            
            with c_cfg1:
                st.markdown("##### 🔒 Status de Homologação da Escala")
                if escala_fechada:
                    st.error("🔒 **ESCALA HOMOLOGADA (AUDITORIA ATIVADA)**")
                    st.caption("A edição de dias passados está bloqueada permanentemente.")
                    if eh_programador_ou_admin:
                        if st.button("🔓 Reabrir Escala (Acesso Restrito)", type="secondary", use_container_width=True):
                            st.session_state["escala_fechada_auditoria"] = False
                            st.rerun()
                else:
                    st.success("🔓 **ESCALA ABERTA (MODO RASCUNHO)**")
                    st.caption("Ao terminar o planejamento do mês, feche a escala para ativar a auditoria diária.")
                    
                    if st.button("🔒 Encerrar e Homologar Escala", type="primary", use_container_width=True):
                        st.session_state["limpar_avisos_manual"] = False
                        verificar_trava_sobreposicao()
                        
                        bloqueios_p6 = st.session_state.get("lista_bloqueios_auditoria", [])
                        avisos_descanso_p6 = st.session_state.get("lista_avisos_descanso", [])
                        
                        if bloqueios_p6 or avisos_descanso_p6:
                            st.error("🚨 **A homologação foi interrompida devido a pendências de auditoria na escala!**")
                        else:
                            st.session_state["escala_fechada_auditoria"] = True
                            st.success("✅ Escala homologada e encerrada com sucesso!")
                            st.rerun()

                bloqueios_p6 = st.session_state.get("lista_bloqueios_auditoria", [])
                avisos_descanso_p6 = st.session_state.get("lista_avisos_descanso", [])
                
                if (bloqueios_p6 or avisos_descanso_p6) and not st.session_state.get("limpar_avisos_manual", False):
                    st.markdown("---")
                    c_head_av, c_btn_fechar = st.columns([3, 1.2])
                    with c_head_av:
                        st.markdown("##### 🚨 Pendências de Auditoria:")
                    with c_btn_fechar:
                        if st.button("✖ OK / Entendido", type="secondary", use_container_width=True, key="btn_limpar_avisos_p6"):
                            st.session_state["lista_bloqueios_auditoria"] = []
                            st.session_state["lista_avisos_descanso"] = []
                            st.session_state["limpar_avisos_manual"] = True
                            st.toast("🧹 Avisos cientes!", icon="✅")
                            st.rerun()

                    if bloqueios_p6:
                        for b in bloqueios_p6:
                            st.error(f"❌ **IMPEDIMENTO ({b['militar']}):** {b['mensagem']}")

                    if avisos_descanso_p6:
                        for a in avisos_descanso_p6:
                            st.warning(f"⚠️ **ALERTA DE DESCANSO < 6H ({a['militar']}):** {a['mensagem']}")
                    st.markdown("---")

                # 🟢 NÚCLEO DE IMPORTAÇÃO EXERNA DO EXCEL DIRETO NO PASSO 6
                st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
                st.markdown("##### 📥 Importar Escala Externa em Excel")
                st.caption("Selecione a planilha (.xlsx) com a grade montada para carregar diretamente no Passo 5 e no Banco.")
                
                arq_excel_escala = st.file_uploader(
                    "Selecione o arquivo Excel da Escala:", 
                    type=["xlsx", "xls"], 
                    key="p6_uploader_excel_escala"
                )

                if arq_excel_escala is not None:
                    if st.button("🚀 Processar e Carregar no Quadro (Passo 5)", type="primary", use_container_width=True):
                        try:
                            df_imp = pd.read_excel(arq_excel_escala)
                            df_imp.columns = [str(c).strip().upper() for c in df_imp.columns]
                            
                            grade_nova = copy.deepcopy(st.session_state.get("grade_escala_lancamentos", {}))
                            chaves_novas = list(st.session_state.get("militares_no_quadro_chaves", []))
                            mils_cad = st.session_state.get("lista_militares", [])
                            
                            # Mapeia militares por matrícula e por nome de guerra
                            mapa_mils = {}
                            for m in mils_cad:
                                num_p = re.sub(r'\D', '', str(m.get("num_policia", "")))
                                ng = str(m.get("nome_guerra", "")).strip().upper()
                                if num_p: mapa_mils[num_p] = str(m["id"])
                                if ng: mapa_mils[ng] = str(m["id"])

                            linhas_importadas = 0
                            for _, row in df_imp.iterrows():
                                eq_imp = str(row.get("EQUIPE", "ADMINISTRAÇÃO")).strip().upper()
                                mil_txt = str(row.get("MILITAR", row.get("Nº POLÍCIA", ""))).strip().upper()
                                
                                # Tenta achar a ID do militar
                                num_digitos = re.sub(r'\D', '', mil_txt)
                                m_id_encontrado = mapa_mils.get(num_digitos) or mapa_mils.get(mil_txt)
                                
                                if not m_id_encontrado:
                                    # Procura substring do nome
                                    for k_nome, id_v in mapa_mils.items():
                                        if k_nome in mil_txt or mil_txt in k_nome:
                                            m_id_encontrado = id_v
                                            break

                                if m_id_encontrado:
                                    pair = (str(m_id_encontrado), eq_imp)
                                    if pair not in chaves_novas:
                                        chaves_novas.append(pair)

                                    # Percorre as colunas de dias (1 até num_dias_mes)
                                    for d in range(1, num_dias_mes + 1):
                                        col_dia_nome = next((c for c in df_imp.columns if c.startswith(str(d)) or c.startswith(f"{d:02d}")), None)
                                        if col_dia_nome:
                                            val_c = str(row.get(col_dia_nome, "")).strip()
                                            if val_c and val_c.upper() not in ["NAN", "NONE"]:
                                                grade_nova[f"{m_id_encontrado}_{eq_imp}_{m_ano}_{m_mes:02d}_{d:02d}"] = val_c
                                    linhas_importadas += 1

                            if linhas_importadas > 0:
                                st.session_state["militares_no_quadro_chaves"] = chaves_novas
                                st.session_state["grade_escala_lancamentos"] = grade_nova
                                
                                # Tenta auto-salvar no Supabase
                                from modules.escalas.passos.passo5_quadro import executar_auto_save_banco
                                executar_auto_save_banco()
                                
                                st.success(f"✅ {linhas_importadas} linha(s) de militares importadas e sincronizadas com o Passo 5!")
                                st.rerun()
                            else:
                                st.warning("Nenhum militar da planilha foi localizado no cadastro do sistema.")
                        except Exception as ex_imp:
                            st.error(f"Erro ao processar planilha de escala: {ex_imp}")

            with c_cfg2:
                st.markdown("##### ✍️ Assinaturas & Observações")
                cmt_cia = st.selectbox(
                    "Comandante da Cia / Pelotão:", 
                    options=[f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')}" for m in mils_todos] if mils_todos else ["TEN CEL LOPES"], 
                    key="p6_cmt_cia_sel"
                )
                st.text_input("Responsável pela Escala:", value=nome_resp_escala, disabled=True)
                obs_escala = st.text_area("📝 Observações e Diretrizes P1:", placeholder="Digite instruções ou notas de rodapé...", height=80, key="p6_obs_texto")

        # ... (Mantém o resto do código da visualização HTML/Exportação exatamente igual)