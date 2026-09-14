import streamlit as st
import pandas as pd

def renderizar_aba_rbac():
    st.markdown("##### 🔑 Matriz de Controle de Acesso (RBAC - 7 Níveis)")
    st.caption("Mapeamento estruturado das prerrogativas operacionais do SIOP por função.")

    dados_rbac = [
        {
            "Nível de Acesso": "1. ADMIN / PROGRAMADOR",
            "Módulo CREDS/TCO": "Gestão Global (Batalhão)",
            "Módulo Escalas": "Gestão Global (Batalhão)",
            "Prerrogativa Operacional": "Acesso total, configuração de sistema e auditoria geral."
        },
        {
            "Nível de Acesso": "2. GESTOR UNIDADE",
            "Módulo CREDS/TCO": "Gestor Unidade (Visão BPM)",
            "Módulo Escalas": "Visualização Batalhão",
            "Prerrogativa Operacional": "Designação de gestores e tramitação entre todas as Companhias."
        },
        {
            "Nível de Acesso": "3. COMANDANTE DE CIA",
            "Módulo CREDS/TCO": "Gestor Cia (Lotação)",
            "Módulo Escalas": "Comandante Cia (Aprovação)",
            "Prerrogativa Operacional": "Gestão e nomeação de operadores na sua respectiva Companhia."
        },
        {
            "Nível de Acesso": "4. GESTOR CIA / P1",
            "Módulo CREDS/TCO": "Gestor Cia (Lotação)",
            "Módulo Escalas": "Auxiliar Cia",
            "Prerrogativa Operacional": "Recebimento, despacho e controle de materiais e efetivo."
        },
        {
            "Nível de Acesso": "5. SARGENTEAÇÃO",
            "Módulo CREDS/TCO": "Operador CREDS",
            "Módulo Escalas": "Sargenteação / Planejamento",
            "Prerrogativa Operacional": "Elaboração de escalas e apoio operacional."
        },
        {
            "Nível de Acesso": "6. OPERADOR CREDS",
            "Módulo CREDS/TCO": "Operador CREDS",
            "Módulo Escalas": "Consulta Cia",
            "Prerrogativa Operacional": "Preenchimento de relatórias, cadastro manual e aceite de custódia."
        },
        {
            "Nível de Acesso": "7. TROPA (ORDINÁRIO)",
            "Módulo CREDS/TCO": "Registro e Upload REDS",
            "Módulo Escalas": "Consulta Individual",
            "Prerrogativa Operacional": "Confecção de TCO de campo e envio inicial ao sistema."
        }
    ]

    df_rbac = pd.DataFrame(dados_rbac)
    
    st.dataframe(
        df_rbac,
        column_config={
            "Nível de Acesso": st.column_config.TextColumn("Nível / Função", width="medium"),
            "Módulo CREDS/TCO": st.column_config.TextColumn("Escopo CREDS", width="medium"),
            "Módulo Escalas": st.column_config.TextColumn("Escopo Escalas", width="medium"),
            "Prerrogativa Operacional": st.column_config.TextColumn("Descrição de Prerrogativas", width="large"),
        },
        hide_index=True,
        use_container_width=True
    )