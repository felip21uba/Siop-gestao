import streamlit as st
from modules.escalas.passos.passo1_unidade import renderizar_passo1
from modules.escalas.passos.passo2_turno import renderizar_passo2
from modules.escalas.passos.passo3_efetivo import renderizar_passo3, padronizar_graduacao, PESOS_HIERARQUIA
from modules.escalas.passos.passo4_calendario import renderizar_passo4
from modules.escalas.passos.passo5_quadro import renderizar_passo5
from modules.escalas.passos.passo6_exportar import renderizar_passo6
from modules.escalas.passos.passo7_banco_horas import renderizar_passo7
from modules.escalas.passos.passo8_ferias import renderizar_modulo_ferias_anual

def recalcular_matriz_passo5():
    st.session_state["atualizar_quadro_passo5"] = True

def exibir_modulo_escalas():
    passo_ativo = st.session_state.get("passo_escala_ativo", "VISUALIZAR TODOS")
    
    st.title("📅 Módulo de Gestão de Escalas")
    
    if passo_ativo == "VISUALIZAR TODOS":
        renderizar_passo1()
        renderizar_passo2()
        renderizar_passo3()
        renderizar_passo4(recalcular_matriz_passo5)
        renderizar_passo5()
        renderizar_passo6()
        renderizar_passo7()
        renderizar_modulo_ferias_anual()
    elif "PASSO 1" in passo_ativo:
        renderizar_passo1()
    elif "PASSO 2" in passo_ativo:
        renderizar_passo2()
    elif "PASSO 3" in passo_ativo:
        renderizar_passo3()
    elif "PASSO 4" in passo_ativo:
        renderizar_passo4(recalcular_matriz_passo5)
    elif "PASSO 5" in passo_ativo:
        renderizar_passo5()
    elif "PASSO 6" in passo_ativo:
        renderizar_passo6()
    elif "PASSO 7" in passo_ativo:
        renderizar_passo7()
    elif "PASSO 8" in passo_ativo:
        renderizar_modulo_ferias_anual()