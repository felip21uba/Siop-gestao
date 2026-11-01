"""
==============================================================================
Módulo de Verificação de Permissões e Perfis do Sistema (core/permissions.py)
Gerencia os níveis de acesso globais e específicos do módulo CREDS / TCO.
Estrutura desacoplada: Permite que militares da TROPA sejam nomeados Gestores CREDS.
Adicionada verificação de licença comercial para o Módulo de Procedimentos.
==============================================================================
"""

from datetime import datetime, timezone
from core.database import supabase


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


def verificar_acesso_procedimentos(usuario_dados: dict) -> dict:
    """
    Verifica se o militar possui licença comercial ativa para o Módulo de Procedimentos.
    Programadores e Administradores possuem acesso automático irrestrito.
    Usuários comuns têm o prazo validado pela tabela public.procedimentos_licencas_acesso.
    """
    if not usuario_dados or not isinstance(usuario_dados, dict):
        return {
            "autorizado": False,
            "motivo": "Sessão inválida ou não identificada.",
            "dias_restantes": 0,
            "plano": None
        }

    # 1. Regra Master: Administrador e Programador têm acesso irrestrito
    if usuario_eh_admin_ou_programador(usuario_dados):
        return {
            "autorizado": True,
            "motivo": "Acesso Master / Desenvolvedor",
            "dias_restantes": 9999,
            "plano": "MASTER"
        }

    matricula = str(
        usuario_dados.get("usuario_login")
        or usuario_dados.get("matricula")
        or usuario_dados.get("usuario")
        or ""
    ).strip()

    if not matricula or not supabase:
        return {
            "autorizado": False,
            "motivo": "Militar sem matrícula identificada ou Supabase offline.",
            "dias_restantes": 0,
            "plano": None
        }

    try:
        res = supabase.table("procedimentos_licencas_acesso").select("*").eq("usuario_matricula", matricula.upper()).execute()

        if not res.data or len(res.data) == 0:
            return {
                "autorizado": False,
                "motivo": "Militar não possui licença ativa para o Módulo de Procedimentos.",
                "dias_restantes": 0,
                "plano": None
            }

        licenca = res.data[0]
        status = str(licenca.get("status", "")).upper()

        if status != "ATIVO":
            return {
                "autorizado": False,
                "motivo": f"Licença suspensa ou bloqueada ({status}).",
                "dias_restantes": 0,
                "plano": licenca.get("tipo_plano")
            }

        data_exp = licenca.get("data_expiracao")
        if data_exp:
            exp_date = datetime.fromisoformat(data_exp.replace("Z", "+00:00"))
            agora = datetime.now(timezone.utc)
            dias_restantes = (exp_date - agora).days

            if agora > exp_date:
                return {
                    "autorizado": False,
                    "motivo": "Licença comercial expirada. Renove sua assinatura.",
                    "dias_restantes": 0,
                    "plano": licenca.get("tipo_plano")
                }

            return {
                "autorizado": True,
                "motivo": "Licença ativa regular.",
                "dias_restantes": dias_restantes,
                "plano": licenca.get("tipo_plano", "COMERCIAL")
            }

        return {
            "autorizado": True,
            "motivo": "Licença vitalícia ativa.",
            "dias_restantes": 9999,
            "plano": licenca.get("tipo_plano", "VITALICIO")
        }

    except Exception as e:
        return {
            "autorizado": False,
            "motivo": f"Erro ao verificar licença no Supabase: {str(e)}",
            "dias_restantes": 0,
            "plano": None
        }