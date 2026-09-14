import io
import datetime
import hashlib
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from core.database import supabase

def aplicar_estilo_tco():
    """Aplica estilos CSS customizados para o módulo TCO."""
    st.markdown("""
    <style>
        .stMetric {
            background-color: #1E293B;
            padding: 10px;
            border-radius: 8px;
        }
    </style>
    """, unsafe_allow_html=True)

def gerar_hash_compliance(texto):
    """Gera chancela SHA-256 para o Termo de Compliance."""
    return hashlib.sha256(str(texto).encode('utf-8')).hexdigest()

def criar_draw_qrcode(texto_qr):
    """Gera o elemento gráfico do QR Code no PDF."""
    try:
        qr_code = qr.QrCodeWidget(str(texto_qr))
        bounds = qr_code.getBounds()
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        d = Drawing(50, 55, transform=[50/w, 0, 0, 55/h, 0, 0])
        d.add(qr_code)
        return d
    except Exception:
        return None

def gerar_pdf_termo_compliance(nome_militar, cargo_funcao, unidade, num_policia, data_aceite_str, data_impressao_str=None):
    """Gera o PDF oficial do Termo de Compliance com todas as cláusulas e protocolos de segurança ativos."""
    if not data_impressao_str:
        data_impressao_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    styles = getSampleStyleSheet()
    style_hdr = ParagraphStyle('HeaderComp', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=1, textColor=colors.HexColor('#0F172A'))
    style_tit = ParagraphStyle('TitComp', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=14, alignment=1, textColor=colors.HexColor('#1E293B'))
    style_body = ParagraphStyle('BodyComp', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11.5, alignment=4, textColor=colors.HexColor('#334155'))
    style_box = ParagraphStyle('BoxComp', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=13, textColor=colors.HexColor('#0F172A'))

    elements = []

    # Cabeçalho Institucional
    elements.append(Paragraph("<b>POLÍCIA MILITAR DE MINAS GERAIS</b><br/><b>SEÇÃO DE CUSTÓDIA DE MATERIAIS E TCO - SIOP</b>", style_hdr))
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceAfter=8))

    elements.append(Paragraph("TERMO DE COMPLIANCE, RESPONSABILIDADE LEGAL E SEGURANÇA DA INFORMAÇÃO", style_tit))
    elements.append(Spacer(1, 8))

    # Bloco de Identificação
    operador_completo = f"{cargo_funcao} {nome_militar}".strip()
    bloco_id = f"<b>OPERADOR:</b> {operador_completo.upper()}<br/>" \
               f"<b>IDENTIFICAÇÃO / POLÍCIA:</b> {str(num_policia).upper()}<br/>" \
               f"<b>UNIDADE:</b> {str(unidade).upper()}<br/>" \
               f"<b>DATA DE ACEITE ELETRÔNICO:</b> <font color='#166534'>{data_aceite_str}</font><br/>" \
               f"<b>DATA E HORA DE IMPRESSÃO:</b> {data_impressao_str}"
    
    tabela_id = Table([[Paragraph(bloco_id, style_box)]], colWidths=[540])
    tabela_id.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(tabela_id)
    elements.append(Spacer(1, 10))

    # Texto Jurídico de Compliance com todos os Protocolos Técnicos
    texto_juridico = (
        "<b>1. DA CADEIA DE CUSTÓDIA (ART. 158-A CPP):</b> O operador declara ciência formal de que todas as ações "
        "realizadas no Módulo de Custódia e TCO (importação de REDS, alteração de invólucro, transferência física, "
        "registro de divergências e destinação final) são vinculadas de forma unívoca à sua credencial funcional e endereço IP.<br/><br/>"
        "<b>2. DA VINCULAÇÃO E IMUTABILIDADE:</b> O aceite deste termo foi registrado eletronicamente no primeiro acesso do "
        "militar ao sistema e constitui assinatura digital idônea para fins de auditoria interna, correicional e instrução processual.<br/><br/>"
        "<b>3. DA SEGURANÇA DA INFORMAÇÃO E LGPD:</b> A credencial de acesso é pessoal e intransferível. O uso inadequado "
        "ou o repasse de senhas/tokens MFA a terceiros ensejará responsabilidade administrativa, civil e penal.<br/><br/>"
        "<b>4. DOS PROTOCOLOS DE SEGURANÇA E CONFORMIDADE TÉCNICA (PARTE INFORMATIVA Nº 12.4/2026):</b><br/>"
        "• <b>a. Autenticação e Duplo Papel (RBAC):</b> Controle de acesso em 7 níveis com separação independente de papéis (perfil_creds x perfil_escala) e escopo por Cia/BPM.<br/>"
        "• <b>b. Autenticação 2FA/TOTP:</b> Validação de identidade via aplicativo TOTP (Google Authenticator/Authy) e trava de dispositivo único.<br/>"
        "• <b>c. Gestão de Sessão e Timeout:</b> Encerramento automático por ociosidade (30 min) e desconexão emergencial remota.<br/>"
        "• <b>d. Trilha Universal de Auditoria:</b> Registro imutável de ações de comando e custódia (operador, alvo, IP e carimbo DD/MM/AAAA HH:MM).<br/>"
        "• <b>e. Proteção de Banco de Dados:</b> Criptografia HTTPS/TLS 1.3 em trânsito e isolamento estrito de registros por Row Level Security (RLS) no PostgreSQL/Supabase.<br/>"
        "• <b>f. Sanitização e Filtro Anti-Injeção:</b> Escape automático de caracteres e tratamento rigoroso de texto livre contra scripts maliciosos (Anti-XSS e Anti-SQLi)."
    )
    elements.append(Paragraph(texto_juridico, style_body))
    elements.append(Spacer(1, 14))

    # Assinatura
    ass_txt = f"____________________________________________________<br/>" \
              f"<b>{operador_completo.upper()}</b><br/>" \
              f"Nº de Polícia: {num_policia} - {unidade}"
    elements.append(Paragraph(ass_txt, ParagraphStyle('AssComp', parent=style_hdr, alignment=1)))
    elements.append(Spacer(1, 10))

    # Chancela SHA-256 e QR Code
    hash_doc = gerar_hash_compliance(f"{num_policia}{data_aceite_str}{operador_completo}")
    qr_draw = criar_draw_qrcode(f"SIOP-PMMG | COMPLIANCE PM: {num_policia} | ACEITE: {data_aceite_str} | SHA: {hash_doc}")

    txt_rodape = Paragraph(
        f"<b>CHANCELA ELETRÔNICA DE AUTENTICIDADE:</b><br/>"
        f"<font size=6.5 color='#64748B'>SHA-256: {hash_doc}</font><br/>"
        f"<font size=6.5 color='#64748B'>Documento extraído via SIOP em {data_impressao_str}.</font>",
        ParagraphStyle('RodapeComp', parent=styles['Normal'], alignment=0)
    )

    if qr_draw:
        tbl_f = Table([[txt_rodape, qr_draw]], colWidths=[475, 65])
        tbl_f.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=6, spaceAfter=4))
        elements.append(tbl_f)
    else:
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=6, spaceAfter=4))
        elements.append(txt_rodape)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def salvar_pdf_termo_no_storage(pdf_bytes, num_policia, nome_militar):
    """Salva o PDF do Termo no Supabase Storage testando buckets de backup sem interromper o sistema."""
    if not supabase or not pdf_bytes:
        return None

    data_hoje = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"Termo_{num_policia}_{data_hoje}.pdf"
    
    buckets_candidatos = ["termos_compliance", "tco_midias", "midias_tco"]

    for bucket in buckets_candidatos:
        try:
            supabase.storage.from_(bucket).upload(
                path=nome_arquivo,
                file=pdf_bytes,
                file_options={"content-type": "application/pdf"}
            )
            return supabase.storage.from_(bucket).get_public_url(nome_arquivo)
        except Exception:
            continue
    return None

def obter_ou_registrar_aceite_compliance(num_policia, nome_militar, cargo_funcao, unidade):
    """Verifica se o militar possui aceite gravado. Se for o primeiro acesso, registra e gera o PDF de backup."""
    if not supabase or not num_policia:
        return True, datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    try:
        num_pm_str = str(num_policia).strip().upper()
        res = supabase.table("usuarios").select("termo_compliance_aceito, data_aceite_compliance").eq("usuario_login", num_pm_str).execute()
        
        data_banco = res.data[0] if res.data else {}
        aceito = data_banco.get("termo_compliance_aceito", False)
        data_existente = data_banco.get("data_aceite_compliance")

        if aceito and data_existente:
            return True, data_existente

        now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        
        supabase.table("usuarios").update({
            "termo_compliance_aceito": True,
            "data_aceite_compliance": now_str
        }).eq("usuario_login", num_pm_str).execute()

        try:
            pdf_bytes = gerar_pdf_termo_compliance(nome_militar, cargo_funcao, unidade, num_pm_str, now_str)
            salvar_pdf_termo_no_storage(pdf_bytes, num_pm_str, nome_militar)
        except Exception:
            pass

        return True, now_str
    except Exception:
        return True, datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

def verificar_aceite_compliance_supabase(num_policia):
    """Verifica no Supabase se o usuário aceitou o termo de compliance."""
    if not supabase or not num_policia:
        return True
    try:
        num_pm_str = str(num_policia).strip().upper()
        res = supabase.table("usuarios").select("termo_compliance_aceito").eq("usuario_login", num_pm_str).execute()
        if res.data and len(res.data) > 0:
            return res.data[0].get("termo_compliance_aceito", False)
        return False
    except Exception:
        return True

def exibir_modal_termo_compliance(num_policia, nome_militar, cargo_funcao, unidade):
    """Exibe a tela para aceite do Termo de Compliance no primeiro acesso."""
    st.warning("⚠️ **TERMO DE COMPLIANCE E RESPONSABILIDADE LEGAL**")
    st.markdown(
        "Para utilizar o Módulo TCO / Custódia, você deve declarar ciência das normas de "
        "Cadeia de Custódia (Art. 158-A do CPP) e Responsabilidade pela Segurança da Informação."
    )
    if st.button("✅ Declarar Ciente e Aceitar Termo", type="primary", use_container_width=True):
        obter_ou_registrar_aceite_compliance(num_policia, nome_militar, cargo_funcao, unidade)
        st.session_state["termo_compliance_aceito"] = True
        st.rerun()