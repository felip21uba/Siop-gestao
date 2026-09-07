import streamlit as st
import pandas as pd
import datetime

def renderizar_mural():
    st.markdown("""<style>div[data-testid="stContainer"] div[data-testid="stColumn"] button {height: auto !important; min-height: 40px !important;}</style>""", unsafe_allow_html=True)
    
    st.title("🗣️ Portal do Efetivo e Mural de Avisos")
    st.caption("Solicitação de trocas de serviço, balcão de voluntários e comunicados oficiais.")
    st.divider()

    # Identificação do Usuário Logado e Perfil
    usr_logado = st.session_state.get("usuario_dados", {})
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    perfil_str = str(usr_logado.get("perfil", "")).upper()
    eh_admin = "PROGRAMADOR" in cargo_str or "TESTADOR" in cargo_str or "ADMIN" in perfil_str or "DESENVOLVEDOR" in cargo_str
    
    # Para testes, se não houver login real, vamos permitir selecionar "quem sou eu" na tela
    mils_todos = st.session_state.get("lista_militares", [])
    if not mils_todos:
        st.warning("⚠️ Nenhum militar cadastrado. Vá ao Módulo de Escalas (Passo 3) para carregar o efetivo.")
        return

    nomes_mils = [f"{m.get('posto_grad')} {m.get('nome_guerra')}" for m in mils_todos]
    
    # SIMULADOR DE LOGIN (Remova depois se o seu app.py já fixar o usuário logado)
    with st.sidebar.expander("👤 Simulador de Usuário (Para Testes do Mural)", expanded=True):
        militar_simulado = st.selectbox("Acessar Mural como:", ["[ADMINISTRAÇÃO / P1]"] + nomes_mils)
        if militar_simulado == "[ADMINISTRAÇÃO / P1]":
            eh_admin = True
            nome_usuario_atual = "ADMINISTRAÇÃO"
        else:
            eh_admin = False
            nome_usuario_atual = militar_simulado

    # INICIALIZAÇÃO DOS BANCOS DE DADOS LOCAIS DO MURAL
    if "mural_trocas" not in st.session_state:
        st.session_state["mural_trocas"] = []
    if "mural_mensagens" not in st.session_state:
        st.session_state["mural_mensagens"] = []

    # ABAS DO MURAL
    aba1, aba2 = st.tabs(["🔄 Trocas de Serviço", "📢 Correio e Comunicados"])

    # ==========================================
    # ABA 1: TROCAS DE SERVIÇO
    # ==========================================
    with aba1:
        st.markdown("### Gestão de Trocas e Permutas")
        
        # VISÃO DO OPERADOR / MILITAR
        if not eh_admin:
            with st.form("form_nova_troca"):
                st.markdown(f"**Nova Solicitação para:** `{nome_usuario_atual}`")
                c1, c2 = st.columns(2)
                with c1:
                    tipo_troca = st.radio("Tipo de Solicitação:", ["Troca Direta (Com colega definido)", "Balcão (Procuro voluntário)"])
                    data_meu_servico = st.date_input("Data do MEU serviço atual que quero passar:")
                with c2:
                    if "Direta" in tipo_troca:
                        substituto = st.selectbox("Quem vai tirar o serviço no meu lugar?", [n for n in nomes_mils if n != nome_usuario_atual])
                        data_devolucao = st.date_input("Data que vou tirar o serviço para ele (Devolução):")
                    else:
                        substituto = "PENDENTE (Balcão)"
                        data_devolucao = None
                
                motivo = st.text_input("Motivo / Justificativa:")
                
                if st.form_submit_button("📤 Enviar Solicitação para P1", type="primary"):
                    nova_troca = {
                        "id_troca": len(st.session_state["mural_trocas"]) + 1,
                        "solicitante": nome_usuario_atual,
                        "tipo": "Direta" if "Direta" in tipo_troca else "Balcão",
                        "data_servico": data_meu_servico.strftime("%d/%m/%Y"),
                        "substituto": substituto,
                        "data_devolucao": data_devolucao.strftime("%d/%m/%Y") if data_devolucao else "-",
                        "motivo": motivo,
                        "status": "Aguardando P1",
                        "data_pedido": datetime.datetime.now().strftime("%d/%m %H:%M")
                    }
                    st.session_state["mural_trocas"].append(nova_troca)
                    st.success("Solicitação enviada com sucesso!")
                    st.rerun()

        # VISÃO GERAL (BALCÃO DE VOLUNTÁRIOS)
        st.markdown("#### 🤝 Balcão de Voluntários (Trocas Abertas)")
        trocas_abertas = [t for t in st.session_state["mural_trocas"] if t["tipo"] == "Balcão" and t["status"] == "Aguardando P1"]
        if trocas_abertas:
            for t in trocas_abertas:
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{t['solicitante']}** precisa de alguém para o dia **{t['data_servico']}**.")
                        st.caption(f"Motivo: {t['motivo']}")
                    with col2:
                        if not eh_admin and t['solicitante'] != nome_usuario_atual:
                            if st.button("🙋‍♂️ Eu assumo!", key=f"btn_assumir_{t['id_troca']}"):
                                t["tipo"] = "Direta"
                                t["substituto"] = nome_usuario_atual
                                st.success("Você se voluntariou! Agora aguarda aprovação da P1.")
                                st.rerun()
        else:
            st.info("Nenhuma troca aberta no balcão no momento.")

        # VISÃO DA ADMINISTRAÇÃO (APROVAR/NEGAR)
        st.divider()
        st.markdown("#### 📋 Acompanhamento e Auditoria")
        if st.session_state["mural_trocas"]:
            df_trocas = pd.DataFrame(st.session_state["mural_trocas"])
            
            if eh_admin:
                st.caption("Você é o administrador. Marque a caixa para Aprovar ou Negar as solicitações.")
                df_trocas["Aprovar"] = False
                df_trocas["Negar"] = False
                
                df_edit = st.data_editor(
                    df_trocas,
                    column_config={
                        "id_troca": None,
                        "status": st.column_config.TextColumn("Status Atual", disabled=True),
                    },
                    hide_index=True, use_container_width=True
                )
                
                houve_att = False
                for i, row in df_edit.iterrows():
                    troca_real = st.session_state["mural_trocas"][i]
                    if row.get("Aprovar") and troca_real["status"] == "Aguardando P1":
                        troca_real["status"] = "✅ APROVADO"
                        houve_att = True
                    elif row.get("Negar") and troca_real["status"] == "Aguardando P1":
                        troca_real["status"] = "❌ NEGADO"
                        houve_att = True
                        
                if houve_att:
                    st.rerun()
            else:
                # Soldado só vê as próprias solicitações ou as concluídas dele
                df_filtro = df_trocas[(df_trocas["solicitante"] == nome_usuario_atual) | (df_trocas["substituto"] == nome_usuario_atual)]
                st.dataframe(df_filtro.drop(columns=["id_troca"]), hide_index=True, use_container_width=True)
        else:
            st.caption("Nenhum registro de troca de serviço.")

    # ==========================================
    # ABA 2: CORREIO E AVISOS (COM CIENTE)
    # ==========================================
    with aba2:
        st.markdown("### 📢 Comunicados Oficiais e Caixa de Mensagens")
        
        # ADMIN: CRIAR NOVA MENSAGEM
        if eh_admin:
            with st.expander("✍️ Escrever Novo Comunicado", expanded=False):
                with st.form("form_mensagem"):
                    titulo_msg = st.text_input("Título / Assunto:")
                    corpo_msg = st.text_area("Conteúdo da Mensagem:")
                    
                    destinatarios = st.multiselect("Destinatários:", ["TODOS O EFETIVO"] + nomes_mils)
                    
                    if st.form_submit_button("🚀 Enviar Mensagem", type="primary"):
                        if "TODOS O EFETIVO" in destinatarios:
                            lista_dest = nomes_mils
                        else:
                            lista_dest = destinatarios
                            
                        nova_msg = {
                            "id_msg": len(st.session_state["mural_mensagens"]) + 1,
                            "data_envio": datetime.datetime.now().strftime("%d/%m %H:%M"),
                            "titulo": titulo_msg,
                            "conteudo": corpo_msg,
                            "destinatarios": lista_dest,
                            "lido_por": {} # Dicionário {Nome: "Data/Hora que leu"}
                        }
                        st.session_state["mural_mensagens"].append(nova_msg)
                        st.success("Mensagem enviada!")
                        st.rerun()

            # ADMIN: PAINEL DE AUDITORIA DE LEITURA
            st.markdown("#### 👁️ Auditoria de Leitura (Controle da P1)")
            if not st.session_state["mural_mensagens"]:
                st.info("Nenhuma mensagem enviada.")
            else:
                for msg in reversed(st.session_state["mural_mensagens"]):
                    with st.container(border=True):
                        st.markdown(f"**{msg['titulo']}** (Enviado em {msg['data_envio']})")
                        lidos_qtd = len(msg['lido_por'])
                        dest_qtd = len(msg['destinatarios'])
                        st.progress(lidos_qtd / dest_qtd if dest_qtd > 0 else 0)
                        st.caption(f"Lido por {lidos_qtd} de {dest_qtd} destinatários.")
                        
                        with st.expander("Ver detalhes de quem leu/não leu"):
                            lidos_nomes = list(msg['lido_por'].keys())
                            faltam_nomes = [n for n in msg['destinatarios'] if n not in lidos_nomes]
                            
                            c_leu, c_nleu = st.columns(2)
                            with c_leu:
                                st.markdown("✅ **Cientes:**")
                                for n, data_l in msg['lido_por'].items():
                                    st.markdown(f"- {n} *(em {data_l})*")
                            with c_nleu:
                                st.markdown("❌ **Pendentes:**")
                                for n in faltam_nomes:
                                    st.markdown(f"- {n}")

        # USUÁRIO / SOLDADO: CAIXA DE ENTRADA E BOTÃO DE "CIENTE"
        else:
            minhas_mensagens = [m for m in st.session_state["mural_mensagens"] if nome_usuario_atual in m["destinatarios"]]
            
            if not minhas_mensagens:
                st.info("Sua caixa de entrada está vazia. Nenhum recado no momento. ☕")
            else:
                st.markdown(f"**Caixa de Entrada de:** `{nome_usuario_atual}`")
                
                # Exibe de trás pra frente (mais novas primeiro)
                for msg in reversed(minhas_mensagens):
                    ja_leu = nome_usuario_atual in msg["lido_por"]
                    cor_borda = "#059669" if ja_leu else "#dc2626"
                    icone = "✅" if ja_leu else "🚨"
                    
                    with st.container(border=True):
                        st.markdown(f"### {icone} {msg['titulo']}")
                        st.caption(f"Enviado pela ADMINISTRAÇÃO em {msg['data_envio']}")
                        st.markdown(f">{msg['conteudo']}")
                        
                        if not ja_leu:
                            if st.button("👁️ Marcar como 'Li e Estou Ciente'", key=f"ciente_{msg['id_msg']}", type="primary"):
                                msg["lido_por"][nome_usuario_atual] = datetime.datetime.now().strftime("%d/%m %H:%M")
                                st.rerun()
                        else:
                            st.success(f"Você tomou ciência deste aviso em: {msg['lido_por'][nome_usuario_atual]}")