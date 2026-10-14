"""
==============================================================================
Módulo de Verificação de Permissões e Perfis do Sistema (core/permissions.py)
Gerencia os níveis de acesso globais e específicos do módulo CREDS / TCO.
==============================================================================
"""


def usuario_eh_admin_ou_programador(usuario_dados: dict) -> bool:
    """Verifica se o usuário possui nível de acesso de Administrador ou Programador."""
    if not usuario_dados or not isinstance(usuario_dados, dict):
        return False

    nivel_geral = str(usuario_dados.get("nivel_acesso", "")).upper().strip()
    return nivel_geral in ["ADMIN", "PROGRAMADOR", "GESTOR_SISTEMA"]


def usuario_eh_gestor_creds(usuario_dados: dict) -> bool:
    """
    Verifica se o usuário é Gestor do CREDS (Gestor de Unidade ou Gestor de Cia)
    ou Administrador do Sistema para liberar acesso ao Painel CREDS e Auditoria.
    """
    if not usuario_dados or not isinstance(usuario_dados, dict):
        return False

    if usuario_eh_admin_ou_programador(usuario_dados):
        return True

    perfil_creds = str(usuario_dados.get("perfil_creds", "")).upper().strip()
    return perfil_creds in ["GESTOR_UNIDADE", "GESTOR_CIA"]


def obter_escopo_militar_creds(usuario_dados: dict) -> tuple[str, str, str]:
    """
    Retorna a tupla (nivel_escopo, nome_militar, unidade_militar) para filtragem
    no banco de dados.

    Níveis possíveis:
    - 'TODOS': Acesso global ao Batalhão (Admin, Programador, Gestor Unidade).
    - 'COMPANHIA': Acesso restrito à Cia do militar (Gestor Cia).
    - 'PESSOAL': Acesso restrito apenas aos bens sob custódia direta (Tropa).
    """
    if not usuario_dados or not isinstance(usuario_dados, dict):
        return "PESSOAL", "Militar", "21º BPM"

    nome_militar = str(usuario_dados.get("nome_guerra") or usuario_dados.get("nome") or "MILITAR").upper().strip()
    unidade_militar = str(usuario_dados.get("unidade") or "21º BPM").strip()
    perfil_creds = str(usuario_dados.get("perfil_creds", "TROPA")).upper().strip()

    if usuario_eh_admin_ou_programador(usuario_dados) or perfil_creds == "GESTOR_UNIDADE":
        return "TODOS", nome_militar, unidade_militar
    elif perfil_creds == "GESTOR_CIA":
        return "COMPANHIA", nome_militar, unidade_militar
    else:
        return "PESSOAL", nome_militar, unidade_militar