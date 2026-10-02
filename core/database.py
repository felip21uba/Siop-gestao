"""
==============================================================================
Módulo de Infraestrutura de Banco de Dados Central (core/database.py)
Gerencia a conexão unificada com o Supabase na tabela 'usuarios', 
extração do Batalhão Mãe (Multi-Tenant) e auditoria de sistema.
==============================================================================
"""

import datetime
import hashlib
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
    """Abre e otimiza a conexão estática com o cliente do Supabase."""
    try:
        url = None
        key = None
        if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        else:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            return None
            
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Erro crítico ao conectar no Supabase: {e}")
        return None

# Instância estática global do cliente Supabase
supabase = conectar_supabase()

def init_db():
    """Garante compatibilidade de inicialização da conexão no bootstrap da aplicação."""
    pass

# =========================================================================
# 2. ISOLAMENTO MULTI-TENANT & EXTRAÇÃO DE BATALHÃO MÃE (BPM)
# =========================================================================
def extrair_bpm_mae(texto_unidade: str) -> str:
    """
    Extrai o Batalhão Principal (Unidade Mãe) de qualquer string de lotação.
    Exemplos:
      '1 PEL/31 CIA PM/2 BPM' -> '2º BPM'
      '2º BPM / 31ª CIA PM' -> '2º BPM'
      '1 PEL/111 CIA PM/21 BPM/4 RPM' -> '21º BPM'
    """
    if not texto_unidade or str(texto_unidade).upper() in ["NONE", "NAN", "N/I", "UNIDADE N/I"]:
        return "21º BPM"

    txt = str(texto_unidade).strip().upper()
    
    match = re.search(r'(\d+)\s*º?\s*BPM', txt)
    if match:
        num_bpm = match.group(1)
        return f"{num_bpm}º BPM"

    return txt

def obter_unidade_operacao_atual() -> str:
    """
    Retorna a unidade sobre a qual o operador possui autoridade de visualização.
    - PROGRAMADOR / ADMIN: Usa o filtro escolhido no Seletor da Barra Lateral.
    - TROPA / GESTOR LOCAL: Usa estritamente a unidade cadastrada no perfil do usuário logado.
    """
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

# =========================================================================
# 3. CAPTURA AUTOMÁTICA DO IP REAL DO CLIENTE
# =========================================================================
def obter_ip_cliente_real() -> str:
    """Extrai o IP público/real da conexão do usuário através dos cabeçalhos HTTP do Streamlit."""
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers  # type: ignore
        headers = _get_websocket_headers()
        if headers:
            x_forwarded_for = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for")
            if x_forwarded_for:
                ip_cliente = x_forwarded_for.split(",")[0].strip()
                if ip_cliente:
                    return ip_cliente
            
            x_real_ip = headers.get("X-Real-IP") or headers.get("x-real-ip")
            if x_real_ip:
                return x_real_ip.strip()

            remote_ip = headers.get("Host") or headers.get("host")
            if remote_ip:
                return remote_ip.split(":")[0].strip()
    except Exception:
        pass
    
    try:
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            xf_ctx = st.context.headers.get("x-forwarded-for") or st.context.headers.get("X-Forwarded-For")
            if xf_ctx:
                return xf_ctx.split(",")[0].strip()
    except Exception:
        pass

    return "127.0.0.1"

# =========================================================================
# 4. GESTÃO E LEITURA UNIFICADA DA TABELA 'USUARIOS'
# =========================================================================
def atualizar_usuario_supabase(identificador: str, dados: dict) -> bool:
    """Atualiza dados do usuário no Supabase por login, usuario ou e-mail e invalida o cache."""
    if not supabase or not identificador:
        return False
    try:
        u_clean = str(identificador).strip()
        res = supabase.table("usuarios").update(dados).or_(
            f"usuario_login.eq.{u_clean},usuario.eq.{u_clean},email_recuperacao.eq.{u_clean}"
        ).execute()
        
        if res and res.data and len(res.data) > 0:
            st.cache_data.clear()
            return True
        return False
    except Exception as e:
        st.error(f"Erro ao atualizar usuário no Supabase: {e}")
        return False

@st.cache_data(ttl=300, show_spinner=False)
def carregar_militares_supabase() -> list[dict]:
    """
    Busca a lista de militares UNIFICADA diretamente da tabela 'usuarios'.
    Elimina permanentemente a dependência da antiga tabela 'efetivo'.
    """
    if not supabase:
        return st.session_state.get("lista_militares", [])

    try:
        res = supabase.table("usuarios").select("*").order("cargo_funcao").execute()
        if res and res.data:
            militares_unificados = []
            for u in res.data:
                num_pol = str(u.get("usuario_login") or u.get("usuario") or "").strip().upper()
                if not num_pol or num_pol == "N/I":
                    continue

                lotacao_str = str(u.get("unidade") or "21º BPM").strip().upper()
                bpm_mae = extrair_bpm_mae(lotacao_str)

                militares_unificados.append({
                    "id": str(u.get("id")),
                    "num_policia": num_pol,
                    "posto_grad": str(u.get("cargo_funcao") or "SD").strip().upper(),
                    "nome_guerra": str(u.get("nome_guerra") or "MILITAR").strip().upper(),
                    "nome_completo": str(u.get("nome_completo") or u.get("nome_guerra") or "MILITAR").strip().upper(),
                    "cidade": str(u.get("cidade") or "UBÁ").strip().upper(),
                    "unidade": bpm_mae,               # Batalhão Mãe (ex: "2º BPM")
                    "lotacao": lotacao_str,            # Lotação Completa (ex: "1 PEL/31 CIA PM/2 BPM")
                    "nivel_acesso": u.get("nivel_acesso", "TROPA"),
                    "perfil_creds": u.get("perfil_creds", "TROPA"),
                    "perfil_escala": u.get("perfil_escala", "TROPA"),
                    "ativo": u.get("ativo", True)
                })
            
            st.session_state["lista_militares"] = militares_unificados
            return militares_unificados
    except Exception as e:
        print(f"Erro ao carregar militares da tabela usuarios: {e}")
        return st.session_state.get("lista_militares", [])

def salvar_militares_supabase(lista_militares: list[dict]) -> bool:
    """
    Grava/atualiza militares DIRETAMENTE na tabela 'usuarios' do Supabase.
    Possui tratamento de fallback para schemas sem a coluna 'cidade'.
    """
    if not supabase or not lista_militares:
        return False
    try:
        dados_salvar = []
        for m in lista_militares:
            num_pol = str(m.get("num_policia", "N/I")).strip().upper()
            if not num_pol or num_pol == "N/I":
                continue

            nome_g = str(m.get("nome_guerra", "MILITAR")).strip().upper()
            nome_c = str(m.get("nome_completo") or nome_g).strip().upper()
            lotacao_full = str(m.get("lotacao") or m.get("unidade") or "21º BPM").strip().upper()

            item = {
                "usuario_login": num_pol,
                "usuario": num_pol,
                "cargo_funcao": m.get("posto_grad", "SD"),
                "nome_guerra": nome_g,
                "nome_completo": nome_c,
                "cidade": str(m.get("cidade", "UBÁ")).strip().upper(),
                "unidade": lotacao_full,
                "ativo": m.get("ativo", True)
            }
            dados_salvar.append(item)

        try:
            supabase.table("usuarios").upsert(dados_salvar, on_conflict="usuario_login").execute()
        except Exception as ex_cidade:
            print(f"Aviso ao salvar com coluna cidade ({ex_cidade}). Aplicando fallback sem cidade...")
            for item in dados_salvar:
                item.pop("cidade", None)
            supabase.table("usuarios").upsert(dados_salvar, on_conflict="usuario_login").execute()

        st.session_state["lista_militares"] = lista_militares
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar militares na tabela usuarios: {e}")
        return False

# =========================================================================
# 5. ESCALAS MENSAIS E SESSÃO
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

def salvar_mensagem_p1_supabase(remetente_id, remetente_nome, assunto, mensagem) -> bool:
    """Envia uma solicitação para a P1 na tabela 'mensagens_p1'."""
    if not supabase:
        return False
    try:
        payload = {
            "remetente_id": str(remetente_id),
            "assunto": assunto,
            "mensagem": mensagem,
            "status": "RECEBIDA"
        }
        supabase.table("mensagens_p1").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao enviar mensagem no Supabase: {e}")
        return False

# =========================================================================
# 6. AUDITORIA E LOGS
# =========================================================================
def registrar_audit_log(operador_pm: str, alvo_pm: str | None, tipo_acao: str, descricao: str):
    """Grava o evento de auditoria capturando automaticamente o IP público real da conexão."""
    if supabase:
        try:
            ip_real = obter_ip_cliente_real()
            
            supabase.table("historico_auditoria").insert({
                "militar_operador": str(operador_pm),
                "militar_alvo": str(alvo_pm) if alvo_pm else None,
                "tipo_acao": str(tipo_acao),
                "descricao_detalhada": str(descricao),
                "ip_origem": ip_real
            }).execute()
            st.cache_data.clear()
        except Exception as e:
            print(f"Erro ao gravar audit log no Supabase: {e}")

def registrar_log_banco(usuario_dados, acao, detalhe):
    """Função auxiliar para salvar logs a partir do dicionário de dados do usuário."""
    if not isinstance(usuario_dados, dict):
        usuario_dados = {}
        
    nome_usuario = usuario_dados.get("nome_guerra", usuario_dados.get("nome", "OPERADOR"))
    cargo_usuario = usuario_dados.get("cargo_funcao", usuario_dados.get("perfil", "GESTOR"))
    usuario_formatado = f"{cargo_usuario} {nome_usuario}".strip()
    
    registrar_audit_log(
        operador_pm=usuario_formatado,
        alvo_pm=None,
        tipo_acao=acao,
        descricao=detalhe
    )

def buscar_logs_banco(limite=500) -> pd.DataFrame:
    """Busca o histórico de logs no Supabase."""
    if not supabase:
        return pd.DataFrame(columns=["data_hora", "usuario", "acao", "detalhe", "ip"])

    logs = []
    try:
        res_aud = supabase.table("historico_auditoria").select("*").order("data_hora", desc=True).limit(limite).execute()
        if res_aud and res_aud.data:
            for r in res_aud.data:
                logs.append({
                    "data_hora": r.get("data_hora", r.get("created_at", "N/I")),
                    "usuario": r.get("militar_operador", "SISTEMA"),
                    "acao": r.get("tipo_acao", "AUDITORIA"),
                    "detalhe": r.get("descricao_detalhada", ""),
                    "ip": r.get("ip_origem", "127.0.0.1")
                })
    except Exception as e:
        print(f"Aviso na consulta de historico_auditoria: {e}")

    if logs:
        df = pd.DataFrame(logs)
        df["dt_sort"] = pd.to_datetime(df["data_hora"], errors="coerce")
        df = df.sort_values(by="dt_sort", ascending=False).drop(columns=["dt_sort"])
        return df

    return pd.DataFrame(columns=["data_hora", "usuario", "acao", "detalhe", "ip"])