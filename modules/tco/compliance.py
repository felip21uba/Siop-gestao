import io
import datetime
import hashlib
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from core.database import supabase

TEXTO_TERMO_COMPLIANCE = """
<b>TERMO DE COMPROMISSO, CONFIDENCIALIDADE E COMPLIANCE OPERACIONAL</b><br/>
<b>SISTEMA INTEGRADO DE OPERAÇÕES POLICIAIS (SIOP) — MÓDULO TCO & CUSTÓDIA DE MATERIAIS</b><br/><br/>

<b>1. DA CADEIA DE CUSTÓDIA (ART. 158-A AO 158-F DO CPP):</b><br/>
1.1. O operador compromete-se a assegurar a rastreabilidade e a inviolabilidade dos elementos probatórios apreendidos, utilizando obrigatoriamente o registro de invólucros/lacres oficiais.<br/>
1.2. Qualquer divergência observada na conferência física do material (violação de lacre, avaria ou diferença de quantidade) deve ser registrada na função de "Divergência/Recusa" do sistema.<br/><br/>

<b>2. DA RESPONSABILIDADE SOBRE DADOS E LGPD (LEI Nº 13.709/2018):</b><br/>
2.1. Todas as informações de qualificação de civis, testemunhas, vítimas e infratores acessadas via REDS/TCO são estritamente confidenciais e de uso exclusivo para instrução de procedimentos oficiais.<br/>
2.2. É expressamente vedado o compartilhamento, extração não autorizada, captura de tela ou divulgação de dados sensíveis para finalidades alheias ao serviço policial militar.<br/><br/>

<b>3. DA IRRETRATABILIDADE E AUDITORIA DE AÇÕES:</b><br/>
3.1. O operador declara ciência de que edições de materiais, uploads de mídias, solicitações de tramitação, aceite e rejeição de custódia são gravados com chancela SHA-256 na trilha imutável de auditoria.<br/>
3.2. As alterações manuais de dados importados do REDS exigem justificativa fundamentada, sujeita à fiscalização da Seção de P1/CREDS e Corregedoria.<br/><br/>

<b>4. DO USO DE CREDENCIAIS PESSOAIS:</b><br/>
4.1. A senha e as chaves de acesso ao SIOP são pessoais e intransferíveis. O militar responde administrativa, civil e penalmente por todos os atos praticados sob sua autenticação.
"""

def verificar_aceite_compliance_supabase(usuario_id):
    """Verifica se o usuário já aceitou o termo de compliance no banco de dados."""
    if not supabase or not usuario_id:
        return True
    try:
        res = supabase.table("tco_compliance_aceites").select("*").eq("usuario_id", usuario_id).execute()
        return len(res.data) > 0 if res.data else False
    except Exception:
        return False

def registrar_aceite_compliance_supabase(usuario_id, nome_militar, cargo_funcao, unidade):
    """Grava a aceitação única do militar no Supabase."""
    if not supabase or not usuario_id:
        return False
    try:
        now_iso = datetime.datetime.now().isoformat()
        dados_aceite = {
            "usuario_id": usuario_id,
            "nome_militar": nome_militar,
            "cargo_funcao": cargo_funcao,
            "unidade": unidade,
            "data_aceite": now_iso,
            "versao_termo": "1.0 - 2026"
        }
        
        supabase.table("tco_compliance_aceites").insert(dados_aceite).execute()
        
        supabase.table("tco_logs").insert({
            "data_hora": now_iso,
            "num_reds": "COMPLIANCE-SISTEMA",
            "bem_id": "ACEITE-TERMO",
            "acao": "ACEITE DO TERMO DE COMPLIANCE TCO/CREDS",
            "origem": nome_militar,
            "unidade_origem": unidade,
            "destino": "SIOP COMPLIANCE",
            "unidade_destino": unidade,
            "detalhe": f"Militar {nome_militar} ({cargo_funcao}) confirmou leitura e aceite do Termo de Compliance v1.0."
        }).execute()
        
        return True
    except Exception as e:
        return False

def gerar_pdf_termo_compliance(nome_militar, cargo_funcao, unidade, usuario_id, data_aceite_str):
    """Gera o arquivo PDF imprimível do Termo de Compliance assinado pelo operador."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    style_header = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        alignment=1,
        textColor=colors.HexColor('#1E293B')
    )
    
    style_body = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        alignment=4,
        textColor=colors.HexColor('#334155')
    )

    elements = []

    header_text = "<b>POLÍCIA MILITAR DE MINAS GERAIS</b><br/>" \
                  f"<b>{unidade.upper()}</b><br/>" \
                  "<b>DECLARAÇÃO DE CUMPRIÇÃO E COMPLIANCE OPERACIONAL (TCO/CREDS)</b>"
    elements.append(Paragraph(header_text, style_header))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceAfter=15))

    meta_text = f"<b>OPERADOR:</b> {cargo_funcao} {nome_militar}<br/>" \
                f"<b>IDENTIFICAÇÃO / POLÍCIA:</b> {usuario_id}<br/>" \
                f"<b>UNIDADE:</b> {unidade}<br/>" \
                f"<b>DATA DE ACEITE ELETRÔNICO:</b> {data_aceite_str}"
    elements.append(Paragraph(meta_text, style_body))
    elements.append(Spacer(1, 15))

    elements.append(Paragraph(TEXTO_TERMO_COMPLIANCE, style_body))
    elements.append(Spacer(1, 30))

    ass_text = f"____________________________________________________<br/>" \
               f"<b>{nome_militar.upper()}</b><br/>" \
               f"{cargo_funcao} - {unidade}<br/>" \
               f"Assinado Eletronicamente via SIOP"
    elements.append(Paragraph(ass_text, ParagraphStyle('AssStyle', parent=style_header, alignment=1)))
    elements.append(Spacer(1, 20))

    hash_comp = hashlib.sha256(f"{usuario_id}{nome_militar}{data_aceite_str}".encode('utf-8')).hexdigest()
    rodape_text = f"<b>CHANCELA DIGITAL DE COMPLIANCE:</b> SHA-256: {hash_comp}<br/>" \
                  "Documento impresso via Sistema SIOP para fins de auditoria e conformidade."
    
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1'), spaceBefore=10, spaceAfter=8))
    elements.append(Paragraph(rodape_text, ParagraphStyle('RodapeStyle', parent=styles['Normal'], fontSize=7, alignment=1)))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()