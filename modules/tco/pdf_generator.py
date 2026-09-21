import io
import datetime
import hashlib
import json
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from core.database import supabase
from modules.tco.database import registrar_log_supabase, atualizar_material_supabase
from modules.tco.storage import upload_oficio_pdf_supabase, deletar_arquivo_storage_supabase

def gerar_hash_oficio(conteudo_str):
    """Gera assinatura SHA-256 para o documento oficial."""
    return hashlib.sha256(str(conteudo_str).encode('utf-8')).hexdigest()

def criar_draw_qrcode(texto_qr):
    """Gera um elemento Drawing com QR Code para inserção no ReportLab."""
    try:
        qr_code = qr.QrCodeWidget(str(texto_qr))
        bounds = qr_code.getBounds()
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        d = Drawing(55, 55, transform=[55/w, 0, 0, 55/h, 0, 0])
        d.add(qr_code)
        return d
    except Exception:
        return None

def gerar_pdf_oficio(num_oficio, destinatario_nome, destinatario_cargo, orgao_destino, lista_materiais, pa_oficio, corpo_texto, emissor_nome, emissor_cargo, emissor_unidade):
    """Gera o arquivo PDF do Ofício de Encaminhamento com tabela unificada e QR Code."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    styles = getSampleStyleSheet()
    style_header = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=1, textColor=colors.HexColor('#1E293B'))
    style_title = ParagraphStyle('TitleStyle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=13, alignment=0, textColor=colors.HexColor('#0F172A'))
    style_body = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, alignment=4, textColor=colors.HexColor('#334155'))
    style_meta = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#1E293B'))
    style_table_hdr = ParagraphStyle('TableHdrStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0F172A'))
    style_table_cell = ParagraphStyle('TableCellStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#334155'))

    elements = []

    header_text = "<b>POLÍCIA MILITAR DE MINAS GERAIS</b><br/>" \
                  f"<b>{emissor_unidade.upper()}</b><br/>" \
                  "SEÇÃO DE CUSTÓDIA DE MATERIAIS E TCO - CREDS"
    elements.append(Paragraph(header_text, style_header))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceAfter=12))

    # Metadados do Ofício (Ajustado para REFERÊNCIA e data em DD/MM/AAAA)
    meta_text = f"<b>OFÍCIO Nº:</b> {num_oficio}<br/>" \
                f"<b>REFERÊNCIA:</b> {pa_oficio if pa_oficio else 'N/A'}<br/>" \
                f"<b>DATA DE EMISSÃO:</b> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
    elements.append(Paragraph(meta_text, style_meta))
    elements.append(Spacer(1, 12))

    dest_text = f"<b>Ao(À) Excelentíssimo(a) Senhor(a):</b><br/>" \
                f"<b>{destinatario_nome.upper()}</b><br/>" \
                f"{destinatario_cargo.upper()}<br/>" \
                f"<b>{orgao_destino.upper()}</b>"
    elements.append(Paragraph(dest_text, style_body))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>RELAÇÃO DE MATERIAIS ENCAMINHADOS (CADEIA DE CUSTÓDIA)</b>", style_title))
    elements.append(Spacer(1, 6))

    dados_tabela = [
        [
            Paragraph("<b>Nº REDS</b>", style_table_hdr), 
            Paragraph("<b>DESCRIÇÃO DO MATERIAL / LACRE</b>", style_table_hdr), 
            Paragraph("<b>NOME DO AUTOR</b>", style_table_hdr)
        ]
    ]

    for item in lista_materiais:
        reds_str = str(item.get("num_reds", "N/I"))
        desc_mat = f"{item.get('descricao', 'N/I')} (Qtd: {item.get('quantidade', '1.0')} {item.get('unidade_medida', 'UN')}) | Lacre: {item.get('involucro_lacre', 'N/I')}"
        autor_str = str(item.get("autores", "AUTOR NÃO INFORMADO"))

        dados_tabela.append([
            Paragraph(reds_str, style_table_cell),
            Paragraph(desc_mat, style_table_cell),
            Paragraph(autor_str, style_table_cell)
        ])

    tabela = Table(dados_tabela, colWidths=[120, 260, 160])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(tabela)
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("<b>TEOR DA SOLICITAÇÃO / HISTÓRICO:</b>", style_title))
    elements.append(Spacer(1, 4))
    corpo_formatado = str(corpo_texto or "").replace('\n', '<br/>')
    elements.append(Paragraph(corpo_formatado, style_body))
    elements.append(Spacer(1, 20))

    ass_text = f"____________________________________________________<br/>" \
               f"<b>{emissor_nome.upper()}</b><br/>" \
               f"{emissor_cargo} - {emissor_unidade}"
    elements.append(Paragraph(ass_text, ParagraphStyle('AssStyle', parent=style_header, alignment=1)))
    elements.append(Spacer(1, 15))

    concat_materiais = "".join([f"{m.get('id_bem')}{m.get('num_reds')}" for m in lista_materiais])
    hash_doc = gerar_hash_oficio(f"{num_oficio}{concat_materiais}{corpo_texto}")
    
    qr_drawing = criar_draw_qrcode(f"SIOP-PMMG | OFICIO: {num_oficio} | SHA-256: {hash_doc}")

    rodape_p1 = Paragraph(
        f"<b>CHANCELA ELETRÔNICA DE AUTENTICIDADE (ART. 158-A CPP):</b><br/>"
        f"<font size=7 color='#64748B'>SHA-256: {hash_doc}</font><br/>"
        f"<font size=7 color='#64748B'>Documento gerado pelo Sistema SIOP em {datetime.datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}.</font>",
        ParagraphStyle('RodapeStyle', parent=styles['Normal'], alignment=0)
    )

    if qr_drawing:
        tabela_rodape = Table([[rodape_p1, qr_drawing]], colWidths=[475, 65])
        tabela_rodape.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=8, spaceAfter=6))
        elements.append(tabela_rodape)
    else:
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=8, spaceAfter=6))
        elements.append(rodape_p1)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue(), hash_doc