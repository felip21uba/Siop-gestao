import os
import io
import re
from PIL import Image
import pandas as pd

# Limites de tamanho de arquivo (Bytes)
LIMITE_PLANILHA_BYTES = 5 * 1024 * 1024   # 5 MB
LIMITE_PDF_BYTES = 15 * 1024 * 1024       # 15 MB
LIMITE_IMAGEM_BYTES = 10 * 1024 * 1024    # 10 MB

def sanitizar_nome_arquivo(nome_original: str) -> str:
    """Evita ataques de Directory Traversal removendo rotas e caracteres especiais."""
    nome_limpo = os.path.basename(nome_original)
    nome_limpo = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', nome_limpo)
    return nome_limpo

def desarmar_csv_injection(df: pd.DataFrame) -> pd.DataFrame:
    """
    Desarma Formulas Injections no Excel/CSV (ex: células começando com =, +, -, @, \t que executam comandos no SO).
    """
    def neutralizar(val):
        if isinstance(val, str) and val.startswith(('=', '+', '-', '@', '\t', '\r')):
            return "'" + val  # Adiciona aspas simples para desarmar a fórmula
        return val

    return df.map(neutralizar) if hasattr(df, 'map') else df.applymap(neutralizar)

def validar_planilha_upload(arquivo) -> tuple[bool, str]:
    """Valida tamanho, extensão e assinatura binária (Magic Bytes) de planilhas."""
    if not arquivo:
        return False, "Nenhum arquivo enviado."

    if arquivo.size > LIMITE_PLANILHA_BYTES:
        return False, "❌ A planilha excede o limite máximo de 5 MB."

    extensao = os.path.splitext(arquivo.name)[1].lower()
    if extensao not in ['.xlsx', '.xls', '.csv']:
        return False, "❌ Extensão não permitida. Envie apenas arquivos .XLSX, .XLS ou .CSV."

    # Validação dos Magic Bytes (cabeçalho binário real do arquivo)
    header = arquivo.read(8)
    arquivo.seek(0)

    if extensao == '.xlsx' and not header.startswith(b'PK\x03\x04'):
        return False, "🚨 Arquivo .XLSX inválido ou com conteúdo mascarado."
    elif extensao == '.xls' and not header.startswith(b'\xd0\xcf\x11\xe0'):
        return False, "🚨 Arquivo .XLS inválido ou com conteúdo mascarado."

    return True, "Planilha válida."

def validar_pdf_upload(arquivo) -> tuple[bool, str]:
    """Valida tamanho e Magic Bytes (%PDF-) de arquivos PDF."""
    if not arquivo:
        return False, "Nenhum arquivo enviado."

    if arquivo.size > LIMITE_PDF_BYTES:
        return False, "❌ O PDF excede o limite máximo de 15 MB."

    extensao = os.path.splitext(arquivo.name)[1].lower()
    if extensao != '.pdf':
        return False, "❌ Extensão não permitida. Envie apenas documentos .PDF."

    header = arquivo.read(5)
    arquivo.seek(0)

    if not header.startswith(b'%PDF-'):
        return False, "🚨 O arquivo enviado não é um PDF válido."

    return True, "PDF válido."

def validar_imagem_upload(arquivo) -> tuple[bool, str]:
    """Valida imagens decodificando a estrutura via Pillow (evita scripts maliciosos embutidos)."""
    if not arquivo:
        return False, "Nenhum arquivo enviado."

    if arquivo.size > LIMITE_IMAGEM_BYTES:
        return False, "❌ A imagem excede o limite máximo de 10 MB."

    extensao = os.path.splitext(arquivo.name)[1].lower()
    if extensao not in ['.jpg', '.jpeg', '.png']:
        return False, "❌ Extensão não permitida. Use apenas JPG, JPEG ou PNG."

    try:
        bytes_img = arquivo.read()
        arquivo.seek(0)
        img = Image.open(io.BytesIO(bytes_img))
        img.verify()  # Tenta decodificar a imagem de ponta a ponta
    except Exception:
        return False, "🚨 O arquivo de imagem está corrompido ou contém payload malicioso."

    return True, "Imagem válida."