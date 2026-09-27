"""
Módulo de Banco de Dados Específico do TCO / Custódia (modules/tco/database.py).
Gerencia exclusivamente as operações na tabela de bens (tco_materiais)
e logs de tramitação/custódia (tco_logs) no Supabase.
"""

import datetime
import streamlit as st
from core.database import supabase


# =========================================================================
# 1. OPERAÇÕES DE MATERIAIS NO SUPABASE (tco_materiais)
# =========================================================================

@st.cache_data(ttl=120, show_spinner=False)
def carregar_materiais_supabase() -> list[dict]:
    """
    Carrega todos os materiais e bens registrados na custódia do TCO.
    Mantém cache local de 2 minutos para alta performance.
    """
    if not supabase:
        return []
    try:
        res = supabase.table("tco_materiais").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"Aviso ao carregar tco_materiais: {e}")
        return []


def salvar_material_supabase(dados_bem: dict) -> bool:
    """
    Insere ou atualiza um material/bem na tabela 'tco_materiais' do Supabase.
    
    Parâmetros:
        dados_bem (dict): Informações completas do bem apreendido.
        
    Retorna:
        bool: True se salvo com sucesso, False em caso de falha.
    """
    if not supabase or not dados_bem:
        return False
    try:
        supabase.table("tco_materiais").upsert(dados_bem, on_conflict="id_bem").execute()
        st.cache_data.clear()  # Limpa o cache para recarregar a lista atualizada
        return True
    except Exception as e:
        st.error(f"Erro ao salvar material no Supabase: {e}")
        return False


def atualizar_material_supabase(id_bem: str, payload_update: dict) -> bool:
    """
    Atualiza as informações de um material existente na tabela 'tco_materiais'.
    
    Parâmetros:
        id_bem (str): Código identificador do bem.
        payload_update (dict): Dados atualizados do bem.
        
    Retorna:
        bool: True se atualizado com sucesso.
    """
    if not supabase or not id_bem:
        return False
    try:
        res = supabase.table("tco_materiais").update(payload_update).eq("id_bem", str(id_bem)).execute()
        if res and res.data:
            st.cache_data.clear()
            return True
        return False
    except Exception as e:
        st.error(f"Erro ao atualizar material no Supabase: {e}")
        return False


# =========================================================================
# 2. OPERAÇÕES DE LOGS DE TRAMITAÇÃO (tco_logs)
# =========================================================================

@st.cache_data(ttl=120, show_spinner=False)
def carregar_logs_supabase() -> list[dict]:
    """
    Carrega o histórico de tramitações e ações do TCO na tabela 'tco_logs'.
    """
    if not supabase:
        return []
    try:
        res = supabase.table("tco_logs").select("*").order("data_hora", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"Aviso ao carregar tco_logs: {e}")
        return []


def registrar_log_supabase(dados_log: dict) -> bool:
    """
    Registra um novo evento de tramitação ou custódia na tabela 'tco_logs'.
    
    Parâmetros:
        dados_log (dict): Evento a ser registrado.
        
    Retorna:
        bool: True se gravado com sucesso.
    """
    if not supabase or not dados_log:
        return False
    try:
        if "data_hora" not in dados_log:
            dados_log["data_hora"] = datetime.datetime.now().isoformat()
            
        supabase.table("tco_logs").insert(dados_log).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        print(f"Erro ao registrar log do TCO: {e}")
        return False