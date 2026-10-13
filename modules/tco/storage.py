"""
==============================================================================
Módulo de Armazenamento e Gestão de Mídias/Documentos TCO (modules/tco/storage.py)
Gerencia uploads, remoções e links públicos no Supabase Storage (bucket 'midias_tco'),
garantindo a preservação estrita da extensão do arquivo para abertura direta no navegador.
==============================================================================
"""

import os
import mimetypes
import datetime
import streamlit as st
from core.database import supabase
from utils.file_validator import sanitizar_nome_arquivo

BUCKET_NAME = "midias_tco"


def extrair_extensao_arquivo(file_name: str, file_type: str = "") -> str:
    """
    Extrai e normaliza a extensão do arquivo a partir do nome ou do tipo MIME.
    Garante que a extensão sempre comece com ponto (ex: '.pdf', '.jpg').
    """
    if file_name and "." in file_name:
        ext = os.path.splitext(file_name)[1].lower()
        if ext and len(ext) <= 5:
            return ext

    if file_type:
        ext_mime = mimetypes.guess_extension(file_type)
        if ext_mime:
            if ext_mime == ".jpe":
                return ".jpg"
            return ext_mime.lower()

    return ".bin"


def upload_midia_supabase(file_bytes: bytes, file_name: str, file_type: str, num_reds: str, id_bem: str = None) -> dict:
    """
    Realiza o upload do arquivo para o Supabase Storage preservando a extensão original.
    Registra os metadados na tabela 'tco_midias'.
    """
    if not supabase:
        st.error("❌ Conexão com o Supabase não disponível.")
        return None

    try:
        nome_limpo = sanitizar_nome_arquivo(file_name)
        extensao = extrair_extensao_arquivo(nome_limpo, file_type)

        reds_sanitizado = str(num_reds).replace("/", "_").replace("-", "_").strip()
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        if id_bem:
            bem_str = str(id_bem).replace("/", "_").replace("-", "_").strip()
            caminho_storage = f"{reds_sanitizado}/bem_{bem_str}_{timestamp_str}{extensao}"
        else:
            caminho_storage = f"{reds_sanitizado}/doc_{timestamp_str}{extensao}"

        # Upload do arquivo físico para o bucket no Supabase Storage
        res_upload = supabase.storage.from_(BUCKET_NAME).upload(
            path=caminho_storage,
            file=file_bytes,
            file_options={"content-type": file_type or "application/octet-stream", "upsert": "true"}
        )

        # Obtenção da URL pública
        url_publica = supabase.storage.from_(BUCKET_NAME).get_public_url(caminho_storage)

        # Gravação do registro na tabela 'tco_midias'
        payload_midia = {
            "num_reds": num_reds,
            "id_bem": id_bem,
            "nome_arquivo": nome_limpo,
            "caminho_storage": caminho_storage,
            "url_publica": url_publica,
            "tipo_mime": file_type,
            "tamanho_bytes": len(file_bytes),
            "data_upload": datetime.datetime.now().isoformat()
        }

        res_db = supabase.table("tco_midias").insert(payload_midia).execute()

        if res_db and res_db.data:
            return res_db.data[0]
        return payload_midia

    except Exception as e:
        st.error(f"Erro ao realizar upload da mídia no Supabase Storage: {e}")
        return None


def listar_midias_reds_supabase(num_reds: str) -> list:
    """
    Lista todas as mídias e documentos vinculados a um determinado REDS.
    """
    if not supabase or not num_reds:
        return []

    try:
        res = supabase.table("tco_midias").select("*").eq("num_reds", str(num_reds)).order("data_upload", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"Aviso ao consultar mídias do REDS {num_reds}: {e}")
        return []


def excluir_midia_supabase(id_midia: str, caminho_storage: str) -> bool:
    """
    Exclui a mídia física do bucket e remove o registro da tabela 'tco_midias'.
    """
    if not supabase:
        return False

    try:
        # Exclui o arquivo do Storage
        if caminho_storage:
            supabase.storage.from_(BUCKET_NAME).remove([caminho_storage])

        # Exclui a linha do banco de dados
        supabase.table("tco_midias").delete().eq("id", id_midia).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir mídia: {e}")
        return False