import streamlit as st
import datetime
from core.database import supabase, atualizar_usuario_supabase, registrar_audit_log

# Importações diretas do seu views.py existente
from modules.tco.views import (
    renderizar_aba_importar_reds, 
    renderizar_aba_painel_creds,
    renderizar_aba_gestores_creds,
    renderizar_aba_logs
)
from modules.tco.views_tramitacao_unificada import renderizar_aba_custodia_tramitacao_unificada
from modules.tco.views_oficios import renderizar_aba_gerador_oficios

def verificar_e_exigir_termo_tco(usr_dados):
    """Exige obrigatoriamente o aceite do Termo de Compliance TCO no primeiro acesso do militar ao módulo."""
    if not usr_dados or not isinstance(usr_dados, dict):
        return True

    # Verifica se já aceitou o termo na sessão ou nos dados do usuário
    ja_aceitou = usr_dados.get("termo_compliance_aceito") or usr_dados.get("termo_tco_aceito") or False
    if ja_aceitou:
        return True

    st.warning("🛡️ **ACEITE OBRIGATÓRIO: Termo de Compliance e Responsabilidade TCO/CREDS**")
    
    st.markdown("""
    <div style="background-color: #1e293b; padding: 18px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 15px;">
        <h4 style="color: #38bdf8; margin-top: 0;">📜 Termo de Adesão, Custódia e Fidelidade Processual (Art. 158-A do CPP)</h4>
        <p style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
        Ao operar o Módulo TCO/CREDS do SIOP, o(a) militar declara estar ciente e de acordo com as seguintes condições:<br><br>
        1. <b>Rastreabilidade Imutável:</b> Todas as ações de inserção de REDS, recebimento de materiais, conferência de invólucros/lacres, alteração de dados e transferência de custódia são registradas com identificação individual, data/hora e IP de origem.<br>
        2. <b>Fiel Depositário:</b> A guarda física dos bens vinculados ao seu cadastro é de sua responsabilidade até a transferência formal e aceite pelo próximo custodiante ou depósito final (PCMG/JECRIM).<br>
        3. <b>Penalidades:</b> O uso indevido do sistema, falsificação de registros ou extravio de bens sujeitará o operador às sanções disciplinares, administrativas e penais cabíveis (CPM/CPP).
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        aceito = st.checkbox("Declaro que li, compreendi e aceito integralmente o Termo de Responsabilidade TCO/CREDS.")
    
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

    if st.button("✅ Confirmar Aceite e Acessar Módulo TCO", type="primary", use_container_width=True, disabled=not aceito, key="btn_aceite_termo_tco_main_fix"):
        login_usr = str(usr_dados.get("usuario_login") or usr_dados.get("num_policia") or usr_dados.get("usuario") or "OPERADOR").strip()
        now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if supabase and login_usr:
            try:
                atualizar_usuario_supabase(login_usr, {
                    "termo_compliance_aceito": True,
                    "data_aceite_compliance": now_iso
                })
            except Exception:
                try:
                    atualizar_usuario_supabase(login_usr, {"termo_compliance_aceito": True})
                except Exception:
                    pass

        if "usuario_dados" in st.session_state and isinstance(st.session_state["usuario_dados"], dict):
            st.session_state["usuario_dados"]["termo_compliance_aceito"] = True
            st.session_state["usuario_dados"]["termo_tco_aceito"] = True

        try:
            registrar_audit_log(
                operador_pm=login_usr,
                alvo_pm="MODULO_TCO",
                tipo_acao="ACEITE_TERMO_COMPLIANCE",
                descricao=f"Aceite do termo de compliance do Módulo TCO realizado em {now_iso}."
            )
        except Exception:
            pass

        st.toast("✅ Termo de Compliance aceito com sucesso!", icon="🎉")
        st.rerun()

    st.stop()
    return False

def renderizar_modulo_tco():
    """Ponto de entrada principal do Módulo TCO/CREDS com trava de termo e subnavegação."""
    st.title("📦 Módulo TCO / Cadeia de Custódia CREDS")

    usr_dados = st.session_state.get("usuario_dados", {})
    
    # Exige aceite no primeiro acesso
    verificar_e_exigir_termo_tco(usr_dados)

    nome_militar = usr_dados.get("nome_guerra") or usr_dados.get("nome_completo") or "OPERADOR"
    unidade_militar = st.session_state.get("unidade_ativa_nome") or usr_dados.get("unidade", "21º BPM / 35ª CIA PM")

    subnav = st.session_state.get("subnav_tco", "🎒 Meus Materiais")

    st.caption(f"👤 **Operador:** {usr_dados.get('posto_grad', '')} {nome_militar} | 🏛️ **Unidade Ativa:** {unidade_militar}")
    st.divider()

    all_bens = []
    if supabase:
        try:
            res_b = supabase.table("tco_materiais").select("*").execute()
            all_bens = res_b.data or []
        except Exception as ex:
            st.error(f"Erro ao carregar acervo do TCO: {ex}")

    # Roteamento das abas utilizando as funções nativas existentes
    if "Importar REDS" in subnav:
        renderizar_aba_importar_reds(nome_militar, unidade_militar)
    elif "Meus Materiais" in subnav or "Tramitação" in subnav:
        renderizar_aba_custodia_tramitacao_unificada(all_bens, nome_militar, unidade_militar)
    elif "Ofícios" in subnav:
        renderizar_aba_gerador_oficios(all_bens, nome_militar, unidade_militar)
    elif "Painel CREDS" in subnav:
        renderizar_aba_painel_creds(all_bens, nome_militar, unidade_militar)
    elif "Auditoria" in subnav or "Logs" in subnav:
        # Busca os logs da tabela tco_logs e passa para a funcao nativa do views.py
        all_logs = []
        if supabase:
            try:
                res_l = supabase.table("tco_logs").select("*").order("data_hora", desc=True).execute()
                all_logs = res_l.data or []
            except Exception as ex:
                st.warning(f"Aviso ao consultar tco_logs: {ex}")
        renderizar_aba_logs(all_logs)
    elif "Gestores" in subnav:
        renderizar_aba_gestores_creds(nome_militar, unidade_militar, "MILITAR", "GESTOR")
    else:
        renderizar_aba_custodia_tramitacao_unificada(all_bens, nome_militar, unidade_militar)