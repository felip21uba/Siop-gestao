import streamlit as st
import pandas as pd
import datetime
from core.database import supabase, carregar_militares_supabase
from core.permissions import usuario_eh_gestor_creds, usuario_eh_admin_ou_programador
from modules.tco.database import registrar_log_supabase, atualizar_material_supabase
from modules.tco.storage import upload_midia_supabase
from modules.tco.modais import abrir_modal_edicao_material
from modules.tco.estilo_tco import modal_cadeia_custodia_timeline, modal_guia_termo_oficial
from utils.file_validator import sanitizar_nome_arquivo


def extrair_unidades_creds_banco(unidade_militar_atual=""):
    orgaos_externos = [
        "DELEGACIA DE POLÍCIA CIVIL (PCMG)",
        "PODER JUDICIÁRIO / TRIBUNAL DE JUSTIÇA (JECRIM)",
        "PERÍCIA TÉCNICA / PERÍCIA OFICIAL",
        "MINISTÉRIO PÚBLICO (MPMG)",
        "OUTRO ÓRGÃO EXTERNO (ESPECIFICAR NAS OBSERVAÇÕES)"
    ]

    unidades_set = set()

    def normalizar_para_nivel_pelotao(texto_unid):
        u_str = str(texto_unid).strip().upper()
        if not u_str or u_str in ["NONE", "NAN", "N/I", ""]:
            return ""
            
        if "GP/" in u_str:
            partes = u_str.split("GP/")
            if len(partes) > 1:
                sub_partes = partes[1].split("/", 1)
                u_str = sub_partes[1].strip() if len(sub_partes) > 1 else partes[1].strip()
        
        if not u_str.startswith("CREDS"):
            return f"CREDS {u_str}"
        return u_str

    if supabase:
        try:
            res = supabase.table("usuarios").select("unidade, creds_acesso").execute()
            if res and res.data:
                for row in res.data:
                    unid_raw = str(row.get("creds_acesso") or row.get("unidade") or "").strip().upper()
                    unid_fmt = normalizar_para_nivel_pelotao(unid_raw)
                    if unid_fmt:
                        unidades_set.add(unid_fmt)
        except Exception as e:
            print(f"Aviso ao consultar unidades para o CREDS no Supabase: {e}")

    if unidade_militar_atual:
        unid_op_fmt = normalizar_para_nivel_pelotao(unidade_militar_atual)
        if unid_op_fmt:
            unidades_set.add(unid_op_fmt)

    if not unidades_set:
        unidades_set.add("CREDS 35ª CIA PM / 21º BPM")
        unidades_set.add("CREDS 1º PEL / 35ª CIA PM / 21º BPM")
        unidades_set.add("CREDS 2º PEL / 35ª CIA PM / 21º BPM")
        unidades_set.add("CREDS 3º PEL / 35ª CIA PM / 21º BPM")
        unidades_set.add("CREDS 4º PEL / 35ª CIA PM / 21º BPM")
        unidades_set.add("CREDS 111ª CIA PM / 21º BPM")
        unidades_set.add("CREDS 285ª CIA TM / 21º BPM")
        unidades_set.add("CREDS 21º BPM")

    return sorted(list(unidades_set)) + orgaos_externos


def renderizar_aba_custodia_tramitacao_unificada(all_bens, nome_militar_atual, unidade_militar_atual):
    usr_logado = st.session_state.get("usuario_dados", {})
    num_pm_logado = str(usr_logado.get("usuario_login") or usr_logado.get("usuario") or "").strip().upper()
    creds_atribuido_usr = str(usr_logado.get("creds_acesso") or usr_logado.get("unidade") or unidade_militar_atual).strip().upper()

    eh_gestor_creds = usuario_eh_gestor_creds(usr_logado) or usuario_eh_admin_ou_programador(usr_logado)

    if "subaba_tramitacao_ativa" not in st.session_state:
        st.session_state["subaba_tramitacao_ativa"] = "TRAMITAR"

    aba_atual = st.session_state["subaba_tramitacao_ativa"]

    # Estilos táticos incluindo a correção da badge de alerta de prazo
    st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"]:has(> div > .painel-tramitacao-cabecalho) {
        background: linear-gradient(135deg, #7d6539 0%, #63502c 100%) !important;
        border: 2px solid #c5a059 !important;
        border-radius: 12px !important;
        padding: 18px 20px 20px 20px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.45) !important;
        margin-bottom: 22px !important;
    }
    .painel-tramitacao-cabecalho {
        margin-bottom: 14px;
    }
    .painel-tramitacao-titulo {
        font-size: 1.25rem !important;
        font-weight: 800 !important;
        color: #ffffff !important;
        margin: 0 0 4px 0 !important;
        display: flex;
        align-items: center;
        gap: 8px;
        text-shadow: 0 1px 2px rgba(0,0,0,0.4);
    }
    .painel-tramitacao-subtitulo {
        font-size: 0.84rem;
        color: #f5ebe0;
        margin: 0;
    }
    .badge-creds-origem {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border: 1px solid #38bdf8 !important;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.78rem;
        font-weight: 800;
        text-transform: uppercase;
        display: inline-block;
    }
    .badge-fase-status {
        background-color: #8c7343 !important;
        color: #ffffff !important;
        border: 1px solid #c5a059 !important;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.76rem;
        font-weight: 800;
        text-transform: uppercase;
        display: inline-block;
    }
    .badge-prazo-alerta {
        background-color: #7f1d1d !important;
        color: #fecaca !important;
        border: 1px solid #ef4444 !important;
        border-radius: 6px;
        padding: 3px 8px;
        font-size: 0.74rem;
        font-weight: 800;
        display: inline-block;
        white-space: nowrap;
    }
    .badge-midia-anexa {
        background-color: #1e3a8a !important;
        color: #93c5fd !important;
        border: 1px solid #3b82f6 !important;
        border-radius: 6px;
        padding: 3px 8px;
        font-size: 0.74rem;
        font-weight: 800;
        display: inline-block;
    }
    .tag-info-retangulo {
        background-color: #2b2118;
        border: 1px solid #7d6339;
        border-radius: 6px;
        padding: 3px 8px;
        color: #ffe8cd;
        font-family: monospace;
        font-size: 0.82rem;
        font-weight: 700;
        display: inline-block;
        margin-right: 4px;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown(f"""
        <div class="painel-tramitacao-cabecalho">
            <div class="painel-tramitacao-titulo">
                🎒 Custódia Física &amp; Tramitação Unificada
            </div>
            <div class="painel-tramitacao-subtitulo">
                Gerencie os bens sob sua posse, realize remessas para policiais/órgãos e consulte o histórico imutável das movimentações.
                <br/><b>📍 Seu Escopo de Atuação Ativo:</b> <span class="badge-creds-origem">🏢 CREDS {creds_atribuido_usr}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_btn1, col_btn2, col_btn3 = st.columns(3)

        with col_btn1:
            btn_tipo1 = "primary" if aba_atual == "TRAMITAR" else "secondary"
            if st.button("📤 Tramitar Materiais / REDS", key="nav_btn_tramitar_v9", type=btn_tipo1, use_container_width=True):
                st.session_state["subaba_tramitacao_ativa"] = "TRAMITAR"
                st.rerun()

        with col_btn2:
            btn_tipo2 = "primary" if aba_atual == "EXTERNO" else "secondary"
            if st.button("🏛️ Receber / Confirmar Retorno de Órgão Externo", key="nav_btn_externo_v9", type=btn_tipo2, use_container_width=True):
                st.session_state["subaba_tramitacao_ativa"] = "EXTERNO"
                st.rerun()

        with col_btn3:
            btn_tipo3 = "primary" if aba_atual == "HISTORICO" else "secondary"
            if st.button("📜 Histórico Permanente de Envios & Ocorrência", key="nav_btn_hist_v9", type=btn_tipo3, use_container_width=True):
                st.session_state["subaba_tramitacao_ativa"] = "HISTORICO"
                st.rerun()

    if "fila_tramitacao_mapeada" not in st.session_state:
        st.session_state["fila_tramitacao_mapeada"] = []

    if "itens_selecionados_tramite" not in st.session_state:
        st.session_state["itens_selecionados_tramite"] = {}

    # =========================================================================
    # ABA 1: TRAMITAR MATERIAIS
    # =========================================================================
    if aba_atual == "TRAMITAR":
        bens_posse = []
        reds_sem_materiais = set()

        for b in all_bens or []:
            posse_atual = str(b.get("fiel_depositario_atual") or b.get("unidade_posse_atual") or "").upper()
            status_tr = str(b.get("status_tramite") or "").strip()
            num_r = str(b.get("num_reds", "")).strip()

            if not b.get("destinatario_pendente") and status_tr not in ["Arquivado/Destinado", "Transferido Definitivo", "Destruído / Encerrado"]:
                if num_pm_logado in posse_atual or nome_militar_atual.upper() in posse_atual or unidade_militar_atual in posse_atual or creds_atribuido_usr in posse_atual or "CUSTÓDIA" in posse_atual:
                    bens_posse.append(b)

            if b.get("descricao") == "SEM MATERIAL APREENDIDO" or str(b.get("quantidade")) == "0":
                reds_sem_materiais.add(num_r)

        if not bens_posse and not reds_sem_materiais and not st.session_state["fila_tramitacao_mapeada"]:
            st.info(f"ℹ️ Nenhum material ativo pendente de nova tramitação no escopo do **CREDS {creds_atribuido_usr}** no momento.")
        else:
            if bens_posse:
                st.markdown(f"##### 🎒 Seus Bens em Custódia Física / Cia ({len(bens_posse)} item/ns)")

                df_bens = pd.DataFrame(bens_posse)
                grupos_reds = df_bens.groupby("num_reds")

                lista_militares = carregar_militares_supabase() or []
                opcoes_militares = []
                
                for m in lista_militares:
                    posto = str(m.get('posto_grad') or m.get('cargo_funcao') or 'PM').strip().upper()
                    nome_comp = str(m.get('nome_completo') or m.get('nome_guerra') or 'MILITAR').strip().upper()
                    nome_guerra = str(m.get('nome_guerra') or '').strip().upper()
                    num_pol = str(m.get('num_policia') or m.get('usuario_login') or '').strip().upper()
                    
                    if nome_guerra and nome_guerra not in nome_comp:
                        label_mil = f"{posto} {nome_comp} ({nome_guerra} - {num_pol})"
                    else:
                        label_mil = f"{posto} {nome_comp} ({num_pol})"
                        
                    opcoes_militares.append(label_mil)

                if not opcoes_militares:
                    opcoes_militares = [f"{nome_militar_atual} ({num_pm_logado})"]

                lista_unidades_creds = extrair_unidades_creds_banco(unidade_militar_atual)

                idx_card_global = 0
                for num_reds, df_grupo in grupos_reds:
                    qtd_itens_reds = len(df_grupo)
                    
                    with st.expander(f"📄 **REDS: {num_reds}** ({qtd_itens_reds} item/ns apreendido/s)", expanded=True):
                        for idx, row in df_grupo.iterrows():
                            idx_card_global += 1
                            id_bem = str(row.get("id_bem") or row.get("id"))
                            desc = str(row.get("descricao", "SEM DESCRIÇÃO")).strip()
                            qtd = row.get("quantidade", 1)
                            unid = str(row.get("unidade_medida", "UN")).strip()
                            lacre = str(row.get("involucro_lacre", "SEM LACRE")).strip()
                            autor = str(row.get("autores", "N/I")).strip()
                            custod = str(row.get("fiel_depositario_atual") or row.get("unidade_posse_atual") or nome_militar_atual).strip()
                            unid_posse_exata = str(row.get("unidade_posse_atual") or creds_atribuido_usr).strip().upper()
                            dest_raw = row.get("destinatario_pendente") or row.get("fase_destinacao") or "Com Fiel Depositário / Policial"
                            dest_str = str(dest_raw).strip()
                            status_b = str(row.get("status_tramite", "Em Custódia")).strip()
                            dt_raw = row.get("data_envio_tramite") or row.get("data_posse_atual") or row.get("data_ingestao")
                            
                            midias_list = row.get("midias_anexas") or []
                            qtd_midias = len(midias_list) if isinstance(midias_list, list) else 0

                            dt_fmt = "N/I"
                            dias_parado = 0
                            if dt_raw:
                                try:
                                    dt_obj = pd.to_datetime(dt_raw)
                                    dt_fmt = dt_obj.strftime("%d/%m/%Y às %H:%M")
                                    dias_parado = (datetime.datetime.now() - dt_obj.to_pydatetime().replace(tzinfo=None)).days
                                except Exception:
                                    dt_fmt = str(dt_raw)[:16]

                            fase_u = str(dest_str).upper()
                            if "PERÍCIA" in fase_u:
                                tag_local_fase = "🔬 PERÍCIA"
                            elif "JECRIM" in fase_u or "JUDICIÁRIO" in fase_u:
                                tag_local_fase = "⚖️ JECRIM"
                            elif "PCMG" in fase_u or "DELEGACIA" in fase_u:
                                tag_local_fase = "🏛️ POLÍCIA CIVIL"
                            else:
                                tag_local_fase = f"📦 {custod[:22]}"

                            bg_card = "linear-gradient(135deg, #574431 0%, #423324 100%)" if (idx_card_global % 2 == 0) else "linear-gradient(135deg, #3b2e23 0%, #291f17 100%)"

                            c_chk, c_card_info, c_card_btn = st.columns([0.5, 6.8, 2.7])
                            
                            with c_chk:
                                is_selected = st.checkbox(
                                    "Selecionar", 
                                    value=(id_bem in st.session_state["itens_selecionados_tramite"]),
                                    key=f"chk_tramite_{id_bem}_{idx_card_global}",
                                    label_visibility="collapsed"
                                )

                            with c_card_info:
                                html_midia_txt = f" | 🖼️ <b>{qtd_midias} foto(s) anexa(s)</b>" if qtd_midias > 0 else ""
                                html_card_mat = f"""
                                <div style="background: {bg_card}; border: 1.5px solid #a3824b; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; color: #ffffff;">
                                    📄 REDS: <strong style="color: #ffffff;">{num_reds}</strong> | Material: <strong style="color: #ffe0b2;">{desc}</strong> (Qtd: {qtd} {unid}){html_midia_txt}<br/>
                                    🏷️ Lacre: <strong style="color: #ffffff;">{lacre}</strong> | Autor: <strong style="color: #ffe0b2;">{autor}</strong><br/>
                                    🏢 <b>CREDS / Unidade de Posse:</b> <span class="badge-creds-origem">{unid_posse_exata}</span> | 👤 <b>Fiel Depositário:</b> <strong style="color: #ffd180;">{custod}</strong><br/>
                                    <div style="margin-top: 8px;">
                                        🎯 <b>Destino:</b> <span class="tag-info-retangulo">{dest_str}</span>
                                        📊 <b>Status:</b> <span class="tag-info-retangulo">{status_b}</span>
                                        ⏱️ <b>Data/Hora:</b> <span class="tag-info-retangulo">{dt_fmt}</span>
                                    </div>
                                </div>
                                """
                                st.markdown(html_card_mat, unsafe_allow_html=True)

                            with c_card_btn:
                                # Ajuste do badge de prazo com icone correto de relogio
                                badge_dias_html = f'<span class="badge-prazo-alerta">⏱️ {dias_parado} dia(s) parado</span>' if dias_parado >= 1 else ''
                                badge_foto_html = f'<span class="badge-midia-anexa">📷 {qtd_midias} FOTO(S)</span>' if qtd_midias > 0 else ''
                                st.markdown(f"""
                                <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px; margin-bottom: 6px;">
                                    <span class="badge-fase-status">{tag_local_fase}</span>
                                    {badge_foto_html}
                                    {badge_dias_html}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                c_b1, c_b2, c_b3 = st.columns(3)
                                with c_b1:
                                    if st.button("🔗 Cadeia", key=f"btn_cad_tr_{id_bem}_{idx_card_global}", use_container_width=True):
                                        modal_cadeia_custodia_timeline(row.to_dict())
                                with c_b2:
                                    if st.button("🖨️ Guia", key=f"btn_guia_tr_{id_bem}_{idx_card_global}", use_container_width=True):
                                        modal_guia_termo_oficial(row.to_dict(), nome_militar_atual, num_pm_logado, unidade_militar_atual)
                                with c_b3:
                                    lbl_midia = f"📷 Mídias ({qtd_midias})" if qtd_midias > 0 else "📷 Mídias"
                                    if st.button(lbl_midia, key=f"btn_midia_tr_{id_bem}_{idx_card_global}", use_container_width=True):
                                        abrir_modal_edicao_material(row.to_dict(), nome_militar_atual, unidade_militar_atual)

                            if is_selected:
                                st.session_state["itens_selecionados_tramite"][id_bem] = row.to_dict()
                            else:
                                st.session_state["itens_selecionados_tramite"].pop(id_bem, None)

                st.markdown("---")

                selecionados_map = st.session_state["itens_selecionados_tramite"]
                qtd_sel = len(selecionados_map)

                if qtd_sel > 0:
                    st.markdown(f"### 🎯 Definir Destino para {qtd_sel} item(ns) Selecionado(s)")
                    
                    tipo_destinatario = st.radio(
                        "Tipo de Destinatário:",
                        ["Policial Militar / Fiel Depositário", "Seção de Custódia (CREDS-TC / Órgão)"],
                        horizontal=True,
                        key="radio_tipo_destinatario_unificado_v8"
                    )

                    eh_opcao_creds = (tipo_destinatario == "Seção de Custódia (CREDS-TC / Órgão)")

                    col_dest, col_fase = st.columns([1.2, 1])

                    with col_dest:
                        if eh_opcao_creds:
                            destinatario_final = st.selectbox(
                                "Selecione a Unidade / CREDS Destinatário:",
                                options=lista_unidades_creds,
                                index=None,
                                placeholder="Escolha o CREDS da Cia, Batalhão ou Órgão...",
                                key="sb_destinatario_creds_unificado_v8"
                            )
                            unidade_dest_final = destinatario_final or "CREDS / ÓRGÃO EXTERNO"
                        else:
                            destinatario_final = st.selectbox(
                                "Selecione o Policial Destinatário:",
                                options=opcoes_militares,
                                index=None,
                                placeholder="Digite qualquer parte do nome do militar...",
                                key="sb_destinatario_policial_unificado_v8"
                            )
                            unidade_dest_final = unidade_militar_atual

                    with col_fase:
                        if not eh_opcao_creds:
                            fase_destinacao_sel = st.selectbox(
                                "Atualizar Fase de Destinação (Automático):",
                                options=["Com Fiel Depositário / Policial"],
                                index=0,
                                disabled=True,
                                key="sb_fase_policial_locked_v8"
                            )
                        else:
                            if eh_gestor_creds:
                                fase_destinacao_sel = st.selectbox(
                                    "Atualizar Fase de Destinação (Acesso Gestor CREDS):",
                                    [
                                        "Aguardando no CREDS-TC / Custódia",
                                        "Encaminhado à Polícia Civil (PCMG)",
                                        "Entregue ao Poder Judiciário / Fórum",
                                        "Encaminhado para Perícia Técnica",
                                        "Encaminhado para Destruição / Descarte Físico",
                                        "Devolvido ao Proprietário"
                                    ],
                                    key="sb_fase_creds_unificado_enabled_v8"
                                )
                            else:
                                fase_destinacao_sel = "Aguardando no CREDS-TC / Custódia"
                                st.selectbox(
                                    "Fase de Destinação:",
                                    options=["Aguardando no CREDS-TC / Custódia"],
                                    index=0,
                                    disabled=True,
                                    key="sb_fase_creds_unificado_readonly_v8"
                                )

                    eh_orgao_ext_unid = eh_opcao_creds and any(term in str(destinatario_final) for term in ["JUDICIÁRIO", "PERÍCIA", "POLÍCIA CIVIL", "OUTRO"])

                    if eh_orgao_ext_unid:
                        st.warning("🏛️ **Entrega em Órgão Externo:** Defina a modalidade de envio e registre a documentação.")
                        col_ext1, col_ext2 = st.columns(2)
                        with col_ext1:
                            nat_envio_unid = st.radio(
                                "Natureza da Transferência para Órgão Externo:",
                                ["🔄 Com Retorno (Aguardando Devolução / Em Tramitação)", "🔒 Definitiva (Procedimento Encerrado / Sem Retorno)"],
                                key="radio_nat_unificado_v8"
                            )
                            eh_definitivo_val = ("Definitiva" in nat_envio_unid)
                        with col_ext2:
                            num_oficio_unid = st.text_input("Nº do Ofício / Protocolo de Entrega (OBRIGATÓRIO):", placeholder="Ex: Ofício 123/2026", key="txt_ofic_unificado_v8").strip()
                        
                        recibo_unid_file = st.file_uploader("Foto ou PDF do Recibo Assinado / Termo de Aceite (OPCIONAL):", type=["jpg", "jpeg", "png", "pdf"], key="upl_rec_unificado_v8")
                        
                        recebedor_info = st.text_input(
                            "Informe Nome Completo e Matrícula de quem recebeu no Órgão Externo (OBRIGATÓRIO):", 
                            placeholder="Ex: INVESTIGADOR SILVA - MAT 12345", 
                            key="txt_recebedor_info_v11"
                        ).strip()
                    else:
                        eh_definitivo_val = False
                        num_oficio_unid = ""
                        recibo_unid_file = None
                        recebedor_info = str(destinatario_final or nome_militar_atual)

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("➕ Adicionar à Fila de Tramitação", type="secondary", width="stretch"):
                        if not destinatario_final:
                            st.error("⚠️ Selecione o destinatário antes de adicionar à fila.")
                        elif eh_orgao_ext_unid and not recebedor_info:
                            st.error("⚠️ O preenchimento do Nome Completo e Matrícula de quem recebeu no órgão externo é OBRIGATÓRIO.")
                        elif eh_orgao_ext_unid and not num_oficio_unid:
                            st.error("⚠️ O preenchimento do Nº do Ofício / Protocolo é OBRIGATÓRIO para órgãos externos.")
                        else:
                            for id_bem, dados_item in selecionados_map.items():
                                item_fila = {
                                    "id_bem": id_bem,
                                    "num_reds": dados_item.get("num_reds", "N/I"),
                                    "descricao": dados_item.get("descricao", "N/I"),
                                    "involucro_lacre": dados_item.get("involucro_lacre", "SEM LACRE"),
                                    "quantidade": dados_item.get("quantidade", 1),
                                    "unidade_medida": dados_item.get("unidade_medida", "UN"),
                                    "destinatario": destinatario_final,
                                    "unidade_destinatario": unidade_dest_final,
                                    "fase_destinacao": fase_destinacao_sel,
                                    "observacao": recebedor_info,
                                    "eh_creds": eh_opcao_creds,
                                    "eh_orgao_ext": eh_orgao_ext_unid,
                                    "eh_definitivo": eh_definitivo_val,
                                    "num_oficio": num_oficio_unid,
                                    "recibo_file": recibo_unid_file
                                }
                                st.session_state["fila_tramitacao_mapeada"] = [
                                    f for f in st.session_state["fila_tramitacao_mapeada"] if f["id_bem"] != id_bem
                                ]
                                st.session_state["fila_tramitacao_mapeada"].append(item_fila)

                            st.session_state["itens_selecionados_tramite"] = {}
                            st.toast("✅ Itens adicionados à fila de confirmação!", icon="📋")
                            st.rerun()

            fila_atual = st.session_state["fila_tramitacao_mapeada"]
            if fila_atual:
                st.markdown("---")
                st.markdown(f"#### 📋 Retângulo de Confirmação: Fila de Envio ({len(fila_atual)} item/ns)")
                st.caption("Confira os materiais selecionados e seus respetivos destinos antes de efetivar a transferência.")

                with st.container(border=True):
                    for idx_f, item_f in enumerate(fila_atual):
                        col_f_desc, col_f_dest, col_f_del = st.columns([5, 4, 1])
                        
                        with col_f_desc:
                            st.markdown(
                                f"📦 **Material:** {item_f['descricao']} (Qtd: {item_f['quantidade']} {item_f['unidade_medida']})  \n"
                                f"📄 **REDS:** `{item_f['num_reds']}`"
                            )

                        with col_f_dest:
                            st.markdown(
                                f"🎯 **Destino:** `{item_f['destinatario']}`  \n"
                                f"🏷️ **Fase:** `{item_f['fase_destinacao']}`  \n"
                                f"👤 **Recebedor:** `{item_f['observacao']}`"
                            )

                        with col_f_del:
                            if st.button("🗑️", key=f"btn_del_fila_{item_f['id_bem']}_{idx_f}", help="Remover da fila"):
                                st.session_state["fila_tramitacao_mapeada"].pop(idx_f)
                                st.rerun()

                    st.markdown("<br>", unsafe_allow_html=True)
                    col_cf1, col_cf2 = st.columns(2)
                    
                    with col_cf1:
                        btn_finalizar_tudo = st.button("🚀 Confirmar Envio / Tramitação da Fila", type="primary", width="stretch")
                    with col_cf2:
                        btn_limpar_fila = st.button("❌ Cancelar / Limpar Fila", width="stretch")

                    if btn_limpar_fila:
                        st.session_state["fila_tramitacao_mapeada"] = []
                        st.rerun()

                    if btn_finalizar_tudo:
                        agora_iso = datetime.datetime.now().isoformat()
                        sucessos = 0

                        for f_item in fila_atual:
                            rec_f = f_item.get("recibo_file")
                            if rec_f:
                                upload_midia_supabase(
                                    file_bytes=rec_f.getvalue(),
                                    file_name=sanitizar_nome_arquivo(rec_f.name),
                                    file_type=rec_f.type,
                                    num_reds=f_item["num_reds"],
                                    id_bem=f_item["id_bem"]
                                )

                            if f_item.get("eh_orgao_ext"):
                                status_tr_f = "Transferido Definitivo" if f_item.get("eh_definitivo") else "Em Tramitação"
                                dest_limpo = str(f_item["destinatario"]).replace("Entregue ao ", "").replace("Entregue ao", "").strip()
                                fiel_f = dest_limpo
                                
                                if f_item.get("num_oficio"):
                                    fase_f = f"Entregue ao {dest_limpo} (Ofício: {f_item.get('num_oficio')})"
                                else:
                                    fase_f = f"Entregue ao {dest_limpo}"
                            else:
                                status_tr_f = "Pendente de Aceite"
                                dest_p_f = f_item["destinatario"]
                                fiel_f = nome_militar_atual
                                fase_f = f_item["fase_destinacao"]

                            payload_update = {
                                "destinatario_pendente": dest_p_f if not f_item.get("eh_orgao_ext") else None,
                                "unidade_destinatario_pendente": f_item["unidade_destinatario"] if not f_item.get("eh_orgao_ext") else None,
                                "fiel_depositario_atual": fiel_f,
                                "unidade_posse_atual": f_item["unidade_destinatario"],
                                "data_envio_tramite": agora_iso,
                                "fase_destinacao": fase_f,
                                "status_tramite": status_tr_f,
                                "ultimo_gestor_movimentou": nome_militar_atual
                            }

                            if atualizar_material_supabase(f_item["id_bem"], payload_update):
                                sucessos += 1
                                desc_item_log = f"{f_item['descricao']} (Lacre: {f_item.get('involucro_lacre', 'N/I')})"
                                detalhe_txt = f"Material: {f_item['descricao']} | Fase: {fase_f} | Recebido por: {f_item['observacao']}"
                                
                                if f_item.get("num_oficio"):
                                    detalhe_txt += f" | Ofício/Protocolo: {f_item['num_oficio']}"

                                registrar_log_supabase({
                                    "data_hora": agora_iso,
                                    "num_reds": f_item["num_reds"],
                                    "bem_id": desc_item_log,
                                    "web_origem": "SIOP_TCO",
                                    "acao": "TRAMITACAO_ENVIADA",
                                    "origem": nome_militar_atual,
                                    "unidade_origem": unidade_militar_atual,
                                    "destino": f_item["destinatario"],
                                    "unidade_destino": f_item["unidade_destinatario"],
                                    "detalhe": detalhe_txt
                                })

                        if sucessos > 0:
                            st.success(f"🎉 {sucessos} material(is) tramitado(s) com sucesso!")
                            st.session_state["fila_tramitacao_mapeada"] = []
                            st.session_state["itens_selecionados_tramite"] = {}
                            st.cache_data.clear()
                            st.rerun()

    # =========================================================================
    # ABA 2: CONFIRMAR RETORNO DE ÓRGÃO EXTERNO
    # =========================================================================
    elif aba_atual == "EXTERNO":
        st.markdown("##### 🏛️ Materiais em Tramitação Externa (PCMG, JECRIM, Perícia, MP)")
        st.caption("Como usuários de órgãos externos não possuem acesso ao SIOP, o Operador/Militar do TCO dá o aceite de retorno quando o material for devolvido à unidade.")

        TERMOS_EXTERNOS = [
            "DELEGACIA", "POLÍCIA CIVIL", "PCMG", "JECRIM", "JUDICIÁRIO", 
            "PERÍCIA", "MINISTÉRIO PÚBLICO", "MPMG", "ÓRGÃO EXTERNO", "FÓRUM", "TRIBUNAL"
        ]

        bens_em_orgao_externo = []
        for b in all_bens or []:
            dest_p = str(b.get("destinatario_pendente") or "").upper()
            fase_d = str(b.get("fase_destinacao") or "").upper()
            status_t = str(b.get("status_tramite") or "").strip()
            
            if status_t != "Transferido Definitivo" and any(term in dest_p or term in fase_d for term in TERMOS_EXTERNOS):
                bens_em_orgao_externo.append(b)

        if not bens_em_orgao_externo:
            st.info("ℹ️ Nenhum material atualmente localizado em trâmite temporário de órgãos externos.")
        else:
            df_ext = pd.DataFrame(bens_em_orgao_externo)
            for num_reds_e, df_grupo_e in df_ext.groupby("num_reds", sort=False):
                with st.expander(f"🏛️ **REDS: {num_reds_e}** ({len(df_grupo_e)} item/ns em órgão externo)", expanded=True):
                    for idx_e, item_e in df_grupo_e.iterrows():
                        id_bem_e = str(item_e.get("id_bem") or item_e.get("id"))
                        desc_e = item_e.get("descricao", "N/I")
                        qtd_e_val = item_e.get("quantidade", 1)
                        dest_e = item_e.get("destinatario_pendente") or item_e.get("fase_destinacao") or "Órgão Externo"

                        col_e1, col_e2 = st.columns([7, 3])
                        with col_e1:
                            st.markdown(
                                f"• **Material:** {desc_e} (Qtd: {qtd_e_val})  \n"
                                f"• **Órgão/Destino Atual:** <code class='st-emotion-cache-znj1k1'>{dest_e}</code>",
                                unsafe_allow_html=True
                            )

                        with col_e2:
                            if st.button("📥 Aceitar Retorno / Devolução", key=f"btn_aceite_ext_{id_bem_e}_{idx_e}", type="primary", width="stretch"):
                                agora_iso_ext = datetime.datetime.now().isoformat()
                                payload_retorno = {
                                    "destinatario_pendente": None,
                                    "unidade_destinatario_pendente": None,
                                    "status_tramite": "Em Custódia",
                                    "fiel_depositario_atual": nome_militar_atual,
                                    "unidade_posse_atual": creds_atribuido_usr,
                                    "fase_destinacao": "Com Fiel Depositário / Policial"
                                }
                                if atualizar_material_supabase(id_bem_e, payload_retorno):
                                    registrar_log_supabase({
                                        "data_hora": agora_iso_ext,
                                        "num_reds": num_reds_e,
                                        "bem_id": f"{desc_e} (ID: {id_bem_e})",
                                        "web_origem": "SIOP_TCO",
                                        "acao": "ACEITE_DEVOLUCAO_ORGAO_EXTERNO",
                                        "origem": dest_e,
                                        "unidade_origem": "Órgão Externo",
                                        "destino": nome_militar_atual,
                                        "unidade_destino": creds_atribuido_usr,
                                        "detalhe": f"Aceite de retorno do material {desc_e} confirmado na guarda de {nome_militar_atual} ({creds_atribuido_usr})."
                                    })
                                    st.success("✅ Retorno confirmado! O material foi reincorporado à sua custódia individual.")
                                    st.cache_data.clear()
                                    st.rerun()

    # =========================================================================
    # ABA 3: HISTÓRICO PERMANENTE DE ENVIOS & OCORRÊNCIAS
    # =========================================================================
    elif aba_atual == "HISTORICO":
        st.markdown("<h5 style='color: #ffe0b2;'>📜 Histórico Permanente de Envios & Ocorrências</h5>", unsafe_allow_html=True)
        st.caption("Consulte todas as tramitações, visualize a cadeia de custódia imutável ou emita a guia oficial de depósito.")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            busca_reds_hist = st.text_input("🔍 Pesquisar por Nº do REDS (Busca Geral):", placeholder="Ex: 2026-000484967", key="txt_busca_reds_hist_v8").strip()
        with col_f2:
            dt_hoje = datetime.date.today()
            dt_30d = dt_hoje - datetime.timedelta(days=90)
            intervalo_datas = st.date_input("🗓️ Filtrar por Período:", value=(dt_30d, dt_hoje), format="DD/MM/YYYY", key="date_hist_envios_v8")

        envios_militar = []
        for b in all_bens or []:
            remetente = str(b.get("fiel_depositario_atual") or b.get("unidade_posse_atual") or b.get("ultimo_gestor_movimentou") or "").upper()
            dest_pendente = b.get("destinatario_pendente")
            status_t = str(b.get("status_tramite", ""))

            if (num_pm_logado in remetente or nome_militar_atual.upper() in remetente or unidade_militar_atual in remetente or creds_atribuido_usr in remetente) or dest_pendente or status_t == "Transferido Definitivo":
                envios_militar.append(b)

        if busca_reds_hist:
            envios_militar = [b for b in envios_militar if busca_reds_hist.lower() in str(b.get("num_reds", "")).lower()]

        if isinstance(intervalo_datas, tuple) and len(intervalo_datas) == 2:
            d_ini, d_fim = intervalo_datas
            filtrados_data = []
            for b in envios_militar:
                dt_env = b.get("data_envio_tramite") or b.get("data_posse_atual") or b.get("data_ingestao")
                if dt_env:
                    try:
                        dt_obj = pd.to_datetime(dt_env).date()
                        if d_ini <= dt_obj <= d_fim:
                            filtrados_data.append(b)
                    except Exception:
                        filtrados_data.append(b)
                else:
                    filtrados_data.append(b)
            envios_militar = filtrados_data

        if not envios_militar:
            st.info("ℹ️ Nenhum registro de histórico localizado com os parâmetros de pesquisa selecionados.")
        else:
            df_hist = pd.DataFrame(envios_militar)
            if "data_envio_tramite" in df_hist.columns:
                df_hist.sort_values(by="data_envio_tramite", ascending=False, inplace=True)
            
            reds_unicos = list(df_hist["num_reds"].unique())

            idx_card_hist = 0
            for num_reds_h in reds_unicos:
                df_grupo_h = df_hist[df_hist["num_reds"] == num_reds_h]
                qtd_h = len(df_grupo_h)
                
                with st.expander(f"📄 **REDS: {num_reds_h}** ({qtd_h} item/ns no histórico do procedimento)", expanded=False):
                    for idx_h, item_h in df_grupo_h.iterrows():
                        idx_card_hist += 1
                        id_bem_h = str(item_h.get("id_bem") or item_h.get("id"))
                        desc_h = item_h.get("descricao", "N/I")
                        qtd_h_val = item_h.get("quantidade", 1)
                        unid_med = item_h.get("unidade_medida", "UN")
                        lacre_h = item_h.get("involucro_lacre", "SEM LACRE")
                        autor_h = item_h.get("autores", "N/I")
                        custod_h = str(item_h.get("fiel_depositario_atual") or item_h.get("unidade_posse_atual") or "N/I").strip()
                        unid_posse_hist = str(item_h.get("unidade_posse_atual") or "N/I").strip().upper()
                        dest_h_raw = item_h.get("destinatario_pendente") or item_h.get("fase_destinacao") or "N/I"
                        dest_h = str(dest_h_raw).strip()
                        status_h = item_h.get("status_tramite", "Em Custódia")
                        dt_env_str = item_h.get("data_envio_tramite") or item_h.get("data_posse_atual") or item_h.get("data_ingestao")

                        midias_list_h = item_h.get("midias_anexas") or []
                        qtd_midias_h = len(midias_list_h) if isinstance(midias_list_h, list) else 0

                        dt_fmt_exata = "Data N/I"
                        dias_parado_h = 0
                        if dt_env_str:
                            try:
                                dt_obj_item = pd.to_datetime(dt_env_str)
                                dt_fmt_exata = dt_obj_item.strftime("%d/%m/%Y às %H:%M")
                                dias_parado_h = (datetime.datetime.now() - dt_obj_item.to_pydatetime().replace(tzinfo=None)).days
                            except Exception:
                                dt_fmt_exata = str(dt_env_str)[:16]

                        fase_u = str(dest_h).upper()
                        if "PERÍCIA" in fase_u:
                            tag_local_hist = "🔬 PERÍCIA"
                        elif "JECRIM" in fase_u or "JUDICIÁRIO" in fase_u:
                            tag_local_hist = "⚖️ JECRIM"
                        elif "PCMG" in fase_u or "DELEGACIA" in fase_u:
                            tag_local_hist = "🏛️ POLÍCIA CIVIL"
                        else:
                            tag_local_hist = f"📦 {custod_h[:22]}"

                        bg_card_h = "linear-gradient(135deg, #574431 0%, #423324 100%)" if (idx_card_hist % 2 == 0) else "linear-gradient(135deg, #3b2e23 0%, #291f17 100%)"

                        col_card_info, col_card_lateral = st.columns([7.3, 2.7])
                        
                        with col_card_info:
                            html_midia_txt_h = f" | 🖼️ <b>{qtd_midias_h} foto(s) anexa(s)</b>" if qtd_midias_h > 0 else ""
                            html_card_mat = f"""
                            <div style="background: {bg_card_h}; border: 1.5px solid #a3824b; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; color: #ffffff;">
                                📄 REDS: <strong style="color: #ffffff;">{num_reds_h}</strong> | Material: <strong style="color: #ffe0b2;">{desc_h}</strong> (Qtd: {qtd_h_val} {unid_med}){html_midia_txt_h}<br/>
                                🏷️ Lacre: <strong style="color: #ffffff;">{lacre_h}</strong> | Autor: <strong style="color: #ffe0b2;">{autor_h}</strong><br/>
                                🏢 <b>CREDS / Unidade da Posse:</b> <span class="badge-creds-origem">{unid_posse_hist}</span> | 👤 <b>Fiel Depositário:</b> <strong style="color: #ffd180;">{custod_h}</strong><br/>
                                <div style="margin-top: 8px;">
                                    🎯 <b>Destino:</b> <span class="tag-info-retangulo">{dest_h}</span>
                                    📊 <b>Status:</b> <span class="tag-info-retangulo">{status_h}</span>
                                    ⏱️ <b>Data/Hora:</b> <span class="tag-info-retangulo">{dt_fmt_exata}</span>
                                </div>
                            </div>
                            """
                            st.markdown(html_card_mat, unsafe_allow_html=True)

                        with col_card_lateral:
                            badge_dias_hist_html = f'<span class="badge-prazo-alerta">⏱️ {dias_parado_h} dia(s) parado</span>' if dias_parado_h >= 1 else ''
                            badge_foto_hist_html = f'<span class="badge-midia-anexa">📷 {qtd_midias_h} FOTO(S)</span>' if qtd_midias_h > 0 else ''
                            st.markdown(f"""
                            <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px; margin-bottom: 6px;">
                                <span class="badge-fase-status">{tag_local_hist}</span>
                                {badge_foto_hist_html}
                                {badge_dias_hist_html}
                            </div>
                            """, unsafe_allow_html=True)

                            col_b1, col_b2, col_b3 = st.columns(3)
                            with col_b1:
                                if st.button("🔗 Cadeia", key=f"btn_cad_{id_bem_h}_{idx_h}", help="Ver histórico imutável (Art. 158-B CPP)", use_container_width=True):
                                    modal_cadeia_custodia_timeline(item_h.to_dict())
                            with col_b2:
                                if st.button("🖨️ Guia", key=f"btn_guia_{id_bem_h}_{idx_h}", help="Gerar Termo de Depósito e Apreensão", use_container_width=True):
                                    modal_guia_termo_oficial(item_h.to_dict(), nome_militar_atual, num_pm_logado, unidade_militar_atual)
                            with col_b3:
                                lbl_midia_h = f"📷 Mídias ({qtd_midias_h})" if qtd_midias_h > 0 else "📷 Mídias"
                                if st.button(lbl_midia_h, key=f"btn_midia_hist_{id_bem_h}_{idx_h}", help="Anexar ou visualizar fotos/documentos do bem", use_container_width=True):
                                    abrir_modal_edicao_material(item_h.to_dict(), nome_militar_atual, unidade_militar_atual)