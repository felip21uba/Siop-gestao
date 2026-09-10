import streamlit as st
import time
import datetime
import json
from core.database import supabase

# ⏱️ 20 minutos = 1.200 segundos
TEMPO_TIMEOUT_SEGUNDOS = 20 * 60

def auto_salvar_rascunho_escala_supabase(usuario_id):
    """Salva automaticamente o progresso da escala no Supabase."""
    if not supabase or not usuario_id or usuario_id == "default_user":
        return
    try:
        now_iso = datetime.datetime.now().isoformat()
        estado_escala = {
            "grade_escala_lancamentos": st.session_state.get("grade_escala_lancamentos", {}),
            "militares_selecionados_ids": st.session_state.get("militares_selecionados_ids", []),
            "afastamentos_militares": st.session_state.get("afastamentos_militares", []),
            "subunidade": st.session_state.get("cfg_subunidade", "")
        }
        
        payload = {
            "usuario_id": str(usuario_id),
            "estado_json": json.dumps(estado_escala, ensure_ascii=False),
            "ultima_atividade": now_iso
        }
        
        supabase.table("escalas_sessao_rascunho").upsert(payload, on_conflict="usuario_id").execute()
    except Exception:
        pass

def restaurar_rascunho_escala_supabase(usuario_id):
    """Restaura os dados do rascunho de onde o operador parou."""
    if not supabase or not usuario_id or st.session_state.get("escala_restaurada", False):
        return
    try:
        res = supabase.table("escalas_sessao_rascunho").select("*").eq("usuario_id", str(usuario_id)).execute()
        if res.data and len(res.data) > 0:
            rec = res.data[0]
            estado = json.loads(rec.get("estado_json", "{}"))
            
            if estado.get("grade_escala_lancamentos"):
                st.session_state["grade_escala_lancamentos"] = estado["grade_escala_lancamentos"]
            if estado.get("militares_selecionados_ids"):
                st.session_state["militares_selecionados_ids"] = estado["militares_selecionados_ids"]
            if estado.get("afastamentos_militares"):
                st.session_state["afastamentos_militares"] = estado["afastamentos_militares"]
            
            st.toast("🔄 Rascunho da escala anterior restaurado!", icon="ℹ️")
    except Exception:
        pass
    finally:
        st.session_state["escala_restaurada"] = True

def gerenciar_timeout_sessao():
    """Controla a inatividade de 20 minutos usando Epoch Timestamp (imune a fuso horário)."""
    if not st.session_state.get("autenticado", False):
        return

    usr_logado = st.session_state.get("usuario_dados", {})
    usr_id = str(usr_logado.get("id") or usr_logado.get("usuario_login") or "").strip()
    now_ts = time.time()

    ultima_ts = st.session_state.get("ultima_atividade_ts")

    if ultima_ts is not None:
        tempo_inativo_seg = now_ts - ultima_ts
        
        if tempo_inativo_seg >= TEMPO_TIMEOUT_SEGUNDOS:
            if usr_id:
                auto_salvar_rascunho_escala_supabase(usr_id)
            
            st.session_state["autenticado"] = False
            st.session_state["usuario_autenticado"] = False
            st.session_state["mfa_pendente"] = False
            st.session_state["mfa_setup_mode"] = False
            st.session_state["usuario_dados"] = {}
            st.session_state["token_sessao_local"] = None
            st.session_state["escala_restaurada"] = False
            st.session_state["ultima_atividade_ts"] = None
            st.error("⌛ Sua sessão expirou por inatividade (20 min). Seu rascunho foi salvo automaticamente!")
            st.rerun()

    st.session_state["ultima_atividade_ts"] = now_ts

    if usr_id:
        auto_salvar_rascunho_escala_supabase(usr_id)