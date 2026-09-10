import io
import datetime
import hashlib
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from modules.tco.database import registrar_log_supabase, atualizar_material_supabase

def gerar_hash_oficio(conteudo_str):
    """Gera assinatura SHA-256 para o documento oficial."""
    return hashlib.sha256(conteudo_str.encode('utf-8')).hexdigest()

def gerar_pdf_oficio(num_oficio, destinatario, cargo_destinatario, orgao_destino, num_reds, id_bem, desc_material, qtd_unid, lacre, pa_oficio, corpo_texto, emissor_nome, emissor_cargo, emissor_unidade):
    """Gera o arquivo PDF do Ofício de Encaminhamento com padrões PMMG."""
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
        fontSize=10,
        leading=12,
        alignment=1, # Centralizado
        textColor=colors.HexColor('#1E293B')
    )
    
    style_title = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        alignment=0,
        textColor=colors.HexColor('#0F172A')
    )
    
    style_body = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=4, # Justificado
        textColor=colors.HexColor('#334155')
    )

    style_meta = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1E293B')
    )

    elements = []

    # Cabeçalho Institucional
    header_text = "<b>POLÍCIA MILITAR DE MINAS GERAIS</b><br/>" \
                  f"<b>{emissor_unidade.upper()}</b><br/>" \
                  "SEÇÃO DE CUSTÓDIA DE MATERIAIS E TCO - CREDS"
    elements.append(Paragraph(header_text, style_header))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceAfter=15))

    # Número do Ofício e Data
    data_extenso = datetime.datetime.now().strftime("%d de %B de %Y")
    meta_text = f"<b>OFÍCIO Nº:</b> {num_oficio}<br/>" \
                f"<b>REF. P.A. / PROTOCOLO:</b> {pa_oficio if pa_oficio else 'N/A'}<br/>" \
                f"<b>DATA DE EMISSÃO:</b> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
    elements.append(Paragraph(meta_text, style_meta))
    elements.append(Spacer(1, 15))

    # Endereçamento / Destinatário
    dest_text = f"<b>Ao(À) Excelentíssimo(a) Senhor(a):</b><br/>" \
                f"<b>{destinatario.upper()}</b><br/>" \
                f"{cargo_destinatario}<br/>" \
                f"<b>{orgao_destino}</b>"
    elements.append(Paragraph(dest_text, style_body))
    elements.append(Spacer(1, 15))

    # Tabela com Detalhes do Material sob Custódia
    elements.append(Paragraph("<b>DADOS DO MATERIAL ENCAMINHADO (CADEIA DE CUSTÓDIA)</b>", style_title))
    elements.append(Spacer(1, 6))

    dados_tabela = [
        [Paragraph("<b>Nº REDS</b>", style_meta), Paragraph(num_reds, style_body)],
        [Paragraph("<b>CÓDIGO BEM</b>", style_meta), Paragraph(id_bem, style_body)],
        [Paragraph("<b>DESCRIÇÃO</b>", style_meta), Paragraph(desc_material, style_body)],
        [Paragraph("<b>QUANTIDADE</b>", style_meta), Paragraph(str(qtd_unid), style_body)],
        [Paragraph("<b>INVÓLUCRO / LACRE</b>", style_meta), Paragraph(lacre, style_body)],
    ]

    tabela = Table(dados_tabela, colWidths=[140, 390])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(tabela)
    elements.append(Spacer(1, 15))

    # Corpo do Ofício
    elements.append(Paragraph("<b>TEOR DA SOLICITAÇÃO / HISTÓRICO:</b>", style_title))
    elements.append(Spacer(1, 6))
    corpo_formatado = corpo_texto.replace('\n', '<br/>')
    elements.append(Paragraph(corpo_formatado, style_body))
    elements.append(Spacer(1, 25))

    # Assinatura Digital do Emissor
    elements.append(Spacer(1, 20))
    ass_text = f"____________________________________________________<br/>" \
               f"<b>{emissor_nome.upper()}</b><br/>" \
               f"{emissor_cargo} - {emissor_unidade}"
    elements.append(Paragraph(ass_text, ParagraphStyle('AssStyle', parent=style_header, alignment=1)))
    elements.append(Spacer(1, 20))

    # Rodapé de Segurança e Assinatura SHA-256
    hash_doc = gerar_hash_oficio(f"{num_oficio}{num_reds}{id_bem}{corpo_texto}")
    rodape_text = f"<b>CHANCELA ELETRÔNICA DE AUTENTICIDADE (ART. 158-A CPP):</b><br/>" \
                  f"<font size=7 color='#64748B'>SHA-256: {hash_doc}</font><br/>" \
                  f"<font size=7 color='#64748B'>Documento gerado eletronicamente pelo Sistema SIOP em {datetime.datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}.</font>"
    
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=10, spaceAfter=8))
    elements.append(Paragraph(rodape_text, ParagraphStyle('RodapeStyle', parent=styles['Normal'], alignment=1)))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue(), hash_doc

def renderizar_aba_gerador_oficios(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    """Aba interativa para preenchimento e geração do Ofício em PDF."""
    st.markdown("#### 📄 Gerador Oficial de Ofícios de Encaminhamento e Tramitação")
    st.caption("Emissão de expediente oficial de custódia para o JECRIM, Polícia Civil, Perícia Técnica ou Fórum.")

    if not all_bens_banco:
        st.info("Nenhum material cadastrado no banco para gerar ofício.")
        return

    bens_dict = {f"REDS: {b['num_reds']} | {b['id_bem']} - {b['descricao']} (Lacre: {b.get('involucro_lacre', 'N/I')})": b for b in all_bens_banco}
    
    with st.form("form_gerador_oficio_v1"):
        st.markdown("##### 1. Seleção do Material sob Custódia")
        material_sel_label = st.selectbox("Selecione o Material Relacionado:", list(bens_dict.keys()))
        bem_obj = bens_dict[material_sel_label]

        st.divider()
        st.markdown("##### 2. Dados do Destinatário / Órgão Externo")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            num_oficio = st.text_input("Nº do Ofício:", value=f"OFÍCIO {datetime.datetime.now().strftime('%Y%m%d')}-35CIA").strip().upper()
            destinatario_nome = st.text_input("Nome do Destinatário / Autoridade:", placeholder="Ex: Dr. Marco Antônio Silva").strip().upper()
        with col_d2:
            destinatario_cargo = st.text_input("Cargo da Autoridade:", value="EXCELENTÍSSIMO(A) SENHOR(A) JUIZ(A) DE DIREITO").strip().upper()
            orgao_destino = st.selectbox("Órgão / Destino:", [
                "JUIZADO ESPECIAL CRIMINAL (JECRIM)",
                "DELEGACIA DE POLÍCIA CIVIL (PCMG)",
                "SEÇÃO DE PERÍCIAS TÉCNICAS",
                "PODER JUDICIÁRIO / FÓRUM DA COMARCA",
                "PROMOTORIA DE JUSTIÇA / MPMG"
            ])

        pa_oficio = st.text_input("Nº do Processo Administrativo (P.A.) / Protocolo:", value=bem_obj.get("pa_oficio_autorizador", "")).strip().upper()

        st.divider()
        st.markdown("##### 3. Texto do Ofício / Histórico de Encaminhamento")
        corpo_padrao = (
            f"Cumprimentando-o(a) cordialmente, encaminho a Vossa Excelência/Senhoria o material apreendido "
            f"vinculado ao REDS Nº {bem_obj['num_reds']}, conforme discriminado na tabela acima, para as providências "
            f"de praxe relativas ao processo/procedimento em epígrafe.\n\n"
            f"Ressalta-se que o referido bem encontra-se devidamente acondicionado em invólucro inspecionado "
            f"e registrado sob o lacre de segurança nº {bem_obj.get('involucro_lacre', 'N/I')}, garantindo a "
            f"preservação da Cadeia de Custódia nos termos do Artigo 158-A e seguintes do Código de Processo Penal."
        )
        corpo_texto = st.text_area("Teor do Expediente:", value=corpo_padrao, height=160)

        st.divider()
        st.markdown("##### 4. Dados do Emissor / Assinatura")
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            emissor_nome = st.text_input("Nome Completo do Emissor:", value=nome_militar_atual).strip().upper()
        with col_e2:
            emissor_cargo = st.text_input("Cargo / Função:", value="RESPONSÁVEL PELA CUSTÓDIA / CREDS").strip().upper()

        btn_gerar = st.form_submit_button("🚀 Gerar e Baixar Ofício (PDF)", type="primary", use_container_width=True)

    if btn_gerar:
        if not destinatario_nome or not corpo_texto:
            st.error("⚠️ Preencha todos os campos obrigatórios (Destinatário e Texto do Ofício).")
        else:
            pdf_bytes, hash_sha = gerar_pdf_oficio(
                num_oficio=num_oficio,
                destinatario=destinatario_nome,
                cargo_destinatario=destinatario_cargo,
                orgao_destino=orgao_destino,
                num_reds=bem_obj['num_reds'],
                id_bem=bem_obj['id_bem'],
                desc_material=bem_obj['descricao'],
                qtd_unid=f"{bem_obj['quantidade']} {bem_obj.get('unidade_medida', 'UN')}",
                lacre=bem_obj.get('involucro_lacre', 'SEM LACRE'),
                pa_oficio=pa_oficio,
                corpo_texto=corpo_texto,
                emissor_nome=emissor_nome,
                emissor_cargo=emissor_cargo,
                emissor_unidade=unidade_militar_atual
            )

            # Atualiza fase no Supabase e grava log
            now_iso = datetime.datetime.now().isoformat()
            atualizar_material_supabase(bem_obj["id_bem"], {
                "fase_destinacao": f"Encaminhado ({orgao_destino})",
                "pa_oficio_autorizador": num_oficio
            })
            
            registrar_log_supabase({
                "data_hora": now_iso,
                "num_reds": bem_obj["num_reds"],
                "bem_id": bem_obj["id_bem"],
                "acao": "EMISSÃO DE OFÍCIO DE ENCAMINHAMENTO",
                "origem": nome_militar_atual,
                "unidade_origem": unidade_militar_atual,
                "destino": orgao_destino,
                "unidade_destino": "Órgão Externo",
                "detalhe": f"Gerado {num_oficio} para {destinatario_nome}. SHA-256: {hash_sha}"
            })

            st.success("✅ Ofício gerado com sucesso e registrado na trilha de auditoria!")
            st.download_button(
                label="📥 Clique aqui para Baixar o Ofício (PDF)",
                data=pdf_bytes,
                file_name=f"{num_oficio.replace(' ', '_')}_{bem_obj['id_bem']}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )