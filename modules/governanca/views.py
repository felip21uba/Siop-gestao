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
        st.caption("Eventos administrativos, trocas de permissões, resets, alterações de sistema e movimentações de TCO.")

        logs_auditoria = []
        if supabase:
            # 1. Busca da tabela 'historico_auditoria'
            try:
                res_aud = supabase.table("historico_auditoria").select("*").order("created_at", desc=True).limit(500).execute()
                logs_auditoria = res_aud.data or []
            except Exception as e:
                print(f"Aviso ao consultar historico_auditoria: {e}")

            # 2. Complementa com os logs da tabela 'tco_logs'
            try:
                res_tco = supabase.table("tco_logs").select("*").order("data_hora", desc=True).limit(500).execute()
                if res_tco and res_tco.data:
                    for l_tco in res_tco.data:
                        logs_auditoria.append({
                            "created_at": l_tco.get("data_hora") or l_tco.get("created_at"),
                            "militar_operador": l_tco.get("origem") or l_tco.get("usuario") or "SISTEMA",
                            "militar_alvo": l_tco.get("destino") or l_tco.get("num_reds") or "GERAL",
                            "tipo_acao": l_tco.get("acao", "EVENTO_TCO"),
                            "descricao_detalhada": f"[{l_tco.get('unidade_origem', '')}] {l_tco.get('detalhe', '')}".strip(),
                            "ip_origem": "Sistema SIOP"
                        })
            except Exception as e:
                print(f"Aviso ao consultar tco_logs: {e}")

        if logs_auditoria:
            df_aud = pd.DataFrame(logs_auditoria)
            
            # Tratamento robusto das datas no formato ISO / UTC (+00)
            col_data = "created_at" if "created_at" in df_aud.columns else ("data_hora" if "data_hora" in df_aud.columns else None)
            
            if col_data:
                df_aud["dt_obj"] = pd.to_datetime(df_aud[col_data], errors="coerce", utc=True)
                df_aud.sort_values(by="dt_obj", ascending=False, inplace=True)
                df_aud["Data / Hora"] = df_aud["dt_obj"].dt.strftime("%d/%m/%Y %H:%M:%S")
            else:
                df_aud["Data / Hora"] = "N/I"

            df_aud.rename(columns={
                "militar_operador": "Operador",
                "militar_alvo": "Alvo / REDS",
                "tipo_acao": "Ação / Evento",
                "descricao_detalhada": "Descrição / Detalhes",
                "ip_origem": "Origem / IP"
            }, inplace=True)

            cols_exib = ["Data / Hora", "Operador", "Alvo / REDS", "Ação / Evento", "Descrição / Detalhes", "Origem / IP"]
            cols_presentes = [c for c in cols_exib if c in df_aud.columns]
            
            st.dataframe(df_aud[cols_presentes], use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ Nenhum registro de auditoria geral localizado no momento.")

    # =========================================================================
    # ABA 2: HISTÓRICO DE LOGINS & ACESSOS
    # =========================================================================
    with tab_logins:
        st.subheader("🔑 Registros de Conexão e Sessões")
        st.caption("Rastreabilidade de acessos por usuário, endereço IP e identificador de dispositivo.")

        logins_dados = []
        if supabase:
            # Pega todos os registros de LOGIN_SUCESSO da tabela historico_auditoria
            try:
                res_login_aud = supabase.table("historico_auditoria").select("*").ilike("tipo_acao", "%LOGIN%").order("created_at", desc=True).limit(500).execute()
                logins_dados = res_login_aud.data or []
            except Exception as ex:
                print(f"Aviso ao consultar logins: {ex}")

            # Se houver registros na tabela historico_logins, complementa
            try:
                res_logins = supabase.table("historico_logins").select("*").order("data_hora", desc=True).limit(500).execute()
                if res_logins and res_logins.data:
                    for l_in in res_logins.data:
                        logins_dados.append({
                            "created_at": l_in.get("data_hora") or l_in.get("created_at"),
                            "militar_operador": l_in.get("usuario_login"),
                            "ip_origem": l_in.get("ip_origem", "127.0.0.1"),
                            "descricao_detalhada": l_in.get("user_agent", "Acesso Web SIOP")
                        })
            except Exception as e:
                print(f"Aviso ao consultar historico_logins: {e}")

        if logins_dados:
            df_logins = pd.DataFrame(logins_dados)
            
            col_data_l = "created_at" if "created_at" in df_logins.columns else ("data_hora" if "data_hora" in df_logins.columns else None)
            
            if col_data_l:
                df_logins["dt_obj"] = pd.to_datetime(df_logins[col_data_l], errors="coerce", utc=True)
                df_logins.sort_values(by="dt_obj", ascending=False, inplace=True)
                df_logins["Data / Hora Conexão"] = df_logins["dt_obj"].dt.strftime("%d/%m/%Y %H:%M:%S")
            else:
                df_logins["Data / Hora Conexão"] = "N/I"

            df_logins.rename(columns={
                "militar_operador": "Nº Polícia / Usuário",
                "ip_origem": "Endereço IP",
                "descricao_detalhada": "Navegador / Dispositivo"
            }, inplace=True)

            cols_logins = ["Data / Hora Conexão", "Nº Polícia / Usuário", "Endereço IP", "Navegador / Dispositivo"]
            cols_reais_logins = [c for c in cols_logins if c in df_logins.columns]

            st.dataframe(df_logins[cols_reais_logins], use_container_width=True, hide_index=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
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
            st.info("ℹ️ Nenhum registro de login capturado até o momento.")

    # =========================================================================
    # ABA 3: CONFORMIDADE & SEGURANÇA (RLS & LGPD)
    # =========================================================================
    with tab_conformidade:
        st.subheader("🔒 Status de Segurança e Políticas RLS")
        st.markdown("""
        * **Ambiente Operacional Multi-Tenant:** Isolamento automático por Unidade e Companhia.
        * **Governança & Rastreabilidade:** Todos os eventos de alteração de permissão, exclusão ou login são gravados nas tabelas de auditoria.
        * **Compliance LGPD:** Senhas armazenadas sob criptografia forte SHA-256 e sessões únicas validadas por `session_token`.
        """)