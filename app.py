import os
import sys
import urllib.parse

# 🌐 REGISTRO DO DIRETÓRIO RAIZ NO SYS.PATH
DIRETORIO_RAIZ = os.path.abspath(os.path.dirname(__file__))
if DIRETORIO_RAIZ not in sys.path:
    sys.path.insert(0, DIRETORIO_RAIZ)

import datetime
from zoneinfo import ZoneInfo
import hashlib
import random
import uuid
import html
import re
import pyotp
import streamlit as st

# ==============================================================================
# 🌐 CONFIGURAÇÃO DE FUSO HORÁRIO E FUNÇÕES UTILITÁRIAS
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

def renderizar_rodape_corporativo():
    """Renderiza o rodapé institucional no final da página."""
    st.markdown("<br><hr>", unsafe_allow_html=True)
    col_f1, col_f2, col_f3 = st.columns([1.5, 2, 1.5])
    
    with col_f1:
        unidade_txt = st.session_state.get("cfg_unidade") or st.session_state.get("usuario_dados", {}).get("unidade") or "21º BPM"
        subunidade_txt = st.session_state.get("cfg_subunidade") or "35ª CIA PM"
        st.caption(f"🏛️ **{unidade_txt}** | {subunidade_txt}")
        st.caption("PMMG - Polícia Militar de Minas Gerais")
        
    with col_f2:
        st.caption("🛡️ **SIOP - Sistema Integrado de Operações** v2.5")
        st.caption("Segurança da Informação, Compliance e Protocolos LGPD/PMMG")
        
    with col_f3:
        usr_dados = st.session_state.get("usuario_dados", {})
        if isinstance(usr_dados, str):
            usr_dados = {"nome_guerra": usr_dados}

        nome_operador_rodape = (
            usr_dados.get("nome_guerra") 
            or usr_dados.get("nome_completo") 
            or usr_dados.get("usuario_login") 
            or "Operador"
        )

        st.caption(f"🟢 **Sessão Ativa:** {nome_operador_rodape}")
        st.caption(f"⏱️ **Acesso:** {obter_agora().strftime('%H:%M:%S')}")

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
from core.session_manager import (
    gerenciar_timeout_sessao, 
    restaurar_rascunho_escala_supabase
)

# IMPORTE DOS MÓDULOS OPERACIONAIS
from modules.escalas import exibir_modulo_escalas
from modules.mural import renderizar_mural
from modules.gestao_usuarios import exibir_tela_gestao_usuarios
from modules.perfil import exibir_tela_perfil
from modules.tco.main_tco import renderizar_modulo_tco
from modules.governanca.views import renderizar_modulo_governanca

# 1. Configuração Inicial da Página
st.set_page_config(
    page_title="SIOP - Sistema Integrado de Operações",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🎨 OCULTA A SELEÇÃO NATIVA DE PÁGINAS DA BARRA LATERAL
st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 🖥️ VERIFICAÇÃO ANTECIPADA DO MODO POP-OUT / SEGUNDA TELA
query_params = st.query_params
if query_params.get("modo_monitor") == "segunda_tela":
    from modules.escalas.passos.passo5_espelho import renderizar_modo_segunda_tela
    renderizar_modo_segunda_tela()
    st.stop()

# 2. Inicialização do Estado de Sessão
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_autenticado" not in st.session_state:
    st.session_state["usuario_autenticado"] = False
if "usuario_dados" not in st.session_state:
    st.session_state["usuario_dados"] = {}
if "token_sessao_local" not in st.session_state:
    st.session_state["token_sessao_local"] = None
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
if "tema_visual" not in st.session_state:
    st.session_state["tema_visual"] = "DARK"

# ==============================================================================
# 🔄 RESTAURAÇÃO DE SESSÃO COM CONTROLE RÍGIDO DE TIMEOUT (20 MINUTOS)
# ==============================================================================
token_url = query_params.get("session_token")

if not st.session_state.get("autenticado", False) and token_url:
    if supabase:
        try:
            res_sessao = supabase.table("usuarios").select("*").eq("token_sessao_ativa", token_url).execute()
            if res_sessao.data and len(res_sessao.data) > 0:
                usr_recuperado = res_sessao.data[0]
                if usr_recuperado.get("ativo", True):
                    # Valida se a última atividade não ultrapassou 20 minutos
                    ult_atividade_str = usr_recuperado.get("ultima_atividade")
                    sessao_valida = True
                    if ult_atividade_str:
                        try:
                            dt_ult = datetime.datetime.fromisoformat(str(ult_atividade_str).replace("Z", "+00:00"))
                            diferenca_minutos = (datetime.datetime.now(datetime.timezone.utc) - dt_ult).total_seconds() / 60.0
                            if diferenca_minutos > 20.0:
                                sessao_valida = False
                        except Exception:
                            pass

                    if sessao_valida:
                        st.session_state["usuario_dados"] = usr_recuperado
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_autenticado"] = True
                        st.session_state["token_sessao_local"] = token_url
                        st.session_state["ultima_atividade_time"] = datetime.datetime.now()
                        st.toast(f"🟢 Sessão mantida para {usr_recuperado.get('nome_guerra', 'Operador')}!", icon="🔄")
                    else:
                        # Expira a sessão no banco e limpa parâmetros
                        supabase.table("usuarios").update({"token_sessao_ativa": "EXPIRADO"}).eq("id", usr_recuperado["id"]).execute()
                        st.query_params.clear()
                        st.error("⏰ **Sessão Expirada:** Você permaneceu inativo por mais de 20 minutos. Faça login novamente.")
        except Exception as ex:
            print(f"Erro ao restaurar sessão pelo F5: {ex}")

# CONSTANTES VISUAIS INSTITUCIONAIS
URL_BRASAO_PADRAO = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Bras%C3%A3o_PMMG.svg/500px-Bras%C3%A3o_PMMG.svg.png"
CAMINHO_BRASAO_LOCAL = "assets/brasao.png"

def obter_imagem_brasao():
    if os.path.exists(CAMINHO_BRASAO_LOCAL):
        return CAMINHO_BRASAO_LOCAL
    return URL_BRASAO_PADRAO

# ==============================================================================
# ⏱️ GERENCIAMENTO DE TIMEOUT E SESSÃO ÚNICA CONCORRENTE
# ==============================================================================
if st.session_state.get("autenticado", False):
    usr_dados = st.session_state.get("usuario_dados", {})
    usr_login = str(usr_dados.get("usuario_login") or usr_dados.get("usuario") or "").strip().upper()
    usr_id = str(usr_dados.get("id") or usr_login or "").strip()
    token_local = st.session_state.get("token_sessao_local")

    if token_local and st.query_params.get("session_token") != token_local:
        st.query_params["session_token"] = token_local

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
                    st.session_state["mfa_setup_mode"] = False
                    st.session_state["usuario_dados"] = {}
                    st.session_state["token_sessao_local"] = None
                    st.query_params.clear()
                    st.error("🚨 **Sessão Encerrada:** Sua conta foi acessada em outro dispositivo ou a sessão expirou.")
                    st.stop()
        except Exception:
            pass

    if usr_id:
        restaurar_rascunho_escala_supabase(usr_id)

    gerenciar_timeout_sessao()

# ==============================================================================
# 🛠️ DIÁLOGOS DE SUPORTE (MODAL DE REPORTAR ERRO)
# ==============================================================================
@st.dialog("🐛 Reportar Defeito / Erro no Sistema")
def abrir_modal_reportar_erro():
    st.markdown("##### Preencha os detalhes do problema encontrado:")
    st.caption("A mensagem será enviada diretamente à equipe de desenvolvimento e gravada no histórico de auditoria.")

    with st.form("form_modal_reportar_erro", clear_on_submit=True):
        operador_nome = st.text_input("Militar / Operador:", value=st.session_state.get("usuario_dados", {}).get("nome_guerra", "Operador"), disabled=True)
        categoria_erro = st.selectbox("Tipo de Problema:", ["Erro de Cálculo na Escala", "Falha de Interface / Layout", "Problema com Impressão / PDF", "Erro de Conexão / Supabase", "Outro"])
        descricao_erro = st.text_area("Descrição Detalhada do Erro:", placeholder="Explique o que aconteceu, a tela em que ocorreu e os passos para reproduzir o erro...", height=120)

        col_rep1, col_rep2 = st.columns(2)
        with col_rep1:
            btn_enviar_reporte = st.form_submit_button("📤 Enviar Relatório", type="primary", use_container_width=True)
        with col_rep2:
            btn_cancelar_reporte = st.form_submit_button("❌ Cancelar", use_container_width=True)

        if btn_cancelar_reporte:
            st.rerun()

        if btn_enviar_reporte:
            if not descricao_erro.strip():
                st.error("⚠️ Descreva o erro antes de enviar.")
            else:
                email_desenvolvedor = "felip21uba@gmail.com"
                corpo_email = f"""
                <h3>🐛 Novo Relatório de Erro - SIOP PMMG</h3>
                <p><b>Operador:</b> {operador_nome}</p>
                <p><b>Categoria:</b> {categoria_erro}</p>
                <p><b>Data/Hora:</b> {obter_agora().strftime('%d/%m/%Y %H:%M:%S')}</p>
                <p><b>Detalhamento:</b></p>
                <blockquote style="background: #f1f5f9; padding: 10px; border-left: 4px solid #b91c1c;">
                    {sanitizar_texto(descricao_erro)}
                </blockquote>
                """
                
                sucesso_envio, msg_envio = enviar_email_codigo(email_desenvolvedor, f"ERRO: {categoria_erro}")
                
                # Grava no banco
                registrar_audit_log(
                    operador_pm=operador_nome,
                    alvo_pm="SISTEMA",
                    tipo_acao="REPORTE_ERRO",
                    descricao=f"[{categoria_erro}] {descricao_erro}"
                )

                st.success("✅ Relatório de erro enviado com sucesso para a equipe de suporte!")
                st.rerun()

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

        # FLUXO 1: RECUPERAÇÃO DE SENHA VALIDADO POR E-MAIL + CÓDIGO DO QR CODE (2FA)
        if st.session_state.get("recuperar_senha_modo", False):
            st.subheader("🔑 Recuperação de Senha & Validação 2FA")
            st.info("Informe seu Nº de Polícia ou e-mail. Para segurança, a redefinição exige a validação do e-mail + o código do QR Code cadastrado.")

            if "codigo_enviado" not in st.session_state["reset_token_dados"]:
                with st.form("form_solicitar_codigo_email"):
                    identificador = (st.text_input("Nº de Polícia ou E-mail Cadastrado:", placeholder="Ex: 0000000 ou militar@pmmg.mg.gov.br") or "").strip()
                    
                    c_rec1, c_rec2 = st.columns(2)
                    with c_rec1:
                        btn_gerar_codigo = st.form_submit_button("📩 Solicitar Código por E-mail", type="primary", use_container_width=True)
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
                            
                            if not usr_obj:
                                st.error("❌ Usuário não localizado no sistema. Verifique a matrícula ou e-mail digitado.")
                            else:
                                email_alvo = usr_obj.get("email_recuperacao") or (identificador if "@" in identificador else None)

                                if not email_alvo:
                                    st.error("❌ Nenhum e-mail de recuperação cadastrado para este usuário.")
                                else:
                                    codigo_gerado = str(random.randint(100000, 999999))
                                    sucesso_envio, msg_envio = enviar_email_codigo(email_alvo, codigo_gerado)
                                    
                                    if sucesso_envio:
                                        num_login_real = usr_obj.get("usuario_login") or usr_obj.get("usuario") or identificador
                                        st.session_state["reset_token_dados"] = {
                                            "codigo_enviado": codigo_gerado,
                                            "usuario_id": num_login_real,
                                            "mfa_secret": usr_obj.get("mfa_secret", ""),
                                            "identificador_digitado": identificador
                                        }
                                        st.toast(f"Código enviado para {email_alvo}!", icon="📩")
                                        st.rerun()
                                    else:
                                        st.error(f"🚨 {msg_envio}")

            else:
                cod_correto = st.session_state["reset_token_dados"]["codigo_enviado"]
                usr_id = st.session_state["reset_token_dados"]["usuario_id"]
                secret_mfa_usr = st.session_state["reset_token_dados"].get("mfa_secret", "")

                st.success("📧 **Instruções enviadas!** Digite o código do e-mail, o código de 6 dígitos do seu QR Code/App Authenticator e cadastre a nova senha:")

                with st.form("form_confirmar_reset_email"):
                    cod_email_digitado = (st.text_input("📩 Código de 6 dígitos recebido por E-mail:", max_chars=6) or "").strip()
                    cod_qr_digitado = (st.text_input("📱 Código de 6 dígitos do seu App/QR Code (Authy/Google Authenticator):", max_chars=6) or "").strip()
                    nova_senha = (st.text_input("Nova Senha:", type="password", placeholder="Ex: Pmmg@2026") or "").strip()
                    confirma_senha = (st.text_input("Confirme a Nova Senha:", type="password") or "").strip()

                    col_res1, col_res2 = st.columns(2)
                    with col_res1:
                        btn_finalizar_reset = st.form_submit_button("✅ Redefinir Senha & Desbloquear", type="primary", use_container_width=True)
                    with col_res2:
                        btn_cancelar_reset = st.form_submit_button("❌ Cancelar", use_container_width=True)

                    if btn_cancelar_reset:
                        st.session_state["recuperar_senha_modo"] = False
                        st.session_state["reset_token_dados"] = {}
                        st.rerun()

                    if btn_finalizar_reset:
                        if cod_email_digitado != cod_correto:
                            st.error("🚨 Código enviado por e-mail está incorreto!")
                        elif secret_mfa_usr and not validar_codigo_authy(secret_mfa_usr, cod_qr_digitado):
                            st.error("🚨 Código do QR Code (Authenticator) incorreto ou expirado!")
                        elif nova_senha != confirma_senha:
                            st.error("❌ As senhas não coincidem.")
                        else:
                            senha_ok, msg_s = validar_requisitos_senha(nova_senha)
                            if not senha_ok:
                                st.error(f"⛔ {msg_s}")
                            else:
                                hash_nova = gerar_hash_senha(nova_senha)
                                u_clean = str(usr_id).strip().upper()

                                if supabase:
                                    try:
                                        supabase.table("usuarios").update({
                                            "senha": nova_senha,
                                            "senha_hash": hash_nova,
                                            "ativo": True,
                                            "tentativas_erradas": 0
                                        }).eq("usuario_login", u_clean).execute()
                                    except Exception:
                                        atualizar_usuario_supabase(usr_id, {
                                            "senha": nova_senha,
                                            "senha_hash": hash_nova,
                                            "ativo": True
                                        })

                                registrar_audit_log(
                                    operador_pm=usr_id,
                                    alvo_pm=usr_id,
                                    tipo_acao="RESET_SENHA_MFA",
                                    descricao="Senha redefinida com dupla validação (E-mail + QR Code)."
                                )

                                st.success("🎉 Senha redefinida com sucesso! Acesse utilizando sua nova senha.")
                                st.session_state["recuperar_senha_modo"] = False
                                st.session_state["reset_token_dados"] = {}
                                st.rerun()

        # FLUXO 2: PRIMEIRO ACESSO - CADASTRO DO QR CODE + E-MAIL + CELULAR + TROCA DE SENHA
        elif st.session_state.get("mfa_setup_mode", False):
            usr_temp = st.session_state.get("temp_user_data", {})
            st.warning("🛡️ **Primeiro Acesso: Cadastro de Segurança & QR Code**")
            st.markdown("Cadastre seus dados de contato, sua **nova senha pessoal** e escaneie o QR Code no seu aplicativo **Google Authenticator ou Authy**.")

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
                st.image(qr_url, caption="Escaneie com o Google Authenticator ou Authy")
            with c_qr2:
                st.info(f"📍 **Chave Manual TOTP:**\n\n`{secret}`\n\n*Guarde este QR Code. Ele será solicitado caso precise redefinir sua senha no futuro.*")

            st.markdown("---")
            with st.form("form_mfa_setup"):
                st.markdown("##### 🔐 1. Cadastre sua Nova Senha Pessoal:")
                nova_senha = (st.text_input("Nova Senha:", type="password", placeholder="Ex: Pmmg@2026") or "").strip()
                confirma_senha = (st.text_input("Confirme a Nova Senha:", type="password") or "").strip()

                st.markdown("##### 📱 2. Dados de Contato & Validação Inicial do QR Code:")
                email_input = (st.text_input("E-mail Funcional/Pessoal:", value=usr_temp.get("email_recuperacao") or "", placeholder="militar@pmmg.mg.gov.br") or "").strip()
                celular_input = (st.text_input("Celular / WhatsApp:", value=usr_temp.get("celular_recuperacao") or "", placeholder="(32) 90000-0000") or "").strip()
                codigo_setup = (st.text_input("🔑 Token de 6 dígitos gerado no App para confirmar o vínculo:", max_chars=6) or "").strip()

                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    btn_confirmar_setup = st.form_submit_button("💾 Salvar Cadastro & Ativar Conta", type="primary", use_container_width=True)
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
                            st.error("🚨 Código de validação do QR Code incorreto.")
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
                                        "primeiro_acesso": False,
                                        "email_recuperacao": email_input, 
                                        "celular_recuperacao": celular_input,
                                        "token_sessao_ativa": novo_token,
                                        "ativo": True
                                    }).eq("usuario_login", num_pol_str).execute()
                                except Exception:
                                    atualizar_usuario_supabase(num_pol_str, {"token_sessao_ativa": novo_token})
                            
                            usr_temp["senha"] = nova_senha
                            usr_temp["senha_hash"] = hash_nova
                            usr_temp["mfa_secret"] = secret
                            usr_temp["mfa_habilitado"] = True
                            usr_temp["primeiro_acesso"] = False
                            usr_temp["email_recuperacao"] = email_input
                            usr_temp["celular_recuperacao"] = celular_input
                            usr_temp["token_sessao_ativa"] = novo_token

                            st.session_state["token_sessao_local"] = novo_token
                            st.session_state["usuario_dados"] = usr_temp
                            st.session_state["autenticado"] = True
                            st.session_state["usuario_autenticado"] = True
                            st.session_state["mfa_setup_mode"] = False
                            st.session_state["ultima_atividade_time"] = datetime.datetime.now()
                            st.query_params["session_token"] = novo_token
                            
                            if "temp_mfa_secret" in st.session_state:
                                del st.session_state["temp_mfa_secret"]

                            st.toast("✅ Primeiro acesso concluído com sucesso!", icon="🎉")
                            st.rerun()

        # FLUXO 3: TELA PRINCIPAL DE LOGIN (LOGIN DIRETO SEM QR CODE NO ACESSO DIÁRIO)
        else:
            with st.form("form_login_principal"):
                usuario_input = (st.text_input("Nº de Polícia / Matrícula / E-mail:", placeholder="Ex: 1337468") or "").strip()
                senha_input = (st.text_input("Senha de Acesso:", type="password", placeholder="••••••••") or "").strip()
                
                btn_entrar = st.form_submit_button("🔑 Entrar no Sistema", type="primary", use_container_width=True)

                if btn_entrar:
                    if not usuario_input or not senha_input:
                        st.error("⚠️ Preencha as credenciais de acesso.")
                    else:
                        u_clean = str(usuario_input).strip().upper()
                        u_sem_zero = u_clean.lstrip("0")
                        
                        usuario_encontrado = buscar_usuario_para_login(u_clean) or buscar_usuario_para_login(u_sem_zero)

                        if not usuario_encontrado:
                            st.error(f"❌ Usuário '{usuario_input}' não localizado no sistema.")
                        elif not usuario_encontrado.get("ativo", True):
                            st.error("🔒 Conta Bloqueada. Utilize a redefinição de senha abaixo.")
                        else:
                            senha_db_texto = usuario_encontrado.get("senha")
                            senha_db_hash = usuario_encontrado.get("senha_hash")

                            if not verificar_senha(senha_input, senha_db_texto, senha_db_hash):
                                erros_atuais = st.session_state["tentativas_login"].get(usuario_input, 0) + 1
                                st.session_state["tentativas_login"][usuario_input] = erros_atuais

                                if erros_atuais >= 3:
                                    if supabase:
                                        atualizar_usuario_supabase(u_clean, {"ativo": False})
                                    st.error("🚨 Senha Incorreta! Sua conta foi temporariamente BLOQUEADA.")
                                else:
                                    st.error(f"🚨 Senha Incorreta! Tentativa {erros_atuais} de 3.")
                            else:
                                # Se for PRIMEIRO ACESSO, força a configuração inicial do QR Code
                                if usuario_encontrado.get("primeiro_acesso", True) or not usuario_encontrado.get("mfa_habilitado", False):
                                    st.session_state["temp_user_data"] = usuario_encontrado
                                    st.session_state["mfa_setup_mode"] = True
                                    st.rerun()

                                # ACESSO NORMAL (Login direto sem pedir QR Code)
                                st.session_state["tentativas_login"][usuario_input] = 0
                                novo_token = str(uuid.uuid4())
                                num_pol_str = str(usuario_encontrado.get("usuario_login") or usuario_encontrado.get("usuario") or "").strip().upper()

                                if supabase and num_pol_str:
                                    try:
                                        supabase.table("usuarios").update({
                                            "token_sessao_ativa": novo_token,
                                            "ultima_atividade": datetime.datetime.now(datetime.timezone.utc).isoformat()
                                        }).eq("usuario_login", num_pol_str).execute()
                                    except Exception:
                                        atualizar_usuario_supabase(num_pol_str, {"token_sessao_ativa": novo_token})

                                usuario_encontrado["token_sessao_ativa"] = novo_token
                                st.session_state["token_sessao_local"] = novo_token
                                st.session_state["usuario_dados"] = usuario_encontrado
                                st.session_state["autenticado"] = True
                                st.session_state["usuario_autenticado"] = True
                                st.session_state["ultima_atividade_time"] = datetime.datetime.now()
                                st.query_params["session_token"] = novo_token
                                
                                registrar_audit_log(
                                    operador_pm=num_pol_str,
                                    alvo_pm=None,
                                    tipo_acao="LOGIN_SUCESSO",
                                    descricao="Login realizado com sucesso."
                                )
                                st.toast(f"Acesso liberado! Bem-vindo, {usuario_encontrado.get('nome_guerra')}!", icon="🟢")
                                st.rerun()

            col_b1, col_b2 = st.columns([1, 1])
            with col_b1:
                if st.button("🐛 Reportar Defeito", use_container_width=True):
                    abrir_modal_reportar_erro()
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
# 📌 EXTRAÇÃO DE DADOS DO OPERADOR PARA ESCOPO GLOBAL
# =========================================================================
aplicar_estilo_visual()

usr = st.session_state.get("usuario_dados", {})
if isinstance(usr, str):
    usr = {"nome_guerra": usr}

nome_op = (
    usr.get("nome_guerra") 
    or usr.get("nome_completo") 
    or usr.get("usuario_login") 
    or "OPERADOR"
)
unid_op = st.session_state.get("unidade_ativa_nome") or usr.get("unidade", "21º BPM / 35ª CIA PM")
cargo_op = usr.get("cargo_funcao", "MILITAR")
perfil_op = str(usr.get("nivel_acesso") or usr.get("perfil") or usr.get("cargo_funcao") or "TROPA").upper()

# DEFINIÇÃO DE PERFIL E MODO DE VISUALIZAÇÃO
LISTA_GESTORES = ["PROGRAMADOR", "DESENVOLVEDOR", "TESTADOR", "ADMIN", "COMANDANTE_CIA", "P1", "P3", "SARGENTEANTE", "CMT_PELOTAO", "CMT_FRACAO", "GESTOR"]
eh_gestor_real = any(p in perfil_op for p in LISTA_GESTORES)

if eh_gestor_real:
    simular_tropa = st.session_state.get("simular_visao_tropa", False)
    if simular_tropa:
        perfil_ativo = "TROPA"
    else:
        perfil_ativo = perfil_op
else:
    perfil_ativo = "TROPA"
    st.session_state["simular_visao_tropa"] = False

eh_gestor_ou_admin = (perfil_ativo != "TROPA")

if "modulo_ativo" not in st.session_state:
    st.session_state["modulo_ativo"] = "ESCALAS" if eh_gestor_ou_admin else "MINHA_ESCALA"

modulo_ativo = st.session_state["modulo_ativo"]

# =========================================================================
# 🏗️ RENDERIZAÇÃO DA BARRA LATERAL UNIFICADA (SIDEBAR)
# =========================================================================
with st.sidebar:
    c_l, c_mid, c_r = st.columns([1, 1.5, 1])
    with c_mid:
        try:
            st.image(obter_imagem_brasao(), use_container_width=True)
        except Exception:
            st.markdown("🛡️")

    if eh_gestor_real:
        if st.toggle("👁️ Visão da Tropa (Simulador)", value=st.session_state.get("simular_visao_tropa", False), key="toggle_visao_tropa_nav"):
            st.session_state["simular_visao_tropa"] = True
            st.rerun()
        elif st.session_state.get("simular_visao_tropa", False):
            st.session_state["simular_visao_tropa"] = False
            st.rerun()

        if not st.session_state.get("simular_visao_tropa", False):
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
                    key="sb_multi_tenant_unidade_nav",
                    label_visibility="collapsed"
                )
                st.session_state["unidade_ativa_nome"] = sel_uni_sidebar
                parts = sel_uni_sidebar.split(" / ")
                st.session_state["cfg_unidade"] = parts[0] if len(parts) > 0 else "21º BPM"
                st.session_state["cfg_subunidade"] = parts[1] if len(parts) > 1 else ""
            else:
                st.session_state["unidade_ativa_nome"] = usr.get("unidade", "21º BPM / 35ª CIA PM")
    else:
        st.session_state["unidade_ativa_nome"] = usr.get("unidade", "21º BPM / 35ª CIA PM")

    st.divider()

    st.markdown("##### 🧩 Módulos do Sistema")
    with st.container(border=True):
        if eh_gestor_ou_admin:
            if st.button("📅 Módulo Escalas", key="k_btn_mod_escalas_nav", use_container_width=True, type="primary" if modulo_ativo == "ESCALAS" else "secondary"):
                st.session_state["modulo_ativo"] = "ESCALAS"
                st.rerun()

            if modulo_ativo == "ESCALAS":
                passo_sel = st.radio(
                    "Submenu Escalas:",
                    [
                        "VISUALIZAR TODOS",
                        "PASSO 1: Unidade & Equipes",
                        "PASSO 2: Turno & Horários",
                        "PASSO 3: Efetivo & Ausências",
                        "PASSO 4: Matriz Mensal",
                        "PASSO 5: Quadro Geral",
                        "PASSO 6: Exportação & Auditoria",
                        "PASSO 7: Banco de Horas",
                        "PASSO 8: Férias Anuais"
                    ],
                    key="subnav_escalas_unique_nav",
                    label_visibility="collapsed"
                )
                st.session_state["passo_escala_ativo"] = passo_sel
        else:
            if st.button("📅 Minha Escala Individual", key="k_btn_mod_minha_escala_nav", use_container_width=True, type="primary" if modulo_ativo == "MINHA_ESCALA" else "secondary"):
                st.session_state["modulo_ativo"] = "MINHA_ESCALA"
                st.rerun()

        if st.button("📦 Módulo TCO / Custódia", key="k_btn_mod_tco_nav", use_container_width=True, type="primary" if modulo_ativo == "TCO" else "secondary"):
            st.session_state["modulo_ativo"] = "TCO"
            st.rerun()

        if modulo_ativo == "TCO":
            subnav_tco_sel = st.radio(
                "Submenu TCO:",
                [
                    "📥 Importar REDS",
                    "🎒 Meus Materiais",
                    "🔄 Tramitação",
                    "📄 Ofícios",
                    "🏛️ Painel CREDS",
                    "📜 Auditoria",
                    "👥 Gestores"
                ],
                key="subnav_tco_sidebar_unique",
                label_visibility="collapsed"
            )
            st.session_state["subnav_tco"] = subnav_tco_sel

        if st.button("⚖️ Módulo Procedimentos", key="k_btn_mod_procedimentos_nav", use_container_width=True, type="primary" if modulo_ativo == "PROCEDIMENTOS" else "secondary"):
            st.session_state["modulo_ativo"] = "PROCEDIMENTOS"
            st.rerun()

        if any(p in perfil_ativo for p in ["PROGRAMADOR", "ADMIN", "COMANDANTE_CIA", "P1", "DESENVOLVEDOR"]):
            if st.button("⚙️ Gestão de Acessos", key="k_btn_mod_gestao_acessos_nav", use_container_width=True, type="primary" if modulo_ativo == "GESTOES_USUARIOS" else "secondary"):
                st.session_state["modulo_ativo"] = "GESTOES_USUARIOS"
                st.rerun()

        if st.button("🛡️ Governança & Segurança", key="k_btn_mod_governanca_nav", use_container_width=True, type="primary" if modulo_ativo == "GOVERNANCA" else "secondary"):
            st.session_state["modulo_ativo"] = "GOVERNANCA"
            st.rerun()

    qtd_novas_mensagens = 0 
    badge_msg = f" 🔴 ({qtd_novas_mensagens})" if qtd_novas_mensagens > 0 else ""
    if st.button(f"📢 Mural de Avisos & Trocas{badge_msg}", key="k_btn_mural_avisos_nav", use_container_width=True, type="primary" if modulo_ativo == "MURAL" else "secondary"):
        st.session_state["modulo_ativo"] = "MURAL"
        st.rerun()

    st.divider()

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("👤 Perfil", key="k_btn_perfil_nav", use_container_width=True, type="primary" if modulo_ativo == "MEU_PERFIL" else "secondary"):
            st.session_state["modulo_ativo"] = "MEU_PERFIL"
            st.rerun()
            
    with col_p2:
        tema_atual = st.session_state.get("tema_visual", "DARK")
        is_dark = (tema_atual == "DARK")
        novo_tema_toggle = st.toggle("🌙 Escuro", value=is_dark, key="toggle_tema_escuro_nav_fix")
        if novo_tema_toggle != is_dark:
            st.session_state["tema_visual"] = "DARK" if novo_tema_toggle else "LIGHT"
            st.rerun()

    if st.button("🚪 Sair do Sistema", key="k_btn_logout_nav", use_container_width=True):
        usr_m = str(usr.get("usuario_login") or usr.get("usuario") or "").strip().upper()
        if supabase and usr_m:
            try:
                supabase.table("usuarios").update({"token_sessao_ativa": "REVOGADO"}).eq("usuario_login", usr_m).execute()
            except Exception:
                pass

        st.session_state["autenticado"] = False
        st.session_state["usuario_autenticado"] = False
        st.session_state["usuario_dados"] = {}
        st.session_state["token_sessao_local"] = None
        st.query_params.clear()
        st.rerun()

# =========================================================================
# 🚀 ROUTER CENTRAL DE TELAS
# =========================================================================
modulo = st.session_state.get("modulo_ativo", "ESCALAS" if eh_gestor_ou_admin else "MINHA_ESCALA")

if modulo == "MINHA_ESCALA" or (not eh_gestor_ou_admin and modulo not in ["TCO", "MURAL", "MEU_PERFIL", "PROCEDIMENTOS", "GOVERNANCA"]):
    st.title("📅 Central do Policial")
    aba_escala, aba_mensagens = st.tabs([
        "📅 Minha Escala Individual", 
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

elif modulo == "ESCALAS":
    exibir_modulo_escalas()

elif modulo == "TCO":
    renderizar_modulo_tco()

elif modulo == "PROCEDIMENTOS":
    st.title("📑 Módulo de Procedimentos Administrativos")
    st.info("ℹ️ Módulo em desenvolvimento operacional.")

elif modulo == "GESTOES_USUARIOS":
    exibir_tela_gestao_usuarios()

elif modulo == "GOVERNANCA":
    try:
        renderizar_modulo_governanca(
            nome_operador=nome_op,
            unidade_operador=unid_op,
            cargo_operador=cargo_op,
            perfil_operador=perfil_op
        )
    except TypeError:
        try:
            renderizar_modulo_governanca(usr)
        except TypeError:
            renderizar_modulo_governanca()

elif modulo == "MURAL":
    st.title("📢 Mural de Avisos & Trocas de Serviço")
    renderizar_mural()

elif modulo == "MEU_PERFIL":
    exibir_tela_perfil()

else:
    st.session_state["modulo_ativo"] = "ESCALAS" if eh_gestor_ou_admin else "MINHA_ESCALA"
    st.rerun()

renderizar_rodape_corporativo()