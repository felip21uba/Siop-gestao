import streamlit as st
from supabase import create_client, Client

# =========================================================================
# CONEXÃO COM O SUPABASE (com cache para não recriar conexão em todo rerun)
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
        st.cache_data.clear()  # Força atualização da leitura no próximo acesso
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