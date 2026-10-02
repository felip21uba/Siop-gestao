"""
==============================================================================
Módulo de Infraestrutura de Banco de Dados Central (core/database.py)
Gerencia a conexão com o Supabase utilizando a tabela 'efetivo_oficial' 
para o Passo 3 e 'usuarios' para login/autenticação.
==============================================================================
"""

import datetime
import os
import re
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# =========================================================================
# 1. CONEXÃO COM O SUPABASE
# =========================================================================
@st.cache_resource
def conectar_supabase() -> Client | None:
    """Abre a conexão com o cliente do Supabase."""
    try:
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")

        if not url or not key:
            return None
            
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Erro crítico ao conectar no Supabase: {e}")
        return None

supabase = conectar_supabase()

def init_db():
    pass

# =========================================================================
# 2. ISOLAMENTO MULTI-TENANT & EXTRAÇÃO DE BATALHÃO MÃE (BPM)
# =========================================================================
def extrair_bpm_mae(texto_unidade: str) -> str:
    """Extrai o Batalhão Principal (Unidade Mãe) de qualquer string de lotação."""
    if not texto_unidade or str(texto_unidade).upper() in ["NONE", "NAN", "N/I", "UNIDADE N/I"]:
        return "21º BPM"

    txt = str(texto_unidade).strip().upper()
    match = re.search(r'(\d+)\s*º?\s*BPM', txt)
    if match:
        return f"{match.group(1)}º BPM"

    return txt

def obter_unidade_operacao_atual() -> str:
    """Retorna a unidade ativa da sessão ou da barra lateral."""
    usr_dados = st.session_state.get("usuario_dados", {})
    if isinstance(usr_dados, str):
        usr_dados = {}

    perfil = str(usr_dados.get("nivel_acesso") or usr_dados.get("perfil") or "TROPA").upper()
    eh_desenvolvedor = any(p in perfil for p in ["PROGRAMADOR", "DESENVOLVEDOR", "ADMIN"])

    if eh_desenvolvedor:
        bpm_sidebar = st.session_state.get("unidade_ativa_bpm")
        if bpm_sidebar and bpm_sidebar != "🌐 TODAS AS UNIDADES":
            return bpm_sidebar

    unidade_usuario = usr_dados.get("unidade") or "21º BPM"
    return extrair_bpm_mae(unidade_usuario)

def obter_ip_cliente_real() -> str:
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers  # type: ignore
        headers = _get_websocket_headers()
        if headers and headers.get("X-Forwarded-For"):
            return headers.get("X-Forwarded-For").split(",")[0].strip()
    except Exception:
        pass
    return "127.0.0.1"

# =========================================================================
# 3. LEITURA E GRAVAÇÃO NA TABELA 'EFETIVO_OFICIAL'
# =========================================================================
@st.cache_data(ttl=15, show_spinner=False)
def carregar_militares_supabase() -> list[dict]:
    """Busca a lista de militares diretamente da nova tabela 'efetivo_oficial'."""
    if not supabase:
        return st.session_state.get("lista_militares", [])

    try:
        res = supabase.table("efetivo_oficial").select("*").order("posto_grad").execute()
        if res and res.data:
            militares = []
            for u in res.data:
                num_pol = str(u.get("num_policia", "")).strip().upper()
                if not num_pol or num_pol == "N/I":
                    continue

                lotacao_str = str(u.get("lotacao") or "21º BPM").strip().upper()
                bpm_mae = extrair_bpm_mae(lotacao_str)

                militares.append({
                    "id": str(u.get("id")),
                    "num_policia": num_pol,
                    "posto_grad": str(u.get("posto_grad") or "SD").strip().upper(),
                    "nome_guerra": str(u.get("nome_guerra") or "MILITAR").strip().upper(),
                    "nome_completo": str(u.get("nome_completo") or u.get("nome_guerra") or "MILITAR").strip().upper(),
                    "cidade": str(u.get("cidade") or "UBÁ").strip().upper(),
                    "unidade": bpm_mae,
                    "lotacao": lotacao_str,
                    "ativo": True
                })
            st.session_state["lista_militares"] = militares
            return militares
    except Exception as e:
        print(f"Erro ao carregar dados da tabela efetivo_oficial: {e}")
    return st.session_state.get("lista_militares", [])

def salvar_militares_supabase(lista_militares: list[dict]) -> bool:
    """Grava/atualiza militares diretamente na tabela 'efetivo_oficial'."""
    if not supabase or not lista_militares:
        return False
    try:
        dados_salvar = []
        for m in lista_militares:
            num_pol = str(m.get("num_policia", "N/I")).strip().upper()
            if not num_pol or num_pol == "N/I":
                continue

            lotacao_full = str(m.get("lotacao") or m.get("unidade") or "21º BPM").strip().upper()

            dados_salvar.append({
                "num_policia": num_pol,
                "posto_grad": m.get("posto_grad", "SD"),
                "nome_guerra": str(m.get("nome_guerra", "MILITAR")).strip().upper(),
                "nome_completo": str(m.get("nome_completo") or m.get("nome_guerra")).strip().upper(),
                "cidade": str(m.get("cidade", "UBÁ")).strip().upper(),
                "lotacao": lotacao_full
            })

        supabase.table("efetivo_oficial").upsert(dados_salvar, on_conflict="num_policia").execute()
        st.cache_data.clear()
        st.session_state["lista_militares"] = carregar_militares_supabase()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar na tabela efetivo_oficial: {e}")
        return False

def atualizar_usuario_supabase(identificador: str, dados: dict) -> bool:
    if not supabase or not identificador:
        return False
    try:
        u_clean = str(identificador).strip()
        supabase.table("usuarios").update(dados).or_(
            f"usuario_login.eq.{u_clean},usuario.eq.{u_clean}"
        ).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        print(f"Erro ao atualizar usuario: {e}")
        return False

def registrar_audit_log(operador_pm: str, alvo_pm: str | None, tipo_acao: str, descricao: str):
    if supabase:
        try:
            supabase.table("historico_auditoria").insert({
                "militar_operador": str(operador_pm),
                "militar_alvo": str(alvo_pm) if alvo_pm else None,
                "tipo_acao": str(tipo_acao),
                "descricao_detalhada": str(descricao),
                "ip_origem": obter_ip_cliente_real()
            }).execute()
        except Exception:
            pass