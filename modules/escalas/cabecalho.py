"""
==============================================================================
Módulo de Cabeçalho Institucional PMMG - Escalas (modules/escalas/cabecalho.py)
Design tático idêntico ao padrão oficial do TCO (gradiente caqui/dourado)
com relógio dinâmico em tempo real rodando segundo a segundo.
==============================================================================
"""

import datetime
from zoneinfo import ZoneInfo
import streamlit as st
import streamlit.components.v1 as components

FUSO_BR = ZoneInfo("America/Sao_Paulo")

def formatar_matricula_pm(mat: str) -> str:
    """Formata a matrícula funcional de 7 dígitos para o padrão PM (Ex: 1337468 -> 133.746-8)."""
    mat_limpa = "".join(filter(str.isalnum, str(mat)))
    if len(mat_limpa) == 7:
        return f"{mat_limpa[:3]}.{mat_limpa[3:6]}-{mat_limpa[6]}"
    return str(mat)

def renderizar_cabecalho_escalas(unidade_lotacao="21º BPM", subunidade_lotacao="35ª CIA PM", titulo_modulo="Gestão de Escalas & Planejamento Operacional"):
    """
    Renderiza o cabeçalho tático corporativo em HTML/CSS com relógio vivo em tempo real.
    """
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    posto_grad = str(usr_dados.get("cargo_funcao") or usr_dados.get("posto_grad") or "CAP PM").strip().upper()
    nome_guerra = str(usr_dados.get("nome_guerra") or usr_dados.get("nome_completo") or "PEREIRA").strip().upper()

    if posto_grad and not nome_guerra.startswith(posto_grad):
        militar_completo = f"{posto_grad} {nome_guerra}"
    else:
        militar_completo = nome_guerra

    mat_raw = str(
        usr_dados.get("num_policia")
        or usr_dados.get("usuario_login")
        or usr_dados.get("usuario")
        or "1337468"
    ).strip()
    matricula_fmt = formatar_matricula_pm(mat_raw)

    unidade_atual = str(st.session_state.get("cfg_unidade") or unidade_lotacao or "21º BPM").strip().upper()
    subunidade_atual = str(st.session_state.get("cfg_subunidade") or subunidade_lotacao or "35ª CIA PM").strip().upper()

    if "21" in unidade_atual and "UBÁ" not in unidade_atual and "UBA" not in unidade_atual:
        tag_local = f"{subunidade_atual} / P3/EM/{unidade_atual}/4 RPM (Ubá-MG)"
    else:
        tag_local = f"{subunidade_atual} / P3/EM/{unidade_atual}/4 RPM"

    html_cabecalho_escalas = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: transparent;
            }}
            .banner-container {{
                background: linear-gradient(135deg, #7d6539 0%, #63502c 100%);
                border: 2px solid #c5a059;