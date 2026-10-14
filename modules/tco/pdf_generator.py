"""
==============================================================================
Módulo Gerador de PDFs Oficiais do TCO (modules/tco/pdf_generator.py)
Gera os PDFs dos Ofícios de Remessa de Bens com tabela de materiais,
Assinatura Digital do Emissor e Hash de Autenticidade SHA-256.
==============================================================================
"""

import io
import hashlib
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT


def calcular_hash_sha256(conteudo_texto: str) -> str:
    """Gera a assinatura digital SHA-256 para garantia da integridade do documento."""
    return hashlib.sha256(conteudo_texto.encode("utf-8")).hexdigest().upper()


def gerar_pdf_oficio(
    num_oficio: str,
    destinatario_nome: str,
    destinatario_cargo: str,
    orgao_destino: str,
    lista_materiais: list,
    pa_oficio: str = "",
    corpo_texto: str = "",
    emissor_nome: str = "POLICIAL MILITAR",
    emissor_cargo: str = "FIEL DEPOSITÁRIO / CREDS",
    emissor_unidade: str = "21º BPM"
) -> tuple[bytes, str]:
    """
    Gera o PDF oficial do Ofício de Remessa no padrão PMMG / TCO.
    Retorna uma tupla (pdf_bytes, hash_sha256).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Estilos Customizados
    style_cabecalho_top = ParagraphStyle(
        "CabecalhoTop",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1e293b")
    )

    style_subcabecalho = ParagraphStyle(
        "SubCabecalho",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569")
    )

    style_titulo_oficio = ParagraphStyle(
        "TituloOficio",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#0f172a")
    )

    style_corpo = ParagraphStyle(
        "CorpoOficio",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#1e293b")
    )

    style_tabela_hdr = ParagraphStyle(
        "TabelaHdr",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.white
    )

    style_tabela_cell = ParagraphStyle(
        "TabelaCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#1e293b")
    )

    style_assinatura_nome = ParagraphStyle(
        "AssinaturaNome",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a")
    )

    style_rodape_hash = ParagraphStyle(
        "RodapeHash",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=7,
        leading=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748b")
    )

    story = []

    # 1. Cabeçalho Institucional PMMG
    story.append(Paragraph("POLÍCIA MILITAR DE MINAS GERAIS", style_cabecalho_top))
    story.append(Paragraph(f"{emissor_unidade.upper()} — SEÇÃO DE CUSTÓDIA DE MATERIAIS (CREDS-TCO)", style_subcabecalho))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#c5a059"), spaceAfter=12))

    # 2. Número do Ofício e Referência
    dt_extenso = datetime.datetime.now().strftime("%d de %B de %Y")
    story.append(Paragraph(f"<b>{num_oficio}</b>", style_titulo_oficio))
    if pa_oficio:
        story.append(Paragraph(f"<font size=9 color='#475569'><b>Ref. Procedimento / P.A.:</b> {pa_oficio}</font>", style_corpo))
    story.append(Paragraph(f"<font size=9 color='#475569'><b>Data da Emissão:</b> {dt_extenso}</font>", style_corpo))
    story.append(Spacer(1, 12))

    # 3. Destinatário
    story.append(Paragraph(f"<b>Ao(À):</b> {destinatario_cargo}", style_corpo))
    story.append(Paragraph(f"<b>A/C:</b> {destinatario_nome}", style_corpo))
    story.append(Paragraph(f"<b>Órgão Destino:</b> {orgao_destino}", style_corpo))
    story.append(Spacer(1, 12))

    # 4. Corpo do Texto
    for paragrafo in corpo_texto.split("\n"):
        if paragrafo.strip():
            story.append(Paragraph(paragrafo.strip(), style_corpo))
            story.append(Spacer(1, 6))

    story.append(Spacer(1, 10))

    # 5. Tabela de Materiais Apreendidos
    story.append(Paragraph("<b>RELAÇÃO DOS BENS APREENDIDOS E ENCAMINHADOS:</b>", style_corpo))
    story.append(Spacer(1, 6))

    dados_tabela = [[
        Paragraph("Nº REDS", style_tabela_hdr),
        Paragraph("Descrição do Material", style_tabela_hdr),
        Paragraph("Qtd / Unid", style_tabela_hdr),
        Paragraph("Nº Lacre / Invólucro", style_tabela_hdr),
        Paragraph("Autor / Envolvido", style_tabela_hdr)
    ]]

    for m in lista_materiais:
        dados_tabela.append([
            Paragraph(str(m.get("num_reds", "N/I")), style_tabela_cell),
            Paragraph(str(m.get("descricao", "N/I")), style_tabela_cell),
            Paragraph(f"{m.get('quantidade', 1)} {m.get('unidade_medida', 'UN')}", style_tabela_cell),
            Paragraph(str(m.get("involucro_lacre", "SEM LACRE")), style_tabela_cell),
            Paragraph(str(m.get("autores", "N/I")), style_tabela_cell)
        ])

    tabela_mats = Table(dados_tabela, colWidths=[110, 180, 60, 95, 95])
    tabela_mats.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#63502c")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(tabela_mats)
    story.append(Spacer(1, 25))

    # 6. Campo de Assinatura
    story.append(HRFlowable(width="50%", thickness=1, color=colors.HexColor("#475569"), hAlign="CENTER", spaceAfter=6))
    story.append(Paragraph(f"<b>{emissor_nome}</b>", style_assinatura_nome))
    story.append(Paragraph(f"<font size=8 color='#475569'>{emissor_cargo} — {emissor_unidade}</font>", style_assinatura_nome))
    story.append(Spacer(1, 20))

    # 7. Hash SHA-256 e Autenticidade
    texto_para_hash = f"{num_oficio}|{destinatario_nome}|{orgao_destino}|{len(lista_materiais)}|{emissor_nome}|{dt_extenso}"
    hash_sha256 = calcular_hash_sha256(texto_para_hash)

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=6))
    story.append(Paragraph(f"🔒 AUTENTICIDADE DIGITAL SHA-256: {hash_sha256}", style_rodape_hash))
    story.append(Paragraph("Documento emitido eletronicamente via SIOP PMMG — Validação da Cadeia de Custódia (Art. 158-A CPP)", style_subcabecalho))

    # Construir PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes, hash_sha256