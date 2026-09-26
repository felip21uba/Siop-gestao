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
        "🏛️ Arquitetura de Defesa & Mecanismos de Criptografia"
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
                # Converte para UTC e ajusta para o Fuso Horário de Brasília (-3h)
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
                # Converte para UTC e ajusta para o Fuso Horário de Brasília (-3h)
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
    # ABA 3: ARQUITETURA DE DEFESA & MECANISMOS DE CRIPTOGRAFIA
    # =========================================================================
    with tab_conformidade:
        st.markdown("##### 🏛️ Arquitetura de Defesa e Mecanismos de Criptografia do SIOP")
        st.caption("Estrutura técnica para apresentação à Diretoria de TI e Auditoria Institucional.")

        with st.expander("🔑 **1. Autenticação, Proteção Anti-Força Bruta e Controle de Sessão**", expanded=True):
            st.markdown("""
            * **Autenticação em Duas Etapas (2FA / TOTP):** Integração com Google Authenticator e Authy via chaves temporárias base32.
            * **Proteção Anti-Brute Force:** Bloqueio temporário progressivo por IP e usuário no endpoint do Supabase Auth após 3 tentativas malsucedidas.
            * **Controle de Sessão Concorrente (Sessão Única):** Validação por `token_sessao_ativa` no banco de dados. Caso ocorra novo login simultâneo, o acesso anterior é revogado e desconectado imediatamente.
            * **Gestão de Timeout por Inatividade:** Destruição automática das variáveis locais (`st.session_state`) após 20 minutos de ociosidade ou fechamento do navegador.
            """)

        with st.expander("🛡️ **2. Proteção de Storage e Sanitização de Uploads (Anti-Malware & Traversal)**", expanded=False):
            st.markdown("""
            * **Sanitização Criptográfica de Arquivos (`sanitizar_nome_arquivo`):** Tratamento de nomes via Regex e `unicodedata`, eliminando caracteres especiais, cedilhas e caminhos para neutralizar ataques de *Directory Traversal*.
            * **Filtro Estrito por Extensão e MIME-Type (`file_validator.py`):** Bloqueio absoluto de arquivos executáveis ou maliciosos (`.exe`, `.php`, `.js`, `.py`, `.sh`, `.bat`). Liberação restrita a documentos validados como `application/pdf`, `image/jpeg` e `image/png`.
            * **Leitura com Buffer Sanitizado:** Leitura de arquivos limitada em memória RAM para prevenir invasões por estouro de cota e estouro de memória (DoS).
            """)

        with st.expander("⚡ **3. Integridade do Banco de Dados, Anti-SQL Injection e PostgreSQL RLS**", expanded=False):
            st.markdown("""
            * **Anulação de SQL Injection:** Comunicação com o PostgreSQL executada exclusivamente por endpoints da API PostgREST/Supabase com parametrização restrita de tipos de dados.
            * **Row Level Security (RLS - PostgreSQL):** Segurança aplicada diretamente nas tabelas do banco de dados, bloqueando consultas não autorizadas via API REST por validação do token JWT do usuário.
            * **Isolamento por Controle de Acesso (RBAC):** Restrição de privilégios dividida em 7 níveis funcionais com bloqueio de renderização de componentes de interface no servidor.
            """)

        with st.expander("📜 **4. Trilha de Auditoria Imutável e Triggers no PostgreSQL**", expanded=False):
            st.markdown("""
            * **Triggers de Bloqueio no Banco (`proibir_alteracao_logs`):** Função em PL/pgSQL executada antes de qualquer comando `UPDATE` ou `DELETE` nas tabelas `tco_logs` e `audit_log`, retornando exceção do sistema.
            * **Imutabilidade Jurídica do Histórico:** Todos os registros de ações (Importação, Edição, Tramitação, Exclusão e Aceite) mantêm carimbo de data/hora em ISO com milissegundos, operador responsável, unidade e payload original alterado.
            * **Captura de IP Público Real:** Extração automática de IP de origem do cliente via *headers WebSocket / X-Forwarded-For*.
            """)

        with st.expander("🔐 **5. Assinatura Criptográfica SHA-256 e Autenticidade Pública**", expanded=False):
            st.markdown("""
            * **Chancela Eletrônica SHA-256 (Art. 158-A do CPP):** Geração de hash combinando o código do recibo JECRIM, descrição dos bens, narrativa fática e carimbo de tempo.
            * **QR Code de Validação Pública:** Impressão de QR Code e código hash SHA-256 no rodapé de todos os documentos oficiais emitidos para conferência em tempo real.
            * **Segunda Via Física Inalterável:** Backup automático do PDF idêntico gerado enviado para o bucket de armazenamento seguro no Supabase Storage.
            """)