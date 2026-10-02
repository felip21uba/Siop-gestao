"""
==============================================================================
Módulo de Infraestrutura de Banco de Dados Central (core/database.py)
Gerencia a conexão com o Supabase utilizando exclusivamente a tabela 'usuarios'
para Efetivo, Login e Permissões, e 'escalas_mensais' para o Quadro 5.
==============================================================================
"""

import datetime
import os
import re
import pandas as pd
import streamlit as st

try:
    from supabase import create_client, Client
except ImportError:
    Client = None
    create_client = None

# =========================================================================
# 1. CONEXÃO COM O SUPABASE
# =========================================================================
@st.cache_resource
def conectar_supabase():
    """Abre a conexão com o cliente do Supabase de forma segura."""
    if create_client is None:
        return None
    try:
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")

        if not url or not key:
            return None
            
        return create_client(url, key)
    except Exception as e:
        print(f"Aviso ao conectar no Supabase: {e}")
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
# 3. LEITURA E GRAVAÇÃO UNIFICADA NA TABELA 'USUARIOS'
# =========================================================================
@st.cache_data(ttl=10, show_spinner=False)
def carregar_militares_supabase() -> list[dict]:
    """Busca a lista de militares e permissões diretamente da tabela unificada 'usuarios'."""
    if not supabase:
        return st.session_state.get("lista_militares", [])

    try:
        res = supabase.table("usuarios").select("*").order("cargo_funcao").execute()
        if res and res.data:
            militares = []
            for u in res.data:
                num_pol = str(u.get("usuario_login") or u.get("usuario") or u.get("num_policia", "")).strip().upper()
                if not num_pol or num_pol == "N/I":
                    continue

                lotacao_str = str(u.get("unidade") or u.get("lotacao") or "21º BPM").strip().upper()
                bpm_mae = extrair_bpm_mae(lotacao_str)

                militares.append({
                    "id": str(u.get("id")),
                    "num_policia": num_pol,
                    "posto_grad": str(u.get("cargo_funcao") or u.get("posto_grad") or "SD").strip().upper(),
                    "nome_guerra": str(u.get("nome_guerra") or "MILITAR").strip().upper(),
                    "nome_completo": str(u.get("nome_completo") or u.get("nome_guerra") or "MILITAR").strip().upper(),
                    "cidade": str(u.get("cidade") or "UBÁ").strip().upper(),
                    "unidade": bpm_mae,
                    "lotacao": lotacao_str,
                    "nivel_acesso": str(u.get("nivel_acesso") or "TROPA").strip().upper(),
                    "perfil_creds": str(u.get("perfil_creds") or "TROPA").strip().upper(),
                    "perfil_escala": str(u.get("perfil_escala") or "TROPA").strip().upper(),
                    "ativo": bool(u.get("ativo", True))
                })
            st.session_state["lista_militares"] = militares
            return militares
    except Exception as e:
        print(f"Aviso ao carregar militares da tabela usuarios: {e}")
    return st.session_state.get("lista_militares", [])

def salvar_militares_supabase(lista_militares: list[dict]) -> bool:
    """Grava/atualiza militares diretamente na tabela unificada 'usuarios'."""
    if not supabase or not lista_militares:
        return False
    try:
        dados_salvar = []
        for m in lista_militares:
            num_pol_raw = str(m.get("num_policia", "N/I")).strip().upper()
            if not num_pol_raw or num_pol_raw == "N/I":
                continue

            num_pol_limpo = re.sub(r'\D', '', num_pol_raw)
            lotacao_full = str(m.get("lotacao") or m.get("unidade") or "21º BPM").strip().upper()

            dados_salvar.append({
                "usuario_login": num_pol_limpo,
                "usuario": num_pol_limpo,
                "cargo_funcao": m.get("posto_grad", "SD"),
                "nome_guerra": str(m.get("nome_guerra", "MILITAR")).strip().upper(),
                "nome_completo": str(m.get("nome_completo") or m.get("nome_guerra")).strip().upper(),
                "cidade": str(m.get("cidade", "UBÁ")).strip().upper(),
                "unidade": lotacao_full,
                "ativo": True
            })

        for payload in dados_salvar:
            supabase.table("usuarios").upsert(payload, on_conflict="usuario_login").execute()

        st.cache_data.clear()
        st.session_state["lista_militares"] = carregar_militares_supabase()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar na tabela usuarios: {e}")
        return False

# =========================================================================
# 4. GESTÃO DE ESCALAS MENSAIS E PERSISTÊNCIA DO QUADRO 5
# =========================================================================
@st.cache_data(ttl=180, show_spinner=False)
def carregar_escala_mensal_cache(ano: int, mes: int, equipe_nome: str = None) -> list[dict]:
    """Recupera as escalas salvas no Supabase com suporte a cache local."""
    if not supabase:
        return []
    try:
        q = supabase.table("escalas_mensais").select("*").eq("ano", int(ano)).eq("mes", int(mes))
        if equipe_nome:
            q = q.eq("equipe_nome", str(equipe_nome))
        res = q.execute()
        return res.data or []
    except Exception as e:
        print(f"Aviso ao carregar escala do cache: {e}")
        return []

def salvar_escala_mensal_supabase(ano: int, mes: int, equipe_nome: str, modalidade: str, matriz_dados: dict, elaborado_por: str, homologado_por: str, status: str = "HOMOLOGADA") -> bool:
    """Insere ou atualiza a matriz de escala mensal na tabela 'escalas_mensais'."""
    if not supabase:
        return False
    try:
        payload = {
            "ano": int(ano),
            "mes": int(mes),
            "equipe_nome": str(equipe_nome),
            "modalidade": str(modalidade),
            "modalidade_turno": str(modalidade),
            "status": status,
            "matriz_dados": matriz_dados,
            "elaborado_por": elaborado_por,
            "homologado_por": homologado_por
        }

        res = supabase.table("escalas_mensais")\
            .select("id")\
            .eq("ano", int(ano))\
            .eq("mes", int(mes))\
            .eq("equipe_nome", str(equipe_nome))\
            .execute()

        if res and res.data and len(res.data) > 0:
            rec_id = res.data[0]["id"]
            supabase.table("escalas_mensais").update(payload).eq("id", rec_id).execute()
        else:
            supabase.table("escalas_mensais").insert(payload).execute()

        st.cache_data.clear()
        return True
    except Exception as e:
        try:
            payload.pop("modalidade_turno", None)
            res = supabase.table("escalas_mensais").select("id").eq("ano", int(ano)).eq("mes", int(mes)).eq("equipe_nome", str(equipe_nome)).execute()
            if res and res.data and len(res.data) > 0:
                supabase.table("escalas_mensais").update(payload).eq("id", res.data[0]["id"]).execute()
            else:
                supabase.table("escalas_mensais").insert(payload).execute()
            st.cache_data.clear()
            return True
        except Exception as ex_fallback:
            st.error(f"Erro ao salvar escala no Supabase: {ex_fallback}")
            return False

# =========================================================================
# 5. MENSAGENS, SOLICITAÇÕES E ATUALIZAÇÃO DE USUÁRIOS
# =========================================================================
def atualizar_usuario_supabase(identificador: str, dados: dict) -> bool:
    if not supabase or not identificador:
        return False
    try:
        u_raw = str(identificador).strip().upper()
        u_limpo = re.sub(r'\D', '', u_raw)
        
        condicao_busca = f"usuario_login.eq.{u_raw},usuario_login.eq.{u_limpo},usuario.eq.{u_raw},usuario.eq.{u_limpo}"
        supabase.table("usuarios").update(dados).or_(condicao_busca).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        print(f"Erro ao atualizar usuario: {e}")
        return False

def salvar_mensagem_p1_supabase(num_policia, nome_militar, assunto, mensagem) -> bool:
    if not supabase:
        return False
    try:
        payload = {
            "num_policia": num_policia,
            "nome_militar": nome_militar,
            "assunto": assunto,
            "mensagem": mensagem,
            "data_envio": datetime.datetime.now().isoformat()
        }
        supabase.table("mensagens_p1").insert(payload).execute()
        return True
    except Exception as e:
        print(f"Erro ao salvar mensagem P1: {e}")
        return False

# =========================================================================
# 6. AUDITORIA E HISTÓRICO
# =========================================================================
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