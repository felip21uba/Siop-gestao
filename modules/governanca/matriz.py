import streamlit as st

def renderizar_aba_matriz_seguranca():
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
        """)

    with st.expander("🔐 **5. Assinatura Criptográfica SHA-256 e Autenticidade Pública**", expanded=False):
        st.markdown("""
        * **Chancela Eletrônica SHA-256 (Art. 158-A do CPP):** Geração de hash combinando o código do recibo JECRIM, descrição dos bens, narrativa fática e carimbo de tempo.
        * **QR Code de Validação Pública:** Impressão de QR Code e código hash SHA-256 no rodapé de todos os documentos oficiais emitidos para conferência em tempo real.
        * **Segunda Via Física Inalterável:** Backup automático do PDF idêntico gerado enviado para o bucket de armazenamento seguro no Supabase.
        """)