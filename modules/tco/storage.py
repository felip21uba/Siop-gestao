import datetime
import streamlit as st
from core.database import supabase

def upload_midia_supabase(file_bytes, file_name, file_type, num_reds, id_bem):
    """Realiza o upload de mídias/fotos do material para o Supabase Storage."""
    if not supabase or not file_bytes:
        return None
    try:
        caminho_arquivo = f"mids_{num_reds}/{id_bem}_{file_name}"
        res = supabase.storage.from_("midias_tco").upload(
            path=caminho_arquivo,
            file=file_bytes,
            file_options={"content-type": file_type}
        )
        url_publica = supabase.storage.from_("midias_tco").get_public_url(caminho_arquivo)
        return {
            "caminho_storage": caminho_arquivo,
            "url_publica": url_publica,
            "nome_arquivo": file_name
        }
    except Exception as e:
        st.warning(f"Aviso ao realizar upload de mídia: {e}")
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