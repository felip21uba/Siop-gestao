import streamlit as st
from core.database import supabase

def carregar_materiais_supabase():
    """Carrega todo o acervo de materiais cadastrados na tabela tco_materiais do Supabase."""
    if not supabase:
        return []
    try:
        res = supabase.table("tco_materiais").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        st.error(f"Erro ao carregar materiais do Supabase: {e}")
        return []

def carregar_logs_supabase():
    """Carrega o histórico de auditoria da tabela tco_logs do Supabase."""
    if not supabase:
        return []
    try:
        res = supabase.table("tco_logs").select("*").order("data_hora", desc=True).execute()
        return res.data or []
    except Exception as e:
        st.error(f"Erro ao carregar logs de auditoria: {e}")
        return []

def salvar_material_supabase(dados_material):
    """Insere um novo material no Supabase."""
    if not supabase:
        return False
    try:
        supabase.table("tco_materiais").insert(dados_material).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao gravar material no Supabase: {e}")
        return False

def atualizar_material_supabase(id_bem, campos_para_atualizar):
    """Atualiza atributos de um material específico no Supabase."""
    if not supabase or not id_bem:
        return False
    try:
        supabase.table("tco_materiais").update(campos_para_atualizar).eq("id_bem", id_bem).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar material no Supabase: {e}")
        return False

def registrar_log_supabase(log_data):
    """Grava evento imutável na trilha de auditoria do TCO no Supabase."""
    if not supabase:
        return False
    try:
        supabase.table("tco_logs").insert(log_data).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao gravar log de auditoria: {e}")
        return False