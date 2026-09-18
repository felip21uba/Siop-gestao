import streamlit as st
import datetime
import re
import uuid
import pandas as pd
from core.database import supabase

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # Limite rígido de 5MB

def validar_e_sanitizar_pdf_bytes(file_bytes):
    """Inspeção de segurança contra uploads maliciosos (Magic Bytes, tamanho e scripts)."""
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
    """Previne CSV/Formula Injection e remove caracteres nulos."""
    if not texto: return ""
    s = str(texto).strip()
    if s.startswith(('=', '+', '-', '@')): s = "'" + s
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s).upper()

def extrair_registros_ferias_texto(texto_bruto):
    """Suporta padrões como '10 dias a partir de 02/02/2027' ou '02/02/2027 a 12/02/2027'."""
    registros = []
    linhas = texto_bruto.split("\n")

    for linha in linhas:
        linha_clean = sanitizar_texto(linha)
        if not linha_clean: continue

        m_num = re.search(r'\b\d{6,7}\b', linha_clean)
        num_pol = m_num.group(0) if m_num else "N/I"

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
            registros.append({
                "id": uuid.uuid4().hex[:8],
                "num_policia": num_pol,
                "linha_bruta": linha_clean,
                "dt_inicio": dt_i.strftime("%d/%m/%Y"),
                "dt_fim": dt_f.strftime("%d/%m/%Y"),
                "ano": dt_i.year,
                "mes": dt_i.month
            })

    return registros

def carregar_ferias_anual_banco():
    if "plano_ferias_anual" not in st.session_state:
        st.session_state["plano_ferias_anual"] = []
        if supabase:
            try:
                res = supabase.table("configuracoes_sistema").select("valor").eq("chave", "plano_ferias_anual").execute()
                if res.data and len(res.data) > 0:
                    import json
                    st.session_state["plano_ferias_anual"] = json.loads(res.data[0]["valor"])
            except Exception: pass

def salvar_ferias_anual_banco():
    if supabase:
        try:
            import json
            supabase.table("configuracoes_sistema").upsert({
                "chave": "plano_ferias_anual",
                "valor": json.dumps(st.session_state["plano_ferias_anual"])
            }).execute()
        except Exception: pass

def renderizar_modulo_ferias_anual():
    carregar_ferias_anual_banco()

    st.markdown("### 🏖️ Mapeamento Anual de Férias & Indisponibilidade")
    st.caption("Cadastre ou importe o plano anual. O Passo 5 consultará esta base para preencher 'FE' e aplicar o bloqueio de véspera.")

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
            st.markdown("##### 🔍 Confirme os registros para salvar no Mapeamento Anual:")
            df_temp = pd.DataFrame(st.session_state["temp_ferias_extraidas"])[["num_policia", "dt_inicio", "dt_fim", "linha_bruta"]]
            st.dataframe(df_temp, use_container_width=True, hide_index=True)
            
            if st.button("💾 Gravar no Mapeamento Anual do Banco", type="primary", use_container_width=True):
                st.session_state["plano_ferias_anual"].extend(st.session_state["temp_ferias_extraidas"])
                salvar_ferias_anual_banco()
                st.session_state.pop("temp_ferias_extraidas", None)
                st.success("✅ Férias salvas no banco!")
                st.rerun()

    st.divider()
    st.markdown("#### 🔍 Consulta do Mapeamento Anual")

    c_f1, c_f2, c_f3 = st.columns(3)
    with c_f1: ano_sel = st.number_input("Ano:", min_value=2024, max_value=2035, value=st.session_state.get("ano_escala", datetime.date.today().year))
    with c_f2:
        meses_nomes = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        mes_filtro = st.selectbox("Mês:", meses_nomes)
    with c_f3: busca_militar = st.text_input("Buscar Militar / Nº Polícia:", placeholder="Digite nome ou número...").strip().upper()

    plano_lista = st.session_state.get("plano_ferias_anual", [])
    if plano_lista:
        df_p = pd.DataFrame(plano_lista)
        if ano_sel: df_p = df_p[df_p["ano"] == ano_sel]
        if mes_filtro != "Todos": df_p = df_p[df_p["mes"] == meses_nomes.index(mes_filtro)]
        if busca_militar: df_p = df_p[df_p["linha_bruta"].str.contains(busca_militar, na=False) | df_p["num_policia"].str.contains(busca_militar, na=False)]

        st.markdown(f"📊 **{len(df_p)} registro(s) localizado(s):**")
        df_p["Excluir"] = False
        df_edit = st.data_editor(
            df_p[["num_policia", "dt_inicio", "dt_fim", "linha_bruta", "Excluir"]],
            column_config={
                "num_policia": "Nº Polícia",
                "dt_inicio": "Data Início",
                "dt_fim": "Data Fim",
                "linha_bruta": "Detalhamento",
                "Excluir": st.column_config.CheckboxColumn("🗑️ Remover")
            },
            hide_index=True,
            use_container_width=True,
            key="editor_plano_anual_ferias"
        )

        if any(df_edit["Excluir"]):
            indices_manter = [i for i in range(len(df_edit)) if not df_edit.iloc[i]["Excluir"]]
            st.session_state["plano_ferias_anual"] = [st.session_state["plano_ferias_anual"][idx] for idx in indices_manter]
            salvar_ferias_anual_banco()
            st.success("Atualizado!")
            st.rerun()
    else: st.info("Nenhuma férias cadastrada para o período selecionado.")