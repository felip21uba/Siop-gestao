import pyotp
import hashlib
from core.database import supabase

def validar_codigo_authy(mfa_secret, codigo):
    """Valida o token do Authy/Google Authenticator com janela de tolerância."""
    if not mfa_secret or not codigo:
        return False
    try:
        codigo_limpo = str(codigo).replace(" ", "").strip()
        totp = pyotp.TOTP(mfa_secret)
        return totp.verify(codigo_limpo, valid_window=1)
    except Exception:
        return False

def validar_requisitos_senha(senha):
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

def validar_senha_forte(senha):
    """Alias exigido pelo modules/perfil.py e módulos de gestão."""
    return validar_requisitos_senha(senha)

def verificar_senha(senha_input, senha_db_texto, senha_db_hash):
    """Compara a senha digitada com Texto Puro e Hash SHA-256."""
    if not senha_input:
        return False
    senha_hash_input = hashlib.sha256(senha_input.encode('utf-8')).hexdigest()
    return (
        senha_input == senha_db_texto or
        senha_hash_input == senha_db_hash or
        senha_hash_input == senha_db_texto
    )

def buscar_usuario_para_login(usuario_input):
    """Consulta o registro do usuário pelas colunas usuario_login, usuario ou email_recuperacao."""
    if not supabase:
        return None
    try:
        res = supabase.table("usuarios").select("*").or_(
            f"usuario_login.eq.{usuario_input},usuario.eq.{usuario_input},email_recuperacao.eq.{usuario_input}"
        ).execute()
        if res and res.data:
            return res.data[0]
    except Exception:
        pass
    return None

def salvar_usuario_universal_supabase(dados_usuario: dict) -> bool:
    """Salva ou atualiza os dados de um usuário na tabela 'usuarios' do Supabase."""
    if not supabase or not dados_usuario:
        return False
    try:
        payload = dados_usuario.copy()
        if "senha" in payload and payload["senha"] and not payload.get("senha_hash"):
            payload["senha_hash"] = hashlib.sha256(str(payload["senha"]).encode('utf-8')).hexdigest()

        supabase.table("usuarios").upsert(payload).execute()
        return True
    except Exception as e:
        print(f"Erro ao salvar usuário no Supabase: {e}")
        return False