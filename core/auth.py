import hashlib
import re
import io
import pyotp
import requests
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
import qrcode
from core.database import supabase

def gerar_hash_senha(senha: str) -> str:
    """Gera o hash SHA-256 da senha fornecida."""
    if not senha:
        return ""
    return hashlib.sha256(senha.encode('utf-8')).hexdigest()

def validar_senha_forte(senha: str) -> tuple[bool, str]:
    """Valida as regras de complexidade de senha corporativa."""
    if len(senha) < 8:
        return False, "A senha deve conter no mínimo 8 caracteres."
    if not re.search(r"[A-Z]", senha):
        return False, "A senha deve conter pelo menos uma letra maiúscula."
    if not re.search(r"[a-z]", senha):
        return False, "A senha deve conter pelo menos uma letra minúscula."
    if not re.search(r"[0-9]", senha):
        return False, "A senha deve conter pelo menos um número."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha):
        return False, "A senha deve conter pelo menos um caractere especial (!@#$%...)."
    return True, ""

def gerar_qrcode_base64(uri: str) -> bytes:
    """Gera o QR Code para pareamento do 2FA no Authy / Google Authenticator."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def validar_codigo_totp(secret_base32: str, pin_digitado: str) -> bool:
    """
    Valida o código de 6 dígitos gerado pelo Authy / Google Authenticator com tolerância de tempo.
    """
    if not secret_base32 or not pin_digitado:
        return False
    try:
        sec_limpo = str(secret_base32).strip().replace(" ", "").upper()
        totp = pyotp.TOTP(sec_limpo)
        # valid_window=1 aceita o PIN atual, o anterior (-30s) e o próximo (+30s)
        return totp.verify(str(pin_digitado).strip(), valid_window=1)
    except Exception as ex:
        print(f"Erro ao validar TOTP: {ex}")
        return False

def mascarar_contato(contato: str) -> str:
    """Mascara e-mails e telefones para proteger dados na tela de validação."""
    if not contato:
        return "****"
    if "@" in contato:
        partes = contato.split("@")
        usuario = partes[0]
        if len(usuario) <= 2:
            usr_m = usuario[0] + "*"
        else:
            usr_m = usuario[0] + "*" * (len(usuario) - 2) + usuario[-1]
        return f"{usr_m}@{partes[1]}"
    else:
        num_limpo = re.sub(r"\D", "", contato)
        if len(num_limpo) >= 8:
            return f"({num_limpo[:2]}) *****-{num_limpo[-4:]}"
        return "****"

# =========================================================================
# 🛡️ REGRAS DE QUARENTENA PROGRESSIVA DE RECUPERAÇÃO DE SENHA
# =========================================================================

def verificar_quarentena_reset(usuario_data: dict) -> tuple[bool, str]:
    """
    Valida se a conta está sob quarentena temporária para solicitar PINs.
    """
    agora = datetime.datetime.now()
    quarentena_ate_str = usuario_data.get("quarentena_ate")
    
    if quarentena_ate_str:
        try:
            quarentena_ate = datetime.datetime.fromisoformat(str(quarentena_ate_str))
            if agora < quarentena_ate:
                minutos_restantes = int((quarentena_ate - agora).total_seconds() / 60) + 1
                return True, f"⏳ Conta em quarentena de segurança. Aguarde {minutos_restantes} minuto(s) para solicitar novo código."
        except Exception:
            pass

    return False, ""

def registrar_solicitacao_reset_supabase(usuario_login: str, usuario_data: dict) -> tuple[bool, str]:
    """
    Contabiliza solicitações de PIN e aplica bloqueios de 5 min ou 20 min.
    """
    agora = datetime.datetime.now()
    tentativas = usuario_data.get("cnt_solicitacoes_reset", 0) or 0
    primeira_sol = usuario_data.get("primeira_solicitacao_reset")
    
    dt_primeira = agora
    if primeira_sol:
        try:
            dt_primeira = datetime.datetime.fromisoformat(str(primeira_sol))
        except Exception:
            dt_primeira = agora

    diferenca_minutos = (agora - dt_primeira).total_seconds() / 60

    # Reseta a contagem se a última solicitação ocorreu há mais de 20 minutos
    if diferenca_minutos > 20:
        tentativas = 1
        dt_primeira = agora
    else:
        tentativas += 1

    quarentena_ate = None
    msg_alerta = ""

    # Aplicação do Escalonamento (5 min na 3ª tentativa em <5min; 20 min nas seguintes)
    if tentativas == 3 and diferenca_minutos <= 5:
        quarentena_ate = agora + datetime.timedelta(minutes=5)
        msg_alerta = "⚠️ Limite atingido! Sua conta entrou em quarentena por 5 minutos."
    elif tentativas > 3:
        quarentena_ate = agora + datetime.timedelta(minutes=20)
        msg_alerta = "⛔ Tentativas excessivas! Sua conta entrou em quarentena de 20 minutos."

    dados_upd = {
        "cnt_solicitacoes_reset": tentativas,
        "primeira_solicitacao_reset": dt_primeira.isoformat(),
        "quarentena_ate": quarentena_ate.isoformat() if quarentena_ate else None
    }

    salvar_usuario_universal_supabase(usuario_login, dados_upd)
    return True, msg_alerta

# =========================================================================
# ✉️ MENSAGERIA E BANCO DE DADOS
# =========================================================================

def enviar_whatsapp_api_real(numero: str, pin: str) -> bool:
    """Envia a mensagem de PIN de contingência via API externa de WhatsApp."""
    cfg_wa = st.secrets.get("whatsapp", {})
    api_url = cfg_wa.get("api_url") or st.secrets.get("WHATSAPP_API_URL")
    token = cfg_wa.get("api_token")

    if not api_url:
        return False

    try:
        num_limpo = "".join([c for c in str(numero) if c.isdigit()])
        if not num_limpo.startswith("55"):
            num_limpo = f"55{num_limpo}"

        payload = {
            "number": num_limpo,
            "textMessage": {"text": f"🛡️ *SIOP - PMMG*\n\nSeu código de verificação é: *{pin}*\n\nEste código é de uso pessoal e expira em breve."}
        }
        headers = {"Content-Type": "application/json"}
        if token:
            headers["apikey"] = token

        resp = requests.post(api_url, json=payload, headers=headers, timeout=5)
        return resp.status_code in [200, 201]
    except Exception:
        return False

def enviar_email_real(destino_email: str, assunto: str, corpo_html: str) -> bool:
    """
    Envia e-mails reais via servidor SMTP do Gmail/Google Workspace usando
    as credenciais cadastradas no .streamlit/secrets.toml.
    """
    try:
        cfg_email = st.secrets.get("email", {})
        servidor_smtp = cfg_email.get("smtp_server", "smtp.gmail.com")
        porta = int(cfg_email.get("smtp_port", 587))
        remetente = cfg_email.get("email_remetente")
        senha = cfg_email.get("email_senha")

        if not remetente or not senha:
            st.error("⚠️ Configurações de e-mail não encontradas no arquivo secrets.toml.")
            return False

        msg = MIMEMultipart()
        msg['From'] = f"SIOP - PMMG <{remetente}>"
        msg['To'] = destino_email
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo_html, 'html'))

        server = smtplib.SMTP(servidor_smtp, porta)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erro ao disparar e-mail: {e}")
        return False

def salvar_usuario_universal_supabase(usuario_login: str, dados_atualizacao: dict) -> bool:
    """Atualiza dados do usuário no Supabase sem amarras rígidas."""
    if not supabase:
        return False
    try:
        pm_limpo = str(usuario_login).strip().replace("-", "").replace(".", "").lower()
        res = supabase.table("usuarios").select("id").or_(f"usuario_login.eq.{pm_limpo},usuario.eq.{pm_limpo}").execute()
        
        if res.data and len(res.data) > 0:
            user_id = res.data[0]["id"]
            supabase.table("usuarios").update(dados_atualizacao).eq("id", user_id).execute()
            return True
        return False
    except Exception as ex:
        print(f"Erro de atualização no Supabase: {ex}")
        return False

def bloquear_usuario_supabase(usuario_login: str) -> bool:
    """Aplica o bloqueio de conta no banco."""
    return salvar_usuario_universal_supabase(usuario_login, {"ativo": False})

def registrar_log_login(usuario_login: str):
    """Registra evento de acesso com sucesso."""
    if supabase:
        try:
            supabase.table("historico_logins").insert({"usuario_login": usuario_login}).execute()
        except Exception:
            pass

def inicializar_estado_sessao():
    """Inicializa variáveis globais da aplicação."""
    defaults = {
        "autenticado": False,
        "usuario_dados": None,
        "etapa_login": "CREDENCIAIS",
        "login_temp_dados": None,
        "token_sessao_dispositivo": None,
        "pin_recuperacao_temp": None,
        "pin_2fa_canal_temp": None,
        "modulo_ativo": "ESCALAS",
        "tema_visual": "DARK"
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

def verificar_validade_sessao():
    """Valida expiração da sessão ativa."""
    pass