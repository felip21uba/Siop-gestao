"""
==============================================================================
Módulo de Banco de Dados do TCO (modules/tco/database.py)
Gerencia as operações de busca, salvamento e atualização de materiais
e logs no Supabase aplicando os filtros de escopo por militar e Cia.
==============================================================================
"""

import datetime
from core.database import supabase
from core.permissions import obter_escopo_militar_creds


def carregar_materiais_supabase(usuario_dados: dict = None) -> list:
    """
    Busca os materiais cadastrados no Supabase aplicando o isolamento de escopo:
    - TROPA: Apenas materiais sob sua custódia ou pendentes de aceite para ele.
    - GESTOR_CIA: Apenas materiais da sua Companhia.
    - GESTOR_UNIDADE / ADMIN: Todos os materiais.
    """
    if not supabase:
        return []

    try:
        escopo, nome_militar, unidade_militar = obter_escopo_militar_creds(usuario_dados)
        query = supabase.table("tco_materiais").select("*")

        if escopo == "PESSOAL":
            # Filtra materiais onde o militar é o fiel depositário ou destinatário pendente
            res = query.or_(
                f"fiel_depositario_atual.ilike.%{nome_militar}%,destinatario_pendente.ilike.%{nome_militar}%"
            ).order("created_at", desc=True).execute()
        elif escopo == "COMPANHIA":
            # Filtra materiais pertencentes à Companhia do militar
            res = query.ilike("unidade_posse_atual", f"%{unidade_militar}%").order("created_at", desc=True).execute()
        else:
            # Acesso Global
            res = query.order("created_at", desc=True).execute()

        return res.data if res and res.data else []

    except Exception as e:
        print(f"Erro ao carregar materiais do Supabase: {e}")
        return []


def salvar_material_supabase(dados_material: dict) -> bool:
    """Insere um novo material na tabela tco_materiais do Supabase."""
    if not supabase or not dados_material:
        return False

    try:
        res = supabase.table("tco_materiais").upsert(dados_material).execute()
        return True if res and res.data else False
    except Exception as e:
        print(f"Erro ao salvar material no Supabase: {e}")
        return False


def atualizar_material_supabase(id_bem: str, dados_atualizacao: dict) -> bool:
    """Atualiza as informações de um material existente no Supabase."""
    if not supabase or not id_bem or not dados_atualizacao:
        return False

    try:
        res = supabase.table("tco_materiais").update(dados_atualizacao).eq("id_bem", id_bem).execute()
        return True if res and res.data else False
    except Exception as e:
        print(f"Erro ao atualizar material no Supabase ({id_bem}): {e}")
        return False


def registrar_log_supabase(log_payload: dict) -> bool:
    """Registra uma ação de auditoria na tabela tco_logs (sem a coluna web_origem)."""
    if not supabase or not log_payload:
        return False

    try:
        payload_limpo = log_payload.copy()
        if "web_origem" in payload_limpo:
            del payload_limpo["web_origem"]

        if "data_hora" not in payload_limpo or not payload_limpo["data_hora"]:
            payload_limpo["data_hora"] = datetime.datetime.now().isoformat()

        res = supabase.table("tco_logs").insert(payload_limpo).execute()
        return True if res and res.data else False
    except Exception as e:
        print(f"Erro ao registrar log no Supabase: {e}")
        return False


def carregar_logs_supabase() -> list:
    """Busca a trilha de auditoria na tabela tco_logs."""
    if not supabase:
        return []

    try:
        res = supabase.table("tco_logs").select("*").order("data_hora", desc=True).limit(500).execute()
        return res.data if res and res.data else []
    except Exception as e:
        print(f"Erro ao carregar logs do Supabase: {e}")
        return []