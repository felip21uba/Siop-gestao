import streamlit as st
import pandas as pd
from core.database import supabase

def renderizar_aba_trilha_auditoria():
    st.markdown("##### 📜 Trilha Universal de Auditoria Imutável (Supabase)")
    st.caption("Acesso centralizado a todos os eventos de movimentação, acessos e alterações no SIOP.")

    with st.expander("🔍 **Filtros Avançados de Pesquisa**", expanded=True):
        fl1, fl2, fl3 = st.columns(3)
        with fl1:
            f_reds = st.text_input("Nº do REDS:", placeholder="Ex: 2026-000484967", key="gov_f_reds").strip()
        with fl2:
            f_kw = st.text_input("Palavra-chave / Ação:", placeholder="Ex: DIVERGÊNCIA, DESIGNAÇÃO", key="gov_f_kw").strip()
        with fl3:
            f_operador = st.text_input("Operador Envolvido:", placeholder="Ex: OLIVEIRA ALVES", key="gov_f_op").strip()

    logs_data = []
    if supabase:
        try:
            res_l = supabase.table("tco_logs").select("*").order("data_hora", desc=True).limit(100).execute()
            logs_data = res_l.data or []
        except Exception:
            pass

    if logs_data:
        df_logs = pd.DataFrame(logs_data)
        
        # Trata a formatação de data/hora prevenindo NaT e mantendo DD/MM/AAAA HH:MM
        if "data_hora" in df_logs.columns and not df_logs.empty:
            df_logs["data_hora"] = df_logs["data_hora"].apply(
                lambda x: pd.to_datetime(x).strftime("%d/%m/%Y %H:%M") if pd.notna(x) and str(x).strip() not in ["", "None", "NaT"] else "N/I"
            )

        if f_reds:
            df_logs = df_logs[df_logs["num_reds"].astype(str).str.contains(f_reds, case=False, na=False)]
        if f_kw:
            df_logs = df_logs[df_logs["acao"].astype(str).str.contains(f_kw, case=False, na=False) | df_logs["detalhe"].astype(str).str.contains(f_kw, case=False, na=False)]
        if f_operador:
            df_logs = df_logs[df_logs["origem"].astype(str).str.contains(f_operador, case=False, na=False) | df_logs["destino"].astype(str).str.contains(f_operador, case=False, na=False)]

        cols_exib = ["data_hora", "num_reds", "bem_id", "acao", "origem", "unidade_origem", "destino", "unidade_destino", "detalhe"]
        cols_presentes = [c for c in cols_exib if c in df_logs.columns]
        
        st.dataframe(df_logs[cols_presentes], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum log de auditoria encontrado.")