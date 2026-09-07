import re
import pypdf

def extrair_cabecalho_reds(texto_completo):
    # N° REDS
    m_reds = re.search(r'N[°º]\s*(\d{4}-\d{9}-\d{3})', texto_completo)
    num_reds = m_reds.group(1).strip() if (m_reds and m_reds.group(1)) else "N/A"

    # DATA DO REGISTRO
    header_block = texto_completo[:2000]
    m_reg = re.search(
        r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})[\s\S]{0,50}?DATA\s+DO\s+REGISTRO|DATA\s+DO\s+REGISTRO[\s\S]{0,50}?(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})', 
        header_block, 
        re.IGNORECASE
    )
    data_registro = "Data N/I"
    if m_reg:
        data_registro = (m_reg.group(1) or m_reg.group(2) or "Data N/I").strip()

    # DATA DO FATO
    idx_oc = texto_completo.find("DADOS DA OCORRÊNCIA")
    if idx_oc == -1: 
        idx_oc = texto_completo.find("DADOS DA OCORRENCIA")
    idx_env = texto_completo.find("QUALIFICAÇÃO DOS ENVOLVIDOS")
    if idx_env == -1: 
        idx_env = idx_oc + 1500 if idx_oc != -1 else 2000

    bloco_oc = texto_completo[idx_oc:idx_env] if idx_oc != -1 else header_block
    m_fato = re.search(r'\b(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})\b', bloco_oc)
    data_fato = m_fato.group(1).strip() if (m_fato and m_fato.group(1)) else data_registro

    # LOCAL
    rua = re.search(r'LOCAL \(AV\., RUA, ETC\)\s*\n\s*([^\n]+)', texto_completo, re.IGNORECASE)
    num = re.search(r'(?:NÚMERO|NUMERO)\s*\n\s*([^\n]+)', texto_completo, re.IGNORECASE)
    bairro = re.search(r'BAIRRO/VILA\s*\n\s*([^\n]+)', texto_completo, re.IGNORECASE)
    municipio = re.search(r'(?:MUNICÍPIO|MUNICIPIO)\s*\n\s*([^\n]+)', texto_completo, re.IGNORECASE)
    
    r_val = rua.group(1).strip() if (rua and rua.group(1)) else ""
    n_val = num.group(1).strip() if (num and num.group(1)) else ""
    b_val = bairro.group(1).strip() if (bairro and bairro.group(1)) else ""
    m_val = municipio.group(1).strip() if (municipio and municipio.group(1)) else "MG"

    r_str = r_val if r_val.upper() != "XXXX" else "S/N"
    n_str = n_val if n_val.upper() != "XXXX" else ""
    b_str = b_val if b_val.upper() != "XXXX" else "BAIRRO N/I"
    m_str = m_val if m_val.upper() != "XXXX" else "MG"
    
    local_str = f"{r_str} {n_str}, Bairro {b_str}, {m_str}".replace("  ", " ").strip()

    # NATUREZA PRINCIPAL
    m_nat = re.search(r'PROVÁVEL\s+DESCRIÇÃO\s+DA\s+OCORRÊNCIA\s+PRINCIPAL\s*\n\s*([^\n]+)', texto_completo, re.IGNORECASE)
    raw_nat = m_nat.group(1).strip() if (m_nat and m_nat.group(1)) else "OCORRÊNCIA POLICIAL"
    
    nat_limpa = re.sub(r'^[A-Z0-9]+\s*[-–]\s*', '', raw_nat, flags=re.IGNORECASE)
    nat_limpa = re.sub(r'\b(XXXX|TENTADO|CONSUMADO)\b', '', nat_limpa, flags=re.IGNORECASE).strip()

    return {
        "num_reds": num_reds,
        "data_registro": data_registro,
        "data_fato": data_fato,
        "natureza": nat_limpa if nat_limpa else "OCORRÊNCIA POLICIAL",
        "local": local_str
    }

def extrair_mapa_envolvidos(texto_busca):
    mapa = {}
    blocos = re.split(r'ENVOLVIDO\s+(\d+)', texto_busca, flags=re.IGNORECASE)
    
    for i in range(1, len(blocos), 2):
        num_env = blocos[i].strip()
        conteudo = blocos[i+1]
        
        m_nome = re.search(r'NOME\s+COMPLETO\s*\n\s*([^\n]+)', conteudo, re.IGNORECASE)
        m_tipo = re.search(r'TIPO\s+ENVOLVIMENTO\s*\n\s*([^\n]+)', conteudo, re.IGNORECASE)
        
        nome = m_nome.group(1).strip() if (m_nome and m_nome.group(1)) else ""
        nome_clean = re.sub(r'\bXXXX\b', '', nome, flags=re.IGNORECASE).strip()
        
        tipo = m_tipo.group(1).strip() if (m_tipo and m_tipo.group(1)) else "ENVOLVIDO"
        tipo_clean = re.sub(r'\bXXXX\b', '', tipo, flags=re.IGNORECASE).strip()
        
        if nome_clean and nome_clean.upper() != "XXXX":
            mapa[num_env] = {
                "nome": nome_clean,
                "qualificacao": tipo_clean if tipo_clean else "ENVOLVIDO"
            }
            
    return mapa

def extrair_relator_completo(texto_completo):
    m_rel = re.search(
        r'DADOS PARA CONTROLE INTERNO/RELATOR DA OCORRÊNCIA[\s\S]*?MATRÍCULA\s*\n\s*(\d+)[\s\S]*?CARGO\s*\n\s*([^\n]+)[\s\S]*?NOME COMPLETO\s*\n\s*([^\n]+)',
        texto_completo,
        re.IGNORECASE
    )
    if m_rel and m_rel.group(1) and m_rel.group(2) and m_rel.group(3):
        return f"{m_rel.group(2).strip()} PM {m_rel.group(1).strip()} - {m_rel.group(3).strip()}"
    
    m_dig = re.search(r'DIGITADOR:\s*PM(\d+)', texto_completo, re.IGNORECASE)
    mat_target = m_dig.group(1).strip() if (m_dig and m_dig.group(1)) else None
    
    if mat_target:
        m_int = re.search(
            r'MATRÍCULA\s*\n\s*' + mat_target + r'[\s\S]*?CARGO\s*\n\s*([^\n]+)[\s\S]*?NOME COMPLETO\s*\n\s*([^\n]+)',
            texto_completo,
            re.IGNORECASE
        )
        if m_int and m_int.group(1) and m_int.group(2):
            return f"{m_int.group(1).strip()} PM {mat_target} - {m_int.group(2).strip()}"

        m_int_alt = re.search(
            r'NOME COMPLETO\s*\n\s*([^\n]+)[\s\S]*?MATRÍCULA\s*\n\s*' + mat_target + r'[\s\S]*?CARGO\s*\n\s*([^\n]+)',
            texto_completo,
            re.IGNORECASE
        )
        if m_int_alt and m_int_alt.group(1) and m_int_alt.group(2):
            return f"{m_int_alt.group(2).strip()} PM {mat_target} - {m_int_alt.group(1).strip()}"
            
        return f"POLICIAL MILITAR PM {mat_target}"
    
    return "RELATOR NÃO IDENTIFICADO"

def extrair_recibo_jecrim(texto_completo):
    m_recibo = re.search(
        r'PODER JUDICIARIO[\s\S]*?UNIDADE\s*\n\s*([^\n]+)[\s\S]*?ITENS ENTREGUES A ESTE DESTINATÁRIO([\s\S]*?)(?=RECIBO|FIM DO AUTO|FIM DOS ANEXOS|HISTÓRICO|$)', 
        texto_completo, 
        re.IGNORECASE
    )
    
    unidade_jecrim = "JECRIM"
    mat_ids = []
    
    if m_recibo:
        unidade_jecrim = m_recibo.group(1).strip() if m_recibo.group(1) else "JECRIM"
        bloco_itens = m_recibo.group(2) if m_recibo.group(2) else ""
        mat_ids = re.findall(r'MATERIAIS\s+(\d+)', bloco_itens, re.IGNORECASE)
        
    return unidade_jecrim, mat_ids

def extrair_materiais_transcritos(texto_busca, mat_ids, mapa_envolvidos):
    materiais = []
    itens_processados = set()
    
    padrao_bloco = re.compile(
        r'MATERIAL\s+(\d+)\s*\n([\s\S]*?)(?=MATERIAL\s+\d+|HISTÓRICO|HISTORICO|VIATURAS|RECIBO|AUTO\s+DE|$)', 
        re.IGNORECASE
    )
    matches = padrao_bloco.finditer(texto_busca)
    
    for m in matches:
        item_num = m.group(1).strip()
        bloco_texto = m.group(2)
        
        if mat_ids and item_num not in mat_ids:
            continue
            
        if item_num in itens_processados:
            continue
        itens_processados.add(item_num)

        lines = [line.strip() for line in bloco_texto.split('\n') if line.strip()]
        
        objeto = "MATERIAL DIVERSO"
        quantidade = 1.0
        unidade = "UNIDADE"
        info_comp = ""
        situacao = "APREENDIDO"
        env_nr = "1"
        involucro_encontrado = None

        m_env = re.search(r'ENVOLV\.?\s*NR\s*\n\s*(\d+)', bloco_texto, re.IGNORECASE)
        if m_env and m_env.group(1):
            env_nr = m_env.group(1).strip()

        dados_env = mapa_envolvidos.get(env_nr, {"nome": f"ENVOLVIDO {env_nr}", "qualificacao": "AUTOR"})
        autor_str = f"{dados_env['nome']} ({dados_env['qualificacao']})"

        for idx, line in enumerate(lines):
            line_u = line.upper()
            
            if "SITUAÇÃO" in line_u and "QUANTIDADE" in line_u:
                if idx + 1 < len(lines):
                    val_line = lines[idx + 1]
                    parts = val_line.split()
                    for p_idx, p in enumerate(parts):
                        if p.upper() in ["APREENDIDO", "RECOLHIDO"]:
                            situacao = p.upper()
                            if p_idx + 1 < len(parts):
                                try:
                                    quantidade = float(parts[p_idx + 1].replace(',', '.'))
                                except ValueError:
                                    pass
                            if p_idx + 2 < len(parts):
                                u_tmp = parts[p_idx + 2].upper()
                                if u_tmp != "XXXX":
                                    unidade = u_tmp

            elif line_u.startswith("OBJETO"):
                if idx + 1 < len(lines):
                    obj_clean = re.sub(r'\bXXXX\b', '', lines[idx + 1], flags=re.IGNORECASE).strip()
                    if obj_clean:
                        objeto = obj_clean

            elif "SERIE" in line_u or "SÉRIE" in line_u or "IDENTIFICAÇÃO" in line_u or "IDENTIFICACAO" in line_u:
                if idx + 1 < len(lines):
                    inv_line = lines[idx + 1]
                    inv_parts = inv_line.split()
                    if inv_parts and inv_parts[0].upper() != "XXXX":
                        involucro_encontrado = inv_parts[0].strip()

            elif "INFORMAÇÕES COMPLEMENTARES" in line_u or "INFORMACOES COMPLEMENTARES" in line_u:
                if idx + 1 < len(lines):
                    info_clean = re.sub(r'\bXXXX\b', '', lines[idx + 1], flags=re.IGNORECASE).strip()
                    if info_clean:
                        info_comp = info_clean

        if not involucro_encontrado:
            m_inv_text = re.search(r'(?:NUMERO\s+)?(?:INVOLUCRO|INVÓLUCRO|LACRE|ENVELOPE)\s*(?:N[°º#]?)?\s*([A-Z0-9-]+)', bloco_texto, re.IGNORECASE)
            if m_inv_text and m_inv_text.group(1) and m_inv_text.group(1).strip().upper() != "XXXX":
                involucro_encontrado = m_inv_text.group(1).strip()

        involucro_final = involucro_encontrado if involucro_encontrado else f"SEM LACRE (ITEM {item_num})"
        info_comp_limpa = re.sub(r'(?:NUMERO\s+)?(?:INVOLUCRO|INVÓLUCRO|LACRE|ENVELOPE)\s*(?:N[°º#]?)?\s*[A-Z0-9-]+', '', info_comp, flags=re.IGNORECASE).strip()

        if objeto.upper() in ["OUTROS OBJETOS (DISCRIMINAR NO HISTORICO)", "MATERIAL DIVERSO", "OUTROS OBJETOS"]:
            descricao_final = info_comp_limpa if info_comp_limpa else objeto
        elif info_comp_limpa and info_comp_limpa.upper() != objeto.upper():
            descricao_final = f"{objeto} ({info_comp_limpa})"
        else:
            descricao_final = objeto

        materiais.append({
            "item_num": item_num,
            "env_nr": env_nr,
            "autor": autor_str,
            "situacao": situacao,
            "descricao": descricao_final,
            "quantidade": quantidade,
            "unidade": unidade,
            "involucro": involucro_final,
            "destinatario_reds": "JECRIM"
        })
        
    return materiais

def extrair_dados_reds_pdf(pdf_file_bytes):
    reader = pypdf.PdfReader(pdf_file_bytes)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += (page.extract_text() or "") + "\n"

    partes_texto = re.split(r'HISTÓRICO DA OCORRÊNCIA|HISTORICO DA OCORRENCIA', texto_completo, flags=re.IGNORECASE)
    texto_busca = partes_texto[0] if partes_texto else texto_completo
    texto_historico = partes_texto[1] if len(partes_texto) > 1 else ""

    cabecalho = extrair_cabecalho_reds(texto_completo)
    redator = extrair_relator_completo(texto_completo)
    unidade_jecrim, mat_ids = extrair_recibo_jecrim(texto_completo)
    mapa_envolvidos = extrair_mapa_envolvidos(texto_busca)
    
    materiais = extrair_materiais_transcritos(texto_busca, mat_ids, mapa_envolvidos)
    
    autores_encontrados = list(set([m["autor"] for m in materiais])) if materiais else ["AUTOR NÃO IDENTIFICADO"]
    resumo_fato = texto_historico.strip().replace("\n", " ")[:250] + "..." if texto_historico else "Resumo indisponível."

    return {
        "num_reds": cabecalho["num_reds"],
        "data_registro": cabecalho["data_registro"],
        "data_fato": cabecalho["data_fato"],
        "natureza": cabecalho["natureza"],
        "local": cabecalho["local"],
        "redator": redator,
        "unidade_jecrim": unidade_jecrim,
        "autores": autores_encontrados,
        "resumo_fato": resumo_fato,
        "materiais": materiais
    }