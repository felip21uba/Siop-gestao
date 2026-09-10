import datetime
from zoneinfo import ZoneInfo
import hashlib
import os
import random
import urllib.parse
import uuid
import pyotp
import streamlit as st

# ==============================================================================
# 🌐 CONFIGURAÇÃO DE FUSO HORÁRIO OFICIAL (BRASÍLIA / UTC-3)
# ==============================================================================
FUSO_BR = ZoneInfo("America/Sao_Paulo")

def obter_agora():
    """Retorna a data/hora atual rigorosamente ajustada para o fuso de Brasília."""
    return datetime.datetime.now(FUSO_BR)

from core.database import init_db
init_db()

from core.styles import aplicar_estilo_visual
from core.database import (
    supabase, 
    carregar_militares_supabase, 
    registrar_audit_log,
    atualizar_usuario_supabase,
    salvar_mensagem_p1_supabase
)
from core.auth import (
    validar_codigo_authy,
    validar_requisitos_senha,
    verificar_senha,
    buscar_usuario_para_login,
    enviar_email_codigo,
    gerar_hash_senha
)
# IMPORTA A NOVA BLINDAGEM DE SEGURANÇA:
from core.security import sanitizar_texto

# IMPORTE DOS MÓDULOS OPERACIONAIS
from modules.escalas import exibir_modulo_escalas
from modules.mural import renderizar_mural
from modules.gestao_usuarios import exibir_tela_gestao_usuarios
from modules.perfil import exibir_tela_perfil
from modules.tco.main_tco import renderizar_modulo_tco

# 1. Configuração Inicial da Página
st.set_page_config(
    page_title="SIOP - Sistema Integrado de Operações",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inicialização do Estado de Sessão
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_autenticado" not in st.session_state:
    st.session_state["usuario_autenticado"] = False
if "usuario_dados" not in st.session_state:
    st.session_state["usuario_dados"] = {}
if "token_sessao_local" not in st.session_state:
    st.session_state["token_sessao_local"] = None
if "mfa_pendente" not in st.session_state:
    st.session_state["mfa_pendente"] = False
if "mfa_setup_mode" not in st.session_state:
    st.session_state["mfa_setup_mode"] = False
if "recuperar_senha_modo" not in st.session_state:
    st.session_state["recuperar_senha_modo"] = False
if "simular_visao_tropa" not in st.session_state:
    st.session_state["simular_visao_tropa"] = False
if "tentativas_login" not in st.session_state:
    st.session_state["tentativas_login"] = {}
if "bloqueados_temp" not in st.session_state:
    st.session_state["bloqueados_temp"] = set()
if "reset_token_dados" not in st.session_state:
    st.session_state["reset_token_dados"] = {}
if "usuarios_teste_db" not in st.session_state:
    st.session_state["usuarios_teste_db"] = {}

# CONSTANTES VISUAIS INSTITUCIONAIS
URL_BRASAO_PADRAO = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Bras%C3%A3o_PMMG.svg/500px-Bras%C3%A3o_PMMG.svg.png"
CAMINHO_BRASAO_LOCAL = "assets/brasao.png"

def obter_imagem_brasao():
    if os.path.exists(CAMINHO_BRASAO_LOCAL):
        return CAMINHO_BRASAO_LOCAL
    return URL_BRASAO_PADRAO

# ==============================================================================
# ⏱️ TRAVA DE INATIVIDADE E SESSÃO ÚNICA CONCORRENTE
# ==============================================================================
AGORA = obter_agora()

if st.session_state.get("autenticado", False):
    usr_dados = st.session_state.get("usuario_dados", {})
    usr_login = str(usr_dados.get("usuario_login") or usr_dados.get("usuario") or "").strip().upper()
    token_local = st.session_state.get("token_sessao_local")

    # 1. Trava de Sessão Única Concorrente
    if supabase and usr_login and token_local:
        try:
            # Força busca limpa direto na coluna principal
            res = supabase.table("usuarios").select("token_sessao_ativa").eq("usuario_login", usr_login).execute()
            
            # Fallback caso use a coluna 'usuario'
            if not res.data or len(res.data) == 0:
                res = supabase.table("usuarios").select("token_sessao_ativa").eq("usuario", usr_login).execute()

            if res.data and len(res.data) > 0:
                token_banco = res.data[0].get("token_sessao_ativa")
                
                # Exibe modo Debug se Gestor
                eh_prog = str(usr_dados.get("nivel_acesso", "TROPA")).upper() == "PROGRAMADOR"
                if eh_prog:
                    st.sidebar.info(f"🕵️ **DEBUG SESSÃO:**\n- Local: `{str(token_local)[:8]}`\n- Banco: `{str(token_banco)[:8]}`")
                
                if token_banco and str(token_banco).strip() != str(token_local).strip() and str(token_banco) != "REVOGADO":
                    st.session_state["autenticado"] = False
                    st.session_state["usuario_autenticado"] = False
                    st.session_state["mfa_pendente"] = False
                    st.session_state["mfa_setup_mode"] = False
                    st.session_state["usuario_dados"] = {}
                    st.session_state["token_sessao_local"] = None
                    st.error("🚨 **Sessão Encerrada:** Sua conta foi acessada em outro dispositivo. Por segurança, este acesso foi desconectado.")
                    st.stop()
        except Exception as e:
            st.sidebar.error(f"⚠️ Erro Sync Sessão: {e}")

    # 2. Trava de Inatividade (3 Minutos = 180s)
    ultima_atividade = st.session_state.get("ultima_atividade")
    if ultima_atividade:
        if ultima_atividade.tzinfo is None:
            ultima_atividade = ultima_atividade.replace(tzinfo=FUSO_BR)
            
        tempo_inativo = (AGORA - ultima_atividade).total_seconds()
        if tempo_inativo > 180:
            st.session_state["autenticado"] = False
            st.session_state["usuario_autenticado"] = False
            st.session_state["mfa_pendente"] = False
            st.session_state["mfa_setup_mode"] = False
            st.session_state["usuario_dados"] = {}
            st.session_state["token_sessao_local"] = None
            st.warning("⚠️ **Sessão Expirada:** Você foi desconectado por inatividade (mais de 3 minutos sem uso).")
            st.stop()

    st.session_state["ultima_atividade"] = AGORA

# ==============================================================================
# 🔒 TELA DE LOGIN INSTITUCIONAL 
# ==============================================================================
if not st.session_state.get("autenticado", False):
    aplicar_estilo_visual()

    col_e, col_centro, col_d = st.columns([1, 2, 1])

    with col_centro:
        st.markdown("<br>", unsafe_allow_html=True)
        
        c_logo, c_tit = st.columns([1, 3])
        with c_logo:
            st.image(obter_imagem_brasao(), width=100)
        with c_tit:
            st.markdown("## 🛡️ **SIOP PMMG**")
            st.markdown("##### Sistema Integrado de Operações")
            st.caption("Polícia Militar de Minas Gerais — Polícia de Cidadania")

        st.divider()

        # ----------------------------------------------------------------------
        # FLUXO 1: RESET DE SENHA AUTOATENDÍVEL VIA E-MAIL
        # ----------------------------------------------------------------------
        if st.session_state.get("recuperar_senha_modo", False):
            st.subheader("🔑 Autoreset de Senha via E-mail")
            st.info("Informe seu Nº de Polícia ou e-mail cadastrado para redefinir sua senha.")

            if "codigo_enviado" not in st.session_state["reset_token_dados"]:
                with st.form("form_solicitar_codigo_email"):
                    identificador = (st.text_input("Nº de Polícia ou E-mail Cadastrado:", placeholder="Ex: 1337468 ou militar@pmmg.mg.gov.br") or "").strip()
                    
                    c_rec1, c_rec2 = st.columns(2)
                    with c_rec1:
                        btn_gerar_codigo = st.form_submit_button("📩 Solicitar Código de Reset", type="primary", use_container_width=True)
                    with c_rec2:
                        btn_voltar_rec = st.form_submit_button("⬅️ Voltar ao Login", use_container_width=True)

                    if btn_voltar_rec:
                        st.session_state["recuperar_senha_modo"] = False
                        st.session_state["reset_token_dados"] = {}
                        st.rerun()

                    if btn_gerar_codigo:
                        if not identificador:
                            st.error("⚠️ Digite o Nº de Polícia ou E-mail.")
                        else:
                            usr_obj = buscar_usuario_para_login(identificador)
                            email_alvo = usr_obj.get("email_recuperacao") if usr_obj else (identificador if "@" in identificador else None)

                            if not email_alvo:
                                st.error("❌ Nenhum e-mail de recuperação cadastrado para este usuário.")
                            else:
                                codigo_gerado = str(random.randint(100000, 999999))
                                sucesso_envio, msg_envio = enviar_email_codigo(email_alvo, codigo_gerado)
                                
                                if sucesso_envio:
                                    st.session_state["reset_token_dados"] = {
                                        "codigo_enviado": codigo_gerado,
                                        "usuario_id": identificador
                                    }
                                    st.toast(f"Código enviado para {email_alvo}!", icon="📩")
                                    st.rerun()
                                else:
                                    st.error(f"🚨 {msg_envio}")

            else:
                cod_correto = st.session_state["reset_token_dados"]["codigo_enviado"]
                usr_id = st.session_state["reset_token_dados"]["usuario_id"]

                st.success("📧 **Instruções enviadas!** Insira o código de verificação de 6 dígitos recebido e cadastre sua nova senha:")

                with st.form("form_confirmar_reset_email"):
                    cod_digitado = (st.text_input("🔑 Digite o Código de 6 dígitos recebido:", max_chars=6) or "").strip()
                    nova_senha = (st.text_input("Nova Senha:", type="password", placeholder="Ex: Pmmg@2026") or "").strip()
                    confirma_senha = (st.text_input("Confirme a Nova Senha:", type="password") or "").strip()

                    col_res1, col_res2 = st.columns(2)
                    with col_res1:
                        btn_finalizar_reset = st.form_submit_button("✅ Alterar Senha & Desbloquear", type="primary", use_container_width=True)
                    with col_res2:
                        btn_cancelar_reset = st.form_submit_button("❌ Cancelar", use_container_width=True)

                    if btn_cancelar_reset:
                        st.session_state["recuperar_senha_modo"] = False
                        st.session_state["reset_token_dados"] = {}
                        st.rerun()

                    if btn_finalizar_reset:
                        if cod_digitado != cod_correto:
                            st.error("🚨 Código de verificação incorreto!")
                        elif nova_senha != confirma_senha:
                            st.error("❌ As senhas não coincidem.")
                        else:
                            senha_ok, msg_s = validar_requisitos_senha(nova_senha)
                            if not senha_ok:
                                st.error(f"⛔ {msg_s}")
                            else:
                                if usr_id in st.session_state["tentativas_login"]:
                                    st.session_state["tentativas_login"][usr_id] = 0
                                st.session_state["bloqueados_temp"].discard(usr_id)

                                hash_nova = gerar_hash_senha(nova_senha)

                                if supabase:
                                    atualizar_usuario_supabase(usr_id, {
                                        "senha": nova_senha,
                                        "senha_hash": hash_nova,
                                        "ativo": True
                                    })

                                if "usuarios_teste_db" in st.session_state:
                                    if usr_id in st.session_state["usuarios_teste_db"]:
                                        st.session_state["usuarios_teste_db"][usr_id]["senha"] = nova_senha
                                        st.session_state["usuarios_teste_db"][usr_id]["senha_hash"] = hash_nova
                                        st.session_state["usuarios_teste_db"][usr_id]["ativo"] = True

                                st.success("🎉 Senha redefinida e conta desbloqueada! Realize o login com a nova senha.")
                                st.session_state["recuperar_senha_modo"] = False
                                st.session_state["reset_token_dados"] = {}
                                st.rerun()

        # ----------------------------------------------------------------------
        # FLUXO 2: PRIMEIRO ACESSO - CADASTRO DO QR CODE + TROCA DE SENHA
        # ----------------------------------------------------------------------
        elif st.session_state.get("mfa_setup_mode", False):
            usr_temp = st.session_state.get("temp_user_data", {})
            st.warning("🛡️ **Primeiro Acesso: Configuração Inicial de Segurança**")
            st.markdown("Cadastre uma **nova senha pessoal** e escaneie o QR Code no seu aplicativo **Google Authenticator ou Authy**.")

            if "temp_mfa_secret" not in st.session_state:
                st.session_state["temp_mfa_secret"] = pyotp.random_base32()
            
            secret = st.session_state["temp_mfa_secret"]
            uri = pyotp.totp.TOTP(secret).provisioning_uri(
                name=str(usr_temp.get('usuario_login', usr_temp.get('usuario', 'Militar'))), 
                issuer_name="SIOP PMMG"
            )
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(uri)}"

            c_qr1, c_qr2 = st.columns([1, 1.5])
            with c_qr1:
                st.image(qr_url, caption="Escaneie com o app Authy/Google Authenticator")
            with c_qr2:
                st.info(f"📍 **Chave Manual TOTP:**\n\n`{secret}`")

            st.markdown("---")
            with st.form("form_mfa_setup"):
                st.markdown("##### 🔐 1. Cadastre sua Nova Senha Pessoal:")
                nova_senha = (st.text_input("Nova Senha:", type="password", placeholder="Ex: Pmmg@2026") or "").strip()
                confirma_senha = (st.text_input("Confirme a Nova Senha:", type="password", placeholder="Repita a nova senha") or "").strip()
                st.caption("⚙️ **Regras:** Mínimo 6 caracteres (1 maiúscula, 1 minúscula e 1 símbolo).")

                st.markdown("##### 📱 2. Dados de Contato & Validação 2FA:")
                email_val_padrao = usr_temp.get("email_recuperacao") or ""
                celular_val_padrao = usr_temp.get("celular_recuperacao") or ""
                
                email_input = (st.text_input("E-mail Funcional/Pessoal:", value=email_val_padrao, placeholder="militar@gmail.com") or "").strip()
                celular_input = (st.text_input("Celular / WhatsApp:", value=celular_val_padrao, placeholder="(32) 90000-0000") or "").strip()
                codigo_setup = (st.text_input("🔑 Token de 6 dígitos gerado no App:", max_chars=6, placeholder="000000") or "").strip()

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    btn_confirmar_setup = st.form_submit_button("💾 Salvar e Ativar 2FA", type="primary", use_container_width=True)
                with col_s2:
                    btn_cancelar_setup = st.form_submit_button("❌ Cancelar", use_container_width=True)

                if btn_cancelar_setup:
                    st.session_state["mfa_setup_mode"] = False
                    st.session_state["temp_user_data"] = {}
                    if "temp_mfa_secret" in st.session_state:
                        del st.session_state["temp_mfa_secret"]
                    st.rerun()

                if btn_confirmar_setup:
                    if nova_senha != confirma_senha:
                        st.error("❌ As senhas não coincidem.")
                    else:
                        senha_ok, msg_senha = validar_requisitos_senha(nova_senha)
                        if not senha_ok:
                            st.error(f"⛔ {msg_senha}")
                        elif not email_input or not celular_input:
                            st.error("⚠️ Preencha o e-mail e o celular para contato.")
                        elif not validar_codigo_authy(secret, codigo_setup):
                            st.error("🚨 Código do aplicativo incorreto ou expirado.")
                        else:
                            num_pol_str = str(usr_temp.get("usuario_login", usr_temp.get("usuario", ""))).strip().upper()
                            hash_nova = gerar_hash_senha(nova_senha)
                            novo_token = str(uuid.uuid4())
                            
                            if supabase and num_pol_str:
                                try:
                                    supabase.table("usuarios").update({
                                        "senha": nova_senha, 
                                        "senha_hash": hash_nova,
                                        "mfa_secret": secret, 
                                        "mfa_habilitado": True,
                                        "email_recuperacao": email_input, 
                                        "celular_recuperacao": celular_input,
                                        "token_sessao_ativa": novo_token
                                    }).eq("usuario_login", num_pol_str).execute()
                                except Exception:
                                    atualizar_usuario_supabase(num_pol_str, {"token_sessao_ativa": novo_token})
                            
                            usr_temp["senha"] = nova_senha
                            usr_temp["senha_hash"] = hash_nova
                            usr_temp["mfa_secret"] = secret
                            usr_temp["mfa_habilitado"] = True
                            usr_temp["email_recuperacao"] = email_input
                            usr_temp["celular_recuperacao"] = celular_input
                            usr_temp["token_sessao_ativa"] = novo_token

                            st.session_state["token_sessao_local"] = novo_token
                            st.session_state["usuarios_teste_db"][num_pol_str] = usr_temp
                            st.session_state["usuario_dados"] = usr_temp
                            st.session_state["autenticado"] = True
                            st.session_state["usuario_autenticado"] = True
                            st.session_state["mfa_setup_mode"] = False
                            st.session_state["ultima_atividade"] = obter_agora()
                            
                            if "temp_mfa_secret" in st.session_state:
                                del st.session_state["temp_mfa_secret"]

                            registrar_audit_log(num_pol_str, "", "PRIMEIRO_ACESSO", "Senha e 2FA configurados.")
                            st.toast("✅ Nova senha e 2FA salvos com sucesso!", icon="🎉")
                            st.rerun()

        # ----------------------------------------------------------------------
        # FLUXO 3: DIGITAÇÃO DO CÓDIGO AUTHY PARA ACESSOS SEGUINTES
        # ----------------------------------------------------------------------
        elif st.session_state.get("mfa_pendente", False):
            usr_temp = st.session_state.get("temp_user_data", {})
            
            st.warning("📲 **Autenticação em Duas Etapas (Authy/MFA)**")
            st.markdown(f"Militar: **{usr_temp.get('cargo_funcao', '')} {usr_temp.get('nome_guerra', 'Operador')}**")

            with st.form("form_validar_authy_mfa"):
                codigo_authy = (st.text_input("🔑 Token de Segurança (6 dígitos):", max_chars=6, placeholder="000000") or "").strip()
                
                c_aut1, c_aut2 = st.columns(2)
                with c_aut1:
                    btn_validar_mfa = st.form_submit_button("✅ Validar Código", type="primary", use_container_width=True)
                with c_aut2:
                    btn_enviar_email = st.form_submit_button("📧 Enviar por E-mail", use_container_width=True)

                btn_cancelar_mfa = st.form_submit_button("❌ Voltar ao Login", use_container_width=True)

                if btn_enviar_email:
                    email_user = usr_temp.get("email_recuperacao")
                    if not email_user:
                        st.error("⚠️ Nenhum e-mail de recuperação cadastrado.")
                    else:
                        cod_mfa_email = str(random.randint(100000, 999999))
                        usr_temp["mfa_secret_temp_email"] = cod_mfa_email
                        sucesso_mfa_e, msg_mfa_e = enviar_email_codigo(email_user, cod_mfa_email)
                        if sucesso_mfa_e:
                            st.success(f"📩 Código enviado para: {email_user}")
                        else:
                            st.error(f"🚨 {msg_mfa_e}")

                if btn_cancelar_mfa:
                    st.session_state["mfa_pendente"] = False
                    st.session_state["temp_user_data"] = {}
                    st.rerun()

                if btn_validar_mfa:
                    secret = usr_temp.get("mfa_secret", "")
                    codigo_temp_email = usr_temp.get("mfa_secret_temp_email")
                    
                    valido_authy = validar_codigo_authy(secret, codigo_authy)
                    valido_email = (codigo_temp_email and str(codigo_authy).strip() == str(codigo_temp_email).strip())

                    if valido_authy or valido_email:
                        novo_token = str(uuid.uuid4())
                        num_pol_str = str(usr_temp.get("usuario_login") or usr_temp.get("usuario") or "").strip().upper()

                        if supabase and num_pol_str:
                            try:
                                supabase.table("usuarios").update({"token_sessao_ativa": novo_token}).eq("usuario_login", num_pol_str).execute()
                            except Exception:
                                atualizar_usuario_supabase(num_pol_str, {"token_sessao_ativa": novo_token})

                        usr_temp["token_sessao_ativa"] = novo_token
                        st.session_state["token_sessao_local"] = novo_token
                        st.session_state["usuario_dados"] = usr_temp
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_autenticado"] = True
                        st.session_state["mfa_pendente"] = False
                        st.session_state["ultima_atividade"] = obter_agora()
                        
                        registrar_audit_log(num_pol_str, "", "LOGIN_SUCESSO", "Login com 2FA concluído.")
                        st.toast(f"Acesso liberado! Bem-vindo, {usr_temp.get('nome_guerra')}!", icon="🟢")
                        st.rerun()
                    else:
                        st.error("🚨 Token Authy/E-mail incorreto ou expirado. Verifique seu app ou caixa de entrada.")

        # ----------------------------------------------------------------------
        # FLUXO 4: TELA PRINCIPAL DE LOGIN (CONSULTA DIRETA NO SUPABASE)
        # ----------------------------------------------------------------------
        else:
            with st.form("form_login_principal"):
                usuario_input = (st.text_input("Nº de Polícia / Matrícula / E-mail:", placeholder="Ex: 1337468") or "").strip()
                senha_input = (st.text_input("Senha de Acesso:", type="password", placeholder="••••••••") or "").strip()
                
                btn_entrar = st.form_submit_button("🔑 Entrar no Sistema", type="primary", use_container_width=True)

                if btn_entrar:
                    if not usuario_input or not senha_input:
                        st.error("⚠️ Preencha as credenciais de acesso.")
                    elif usuario_input in st.session_state["bloqueados_temp"]:
                        st.error("🔒 **Conta Bloqueada por Excesso de Tentativas Incorretas (3/3).** Use a redefinição de senha via e-mail abaixo.")
                    else:
                        num_pol_key = str(usuario_input).strip()
                        usuario_encontrado = buscar_usuario_para_login(usuario_input)

                        # Cache Local apenas se o banco falhar
                        if not usuario_encontrado:
                            db_teste = st.session_state.get("usuarios_teste_db", {})
                            if num_pol_key in db_teste:
                                usuario_encontrado = db_teste[num_pol_key]

                        if not usuario_encontrado:
                            st.error("❌ Usuário não localizado no sistema.")
                        elif not usuario_encontrado.get("ativo", True):
                            st.error("🔒 Sua conta está bloqueada no banco de dados. Utilize o reset por e-mail abaixo.")
                        else:
                            senha_db_texto = usuario_encontrado.get("senha")
                            senha_db_hash = usuario_encontrado.get("senha_hash")

                            if not verificar_senha(senha_input, senha_db_texto, senha_db_hash):
                                erros_atuais = st.session_state["tentativas_login"].get(usuario_input, 0) + 1
                                st.session_state["tentativas_login"][usuario_input] = erros_atuais

                                if erros_atuais >= 3:
                                    st.session_state["bloqueados_temp"].add(usuario_input)
                                    if supabase:
                                        atualizar_usuario_supabase(num_pol_key, {"ativo": False})
                                    st.error("🚨 **Senha Incorreta! Tentativa 3 de 3.** Sua conta foi BLOQUEADA por segurança! Clique em 'Esqueci a Senha' abaixo para redefinir via e-mail.")
                                else:
                                    restantes = 3 - erros_atuais
                                    st.error(f"🚨 **Senha Incorreta!** Tentativa **{erros_atuais} de 3**. Você tem mais **{restantes}** tentativa(s) antes do bloqueio.")
                            else:
                                st.session_state["tentativas_login"][usuario_input] = 0
                                st.session_state["temp_user_data"] = usuario_encontrado

                                if usuario_encontrado.get("mfa_habilitado", False) and usuario_encontrado.get("mfa_secret"):
                                    st.session_state["mfa_pendente"] = True
                                else:
                                    st.session_state["mfa_setup_mode"] = True
                                st.rerun()

            col_b1, col_b2 = st.columns([1, 1])
            with col_b1:
                st.link_button("🐛 Reportar Defeito", "mailto:felip21uba@gmail.com?subject=Reporte%20de%20Defeito%20-%20SIOP", use_container_width=True)
            with col_b2:
                if st.button("❓ Esqueci a Senha / Desbloquear Conta", use_container_width=True):
                    st.session_state["recuperar_senha_modo"] = True
                    st.rerun()

        st.markdown("""
            <div style="text-align: center; margin-top: 35px; border-top: 1px solid #334155; padding-top: 15px;">
                <span style="font-size: 11px; color: #64748b;">
                    <b>AVISO TÉCNICO:</b> Este software consiste em uma infraestrutura de gestão e automação de desenvolvimento independente.<br>
                    Possui caráter privado e não detém vínculo oficial, endosso ou integração direta com a arquitetura de TI oficial da PMMG.
                </span>
            </div>
        """, unsafe_allow_html=True)

    st.stop()

# =========================================================================
# 📌 SISTEMA PRINCIPAL (LIBERADO APÓS SUCESSO NO LOGIN)
# =========================================================================
aplicar_estilo_visual()

usr = st.session_state.get("usuario_dados", {})
usr_real_perfil = str(usr.get("nivel_acesso", "TROPA")).upper()

with st.sidebar:
    c_side_logo, c_side_txt = st.columns([1, 2])
    with c_side_logo:
        st.image(obter_imagem_brasao(), width=50)
    with c_side_txt:
        st.markdown("### **SIOP**")
        st.caption("PMMG - 2026")

    # -------------------------------------------------------------------------
    # 👁️ SIMULADOR DE VISÃO DE TROPA (BOTÃO PARA GESTORES)
    # -------------------------------------------------------------------------
    eh_gestor_real = usr_real_perfil in ["PROGRAMADOR", "ADMIN", "COMANDANTE_CIA", "P1", "P3", "SARGENTEANTE", "CMT_PELOTAO", "GESTOR"]
    
    if eh_gestor_real:
        st.markdown("---")
        st.markdown("👁️ **Modo de Visualização:**")
        
        simular_tropa = st.toggle("👁️ Visão da Tropa (Simulador)", value=st.session_state.get("simular_visao_tropa", False), key="toggle_visao_tropa")
        st.session_state["simular_visao_tropa"] = simular_tropa
        
        if simular_tropa:
            perfil_ativo = "TROPA"
            st.info("💡 **Simulador Ativo:** Exibindo tela restrita da TROPA.")
        else:
            perfil_ativo = usr_real_perfil

        # -------------------------------------------------------------------------
        # 🏛️ SELETOR MULTI-TENANT DE UNIDADES (PARA PROGRAMADOR / GESTOR)
        # -------------------------------------------------------------------------
        st.markdown("---")
        st.markdown("🏛️ **Seletor de Unidade (Multi-Tenant):**")
        
        lista_unis = []
        if supabase:
            try:
                res_u = supabase.table("configuracao_unidade").select("id, unidade_nome, subunidade_nome").execute()
                lista_unis = res_u.data or []
            except Exception:
                lista_unis = []

        if lista_unis:
            opcoes_uni = [f"{u.get('unidade_nome', '')} / {u.get('subunidade_nome', '')}".strip(" /") for u in lista_unis]
            
            idx_sel = 0
            uni_atual_sessao = st.session_state.get("unidade_ativa_nome")
            if uni_atual_sessao and uni_atual_sessao in opcoes_uni:
                idx_sel = opcoes_uni.index(uni_atual_sessao)

            sel_uni_sidebar = st.selectbox(
                "Unidade em Operação:",
                opcoes_uni,
                index=idx_sel,
                key="sb_multi_tenant_unidade"
            )
            st.session_state["unidade_ativa_nome"] = sel_uni_sidebar
            
            parts = sel_uni_sidebar.split(" / ")
            st.session_state["cfg_unidade"] = parts[0] if len(parts) > 0 else "21º BPM"
            st.session_state["cfg_subunidade"] = parts[1] if len(parts) > 1 else ""
        else:
            st.session_state["unidade_ativa_nome"] = usr.get("unidade", "21º BPM / 35ª CIA PM")
        st.markdown("---")
    else:
        perfil_ativo = "TROPA"
        st.session_state["unidade_ativa_nome"] = usr.get("unidade", "21º BPM / 35ª CIA PM")

    eh_gestor_ou_admin = (perfil_ativo != "TROPA")

    unidade_card_exibida = st.session_state.get("unidade_ativa_nome", usr.get("unidade", "PMMG"))
    st.info(f"👤 **{usr.get('nome_guerra', 'Militar')}**\n\n🔰 **Perfil Ativo:** `{perfil_ativo}`\n\n🏛️ **Unidade Ativa:** {unidade_card_exibida}")
    st.divider()

    if "modulo_ativo" not in st.session_state:
        st.session_state["modulo_ativo"] = "ESCALAS" if eh_gestor_ou_admin else "MINHA_ESCALA"

    st.markdown("**📌 Módulos Operacionais:**")
    
    if eh_gestor_ou_admin:
        if st.button("📅 Módulo de Escalas (Gestão)", use_container_width=True):
            st.session_state["modulo_ativo"] = "ESCALAS"
            st.rerun()

        if st.session_state.get("modulo_ativo") == "ESCALAS":
            st.markdown("**📍 Filtro de Passos da Escala:**")
            passo_sel = st.radio(
                "Exibir na Tela:",
                [
                    "VISUALIZAR TODOS",
                    "PASSO 1: Unidade & Equipes",
                    "PASSO 2: Turno & Horários",
                    "PASSO 3: Efetivo & Ausências",
                    "PASSO 4: Matriz Mensal",
                    "PASSO 5: Quadro Geral",
                    "PASSO 6: Exportação & Auditoria",
                    "PASSO 7: Banco de Horas",
                    "🗣️ Mural & Trocas de Serviço"
                ],
                key="rad_passos_escala"
            )
            st.session_state["passo_escala_ativo"] = passo_sel
        st.divider()

    if not eh_gestor_ou_admin:
        if st.button("📅 Minha Escala & Mural", use_container_width=True):
            st.session_state["modulo_ativo"] = "MINHA_ESCALA"
            st.rerun()
        st.divider()

    if eh_gestor_ou_admin:
        if st.button("📋 Módulo de TCO", use_container_width=True):
            st.session_state["modulo_ativo"] = "TCO"
            st.rerun()

        if st.button("📑 Módulo de Procedimentos", use_container_width=True):
            st.session_state["modulo_ativo"] = "PROCEDIMENTOS"
            st.rerun()
            
        if perfil_ativo in ["PROGRAMADOR", "ADMIN", "COMANDANTE_CIA", "P1"]:
            if st.button("⚙️ Gestão de Acessos", use_container_width=True):
                st.session_state["modulo_ativo"] = "GESTOES_USUARIOS"
                st.rerun()
        st.divider()

    if st.button("👤 Meu Perfil & Segurança", key="btn_menu_meu_perfil", use_container_width=True):
        st.session_state["modulo_ativo"] = "MEU_PERFIL"
        st.rerun()

    st.markdown("**🎨 Visualização da Interface:**")
    tema_atual = st.session_state.get("tema_visual", "DARK")
    label_tema = "☀️ Modo Claro" if tema_atual == "DARK" else "🌙 Modo Escuro"
    if st.button(label_tema, use_container_width=True):
        st.session_state["tema_visual"] = "LIGHT" if tema_atual == "DARK" else "DARK"
        st.rerun()
    st.divider()

    if st.button("🚪 Sair do Sistema", use_container_width=True):
        usr_m = str(usr.get("usuario_login") or usr.get("usuario") or "").strip().upper()
        if supabase and usr_m:
            try:
                supabase.table("usuarios").update({"token_sessao_ativa": "REVOGADO"}).eq("usuario_login", usr_m).execute()
            except Exception:
                pass

        registrar_audit_log(usr_m, "", "LOGOUT", "Sessão encerrada ativamente pelo usuário.")
        st.session_state["autenticado"] = False
        st.session_state["usuario_autenticado"] = False
        st.session_state["mfa_pendente"] = False
        st.session_state["mfa_setup_mode"] = False
        st.session_state["recuperar_senha_modo"] = False
        st.session_state["simular_visao_tropa"] = False
        st.session_state["usuario_dados"] = {}
        st.session_state["token_sessao_local"] = None
        st.rerun()

# =========================================================================
# 🚀 ROUTER CENTRAL DE TELAS
# =========================================================================
modulo = st.session_state.get("modulo_ativo", "MINHA_ESCALA")

# -------------------------------------------------------------------------
# 👮‍♂️ VISÃO RESTRITA DA TROPA
# -------------------------------------------------------------------------
if not eh_gestor_ou_admin or perfil_ativo == "TROPA":
    st.title("📅 Central do Policial")
    aba_escala, aba_mural, aba_mensagens = st.tabs([
        "📅 Minha Escala Individual", 
        "🗣️ Mural & Trocas de Serviço", 
        "📩 Mensagens & Requerimentos P1"
    ])
    
    num_policia_user = str(usr.get("usuario_login") or usr.get("usuario") or usr.get("num_policia") or "").strip()
    nome_user = usr.get("nome_guerra", "Militar")

    with aba_escala:
        st.info(f"👮‍♂️ Exibindo a linha individual na escala para **{usr.get('cargo_funcao', '')} {nome_user} ({num_policia_user})**.")
        
        df_escala = st.session_state.get("df_escala_consolidada")
        if df_escala is not None and not df_escala.empty:
            df_individual = df_escala[
                df_escala["Nº POLÍCIA"].astype(str).str.contains(num_policia_user, na=False) |
                df_escala["MILITAR"].astype(str).str.contains(nome_user, na=False)
            ]
            if not df_individual.empty:
                st.dataframe(df_individual, use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum turno cadastrado para você na escala publicada deste mês.")
        else:
            st.warning("A escala geral deste mês ainda não foi publicada pela P1/P3.")
            
    with aba_mural:
        renderizar_mural()

    with aba_mensagens:
        st.subheader("📩 Enviar Mensagem ou Solicitação à P1")
        st.caption("Utilize este canal oficial para encaminhar solicitações de permuta, certidões ou requerimentos ao comando.")
        
        with st.form("form_envio_msg_p1_tropa", clear_on_submit=True):
            assunto_msg = (st.text_input("Assunto / Motivo:") or "").strip()
            texto_msg = (st.text_area("Detalhamento da Solicitação:", height=120) or "").strip()
            
            btn_enviar_msg = st.form_submit_button("📤 Enviar Mensagem à P1", type="primary", use_container_width=True)
            if btn_enviar_msg:
                if not assunto_msg or not texto_msg:
                    st.error("⚠️ Preencha o assunto e o texto da mensagem.")
                else:
                    # 🛡️ APLICAÇÃO DA SANITIZAÇÃO DE ENTRADA AQUI:
                    assunto_limpo = sanitizar_texto(assunto_msg)
                    texto_limpo = sanitizar_texto(texto_msg)

                    sucesso = salvar_mensagem_p1_supabase(num_policia_user, nome_user, assunto_limpo, texto_limpo)
                    if sucesso:
                        st.success("✅ Sua mensagem foi gravada no Supabase e enviada com segurança para a P1!")
                    else:
                        st.error("Erro ao enviar mensagem. Tente novamente.")

elif modulo == "ESCALAS" and eh_gestor_ou_admin:
    if st.session_state.get("passo_escala_ativo") == "🗣️ Mural & Trocas de Serviço":
        renderizar_mural()
    else:
        exibir_modulo_escalas()

elif modulo == "TCO" and eh_gestor_ou_admin:
    renderizar_modulo_tco()

elif modulo == "PROCEDIMENTOS" and eh_gestor_ou_admin:
    st.title("📑 Módulo de Procedimentos Administrativos")
    st.info("ℹ️ Módulo em desenvolvimento operacional.")

elif modulo == "GESTOES_USUARIOS" and perfil_ativo in ["PROGRAMADOR", "ADMIN", "COMANDANTE_CIA", "P1"]:
    exibir_tela_gestao_usuarios()

elif modulo == "MEU_PERFIL":
    exibir_tela_perfil()

else:
    st.error("🚨 Acesso Não Autorizado: Seu perfil não possui permissão para acessar este módulo.")

def renderizar_rodape_corporativo():
    st.markdown("<br><hr>", unsafe_allow_html=True)
    col_f1, col_f2, col_f3 = st.columns([1.5, 2, 1.5])
    
    with col_f1:
        unidade_txt = st.session_state.get("cfg_unidade") or st.session_state.get("usuario_dados", {}).get("unidade") or "21º BPM"
        subunidade_txt = st.session_state.get("cfg_subunidade") or "35ª CIA PM"
        st.caption(f"🏛️ **{unidade_txt}** | {subunidade_txt}")
        st.caption("PMMG - Polícia Militar de Minas Gerais")
        
    with col_f2:
        st.caption("🛡️ **SIOP - Sistema Integrado de Operações** v2.4")
        st.caption("Segurança da Informação, Compliance e Protocolos LGPD/PMMG")
        
    with col_f3:
        usr_sessao = st.session_state.get("usuario_dados", {}).get("nome_guerra", "Operador")
        st.caption(f"🟢 **Sessão Ativa:** {usr_sessao}")
        st.caption(f"⏱️ **Acesso:** {obter_agora().strftime('%H:%M:%S')}")

renderizar_rodape_corporativo()import os
import sys
import datetime
from zoneinfo import ZoneInfo
import hashlib
import random
import urllib.parse
import uuid
import html
import re
import pyotp
import streamlit as st

# ==============================================================================
# 🌐 CONFIGURAÇÃO DE FUSO HORÁRIO OFICIAL (BRASÍLIA / UTC-3)
# ==============================================================================
FUSO_BR = ZoneInfo("America/Sao_Paulo")

def obter_agora():
    """Retorna a data/hora atual rigorosamente ajustada para o fuso de Brasília."""
    return datetime.datetime.now(FUSO_BR)

def sanitizar_texto(texto: str) -> str:
    """Limpa e escapa caracteres perigosos em textos recebidos da interface (Prevenção de XSS e SQLi)."""
    if not texto:
        return ""
    texto_limpo = html.escape(str(texto).strip())
    texto_limpo = re.sub(r'(?i)<script.*?>.*?</script>', '', texto_limpo)
    texto_limpo = re.sub(r'(?i)javascript:', '', texto_limpo)
    texto_limpo = re.sub(r'(?i)onerror\s*=', '', texto_limpo)
    return texto_limpo

from core.database import init_db
init_db()

from core.styles import aplicar_estilo_visual
from core.database import (
    supabase, 
    carregar_militares_supabase, 
    registrar_audit_log,
    atualizar_usuario_supabase,
    salvar_mensagem_p1_supabase
)
from core.auth import (
    validar_codigo_authy,
    validar_requisitos_senha,
    verificar_senha,
    buscar_usuario_para_login,
    enviar_email_codigo,
    gerar_hash_senha
)

# IMPORTE DOS MÓDULOS OPERACIONAIS
from modules.escalas import exibir_modulo_escalas
from modules.mural import renderizar_mural
from modules.gestao_usuarios import exibir_tela_gestao_usuarios
from modules.perfil import exibir_tela_perfil
from modules.tco.main_tco import renderizar_modulo_tco

# 1. Configuração Inicial da Página
st.set_page_config(
    page_title="SIOP - Sistema Integrado de Operações",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inicialização do Estado de Sessão
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_autenticado" not in st.session_state:
    st.session_state["usuario_autenticado"] = False
if "usuario_dados" not in st.session_state:
    st.session_state["usuario_dados"] = {}
if "token_sessao_local" not in st.session_state:
    st.session_state["token_sessao_local"] = None
if "mfa_pendente" not in st.session_state:
    st.session_state["mfa_pendente"] = False
if "mfa_setup_mode" not in st.session_state:
    st.session_state["mfa_setup_mode"] = False
if "recuperar_senha_modo" not in st.session_state:
    st.session_state["recuperar_senha_modo"] = False
if "simular_visao_tropa" not in st.session_state:
    st.session_state["simular_visao_tropa"] = False
if "tentativas_login" not in st.session_state:
    st.session_state["tentativas_login"] = {}
if "bloqueados_temp" not in st.session_state:
    st.session_state["bloqueados_temp"] = set()
if "reset_token_dados" not in st.session_state:
    st.session_state["reset_token_dados"] = {}
if "usuarios_teste_db" not in st.session_state:
    st.session_state["usuarios_teste_db"] = {}

# CONSTANTES VISUAIS INSTITUCIONAIS
URL_BRASAO_PADRAO = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Bras%C3%A3o_PMMG.svg/500px-Bras%C3%A3o_PMMG.svg.png"
CAMINHO_BRASAO_LOCAL = "assets/brasao.png"

def obter_imagem_brasao():
    if os.path.exists(CAMINHO_BRASAO_LOCAL):
        return CAMINHO_BRASAO_LOCAL
    return URL_BRASAO_PADRAO

# ==============================================================================
# ⏱️ TRAVA DE INATIVIDADE E SESSÃO ÚNICA CONCORRENTE
# ==============================================================================
AGORA = obter_agora()

if st.session_state.get("autenticado", False):
    usr_dados = st.session_state.get("usuario_dados", {})
    usr_login = str(usr_dados.get("usuario_login") or usr_dados.get("usuario") or "").strip().upper()
    token_local = st.session_state.get("token_sessao_local")

    # 1. Trava de Sessão Única Concorrente
    if supabase and usr_login and token_local:
        try:
            res = supabase.table("usuarios").select("token_sessao_ativa").eq("usuario_login", usr_login).execute()
            
            if not res.data or len(res.data) == 0:
                res = supabase.table("usuarios").select("token_sessao_ativa").eq("usuario", usr_login).execute()

            if res.data and len(res.data) > 0:
                token_banco = res.data[0].get("token_sessao_ativa")
                
                if token_banco and str(token_banco).strip() != str(token_local).strip() and str(token_banco) != "REVOGADO":
                    st.session_state["autenticado"] = False
                    st.session_state["usuario_autenticado"] = False
                    st.session_state["mfa_pendente"] = False
                    st.session_state["mfa_setup_mode"] = False
                    st.session_state["usuario_dados"] = {}
                    st.session_state["token_sessao_local"] = None
                    st.error("🚨 **Sessão Encerrada:** Sua conta foi acessada em outro dispositivo. Por segurança, este acesso foi desconectado.")
                    st.stop()
        except Exception:
            pass

    # 2. Trava de Inatividade (3 Minutos = 180s)
    ultima_atividade = st.session_state.get("ultima_atividade")
    if ultima_atividade:
        if ultima_atividade.tzinfo is None:
            ultima_atividade = ultima_atividade.replace(tzinfo=FUSO_BR)
            
        tempo_inativo = (AGORA - ultima_atividade).total_seconds()
        if tempo_inativo > 180:
            st.session_state["autenticado"] = False
            st.session_state["usuario_autenticado"] = False
            st.session_state["mfa_pendente"] = False
            st.session_state["mfa_setup_mode"] = False
            st.session_state["usuario_dados"] = {}
            st.session_state["token_sessao_local"] = None
            st.warning("⚠️ **Sessão Expirada:** Você foi desconectado por inatividade (mais de 3 minutos sem uso).")
            st.stop()

    st.session_state["ultima_atividade"] = AGORA

# ==============================================================================
# 🔒 TELA DE LOGIN INSTITUCIONAL 
# ==============================================================================
if not st.session_state.get("autenticado", False):
    aplicar_estilo_visual()

    col_e, col_centro, col_d = st.columns([1, 2, 1])

    with col_centro:
        st.markdown("<br>", unsafe_allow_html=True)
        
        c_logo, c_tit = st.columns([1, 3])
        with c_logo:
            st.image(obter_imagem_brasao(), width=100)
        with c_tit:
            st.markdown("## 🛡️ **SIOP PMMG**")
            st.markdown("##### Sistema Integrado de Operações")
            st.caption("Polícia Militar de Minas Gerais — Polícia de Cidadania")

        st.divider()

        # ----------------------------------------------------------------------
        # FLUXO 1: RESET DE SENHA AUTOATENDÍVEL VIA E-MAIL
        # ----------------------------------------------------------------------
        if st.session_state.get("recuperar_senha_modo", False):
            st.subheader("🔑 Autoreset de Senha via E-mail")
            st.info("Informe seu Nº de Polícia ou e-mail cadastrado para redefinir sua senha.")

            if "codigo_enviado" not in st.session_state["reset_token_dados"]:
                with st.form("form_solicitar_codigo_email"):
                    identificador = (st.text_input("Nº de Polícia ou E-mail Cadastrado:", placeholder="Ex: 1337468 ou militar@pmmg.mg.gov.br") or "").strip()
                    
                    c_rec1, c_rec2 = st.columns(2)
                    with c_rec1:
                        btn_gerar_codigo = st.form_submit_button("📩 Solicitar Código de Reset", type="primary", use_container_width=True)
                    with c_rec2:
                        btn_voltar_rec = st.form_submit_button("⬅️ Voltar ao Login", use_container_width=True)

                    if btn_voltar_rec:
                        st.session_state["recuperar_senha_modo"] = False
                        st.session_state["reset_token_dados"] = {}
                        st.rerun()

                    if btn_gerar_codigo:
                        if not identificador:
                            st.error("⚠️ Digite o Nº de Polícia ou E-mail.")
                        else:
                            usr_obj = buscar_usuario_para_login(identificador)
                            email_alvo = usr_obj.get("email_recuperacao") if usr_obj else (identificador if "@" in identificador else None)

                            if not email_alvo:
                                st.error("❌ Nenhum e-mail de recuperação cadastrado para este usuário.")
                            else:
                                codigo_gerado = str(random.randint(100000, 999999))
                                sucesso_envio, msg_envio = enviar_email_codigo(email_alvo, codigo_gerado)
                                
                                if sucesso_envio:
                                    st.session_state["reset_token_dados"] = {
                                        "codigo_enviado": codigo_gerado,
                                        "usuario_id": identificador
                                    }
                                    st.toast(f"Código enviado para {email_alvo}!", icon="📩")
                                    st.rerun()
                                else:
                                    st.error(f"🚨 {msg_envio}")

            else:
                cod_correto = st.session_state["reset_token_dados"]["codigo_enviado"]
                usr_id = st.session_state["reset_token_dados"]["usuario_id"]

                st.success("📧 **Instruções enviadas!** Insira o código de verificação de 6 dígitos recebido e cadastre sua nova senha:")

                with st.form("form_confirmar_reset_email"):
                    cod_digitado = (st.text_input("🔑 Digite o Código de 6 dígitos recebido:", max_chars=6) or "").strip()
                    nova_senha = (st.text_input("Nova Senha:", type="password", placeholder="Ex: Pmmg@2026") or "").strip()
                    confirma_senha = (st.text_input("Confirme a Nova Senha:", type="password") or "").strip()

                    col_res1, col_res2 = st.columns(2)
                    with col_res1:
                        btn_finalizar_reset = st.form_submit_button("✅ Alterar Senha & Desbloquear", type="primary", use_container_width=True)
                    with col_res2:
                        btn_cancelar_reset = st.form_submit_button("❌ Cancelar", use_container_width=True)

                    if btn_cancelar_reset:
                        st.session_state["recuperar_senha_modo"] = False
                        st.session_state["reset_token_dados"] = {}
                        st.rerun()

                    if btn_finalizar_reset:
                        if cod_digitado != cod_correto:
                            st.error("🚨 Código de verificação incorreto!")
                        elif nova_senha != confirma_senha:
                            st.error("❌ As senhas não coincidem.")
                        else:
                            senha_ok, msg_s = validar_requisitos_senha(nova_senha)
                            if not senha_ok:
                                st.error(f"⛔ {msg_s}")
                            else:
                                if usr_id in st.session_state["tentativas_login"]:
                                    st.session_state["tentativas_login"][usr_id] = 0
                                st.session_state["bloqueados_temp"].discard(usr_id)

                                hash_nova = gerar_hash_senha(nova_senha)

                                if supabase:
                                    atualizar_usuario_supabase(usr_id, {
                                        "senha": nova_senha,
                                        "senha_hash": hash_nova,
                                        "ativo": True
                                    })

                                if "usuarios_teste_db" in st.session_state:
                                    if usr_id in st.session_state["usuarios_teste_db"]:
                                        st.session_state["usuarios_teste_db"][usr_id]["senha"] = nova_senha
                                        st.session_state["usuarios_teste_db"][usr_id]["senha_hash"] = hash_nova
                                        st.session_state["usuarios_teste_db"][usr_id]["ativo"] = True

                                st.success("🎉 Senha redefinida e conta desbloqueada! Realize o login com a nova senha.")
                                st.session_state["recuperar_senha_modo"] = False
                                st.session_state["reset_token_dados"] = {}
                                st.rerun()

        # ----------------------------------------------------------------------
        # FLUXO 2: PRIMEIRO ACESSO - CADASTRO DO QR CODE + TROCA DE SENHA
        # ----------------------------------------------------------------------
        elif st.session_state.get("mfa_setup_mode", False):
            usr_temp = st.session_state.get("temp_user_data", {})
            st.warning("🛡️ **Primeiro Acesso: Configuração Inicial de Segurança**")
            st.markdown("Cadastre uma **nova senha pessoal** e escaneie o QR Code no seu aplicativo **Google Authenticator ou Authy**.")

            if "temp_mfa_secret" not in st.session_state:
                st.session_state["temp_mfa_secret"] = pyotp.random_base32()
            
            secret = st.session_state["temp_mfa_secret"]
            uri = pyotp.totp.TOTP(secret).provisioning_uri(
                name=str(usr_temp.get('usuario_login', usr_temp.get('usuario', 'Militar'))), 
                issuer_name="SIOP PMMG"
            )
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(uri)}"

            c_qr1, c_qr2 = st.columns([1, 1.5])
            with c_qr1:
                st.image(qr_url, caption="Escaneie com o app Authy/Google Authenticator")
            with c_qr2:
                st.info(f"📍 **Chave Manual TOTP:**\n\n`{secret}`")

            st.markdown("---")
            with st.form("form_mfa_setup"):
                st.markdown("##### 🔐 1. Cadastre sua Nova Senha Pessoal:")
                nova_senha = (st.text_input("Nova Senha:", type="password", placeholder="Ex: Pmmg@2026") or "").strip()
                confirma_senha = (st.text_input("Confirme a Nova Senha:", type="password", placeholder="Repita a nova senha") or "").strip()
                st.caption("⚙️ **Regras:** Mínimo 6 caracteres (1 maiúscula, 1 minúscula e 1 símbolo).")

                st.markdown("##### 📱 2. Dados de Contato & Validação 2FA:")
                email_val_padrao = usr_temp.get("email_recuperacao") or ""
                celular_val_padrao = usr_temp.get("celular_recuperacao") or ""
                
                email_input = (st.text_input("E-mail Funcional/Pessoal:", value=email_val_padrao, placeholder="militar@gmail.com") or "").strip()
                celular_input = (st.text_input("Celular / WhatsApp:", value=celular_val_padrao, placeholder="(32) 90000-0000") or "").strip()
                codigo_setup = (st.text_input("🔑 Token de 6 dígitos gerado no App:", max_chars=6, placeholder="000000") or "").strip()

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    btn_confirmar_setup = st.form_submit_button("💾 Salvar e Ativar 2FA", type="primary", use_container_width=True)
                with col_s2:
                    btn_cancelar_setup = st.form_submit_button("❌ Cancelar", use_container_width=True)

                if btn_cancelar_setup:
                    st.session_state["mfa_setup_mode"] = False
                    st.session_state["temp_user_data"] = {}
                    if "temp_mfa_secret" in st.session_state:
                        del st.session_state["temp_mfa_secret"]
                    st.rerun()

                if btn_confirmar_setup:
                    if nova_senha != confirma_senha:
                        st.error("❌ As senhas não coincidem.")
                    else:
                        senha_ok, msg_senha = validar_requisitos_senha(nova_senha)
                        if not senha_ok:
                            st.error(f"⛔ {msg_senha}")
                        elif not email_input or not celular_input:
                            st.error("⚠️ Preencha o e-mail e o celular para contato.")
                        elif not validar_codigo_authy(secret, codigo_setup):
                            st.error("🚨 Código do aplicativo incorreto ou expirado.")
                        else:
                            num_pol_str = str(usr_temp.get("usuario_login", usr_temp.get("usuario", ""))).strip().upper()
                            hash_nova = gerar_hash_senha(nova_senha)
                            novo_token = str(uuid.uuid4())
                            
                            if supabase and num_pol_str:
                                try:
                                    supabase.table("usuarios").update({
                                        "senha": nova_senha, 
                                        "senha_hash": hash_nova,
                                        "mfa_secret": secret, 
                                        "mfa_habilitado": True,
                                        "email_recuperacao": email_input, 
                                        "celular_recuperacao": celular_input,
                                        "token_sessao_ativa": novo_token
                                    }).eq("usuario_login", num_pol_str).execute()
                                except Exception:
                                    atualizar_usuario_supabase(num_pol_str, {"token_sessao_ativa": novo_token})
                            
                            usr_temp["senha"] = nova_senha
                            usr_temp["senha_hash"] = hash_nova
                            usr_temp["mfa_secret"] = secret
                            usr_temp["mfa_habilitado"] = True
                            usr_temp["email_recuperacao"] = email_input
                            usr_temp["celular_recuperacao"] = celular_input
                            usr_temp["token_sessao_ativa"] = novo_token

                            st.session_state["token_sessao_local"] = novo_token
                            st.session_state["usuarios_teste_db"][num_pol_str] = usr_temp
                            st.session_state["usuario_dados"] = usr_temp
                            st.session_state["autenticado"] = True
                            st.session_state["usuario_autenticado"] = True
                            st.session_state["mfa_setup_mode"] = False
                            st.session_state["ultima_atividade"] = obter_agora()
                            
                            if "temp_mfa_secret" in st.session_state:
                                del st.session_state["temp_mfa_secret"]

                            registrar_audit_log(num_pol_str, "", "PRIMEIRO_ACESSO", "Senha e 2FA configurados.")
                            st.toast("✅ Nova senha e 2FA salvos com sucesso!", icon="🎉")
                            st.rerun()

        # ----------------------------------------------------------------------
        # FLUXO 3: DIGITAÇÃO DO CÓDIGO AUTHY PARA ACESSOS SEGUINTES
        # ----------------------------------------------------------------------
        elif st.session_state.get("mfa_pendente", False):
            usr_temp = st.session_state.get("temp_user_data", {})
            
            st.warning("📲 **Autenticação em Duas Etapas (Authy/MFA)**")
            st.markdown(f"Militar: **{usr_temp.get('cargo_funcao', '')} {usr_temp.get('nome_guerra', 'Operador')}**")

            with st.form("form_validar_authy_mfa"):
                codigo_authy = (st.text_input("🔑 Token de Segurança (6 dígitos):", max_chars=6, placeholder="000000") or "").strip()
                
                c_aut1, c_aut2 = st.columns(2)
                with c_aut1:
                    btn_validar_mfa = st.form_submit_button("✅ Validar Código", type="primary", use_container_width=True)
                with c_aut2:
                    btn_enviar_email = st.form_submit_button("📧 Enviar por E-mail", use_container_width=True)

                btn_cancelar_mfa = st.form_submit_button("❌ Voltar ao Login", use_container_width=True)

                if btn_enviar_email:
                    email_user = usr_temp.get("email_recuperacao")
                    if not email_user:
                        st.error("⚠️ Nenhum e-mail de recuperação cadastrado.")
                    else:
                        cod_mfa_email = str(random.randint(100000, 999999))
                        usr_temp["mfa_secret_temp_email"] = cod_mfa_email
                        sucesso_mfa_e, msg_mfa_e = enviar_email_codigo(email_user, cod_mfa_email)
                        if sucesso_mfa_e:
                            st.success(f"📩 Código enviado para: {email_user}")
                        else:
                            st.error(f"🚨 {msg_mfa_e}")

                if btn_cancelar_mfa:
                    st.session_state["mfa_pendente"] = False
                    st.session_state["temp_user_data"] = {}
                    st.rerun()

                if btn_validar_mfa:
                    secret = usr_temp.get("mfa_secret", "")
                    codigo_temp_email = usr_temp.get("mfa_secret_temp_email")
                    
                    valido_authy = validar_codigo_authy(secret, codigo_authy)
                    valido_email = (codigo_temp_email and str(codigo_authy).strip() == str(codigo_temp_email).strip())

                    if valido_authy or valido_email:
                        novo_token = str(uuid.uuid4())
                        num_pol_str = str(usr_temp.get("usuario_login") or usr_temp.get("usuario") or "").strip().upper()

                        if supabase and num_pol_str:
                            try:
                                supabase.table("usuarios").update({"token_sessao_ativa": novo_token}).eq("usuario_login", num_pol_str).execute()
                            except Exception:
                                atualizar_usuario_supabase(num_pol_str, {"token_sessao_ativa": novo_token})

                        usr_temp["token_sessao_ativa"] = novo_token
                        st.session_state["token_sessao_local"] = novo_token
                        st.session_state["usuario_dados"] = usr_temp
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_autenticado"] = True
                        st.session_state["mfa_pendente"] = False
                        st.session_state["ultima_atividade"] = obter_agora()
                        
                        registrar_audit_log(num_pol_str, "", "LOGIN_SUCESSO", "Login com 2FA concluído.")
                        st.toast(f"Acesso liberado! Bem-vindo, {usr_temp.get('nome_guerra')}!", icon="🟢")
                        st.rerun()
                    else:
                        st.error("🚨 Token Authy/E-mail incorreto ou expirado. Verifique seu app ou caixa de entrada.")

        # ----------------------------------------------------------------------
        # FLUXO 4: TELA PRINCIPAL DE LOGIN (CONSULTA DIRETA NO SUPABASE)
        # ----------------------------------------------------------------------
        else:
            with st.form("form_login_principal"):
                usuario_input = (st.text_input("Nº de Polícia / Matrícula / E-mail:", placeholder="Ex: 1337468") or "").strip()
                senha_input = (st.text_input("Senha de Acesso:", type="password", placeholder="••••••••") or "").strip()
                
                btn_entrar = st.form_submit_button("🔑 Entrar no Sistema", type="primary", use_container_width=True)

                if btn_entrar:
                    if not usuario_input or not senha_input:
                        st.error("⚠️ Preencha as credenciais de acesso.")
                    elif usuario_input in st.session_state["bloqueados_temp"]:
                        st.error("🔒 **Conta Bloqueada por Excesso de Tentativas Incorretas (3/3).** Use a redefinição de senha via e-mail abaixo.")
                    else:
                        num_pol_key = str(usuario_input).strip()
                        usuario_encontrado = buscar_usuario_para_login(usuario_input)

                        # Cache Local apenas se o banco falhar
                        if not usuario_encontrado:
                            db_teste = st.session_state.get("usuarios_teste_db", {})
                            if num_pol_key in db_teste:
                                usuario_encontrado = db_teste[num_pol_key]

                        if not usuario_encontrado:
                            st.error("❌ Usuário não localizado no sistema.")
                        elif not usuario_encontrado.get("ativo", True):
                            st.error("🔒 Sua conta está bloqueada no banco de dados. Utilize o reset por e-mail abaixo.")
                        else:
                            senha_db_texto = usuario_encontrado.get("senha")
                            senha_db_hash = usuario_encontrado.get("senha_hash")

                            if not verificar_senha(senha_input, senha_db_texto, senha_db_hash):
                                erros_atuais = st.session_state["tentativas_login"].get(usuario_input, 0) + 1
                                st.session_state["tentativas_login"][usuario_input] = erros_atuais

                                if erros_atuais >= 3:
                                    st.session_state["bloqueados_temp"].add(usuario_input)
                                    if supabase:
                                        atualizar_usuario_supabase(num_pol_key, {"ativo": False})
                                    st.error("🚨 **Senha Incorreta! Tentativa 3 de 3.** Sua conta foi BLOQUEADA por segurança! Clique em 'Esqueci a Senha' abaixo para redefinir via e-mail.")
                                else:
                                    restantes = 3 - erros_atuais
                                    st.error(f"🚨 **Senha Incorreta!** Tentativa **{erros_atuais} de 3**. Você tem mais **{restantes}** tentativa(s) antes do bloqueio.")
                            else:
                                st.session_state["tentativas_login"][usuario_input] = 0
                                st.session_state["temp_user_data"] = usuario_encontrado

                                if usuario_encontrado.get("mfa_habilitado", False) and usuario_encontrado.get("mfa_secret"):
                                    st.session_state["mfa_pendente"] = True
                                else:
                                    st.session_state["mfa_setup_mode"] = True
                                st.rerun()

            col_b1, col_b2 = st.columns([1, 1])
            with col_b1:
                st.link_button("🐛 Reportar Defeito", "mailto:felip21uba@gmail.com?subject=Reporte%20de%20Defeito%20-%20SIOP", use_container_width=True)
            with col_b2:
                if st.button("❓ Esqueci a Senha / Desbloquear Conta", use_container_width=True):
                    st.session_state["recuperar_senha_modo"] = True
                    st.rerun()

        st.markdown("""
            <div style="text-align: center; margin-top: 35px; border-top: 1px solid #334155; padding-top: 15px;">
                <span style="font-size: 11px; color: #64748b;">
                    <b>AVISO TÉCNICO:</b> Este software consiste em uma infraestrutura de gestão e automação de desenvolvimento independente.<br>
                    Possui caráter privado e não detém vínculo oficial, endosso ou integração direta com a arquitetura de TI oficial da PMMG.
                </span>
            </div>
        """, unsafe_allow_html=True)

    st.stop()

# =========================================================================
# 📌 SISTEMA PRINCIPAL (LIBERADO APÓS SUCESSO NO LOGIN)
# =========================================================================
aplicar_estilo_visual()

usr = st.session_state.get("usuario_dados", {})
usr_real_perfil = str(usr.get("nivel_acesso", "TROPA")).upper()

with st.sidebar:
    c_side_logo, c_side_txt = st.columns([1, 2])
    with c_side_logo:
        st.image(obter_imagem_brasao(), width=50)
    with c_side_txt:
        st.markdown("### **SIOP**")
        st.caption("PMMG - 2026")

    # -------------------------------------------------------------------------
    # 👁️ SIMULADOR DE VISÃO DE TROPA (BOTÃO PARA GESTORES)
    # -------------------------------------------------------------------------
    eh_gestor_real = usr_real_perfil in ["PROGRAMADOR", "ADMIN", "COMANDANTE_CIA", "P1", "P3", "SARGENTEANTE", "CMT_PELOTAO", "GESTOR"]
    
    if eh_gestor_real:
        st.markdown("---")
        st.markdown("👁️ **Modo de Visualização:**")
        
        simular_tropa = st.toggle("👁️ Visão da Tropa (Simulador)", value=st.session_state.get("simular_visao_tropa", False), key="toggle_visao_tropa")
        st.session_state["simular_visao_tropa"] = simular_tropa
        
        if simular_tropa:
            perfil_ativo = "TROPA"
            st.info("💡 **Simulador Ativo:** Exibindo tela restrita da TROPA.")
        else:
            perfil_ativo = usr_real_perfil

        # -------------------------------------------------------------------------
        # 🏛️ SELETOR MULTI-TENANT DE UNIDADES (PARA PROGRAMADOR / GESTOR)
        # -------------------------------------------------------------------------
        st.markdown("---")
        st.markdown("🏛️ **Seletor de Unidade (Multi-Tenant):**")
        
        lista_unis = []
        if supabase:
            try:
                res_u = supabase.table("configuracao_unidade").select("id, unidade_nome, subunidade_nome").execute()
                lista_unis = res_u.data or []
            except Exception:
                lista_unis = []

        if lista_unis:
            opcoes_uni = [f"{u.get('unidade_nome', '')} / {u.get('subunidade_nome', '')}".strip(" /") for u in lista_unis]
            
            idx_sel = 0
            uni_atual_sessao = st.session_state.get("unidade_ativa_nome")
            if uni_atual_sessao and uni_atual_sessao in opcoes_uni:
                idx_sel = opcoes_uni.index(uni_atual_sessao)

            sel_uni_sidebar = st.selectbox(
                "Unidade em Operação:",
                opcoes_uni,
                index=idx_sel,
                key="sb_multi_tenant_unidade"
            )
            st.session_state["unidade_ativa_nome"] = sel_uni_sidebar
            
            parts = sel_uni_sidebar.split(" / ")
            st.session_state["cfg_unidade"] = parts[0] if len(parts) > 0 else "21º BPM"
            st.session_state["cfg_subunidade"] = parts[1] if len(parts) > 1 else ""
        else:
            st.session_state["unidade_ativa_nome"] = usr.get("unidade", "21º BPM / 35ª CIA PM")
        st.markdown("---")
    else:
        perfil_ativo = "TROPA"
        st.session_state["unidade_ativa_nome"] = usr.get("unidade", "21º BPM / 35ª CIA PM")

    eh_gestor_ou_admin = (perfil_ativo != "TROPA")

    unidade_card_exibida = st.session_state.get("unidade_ativa_nome", usr.get("unidade", "PMMG"))
    st.info(f"👤 **{usr.get('nome_guerra', 'Militar')}**\n\n🔰 **Perfil Ativo:** `{perfil_ativo}`\n\n🏛️ **Unidade Ativa:** {unidade_card_exibida}")
    st.divider()

    if "modulo_ativo" not in st.session_state:
        st.session_state["modulo_ativo"] = "ESCALAS" if eh_gestor_ou_admin else "MINHA_ESCALA"

    st.markdown("**📌 Módulos Operacionais:**")
    
    if eh_gestor_ou_admin:
        if st.button("📅 Módulo de Escalas (Gestão)", use_container_width=True):
            st.session_state["modulo_ativo"] = "ESCALAS"
            st.rerun()

        if st.session_state.get("modulo_ativo") == "ESCALAS":
            st.markdown("**📍 Filtro de Passos da Escala:**")
            passo_sel = st.radio(
                "Exibir na Tela:",
                [
                    "VISUALIZAR TODOS",
                    "PASSO 1: Unidade & Equipes",
                    "PASSO 2: Turno & Horários",
                    "PASSO 3: Efetivo & Ausências",
                    "PASSO 4: Matriz Mensal",
                    "PASSO 5: Quadro Geral",
                    "PASSO 6: Exportação & Auditoria",
                    "PASSO 7: Banco de Horas",
                    "🗣️ Mural & Trocas de Serviço"
                ],
                key="rad_passos_escala"
            )
            st.session_state["passo_escala_ativo"] = passo_sel
        st.divider()

    if not eh_gestor_ou_admin:
        if st.button("📅 Minha Escala & Mural", use_container_width=True):
            st.session_state["modulo_ativo"] = "MINHA_ESCALA"
            st.rerun()
        st.divider()

    if eh_gestor_ou_admin:
        if st.button("📋 Módulo de TCO", use_container_width=True):
            st.session_state["modulo_ativo"] = "TCO"
            st.rerun()

        if st.button("📑 Módulo de Procedimentos", use_container_width=True):
            st.session_state["modulo_ativo"] = "PROCEDIMENTOS"
            st.rerun()
            
        if perfil_ativo in ["PROGRAMADOR", "ADMIN", "COMANDANTE_CIA", "P1"]:
            if st.button("⚙️ Gestão de Acessos", use_container_width=True):
                st.session_state["modulo_ativo"] = "GESTOES_USUARIOS"
                st.rerun()
        st.divider()

    if st.button("👤 Meu Perfil & Segurança", key="btn_menu_meu_perfil", use_container_width=True):
        st.session_state["modulo_ativo"] = "MEU_PERFIL"
        st.rerun()

    st.markdown("**🎨 Visualização da Interface:**")
    tema_atual = st.session_state.get("tema_visual", "DARK")
    label_tema = "☀️ Modo Claro" if tema_atual == "DARK" else "🌙 Modo Escuro"
    if st.button(label_tema, use_container_width=True):
        st.session_state["tema_visual"] = "LIGHT" if tema_atual == "DARK" else "DARK"
        st.rerun()
    st.divider()

    if st.button("🚪 Sair do Sistema", use_container_width=True):
        usr_m = str(usr.get("usuario_login") or usr.get("usuario") or "").strip().upper()
        if supabase and usr_m:
            try:
                supabase.table("usuarios").update({"token_sessao_ativa": "REVOGADO"}).eq("usuario_login", usr_m).execute()
            except Exception:
                pass

        registrar_audit_log(usr_m, "", "LOGOUT", "Sessão encerrada ativamente pelo usuário.")
        st.session_state["autenticado"] = False
        st.session_state["usuario_autenticado"] = False
        st.session_state["mfa_pendente"] = False
        st.session_state["mfa_setup_mode"] = False
        st.session_state["recuperar_senha_modo"] = False
        st.session_state["simular_visao_tropa"] = False
        st.session_state["usuario_dados"] = {}
        st.session_state["token_sessao_local"] = None
        st.rerun()

# =========================================================================
# 🚀 ROUTER CENTRAL DE TELAS
# =========================================================================
modulo = st.session_state.get("modulo_ativo", "MINHA_ESCALA")

# -------------------------------------------------------------------------
# 👮‍♂️ VISÃO RESTRITA DA TROPA
# -------------------------------------------------------------------------
if not eh_gestor_ou_admin or perfil_ativo == "TROPA":
    st.title("📅 Central do Policial")
    aba_escala, aba_mural, aba_mensagens = st.tabs([
        "📅 Minha Escala Individual", 
        "🗣️ Mural & Trocas de Serviço", 
        "📩 Mensagens & Requerimentos P1"
    ])
    
    num_policia_user = str(usr.get("usuario_login") or usr.get("usuario") or usr.get("num_policia") or "").strip()
    nome_user = usr.get("nome_guerra", "Militar")

    with aba_escala:
        st.info(f"👮‍♂️ Exibindo a linha individual na escala para **{usr.get('cargo_funcao', '')} {nome_user} ({num_policia_user})**.")
        
        df_escala = st.session_state.get("df_escala_consolidada")
        if df_escala is not None and not df_escala.empty:
            df_individual = df_escala[
                df_escala["Nº POLÍCIA"].astype(str).str.contains(num_policia_user, na=False) |
                df_escala["MILITAR"].astype(str).str.contains(nome_user, na=False)
            ]
            if not df_individual.empty:
                st.dataframe(df_individual, use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum turno cadastrado para você na escala publicada deste mês.")
        else:
            st.warning("A escala geral deste mês ainda não foi publicada pela P1/P3.")
            
    with aba_mural:
        renderizar_mural()

    with aba_mensagens:
        st.subheader("📩 Enviar Mensagem ou Solicitação à P1")
        st.caption("Utilize este canal oficial para encaminhar solicitações de permuta, certidões ou requerimentos ao comando.")
        
        with st.form("form_envio_msg_p1_tropa", clear_on_submit=True):
            assunto_msg = (st.text_input("Assunto / Motivo:") or "").strip()
            texto_msg = (st.text_area("Detalhamento da Solicitação:", height=120) or "").strip()
            
            btn_enviar_msg = st.form_submit_button("📤 Enviar Mensagem à P1", type="primary", use_container_width=True)
            if btn_enviar_msg:
                if not assunto_msg or not texto_msg:
                    st.error("⚠️ Preencha o assunto e o texto da mensagem.")
                else:
                    assunto_limpo = sanitizar_texto(assunto_msg)
                    texto_limpo = sanitizar_texto(texto_msg)

                    sucesso = salvar_mensagem_p1_supabase(num_policia_user, nome_user, assunto_limpo, texto_limpo)
                    if sucesso:
                        st.success("✅ Sua mensagem foi gravada no Supabase e enviada com segurança para a P1!")
                    else:
                        st.error("Erro ao enviar mensagem. Tente novamente.")

elif modulo == "ESCALAS" and eh_gestor_ou_admin:
    if st.session_state.get("passo_escala_ativo") == "🗣️ Mural & Trocas de Serviço":
        renderizar_mural()
    else:
        exibir_modulo_escalas()

elif modulo == "TCO" and eh_gestor_ou_admin:
    renderizar_modulo_tco()

elif modulo == "PROCEDIMENTOS" and eh_gestor_ou_admin:
    st.title("📑 Módulo de Procedimentos Administrativos")
    st.info("ℹ️ Módulo em desenvolvimento operacional.")

elif modulo == "GESTOES_USUARIOS" and perfil_ativo in ["PROGRAMADOR", "ADMIN", "COMANDANTE_CIA", "P1"]:
    exibir_tela_gestao_usuarios()

elif modulo == "MEU_PERFIL":
    exibir_tela_perfil()

else:
    st.error("🚨 Acesso Não Autorizado: Seu perfil não possui permissão para acessar este módulo.")

def renderizar_rodape_corporativo():
    st.markdown("<br><hr>", unsafe_allow_html=True)
    col_f1, col_f2, col_f3 = st.columns([1.5, 2, 1.5])
    
    with col_f1:
        unidade_txt = st.session_state.get("cfg_unidade") or st.session_state.get("usuario_dados", {}).get("unidade") or "21º BPM"
        subunidade_txt = st.session_state.get("cfg_subunidade") or "35ª CIA PM"
        st.caption(f"🏛️ **{unidade_txt}** | {subunidade_txt}")
        st.caption("PMMG - Polícia Militar de Minas Gerais")
        
    with col_f2:
        st.caption("🛡️ **SIOP - Sistema Integrado de Operações** v2.4")
        st.caption("Segurança da Informação, Compliance e Protocolos LGPD/PMMG")
        
    with col_f3:
        usr_sessao = st.session_state.get("usuario_dados", {}).get("nome_guerra", "Operador")
        st.caption(f"🟢 **Sessão Ativa:** {usr_sessao}")
        st.caption(f"⏱️ **Acesso:** {obter_agora().strftime('%H:%M:%S')}")

renderizar_rodape_corporativo()