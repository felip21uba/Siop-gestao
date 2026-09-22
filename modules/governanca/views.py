import streamlit as st
import pandas as pd
import datetime
import io
import openpyxl
from core.database import supabase

def renderizar_modulo_governanca(nome_operador="OPERADOR", unidade_operador="21º BPM", cargo_operador="MILITAR", perfil_operador="ADMIN"):
    """Renderiza a Central de Governança, Conformidade e Segurança do SIOP."""
    st.title("🛡️ Governança, Compliance & Auditoria do Sistema")
    st.caption(f"👤 **Operador:** {cargo_operador} {nome_operador} | 🏛️ **Unidade:** {unidade_operador} | ⚙️ **Perfil:** {perfil_operador}")
    st.divider()

    tab_auditoria_geral, tab_logins, tab_conformidade = st.tabs([
        "📜 Histórico Geral de Auditoria",
        "🔑 Histórico de Logins & Acessos",
        "🔒 Painel de Conformidade & RLS"
    ])

    # =========================================================================
    # ABA 1: HISTÓRICO GERAL DE AUDITORIA (historico_auditoria + tco_logs)
    # =========================================================================
    with tab_auditoria_geral:
        st.subheader("📜 Trilha Unificada de Auditoria do SIOP")
        st.caption("Eventos administrativos, trocas de permissões, resets e alterações de sistema.")

        logs_auditoria = []
        if supabase:
            try:
                res_aud = supabase.table("historico_auditoria").select("*").order("data_hora", desc=True).limit(500).execute()
                logs_auditoria = res_aud.data or []
            except Exception as e:
                st.error(f"Erro ao carregar historico_auditoria: {e}")

        if logs_auditoria:
            df_aud = pd.DataFrame(logs_auditoria)
            if "data_hora" in df_aud.columns and not df_aud.empty:
                df_aud["data_hora_fmt"] = df_aud["data_hora"].apply(
                    lambda x: pd.to_datetime(x).strftime("%d/%m/%Y %H:%M:%S") if pd.notna(x) and str(x).strip() not in ["", "None", "NaT"] else "N/I"
                )
            
            cols_aud = ["data_hora_fmt", "militar_operador", "militar_alvo", "tipo_acao", "descricao_detalhada", "ip_origem"]
            cols_exib = [c for c in cols_aud if c in df_aud.columns]
            
            st.dataframe(df_aud[cols_exib], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum registro de auditoria geral localizado.")

    # =========================================================================
    # ABA 2: HISTÓRICO DE LOGINS & ACESSOS (historico_logins)
    # =========================================================================
    with tab_logins:
        st.subheader("🔑 Registros de Conexão e Sessões (historico_logins)")
        st.caption("Rastreabilidade de acessos por usuário, endereço IP e identificador de dispositivo.")

        logins_dados = []
        if supabase:
            try:
                res_logins = supabase.table("historico_logins").select("*").order("data_hora", desc=True).limit(500).execute()
                logins_dados = res_logins.data or []
            except Exception as e:
                st.error(f"Erro ao consultar a tabela historico_logins: {e}")

        if logins_dados:
            df_logins = pd.DataFrame(logins_dados)
            
            if "data_hora" in df_logins.columns and not df_logins.empty:
                df_logins["Data / Hora Conexão"] = df_logins["data_hora"].apply(
                    lambda x: pd.to_datetime(x).strftime("%d/%m/%Y %H:%M:%S") if pd.notna(x) and str(x).strip() not in ["", "None", "NaT"] else "N/I"
                )

            df_logins.rename(columns={
                "usuario_login": "Nº Polícia / Usuário",
                "ip_origem": "Endereço IP",
                "user_agent": "Navegador / Dispositivo"
            }, inplace=True)

            cols_logins = ["Data / Hora Conexão", "Nº Polícia / Usuário", "Endereço IP", "Navegador / Dispositivo"]
            cols_reais_logins = [c for c in cols_logins if c in df_logins.columns]

            st.dataframe(df_logins[cols_reais_logins], use_container_width=True, hide_index=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # Exportação Excel do Histórico de Logins
            buffer_logins = io.BytesIO()
            with pd.ExcelWriter(buffer_logins, engine='openpyxl') as writer:
                df_logins[cols_reais_logins].to_excel(writer, index=False, sheet_name="Historico_Logins")
            buffer_logins.seek(0)

            st.download_button(
                label=f"📊 Baixar Relatório de Logins em Excel ({len(df_logins)} acessos)",
                data=buffer_logins.getvalue(),
                file_name=f"Historico_Logins_SIOP_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                key="btn_dl_historico_logins_excel"
            )
        else:
            st.info("Nenhum registro de login capturado até o momento na tabela 'historico_logins'.")

    # =========================================================================
    # ABA 3: CONFORMIDADE & SEGURANÇA (RLS & LGPD)
    # =========================================================================
    with tab_conformidade:
        st.subheader("🔒 Status de Segurança e Políticas RLS")
        st.markdown("""
        * **Ambiente de Homologação (`dev`):** Tabelas em modo direto REST para depuração de novos módulos.
        * **Ambiente de Produção (`main`):** Políticas RLS ativas permitindo apenas leitura/escrita autenticada via Service Role/JWT.
        * **Compliance LGPD:** Senhas armazenadas sob criptografia forte SHA-256 e sessões únicas validadas por `session_token`.
        """)