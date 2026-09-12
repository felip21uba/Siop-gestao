import io
import datetime
import hashlib
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from modules.tco.database import registrar_log_supabase, atualizar_material_supabase

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
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    style_header = ParagraphStyle(
        'HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=1, textColor=colors.HexColor('#1E293B')
    )
    
    style_title = ParagraphStyle(
        'TitleStyle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=13, alignment=0, textColor=colors.HexColor('#0F172A')
    )
    
    style_body = ParagraphStyle(
        'BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, alignment=4, textColor=colors.HexColor('#334155')
    )

    style_meta = ParagraphStyle(
        'MetaStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#1E293B')
    )

    style_table_hdr = ParagraphStyle(
        'TableHdrStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0F172A')
    )

    style_table_cell = ParagraphStyle(
        'TableCellStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#334155')
    )

    elements = []

    # Cabeçalho Institucional
    header_text = "<b>POLÍCIA MILITAR DE MINAS GERAIS</b><br/>" \
                  f"<b>{emissor_unidade.upper()}</b><br/>" \
                  "SEÇÃO DE CUSTÓDIA DE MATERIAIS E TCO - CREDS"
    elements.append(Paragraph(header_text, style_header))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceAfter=12))

    # Dados do Expediente
    meta_text = f"<b>OFÍCIO Nº:</b> {num_oficio}<br/>" \
                f"<b>REF. P.A. / PROTOCOLO:</b> {pa_oficio if pa_oficio else 'N/A'}<br/>" \
                f"<b>DATA DE EMISSÃO:</b> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
    elements.append(Paragraph(meta_text, style_meta))
    elements.append(Spacer(1, 12))

    # Endereçamento
    dest_text = f"<b>Ao(À) Excelentíssimo(a) Senhor(a):</b><br/>" \
                f"<b>{destinatario_nome.upper()}</b><br/>" \
                f"{destinatario_cargo.upper()}<br/>" \
                f"<b>{orgao_destino.upper()}</b>"
    elements.append(Paragraph(dest_text, style_body))
    elements.append(Spacer(1, 12))

    # Tabela com Materiais, REDS e Autores
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

    # Corpo do Texto
    elements.append(Paragraph("<b>TEOR DA SOLICITAÇÃO / HISTÓRICO:</b>", style_title))
    elements.append(Spacer(1, 4))
    corpo_formatado = str(corpo_texto or "").replace('\n', '<br/>')
    elements.append(Paragraph(corpo_formatado, style_body))
    elements.append(Spacer(1, 20))

    # Assinatura
    ass_text = f"____________________________________________________<br/>" \
               f"<b>{emissor_nome.upper()}</b><br/>" \
               f"{emissor_cargo} - {emissor_unidade}"
    elements.append(Paragraph(ass_text, ParagraphStyle('AssStyle', parent=style_header, alignment=1)))
    elements.append(Spacer(1, 15))

    # Hash SHA-256 e Rodapé
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
        tabela_rodape.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT')
        ]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=8, spaceAfter=6))
        elements.append(tabela_rodape)
    else:
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=8, spaceAfter=6))
        elements.append(rodape_p1)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue(), hash_doc

def renderizar_aba_gerador_oficios(all_bens_banco, nome_militar_atual, unidade_militar_atual):
    """Aba interativa para emissão de Ofícios com seleção múltipla ou envio em bloco por REDS."""
    st.markdown("#### 📄 Gerador Oficial de Ofícios de Encaminhamento")
    st.caption("Emita expedientes oficiais de custódia contendo materiais de um único REDS ou múltiplos REDSs unificados.")

    if not all_bens_banco:
        st.info("Nenhum material cadastrado no banco para gerar ofício.")
        return

    # 1. MODO DE SELEÇÃO DE MATERIAIS
    st.markdown("**1. Seleção dos Materiais Relacionados**")
    modo_selecao = st.radio(
        "Como deseja selecionar os materiais?",
        ["📦 Envio em Bloco (Todos os materiais de um REDS)", "🔀 Seleção Múltipla Livre (Vários REDSs / Materiais Avulsos)"],
        horizontal=True
    )

    materiais_selecionados = []

    if "Envio em Bloco" in modo_selecao:
        reds_unicos = sorted(list(set([str(b.get("num_reds", "")) for b in all_bens_banco if b.get("num_reds")])))
        reds_escolhido = st.selectbox("Selecione o Número do REDS:", reds_unicos)
        
        if reds_escolhido:
            materiais_selecionados = [b for b in all_bens_banco if str(b.get("num_reds")) == reds_escolhido]
            st.success(f"Encontrado(s) {len(materiais_selecionados)} material(is) vinculado(s) ao REDS {reds_escolhido}.")
    else:
        bens_map = {
            f"REDS: {b['num_reds']} | {b['id_bem']} - {b['descricao']} (Autor: {b.get('autores', 'N/I')})": b 
            for b in all_bens_banco
        }
        chaves_sel = st.multiselect("Selecione um ou mais materiais (pode ser de REDSs diferentes):", list(bens_map.keys()))
        materiais_selecionados = [bens_map[k] for k in chaves_sel]

    if materiais_selecionados:
        st.markdown("**Pré-visualização da Tabela do Ofício:**")
        df_prev = pd.DataFrame(materiais_selecionados)
        st.dataframe(
            df_prev[["num_reds", "descricao", "involucro_lacre", "autores"]],
            column_config={
                "num_reds": "Nº REDS",
                "descricao": "Descrição do Material",
                "involucro_lacre": "Nº Lacre / Invólucro",
                "autores": "Nome do Autor"
            },
            hide_index=True,
            use_container_width=True
        )

    st.divider()

    # 2. DADOS DO DESTINATÁRIO
    st.markdown("**2. Dados do Destinatário / Autoridade**")
    
    preset_dest = st.selectbox(
        "Selecione um destinatário predefinido ou digite o seu:",
        [
            "EXCELENTÍSSIMO(A) SENHOR(A) JUIZ(A) DE DIREITO",
            "ILUSTRÍSSIMO(A) SENHOR(A) DELEGADO(A) REGIONAL DA POLÍCIA CIVIL",
            "✏️ Outra Autoridade / Digitação Livre"
        ]
    )

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        if preset_dest == "✏️ Outra Autoridade / Digitação Livre":
            destinatario_cargo = st.text_input("Cargo da Autoridade:", placeholder="Ex: PROMOTOR(A) DE JUSTIÇA").strip().upper()
        else:
            destinatario_cargo = preset_dest

        destinatario_nome = st.text_input("Nome da Autoridade / Destinatário:", placeholder="Ex: DR. MARCO ANTÔNIO SILVA").strip().upper()

    with col_d2:
        if "JUIZ" in destinatario_cargo:
            orgao_padrao = "JUIZADO ESPECIAL CRIMINAL (JECRIM) / FÓRUM"
        elif "DELEGADO" in destinatario_cargo:
            orgao_padrao = "DELEGACIA REGIONAL DE POLÍCIA CIVIL (PCMG)"
        else:
            orgao_padrao = "ÓRGÃO JUDICIÁRIO / POLICIAL"

        orgao_destino = st.text_input("Órgão / Destino:", value=orgao_padrao).strip().upper()

    st.divider()

    # 3. IDENTIFICAÇÃO DO EXPEDIENTE E CORPO DO TEXTO
    st.markdown("**3. Dados do Ofício e Texto do Expediente**")
    
    c_of1, c_of2 = st.columns(2)
    with c_of1:
        val_num_oficio = f"OFÍCIO {datetime.datetime.now().strftime('%Y%m%d')}-35CIA"
        num_oficio = st.text_input("Nº do Ofício:", value=val_num_oficio).strip().upper()
    with c_of2:
        pa_oficio = st.text_input("Nº do Processo Administrativo (P.A.) / Protocolo:", placeholder="Ex: P.A. 104/2026").strip().upper()

    reds_listados_str = ", ".join(sorted(list(set([str(m['num_reds']) for m in materiais_selecionados])))) if materiais_selecionados else "N/I"
    
    corpo_padrao = (
        f"Cumprimentando-o(a) cordialmente, encaminho a Vossa Excelência/Senhoria o(s) material(is) apreendido(s) "
        f"vinculado(s) ao(s) REDS Nº {reds_listados_str}, conforme discriminado na tabela acima, para as providências "
        f"de praxe relativas ao procedimento em epígrafe.\n\n"
        f"Ressalta-se que o(s) referido(s) bem(ns) encontra(m)-se devidamente acondicionado(s) em invólucro(s) inspecionado(s) "
        f"e registrado(s), garantindo a preservação da Cadeia de Custódia nos termos do Artigo 158-A e seguintes do Código de Processo Penal."
    )
    
    corpo_texto = st.text_area("Teor do Expediente:", value=corpo_padrao, height=150)

    st.divider()

    # 4. ASSINATURA E EMISSÃO
    st.markdown("**4. Emissor / Responsável**")
    c_em1, c_em2 = st.columns(2)
    with c_em1:
        emissor_nome = st.text_input("Nome Completo do Emissor:", value=str(nome_militar_atual)).strip().upper()
    with c_em2:
        emissor_cargo = st.text_input("Cargo / Função:", value="RESPONSÁVEL PELA CUSTÓDIA / CREDS").strip().upper()

    btn_gerar = st.button("🚀 Gerar e Baixar Ofício com QR Code (PDF)", type="primary", disabled=(not materiais_selecionados), use_container_width=True)

    if btn_gerar:
        if not destinatario_nome or not destinatario_cargo or not corpo_texto:
            st.error("⚠️ Preencha os campos de Destinatário e Teor do Expediente.")
        else:
            pdf_bytes, hash_sha = gerar_pdf_oficio(
                num_oficio=num_oficio,
                destinatario_nome=destinatario_nome,
                destinatario_cargo=destinatario_cargo,
                orgao_destino=orgao_destino,
                lista_materiais=materiais_selecionados,
                pa_oficio=pa_oficio,
                corpo_texto=corpo_texto,
                emissor_nome=emissor_nome,
                emissor_cargo=emissor_cargo,
                emissor_unidade=unidade_militar_atual
            )

            now_iso = datetime.datetime.now().isoformat()
            
            # Atualiza fase e processo de todos os materiais incluídos
            for m_item in materiais_selecionados:
                atualizar_material_supabase(m_item["id_bem"], {
                    "fase_destinacao": f"Encaminhado ({orgao_destino})",
                    "pa_oficio_autorizador": num_oficio
                })
                
                registrar_log_supabase({
                    "data_hora": now_iso,
                    "num_reds": m_item["num_reds"],
                    "bem_id": m_item["id_bem"],
                    "acao": "EMISSÃO DE OFÍCIO DE ENCAMINHAMENTO",
                    "origem": nome_militar_atual,
                    "unidade_origem": unidade_militar_atual,
                    "destino": orgao_destino,
                    "unidade_destino": "Órgão Externo",
                    "detalhe": f"Gerado {num_oficio} para {destinatario_nome}. SHA-256: {hash_sha}"
                })

            st.success("✅ Ofício gerado com sucesso com QR Code de Autenticidade!")
            st.download_button(
                label="📥 Clique para Baixar o Ofício (PDF)",
                data=pdf_bytes,
                file_name=f"{num_oficio.replace(' ', '_')}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )