import streamlit as st
import pandas as pd
from core.database import supabase, registrar_audit_log

# =========================================================================
# 🏛️ PAINEL DE LISTAGEM E EXCLUSÃO DE UNIDADES (MULTI-TENANT)
# =========================================================================

def exibir_painel_gestao_unidades():
    st.markdown("##### 📋 Unidades Cadastradas no SIOP")
    st.caption("Visualização e administração global das unidades cadastradas no banco de dados.")

    if not supabase:
        st.error("⚠️ Conexão com o Supabase indisponível.")
        return

    try:
        res = supabase.table("configuracao_unidade").select("*").execute()
        unidades = res.data or []
    except Exception as ex:
        st.error(f"Erro ao carregar lista de unidades: {ex}")
        unidades = []

    if not unidades:
        st.info("ℹ️ Nenhuma unidade cadastrada no momento.")
        return

    for uni in unidades:
        id_uni = uni.get("id")
        unidade_nome = uni.get("unidade_nome", "Não Informada")
        subunidade_nome = uni.get("subunidade_nome", "Não Informada")

        with st.container():
            col_info, col_acao = st.columns([4, 1])
            
            with col_info:
                st.markdown(f"**🏛️ Unidade:** {unidade_nome}")
                st.caption(f"📍 **Subunidade / Cia:** {subunidade_nome}")
            
            with col_acao:
                if st.button("🗑️ Excluir", key=f"btn_del_uni_{id_uni}", type="secondary"):
                    st.session_state[f"confirm_del_{id_uni}"] = True

            if st.session_state.get(f"confirm_del_{id_uni}"):
                st.warning(f"⚠️ Confirmar exclusão da unidade **{unidade_nome}**?")
                c_sim, c_nao = st.columns(2)
                
                with c_sim:
                    if st.button("✅ Confirmar Exclusão", key=f"btn_conf_yes_{id_uni}", type="primary"):
                        try:
                            supabase.table("configuracao_unidade").delete().eq("id", id_uni).execute()
                            st.success(f"Unidade '{unidade_nome}' excluída!")
                            st.session_state[f"confirm_del_{id_uni}"] = False
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Erro ao excluir unidade: {ex}")
                            
                with c_nao:
                    if st.button("❌ Cancelar", key=f"btn_conf_no_{id_uni}"):
                        st.session_state[f"confirm_del_{id_uni}"] = False
                        st.rerun()

        st.divider()

# =========================================================================
# ⚙️ TELA PRINCIPAL DE GESTÃO DE ACESSOS E UNIDADES
# =========================================================================

def salvar_permissao_militar(matricula, novo_nivel, ativo=True):
    """Função utilitária para gravar permissão de um usuário no Supabase"""
    if supabase:
        try:
            supabase.table("usuarios").update({
                "nivel_acesso": novo_nivel, 
                "ativo": ativo
            }).or_(f"usuario_login.eq.{matricula},usuario.eq.{matricula}").execute()
            return True
        except Exception:
            return False
    return False

def exibir_tela_gestao_usuarios():
    st.title("⚙️ Painel de Gestão de Níveis de Acesso e Permissões SIOP")
    st.caption("Gerencie atribuições funcionais, permissões por fração e ações de comando sobre as contas do efetivo.")
    st.divider()

    # Controle de versão de cache (Força recarregamento da tabela na tela)
    if "gestao_usr_version" not in st.session_state:
        st.session_state["gestao_usr_version"] = 0

    usr = st.session_state.get("usuario_dados") or {}
    usr_atual_nivel = usr.get("nivel_acesso", "TROPA")
    usr_id_operador = usr.get("usuario", "")

    if usr_atual_nivel not in ["PROGRAMADOR", "GESTOR", "COMANDANTE_CIA", "P1", "SARGENTEANTE", "ADMIN"]:
        st.error("⛔ **Acesso Negado:** Você não possui permissão para gerenciar níveis de acesso.")
        return

    aba_permissao_efetivo, aba_cadastrar_unidade, aba_lista_unidades = st.tabs([
        "👥 Permissões por Lotação & Ações de Conta",
        "🏛️ Cadastrar Nova Unidade / Batalhão",
        "📋 Lista de Unidades Cadastradas"
    ])

    # Busca a lista real de usuários cadastrados no banco
    usuarios_banco = []
    if supabase:
        try:
            res_usrs = supabase.table("usuarios").select("usuario_login, usuario, nome_guerra, cargo_funcao, nivel_acesso, ativo").execute()
            usuarios_banco = res_usrs.data or []
        except Exception:
            usuarios_banco = []

    # ---------------------------------------------------------------------
    # ABA 1: PERMISSÕES E AÇÕES DE CONTA DO EFETIVO
    # ---------------------------------------------------------------------
    with aba_permissao_efetivo:
        
        # 1.1 CADASTRO RÁPIDO DE USUÁRIO
        with st.expander("➕ Cadastrar Operador (Sem Efetivo Pré-Cadastrado)"):
            with st.form("form_criar_user_manual", clear_on_submit=True):
                st.caption("Insira os dados se o militar não constar na lista padrão (Efetivo).")
                c_u1, c_u2, c_u3 = st.columns([2,2,3])
                with c_u1: cad_matr = st.text_input("Matrícula / Nº PM *")
                with c_u2: cad_posto = st.selectbox("Posto/Graduação", ["SD PM", "CB PM", "3º SGT PM", "2º SGT PM", "1º SGT PM", "SUB TEN PM", "2º TEN PM", "1º TEN PM", "CAP PM", "MAJ PM", "TEN CEL PM", "CEL PM"])
                with c_u3: cad_nome = st.text_input("Nome de Guerra *")
                
                c_u4, c_u5 = st.columns(2)
                with c_u4: cad_perfil = st.selectbox("Perfil de Acesso", ["TROPA", "SARGENTEANTE", "CMT_PELOTAO", "P1", "COMANDANTE_CIA", "PROGRAMADOR"])
                with c_u5: cad_email = st.text_input("E-mail (Opcional)")
                
                if st.form_submit_button("Criar Conta", type="primary"):
                    if not cad_matr or not cad_nome:
                        st.error("Preencha Matrícula e Nome de Guerra.")
                    else:
                        if supabase:
                            try:
                                supabase.table("usuarios").insert({
                                    "usuario_login": cad_matr,
                                    "usuario": cad_matr,
                                    "nome_guerra": cad_nome.upper(),
                                    "cargo_funcao": cad_posto,
                                    "nivel_acesso": cad_perfil,
                                    "email": cad_email,
                                    "ativo": True,
                                    "primeiro_acesso": True
                                }).execute()
                                st.session_state["gestao_usr_version"] += 1
                                st.success(f"Conta para {cad_nome} criada com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao cadastrar usuário: {e}")

        # 1.2 EDIÇÃO EM BLOCO (LOTE)
        st.markdown("##### ⚡ Alteração de Perfis em Bloco")
        dict_mils = {}
        for u in usuarios_banco:
            matr = u.get("usuario_login") or u.get("usuario")
            rotulo = f"[{matr}] {u.get('cargo_funcao','')} {u.get('nome_guerra','')} - (Atual: {u.get('nivel_acesso')})"
            dict_mils[rotulo] = matr

        if dict_mils:
            c_bl1, c_bl2 = st.columns([3, 2])
            with c_bl1:
                selecionados = st.multiselect("Selecione os Usuários:", list(dict_mils.keys()))
            with c_bl2:
                novo_perfil_lote = st.selectbox(
                    "Novo Perfil / Função:", 
                    ["TROPA", "CMT_FRACAO", "SARGENTEANTE", "CMT_PELOTAO", "P1", "COMANDANTE_CIA", "PROGRAMADOR"]
                )

            if st.button("⚡ Aplicar Perfil aos Selecionados", type="primary", use_container_width=True):
                if not selecionados:
                    st.warning("Selecione ao menos um usuário.")
                else:
                    sucesso_qtd = 0
                    for label in selecionados:
                        matr_alvo = dict_mils[label]
                        if salvar_permissao_militar(matr_alvo, novo_perfil_lote):
                            sucesso_qtd += 1
                            registrar_audit_log(usr_id_operador, matr_alvo, "ALTERAR_PERMISSAO_LOTE", f"Nível de permissão alterado para [{novo_perfil_lote}] em lote.")
                    
                    st.session_state["gestao_usr_version"] += 1
                    st.success(f"✅ {sucesso_qtd} conta(s) atualizada(s) para {novo_perfil_lote}.")
                    st.rerun()

        st.divider()

        # 1.3 QUADRO GERAL COM EDIÇÃO DIRETA
        col_q1, col_q2 = st.columns([3, 1])
        with col_q1: st.markdown("##### 📜 Quadro Geral de Acessos")
        with col_q2: 
            if st.button("🔄 Recarregar", use_container_width=True):
                st.session_state["gestao_usr_version"] += 1
                st.rerun()

        if usuarios_banco:
            df_usr = pd.DataFrame(usuarios_banco)
            df_usr["Matrícula"] = df_usr["usuario_login"].fillna(df_usr["usuario"])
            
            # Assegura que a coluna "ativo" exista
            if "ativo" not in df_usr.columns:
                df_usr["ativo"] = True
                
            df_display = df_usr[["Matrícula", "cargo_funcao", "nome_guerra", "nivel_acesso", "ativo"]].copy()
            df_display.columns = ["MATRÍCULA", "POSTO/GRAD", "MILITAR", "PERFIL DE ACESSO", "CONTA ATIVA"]

            config_cols = {
                "MATRÍCULA": st.column_config.TextColumn("MATRÍCULA", disabled=True),
                "POSTO/GRAD": st.column_config.TextColumn("POSTO/GRAD", disabled=True),
                "MILITAR": st.column_config.TextColumn("MILITAR", disabled=True),
                "PERFIL DE ACESSO": st.column_config.SelectboxColumn("PERFIL DE ACESSO", options=["TROPA", "CMT_FRACAO", "SARGENTEANTE", "CMT_PELOTAO", "P1", "COMANDANTE_CIA", "PROGRAMADOR"], required=True),
                "CONTA ATIVA": st.column_config.CheckboxColumn("CONTA ATIVA")
            }

            chave_editor = f"editor_acessos_v{st.session_state['gestao_usr_version']}"
            df_editado = st.data_editor(
                df_display, 
                column_config=config_cols, 
                hide_index=True, 
                use_container_width=True, 
                key=chave_editor
            )

            houve_mudanca = False
            for idx, row in df_editado.iterrows():
                matr = str(row["MATRÍCULA"])
                p_novo = str(row["PERFIL DE ACESSO"])
                s_novo = bool(row["CONTA ATIVA"])
                
                # Procura os dados antigos para ver se mudou
                u_antigo = next((u for u in usuarios_banco if (u.get("usuario_login") == matr or u.get("usuario") == matr)), {})
                p_antigo = u_antigo.get("nivel_acesso")
                s_antigo = u_antigo.get("ativo", True)
                
                if p_novo != p_antigo or s_novo != s_antigo:
                    if salvar_permissao_militar(matr, p_novo, s_novo):
                        houve_mudanca = True

            if houve_mudanca:
                st.session_state["gestao_usr_version"] += 1
                st.success("✅ Edições individuais salvas no banco de dados!")
                st.rerun()

        st.divider()

        # 1.4 AÇÕES DE COMANDO EMERGENCIAIS (DERRUBAR SESSÃO / RESET)
        st.markdown("##### 🛠️ Ações de Comando sobre Acessos")
        col_act1, col_act2, col_act3 = st.columns(3)
        opcoes_acoes = [u.get("usuario_login") or u.get("usuario") for u in usuarios_banco] if usuarios_banco else ["Nenhum"]

        with col_act1:
            st.markdown("**🛑 Derrubar Sessão Ativa:**")
            milit_derrubar_pm = st.selectbox(
                "Selecione o usuário:",
                opcoes_acoes,
                format_func=lambda x: next((f"{u.get('nome_guerra','')} ({x})".strip() for u in usuarios_banco if (u.get('usuario_login') == x or u.get('usuario') == x)), x),
                key="sel_derrubar_s"
            )
            if st.button("🚫 Desconectar Dispositivo", use_container_width=True):
                if supabase and milit_derrubar_pm != "Nenhum":
                    try:
                        supabase.table("usuarios").update({"token_sessao_ativa": "REVOGADO", "token_recuperacao": "REVOGADO"}).or_(f"usuario_login.eq.{milit_derrubar_pm},usuario.eq.{milit_derrubar_pm}").execute()
                    except Exception:
                        pass
                registrar_audit_log(usr_id_operador, milit_derrubar_pm, "DERRUBAR_SESSAO", "Sessão encerrada remotamente pelo Gestor")
                st.success("✅ Sessão do usuário desconectada!")

        with col_act2:
            st.markdown("**🔄 Resetar para Senha Padrão:**")
            milit_reset_pm = st.selectbox(
                "Selecione o usuário:",
                opcoes_acoes,
                format_func=lambda x: next((f"{u.get('nome_guerra','')} ({x})".strip() for u in usuarios_banco if (u.get('usuario_login') == x or u.get('usuario') == x)), x),
                key="sel_reset_s"
            )
            if st.button("🔑 Resetar Credenciais Iniciais", use_container_width=True):
                if milit_reset_pm != "Nenhum":
                    pm_limpo = str(milit_reset_pm).replace("-", "").replace(".", "").strip().lower()
                    
                    if supabase:
                        try:
                            supabase.table("usuarios").update({
                                "primeiro_acesso": True,
                                "mfa_habilitado": False,
                                "mfa_secret": None,
                                "senha_hash": None,
                                "token_sessao_ativa": None,
                                "token_recuperacao": None,
                                "ativo": True,
                                "tentativas_erradas": 0
                            }).or_(f"usuario_login.eq.{milit_reset_pm},usuario.eq.{pm_limpo}").execute()
                        except Exception:
                            pass
                            
                    registrar_audit_log(usr_id_operador, milit_reset_pm, "RESET_SENHA", "Credenciais resetadas para a senha padrão e conta desbloqueada")
                    st.success("✅ Conta restaurada para a senha padrão e desbloqueada com sucesso!")

        with col_act3:
            st.markdown("**📱 Resetar Apenas o 2FA (Novo Celular):**")
            milit_2fa_pm = st.selectbox(
                "Selecione o usuário:",
                opcoes_acoes,
                format_func=lambda x: next((f"{u.get('nome_guerra','')} ({x})".strip() for u in usuarios_banco if (u.get('usuario_login') == x or u.get('usuario') == x)), x),
                key="sel_2fa_s"
            )
            if st.button("📲 Gerar Novo QR Code 2FA", use_container_width=True):
                if supabase and milit_2fa_pm != "Nenhum":
                    try:
                        supabase.table("usuarios").update({
                            "mfa_habilitado": False,
                            "mfa_secret": None
                        }).or_(f"usuario_login.eq.{milit_2fa_pm},usuario.eq.{milit_2fa_pm}").execute()
                    except Exception:
                        pass
                registrar_audit_log(usr_id_operador, milit_2fa_pm, "RESET_2FA", "Vínculo de autenticador 2FA removido para recadastro em novo dispositivo")
                st.success("✅ Vínculo de 2FA removido. Novo QR Code será exigido no próximo login.")

    # ---------------------------------------------------------------------
    # ABA 2: FORMULÁRIO DE CADASTRO DE UNIDADES
    # ---------------------------------------------------------------------
    with aba_cadastrar_unidade:
        st.markdown("##### 🏛️ Cadastro de Novas Unidades / Batalhões (Multi-Tenant)")
        with st.form("form_nova_unidade_multitenant", clear_on_submit=True):
            c_un_a, c_un_b = st.columns(2)
            with c_un_a:
                nova_unidade_nome = st.text_input("Nome da Nova Unidade / Batalhão:", placeholder="Ex: 47º BPM / 4ª RPM").strip().upper()
                nova_subunidade_nome = st.text_input("Companhia / Subunidade Principal:", placeholder="Ex: 75ª CIA PM / CARANGOLA").strip().upper()
            with c_un_b:
                nova_brasao_url = st.text_input("URL do Brasão da Unidade (Opcional):", value="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Bras%C3%A3o_PMMG.svg/500px-Bras%C3%A3o_PMMG.svg.png").strip()

            st.markdown("<br>", unsafe_allow_html=True)
            btn_cadastrar_unidade = st.form_submit_button("🏛️ Cadastrar Nova Unidade no SIOP")

            if btn_cadastrar_unidade and nova_unidade_nome and nova_subunidade_nome:
                if supabase:
                    try:
                        supabase.table("configuracao_unidade").insert({
                            "unidade_nome": nova_unidade_nome,
                            "subunidade_nome": nova_subunidade_nome,
                            "brasao_url": nova_brasao_url
                        }).execute()
                        registrar_audit_log(usr_id_operador, None, "CADASTRAR_UNIDADE", f"Nova unidade cadastrada: {nova_unidade_nome} / {nova_subunidade_nome}")
                        st.success(f"✅ Unidade '{nova_unidade_nome}' cadastrada no Supabase!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar unidade: {e}")

    # ---------------------------------------------------------------------
    # ABA 3: LISTAGEM E EXCLUSÃO DE UNIDADES
    # ---------------------------------------------------------------------
    with aba_lista_unidades:
        exibir_painel_gestao_unidades()