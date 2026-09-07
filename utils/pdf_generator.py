import io
import datetime
import pandas as pd

# IMPORTS DO REPORTLAB (PDF)
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# =========================================================================
# 1. GERADOR DO QUADRO GERAL DE ESCALA DE SERVIÇO DE CAMPO (PDF)
# =========================================================================
def gerar_pdf_pmmg_oficial(unidade, subunidade, mes_ano, militares, equipes, ajustes_mapa, horas_dia, meta_h, resp_txt, homolog_txt, homolog_funcao):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
    elements = []
    styles = getSampleStyleSheet()

    style_titulo = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, alignment=1, textColor=colors.HexColor('#0F172A'))
    style_sub = ParagraphStyle('SubStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=1, textColor=colors.HexColor('#475569'))
    style_th = ParagraphStyle('THStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7, alignment=1, textColor=colors.HexColor('#0F172A'))
    style_militar = ParagraphStyle('MilStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7, alignment=0, textColor=colors.HexColor('#0F172A'))
    style_celula = ParagraphStyle('CelStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=6.5, alignment=1, textColor=colors.HexColor('#1E293B'))
    style_eq = ParagraphStyle('EqStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, alignment=1, textColor=colors.white)

    elements.append(Paragraph(f"<b>{unidade}</b>", style_titulo))
    elements.append(Paragraph(f"{subunidade}", style_sub))
    elements.append(Paragraph(f"QUADRO GERAL DE ESCALA DE SERVIÇO - {mes_ano.upper()}", style_sub))
    elements.append(Spacer(1, 8))

    num_dias = max([int(k.split('_')[1]) for k in ajustes_mapa.keys() if '_' in k] or [30])
    
    table_data = []
    row_h = [Paragraph("<b>EQUIPE</b>", style_th), Paragraph("<b>MILITAR</b>", style_th)]
    for d in range(1, num_dias + 1):
        row_h.append(Paragraph(f"<b>{d}</b>", style_th))
    row_h.append(Paragraph("<b>HORAS</b>", style_th))
    table_data.append(row_h)

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]

    linha_idx = 1
    for eq in equipes:
        militares_eq = [m for m in militares if m.get("equipe") == eq or eq == "ADMINISTRAÇÃO"]
        qtd_m = len(militares_eq)

        if qtd_m > 0:
            linha_inicio_eq = linha_idx
            cor_bg_eq = colors.HexColor('#1E293B') if ("RP" in eq or "SUP" in eq) else colors.HexColor('#B45309')

            for m in militares_eq:
                row_m = [
                    Paragraph(f"<b>{eq}</b>", style_eq),
                    Paragraph(f"<b>{m['posto_grad']} {m['nome_guerra']}</b><br/>{m.get('num_policia','N/I')}", style_militar)
                ]
                dias_trab = 0

                for d in range(1, num_dias + 1):
                    val = ajustes_mapa.get(f"{m['id']}_{d}", "FOLGA")
                    if val in ["07H AS 19H", "19H AS 07H", "08H AS 17H", "18H AS 00H"]:
                        row_m.append(Paragraph(f"<b>{val}</b>", style_celula))
                        dias_trab += 1
                    elif val == "NEUTRO":
                        row_m.append(Paragraph("NEUTRO", style_celula))
                    elif val == "PERMUTA":
                        row_m.append(Paragraph("<b>PERM.</b>", style_celula))
                    else:
                        row_m.append(Paragraph("", style_celula))

                tot_h = round(dias_trab * horas_dia, 1)
                saldo = round(tot_h - meta_h, 1)
                row_m.append(Paragraph(f"<b>{tot_h}h</b><br/>({saldo:+.1f}h)", style_celula))

                table_data.append(row_m)
                linha_idx += 1

            linha_fim_eq = linha_idx - 1
            table_styles.append(('SPAN', (0, linha_inicio_eq), (0, linha_fim_eq)))
            table_styles.append(('BACKGROUND', (0, linha_inicio_eq), (0, linha_fim_eq), cor_bg_eq))

    col_widths = [55, 95] + [18] * num_dias + [45]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(table_styles))
    elements.append(t)
    elements.append(Spacer(1, 20))

    ass_data = [
        [
            Paragraph(f"Elaborado por:<br/><br/><br/>____________________________________<br/><b>{resp_txt}</b>", style_sub),
            Paragraph(f"Homologado por:<br/><br/><br/>____________________________________<br/><b>{homolog_txt}</b><br/>{homolog_funcao}", style_sub)
        ]
    ]
    t_ass = Table(ass_data, colWidths=[350, 350])
    t_ass.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_ass)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# =========================================================================
# 2. GERADOR DA PARTE INFORMATIVA E PLANO DE COMPLIANCE (PDF E TXT)
# =========================================================================
def gerar_pdf_parte_informativa(num_parte="12.4/2026", responsavel_nome="FELIPE OLIVEIRA ALVES", responsavel_posto="CAP QOPM") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()

    style_header = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, alignment=1, leading=14)
    style_title = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, alignment=1, spaceAfter=15)
    style_meta = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, spaceAfter=10)
    style_body = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, alignment=4, spaceAfter=8)
    style_item = ParagraphStyle('ItemStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=13, leftIndent=15, spaceAfter=4)
    style_ass = ParagraphStyle('AssStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, alignment=1, spaceBefore=30)

    elements.append(Paragraph("<b>POLÍCIA MILITAR DE MINAS GERAIS</b><br/>21º BATALHÃO DE POLÍCIA MILITAR", style_header))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph(f"<b>PARTE INFORMATIVA Nº {num_parte} – 35ª CIA PM</b>", style_title))

    data_hoje = datetime.date.today().strftime("%d de %B de %Y")
    elements.append(Paragraph(f"<b>Do:</b> {responsavel_posto} {responsavel_nome}<br/><b>Ao:</b> Senhor Comandante do 21º BPM<br/><b>Assunto:</b> Apresentação do Plano de Segurança e Compliance do SIOP<br/><b>Data:</b> {data_hoje}", style_meta))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("1. Respeitosamente, venho perante Vossa Senhoria apresentar o <b>Plano de Segurança da Informação, Controle de Acesso e Compliance</b> do <b>Sistema Integrado de Operações (SIOP)</b>, desenvolvido no âmbito da 35ª Cia PM para a gestão de escalas de serviço, efetivo e rotinas operacionais.", style_body))
    elements.append(Paragraph("2. A referida aplicação foi concebida sob os princípios da <i>Segurança por Design</i> e <i>Privacidade por Padrão</i>, visando garantir a integridade, disponibilidade e confidencialidade dos dados do efetivo policial militar.", style_body))
    elements.append(Paragraph("3. Diante disso, levo ao conhecimento de Vossa Senhoria a síntese dos protocolos de proteção técnicos e operacionais homologados:", style_body))

    elements.append(Paragraph("<b>a. Autenticação e Controle de Acesso (RBAC):</b> Login por Nº de Polícia, validação de senhas fortes com histórico e 7 níveis de permissão isolados.", style_item))
    elements.append(Paragraph("<b>b. Autenticação em Dois Fatores (2FA/TOTP):</b> Integração com Google Authenticator/Authy, trava de dispositivo único e timeout por inatividade de 30 minutos.", style_item))
    elements.append(Paragraph("<b>c. Audit Log e Rastreabilidade:</b> Registro imutável de ações de comando (operador, alvo, data/hora UTC e IP de origem) com autoatendimento seguro.", style_item))
    elements.append(Paragraph("<b>d. Proteção de Banco de Dados:</b> Criptografia HTTPS/TLS em trânsito e políticas de Row Level Security (RLS) no PostgreSQL/Supabase.", style_item))

    elements.append(Paragraph("4. Por fim, informo que o sistema encontra-se munido de plano de contingência para exportação do Quadro Geral em formatos .PDF e .XLSX.", style_body))
    elements.append(Paragraph("5. Respeitosamente, submeto o presente documento à apreciação de Vossa Senhoria para fins de ciência e arquivamento.", style_body))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"__________________________________________<br/><b>{responsavel_nome}, {responsavel_posto}</b><br/>Programador / Gestor do SIOP", style_ass))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def gerar_txt_parte_informativa(num_parte="12.4/2026", responsavel_nome="FELIPE OLIVEIRA ALVES", responsavel_posto="CAP QOPM") -> bytes:
    texto = f"""POLÍCIA MILITAR DE MINAS GERAIS
21º BATALHÃO DE POLÍCIA MILITAR – 35ª CIA PM

PARTE INFORMATIVA Nº {num_parte} – 35ª CIA PM

Do: {responsavel_posto} {responsavel_nome}
Ao: Senhor Comandante do 21º BPM
Assunto: Apresentação do Plano de Segurança, Compliance e Protocolos de Proteção de Dados da Aplicação SIOP
Data: {datetime.date.today().strftime("%d de %B de %Y")}

1. Respeitosamente, venho perante Vossa Senhoria apresentar o Plano de Segurança da Informação, Controle de Acesso e Compliance do Sistema Integrado de Operações (SIOP), desenvolvido no âmbito da 35ª Cia PM para a gestão de escalas de serviço, efetivo e rotinas operacionais.

2. A referida aplicação foi concebida sob os princípios da Segurança por Design (Security by Design) e Privacidade por Padrão (Privacy by Default), visando garantir a integridade, disponibilidade e confidencialidade dos dados do efetivo policial militar.

3. Diante disso, levo ao conhecimento de Vossa Senhoria a síntese dos protocolos de proteção técnicos e operacionais que foram devidamente homologados e implementados na aplicação:

   a. Autenticação e Controle de Acesso por Função (RBAC):
   - Identificação Única via Número de Polícia;
   - Política de Senhas Fortes com complexidade mínima e restrição de reutilização;
   - Escopo de permissão em 7 níveis funcionais.

   b. Autenticação em Dois Fatores (2FA/TOTP) e Sessão Única:
   - Duplo fator via Google Authenticator / Authy;
   - Trava de Dispositivo Único (Single Device Enforcement);
   - Timeout automático por inatividade de 30 minutos.

   c. Rastreabilidade, Auditabilidade e Integridade:
   - Audit Log imutável gravando operador, alvo e data/hora UTC;
   - Self-service autônomo para recuperação de credenciais via PIN temporal.

   d. Proteção e Segurança de Banco de Dados:
   - Criptografia em trânsito (HTTPS/TLS);
   - Row Level Security (RLS) no PostgreSQL/Supabase contra SQL Injection.

4. Por fim, informo que o sistema encontra-se munido de plano de contingência para exportação física e digital do Quadro Geral em formatos .PDF e .XLSX.

5. Respeitosamente, submeto o presente documento à apreciação de Vossa Senhoria para fins de ciência e arquivamento junto à Seção de Planejamento e P/1.


__________________________________________
{responsavel_nome}, {responsavel_posto}
Programador / Gestor do SIOP
"""
    return texto.encode("utf-8")