import datetime
import unicodedata
import re
import streamlit as st
from core.database import supabase

def remover_acentos_e_caracteres_especiais(texto):
    """Remove acentos, ç e caracteres especiais mantendo apenas caracteres ASCII seguros para URLs/S3."""
    texto_sem_acento = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
    texto_limpo = re.sub(r'[^a-zA-Z0-9_\-]', '_', texto_sem_acento)
    texto_limpo = re.sub(r'_+', '_', texto_limpo).strip('_')
    return texto_limpo.upper()

def garantir_bucket_midias_tco():
    """Verifica se o bucket 'midias_tco' existe no Supabase. Se não existir, cria automaticamente."""
    if not supabase:
        return
    try:
        supabase.storage.get_bucket("midias_tco")
    except Exception:
        try:
            supabase.storage.create_bucket("midias_tco", options={"public": True})
        except Exception:
            pass

def upload_midia_supabase(file_bytes, file_name, file_type, num_reds, id_bem):
    """Realiza o upload de mídias/fotos do material para o Supabase Storage."""
    if not supabase or not file_bytes:
        return None
    try:
        garantir_bucket_midias_tco()
        reds_limpo = remover_acentos_e_caracteres_especiais(num_reds)
        bem_limpo = remover_acentos_e_caracteres_especiais(id_bem)
        nome_limpo = remover_acentos_e_caracteres_especiais(file_name)
        
        caminho_arquivo = f"mids_{reds_limpo}/{bem_limpo}_{nome_limpo}"
        supabase.storage.from_("midias_tco").upload(
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
        garantir_bucket_midias_tco()
        nome_limpo = remover_acentos_e_caracteres_especiais(num_oficio)
        time_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_arquivo = f"oficios/{time_stamp}_{nome_limpo}.pdf"

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