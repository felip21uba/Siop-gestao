import streamlit as st
import pandas as pd
import datetime
from core.database import supabase, registrar_audit_log, atualizar_usuario_supabase
from core.auth import gerar_hash_senha, validar_requisitos_senha

def exibir_tela_perfil():
    st.title("👤 Perfil do Usuário & Registros de Aceite")
    st.caption("Consulte seus dados funcionais, níveis de acesso, termos de aceite assinados e gerencie suas credenciais.")
    st.divider()

    usr = st.session_state.get("usuario_dados") or {}
    num_login = str(usr.get("usuario_login") or usr.get("usuario") or usr.get("num_policia") or "1337468").strip().upper()
    nome_guerra = str(usr.get("nome_guerra") or "OPERADOR").strip().upper()
    nome_completo = str(usr.get("nome_completo") or f"{usr.get('cargo_funcao', '')} {nome_guerra}").strip().upper()
    cargo_funcao = str(usr.get("cargo_funcao") or usr.get("posto_grad") or "CAP").strip().upper()
    nivel_acesso = str(usr.get("nivel_acesso") or "ADMIN").strip().upper()
    unidade_vinculada = st.session_state.get("unidade_ativa_nome") or usr.get("unidade") or "21º BPM / 35ª CIA PM"
    mfa_ativo = bool(usr.get("mfa_habilitado", True))

    # --- CARTÃO DE DADOS PESSOAIS E FUNCIONAIS ---
    with st.container(border=True):
        col_avatar, col_dados = st.columns([1, 3.5])
        
        with col_avatar:
            st.markdown("<div style='text-align: center; font-size: 70px; margin-top: 10px;'>👤</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: center; font-weight: bold;'>{cargo_funcao} {nome_guerra}</div>", unsafe_allow_html=True)
            st.caption(f"<div style='text-align: center;'>Nº PM: {num_login}</div>", unsafe_allow_html=True)

        with col_dados:
            st.markdown(f"### **{nome_completo}**")
            
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                st.markdown(f"🆔 **Nº de Polícia / Login:** `{num_login}`")
                st.markdown(f"🔰 **Cargo / Função:** `{cargo_funcao}`")
                st.markdown(f"🏛️ **Unidade Vinculada:** `{unidade_vinculada}`")
            with c_d2:
                st.markdown(f"🔐 **Nível de Permissão:** `{nivel_acesso}`")
                status_2fa = "🟢 Ativo (TOTP / Authenticator)" if mfa_ativo else "🔴 Inativo"
                st.markdown(f"📲 **Fator Autenticador (2FA):** {status_2fa}")
                
            st.info(f"📌 **O que meu nível de permissão permite fazer?**\n\nVisualização de escalas publicadas, gestão do módulo operacional conforme perfil `{nivel_acesso}` e solicitação de permutas de serviço.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- TABS INTERNAS DE CONFIGURAÇÕES E REGISTROS DE ACEITE ---
    tab_termos, tab_senha = st.tabs([
        "📄 Meus Termos de Aceite & Sigilo de Informações",
        "⚙️ Alterar Contatos & Senha"
    ])

    # =========================================================================
    # ABA 1: ACEITES DE TCO, FIEL DEPÓSITO E SIGILO DE INFORMAÇÕES
    # =========================================================================
    with tab_termos:
        st.subheader("📜 Registros Formais de Aceite e Compromisso de Sigilo")
        st.caption("Histórico de concordância com os termos de fiel depósito (TCO) e declarações de sigilo das informações do SIOP.")

        aceites_usuario = []
        if supabase and num_login:
            try:
                res_ac = supabase.table("aceites_compliance")\
                    .select("*")\
                    .or_(f"num_policia.eq.{num_login},num_policia.ilike.%{num_login}%")\
                    .order("data_aceite", desc=True)\
                    .execute()
                aceites_usuario = res_ac.data or []
            except Exception as e:
                print(f"Aviso ao consultar aceites do perfil: {e}")

        if aceites_usuario:
            df_ac = pd.DataFrame(aceites_usuario)
            if "data_aceite" in df_ac.columns and not df_ac.empty:
                df_ac["Data / Hora Aceite"] = df_ac["data_aceite"].apply(
                    lambda x: pd.to_datetime(x).strftime("%d/%m/%Y %H:%M:%S") if pd.notna(x) else "N/I"
                )

            df_ac.rename(columns={
                "termo_versao": "Versão do Termo",
                "unidade": "Unidade / Lotação",
                "cargo_funcao": "Cargo/Função",
                "ip_origem": "Endereço IP"
            }, inplace=True)

            cols_exib = ["Data / Hora Aceite", "Versão do Termo", "Unidade / Lotação", "Cargo/Função", "Endereço IP"]
            cols_presentes = [c for c in cols_exib if c in df_ac.columns]

            st.dataframe(df_ac[cols_presentes], use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ Nenhum registro de aceite do Termo de Fiel Depósito / Compliance localizado para sua matrícula.")

        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- BLOCOS DE COMPROMISSO E DECLARAÇÕES INSTITUCIONAIS ---
        with st.expander("🛡️ Termo de Fiel Depósito e Cadeia de Custódia (TCO)", expanded=False):
            st.markdown("""
            > * Declaro estar ciente da custódia física dos materiais apreendidos sob minha responsabilidade.
            > * Comprometo-me a zelar pela integridade dos invólucros, lacres e da rastreabilidade probatória, cumprindo rigorosamente os artigos 158-A a 158-F do Código de Processamento Penal (Lei nº 13.964/2019 - Pacote Anticrime) e as Instruções Normativas Institucionais de Cadeia de Custódia.
            """)

        with st.expander("🔒 Termo de Compromisso de Sigilo e Proteção de Dados (LGPD / PMMG)", expanded=False):
            st.markdown("""
            > * Declaro ciência de que todas as informações acessadas no SIOP possuem caráter estritamente sigiloso e de uso restrito às atividades operacionais da Polícia Militar de Minas Gerais.
            > * Comprometo-me a cumprir os ditames da Lei Geral de Proteção de Dados Pessoais (Lei Federal nº 13.709/2018 - LGPD), não divulgando, copiando ou transferindo credenciais de acesso ou dados pessoais de terceiros sem autorização formal do Comando/P1/P3.
            """)

    # =========================================================================
    # ABA 2: FORMULÁRIO DE ALTERAÇÃO DE CONTATOS E SENHA
    # =========================================================================
    with tab_senha:
        st.subheader("⚙️ Alteração de Credenciais de Acesso")
        st.caption("Atualize seu e-mail de recuperação, telefone de contato e sua senha pessoal de acesso.")

        with st.form("form_alterar_dados_perfil", clear_on_submit=False):
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                novo_email = st.text_input("E-mail de Recuperação:", value=usr.get("email_recuperacao") or "", placeholder="militar@pmmg.mg.gov.br").strip()
                novo_celular = st.text_input("Celular / WhatsApp:", value=usr.get("celular_recuperacao") or "", placeholder="(32) 90000-0000").strip()
            
            with c_p2:
                senha_atual = st.text_input("Senha Atual:", type="password").strip()
                nova_senha = st.text_input("Nova Senha:", type="password", placeholder="No mínimo 6 caracteres, maiúscula, minúscula e símbolo").strip()
                confirma_senha = st.text_input("Confirme a Nova Senha:", type="password").strip()

            st.markdown("<br>", unsafe_allow_html=True)
            btn_salvar_perfil = st.form_submit_button("💾 Salvar Alterações do Perfil", type="primary", use_container_width=True)

            if btn_salvar_perfil:
                if nova_senha or confirma_senha:
                    if nova_senha != confirma_senha:
                        st.error("❌ A nova senha e a confirmação não coincidem.")
                    else:
                        senha_ok, msg_s = validar_requisitos_senha(nova_senha)
                        if not senha_ok:
                            st.error(f"⛔ {msg_s}")
                        else:
                            hash_nova = gerar_hash_senha(nova_senha)
                            payload_update = {
                                "email_recuperacao": novo_email,
                                "celular_recuperacao": novo_celular,
                                "senha": nova_senha,
                                "senha_hash": hash_nova
                            }
                            
                            if atualizar_usuario_supabase(num_login, payload_update):
                                registrar_audit_log(num_login, num_login, "ALTERAR_SENHA_PERFIL", "Senha e contatos alterados pelo próprio usuário no Perfil.")
                                st.success("✅ Senha e contatos alterados com sucesso!")
                                st.rerun()
                            else:
                                st.error("Erro ao salvar alterações no banco de dados.")
                else:
                    payload_update = {
                        "email_recuperacao": novo_email,
                        "celular_recuperacao": novo_celular
                    }
                    if atualizar_usuario_supabase(num_login, payload_update):
                        st.success("✅ Contatos atualizados com sucesso!")
                        st.rerun()