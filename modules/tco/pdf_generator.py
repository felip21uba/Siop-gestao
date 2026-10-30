"""
==============================================================================
Módulo Gerador de PDFs Oficiais do TCO (modules/tco/pdf_generator.py)
Gera os PDFs dos Ofícios de Remessa de Bens e Recibos Digitais de Transferência
com fuso de Brasília, Assinatura Digital do Emissor, QR Code e Hash SHA-256.
==============================================================================
"""

import io
import datetime
import hashlib
from zoneinfo import ZoneInfo
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def obter_agora_br():
    """Retorna data/hora no fuso horário oficial de Brasília (UTC-3)."""
    return datetime.datetime.now(FUSO_BR)


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
    """Gera o arquivo PDF do Ofício de Encaminhamento ajustado ao fuso de Brasília."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    agora_br = obter_agora_br()

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

    meta_text = f"<b>OFÍCIO Nº:</b> {num_oficio}<br/>" \
                f"<b>REFERÊNCIA:</b> {pa_oficio if pa_oficio else 'N/A'}<br/>" \
                f"<b>DATA DE EMISSÃO:</b> {agora_br.strftime('%d/%m/%Y %H:%M')}"
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
               f"{emissor_cargo}<br/>{emissor_unidade}"
    elements.append(Paragraph(ass_text, ParagraphStyle('AssStyle', parent=style_header, alignment=1)))
    elements.append(Spacer(1, 15))

    concat_materiais = "".join([f"{m.get('id_bem')}{m.get('num_reds')}" for m in lista_materiais])
    hash_doc = gerar_hash_oficio(f"{num_oficio}{concat_materiais}{corpo_texto}")
    
    qr_drawing = criar_draw_qrcode(f"SIOP-PMMG | OFICIO: {num_oficio} | SHA-256: {hash_doc}")

    rodape_p1 = Paragraph(
        f"<b>CHANCELA ELETRÔNICA DE AUTENTICIDADE (ART. 158-A CPP):</b><br/>"
        f"<font size=7 color='#64748B'>SHA-256: {hash_doc}</font><br/>"
        f"<font size=7 color='#64748B'>Documento gerado pelo Sistema SIOP em {agora_br.strftime('%d/%m/%Y às %H:%M:%S')}.</font>",
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


def gerar_pdf_recibo_transferencia(id_transferencia: str, remetente_nome: str, remetente_unidade: str, recebedor_nome: str, recebedor_unidade: str, lista_materiais: list, ip_origem: str = "N/I", observacao: str = "") -> tuple:
    """Gera o Recibo Digital de Transferência de Custódia (Art. 158-A CPP) com SHA-256 e QR Code."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    agora_br = obter_agora_br()
    data_formatada = agora_br.strftime("%d/%m/%Y às %H:%M:%S")

    styles = getSampleStyleSheet()
    style_header = ParagraphStyle('HdrRecibo', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=1, textColor=colors.HexColor('#1E293B'))
    style_title = ParagraphStyle('TitRecibo', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=14, alignment=1, textColor=colors.HexColor('#0F172A'))
    style_body = ParagraphStyle('BdyRecibo', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, alignment=4, textColor=colors.HexColor('#334155'))
    style_meta_box = ParagraphStyle('MtxRecibo', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=colors.HexColor('#0F172A'))
    style_table_hdr = ParagraphStyle('ThRecibo', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0F172A'))
    style_table_cell = ParagraphStyle('TdRecibo', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=10, textColor=colors.HexColor('#334155'))

    elements = []

    header_text = "<b>POLÍCIA MILITAR DE MINAS GERAIS</b><br/>" \
                  "<b>SISTEMA INTEGRADO DE OPERAÇÕES - SIOP</b><br/>" \
                  "SEÇÃO DE CUSTÓDIA DE MATERIAIS E TCO - CREDS"
    elements.append(Paragraph(header_text, style_header))
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceAfter=8))

    elements.append(Paragraph("<b>RECIBO DIGITAL DE TRANSFERÊNCIA DE CUSTÓDIA (ART. 158-A DO CPP)</b>", style_title))
    elements.append(Spacer(1, 6))

    bloco_partes = [
        [
            Paragraph(f"<b>ORIGEM / REMETENTE:</b><br/>{remetente_nome.upper()}<br/><font color='#64748B'>Lotação: {remetente_unidade.upper()}</font>", style_meta_box),
            Paragraph(f"<b>DESTINO / RECEBEDOR:</b><br/>{recebedor_nome.upper()}<br/><font color='#64748B'>Lotação: {recebedor_unidade.upper()}</font>", style_meta_box)
        ],
        [
            Paragraph(f"<b>Nº CONTROLO:</b> {id_transferencia}<br/><b>DATA/HORA:</b> {data_formatada}", style_meta_box),
            Paragraph(f"<b>IP DE REGISTRO:</b> {ip_origem}<br/><b>STATUS:</b> ACEITE CONFIRMADO NO SIOP", style_meta_box)
        ]
    ]

    tabela_partes = Table(bloco_partes, colWidths=[270, 270])
    tabela_partes.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(tabela_partes)
    elements.append(Spacer(1, 8))

    dados_tabela = [
        [
            Paragraph("<b>Nº REDS</b>", style_table_hdr),
            Paragraph("<b>DESCRIÇÃO DO BEM</b>", style_table_hdr),
            Paragraph("<b>QTD / UNID</b>", style_table_hdr),
            Paragraph("<b>INVÓLUCRO / LACRE</b>", style_table_hdr),
            Paragraph("<b>AUTOR / ENVOLVIDO</b>", style_table_hdr)
        ]
    ]

    for item in lista_materiais:
        r_num = str(item.get("num_reds", "N/I"))
        r_desc = str(item.get("descricao", "N/I"))
        r_qtd = f"{item.get('quantidade', 1)} {item.get('unidade_medida', 'UN')}"
        r_lacre = str(item.get("involucro_lacre", "SEM LACRE"))
        r_autor = str(item.get("autores", "N/I"))

        dados_tabela.append([
            Paragraph(r_num, style_table_cell),
            Paragraph(r_desc, style_table_cell),
            Paragraph(r_qtd, style_table_cell),
            Paragraph(r_lacre, style_table_cell),
            Paragraph(r_autor, style_table_cell)
        ])

    tabela_materiais = Table(dados_tabela, colWidths=[90, 180, 60, 100, 110])
    tabela_materiais.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    elements.append(tabela_materiais)
    elements.append(Spacer(1, 8))

    declaracao_txt = (
        "<b>DECLARAÇÃO DE FIEL CUSTÓDIA E ACEITE:</b><br/>"
        "O recebedor qualificado declara que realizou a conferência física e documental dos bens e invólucros acima discriminados, "
        "assumindo formalmente a sua posse e guarda na condição de Fiel Custodiante, comprometendo-se com a rigorosa preservação da "
        "Cadeia de Custódia e inalterabilidade dos lacres nos termos dos artigos 158-A a 158-F do Código de Processo Penal."
    )
    if observacao:
        declaracao_txt += f"<br/><br/><b>RESSALVAS NO ATO DO ACEITE:</b> {observacao}"

    elements.append(Paragraph(declaracao_txt, style_body))
    elements.append(Spacer(1, 14))

    ass_tabela = Table([
        [
            Paragraph(f"_________________________________________<br/><b>{remetente_nome.upper()}</b><br/>Remetente / Custodiante Anterior", ParagraphStyle('Ass1', parent=style_header, fontSize=7.5, leading=10)),
            Paragraph(f"_________________________________________<br/><b>{recebedor_nome.upper()}</b><br/>Recebedor / Novo Fiel Custodiante", ParagraphStyle('Ass2', parent=style_header, fontSize=7.5, leading=10))
        ]
    ], colWidths=[270, 270])
    elements.append(ass_tabela)
    elements.append(Spacer(1, 10))

    concat_mats = "".join([f"{m.get('id_bem')}{m.get('involucro_lacre')}" for m in lista_materiais])
    hash_doc = gerar_hash_oficio(f"{id_transferencia}{remetente_nome}{recebedor_nome}{concat_mats}{data_formatada}{ip_origem}")
    qr_draw = criar_draw_qrcode(f"SIOP-PMMG | RECIBO CUSTODIA: {id_transferencia} | RECEBEDOR: {recebedor_nome} | SHA: {hash_doc}")

    txt_rodape = Paragraph(
        f"<b>CHANCELA ELETRÔNICA DE AUTENTICIDADE E NÃO-REPUDIABILIDADE:</b><br/>"
        f"<font size=6.5 color='#64748B'>SHA-256: {hash_doc}</font><br/>"
        f"<font size=6.5 color='#64748B'>Recibo emitido automaticamente pelo SIOP em {data_formatada} sob o endereço IP {ip_origem}.</font>",
        ParagraphStyle('RodapeRecibo', parent=styles['Normal'], alignment=0)
    )

    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=6, spaceAfter=4))
    if qr_draw:
        tabela_rodape = Table([[txt_rodape, qr_draw]], colWidths=[475, 65])
        tabela_rodape.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        elements.append(tabela_rodape)
    else:
        elements.append(txt_rodape)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue(), hash_doc