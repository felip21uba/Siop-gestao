import streamlit as st
from core.database import supabase

# ==========================================
# BENS / MATERIAIS TCO (tabela: tco_materiais)
# ==========================================

@st.cache_data(ttl=300)
def carregar_materiais_supabase() -> list[dict]:
    """Carrega todo o acervo de materiais cadastrados na tabela tco_materiais do Supabase."""
    if not supabase:
        return []
    try:
        res = supabase.table("tco_materiais").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        st.warning(f"Aviso ao carregar materiais TCO do Supabase: {e}")
        return []

def salvar_material_supabase(dados: dict) -> bool:
    """Insere um novo material/bem em custódia na tabela tco_materiais."""
    if not supabase or not dados:
        return False
    try:
        supabase.table("tco_materiais").insert(dados).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar material TCO no Supabase: {e}")
        return False

def atualizar_material_supabase(id_bem: str, dados: dict) -> bool:
    """Atualiza atributos de um material específico na tabela tco_materiais."""
    if not supabase or not id_bem or not dados:
        return False
    try:
        supabase.table("tco_materiais").update(dados).eq("id_bem", id_bem).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar material TCO no Supabase: {e}")
        return False


# ==========================================
# TRILHA DE AUDITORIA TCO (tabela: tco_logs)
# ==========================================

@st.cache_data(ttl=300)
def carregar_logs_supabase() -> list[dict]:
    """Carrega o histórico de auditoria da tabela tco_logs do Supabase."""
    if not supabase:
        return []
    try:
        res = supabase.table("tco_logs").select("*").order("data_hora", desc=True).execute()
        return res.data or []
    except Exception as e:
        st.warning(f"Aviso ao carregar logs TCO do Supabase: {e}")
        return []

def registrar_log_supabase(dados: dict) -> bool:
    """Grava evento imutável na trilha de auditoria do TCO na tabela tco_logs."""
    if not supabase or not dados:
        return False
    try:
        supabase.table("tco_logs").insert(dados).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        print(f"Erro ao registrar log TCO no Supabase: {e}")
        return False

# Aliases de compatibilidade para evitar divergências de importação
carregar_materiais = carregar_materiais_supabase
carregar_logs = carregar_logs_supabase