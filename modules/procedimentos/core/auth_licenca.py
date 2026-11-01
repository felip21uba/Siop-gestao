"""
MÓDULO DE AUTORIZAÇÃO E LICENCIAMENTO COMERCIAL (SIOP - PROCEDIMENTOS)
Verifica permissões de forma isolada, sem interferir no TCO ou Escalas.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional

def verificar_licenca_procedimentos(supabase_client, matricula_usuario: str) -> Dict[str, Any]:
    """
    Verifica se a matrícula possui licença ativa para o módulo de Procedimentos.
    Retorna dicionário com status de autorização, motivo e detalhes do plano.
    """
    if not matricula_usuario:
        return {
            "autorizado": False,
            "motivo": "Matrícula não informada para autenticação do módulo.",
            "plano": None,
            "dias_restantes": 0
        }

    try:
        response = supabase_client.table("procedimentos_licencas_acesso") \
            .select("*") \
            .eq("usuario_matricula", matricula_usuario) \
            .execute()

        registros = response.data

        if not registros or len(registros) == 0:
            return {
                "autorizado": False,
                "motivo": "Militar não possui licença ativa para o Módulo de Procedimentos Administrativos.",
                "plano": None,
                "dias_restantes": 0
            }

        licenca = registros[0]
        status = licenca.get("status", "").upper()

        if status != "ATIVO":
            return {
                "autorizado": False,
                "motivo": f"Acesso bloqueado. Licença encontra-se no status: {status}.",
                "plano": licenca.get("tipo_plano"),
                "dias_restantes": 0
            }

        data_exp = licenca.get("data_expiracao")
        if data_exp:
            exp_date = datetime.fromisoformat(data_exp.replace("Z", "+00:00"))
            agora = datetime.now(timezone.utc)
            dias_restantes = (exp_date - agora).days

            if agora > exp_date:
                return {
                    "autorizado": False,
                    "motivo": "Licença comercial expirada. Favor contatar o suporte para renovação do módulo.",
                    "plano": licenca.get("tipo_plano"),
                    "dias_restantes": 0
                }
            return {
                "autorizado": True,
                "motivo": "Licença regular e ativa.",
                "plano": licenca.get("tipo_plano"),
                "dias_restantes": dias_restantes,
                "licenca_id": licenca.get("id"),
                "limite_procedimentos": licenca.get("limite_procedimentos_ativos", 50)
            }

        return {
            "autorizado": True,
            "motivo": "Licença vitalícia ativa.",
            "plano": licenca.get("tipo_plano"),
            "dias_restantes": 9999,
            "licenca_id": licenca.get("id"),
            "limite_procedimentos": licenca.get("limite_procedimentos_ativos", 50)
        }

    except Exception as e:
        return {
            "autorizado": False,
            "motivo": f"Falha ao validar licença no banco de dados: {str(e)}",
            "plano": None,
            "dias_restantes": 0
        }

def registrar_ou_atualizar_licenca(
    supabase_client,
    matricula: str,
    nome: str,
    unidade: str,
    tipo_plano: str = "INDIVIDUAL",
    status: str = "ATIVO",
    data_expiracao: Optional[datetime] = None,
    limite_procedimentos: int = 50,
    observacoes: str = ""
) -> Dict[str, Any]:
    """
    Função administrativa para conceder, renovar ou revogar licença de uso do módulo.
    """
    payload = {
        "usuario_matricula": matricula,
        "usuario_nome": nome,
        "unidade_lotacao": unidade,
        "tipo_plano": tipo_plano,
        "status": status,
        "limite_procedimentos_ativos": limite_procedimentos,
        "observacoes_licenca": observacoes,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    if data_expiracao:
        payload["data_expiracao"] = data_expiracao.isoformat()

    try:
        response = supabase_client.table("procedimentos_licencas_acesso") \
            .upsert(payload, on_conflict="usuario_matricula") \
            .execute()
        return {"sucesso": True, "dados": response.data}
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}