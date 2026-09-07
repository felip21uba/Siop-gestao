import io
import zipfile
import pandas as pd
import xml.etree.ElementTree as ET

def carregar_planilha_universal(arquivo_upload) -> pd.DataFrame:
    """
    Lê arquivos Excel (.xlsx, .xls) ou CSV de forma robusta.
    Possui fallback com parser XML caso o openpyxl falhe em planilhas corrompidas.
    """
    bytes_data = arquivo_upload.read()
    arquivo_upload.seek(0)
    nome_arquivo = arquivo_upload.name.lower()

    if nome_arquivo.endswith('.csv'):
        try:
            return pd.read_csv(io.BytesIO(bytes_data))
        except Exception:
            return pd.read_csv(io.BytesIO(bytes_data), encoding='latin1', sep=None, engine='python')

    try:
        return pd.read_excel(io.BytesIO(bytes_data))
    except Exception:
        pass

    try:
        return pd.read_excel(io.BytesIO(bytes_data), engine='xlrd')
    except Exception:
        pass

    # Fallback via XML para planilhas geradas por sistemas antigos
    try:
        with zipfile.ZipFile(io.BytesIO(bytes_data), 'r') as z:
            strings_xml = z.read('xl/sharedStrings.xml')
            tree_s = ET.fromstring(strings_xml)
            shared_strings = [t.text for t in tree_s.iter() if t.tag.endswith('t') and t.text is not None]

            sheet_xml = z.read('xl/worksheets/sheet1.xml')
            tree_sheet = ET.fromstring(sheet_xml)

            rows = []
            for row in tree_sheet.iter():
                if row.tag.endswith('row'):
                    r_vals = []
                    for cell in row.iter():
                        if cell.tag.endswith('c'):
                            val_text = None
                            for child in cell:
                                if child.tag.endswith('v'):
                                    val_text = child.text
                            if val_text is not None:
                                if cell.attrib.get('t') == 's':
                                    idx_s = int(val_text)
                                    val_text = shared_strings[idx_s] if idx_s < len(shared_strings) else val_text
                                r_vals.append(val_text)
                    if r_vals:
                        rows.append(r_vals)

            if rows:
                return pd.DataFrame(rows[1:], columns=rows[0])
    except Exception as e:
        raise Exception(f"Erro ao processar estrutura da planilha: {e}")

    raise Exception("Formato de arquivo não reconhecido.")