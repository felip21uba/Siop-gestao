import streamlit as st
import datetime
from core.database import supabase, atualizar_usuario_supabase, registrar_audit_log

# Importação das abas do Módulo TCO
from modules.tco.views import renderizar_aba_importar_reds, renderizar_aba_painel_creds
from modules.tco.views_tramitacao_unificada import renderizar_aba_custodia_tramitacao_unificada
from modules.tco.views_oficios import renderizar_aba_oficios
from modules.tco.views_gestores import renderizar_aba_gestores_creds

def verificar_e_exigir_termo_tco(usr_dados):
    """Exige obrigatoriamente o aceite do Termo de Compliance TCO no primeiro acesso do militar ao módulo."""
    if not usr_dados or not isinstance(usr_dados, dict):
        return True

    # Verifica se já aceitou o termo
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

    if st.button("✅ Confirmar Aceite e Acessar Módulo TCO", type="primary", use_container_width=True, disabled=not aceito, key="btn_aceite_termo_tco_primeiro_acesso"):
        login_usr = str(usr_dados.get("usuario_login") or usr_dados.get("num_policia") or "").strip()
        now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Grava a confirmação no Supabase
        if supabase and login_usr:
            try:
                atualizar_usuario_supabase(login_usr, {
                    "termo_compliance_aceito": True,
                    "data_aceite_compliance": now_iso
                })
            except Exception as ex:
                st.error(f"Erro ao registrar aceite no banco: {ex}")

        # Atualiza a sessão ativa local
        st.session_state["usuario_dados"]["termo_compliance_aceito"] = True
        st.session_state["usuario_dados"]["termo_tco_aceito"] = True

        registrar_audit_log(
            usuario=login_usr,
            alvo="MODULO_TCO",
            acao="ACEITE_TERMO_COMPLIANCE",
            detalhe=f"Aceite do termo de compliance do Módulo TCO realizado em {now_iso}."
        )
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

    # Mapeamento do subnav vindo da barra lateral ou abas padrão
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

    if "Importar REDS" in subnav:
        renderizar_aba_importar_reds(nome_militar, unidade_militar)
    elif "Meus Materiais" in subnav or "Tramitação" in subnav:
        renderizar_aba_custodia_tramitacao_unificada(all_bens, nome_militar, unidade_militar)
    elif "Ofícios" in subnav:
        renderizar_aba_oficios(all_bens, nome_militar, unidade_militar)
    elif "Painel CREDS" in subnav:
        renderizar_aba_painel_creds(all_bens, nome_militar, unidade_militar)
    elif "Gestores" in subnav:
        renderizar_aba_gestores_creds()
    else:
        renderizar_aba_custodia_tramitacao_unificada(all_bens, nome_militar, unidade_militar)