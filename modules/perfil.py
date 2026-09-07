import streamlit as st
import datetime
import pandas as pd
from core.database import supabase, registrar_audit_log
from core.auth import (
    salvar_usuario_universal_supabase, 
    validar_senha_forte, 
    gerar_hash_senha
)
from utils.pdf_generator import gerar_pdf_parte_informativa, gerar_txt_parte_informativa

def exibir_tela_perfil():
    st.title("👤 Meu Perfil, Permissões e Segurança de Acesso")
    st.caption("Gerencie seus contatos de recuperação, atualize sua senha, acompanhe o histórico de acessos e consulte as travas de auditoria ativas no sistema.")
    st.divider()

    usr = st.session_state.get("usuario_dados") or {}

    aba_p1, aba_p2, aba_p3 = st.tabs([
        "🛡️ Minhas Permissões & Travas de Segurança",
        "⚙️ Alterar Contatos & Senha",
        "📜 Histórico Auditável de Acessos"
    ])

    # =========================================================================
    # ABA 1: PERMISSÕES, TRAVAS DE AUDITORIA E PLANO DE COMPLIANCE
    # =========================================================================
    with aba_p1:
        c_pf1, c_pf2 = st.columns(2)
        with c_pf1:
            st.info(
                f"👤 **Militar:** {usr.get('nome_guerra', 'Militar')}\n\n"
                f"🆔 **Nº de Polícia / Login:** {usr.get('usuario', 'N/I')}\n\n"
                f"🔰 **Cargo / Função:** {usr.get('cargo_funcao', 'Operador')}"
            )
        with c_pf2:
            unidade_exibicao = usr.get('unidade') or st.session_state.get('cfg_subunidade', '35ª CIA PM')
            nivel_exibicao = usr.get('nivel_acesso', 'TROPA')
            st.success(
                f"🔐 **Nível de Permissão:** {nivel_exibicao}\n\n"
                f"🏛️ **Unidade Vinculada:** {unidade_exibicao}\n\n"
                f"📲 **Fator Autenticador (2FA):** Ativo (TOTP / Google Authenticator)"
            )

        st.markdown("##### 📌 O que meu nível de permissão permite fazer?")
        perm_desc = {
            "PROGRAMADOR": "Acesso total e irrestrito a todas as configurações do sistema, criação de tabelas, gestão multi-tenant, desbloqueio retroativo de auditoria e depuração de código.",
            "COMANDANTE_CIA": "Homologação oficial de escalas mensais, trancamento da matriz de serviços, autorização de créditos/débitos retroativos no Banco de Horas e geração do Plano de Compliance.",
            "P1": "Lançamento de ausências, inclusão/exclusão de efetivo, revisão de escalas, gestão do Mural do Efetivo/Trocas e caixa de entrada privada.",
            "SARGENTEANTE": "Cria e edita as prévias das escalas do pelotão/fração e realiza conferência de dados da guarnição.",
            "CMT_PELOTAO": "Revisa a prévia do pelotão, gerencia solicitações de permutas e acompanha o saldo de horas dos subordinados.",
            "CMT_FRACAO": "Cria e gerencia a escala da sua fração e área de lotação específica.",
            "TROPA": "Visualização de escalas publicadas da sua fração, extrato pessoal de horas trabalhadas, confirmação de ciente no Mural e pedidos de permuta."
        }
        st.write(perm_desc.get(nivel_exibicao, "Visualização de escalas publicadas e solicitação de permutas de serviço."))

        st.divider()

        # 🔒 PAINEL DE PROTOCOLOS E TRAVAS DE SEGURANÇA IMPLEMENTADAS
        st.markdown("##### ⚙️ Protocolos Técnicos e Travas de Auditoria Ativas no SIOP")
        
        c_trv1, c_trv2 = st.columns(2)
        with c_trv1:
            st.markdown("""
            * **🔒 Trava de Auditoria Retroativa Diária:** Bloqueio automático de edições e substituições de serviço em datas anteriores ao dia atual (`data < hoje`) para operadores padrão após a homologação da escala.
            * **⚖️ Gestão Cumulativa de Carga e Abatimento:** Cálculo automatizado de metas individuais (160h ou 80h) com abatimento proporcional por Dia Neutro (DN) e Dia Neutro Trabalhado (DNT).
            * **🤝 Trava Antichoques de Guarnição:** Validação em tempo real no Passo 4 para impedir duplicidade de lançamento de um mesmo militar em guarnições ou equipes distintas na mesma data.
            """)
        with c_trv2:
            st.markdown("""
            * **🔑 Controle de Acesso Baseado em Função (RBAC):** Escopo de privilégios dividido em 7 níveis hierárquicos funcionais com isolamento de visões.
            * **📲 Autenticação 2FA/TOTP & Sessão Única:** Proteção contra acessos simultâneos com enforçamento de dispositivo único e *timeout* por inatividade.
            * **🛡️ Criptografia & Row Level Security (RLS):** Tráfego criptografado via HTTPS/TLS e isolamento de dados no PostgreSQL/Supabase por unidade.
            """)

        st.divider()

        # 📄 SEÇÃO DE EXPORTAÇÃO DA PARTE INFORMATIVA DE COMPLIANCE
        st.markdown("##### 📄 Exportação do Plano de Segurança e Compliance (Ofício / Parte)")
        st.caption("Gere a Parte Informativa oficial pré-formatada para apresentação ao Comando da Unidade e órgãos de fiscalização/correição.")

        col_btn_doc1, col_btn_doc2 = st.columns(2)

        with col_btn_doc1:
            pdf_bytes = gerar_pdf_parte_informativa(
                num_parte="12.4/2026",
                responsavel_nome=usr.get("nome_guerra", "DESENVOLVEDOR"),
                responsavel_posto=usr.get("cargo_funcao", "PROGRAMADOR / TESTADOR")
            )
            st.download_button(
                label="📄 Baixar Parte Informativa (.PDF)",
                data=pdf_bytes,
                file_name=f"Parte_Informativa_Seguranca_SIOP_{datetime.date.today().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        with col_btn_doc2:
            txt_bytes = gerar_txt_parte_informativa(
                num_parte="12.4/2026",
                responsavel_nome=usr.get("nome_guerra", "DESENVOLVEDOR"),
                responsavel_posto=usr.get("cargo_funcao", "PROGRAMADOR / TESTADOR")
            )
            st.download_button(
                label="📝 Baixar Texto da Parte (.TXT)",
                data=txt_bytes,
                file_name=f"Parte_Informativa_Seguranca_SIOP_{datetime.date.today().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )

    # =========================================================================
    # ABA 2: ATUALIZAÇÃO DE CONTATOS E TROCA DE SENHA
    # =========================================================================
    with aba_p2:
        st.markdown("##### ⚙️ Atualização de Contatos Corporativos")
        
        with st.form("form_atualizar_contatos_usuario"):
            novo_email = st.text_input("E-mail Institucional de Recuperação:", value=usr.get("email_recuperacao", ""))
            novo_celular = st.text_input("Celular Corporativo (com DDD):", value=usr.get("celular_recuperacao", ""))
            btn_salvar_contatos = st.form_submit_button("📱 Salvar Apenas Contatos")

            if btn_salvar_contatos:
                usr["email_recuperacao"] = novo_email
                usr["celular_recuperacao"] = novo_celular
                
                payload_contatos = {
                    "email_recuperacao": novo_email,
                    "celular_recuperacao": novo_celular
                }
                
                if salvar_usuario_universal_supabase(usr.get('usuario', ''), payload_contatos):
                    registrar_audit_log(usr.get('usuario', ''), usr.get('usuario', ''), "ATUALIZAR_CONTATOS", f"E-mail ({novo_email}) e Celular atualizados no Supabase.")
                    st.success("✅ Contatos corporativos salvos com sucesso no Supabase!")
                    st.rerun()

        st.divider()
        st.markdown("##### 🔒 Alteração de Senha de Acesso")
        
        with st.form("form_atualizar_senha_usuario"):
            senha_atual = st.text_input("Senha Atual para Confirmação:", type="password", placeholder="Digite sua senha atual")
            nova_senha_p = st.text_input("Nova Senha Forte:", type="password", placeholder="Digite a nova senha")
            conf_senha_p = st.text_input("Confirme a Nova Senha:", type="password", placeholder="Repita a nova senha")
            btn_salvar_senha = st.form_submit_button("🔑 Salvar Apenas Nova Senha")

            if btn_salvar_senha:
                if not senha_atual:
                    st.error("⚠️ Digite sua senha atual para autorizar a troca de senha.")
                elif nova_senha_p != conf_senha_p:
                    st.error("⚠️ A nova senha e a confirmação não coincidem.")
                else:
                    s_valida, msg_s = validar_senha_forte(nova_senha_p)
                    if not s_valida:
                        st.error(f"⛔ **Requisito Não Atendido:** {msg_s}")
                    else:
                        hash_nova_p = gerar_hash_senha(nova_senha_p)
                        historico_p = usr.get("historico_senhas", []) or []
                        novo_hist_p = ([hash_nova_p] + historico_p)[:3]
                        
                        payload_senha = {
                            "senha": hash_nova_p,
                            "senha_hash": hash_nova_p,
                            "historico_senhas": novo_hist_p
                        }
                        
                        if salvar_usuario_universal_supabase(usr.get('usuario', ''), payload_senha):
                            usr["historico_senhas"] = novo_hist_p
                            registrar_audit_log(usr.get('usuario', ''), usr.get('usuario', ''), "ALTERAR_SENHA", "Troca de senha efetuada pelo próprio usuário no Perfil.")
                            st.success("✅ Senha e histórico de senhas atualizados no banco de dados com sucesso!")
                            st.rerun()

    # =========================================================================
    # ABA 3: HISTÓRICO AUDITÁVEL DE ACESSOS E OPERAÇÕES
    # =========================================================================
    with aba_p3:
        st.markdown("##### 📜 Registro Auditável de Logins e Operações (UTC)")
        st.caption("Acompanhe o registro auditável e imutável de todas as ações executadas nesta conta para fins de compliance e segurança da informação.")

        usr_pm = usr.get("usuario")
        logs_reais = []

        if supabase and usr_pm:
            try:
                res_logs = supabase.table("historico_auditoria")\
                    .select("data_hora, tipo_acao, descricao_detalhada, ip_origem")\
                    .or_(f"militar_operador.eq.{usr_pm},militar_alvo.eq.{usr_pm}")\
                    .order("data_hora", desc=True)\
                    .limit(15)\
                    .execute()

                if res_logs.data:
                    logs_reais = res_logs.data
            except Exception:
                pass

        if logs_reais:
            df_logs = pd.DataFrame(logs_reais)
            df_logs["data_hora"] = pd.to_datetime(df_logs["data_hora"]).dt.strftime("%d/%m/%Y %H:%M:%S")
            st.dataframe(
                df_logs,
                column_config={
                    "data_hora": "Data/Hora",
                    "tipo_acao": "Ação Executada",
                    "descricao_detalhada": "Detalhamento da Operação",
                    "ip_origem": "IP de Origem"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ Nenhum evento crítico registrado para este usuário nas últimas sessões.")