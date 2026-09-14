import streamlit as st
import pandas as pd
from modules.cartao_programa.ai_generator import analisar_mancha_criminal_e_sugerir_cartao

def renderizar_modulo_cartao_programa(nome_operador, unidade_operador, cargo_operador):
    st.markdown("## 🗺️ Cartão Programa Inteligente & Operações")
    st.caption("Geração de rotas táticas com base em Inteligência Artificial, mancha criminal e alertas dinâmicos.")

    aba_gerar, aba_tropa, aba_operacoes = st.tabs([
        "🤖 1. Carregar Mancha & IA", 
        "📱 2. Consultar Cartões (Tropa)", 
        "📋 3. Quadro de Operações"
    ])

    with aba_gerar:
        st.markdown("##### 📥 Upload da Mancha Criminal / Ocorrências")
        arq_crimes = st.file_uploader("Selecione a planilha de dados criminais (Excel/CSV):", type=["xlsx", "csv"])

        if arq_crimes:
            df_crimes = pd.read_excel(arq_crimes) if arq_crimes.name.endswith(".xlsx") else pd.read_csv(arq_crimes)
            st.success(f"Carga concluída! {len(df_crimes)} registros identificados.")

            if st.button("⚡ Processar com IA Operacional", type="primary"):
                sugestoes = analisar_mancha_criminal_e_sugerir_cartao(df_crimes)
                st.session_state["cartao_rascunho"] = sugestoes

        if st.session_state.get("cartao_rascunho"):
            st.markdown("##### ✏️ Quadro de Edição e Validação do Sargento/P3")
            df_rascunho = pd.DataFrame(st.session_state["cartao_rascunho"])

            df_editado = st.data_editor(
                df_rascunho,
                column_config={
                    "posto": st.column_config.NumberColumn("Posto", width="small"),
                    "local_emprego": st.column_config.TextColumn("Local de Emprego", width="large"),
                    "objetivo": st.column_config.TextColumn("Objetivo", width="medium"),
                    "missao": st.column_config.TextColumn("Missão Tática", width="large"),
                    "observacoes": st.column_config.TextColumn("Observações", width="medium")
                },
                hide_index=True,
                use_container_width=True
            )

            if st.button("🔒 Publicar Cartão Programa Oficial", type="primary"):
                st.success("Cartão publicado com sucesso! Disponibilizado para a Tropa e sincronizado com os alertas via WhatsApp.")