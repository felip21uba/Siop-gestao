"""
==============================================================================
Módulo de Validação e Sanitização de Arquivos (utils/file_validator.py)
Valida extensões, limites de tamanho, estruturas de planilhas e sanitiza
nomes de arquivos para o Supabase Storage e proteção contra CSV Injection.
==============================================================================
"""

import re
import unicodedata
import pandas as pd

TAMANHO_MAXIMO_MB = 15
EXTENSOES_PERMITIDAS_IMAGEM = ["jpg", "jpeg", "png", "webp"]
EXTENSOES_PERMITIDAS_PDF = ["pdf"]
EXTENSOES_PERMITIDAS_DOCX = ["docx"]
EXTENSOES_PERMITIDAS_PLANILHA = ["xlsx", "xls", "csv"]


def sanitizar_nome_arquivo(nome_original: str) -> str:
    """
    Remove acentos, espaços e caracteres especiais do nome do arquivo,
    garantindo compatibilidade total com as URLs do Supabase Storage.
    """
    if not nome_original:
        return "arquivo_anexo"

    partes = nome_original.rsplit(".", 1)
    nome_base = partes[0]
    extensao = partes[1].lower() if len(partes) > 1 else ""

    nome_nfkd = unicodedata.normalize("NFKD", nome_base)
    nome_sem_acento = "".join([c for c in nome_nfkd if not unicodedata.combining(c)])

    nome_limpo = re.sub(r"[^\w\s-]", "", nome_sem_acento).strip()
    nome_limpo = re.sub(r"[-\s]+", "_", nome_limpo)

    if not nome_limpo:
        nome_limpo = "arquivo_anexo"

    return f"{nome_limpo}.{extensao}" if extensao else nome_limpo


def desarmar_csv_injection(val):
    """
    Previne vulnerabilidade de Formula Injection em exportações Excel/CSV
    desarmando caracteres de controle (=, +, -, @, \t, \r).
    """
    if isinstance(val, str) and val.startswith(('=', '+', '-', '@', '\t', '\r')):
        return f"'{val}"
    return val


def validar_imagem_upload(file_obj) -> tuple[bool, str]:
    """Valida o tipo e o tamanho máximo de um arquivo de imagem."""
    if file_obj is None:
        return False, "Nenhum arquivo enviado."

    nome = file_obj.name.lower()
    ext = nome.split(".")[-1] if "." in nome else ""

    if ext not in EXTENSOES_PERMITIDAS_IMAGEM:
        return False, f"Formato inválido (.{ext}). Permitidos: {', '.join(EXTENSOES_PERMITIDAS_IMAGEM).upper()}."

    tamanho_mb = file_obj.size / (1024 * 1024)
    if tamanho_mb > TAMANHO_MAXIMO_MB:
        return False, f"Arquivo excede o limite de {TAMANHO_MAXIMO_MB} MB (Tamanho: {tamanho_mb:.1f} MB)."

    return True, "Arquivo válido."


def validar_pdf_upload(file_obj) -> tuple[bool, str]:
    """Valida o tipo e o tamanho máximo de um arquivo PDF."""
    if file_obj is None:
        return False, "Nenhum arquivo enviado."

    nome = file_obj.name.lower()
    ext = nome.split(".")[-1] if "." in nome else ""

    if ext not in EXTENSOES_PERMITIDAS_PDF:
        return False, f"Formato inválido (.{ext}). Somente arquivos PDF são permitidos."

    tamanho_mb = file_obj.size / (1024 * 1024)
    if tamanho_mb > TAMANHO_MAXIMO_MB:
        return False, f"Arquivo excede o limite de {TAMANHO_MAXIMO_MB} MB (Tamanho: {tamanho_mb:.1f} MB)."

    return True, "Arquivo válido."


def validar_planilha_upload(file_obj) -> tuple[bool, str]:
    """Valida o tipo e tamanho máximo de planilhas Excel/CSV enviadas no módulo de escalas."""
    if file_obj is None:
        return False, "Nenhum arquivo enviado."

    nome = file_obj.name.lower()
    ext = nome.split(".")[-1] if "." in nome else ""

    if ext not in EXTENSOES_PERMITIDAS_PLANILHA:
        return False, f"Formato inválido (.{ext}). Permitidos: {', '.join(EXTENSOES_PERMITIDAS_PLANILHA).upper()}."

    tamanho_mb = file_obj.size / (1024 * 1024)
    if tamanho_mb > TAMANHO_MAXIMO_MB:
        return False, f"Arquivo excede o limite de {TAMANHO_MAXIMO_MB} MB (Tamanho: {tamanho_mb:.1f} MB)."

    return True, "Arquivo válido."