import streamlit as st
import pandas as pd
import datetime
from core.database import supabase, registrar_audit_log

def obter_texto_termo_ativo():
    """Busca a minuta atualizada do Termo de Compliance no Supabase."""
    if supabase:
        try:
            res = supabase.table("configuracoes_sistema").select("valor").eq("chave", "termo_compliance_texto").execute()
            if res.data and len(res.data) > 0:
                return res.data[0]["valor"]
        except Exception:
            pass
    return (
        "TERMO DE RESPONSABILIDADE E FIEL DEPÓSITO DE MATERIAIS - TCO\n\n"
        "Pelo presente termo, declaro estar ciente da custódia física dos materiais apreendidos sob minha responsabilidade, "
        "comprometendo-me a zelar pela integridade dos invólucros/lacres e cumprir rigorosamente as normas de tramitação "
        "do Decreto Estadual nº 48.243/2021 e Diretriz Institucional de Cadeia de Custódia."
    )

def salvar_texto_termo_ativo(novo_texto, operador_pm):
    """Atualiza a redação oficial do Termo de Compliance no banco de dados."""
    if not supabase:
        return False
    try:
        supabase.table("configuracoes_sistema").upsert({
            "chave": "termo_compliance_texto",
            "valor": novo_texto,
            "atualizado_por": operador_pm,
            "data_atualizacao": datetime.datetime.now().isoformat()
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar termo: {e}")
        return False

def renderizar_modulo_governanca(nome_operador, unidade_operador, cargo_operador, perfil_operador):
    st.markdown("## 🛡️ Central de Governança & Controles de Segurança")
    st.caption("Dossiê técnico de segurança da informação, prevenção contra invasões e auditoria imutável.")

    eh_admin = any(k in f"{cargo_operador} {perfil_operador}".upper() for k in ["PROGRAMADOR", "ADMIN", "P1", "COMANDANTE"])

    aba_travas, aba_termos, aba_logs = st.tabs([
        "🔒 Matriz de Segurança & Anti-Ataques", 
        "📄 Gestão de Termos & Aceites", 
        "📜 Trilha Universal de Auditoria"
    ])

    # =========================================================================
    # ABA 1: MATRIZ RETRÁTIL DE SEGURANÇA CIBERNÉTICA E AUDITORIA
    # =========================================================================
    with aba_travas:
        st.markdown("##### 🏛️ Arquitetura de Defesa e Mecanismos de Criptografia do SIOP")
        st.caption("Estrutura técnica para apresentação à Diretoria de TI e Auditoria Institucional.")

        with st.expander("🔑 **1. Autenticação, Proteção Anti-Força Bruta e Controle de Sessão**", expanded=True):
            st.markdown("""
            * **Autenticação em Duas Etapas (2FA / TOTP):** Integração com Google Authenticator e Authy via chaves temporárias base32.
            * **Proteção Anti-Brute Force:** Bloqueio temporário progressivo por IP e usuário no endpoint do Supabase Auth após tentativas malsucedidas consecutivas.
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
            """)

        with st.expander("🔐 **5. Assinatura Criptográfica SHA-256 e Autenticidade Pública**", expanded=False):
            st.markdown("""
            * **Chancela Eletrônica SHA-256 (Art. 158-A do CPP):** Geração de hash combinando o código do recibo JECRIM, descrição dos bens, narrativa fática e carimbo de tempo.
            * **QR Code de Validação Pública:** Impressão de QR Code e código hash SHA-256 no rodapé de todos os documentos oficiais emitidos para conferência em tempo real.
            * **Segunda Via Física Inalterável:** Backup automático do PDF idêntico gerado enviado para o bucket de armazenamento seguro no Supabase.
            """)

    # =========================================================================
    # ABA 2: EDITOR DE TERMOS E BUSCA DE ACEITES
    # =========================================================================
    with aba_termos:
        c_t1, c_t2 = st.columns([2, 2.2])

        with c_t1:
            with st.container(border=True):
                st.markdown("##### ✏️ Redação do Termo de Compliance TCO")
                st.caption("Atualize o texto oficial exigido aos militares no momento do aceite.")
                
                texto_atual = obter_texto_termo_ativo()
                novo_texto_termo = st.text_area(
                    "Minuta do Termo de Fiel Depósito:", 
                    value=texto_atual, 
                    height=240, 
                    disabled=not eh_admin
                )

                if eh_admin:
                    if st.button("💾 Salvar Nova Versão do Termo", type="primary", use_container_width=True):
                        if salvar_texto_termo_ativo(novo_texto_termo, f"{cargo_operador} {nome_operador}"):
                            registrar_audit_log(
                                operador_pm=f"{cargo_operador} {nome_operador}",
                                alvo_pm="SISTEMA",
                                tipo_acao="ATUALIZAÇÃO TERMO COMPLIANCE",
                                descricao="Redação oficial do Termo de Compliance do TCO atualizada no banco de dados."
                            )
                            st.success("Termo de Compliance atualizado com sucesso!")
                            st.rerun()
                else:
                    st.warning("🔒 Apenas Administradores e P1 podem editar a minuta oficial do termo.")

        with c_t2:
            with st.container(border=True):
                st.markdown("##### 🔍 Consultar Aceites Registrados")
                st.caption("Pesquise a concordância formal dos militares com o termo de custódia.")

                filtro_pm = st.text_input("Filtrar por Policial (Nome ou Nº PM):", placeholder="Ex: ASSUNCAO ou 145890").strip().upper()

                aceites_banco = []
                if supabase:
                    try:
                        query = supabase.table("aceites_compliance").select("*")
                        if filtro_pm:
                            query = query.ilike("nome_militar", f"%{filtro_pm}%")
                        res_ac = query.order("data_aceite", desc=True).limit(50).execute()
                        aceites_banco = res_ac.data or []
                    except Exception:
                        pass

                if aceites_banco:
                    df_ac = pd.DataFrame(aceites_banco)
                    st.dataframe(
                        df_ac[["data_aceite", "num_policia", "nome_militar", "unidade", "cargo_funcao"]],
                        column_config={
                            "data_aceite": "Data/Hora Aceite",
                            "num_policia": "Nº PM",
                            "nome_militar": "Nome do Militar",
                            "unidade": "Unidade Orgânica",
                            "cargo_funcao": "Cargo/Função"
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("Nenhum registro de aceite localizado com os filtros aplicados.")

    # =========================================================================
    # ABA 3: TRILHA UNIVERSAL DE AUDITORIA
    # =========================================================================
    with aba_logs:
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