import streamlit as st
import pandas as pd
import datetime
from core.database import carregar_militares_supabase, supabase

def buscar_mensagens_p1_supabase():
    """Busca todas as solicitações e mensagens enviadas pela Tropa para a P1 no Supabase."""
    if not supabase:
        return []
    
    tabelas_para_testar = ["mensagens_p1", "mensagens", "requerimentos_p1"]
    
    for nome_tabela in tabelas_para_testar:
        try:
            res = supabase.table(nome_tabela).select("*").execute()
            if res and res.data and len(res.data) > 0:
                dados = res.data
                dados.sort(
                    key=lambda x: str(x.get("criado_em") or x.get("created_at") or x.get("data_hora") or x.get("id") or ""), 
                    reverse=True
                )
                return dados
        except Exception:
            continue
            
    try:
        res = supabase.table("mensagens_p1").select("*").execute()
        return res.data or []
    except Exception:
        return []

def buscar_mapa_usuarios_supabase():
    """Busca todos os usuários ativos no banco para mapear remetente_id -> Cargo + Nome de Guerra."""
    if not supabase:
        return {}, []
    try:
        res = supabase.table("usuarios").select("usuario_login, usuario, cargo_funcao, nome_guerra").execute()
        mapa = {}
        lista_completa = []
        if res.data:
            for u in res.data:
                key_login = str(u.get("usuario_login") or u.get("usuario") or "").strip().upper()
                cargo = u.get("cargo_funcao") or ""
                nome_guerra = u.get("nome_guerra") or ""
                nome_completo = f"{cargo} {nome_guerra}".strip()
                if key_login and nome_completo:
                    mapa[key_login] = nome_completo
                    lista_completa.append({"login": key_login, "label": f"{nome_completo} ({key_login})"})
        return mapa, lista_completa
    except Exception:
        return {}, []

def atualizar_despacho_mensagem_p1(msg_id, novo_status, despacho_texto=""):
    """Atualiza o status e o texto de despacho de um requerimento no Supabase."""
    if not supabase or not msg_id:
        return False
    try:
        supabase.table("mensagens_p1").update({
            "status": novo_status,
            "despacho": despacho_texto
        }).eq("id", msg_id).execute()
        return True
    except Exception:
        return False

def atualizar_remetente_mensagem_p1(msg_id, novo_remetente_id):
    """Atualiza o militar solicitante do requerimento no Supabase."""
    if not supabase or not msg_id or not novo_remetente_id:
        return False
    try:
        supabase.table("mensagens_p1").update({
            "remetente_id": novo_remetente_id,
            "num_policia": novo_remetente_id
        }).eq("id", msg_id).execute()
        return True
    except Exception:
        return False

def excluir_mensagem_p1_supabase(msg_id):
    """Exclui permanentemente um requerimento da caixa de entrada no Supabase."""
    if not supabase or not msg_id:
        return False
    try:
        supabase.table("mensagens_p1").delete().eq("id", msg_id).execute()
        return True
    except Exception:
        return False

def renderizar_mural():
    st.markdown("""<style>div[data-testid="stContainer"] div[data-testid="stColumn"] button {height: auto !important; min-height: 40px !important;}</style>""", unsafe_allow_html=True)
    
    st.title("🗣️ Portal do Efetivo e Mural de Avisos")
    st.caption("Solicitação de trocas de serviço, balcão de voluntários, caixa de entrada da P1 e comunicados oficiais.")
    st.divider()

    usr_logado = st.session_state.get("usuario_dados", {})
    cargo_str = str(usr_logado.get("cargo_funcao", "")).upper()
    nivel_str = str(usr_logado.get("nivel_acesso", usr_logado.get("perfil", ""))).upper()
    
    LISTA_ADMIN = ["PROGRAMADOR", "DESENVOLVEDOR", "TESTADOR", "ADMIN", "COMANDANTE_CIA", "P1", "SARGENTEANTE"]
    eh_admin = any(p in cargo_str or p in nivel_str for p in LISTA_ADMIN)
    
    mils_todos = st.session_state.get("lista_militares", [])
    if not mils_todos and supabase:
        mils_todos = carregar_militares_supabase()
        if mils_todos:
            st.session_state["lista_militares"] = mils_todos

    if mils_todos:
        nomes_mils = [f"{m.get('posto_grad', m.get('graduacao', ''))} {m.get('nome_guerra', m.get('nome', ''))}".strip() for m in mils_todos if m.get('nome_guerra') or m.get('nome')]
    else:
        nomes_mils = ["SGT Exemplo", "CB Silva", "SD Oliveira"]

    nome_guerra_usr = usr_logado.get("nome_guerra", "Militar")
    posto_usr = usr_logado.get("cargo_funcao", usr_logado.get("posto_grad", "Policial"))
    nome_usuario_atual = f"{posto_usr} {nome_guerra_usr}".strip()

    if "mural_trocas" not in st.session_state:
        st.session_state["mural_trocas"] = []
    if "mural_mensagens" not in st.session_state:
        st.session_state["mural_mensagens"] = []

    aba1, aba2, aba3 = st.tabs([
        "🔄 Trocas de Serviço & Permutas", 
        "📩 Requerimentos P1 (Caixa de Entrada)",
        "📢 Correio e Comunicados"
    ])

    # ==========================================
    # ABA 1: TROCAS DE SERVIÇO
    # ==========================================
    with aba1:
        st.markdown("### Gestão de Trocas e Permutas")
        
        with st.expander("📝 Criar Nova Solicitação de Permuta / Troca de Serviço", expanded=True):
            with st.form("form_nova_troca"):
                st.markdown(f"**Solicitante:** `{nome_usuario_atual}`")
                c1, c2 = st.columns(2)
                with c1:
                    tipo_troca = st.radio("Tipo de Solicitação:", ["Troca Direta (Com colega definido)", "Balcão (Procuro voluntário)"])
                    data_meu_servico = st.date_input("Data do MEU serviço atual que quero passar:")
                with c2:
                    if "Direta" in tipo_troca:
                        opcoes_substitutos = [n for n in nomes_mils if n != nome_usuario_atual]
                        substituto = st.selectbox("Quem vai tirar o serviço no meu lugar?", opcoes_substitutos if opcoes_substitutos else nomes_mils)
                        data_devolucao = st.date_input("Data que vou tirar o serviço para ele (Devolução):")
                    else:
                        substituto = "PENDENTE (Balcão)"
                        data_devolucao = None
                
                motivo = st.text_input("Motivo / Justificativa da Permuta:")
                
                if st.form_submit_button("📤 Enviar Solicitação de Troca à P1", type="primary", use_container_width=True):
                    if not motivo:
                        st.error("⚠️ Informe a justificativa da troca.")
                    else:
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
                        st.success("🎉 Solicitação de permuta registrada com sucesso! Encaminhada para análise da P1.")
                        st.rerun()

        st.markdown("#### 🤝 Balcão de Voluntários (Trocas Abertas)")
        trocas_abertas = [t for t in st.session_state["mural_trocas"] if t["tipo"] == "Balcão" and t["status"] == "Aguardando P1"]
        if trocas_abertas:
            for t in trocas_abertas:
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{t['solicitante']}** precisa de voluntário para o dia **{t['data_servico']}**.")
                        st.caption(f"Motivo: {t['motivo']}")
                    with col2:
                        if t['solicitante'] != nome_usuario_atual:
                            if st.button("🙋‍♂️ Eu assumo!", key=f"btn_assumir_{t['id_troca']}"):
                                t["tipo"] = "Direta"
                                t["substituto"] = nome_usuario_atual
                                st.success("Você se voluntariou! Aguardando homologação da P1.")
                                st.rerun()
        else:
            st.info("ℹ️ Nenhuma permuta aberta no balcão de voluntários no momento.")

        st.divider()
        st.markdown("#### 📋 Acompanhamento e Auditoria de Permutas")
        if st.session_state["mural_trocas"]:
            df_trocas = pd.DataFrame(st.session_state["mural_trocas"])
            
            if eh_admin:
                st.caption("💡 **Painel do Gestor/P1:** Marque a opção para Aprovar ou Negar as solicitações pendentes.")
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
                    if i < len(st.session_state["mural_trocas"]):
                        troca_real = st.session_state["mural_trocas"][i]
                        if row.get("Aprovar") and troca_real["status"] == "Aguardando P1":
                            troca_real["status"] = "✅ APROVADO P1"
                            houve_att = True
                        elif row.get("Negar") and troca_real["status"] == "Aguardando P1":
                            troca_real["status"] = "❌ INDEFERIDO P1"
                            houve_att = True
                        
                if houve_att:
                    st.rerun()
            else:
                df_filtro = df_trocas[(df_trocas["solicitante"] == nome_usuario_atual) | (df_trocas["substituto"] == nome_usuario_atual)]
                st.dataframe(df_filtro.drop(columns=["id_troca"], errors="ignore"), hide_index=True, use_container_width=True)
        else:
            st.caption("Nenhum registro de troca de serviço cadastrado nesta sessão.")

    # ==========================================
    # ABA 2: REQUERIMENTOS P1 (SUPABASE BANCO DE DADOS)
    # ==========================================
    with aba2:
        st.markdown("### 📩 Caixa de Entrada da P1 — Solicitações da Tropa")
        st.caption("Mensagens, requerimentos e comunicados encaminhados pelo efetivo via banco de dados do Supabase.")
        
        msgs_p1_banco = buscar_mensagens_p1_supabase()
        mapa_usuarios, lista_usuarios_mils = buscar_mapa_usuarios_supabase()

        if not msgs_p1_banco:
            st.info("ℹ️ Nenhum requerimento localizado no banco de dados até o momento.")
        else:
            if eh_admin:
                # 🔍 FILTROS DE BUSCA (DATA, MILITAR SOLICITANTE E STATUS)
                with st.expander("🔍 **Filtros de Busca e Consulta da P1**", expanded=True):
                    col_f1, col_f2, col_f3 = st.columns([1, 1.2, 1])
                    with col_f1:
                        filtro_data_p1 = st.date_input("Filtrar por Data de Envio:", value=None, key="filtro_dt_p1")
                    with col_f2:
                        opcoes_filtro_militar = ["TODOS OS MILITARES"] + sorted(list(set(mapa_usuarios.values())))
                        filtro_militar_p1 = st.selectbox("Filtrar por Militar Solicitante:", opcoes_filtro_militar, key="filtro_mil_p1")
                    with col_f3:
                        filtro_status_p1 = st.selectbox("Filtrar por Status:", ["TODOS OS STATUS", "Pendente / RECEBIDA", "DEFERIDO / APROVADO", "INDEFERIDO", "EM ANÁLISE"], key="filtro_st_p1")

                # APLICAÇÃO DOS FILTROS
                msgs_exibição = []
                for msg in msgs_p1_banco:
                    num_pol = str(
                        msg.get("remetente_id") or 
                        msg.get("num_policia") or 
                        msg.get("usuario_login") or 
                        msg.get("usuario") or 
                        ""
                    ).strip().upper()

                    nome_m = mapa_usuarios.get(num_pol) or msg.get("nome_militar") or msg.get("militar_nome") or "Policial Militar"
                    status_atual = msg.get("status") or "Pendente"
                    
                    data_bruta = msg.get("criado_em") or msg.get("created_at") or msg.get("data_hora") or ""
                    dt_obj = None
                    if data_bruta:
                        try:
                            dt_obj = pd.to_datetime(data_bruta).date()
                        except Exception:
                            dt_obj = None

                    # Valida filtro por data
                    if filtro_data_p1 and dt_obj and dt_obj != filtro_data_p1:
                        continue
                    
                    # Valida filtro por militar
                    if filtro_militar_p1 != "TODOS OS MILITARES" and filtro_militar_p1.upper() not in nome_m.upper():
                        continue

                    # Valida filtro por status
                    if filtro_status_p1 != "TODOS OS STATUS":
                        termo_st = "PENDENTE" if "PENDENTE" in filtro_status_p1.upper() or "RECEBIDA" in filtro_status_p1.upper() else filtro_status_p1.upper()
                        if termo_st not in status_atual.upper() and status_atual.upper() not in termo_st:
                            if not ("RECEBIDA" in status_atual.upper() and "PENDENTE" in filtro_status_p1.upper()):
                                continue

                    msgs_exibição.append((msg, num_pol, nome_m, data_bruta))

                st.success(f"📊 Exibindo **{len(msgs_exibição)}** de **{len(msgs_p1_banco)}** requerimentos localizados.")
                
                for msg, num_pol, nome_m, data_bruta in msgs_exibição:
                    msg_id = msg.get("id")
                    assunto = msg.get("assunto") or "Solicitação P1"
                    texto = msg.get("mensagem") or msg.get("texto") or msg.get("conteudo") or ""
                    status_atual = msg.get("status") or "Pendente"
                    despacho_existente = msg.get("despacho") or ""
                    
                    if data_bruta:
                        try:
                            data_fmt = pd.to_datetime(data_bruta).strftime("%d/%m/%Y às %H:%M")
                        except Exception:
                            data_fmt = str(data_bruta)[:16]
                    else:
                        data_fmt = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M")

                    cor_status = "🟡" if "PENDENTE" in status_atual.upper() or "RECEBIDA" in status_atual.upper() else ("🟢" if "DEFERIDO" in status_atual.upper() or "APROVADO" in status_atual.upper() else "🔴")

                    with st.container(border=True):
                        st.markdown(f"#### {cor_status} {assunto}")
                        st.caption(f"👤 **Militar Solicitante:** {nome_m} (`Nº {num_pol if num_pol else 'N/I'}`) | ⏱️ **Enviado em:** {data_fmt} | **Status:** `{status_atual}`")
                        st.markdown(f"> {texto}")

                        if despacho_existente:
                            st.info(f"💬 **Despacho Registrado:** {despacho_existente}")

                        # AÇÕES DO GESTOR DA P1
                        col_act1, col_act2, col_act3 = st.columns([1.5, 1.5, 1])

                        # 1. FORMULÁRIO DE DESPACHO
                        with col_act1:
                            with st.expander(f"✏️ Despachar #{msg_id}"):
                                with st.form(f"form_despacho_{msg_id}"):
                                    novo_st = st.selectbox(
                                        "Decisão da P1 / Comando:",
                                        ["Pendente", "DEFERIDO / APROVADO", "INDEFERIDO", "EM ANÁLISE"],
                                        index=0 if "PENDENTE" in status_atual.upper() or "RECEBIDA" in status_atual.upper() else 1
                                    )
                                    txt_despacho = st.text_area("Texto do Despacho:", value=despacho_existente)
                                    
                                    if st.form_submit_button("💾 Salvar Despacho", type="primary", use_container_width=True):
                                        if atualizar_despacho_mensagem_p1(msg_id, novo_st, txt_despacho):
                                            st.toast("✅ Despacho salvo com sucesso!", icon="🟢")
                                            st.rerun()
                                        else:
                                            st.error("Erro ao atualizar mensagem.")

                        # 2. ALTERAR MILITAR SOLICITANTE
                        with col_act2:
                            with st.expander(f"👤 Reatribuir Solicitante"):
                                if lista_usuarios_mils:
                                    with st.form(f"form_reatribuir_{msg_id}"):
                                        labels_opt = [item["label"] for item in lista_usuarios_mils]
                                        novo_mil_sel = st.selectbox("Selecione o Novo Militar Solicitante:", labels_opt)
                                        
                                        if st.form_submit_button("🔄 Salvar Novo Solicitante", use_container_width=True):
                                            novo_login = next((item["login"] for item in lista_usuarios_mils if item["label"] == novo_mil_sel), None)
                                            if novo_login and atualizar_remetente_mensagem_p1(msg_id, novo_login):
                                                st.toast("✅ Solicitante atualizado!", icon="🟢")
                                                st.rerun()
                                            else:
                                                st.error("Erro ao alterar militar.")
                                else:
                                    st.caption("Nenhum usuário cadastrado para reatribuição.")

                        # 3. EXCLUIR MENSAGEM
                        with col_act3:
                            with st.expander(f"🗑️ Excluir"):
                                with st.form(f"form_excluir_{msg_id}"):
                                    st.warning("Tem certeza?")
                                    confirma_exc = st.checkbox("Confirmar exclusão", key=f"chk_exc_{msg_id}")
                                    if st.form_submit_button("🔥 Excluir", type="primary", use_container_width=True):
                                        if not confirma_exc:
                                            st.error("Marque o checkbox.")
                                        else:
                                            if excluir_mensagem_p1_supabase(msg_id):
                                                st.toast("🗑️ Mensagem excluída!", icon="🟢")
                                                st.rerun()
                                            else:
                                                st.error("Erro ao excluir mensagem.")
            else:
                num_pol_usr = str(usr_logado.get("usuario_login") or usr_logado.get("usuario") or "").strip().upper()
                minhas_msgs = [m for m in msgs_p1_banco if str(m.get("remetente_id") or m.get("num_policia") or m.get("usuario_login")).strip().upper() == num_pol_usr]

                if not minhas_msgs:
                    st.info("Você ainda não possui requerimentos gravados no banco de dados.")
                else:
                    for msg in minhas_msgs:
                        st.markdown(f"**Assunto:** {msg.get('assunto') or 'Solicitação'}")
                        st.caption(f"Status: `{msg.get('status', 'Pendente')}`")
                        st.markdown(f">{msg.get('mensagem') or msg.get('texto')}")
                        if msg.get("despacho"):
                            st.success(f"**Despacho da P1:** {msg.get('despacho')}")
                        st.divider()

    # ==========================================
    # ABA 3: CORREIO E AVISOS (COM CIENTE)
    # ==========================================
    with aba3:
        st.markdown("### 📢 Comunicados Oficiais e Caixa de Mensagens")
        
        if eh_admin:
            with st.expander("✍️ Escrever Novo Comunicado Oficial", expanded=False):
                with st.form("form_mensagem"):
                    titulo_msg = st.text_input("Título / Assunto:")
                    corpo_msg = st.text_area("Conteúdo da Mensagem:")
                    
                    destinatarios = st.multiselect("Destinatários:", ["TODOS O EFETIVO"] + nomes_mils)
                    
                    if st.form_submit_button("🚀 Publicar Comunicado", type="primary", use_container_width=True):
                        if not titulo_msg or not corpo_msg:
                            st.error("⚠️ Preencha o título e o conteúdo do comunicado.")
                        else:
                            if "TODOS O EFETIVO" in destinatarios or not destinatarios:
                                lista_dest = nomes_mils
                            else:
                                lista_dest = destinatarios
                                
                            nova_msg = {
                                "id_msg": len(st.session_state["mural_mensagens"]) + 1,
                                "data_envio": datetime.datetime.now().strftime("%d/%m %H:%M"),
                                "titulo": titulo_msg,
                                "conteudo": corpo_msg,
                                "destinatarios": lista_dest,
                                "lido_por": {}
                            }
                            st.session_state["mural_mensagens"].append(nova_msg)
                            st.success("Comunicado oficial publicado com sucesso!")
                            st.rerun()

            st.markdown("#### 👁️ Auditoria de Leitura (Controle da P1)")
            if not st.session_state["mural_mensagens"]:
                st.info("Nenhum comunicado publicado até o momento.")
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

        minhas_mensagens = [m for m in st.session_state["mural_mensagens"] if nome_usuario_atual in m["destinatarios"] or "TODOS O EFETIVO" in m["destinatarios"]]
        
        if not minhas_mensagens and not eh_admin:
            st.info("Sua caixa de entrada está vazia. Nenhum aviso pendente de leitura. ☕")
        elif minhas_mensagens and not eh_admin:
            st.markdown(f"**Caixa de Entrada de:** `{nome_usuario_atual}`")
            
            for msg in reversed(minhas_mensagens):
                ja_leu = nome_usuario_atual in msg["lido_por"]
                icone = "✅" if ja_leu else "🚨"
                
                with st.container(border=True):
                    st.markdown(f"### {icone} {msg['titulo']}")
                    st.caption(f"Enviado pela P1/Comando em {msg['data_envio']}")
                    st.markdown(f">{msg['conteudo']}")
                    
                    if not ja_leu:
                        if st.button("👁️ Marcar como 'Li e Estou Ciente'", key=f"ciente_{msg['id_msg']}", type="primary"):
                            msg["lido_por"][nome_usuario_atual] = datetime.datetime.now().strftime("%d/%m %H:%M")
                            st.rerun()
                    else:
                        st.success(f"Você tomou ciência deste aviso em: {msg['lido_por'][nome_usuario_atual]}")