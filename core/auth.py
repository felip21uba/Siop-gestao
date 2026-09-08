import pyotp
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
from core.database import supabase

# =========================================================================
# 1. HASHING E VERIFICAÇÃO DE SENHAS
# =========================================================================
def gerar_hash_senha(senha: str) -> str:
    """Gera o hash SHA-256 de uma senha em texto puro."""
    if not senha:
        return ""
    return hashlib.sha256(str(senha).encode('utf-8')).hexdigest()

def verificar_senha(senha_input, senha_db_texto, senha_db_hash):
    """Compara a senha digitada com Texto Puro e Hash SHA-256."""
    if not senha_input:
        return False
    senha_hash_input = gerar_hash_senha(senha_input)
    return (
        senha_input == senha_db_texto or
        senha_hash_input == senha_db_hash or
        senha_hash_input == senha_db_texto
    )

def validar_requisitos_senha(senha: str):
    """Valida regras de complexidade de senha."""
    if len(senha) < 6:
        return False, "A senha deve ter no mínimo 6 caracteres."
    if not any(c.isupper() for c in senha):
        return False, "A senha deve conter ao menos uma letra maiúscula (A-Z)."
    if not any(c.islower() for c in senha):
        return False, "A senha deve conter ao menos uma letra minúscula (a-z)."
    if not any(not c.isalnum() for c in senha):
        return False, "A senha deve conter ao menos um símbolo/caractere especial (@, #, $, !)."
    return True, "Senha válida!"

def validar_senha_forte(senha: str):
    """Alias de compatibilidade para módulos de perfil e gestão."""
    return validar_requisitos_senha(senha)

# =========================================================================
# 2. MFA / AUTHY / TOTP
# =========================================================================
def validar_codigo_authy(mfa_secret: str, codigo: str) -> bool:
    """Valida o token do Authy/Google Authenticator com janela de tolerância."""
    if not mfa_secret or not codigo:
        return False
    try:
        codigo_limpo = str(codigo).replace(" ", "").strip()
        totp = pyotp.TOTP(mfa_secret)
        return totp.verify(codigo_limpo, valid_window=1)
    except Exception:
        return False

def gerar_secret_mfa() -> str:
    """Gera uma nova chave base32 para MFA."""
    return pyotp.random_base32()

# =========================================================================
# 3. BANCO DE DADOS & GESTÃO DE USUÁRIOS
# =========================================================================
def buscar_usuario_para_login(usuario_input: str):
    """Consulta o registro do usuário por num_policia, usuario_login, usuario, id ou email_recuperacao."""
    if not supabase or not usuario_input:
        return None
    try:
        user_clean = str(usuario_input).strip()
        condicao_or = (
            f"num_policia.eq.{user_clean},"
            f"usuario_login.eq.{user_clean},"
            f"usuario.eq.{user_clean},"
            f"email_recuperacao.eq.{user_clean},"
            f"id.eq.{user_clean}"
        )
        res = supabase.table("usuarios").select("*").or_(condicao_or).execute()
        if res and res.data:
            return res.data[0]
    except Exception as e:
        print(f"Erro ao buscar usuário para login no Supabase: {e}")
    return None

def salvar_usuario_universal_supabase(dados_usuario: dict) -> bool:
    """Salva ou atualiza os dados de um usuário na tabela 'usuarios' do Supabase."""
    if not supabase or not dados_usuario:
        return False
    try:
        payload = dados_usuario.copy()
        if "senha" in payload and payload["senha"] and not payload.get("senha_hash"):
            payload["senha_hash"] = gerar_hash_senha(payload["senha"])

        supabase.table("usuarios").upsert(payload).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        print(f"Erro ao salvar usuário no Supabase: {e}")
        return False

def atualizar_senha_usuario(usuario_id: str, nova_senha: str) -> bool:
    """Atualiza a senha, o hash e o status de primeiro acesso do usuário no Supabase."""
    if not supabase or not usuario_id or not nova_senha:
        return False
    try:
        user_clean = str(usuario_id).strip()
        hash_nova = gerar_hash_senha(nova_senha)
        
        condicao_or = (
            f"num_policia.eq.{user_clean},"
            f"usuario_login.eq.{user_clean},"
            f"usuario.eq.{user_clean},"
            f"email_recuperacao.eq.{user_clean},"
            f"id.eq.{user_clean}"
        )
        
        payload = {
            "senha": nova_senha,
            "senha_hash": hash_nova,
            "primeiro_acesso": False
        }
        
        res = supabase.table("usuarios").update(payload).or_(condicao_or).execute()
        
        if res.data and len(res.data) > 0:
            st.cache_data.clear()
            return True
        return False
    except Exception as e:
        print(f"Erro ao atualizar senha no Supabase: {e}")
        return False

def obter_usuario_logado():
    """Retorna os dados do usuário atualmente autenticado na sessão."""
    return st.session_state.get("usuario_dados", {}) or st.session_state.get("usuario_logado", {})

# =========================================================================
# 4. DISPARO DE E-MAIL REAL (SMTP COM LEITURA FLEXÍVEL DE SECRETS)
# =========================================================================
def enviar_email_codigo(email_destino: str, codigo: str) -> tuple[bool, str]:
    """Envia o código de verificação/redefinição via servidor SMTP."""
    try:
        email_cfg = st.secrets.get("email", {})
        
        smtp_server = email_cfg.get("smtp_server") or st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(email_cfg.get("smtp_port") or st.secrets.get("SMTP_PORT", 587))
        smtp_user = email_cfg.get("email_remetente") or st.secrets.get("SMTP_USER") or st.secrets.get("EMAIL_REMETENTE")
        smtp_password = email_cfg.get("email_senha") or st.secrets.get("SMTP_PASSWORD") or st.secrets.get("EMAIL_SENHA")

        if not smtp_user or not smtp_password:
            return False, "Credenciais de e-mail não encontradas no secrets.toml."

        msg = MIMEMultipart()
        msg['From'] = f"SIOP PMMG <{smtp_user}>"
        msg['To'] = email_destino
        msg['Subject'] = f"🔑 Código de Acesso SIOP: {codigo}"

        corpo = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #cbd5e1; border-radius: 8px;">
            <h2 style="color: #1e3a8a;">🛡️ SIOP - Sistema Integrado de Operações</h2>
            <p>Seu código de verificação / redefinição de senha é:</p>
            <div style="font-size: 26px; font-weight: bold; letter-spacing: 5px; color: #0f172a; background: #f1f5f9; padding: 12px; width: fit-content; border-radius: 6px; margin: 15px 0;">
                {codigo}
            </div>
            <p style="font-size: 12px; color: #64748b;">Se você não solicitou esta alteração, ignore este e-mail.</p>
        </div>
        """
        msg.attach(MIMEText(corpo, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, f"Erro no envio de e-mail: {str(e)}"