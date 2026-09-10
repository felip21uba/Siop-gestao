import html
import re
import os

def sanitizar_texto(texto: str) -> str:
    """Limpa e escapa caracteres perigosos em textos recebidos da interface (Prevenção de XSS e SQLi)."""
    if not texto:
        return ""
    
    # Converte caracteres especiais HTML (<, >, &, ", ')
    texto_limpo = html.escape(str(texto).strip())
    
    # Remove tentativas de injeção de scripts e links maliciosos
    texto_limpo = re.sub(r'(?i)<script.*?>.*?</script>', '', texto_limpo)
    texto_limpo = re.sub(r'(?i)javascript:', '', texto_limpo)
    texto_limpo = re.sub(r'(?i)onerror\s*=', '', texto_limpo)
    
    return texto_limpo

def validar_arquivo_upload(arquivo_upload, extensoes_permitidas=['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx'], max_mb=5.0):
    """Bloqueia o upload de arquivos executáveis disfarçados (ex: .exe, .sh, .py, .php, .js)."""
    if arquivo_upload is None:
        return False, "Nenhum arquivo anexado."
        
    nome_arquivo = arquivo_upload.name
    extensao = os.path.splitext(nome_arquivo)[1].lower()
    
    # 1. Trava contra formatos maliciosos
    if extensao not in extensoes_permitidas:
        return False, f"Formato de arquivo não permitido ({extensao}). Use apenas: {', '.join(extensoes_permitidas)}."
        
    # 2. Trava contra arquivos gigantes que podem travar o servidor (DDoS)
    tamanho_mb = arquivo_upload.size / (1024 * 1024)
    if tamanho_mb > max_mb:
        return False, f"O arquivo possui {tamanho_mb:.1f}MB, o que ultrapassa o limite de {max_mb}MB."
        
    return True, "Arquivo seguro."