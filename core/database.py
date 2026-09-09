import streamlit as st
import pandas as pd
from supabase import create_client, Client

# =========================================================================
# CONEXÃO COM O SUPABASE
# =========================================================================
@st.cache_resource
def conectar_supabase() -> Client | None:
    """Abre a conexão com o Supabase usando as chaves do secrets.toml"""
    try:
        if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
            return None
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Erro crítico ao conectar no Supabase: {e}")
        return None

supabase = conectar_supabase()

def init_db():
    """Garante compatibilidade de inicialização da conexão com o banco de dados."""
    pass

# =========================================================================
# GESTÃO E ATUALIZAÇÃO DE USUÁRIOS
# =========================================================================
def atualizar_usuario_supabase(identificador: str, dados: dict) -> bool:
    """Atualiza dados do usuário no Supabase por login, usuario ou e-mail"""
    if not supabase:
        return False
    try:
        u_clean = str(identificador).strip()
        res = supabase.table("usuarios").update(dados).or_(
            f"usuario_login.eq.{u_clean},usuario.eq.{u_clean},email_recuperacao.eq.{u_clean}"
        ).execute()
        
        if res.data and len(res.data) > 0:
            st.cache_data.clear()
            return True
        return False
    except Exception as e:
        st.error(f"Erro ao atualizar usuário no Supabase: {e}")
        return False

# =========================================================================
# LEITURA E GRAVAÇÃO DO EFETIVO DE MILITARES
# =========================================================================
@st.cache_data(ttl=300)
def carregar_militares_supabase() -> list[dict]:
    """Busca a lista de militares no banco com cache de 5 minutos"""
    if not supabase:
        return []
    try:
        res = supabase.table("militares").select("*").execute()
        if res.data:
            militares = []
            for r in res.data:
                militares.append({
                    "id": r["id"],
                    "num_policia": r.get("num_policia", "N/I"),
                    "posto_grad": r["posto_grad"],
                    "nome_guerra": r["nome_guerra"],
                    "nome_completo": r.get("nome_completo", r["nome_guerra"]),
                    "peso": r.get("peso", 99),
                    "ordem_manual": r.get("ordem_manual", 1),
                    "unidade": r.get("unidade", "35ª CIA PM"),
                    "nivel_acesso": r.get("nivel_acesso", "TROPA")
                })
            return militares
    except Exception as e:
        st.warning(f"Aviso ao carregar militares do Supabase: {e}")
    return []

def salvar_militares_supabase(lista_militares: list[dict]) -> bool:
    """Grava/atualiza militares no banco e limpa o cache de leitura"""
    if not supabase:
        return False
    try:
        dados_salvar = []
        for m in lista_militares:
            dados_salvar.append({
                "id": str(m["id"]),
                "num_policia": str(m.get("num_policia", "N/I")),
                "posto_grad": m["posto_grad"],
                "nome_guerra": m["nome_guerra"],
                "nome_completo": m.get("nome_completo", m["nome_guerra"]),
                "peso": m.get("peso", 99),
                "ordem_manual": m.get("ordem_manual", 1),
                "unidade": m.get("unidade", "35ª CIA PM"),
                "nivel_acesso": m.get("nivel_acesso", "TROPA")
            })
        supabase.table("militares").upsert(dados_salvar).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar militares no Supabase: {e}")
        return False

# =========================================================================
# GRAVAÇÃO DE ESCALAS, PERMUTAS E MENSAGENS P1
# =========================================================================
def salvar_escala_mensal_supabase(ano: int, mes: int, equipe_nome: str, modalidade: str, matriz_dados: dict, elaborado_por: str, homologado_por: str, status: str = "HOMOLOGADA") -> bool:
    if not supabase:
        return False
    try:
        payload = {
            "ano": ano,
            "mes": mes,
            "equipe_nome": equipe_nome,
            "modalidade_turno": modalidade,
            "status": status,
            "matriz_dados": matriz_dados,
            "elaborado_por": elaborado_por,
            "homologado_por": homologado_por
        }
        supabase.table("escalas_mensais").upsert(payload, on_conflict="ano,mes,equipe_nome").execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar escala no Supabase: {e}")
        return False

def salvar_permuta_supabase(solicitante_id, solicitante_nome, substituto_id, substituto_nome, data_turno, motivo, documento="N/I", tipo_troca="DIRETA") -> bool:
    if not supabase:
        return False
    try:
        payload = {
            "solicitante_id": str(solicitante_id),
            "solicitante_nome": solicitante_nome,
            "substituto_id": str(substituto_id) if substituto_id else None,
            "substituto_nome": substituto_nome,
            "data_turno": data_turno,
            "motivo": motivo,
            "documento": documento,
            "tipo_troca": tipo_troca,
            "status": "PENDENTE"
        }
        supabase.table("permutas_servico").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar permuta no Supabase: {e}")
        return False

def salvar_mensagem_p1_supabase(remetente_id, remetente_nome, assunto, mensagem) -> bool:
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
# REGISTRO AUDITÁVEL DE AÇÕES DE COMANDO (LOG)
# =========================================================================
def registrar_audit_log(operador_pm: str, alvo_pm: str | None, tipo_acao: str, descricao: str):
    if supabase:
        try:
            supabase.table("historico_auditoria").insert({
                "militar_operador": str(operador_pm),
                "militar_alvo": str(alvo_pm) if alvo_pm else None,
                "tipo_acao": tipo_acao,
                "descricao_detalhada": descricao
            }).execute()
        except Exception as e:
            print(f"Erro ao gravar audit log: {e}")

def registrar_log_banco(usuario_dados, acao, detalhe):
    """Função de compatibilidade para gravar ações no Supabase via Passo 5 e Passo 7."""
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
    """Busca o histórico de auditoria diretamente da tabela historico_auditoria no Supabase."""
    if not supabase:
        return pd.DataFrame(columns=["data_hora", "usuario", "acao", "detalhe"])
    try:
        res = supabase.table("historico_auditoria").select("*").order("id", desc=True).limit(limite).execute()
        if res.data:
            logs = []
            for r in res.data:
                logs.append({
                    "data_hora": r.get("created_at", r.get("data_hora", "N/I")),
                    "usuario": r.get("militar_operador", "SISTEMA"),
                    "acao": r.get("tipo_acao", "AÇÃO"),
                    "detalhe": r.get("descricao_detalhada", "")
                })
            return pd.DataFrame(logs)
    except Exception as e:
        print(f"Erro ao buscar histórico de auditoria no Supabase: {e}")
    return pd.DataFrame(columns=["data_hora", "usuario", "acao", "detalhe"])