import streamlit as st
import pandas as pd
import hashlib
import os
from supabase import create_client, Client

@st.cache_resource
def conectar_supabase() -> Client | None:
    """Abre a conexão com o Supabase usando as chaves do secrets.toml ou ambiente."""
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

def atualizar_usuario_supabase(identificador: str, dados: dict) -> bool:
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

@st.cache_data(ttl=300)
def carregar_militares_supabase() -> list[dict]:
    if not supabase:
        return []
    try:
        res = supabase.table("militares").select("*").execute()
        if res and res.data:
            militares = []
            for r in res.data:
                militares.append({
                    "id": r["id"],
                    "num_policia": r.get("num_policia", "N/I"),
                    "posto_grad": r.get("posto_grad", "SD"),
                    "nome_guerra": r.get("nome_guerra", "MILITAR"),
                    "nome_completo": r.get("nome_completo", r.get("nome_guerra", "MILITAR")),
                    "cidade": r.get("cidade", "N/I"),
                    "peso": r.get("peso", 99),
                    "ordem_manual": r.get("ordem_manual", 1),
                    "unidade": r.get("unidade", "35ª CIA PM"),
                    "nivel_acesso": r.get("nivel_acesso", "TROPA")
                })
            return militares
    except Exception as e:
        st.warning(f"Aviso ao carregar militares do Supabase: {e}")
    return []

def sincronizar_contas_usuarios_do_efetivo(lista_militares: list[dict]):
    if not supabase or not lista_militares:
        return
    try:
        res_u = supabase.table("usuarios").select("usuario_login, usuario").execute()
        existentes = set()
        if res_u and res_u.data:
            for u in res_u.data:
                if u.get("usuario_login"):
                    existentes.add(str(u.get("usuario_login")).strip().upper())
                if u.get("usuario"):
                    existentes.add(str(u.get("usuario")).strip().upper())

        novos_usuarios = []
        for m in lista_militares:
            num_pol = str(m.get("num_policia", "")).strip().upper()
            if num_pol and num_pol != "N/I" and num_pol not in existentes:
                hash_init = hashlib.sha256(num_pol.encode('utf-8')).hexdigest().lower()
                novos_usuarios.append({
                    "usuario_login": num_pol,
                    "usuario": num_pol,
                    "nome_guerra": m.get("nome_guerra", "MILITAR"),
                    "cargo_funcao": m.get("posto_grad", "SD"),
                    "nivel_acesso": m.get("nivel_acesso", "TROPA"),
                    "senha": num_pol,
                    "senha_hash": hash_init,
                    "ativo": True,
                    "primeiro_acesso": True
                })

        if novos_usuarios:
            supabase.table("usuarios").upsert(novos_usuarios, on_conflict="usuario_login").execute()
    except Exception as e:
        print(f"Erro ao sincronizar contas de usuários do efetivo: {e}")

def salvar_militares_supabase(lista_militares: list[dict]) -> bool:
    if not supabase or not lista_militares:
        return False
    try:
        dados_salvar = []
        for m in lista_militares:
            dados_salvar.append({
                "id": str(m["id"]),
                "num_policia": str(m.get("num_policia", "N/I")),
                "posto_grad": m.get("posto_grad", "SD"),
                "nome_guerra": m.get("nome_guerra", "MILITAR"),
                "nome_completo": m.get("nome_completo", m.get("nome_guerra", "MILITAR")),
                "cidade": str(m.get("cidade", "N/I")).strip().upper(),
                "peso": m.get("peso", 99),
                "ordem_manual": m.get("ordem_manual", 1),
                "unidade": m.get("unidade", "35ª CIA PM"),
                "nivel_acesso": m.get("nivel_acesso", "TROPA")
            })
        supabase.table("militares").upsert(dados_salvar).execute()
        sincronizar_contas_usuarios_do_efetivo(lista_militares)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar militares no Supabase: {e}")
        return False

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

def registrar_audit_log(operador_pm: str, alvo_pm: str | None, tipo_acao: str, descricao: str):
    """Grava evento de auditoria no Supabase."""
    if supabase:
        try:
            supabase.table("historico_auditoria").insert({
                "militar_operador": str(operador_pm),
                "militar_alvo": str(alvo_pm) if alvo_pm else None,
                "tipo_acao": str(tipo_acao),
                "descricao_detalhada": str(descricao)
            }).execute()
        except Exception as e:
            print(f"Erro ao gravar audit log no Supabase: {e}")

def registrar_log_banco(usuario_dados, acao, detalhe):
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
    """Busca os registros consolidando as tabelas 'historico_auditoria' e 'tco_logs'."""
    if not supabase:
        return pd.DataFrame(columns=["data_hora", "usuario", "acao", "detalhe"])
    
    logs = []
    
    try:
        res_aud = supabase.table("historico_auditoria").select("*").order("created_at", desc=True).limit(limite).execute()
        if res_aud and res_aud.data:
            for r in res_aud.data:
                logs.append({
                    "data_hora": r.get("created_at", r.get("data_hora", "")),
                    "usuario": r.get("militar_operador", "SISTEMA"),
                    "acao": r.get("tipo_acao", "AÇÃO"),
                    "detalhe": r.get("descricao_detalhada", "")
                })
    except Exception as e:
        print(f"Aviso na consulta de historico_auditoria: {e}")

    try:
        res_tco = supabase.table("tco_logs").select("*").order("data_hora", desc=True).limit(limite).execute()
        if res_tco and res_tco.data:
            for r in res_tco.data:
                logs.append({
                    "data_hora": r.get("data_hora", r.get("created_at", "")),
                    "usuario": r.get("origem", "SISTEMA TCO"),
                    "acao": r.get("acao", "TCO"),
                    "detalhe": f"REDS: {r.get('num_reds', 'N/I')} | {r.get('detalhe', '')}"
                })
    except Exception as e:
        print(f"Aviso na consulta de tco_logs: {e}")

    if logs:
        df = pd.DataFrame(logs)
        df["dt_sort"] = pd.to_datetime(df["data_hora"], errors="coerce")
        df = df.sort_values(by="dt_sort", ascending=False).drop(columns=["dt_sort"])
        return df
    
    return pd.DataFrame(columns=["data_hora", "usuario", "acao", "detalhe"])