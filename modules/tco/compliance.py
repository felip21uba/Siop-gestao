import streamlit as st
import datetime
from core.database import supabase

TEXTO_TERMO_COMPLIANCE = """
### TERMO DE COMPROMISSO, CONFIDENCIALIDADE E COMPLIANCE OPERACIONAL
**SISTEMA INTEGRADO DE OPERAÇÕES POLICIAIS (SIOP) — MÓDULO TCO & CUSTÓDIA DE MATERIAIS (CREDS)**

Pelo presente instrumento, o Policial Militar/Operador devidamente autenticado declara ciência e concordância integral com as normas de segurança, privacidade e procedimentos legais descritos abaixo:

1. **DA CADEIA DE CUSTÓDIA (ART. 158-A AO 158-F DO CPP):**
   1.1. O operador compromete-se a assegurar a rastreabilidade e a inviolabilidade dos elementos probatórios apreendidos, utilizando obrigatoriamente o registro de invólucros/lacres oficiais.
   1.2. Qualquer divergência observada na conferência física do material (violação de lacre, avaria ou diferença de quantidade) deve ser obrigatoriamente registrada na função de "Divergência/Recusa" do sistema.

2. **DA RESPONSABILIDADE SOBRE DADOS E LGPD (LEI Nº 13.709/2018):**
   2.1. Todas as informações de qualificação de civis, testemunhas, vítimas e infratores acessadas via REDS/TCO são estritamente confidenciais e de uso exclusivo para instrução de procedimentos oficiais.
   2.2. É expressamente vedado o compartilhamento, extração não autorizada, captura de tela ou divulgação de dados sensíveis para finalidades alheias ao serviço policial militar.

3. **DA IRRETRATABILIDADE E AUDITORIA DE AÇÕES:**
   3.1. O operador declara ciência de que **todas as edições de materiais, uploads de mídias, solicitações de tramitação, aceite e rejeição de custódia** são gravados com chancela SHA-256 e IP de conexão na trilha imutável de auditoria (`tco_logs`).
   3.2. As alterações manuais de dados importados do REDS exigem justificativa fundamentada, sujeita à fiscalização da Seção de P1/CREDS e Corregedoria.

4. **DO USO DE CREDENCIAIS PESSOAIS:**
   4.1. A senha e as chaves de acesso ao SIOP são pessoais e intransferíveis. O militar responde administrativa, civil e penalmente por todos os atos praticados sob sua autenticação.
"""

def verificar_aceite_compliance_supabase(usuario_id):
    """Verifica no Supabase se o usuário já assinou o Termo de Compliance do TCO."""
    if not supabase or not usuario_id:
        return True
    try:
        res = supabase.table("tco_compliance_aceites").select("*").eq("usuario_id", usuario_id).execute()
        return len(res.data) > 0 if res.data else False
    except Exception:
        return False

def registrar_aceite_compliance_supabase(usuario_id, nome_militar, cargo_funcao, unidade):
    """Grava o registro de aceite do Termo de Compliance com carimbo de data/hora no Supabase."""
    if not supabase or not usuario_id:
        return False
    try:
        now_iso = datetime.datetime.now().isoformat()
        dados_aceite = {
            "usuario_id": usuario_id,
            "nome_militar": nome_militar,
            "cargo_funcao": cargo_funcao,
            "unidade": unidade,
            "data_aceite": now_iso,
            "versao_termo": "1.0 - 2026"
        }
        
        supabase.table("tco_compliance_aceites").insert(dados_aceite).execute()
        
        supabase.table("tco_logs").insert({
            "data_hora": now_iso,
            "num_reds": "COMPLIANCE-SISTEMA",
            "bem_id": "ACEITE-TERMO",
            "acao": "ACEITE DO TERMO DE COMPLIANCE TCO/CREDS",
            "origem": nome_militar,
            "unidade_origem": unidade,
            "destino": "SIOP COMPLIANCE",
            "unidade_destino": unidade,
            "detalhe": f"Militar {nome_militar} ({cargo_funcao}) confirmou leitura e aceite do Termo de Compliance v1.0."
        }).execute()
        
        return True
    except Exception as e:
        st.error(f"Erro ao registrar aceite de compliance: {e}")
        return False

def renderizar_modal_termo_compliance():
    """Exibe o termo para validação obrigatória caso o usuário ainda não tenha assinado."""
    usr_logado = st.session_state.get("usuario_dados", {})
    usr_id = str(usr_logado.get("id") or usr_logado.get("usuario_login") or "").strip()
    nome_m = f"{usr_logado.get('cargo_funcao', 'POLICIAL')} {usr_logado.get('nome_guerra', 'OPERADOR')}".strip()
    cargo_f = str(usr_logado.get("cargo_funcao", "POLICIAL MILITAR")).strip()
    unidade_m = str(usr_logado.get("unidade", "35ª CIA PM")).strip()

    if not verificar_aceite_compliance_supabase(usr_id):
        st.warning("⚠️ **ATENÇÃO: Aceite de Compliance Obrigatório para Uso do TCO / CREDS**")
        
        with st.container(border=True):
            st.markdown(TEXTO_TERMO_COMPLIANCE)
            st.divider()
            
            chk_concordo = st.checkbox("Li, compreendi e concordo integralmente com os termos de segurança, LGPD e procedimentos da Cadeia de Custódia.", key="chk_aceite_compliance_tco")
            
            if st.button("🖊️ Assinar Eletronicamente e Liberar Acesso ao TCO", type="primary", use_container_width=True):
                if not chk_concordo:
                    st.error("Você precisa marcar a caixa de confirmação antes de prosseguir.")
                else:
                    if registrar_aceite_compliance_supabase(usr_id, nome_m, cargo_f, unidade_m):
                        st.success("✅ Termo de Compliance assinado com sucesso!")
                        st.rerun()
        st.stop()