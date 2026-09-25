import datetime
import hashlib
import os
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# =========================================================================
# CONEXÃO COM O SUPABASE
# =========================================================================
@st.cache_resource
def conectar_supabase() -> Client | None:
    """Abre a conexão com o Supabase usando as chaves do secrets.toml ou variáveis de ambiente."""
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

supabase = conectar_supabase()

def init_db():
    """Garante compatibilidade de inicialização da conexão com o banco de dados."""
    pass

# =========================================================================
# GESTÃO E ATUALIZAÇÃO DE USUÁRIOS
# =========================================================================
def atualizar_usuario_supabase(identificador: str, dados: dict) -> bool:
    """Atualiza dados do usuário no Supabase por login, usuario ou e-mail."""
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

# =========================================================================
# LEITURA E GRAVAÇÃO DO EFETIVO DE MILITARES & SINCRONIZAÇÃO DE USUÁRIOS
# =========================================================================
@st.cache_data(ttl=300)
def carregar_militares_supabase() -> list[dict]:
    """Busca a lista de militares no banco com busca resiliente nas tabelas efetivo e militares."""
    if not supabase:
        return []
    try:
        # 1. Tenta carregar primeiro da tabela 'efetivo'
        dados_brutos = []
        try:
            res = supabase.table("efetivo").select("*").execute()
            if res and res.data:
                dados_brutos = res.data
        except Exception:
            pass

        # 2. Fallback silencioso para a tabela/view 'militares'
        if not dados_brutos:
            try:
                res_m = supabase.table("militares").select("*").execute()
                if res_m and res_m.data:
                    dados_brutos = res_m.data
            except Exception:
                pass

        militares = []
        for r in dados_brutos:
            militares.append({
                "id": str(r.get("id")),
                "num_policia": str(r.get("num_policia", "N/I")).strip().upper(),
                "posto_grad": r.get("posto_grad", "SD"),
                "nome_guerra": str(r.get("nome_guerra", "MILITAR")).strip().upper(),
                "nome_completo": str(r.get("nome_completo") or r.get("nome_guerra", "MILITAR")).strip().upper(),
                "cidade": str(r.get("cidade", "N/I")).strip().upper(),
                "peso": r.get("peso", 99),
                "ordem_manual": r.get("ordem_manual", 1),
                "unidade": str(r.get("unidade", "UNIDADE N/I")).strip().upper(),
                "nivel_acesso": r.get("nivel_acesso", "TROPA")
            })
        return militares
    except Exception as e:
        st.warning(f"Aviso ao carregar militares do Supabase: {e}")
        return []

def sincronizar_contas_usuarios_do_efetivo(lista_militares: list[dict]):
    """Garante que todo militar importado receba uma conta de usuário na tabela 'usuarios'."""
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
            try:
                supabase.table("usuarios").upsert(novos_usuarios, on_conflict="usuario_login").execute()
            except Exception:
                for nu in novos_usuarios:
                    try:
                        supabase.table("usuarios").insert(nu).execute()
                    except Exception:
                        pass
    except Exception as e:
        print(f"Erro ao sincronizar contas de usuários do efetivo: {e}")

def salvar_militares_supabase(lista_militares: list[dict]) -> bool:
    """Grava/atualiza militares no Supabase e mantêm os dados fixos na sessão local do Streamlit."""
    if not supabase or not lista_militares:
        return False
    try:
        dados_salvar = []
        for m in lista_militares:
            num_pol = str(m.get("num_policia", "N/I")).strip().upper()
            nome_g = str(m.get("nome_guerra", "MILITAR")).strip().upper()
            nome_c = str(m.get("nome_completo") or nome_g).strip().upper()

            item = {
                "id": str(m.get("id")),
                "num_policia": num_pol,
                "posto_grad": m.get("posto_grad", "SD"),
                "nome_guerra": nome_g,
                "nome_completo": nome_c,
                "cidade": str(m.get("cidade", "N/I")).strip().upper(),
                "peso": m.get("peso", 99),
                "ordem_manual": m.get("ordem_manual", 1),
                "unidade": str(m.get("unidade", "UNIDADE N/I")).strip().upper(),
                "nivel_acesso": m.get("nivel_acesso", "TROPA")
            }
            dados_salvar.append(item)

        # 1. Tenta salvar na tabela 'efetivo' ou 'militares'
        try:
            supabase.table("efetivo").upsert(dados_salvar, on_conflict="num_policia").execute()
        except Exception:
            supabase.table("militares").upsert(dados_salvar, on_conflict="num_policia").execute()

        # 2. Sincroniza logons de usuários
        sincronizar_contas_usuarios_do_efetivo(lista_militares)

        # 3. MANTÉM OS DADOS SALVOS NA SESSÃO E LIMPA O CACHE DE LEITURA
        st.session_state["lista_militares"] = lista_militares
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar militares no Supabase: {e}")
        return False

# =========================================================================
# GRAVAÇÃO DE ESCALAS, PERMUTAS E MENSAGENS P1
# =========================================================================
def salvar_escala_mensal_supabase(ano: int, mes: int, equipe_nome: str, modalidade: str, matriz_dados: dict, elaborado_por: str, homologado_por: str, status: str = "HOMOLOGADA") -> bool:
    """Salva a escala de forma totalmente compatível sem depender de restrições UNIQUE do banco."""
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
# REGISTRO AUDITÁVEL E BUSCA CONSOLIDADA DE LOGS
# =========================================================================
def registrar_audit_log(operador_pm: str, alvo_pm: str | None, tipo_acao: str, descricao: str):
    """Grava o evento de auditoria diretamente na tabela 'historico_auditoria' do Supabase."""
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
    """Busca o histórico unificando 'historico_auditoria', 'historico_logins' e 'tco_logs' com a coluna 'data_hora'."""
    if not supabase:
        return pd.DataFrame(columns=["data_hora", "usuario", "acao", "detalhe"])

    logs = []

    # 1. Tabela: historico_auditoria
    try:
        res_aud = supabase.table("historico_auditoria").select("*").order("data_hora", desc=True).limit(limite).execute()
        if res_aud and res_aud.data:
            for r in res_aud.data:
                logs.append({
                    "data_hora": r.get("data_hora", r.get("created_at", "N/I")),
                    "usuario": r.get("militar_operador", "SISTEMA"),
                    "acao": r.get("tipo_acao", "AUDITORIA"),
                    "detalhe": r.get("descricao_detalhada", "")
                })
    except Exception as e:
        print(f"Aviso na consulta de historico_auditoria: {e}")

    # 2. Tabela: historico_logins
    try:
        res_logins = supabase.table("historico_logins").select("*").order("data_hora", desc=True).limit(limite).execute()
        if res_logins and res_logins.data:
            for r in res_logins.data:
                logs.append({
                    "data_hora": r.get("data_hora", "N/I"),
                    "usuario": r.get("usuario_login", "SISTEMA"),
                    "acao": "LOGIN_SESSAO",
                    "detalhe": f"Acesso efetuado no sistema. IP: {r.get('ip_origem') or 'N/I'}"
                })
    except Exception as e:
        print(f"Aviso na consulta de historico_logins: {e}")

    # 3. Tabela: tco_logs
    try:
        res_tco = supabase.table("tco_logs").select("*").order("data_hora", desc=True).limit(limite).execute()
        if res_tco and res_tco.data:
            for r in res_tco.data:
                logs.append({
                    "data_hora": r.get("data_hora", "N/I"),
                    "usuario": r.get("origem", "SISTEMA TCO"),
                    "acao": r.get("acao", "CUSTÓDIA TCO"),
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