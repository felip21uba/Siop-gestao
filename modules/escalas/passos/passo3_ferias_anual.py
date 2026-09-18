import streamlit as st
import datetime
import re
import pandas as pd
from core.database import supabase

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # Limite de 5MB

def validar_e_sanitizar_pdf_bytes(file_bytes):
    """Verificação de segurança contra uploads maliciosos."""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return False, "🚨 Arquivo excede o tamanho máximo permitido de 5MB."
    if not file_bytes.startswith(b"%PDF-"):
        return False, "🚨 Arquivo inválido. O cabeçalho binário não corresponde a um PDF autêntico."

    padroes_maliciosos = [b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/OpenAction"]
    for p in padroes_maliciosos:
        if p in file_bytes:
            return False, "🚨 Arquivo bloqueado pelas travas de segurança: contém scripts executáveis."
    return True, "OK"

def sanitizar_texto(texto):
    if not texto: return ""
    s = str(texto).strip()
    if s.startswith(('=', '+', '-', '@')): s = "'" + s
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s).upper()

def extrair_registros_ferias_texto(texto_bruto):
    """Extrai férias a partir de padrões como '10 dias a partir de 02/02/2027' ou '02/02/2027 a 12/02/2027'."""
    registros = []
    linhas = texto_bruto.split("\n")

    for linha in linhas:
        linha_clean = sanitizar_texto(linha)
        if not linha_clean: continue

        m_num = re.search(r'\b\d{6,7}\b', linha_clean)
        num_pol = m_num.group(0) if m_num else ""

        m_intervalo = re.search(r'(\d{2}/\d{2}/\d{4})\s*(?:A|À|-|ATE)\s*(\d{2}/\d{2}/\d{4})', linha_clean)
        m_dias_partir = re.search(r'(\d+)\s*DIAS?\s*(?:A\s*PARTIR\s*DE|A\s*CONTAR\s*DE)\s*(\d{2}/\d{2}/\d{4})', linha_clean)

        dt_i, dt_f = None, None

        if m_intervalo:
            try:
                dt_i = datetime.datetime.strptime(m_intervalo.group(1), "%d/%m/%Y").date()
                dt_f = datetime.datetime.strptime(m_intervalo.group(2), "%d/%m/%Y").date()
            except ValueError: pass
        elif m_dias_partir:
            try:
                qtd_dias = int(m_dias_partir.group(1))
                dt_i = datetime.datetime.strptime(m_dias_partir.group(2), "%d/%m/%Y").date()
                dt_f = dt_i + datetime.timedelta(days=qtd_dias - 1)
            except ValueError: pass

        if dt_i and dt_f:
            qtd_dias_calculada = (dt_f - dt_i).days + 1
            registros.append({
                "num_policia": num_pol,
                "nome_militar": linha_clean[:60],
                "dt_inicio": dt_i.strftime("%d/%m/%Y"),
                "dt_fim": dt_f.strftime("%d/%m/%Y"),
                "dias_qtd": qtd_dias_calculada,
                "ano": dt_i.year,
                "mes": dt_i.month,
                "nota_publicacao": linha_clean
            })
    return registros

def salvar_ferias_supabase_lote(lista_registros):
    if supabase and lista_registros:
        try:
            # Converter DD/MM/YYYY para YYYY-MM-DD para compatibilidade SQL
            registros_db = []
            for r in lista_registros:
                item = r.copy()
                item["dt_inicio"] = datetime.datetime.strptime(r["dt_inicio"], "%d/%m/%Y").strftime("%Y-%m-%d")
                item["dt_fim"] = datetime.datetime.strptime(r["dt_fim"], "%d/%m/%Y").strftime("%Y-%m-%d")
                registros_db.append(item)
                
            supabase.table("plano_ferias_anual").insert(registros_db).execute()
            return True, "✅ Registros salvos com sucesso no Supabase!"
        except Exception as ex:
            return False, f"Erro ao salvar no banco: {ex}"
    return False, "Banco Supabase indisponível."

def carregar_ferias_supabase(ano=None, mes=None, busca=""):
    if not supabase: return []
    try:
        query = supabase.table("plano_ferias_anual").select("*")
        if ano: query = query.eq("ano", ano)
        if mes and mes != 0: query = query.eq("mes", mes)
        res = query.order("dt_inicio").execute()
        
        dados = res.data or []
        for d in dados:
            if d.get("dt_inicio") and "-" in str(d["dt_inicio"]):
                d["dt_inicio"] = datetime.datetime.strptime(str(d["dt_inicio"]), "%Y-%m-%d").strftime("%d/%m/%Y")
            if d.get("dt_fim") and "-" in str(d["dt_fim"]):
                d["dt_fim"] = datetime.datetime.strptime(str(d["dt_fim"]), "%Y-%m-%d").strftime("%d/%m/%Y")

        if busca:
            dados = [d for d in dados if busca in str(d.get("num_policia", "")) or busca in str(d.get("nota_publicacao", "")).upper()]
        return dados
    except Exception: return []

def renderizar_modulo_ferias_anual():
    st.markdown("### 🏖️ PASSO 8: Mapeamento Anual de Férias & Indisponibilidade")
    st.caption("Cadastre ou importe a escala anual de férias. O Passo 5 verificará automaticamente estes registros e bloqueará serviços na véspera.")

    with st.expander("📥 Importação Segura via PDF ou Texto Copiado", expanded=False):
        c_up1, c_up2 = st.columns(2)
        
        with c_up1:
            st.markdown("**Upload de Documento PDF:**")
            arq_pdf = st.file_uploader("Selecione o arquivo PDF:", type=["pdf"], key="uploader_pdf_ferias_anual")
            if arq_pdf is not None:
                bytes_pdf = arq_pdf.read()
                is_valido, msg_val = validar_e_sanitizar_pdf_bytes(bytes_pdf)
                if not is_valido:
                    st.error(msg_val)
                else:
                    st.success("✅ Arquivo aprovado nas travas de segurança!")
                    if st.button("🚀 Extrair Férias do PDF", type="primary", use_container_width=True):
                        try:
                            import pypdf
                            reader = pypdf.PdfReader(arq_pdf)
                            texto_extraido = "".join([(page.extract_text() or "") + "\n" for page in reader.pages])
                            regs = extrair_registros_ferias_texto(texto_extraido)
                            if regs:
                                st.session_state["temp_ferias_extraidas"] = regs
                                st.success(f"✅ {len(regs)} registro(s) identificados!")
                            else: st.warning("Nenhum padrão localizado no PDF.")
                        except Exception as ex: st.error(f"Erro ao ler PDF: {ex}")

        with c_up2:
            st.markdown("**Cole o Texto da Nota / Publicação:**")
            txt_area = st.text_area("Cole as linhas aqui:", placeholder="Ex: 1234567 SD SILVA - 10 DIAS A PARTIR DE 02/02/2027", height=120)
            if st.button("⚡ Processar Texto Copiado", use_container_width=True):
                regs = extrair_registros_ferias_texto(txt_area)
                if regs:
                    st.session_state["temp_ferias_extraidas"] = regs
                    st.success(f"✅ {len(regs)} registro(s) identificados!")
                else: st.warning("Nenhum padrão reconhecido.")

        if st.session_state.get("temp_ferias_extraidas"):
            st.divider()
            st.markdown("##### 🔍 Confirme os registros antes de gravar no Supabase:")
            df_temp = pd.DataFrame(st.session_state["temp_ferias_extraidas"])[["num_policia", "dt_inicio", "dt_fim", "dias_qtd", "nota_publicacao"]]
            st.dataframe(df_temp, use_container_width=True, hide_index=True)
            
            if st.button("💾 Gravar no Mapeamento Anual do Banco", type="primary", use_container_width=True):
                ok, msg = salvar_ferias_supabase_lote(st.session_state["temp_ferias_extraidas"])
                if ok:
                    st.session_state.pop("temp_ferias_extraidas", None)
                    st.success(msg)
                    st.rerun()
                else: st.error(msg)

    st.divider()
    st.markdown("#### 🔍 Consulta do Mapeamento Anual")

    c_f1, c_f2, c_f3 = st.columns(3)
    ano_sel = c_f1.number_input("Ano:", min_value=2024, max_value=2035, value=st.session_state.get("ano_escala", datetime.date.today().year))
    meses_nomes = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_filtro_nome = c_f2.selectbox("Mês:", meses_nomes)
    mes_num = meses_nomes.index(mes_filtro_nome)
    busca_militar = c_f3.text_input("Buscar Militar / Nº Polícia:", placeholder="Digite o número ou nota...").strip().upper()

    registros_banco = carregar_ferias_supabase(ano=ano_sel, mes=mes_num, busca=busca_militar)

    if registros_banco:
        df_p = pd.DataFrame(registros_banco)
        st.markdown(f"📊 **{len(df_p)} registro(s) localizado(s):**")
        df_p["Excluir"] = False
        df_edit = st.data_editor(
            df_p[["id", "num_policia", "dt_inicio", "dt_fim", "dias_qtd", "nota_publicacao", "Excluir"]],
            column_config={
                "id": None,
                "num_policia": "Nº Polícia",
                "dt_inicio": "Data Início (DD/MM/YYYY)",
                "dt_fim": "Data Fim (DD/MM/YYYY)",
                "dias_qtd": "Dias",
                "nota_publicacao": "Nota / Publicação",
                "Excluir": st.column_config.CheckboxColumn("🗑️ Remover")
            },
            hide_index=True, use_container_width=True, key="editor_plano_anual_ferias"
        )

        if any(df_edit["Excluir"]):
            ids_deletar = df_edit[df_edit["Excluir"]]["id"].tolist()
            if supabase and ids_deletar:
                for id_del in ids_deletar:
                    supabase.table("plano_ferias_anual").delete().eq("id", id_del).execute()
                st.success("Registro(s) removido(s) com sucesso!")
                st.rerun()
    else: st.info("Nenhuma férias cadastrada no banco para o período selecionado.")