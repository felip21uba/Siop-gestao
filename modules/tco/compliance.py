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
from core.database import supabase, obter_ip_cliente_real


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
    """Gera o PDF oficial da Declaração Individual de Responsabilidade e Sigilo."""
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
    style_body = ParagraphStyle('BodyComp', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, alignment=4, textColor=colors.HexColor('#334155'))
    style_box = ParagraphStyle('BoxComp', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=13, textColor=colors.HexColor('#0F172A'))

    elements = []

    # Cabeçalho Institucional
    elements.append(Paragraph("<b>POLÍCIA MILITAR DE MINAS GERAIS</b><br/><b>SEÇÃO DE CUSTÓDIA DE MATERIAIS E TCO - SIOP</b>", style_hdr))
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceAfter=8))

    elements.append(Paragraph("DECLARAÇÃO INDIVIDUAL DE RESPONSABILIDADE, COMPROMISSO E SIGILO", style_tit))
    elements.append(Spacer(1, 8))

    # Bloco de Identificação
    operador_completo = f"{cargo_funcao} {nome_militar}".strip()
    bloco_id = f"<b>DECLARANTE / POLICIAL MILITAR:</b> {operador_completo.upper()}<br/>" \
               f"<b>Nº DE POLÍCIA / MATRÍCULA:</b> {str(num_policia).upper()}<br/>" \
               f"<b>UNIDADE DE LOTAÇÃO:</b> {str(unidade).upper()}<br/>" \
               f"<b>DATA DE ACEITE ELETRÔNICO:</b> <font color='#166534'>{data_aceite_str}</font><br/>" \
               f"<b>DATA DE EMISSÃO DA 2ª VIA:</b> {data_impressao_str}"
    
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

    # Texto Institucional e Jurídico Sem Jargões Técnicos
    texto_juridico = (
        f"Eu, <b>{operador_completo.upper()}</b>, Nº PM <b>{num_policia}</b>, ciente das minhas obrigações e "
        f"deveres funcionais no Módulo TCO / Custódia do SIOP, declaro, concordo e me comprometo a cumprir os seguintes termos:<br/><br/>"
        "<b>1. RESPONSABILIDADE SOBRE MATERIAIS APREENDIDOS:</b> Declaro estar plenamente ciente de que todos os materiais "
        "e bens sob minha guarda ou recebidos no sistema são de minha estrita responsabilidade funcional e legal.<br/><br/>"
        "<b>2. VERACIDADE DAS INFORMAÇÕES E VEDAÇÃO A DOCUMENTO FALSO:</b> Comprometo-me a inserir apenas dados verdadeiros e "
        "fidedignos, estando ciente de que a inserção de informações ou documentos falsos no sistema configura crime e infração disciplinar grave.<br/><br/>"
        "<b>3. PRESERVAÇÃO DA CADEIA DE CUSTÓDIA:</b> Assumo o dever de zelar pela integridade física dos bens, invólucros, lacres "
        "e registros de tramitação, garantindo a rastreabilidade probatória em estrita conformidade com a legislação vigente.<br/><br/>"
        "<b>4. SIGILO DE INFORMAÇÕES PESSOAIS (LGPD):</b> Comprometo-me a manter sigilo absoluto sobre dados pessoais e informações "
        "sensíveis acessadas no sistema, utilizando-os exclusivamente para o estrito cumprimento do serviço policial militar.<br/><br/>"
        "<b>5. INTRANSFERIBILIDADE DA SENHA DE ACESSO:</b> Declaro ciência de que minha senha de acesso e credenciais de uso são "
        "pessoais e intransferíveis, respondendo diretamente por qualquer ação praticada no sistema sob minha identificação."
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
    """Salva o PDF do Termo no Supabase Storage sem interromper o fluxo do sistema."""
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
    """Registra o aceite no Supabase e atualiza a sessão local em tempo real."""
    if not num_policia:
        return True, datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    now_iso = datetime.datetime.now().isoformat()
    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    num_pm_str = str(num_policia).strip().upper()

    if supabase:
        try:
            # 1. Atualiza na tabela 'usuarios' usando OR flexível
            supabase.table("usuarios").update({
                "termo_compliance_aceito": True,
                "data_aceite_compliance": now_str
            }).or_(f"usuario_login.eq.{num_pm_str},usuario.eq.{num_pm_str}").execute()

            # 2. Grava log auditoria na tabela 'aceites_compliance'
            try:
                ip_cliente = obter_ip_cliente_real()
                supabase.table("aceites_compliance").insert({
                    "num_policia": num_pm_str,
                    "nome_militar": nome_militar,
                    "cargo_funcao": cargo_funcao,
                    "unidade": unidade,
                    "termo_versao": "CPP_ART_158A_LGPD_V1",
                    "ip_origem": ip_cliente,
                    "data_aceite": now_iso
                }).execute()
            except Exception as e_ac:
                print(f"Aviso aceites_compliance: {e_ac}")

            # 3. ATUALIZA A SESSÃO LOCAL
            if "usuario_dados" in st.session_state and isinstance(st.session_state["usuario_dados"], dict):
                st.session_state["usuario_dados"]["termo_compliance_aceito"] = True
                st.session_state["usuario_dados"]["data_aceite_compliance"] = now_str

            st.cache_data.clear()

            # 4. Backup PDF
            try:
                pdf_bytes = gerar_pdf_termo_compliance(nome_militar, cargo_funcao, unidade, num_pm_str, now_str)
                salvar_pdf_termo_no_storage(pdf_bytes, num_pm_str, nome_militar)
            except Exception:
                pass

            return True, now_str
        except Exception as e:
            print(f"Aviso ao registrar aceite no Supabase: {e}")

    # Fallback local
    if "usuario_dados" in st.session_state and isinstance(st.session_state["usuario_dados"], dict):
        st.session_state["usuario_dados"]["termo_compliance_aceito"] = True
        st.session_state["usuario_dados"]["data_aceite_compliance"] = now_str

    return True, now_str


def verificar_aceite_compliance_supabase(num_policia):
    """Verifica no Supabase se o usuário aceitou o termo de compliance."""
    usr_sessao = st.session_state.get("usuario_dados", {})
    if usr_sessao.get("termo_compliance_aceito", False):
        return True

    if not supabase or not num_policia:
        return False

    try:
        num_pm_str = str(num_policia).strip().upper()
        res = supabase.table("usuarios").select("termo_compliance_aceito, data_aceite_compliance").or_(f"usuario_login.eq.{num_pm_str},usuario.eq.{num_pm_str}").execute()
        if res.data and len(res.data) > 0:
            aceito = bool(res.data[0].get("termo_compliance_aceito", False))
            if aceito and "usuario_dados" in st.session_state and isinstance(st.session_state["usuario_dados"], dict):
                st.session_state["usuario_dados"]["termo_compliance_aceito"] = True
                st.session_state["usuario_dados"]["data_aceite_compliance"] = res.data[0].get("data_aceite_compliance")
            return aceito
        return False
    except Exception:
        return False


def exibir_modal_termo_compliance(num_policia, nome_militar, cargo_funcao, unidade):
    """Exibe a tela limpa e direta para aceite do Termo de Responsabilidade no primeiro acesso."""
    st.markdown("## 📜 Termo de Responsabilidade, Fiel Custódia e Sigilo")
    st.info("⚠️ **Primeiro Acesso ao Módulo TCO / Custódia Detectado**")
    
    operador_str = f"{cargo_funcao} {nome_militar}".strip().upper()
    
    st.markdown(f"""
    Eu, **{operador_str}**, Nº PM **{num_policia}**, ciente das minhas obrigações funcionais, declaro, concordo e me comprometo a:
    
    1. **Guarda e Custódia de Materiais:** Reconhecer que todos os materiais e bens sob minha guarda ou recebidos no sistema são de minha estrita responsabilidade funcional e legal.
    2. **Veracidade e Proibição de Documento Falso:** Inserir apenas informações e documentos verdadeiros, ciente de que a inserção de dados falsos no sistema pode configurar crime e infração disciplinar.
    3. **Cadeia de Custódia:** Zelar pela integridade dos bens, invólucros, lacres e registros de tramitação, garantindo a rastreabilidade conforme prevê a legislação.
    4. **Sigilo de Dados (LGPD):** Manter sigilo absoluto sobre informações pessoais e operacionais acessadas, não divulgando ou repassando dados sem autorização.
    5. **Uso de Credenciais Pessoais:** Guardar o sigilo de minha senha de acesso, compreendendo que ela é pessoal e intransferível.
    """)
    
    st.markdown("---")
    st.markdown(f"👤 **Militar Declarante:** `{operador_str}` | **Nº PM:** `{num_policia}` | **Unidade:** `{unidade}`")
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("✅ Declaro Ciente e Concordo com os Termos", type="primary", use_container_width=True):
        obter_ou_registrar_aceite_compliance(num_policia, nome_militar, cargo_funcao, unidade)
        st.session_state["termo_compliance_aceito"] = True
        st.rerun()