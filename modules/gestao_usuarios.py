import streamlit as st
import pandas as pd
from core.database import supabase, registrar_audit_log, carregar_militares_supabase
from core.auth import gerar_hash_senha

# =========================================================================
# 🎯 DEFINIÇÃO CENTRAL DOS PERFIS E NÍVEIS DE ACESSO SIOP
# =========================================================================
PERFIS_NIVEL_GERAL = [
    "PROGRAMADOR", 
    "ADMIN", 
    "GESTOR", 
    "P1", 
    "P3", 
    "COMANDANTE_CIA", 
    "CMT_PELOTAO", 
    "SARGENTEANTE", 
    "TROPA"
]

PERFIS_CREDS = ["GESTOR_UNIDADE", "GESTOR_CIA", "OPERADOR", "TROPA"]
PERFIS_ESCALA = ["CMT_CIA", "SARGENTIACAO", "AUXILIAR_CIA", "TROPA"]

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

def salvar_permissao_militar(matricula, perfil_creds=None, perfil_escala=None, nivel_acesso=None, ativo=True, posto="SD", nome="MILITAR", nome_completo=None):
    """Grava/atualiza permissões por módulo e perfil geral na tabela 'usuarios' do Supabase."""
    if supabase and matricula:
        try:
            m_clean = str(matricula).strip().upper()
            
            payload_update = {"ativo": ativo}
            if perfil_creds is not None:
                payload_update["perfil_creds"] = perfil_creds
            if perfil_escala is not None:
                payload_update["perfil_escala"] = perfil_escala
            if nivel_acesso is not None:
                payload_update["nivel_acesso"] = nivel_acesso
            if nome_completo:
                payload_update["nome_completo"] = nome_completo

            res = supabase.table("usuarios").select("usuario_login").or_(f"usuario_login.eq.{m_clean},usuario.eq.{m_clean}").execute()
            
            if res and res.data and len(res.data) > 0:
                try:
                    supabase.table("usuarios").update(payload_update).or_(f"usuario_login.eq.{m_clean},usuario.eq.{m_clean}").execute()
                except Exception:
                    # Fallback caso a coluna nome_completo ainda nao exista na tabela usuarios
                    payload_update.pop("nome_completo", None)
                    supabase.table("usuarios").update(payload_update).or_(f"usuario_login.eq.{m_clean},usuario.eq.{m_clean}").execute()
            else:
                hash_init = gerar_hash_senha(m_clean)
                payload_insert = {
                    "usuario_login": m_clean,
                    "usuario": m_clean,
                    "nome_guerra": str(nome).upper(),
                    "nome_completo": str(nome_completo or nome).upper(),
                    "cargo_funcao": str(posto).upper(),
                    "nivel_acesso": nivel_acesso or "TROPA",
                    "perfil_creds": perfil_creds or "TROPA",
                    "perfil_escala": perfil_escala or "TROPA",
                    "senha": m_clean,
                    "senha_hash": hash_init,
                    "ativo": ativo,
                    "primeiro_acesso": True
                }
                try:
                    supabase.table("usuarios").insert(payload_insert).execute()
                except Exception:
                    payload_insert.pop("nome_completo", None)
                    supabase.table("usuarios").insert(payload_insert).execute()

            st.cache_data.clear()
            return True
        except Exception as e:
            print(f"Erro ao salvar permissão do militar {matricula}: {e}")
            return False
    return False

def exibir_tela_gestao_usuarios():
    st.title("⚙️ Painel de Gestão de Níveis de Acesso e Permissões SIOP")
    st.caption("Atribua perfis independentes por módulo (CREDS e Escalas) e administre os níveis gerais do sistema.")
    st.divider()

    if "gestao_usr_version" not in st.session_state:
        st.session_state["gestao_usr_version"] = 0

    usr = st.session_state.get("usuario_dados") or {}
    usr_atual_nivel = usr.get("nivel_acesso", "TROPA")
    usr_id_operador = usr.get("usuario_login") or usr.get("usuario") or usr.get("nome_guerra", "OPERADOR")

    if usr_atual_nivel not in ["PROGRAMADOR", "ADMIN", "GESTOR", "COMANDANTE_CIA", "P1", "SARGENTEANTE"]:
        st.error("⛔ **Acesso Negado:** Você não possui permissão para gerenciar níveis de acesso.")
        return

    aba_permissao_efetivo, aba_cadastrar_unidade, aba_lista_unidades = st.tabs([
        "👥 Efetivo & Sincronização de Contas",
        "🏛️ Cadastrar Nova Unidade / Batalhão",
        "📋 Lista de Unidades Cadastradas"
    ])

    efetivo_banco = carregar_militares_supabase() or []

    usuarios_banco = []
    if supabase:
        try:
            # Usa select("*") para evitar erros quando uma coluna especifica nao existe no banco
            res_usrs = supabase.table("usuarios").select("*").execute()
            usuarios_banco = res_usrs.data or []
        except Exception as e:
            st.warning(f"Aviso ao consultar usuários no Supabase: {e}")
            usuarios_banco = []

    dict_usuarios_existentes = {}
    for u in usuarios_banco:
        m_key = str(u.get("usuario_login") or u.get("usuario") or "").strip().upper()
        if m_key:
            dict_usuarios_existentes[m_key] = u

    # ABA 1: GERENCIAMENTO DE ACESSOS DIRETO DO EFETIVO
    with aba_permissao_efetivo:
        c_sync1, c_sync2 = st.columns([3, 1])
        with c_sync1:
            st.markdown("##### ⚡ Sincronização em Bloco do Efetivo")
            st.caption(f"Total de Militares: **{len(efetivo_banco)}** | Contas em 'Usuários': **{len(usuarios_banco)}**")
        with c_sync2:
            if st.button("🚀 Sincronizar Todas as Contas", type="primary", use_container_width=True):
                if not efetivo_banco:
                    st.warning("Nenhum militar cadastrado no Efetivo.")
                else:
                    novas_contas_qtd = 0
                    for m in efetivo_banco:
                        num_pm = str(m.get("num_policia", "")).strip().upper()
                        if num_pm and num_pm != "N/I":
                            if num_pm not in dict_usuarios_existentes:
                                nome_comp_m = m.get("nome_completo") or f"{m.get('posto_grad','')} {m.get('nome_guerra','')}"
                                if salvar_permissao_militar(
                                    matricula=num_pm,
                                    perfil_creds="TROPA",
                                    perfil_escala="TROPA",
                                    nivel_acesso=m.get("nivel_acesso", "TROPA"),
                                    ativo=True,
                                    posto=m.get("posto_grad", "SD PM"),
                                    nome=m.get("nome_guerra", "MILITAR"),
                                    nome_completo=nome_comp_m
                                ):
                                    novas_contas_qtd += 1
                    
                    registrar_audit_log(usr_id_operador, None, "SINCRONIZAR_EFETIVO_EM_BLOCO", f"Sincronização em bloco executada. {novas_contas_qtd} novas contas criadas.")
                    st.session_state["gestao_usr_version"] += 1
                    st.success(f"✅ {novas_contas_qtd} conta(s) criada(s) com senha inicial padrão.")
                    st.rerun()

        st.divider()

        # EDIÇÃO EM LOTE POR SELEÇÃO (COM NOME COMPLETO E NÍVEL GERAL)
        st.markdown("##### 🎯 Alteração de Perfis em Lote")
        dict_mils_options = {}
        for m in efetivo_banco:
            num_pm = str(m.get("num_policia", "")).strip().upper()
            if num_pm and num_pm != "N/I":
                usr_cad = dict_usuarios_existentes.get(num_pm, {})
                nome_comp = m.get("nome_completo") or usr_cad.get("nome_completo") or f"{m.get('posto_grad','')} {m.get('nome_guerra','')}"
                status_txt = f"CREDS: {usr_cad.get('perfil_creds', 'TROPA')} | ESCALA: {usr_cad.get('perfil_escala', 'TROPA')} | GERAL: {usr_cad.get('nivel_acesso', 'TROPA')}" if usr_cad else "Sem Conta Criada"
                rotulo = f"[{num_pm}] {m.get('posto_grad','')} {nome_comp} - ({status_txt})"
                dict_mils_options[rotulo] = m

        if dict_mils_options:
            c_bl1, c_bl2, c_bl3, c_bl4 = st.columns([2.2, 1.2, 1.2, 1.4])
            with c_bl1:
                selecionados = st.multiselect("Selecione os Militares (Busca por Nome Completo ou Matrícula):", list(dict_mils_options.keys()))
            with c_bl2:
                perfil_creds_lote = st.selectbox("Função CREDS:", PERFIS_CREDS)
            with c_bl3:
                perfil_escala_lote = st.selectbox("Função ESCALA:", PERFIS_ESCALA)
            with c_bl4:
                idx_tropa = PERFIS_NIVEL_GERAL.index("TROPA") if "TROPA" in PERFIS_NIVEL_GERAL else 0
                nivel_geral_lote = st.selectbox("Nível Geral (Menu):", PERFIS_NIVEL_GERAL, index=idx_tropa)

            if st.button("⚡ Aplicar Perfis e Nível Geral aos Selecionados", type="primary", use_container_width=True):
                if not selecionados:
                    st.warning("Selecione ao menos um militar.")
                else:
                    sucesso_qtd = 0
                    for label in selecionados:
                        m_obj = dict_mils_options[label]
                        num_pm = str(m_obj.get("num_policia")).strip().upper()
                        nome_comp_m = m_obj.get("nome_completo") or f"{m_obj.get('posto_grad','')} {m_obj.get('nome_guerra','')}"
                        if salvar_permissao_militar(
                            matricula=num_pm, 
                            perfil_creds=perfil_creds_lote,
                            perfil_escala=perfil_escala_lote,
                            nivel_acesso=nivel_geral_lote,
                            ativo=True,
                            posto=m_obj.get("posto_grad", "SD PM"),
                            nome=m_obj.get("nome_guerra", "MILITAR"),
                            nome_completo=nome_comp_m
                        ):
                            sucesso_qtd += 1
                            registrar_audit_log(usr_id_operador, num_pm, "ALTERAR_PERMISSAO_LOTE", f"CREDS: [{perfil_creds_lote}] | ESCALA: [{perfil_escala_lote}] | GERAL: [{nivel_geral_lote}].")
                    
                    st.session_state["gestao_usr_version"] += 1
                    st.success(f"✅ {sucesso_qtd} militar(es) atualizado(s) com sucesso!")
                    st.rerun()

        st.divider()

        # QUADRO GERAL DO EFETIVO COM EDIÇÃO DIRETA
        with st.expander("📜 Tabela Geral de Permissões Duplas e Nível Geral (Clique para expandir)", expanded=True):
            col_q1, col_q2 = st.columns([3, 1])
            with col_q1: 
                st.caption("💡 **Nível Geral (Perfil do Sistema):** Define o nível de autoridade no menu principal (ex: **TROPA** acessa apenas sua escala/mensagens; **P1/P3/COMANDANTE_CIA** gerenciam o efetivo da unidade; **ADMIN/PROGRAMADOR** acessam governança, logs e gestão de acessos).")
            with col_q2: 
                if st.button("🔄 Recarregar Tabela", use_container_width=True):
                    st.session_state["gestao_usr_version"] += 1
                    st.rerun()

            if efetivo_banco:
                linhas_display = []
                for m in efetivo_banco:
                    num_pm = str(m.get("num_policia", "N/I")).strip().upper()
                    usr_cad = dict_usuarios_existentes.get(num_pm, {})
                    nome_comp = m.get("nome_completo") or usr_cad.get("nome_completo") or m.get("nome_guerra", "MILITAR")
                    
                    linhas_display.append({
                        "MATRÍCULA": num_pm,
                        "POSTO/GRAD": m.get("posto_grad", "SD PM"),
                        "MILITAR": nome_comp,
                        "UNIDADE / CIA": m.get("unidade", "21º BPM"),
                        "FUNÇÃO CREDS": usr_cad.get("perfil_creds", "TROPA"),
                        "FUNÇÃO ESCALA": usr_cad.get("perfil_escala", "TROPA"),
                        "NÍVEL GERAL": usr_cad.get("nivel_acesso", "TROPA"),
                        "CONTA ATIVA": bool(usr_cad.get("ativo", True if usr_cad else False))
                    })

                df_display = pd.DataFrame(linhas_display)

                config_cols = {
                    "MATRÍCULA": st.column_config.TextColumn("MATRÍCULA", disabled=True),
                    "POSTO/GRAD": st.column_config.TextColumn("POSTO/GRAD", disabled=True),
                    "MILITAR": st.column_config.TextColumn("NOME COMPLETO", disabled=True),
                    "UNIDADE / CIA": st.column_config.TextColumn("UNIDADE / CIA", disabled=True),
                    "FUNÇÃO CREDS": st.column_config.SelectboxColumn("FUNÇÃO CREDS", options=PERFIS_CREDS, required=True),
                    "FUNÇÃO ESCALA": st.column_config.SelectboxColumn("FUNÇÃO ESCALA", options=PERFIS_ESCALA, required=True),
                    "NÍVEL GERAL": st.column_config.SelectboxColumn("NÍVEL GERAL", options=PERFIS_NIVEL_GERAL, required=True),
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
                    p_creds_novo = str(row["FUNÇÃO CREDS"])
                    p_escala_novo = str(row["FUNÇÃO ESCALA"])
                    p_geral_novo = str(row["NÍVEL GERAL"])
                    s_novo = bool(row["CONTA ATIVA"])
                    
                    m_orig = next((m for m in efetivo_banco if str(m.get("num_policia")).strip().upper() == matr), {})
                    u_orig = dict_usuarios_existentes.get(matr, {})
                    
                    p_creds_ant = str(u_orig.get("perfil_creds", "TROPA"))
                    p_escala_ant = str(u_orig.get("perfil_escala", "TROPA"))
                    p_geral_ant = str(u_orig.get("nivel_acesso", "TROPA"))
                    s_antigo = bool(u_orig.get("ativo", True if u_orig else False))
                    
                    if (p_creds_novo != p_creds_ant or 
                        p_escala_novo != p_escala_ant or 
                        p_geral_novo != p_geral_ant or 
                        s_novo != s_antigo or 
                        not u_orig):
                        
                        nome_comp_m = m_orig.get("nome_completo") or row["MILITAR"]
                        if salvar_permissao_militar(
                            matricula=matr, 
                            perfil_creds=p_creds_novo,
                            perfil_escala=p_escala_novo,
                            nivel_acesso=p_geral_novo, 
                            ativo=s_novo,
                            posto=m_orig.get("posto_grad", "SD PM"),
                            nome=m_orig.get("nome_guerra", "MILITAR"),
                            nome_completo=nome_comp_m
                        ):
                            registrar_audit_log(usr_id_operador, matr, "ALTERAR_ACESSO_TABELA", f"CREDS: [{p_creds_novo}] | ESCALA: [{p_escala_novo}] | GERAL: [{p_geral_novo}]")
                            houve_mudanca = True

                if houve_mudanca:
                    st.session_state["gestao_usr_version"] += 1
                    st.success("✅ Permissões salvas com sucesso!")
                    st.rerun()

        st.divider()

        # AÇÕES DE COMANDO EMERGENCIAIS (EXIBIÇÃO COM NOME COMPLETO)
        st.markdown("##### 🛠️ Ações de Comando sobre Credenciais")
        col_act1, col_act2, col_act3 = st.columns(3)
        opcoes_acoes = [str(u.get("usuario_login") or u.get("usuario")).strip().upper() for u in usuarios_banco if u.get("usuario_login") or u.get("usuario")] if usuarios_banco else ["Nenhum"]

        def formatar_usuario_acao(login_key):
            if login_key == "Nenhum":
                return "Nenhum"
            m_found = next((m for m in efetivo_banco if str(m.get("num_policia")).strip().upper() == login_key), None)
            if m_found:
                pg = m_found.get("posto_grad", "")
                nc = m_found.get("nome_completo") or m_found.get("nome_guerra", "")
                return f"[{login_key}] {pg} {nc}".strip()

            u_found = next((u for u in usuarios_banco if (str(u.get('usuario_login')).upper() == login_key or str(u.get('usuario')).upper() == login_key)), None)
            if u_found:
                pg = u_found.get("cargo_funcao", "")
                nc = u_found.get("nome_completo") or u_found.get("nome_guerra", "")
                return f"[{login_key}] {pg} {nc}".strip()

            return login_key

        with col_act1:
            st.markdown("**🛑 Derrubar Sessão Ativa:**")
            milit_derrubar_pm = st.selectbox(
                "Selecione o usuário:",
                opcoes_acoes,
                format_func=formatar_usuario_acao,
                key="sel_derrubar_s"
            )
            if st.button("🚫 Desconectar Dispositivo", use_container_width=True):
                if supabase and milit_derrubar_pm != "Nenhum":
                    try:
                        supabase.table("usuarios").update({"token_sessao_ativa": "REVOGADO", "token_recuperacao": "REVOGADO"}).or_(f"usuario_login.eq.{milit_derrubar_pm},usuario.eq.{milit_derrubar_pm}").execute()
                        st.cache_data.clear()
                    except Exception:
                        pass
                registrar_audit_log(usr_id_operador, milit_derrubar_pm, "DERRUBAR_SESSAO", "Sessão encerrada remotamente pelo Gestor")
                st.success("✅ Sessão do usuário desconectada!")

        with col_act2:
            st.markdown("**🔄 Resetar para Senha Padrão:**")
            milit_reset_pm = st.selectbox(
                "Selecione o usuário:",
                opcoes_acoes,
                format_func=formatar_usuario_acao,
                key="sel_reset_s"
            )
            if st.button("🔑 Resetar Credenciais Iniciais", use_container_width=True):
                if milit_reset_pm != "Nenhum":
                    pm_limpo = str(milit_reset_pm).replace("-", "").replace(".", "").strip().upper()
                    senha_reset = pm_limpo
                    hash_reset = gerar_hash_senha(senha_reset)
                    
                    if supabase:
                        try:
                            supabase.table("usuarios").update({
                                "senha": senha_reset,
                                "senha_hash": hash_reset,
                                "primeiro_acesso": True,
                                "mfa_habilitado": False,
                                "mfa_secret": None,
                                "token_sessao_ativa": None,
                                "token_recuperacao": None,
                                "ativo": True
                            }).or_(f"usuario_login.eq.{milit_reset_pm},usuario.eq.{pm_limpo}").execute()
                            st.cache_data.clear()
                        except Exception as e:
                            print(f"Erro ao resetar conta: {e}")
                            
                    registrar_audit_log(usr_id_operador, milit_reset_pm, "RESET_SENHA", "Credenciais resetadas para a senha padrão (matrícula).")
                    st.success("✅ Conta restaurada e desbloqueada com sucesso!")

        with col_act3:
            st.markdown("**📱 Resetar Apenas o 2FA (Novo Celular):**")
            milit_2fa_pm = st.selectbox(
                "Selecione o usuário:",
                opcoes_acoes,
                format_func=formatar_usuario_acao,
                key="sel_2fa_s"
            )
            if st.button("📲 Gerar Novo QR Code 2FA", use_container_width=True):
                if supabase and milit_2fa_pm != "Nenhum":
                    try:
                        supabase.table("usuarios").update({
                            "mfa_habilitado": False,
                            "mfa_secret": None
                        }).or_(f"usuario_login.eq.{milit_2fa_pm},usuario.eq.{milit_2fa_pm}").execute()
                        st.cache_data.clear()
                    except Exception:
                        pass
                registrar_audit_log(usr_id_operador, milit_2fa_pm, "RESET_2FA", "Vínculo de autenticador 2FA removido.")
                st.success("✅ Vínculo de 2FA removido com sucesso!")

    # ABA 2: FORMULÁRIO DE CADASTRO DE UNIDADES
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
                        st.cache_data.clear()
                        registrar_audit_log(usr_id_operador, None, "CADASTRAR_UNIDADE", f"Nova unidade cadastrada: {nova_unidade_nome} / {nova_subunidade_nome}")
                        st.success(f"✅ Unidade '{nova_unidade_nome}' cadastrada no Supabase!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar unidade: {e}")

    # ABA 3: LISTAGEM E EXCLUSÃO DE UNIDADES
    with aba_lista_unidades:
        exibir_painel_gestao_unidades()