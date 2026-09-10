import streamlit as st
import hashlib
from core.database import supabase

BUCKET_NAME = "tco_midias"

def gerar_hash_sha256(file_bytes):
    """Gera a assinatura digital SHA-256 do arquivo para a Cadeia de Custódia (Art. 158-A do CPP)."""
    if not file_bytes:
        return None
    return hashlib.sha256(file_bytes).hexdigest()

def upload_midia_supabase(file_bytes, file_name, file_type, num_reds, id_bem):
    """Faz o upload físico do arquivo para o bucket tco_midias no Supabase Storage."""
    if not supabase or not file_bytes:
        return None
    
    try:
        nome_limpo = file_name.replace(" ", "_").replace("/", "_")
        path_on_supa = f"{num_reds}/{id_bem}/{nome_limpo}"
        
        supabase.storage.from_(BUCKET_NAME).upload(
            path=path_on_supa,
            file=file_bytes,
            file_options={"content-type": file_type, "upsert": "true"}
        )
        
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(path_on_supa)
        hash_sha256 = gerar_hash_sha256(file_bytes)
        
        return {
            "caminho_storage": path_on_supa,
            "url_publica": public_url,
            "nome_arquivo": file_name,
            "tipo": file_type,
            "tamanho_bytes": len(file_bytes),
            "hash_sha256": hash_sha256
        }
    except Exception as e:
        st.error(f"Erro ao enviar arquivo para o Supabase Storage: {e}")
        return None