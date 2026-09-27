import datetime
import pandas as pd
import streamlit as st
from core.database import supabase

# =========================================================================
# OPERAÇÕES DE MATERIAIS NO SUPABASE (tco_materiais)
# =========================================================================
@st.cache_data(ttl=120, show_spinner=False)
def carregar_materiais_supabase() -> list[dict]:
    """Carrega todos os materiais/bens registrados na custódia do TCO."""
    if not supabase:
        return []
    try:
        res = supabase.table("tco_materiais").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"Aviso ao carregar tco_materiais: {e}")
        return []

def salvar_material_supabase(dados_bem: dict) -> bool:
    """Insere um novo material/bem na tabela tco_materiais."""
    if not supabase or not dados_bem:
        return False
    try:
        supabase.table("tco_materiais").insert(dados_bem).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar material no Supabase: {e}")
        return False

def atualizar_material_supabase(id_bem: str, payload_update: dict) -> bool:
    """Atualiza as informações de um material existente no Supabase."""
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
# OPERAÇÕES DE LOGS DE TRAMITAÇÃO (tco_logs)
# =========================================================================
@st.cache_data(ttl=120, show_spinner=False)
def carregar_logs_supabase() -> list[dict]:
    """Carrega o histórico de tramitações e ações do TCO."""
    if not supabase:
        return []
    try:
        res = supabase.table("tco_logs").select("*").order("data_hora", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"Aviso ao carregar tco_logs: {e}")
        return []

def registrar_log_supabase(dados_log: dict) -> bool:
    """Registra um novo evento de tramitação ou custódia na tabela tco_logs."""
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