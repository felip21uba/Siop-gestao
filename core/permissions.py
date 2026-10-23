"""
==============================================================================
Módulo de Verificação de Permissões e Perfis do Sistema (core/permissions.py)
Gerencia os níveis de acesso globais e específicos do módulo CREDS / TCO.
Estrutura desacoplada: Permite que militares da TROPA sejam nomeados Gestores CREDS.
==============================================================================
"""


def usuario_eh_admin_ou_programador(usuario_dados: dict) -> bool:
    """
    Verifica se o usuário possui nível de acesso de Administrador ou Programador no sistema geral.
    """
    if not usuario_dados or not isinstance(usuario_dados, dict):
        return False

    nivel_geral = str(usuario_dados.get("nivel_acesso", "")).upper().strip()
    return nivel_geral in ["ADMIN", "PROGRAMADOR", "GESTOR_SISTEMA"]


def usuario_eh_gestor_creds(usuario_dados: dict) -> bool:
    """
    Verifica se o usuário é Gestor do CREDS (Gestor de Unidade ou Gestor de Cia)
    ou Administrador do Sistema para liberar acesso às abas gerenciais do TCO/CREDS.
    Permite acesso mesmo se o nível geral do militar for TROPA, desde que tenha perfil_creds de Gestor.
    """
    if not usuario_dados or not isinstance(usuario_dados, dict):
        return False

    if usuario_eh_admin_ou_programador(usuario_dados):
        return True

    perfil_creds = str(usuario_dados.get("perfil_creds", "")).upper().strip()
    return perfil_creds in ["GESTOR_UNIDADE", "GESTOR_CIA"]


def obter_escopo_militar_creds(usuario_dados: dict) -> tuple[str, str, str]:
    """
    Determina o escopo de visualização dos materiais no CREDS com base na Função CREDS independente do Nível Geral.

    Retorna:
        tuple[str, str, str]: (escopo, nome_militar, creds_atribuido)

    Escopos possíveis:
        - 'TODOS': Visualiza todos os materiais do Batalhão (Admin / Gestor Unidade).
        - 'COMPANHIA': Visualiza todos os materiais do CREDS/Cia/Pelotão atribuído (Gestor Cia).
        - 'PESSOAL': Visualiza apenas os materiais sob sua posse direta (Tropa sem função de gestão CREDS).
    """
    if not usuario_dados or not isinstance(usuario_dados, dict):
        return "PESSOAL", "MILITAR", "21º BPM"

    nome_militar = str(
        usuario_dados.get("nome_guerra") or usuario_dados.get("nome") or "MILITAR"
    ).upper().strip()

    # Obtém a Cia/CREDS atribuída ao usuário (ex: '35ª CIA PM', '111ª CIA PM', 'TODOS', etc.)
    creds_atribuido = str(
        usuario_dados.get("creds_acesso") or usuario_dados.get("unidade") or "21º BPM"
    ).strip()

    perfil_creds = str(usuario_dados.get("perfil_creds", "TROPA")).upper().strip()

    if usuario_eh_admin_ou_programador(usuario_dados) or perfil_creds == "GESTOR_UNIDADE" or creds_atribuido.upper() in ["TODOS", "GLOBAL", "BATALHAO"]:
        return "TODOS", nome_militar, creds_atribuido
    elif perfil_creds == "GESTOR_CIA":
        return "COMPANHIA", nome_militar, creds_atribuido
    else:
        return "PESSOAL", nome_militar, creds_atribuido