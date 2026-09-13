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
def upload_oficio_pdf_supabase(pdf_bytes, num_oficio, num_reds):
    """Envia o arquivo PDF do Ofício expedido para o Supabase Storage (Bucket: midias_tco)."""
    if not supabase or not pdf_bytes:
        return None

    try:
        nome_limpo = str(num_oficio).replace('/', '_').replace(' ', '_').strip().upper()
        time_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_arquivo = f"oficios/{time_stamp}_{nome_limpo}.pdf"

        # Upload no bucket 'midias_tco'
        supabase.storage.from_("midias_tco").upload(
            path=caminho_arquivo,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf"}
        )

        url_publica = supabase.storage.from_("midias_tco").get_public_url(caminho_arquivo)

        return {
            "caminho_storage": caminho_arquivo,
            "url_publica": url_publica,
            "nome_arquivo": f"{nome_limpo}.pdf"
        }
    except Exception as e:
        st.warning(f"Aviso ao realizar backup do Ofício no Storage: {e}")
        return None

def deletar_arquivo_storage_supabase(caminho_storage):
    """Remove um arquivo físico do Supabase Storage."""
    if not supabase or not caminho_storage:
        return False
    try:
        supabase.storage.from_("midias_tco").remove([caminho_storage])
        return True
    except Exception:
        return False