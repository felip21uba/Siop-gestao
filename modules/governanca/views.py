import streamlit as st
import pandas as pd
import datetime
import io
import openpyxl
from core.database import supabase

def renderizar_modulo_governanca(nome_operador="OPERADOR", unidade_operador="21º BPM", cargo_operador="MILITAR", perfil_operador="ADMIN"):
    """Renderiza a Central de Governança, Compliance & Auditoria do SIOP."""
    st.title("🛡️ Governança, Compliance & Auditoria do Sistema")
    st.caption(f"👤 **Operador:** {cargo_operador} {nome_operador} | 🏛️ **Unidade:** {unidade_operador} | ⚙️ **Perfil:** {perfil_operador}")
    st.divider()

    tab_auditoria_geral, tab_logins, tab_conformidade = st.tabs([
        "📜 Histórico Geral de Auditoria",
        "🔑 Histórico de Logins & Acessos",
        "🔒 Protocolos de Segurança, RLS & Auditoria de TI"
    ])

    # =========================================================================
    # ABA 1: HISTÓRICO GERAL DE AUDITORIA (historico_auditoria + tco_logs)
    # =========================================================================
    with tab_auditoria_geral:
        st.subheader("📜 Trilha Unificada de Auditoria do SIOP")
        st.caption("Eventos administrativos, trocas de permissões, resets, alterações de sistema e movimentações de TCO.")

        logs_auditoria = []
        if supabase:
            # 1. Consulta historico_auditoria
            try:
                res_aud = supabase.table("historico_auditoria").select("*").order("data_hora", desc=True).limit(500).execute()
                if res_aud and res_aud.data:
                    for r in res_aud.data:
                        logs_auditoria.append({
                            "data_hora": r.get("data_hora") or r.get("created_at"),
                            "militar_operador": r.get("militar_operador", "SISTEMA"),
                            "militar_alvo": r.get("militar_alvo", "GERAL"),
                            "tipo_acao": r.get("tipo_acao", "EVENTO"),
                            "descricao_detalhada": r.get("descricao_detalhada", ""),
                            "ip_origem": r.get("ip_origem", "Sistema SIOP")
                        })
            except Exception as e:
                print(f"Aviso ao consultar historico_auditoria: {e}")

            # 2. Unifica com tco_logs
            try:
                res_tco = supabase.table("tco_logs").select("*").order("data_hora", desc=True).limit(500).execute()
                if res_tco and res_tco.data:
                    for l_tco in res_tco.data:
                        logs_auditoria.append({
                            "data_hora": l_tco.get("data_hora") or l_tco.get("created_at"),
                            "militar_operador": l_tco.get("origem") or l_tco.get("usuario") or "SISTEMA TCO",
                            "militar_alvo": l_tco.get("destino") or l_tco.get("num_reds") or "GERAL",
                            "tipo_acao": l_tco.get("acao", "EVENTO_TCO"),
                            "descricao_detalhada": f"[{l_tco.get('unidade_origem', '')}] {l_tco.get('detalhe', '')}".strip(),
                            "ip_origem": "Módulo TCO"
                        })
            except Exception as e:
                print(f"Aviso ao consultar tco_logs: {e}")

        if logs_auditoria:
            df_aud = pd.DataFrame(logs_auditoria)
            
            if "data_hora" in df_aud.columns and not df_aud.empty:
                # Converte para UTC e ajusta rigorosamente para o Fuso Horário de Brasília (-3h)
                df_aud["dt_obj"] = pd.to_datetime(df_aud["data_hora"], errors="coerce", utc=True)
                df_aud["dt_obj"] = df_aud["dt_obj"].dt.tz_convert("America/Sao_Paulo")
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
    # ABA 2: HISTÓRICO DE LOGINS & ACESSOS (historico_logins)
    # =========================================================================
    with tab_logins:
        st.subheader("🔑 Registros de Conexão e Sessões (historico_logins)")
        st.caption("Rastreabilidade de acessos por usuário, endereço IP e identificador de dispositivo.")

        logins_dados = []
        if supabase:
            try:
                res_logins = supabase.table("historico_logins").select("*").order("data_hora", desc=True).limit(500).execute()
                if res_logins and res_logins.data:
                    for l_in in res_logins.data:
                        logins_dados.append({
                            "data_hora": l_in.get("data_hora"),
                            "usuario_login": l_in.get("usuario_login"),
                            "ip_origem": l_in.get("ip_origem", "127.0.0.1"),
                            "user_agent": l_in.get("user_agent", "Acesso Web SIOP")
                        })
            except Exception as e:
                print(f"Aviso ao consultar historico_logins: {e}")

            if not logins_dados:
                try:
                    res_login_aud = supabase.table("historico_auditoria").select("*").ilike("tipo_acao", "%LOGIN%").order("data_hora", desc=True).limit(500).execute()
                    if res_login_aud and res_login_aud.data:
                        for l_aud in res_login_aud.data:
                            logins_dados.append({
                                "data_hora": l_aud.get("data_hora"),
                                "usuario_login": l_aud.get("militar_operador"),
                                "ip_origem": l_aud.get("ip_origem", "127.0.0.1"),
                                "user_agent": l_aud.get("descricao_detalhada", "Acesso Web SIOP")
                            })
                except Exception as ex:
                    print(f"Aviso ao consultar fallback de logins: {ex}")

        if logins_dados:
            df_logins = pd.DataFrame(logins_dados)
            
            if "data_hora" in df_logins.columns and not df_logins.empty:
                # Converte para UTC e ajusta rigorosamente para o Fuso Horário de Brasília (-3h)
                df_logins["dt_obj"] = pd.to_datetime(df_logins["data_hora"], errors="coerce", utc=True)
                df_logins["dt_obj"] = df_logins["dt_obj"].dt.tz_convert("America/Sao_Paulo")
                df_logins.sort_values(by="dt_obj", ascending=False, inplace=True)
                df_logins["Data / Hora Conexão"] = df_logins["dt_obj"].dt.strftime("%d/%m/%Y %H:%M:%S")
            else:
                df_logins["Data / Hora Conexão"] = "N/I"

            df_logins.rename(columns={
                "usuario_login": "Nº Polícia / Usuário",
                "ip_origem": "Endereço IP",
                "user_agent": "Navegador / Dispositivo"
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
    # ABA 3: PROTOCOLOS DE SEGURANÇA, RLS & AUDITORIA DE TI
    # =========================================================================
    with tab_conformidade:
        st.subheader("⚙️ Protocolos Técnicos, Regras de Negócio e Travas de Auditoria")
        st.caption("Detalhamento integral dos mecanismos de proteção, travas operacionais e conformidade regulatória para Fiscalização de TI.")
        
        c_sec1, c_sec2 = st.columns(2)
        
        with c_sec1:
            with st.container(border=True):
                st.markdown("##### 🔑 Autenticação, 2FA e Controle de Sessão")
                st.markdown("""
                * **Autenticação Multifator (2FA/TOTP):** Integração com Google Authenticator e Authy.
                * **Sessão Única Concorrente:** Proteção contra acessos simultâneos com enforçamento de dispositivo único e revogação no Supabase.
                * **Controle de Timeout:** Encerramento automático por inatividade e expiração de sessão.
                * **Controle de Acesso Baseado em Função (RBAC):** Escopo dividido em 7 níveis hierárquicos com isolamento de visões.
                * **Recuperação Dupla:** Redefinição via token por e-mail validado conjuntamente com o QR Code do operador.
                """)

            with st.container(border=True):
                st.markdown("##### 🔒 Trava de Auditoria Retroativa & Antichoques")
                st.markdown("""
                * **Trava Retroativa Diária:** Bloqueio automático de edições e substituições de serviço em datas anteriores ao dia atual (`data < hoje`) após homologação.
                * **Trava Antichoques de Guarnição:** Validação em tempo real para impedir duplicidade de lançamento de um militar em equipes distintas na mesma data.
                * **Gestão Cumulativa de Carga:** Cálculo automatizado de metas individuais (160h ou 80h) com abatimento por Dia Neutro (DN) e Dia Neutro Trabalhado (DNT).
                """)

        with c_sec2:
            with st.container(border=True):
                st.markdown("##### 🛡️ Criptografia, Sanitização e RLS")
                st.markdown("""
                * **Criptografia de Senhas:** Armazenamento em hash forte **SHA-256**.
                * **Tráfego Seguro:** Protocolo **HTTPS / TLS 1.3** criptografado em trânsito.
                * **Sanitização Anti-Injection (XSS/SQLi):** Higienização e *escaping* de todas as entradas de texto livre em formulários.
                * **Desarmo de Formula Injection:** Sanitização em exportações e importações de planilhas Excel/CSV.
                * **PostgreSQL Row Level Security (RLS):** Compatibilidade com políticas de segurança nativas a nível de linha no Supabase.
                """)

            with st.container(border=True):
                st.markdown("##### 📜 Rastreabilidade, IP Real e Custódia TCO")
                st.markdown("""
                * **Captura de IP Público Real:** Extração de IP de origem via *headers WebSocket / X-Forwarded-For*.
                * **Trilha do TCO / Custódia:** Histórico imutável de recebimento, aceite de fiel depósito e tramitações (`tco_logs`).
                * **Histórico Auditável de Conexões:** Registro de conexões com horário, IP e dispositivo (`historico_logins`).
                * **Auditoria de Operações Sensíveis:** Gravador automático para trocas de perfil, resets, exclusões e cadastro de unidades (`historico_auditoria`).
                * **Isolamento Multi-Tenant:** Segregação lógica de dados por Unidade (Batalhão) e Subunidade (Companhia).
                """)