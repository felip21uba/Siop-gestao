"""
==============================================================================
Módulo de Armazenamento e Gestão de Mídias/Documentos TCO (modules/tco/storage.py)
Gerencia uploads, remoções e links públicos no Supabase Storage (bucket 'midias_tco').
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
    Realiza o upload direto para o Supabase Storage no bucket 'midias_tco'
    e vincula os metadados no array JSONB 'midias_anexas' do material em 'tco_materiais'.
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

        # 1. Upload do arquivo binário para o bucket 'midias_tco'
        supabase.storage.from_(BUCKET_NAME).upload(
            path=caminho_storage,
            file=file_bytes,
            file_options={"content-type": file_type or "application/octet-stream", "upsert": "true"}
        )

        # 2. Obtenção da URL pública
        url_publica = supabase.storage.from_(BUCKET_NAME).get_public_url(caminho_storage)

        novo_anexo = {
            "nome_arquivo": nome_limpo,
            "caminho_storage": caminho_storage,
            "url_publica": url_publica,
            "tipo_mime": file_type,
            "tamanho_bytes": len(file_bytes),
            "data_upload": datetime.datetime.now().isoformat()
        }

        # 3. Atualização na coluna jsonb 'midias_anexas' do material se id_bem informado
        if id_bem:
            res_bem = supabase.table("tco_materiais").select("midias_anexas").eq("id_bem", str(id_bem)).execute()
            midias_existentes = []
            if res_bem and res_bem.data:
                midias_existentes = res_bem.data[0].get("midias_anexas") or []
                if not isinstance(midias_existentes, list):
                    midias_existentes = []

            midias_existentes.append(novo_anexo)

            supabase.table("tco_materiais").update({"midias_anexas": midias_existentes}).eq("id_bem", str(id_bem)).execute()

        return novo_anexo

    except Exception as e:
        st.error(f"Erro ao realizar upload da mídia no Supabase Storage: {e}")
        return None


def upload_oficio_pdf_supabase(file_bytes: bytes, file_name: str, num_reds: str) -> str:
    """
    Realiza o upload de PDFs de ofícios gerados para o bucket e retorna a URL pública.
    """
    if not supabase:
        st.error("❌ Conexão com o Supabase não disponível.")
        return None

    try:
        nome_limpo = sanitizar_nome_arquivo(file_name)
        if not nome_limpo.endswith(".pdf"):
            nome_limpo += ".pdf"

        reds_sanitizado = str(num_reds).replace("/", "_").replace("-", "_").strip()
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_storage = f"oficios/{reds_sanitizado}/{timestamp_str}_{nome_limpo}"

        supabase.storage.from_(BUCKET_NAME).upload(
            path=caminho_storage,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )

        return supabase.storage.from_(BUCKET_NAME).get_public_url(caminho_storage)
    except Exception as e:
        st.error(f"Erro ao realizar upload do ofício PDF: {e}")
        return None


def deletar_arquivo_storage_supabase(caminho_storage: str) -> bool:
    """
    Remove um arquivo do bucket no Supabase Storage.
    """
    if not supabase or not caminho_storage:
        return False

    try:
        supabase.storage.from_(BUCKET_NAME).remove([caminho_storage])
        return True
    except Exception as e:
        st.error(f"Erro ao deletar arquivo do storage: {e}")
        return False


def listar_midias_reds_supabase(num_reds: str) -> list:
    """
    Lista todas as mídias vinculadas aos materiais de um determinado REDS.
    """
    if not supabase or not num_reds:
        return []

    try:
        res = supabase.table("tco_materiais").select("midias_anexas").eq("num_reds", str(num_reds)).execute()
        todas_midias = []
        if res and res.data:
            for item in res.data:
                anexos = item.get("midias_anexas") or []
                if isinstance(anexos, list):
                    todas_midias.extend(anexos)
        return todas_midias
    except Exception as e:
        print(f"Aviso ao consultar mídias do REDS {num_reds}: {e}")
        return []


def excluir_midia_supabase(id_bem: str, caminho_storage: str) -> bool:
    """
    Exclui a mídia física do bucket e atualiza o JSONB na tabela 'tco_materiais'.
    """
    if not supabase or not id_bem:
        return False

    try:
        if caminho_storage:
            supabase.storage.from_(BUCKET_NAME).remove([caminho_storage])

        res_bem = supabase.table("tco_materiais").select("midias_anexas").eq("id_bem", str(id_bem)).execute()
        if res_bem and res_bem.data:
            anexos = res_bem.data[0].get("midias_anexas") or []
            if isinstance(anexos, list):
                novos_anexos = [a for a in anexos if a.get("caminho_storage") != caminho_storage]
                supabase.table("tco_materiais").update({"midias_anexas": novos_anexos}).eq("id_bem", str(id_bem)).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir mídia: {e}")
        return False