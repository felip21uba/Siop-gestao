import streamlit as st
from modules.escalas.passos.passo1_unidade import renderizar_passo1
from modules.escalas.passos.passo2_turno import renderizar_passo2
from modules.escalas.passos.passo3_efetivo import renderizar_passo3, padronizar_graduacao, PESOS_HIERARQUIA
from modules.escalas.passos.passo4_calendario import renderizar_passo4
from modules.escalas.passos.passo5_quadro import renderizar_passo5
from modules.escalas.passos.passo6_exportar import renderizar_passo6
from modules.escalas.passos.passo7_banco_horas import renderizar_passo7

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
    elif passo_ativo in ["PASSO 1: Unidade & Equipes", "PASSO 1: Unidade Operacional & Mês/Ano"]:
        renderizar_passo1()
    elif passo_ativo in ["PASSO 2: Turno & Horários", "PASSO 2: Gestão de Equipes, Turnos & Horários"]:
        renderizar_passo2()
    elif passo_ativo in ["PASSO 3: Efetivo & Ausências", "PASSO 3: Efetivo, Ausências & Dias Neutros"]:
        renderizar_passo3()
    elif passo_ativo in ["PASSO 4: Matriz Mensal", "PASSO 4: Calendário de Dias da Escala"]:
        renderizar_passo4(recalcular_matriz_passo5)
    elif passo_ativo in ["PASSO 5: Quadro Geral", "PASSO 5: Quadro Mensal de Escalas"]:
        renderizar_passo5()
    elif passo_ativo in ["PASSO 6: Exportação & Auditoria", "PASSO 6: Visualização, Importação & Exportação"]:
        renderizar_passo6()
    elif passo_ativo in ["PASSO 7: Banco de Horas", "PASSO 7: Banco de Horas Consolidado"]:
        renderizar_passo7()