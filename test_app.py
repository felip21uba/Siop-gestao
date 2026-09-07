import pytest
from streamlit.testing.v1 import AppTest

# 1. TESTE DE CARREGAMENTO INICIAL
def test_carregamento_inicial():
    """Valida se o app.py inicializa sem exceções críticas no estado padrão."""
    at = AppTest.from_file("app.py", default_timeout=15).run()
    assert not at.exception, f"❌ Erro ao inicializar a aplicação: {at.exception}"

# 2. TESTE DE NAVEGAÇÃO ENTRE MÓDULOS
def test_navegacao_modulos_sidebar():
    """Simula a navegação por todos os módulos do menu lateral."""
    at = AppTest.from_file("app.py", default_timeout=15).run()
    
    modulos = ["ESCALAS", "MURAL", "TCO", "PROCEDIMENTOS", "GESTOES_USUARIOS", "MEU_PERFIL"]
    
    for mod in modulos:
        at.session_state["modulo_ativo"] = mod
        at.run()
        assert not at.exception, f"❌ Erro ao carregar o módulo {mod}: {at.exception}"

# 3. TESTE DE NAVEGAÇÃO PELOS PASSOS DA ESCALA (PASSOS 1 AO 7)
def test_rotas_passos_escala():
    """Percorre sequencialmente todos os passos da escala garantindo a renderização."""
    at = AppTest.from_file("app.py", default_timeout=15).run()
    at.session_state["modulo_ativo"] = "ESCALAS"
    
    passos = [
        "VISUALIZAR TODOS",
        "PASSO 1: Unidade & Equipes",
        "PASSO 2: Turno & Horários",
        "PASSO 3: Efetivo & Ausências",
        "PASSO 4: Matriz Mensal",
        "PASSO 5: Quadro Geral",
        "PASSO 6: Exportação & Auditoria",
        "PASSO 7: Banco de Horas"
    ]
    
    for passo in passos:
        at.session_state["passo_escala_ativo"] = passo
        at.run()
        assert not at.exception, f"❌ Erro de renderização no {passo}: {at.exception}"

# 4. TESTE DE SEGURANÇA E PERFIL
def test_tela_perfil_e_partes():
    """Valida a renderização do Perfil, abas e componentes da Parte Informativa."""
    at = AppTest.from_file("app.py", default_timeout=15).run()
    at.session_state["modulo_ativo"] = "MEU_PERFIL"
    at.run()
    
    assert not at.exception, f"❌ Erro na tela de Perfil: {at.exception}"

# 5. TESTE DE REINICIALIZAÇÃO DA INTERFACE
def test_botao_atualizar_aplicacao():
    """Simula o recarregamento seguro da aplicação."""
    at = AppTest.from_file("app.py", default_timeout=15).run()
    at.run()
    assert not at.exception, "❌ Erro ao atualizar a aplicação."