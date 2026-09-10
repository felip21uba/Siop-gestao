import io
import pandas as pd
import zipfile
import xml.etree.ElementTree as ET

def carregar_planilha_universal(file_bytes_or_uploaded_file):
    """
    Leitor universal de planilhas Excel (XLSX padrão, XLSX Strict OpenXML da PMMG, XLS e CSV).
    Garante o suporte completo aos arquivos exportados pelos sistemas corporativos PMMG/REDS.
    """
    if hasattr(file_bytes_or_uploaded_file, 'getvalue'):
        content = file_bytes_or_uploaded_file.getvalue()
    elif isinstance(file_bytes_or_uploaded_file, bytes):
        content = file_bytes_or_uploaded_file
    else:
        with open(file_bytes_or_uploaded_file, 'rb') as f:
            content = f.read()

    # 1. Tenta pandas / openpyxl padrão
    try:
        df = pd.read_excel(io.BytesIO(content))
        if not df.empty and len(df.columns) > 1:
            return df
    except Exception:
        pass

    # 2. Parser nativo para 'Strict OpenXML' (PMMG/REDS)
    try:
        with zipfile.ZipFile(io.BytesIO(content), 'r') as z:
            if 'xl/sharedStrings.xml' in z.namelist() and 'xl/worksheets/sheet1.xml' in z.namelist():
                ss_data = z.read('xl/sharedStrings.xml')
                ss_root = ET.fromstring(ss_data)
                ns = {'s': 'http://purl.oclc.org/ooxml/spreadsheetml/main'}
                
                strings = []
                for si in ss_root.findall('.//s:si', ns):
                    t_elems = si.findall('.//s:t', ns)
                    strings.append("".join([t.text for t in t_elems if t.text]))
                    
                sheet_data = z.read('xl/worksheets/sheet1.xml')
                sheet_root = ET.fromstring(sheet_data)
                
                rows = []
                for r in sheet_root.findall('.//s:row', ns):
                    row_dict = {}
                    for c in r.findall('s:c', ns):
                        ref = c.get('r')
                        col = "".join([char for char in ref if char.isalpha()])
                        t_type = c.get('t')
                        v_elem = c.find('s:v', ns)
                        val = v_elem.text if v_elem is not None else ""
                        if t_type == 's' and val != "":
                            val = strings[int(val)]
                        row_dict[col] = val
                    rows.append(row_dict)
                    
                df_strict = pd.DataFrame(rows)
                if not df_strict.empty:
                    df_strict.columns = df_strict.iloc[0]
                    df_strict = df_strict.iloc[1:].reset_index(drop=True)
                    return df_strict
    except Exception:
        pass

    # 3. Fallback para CSV
    try:
        return pd.read_csv(io.BytesIO(content), encoding='utf-8', sep=None, engine='python')
    except Exception:
        try:
            return pd.read_csv(io.BytesIO(content), encoding='latin1', sep=None, engine='python')
        except Exception:
            return pd.DataFrame()