import hashlib
from supabase import create_client, Client

SUPABASE_URL = "https://gfoepzhjyhzxpllyrlce.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdmb2VwemhqeWh6eHBsbHlybGNlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzY3NTY4MywiZXhwIjoyMTAzMjUxNjgzfQ.a7AgtARrVWq69vhWr3XySOttuUTtfF3uLVZ4ndpPr8g"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def resetar_usuario():
    login_usuario = "1337468"
    senha_texto = "Pmmg@2026"
    senha_hash_gerada = hashlib.sha256(senha_texto.encode('utf-8')).hexdigest()
    
    print(f"🔄 Atualizando o usuário {login_usuario} no Supabase...")
    
    dados_atualizacao = {
        "senha": senha_texto,            # Texto puro exigido na linha 411 do app.py
        "senha_hash": senha_hash_gerada, # Hash exigida pelos módulos core/auth
        "ativo": True,
        "mfa_habilitado": False,
        "mfa_secret": None,
        "tentativas_erradas": 0,
        "primeiro_acesso": False
    }
    
    try:
        res = supabase.table("usuarios").update(dados_atualizacao).eq("usuario_login", login_usuario).execute()
        
        if res.data:
            print("✅ SUCESSO! Banco de dados atualizado com compatibilidade dupla.")
            print(f"👤 Login: {login_usuario}")
            print(f"🔑 Senha Texto Puro: {senha_texto}")
            print(f"🔒 Senha Hash: {senha_hash_gerada}")
        else:
            print(f"⚠️ Usuário '{login_usuario}' não localizado.")
            
    except Exception as e:
        print(f"❌ ERRO no Supabase: {e}")

if __name__ == "__main__":
    resetar_usuario()