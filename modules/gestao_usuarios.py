"""
==============================================================================
Módulo de Gestão de Usuários e Permissões SIOP
Gerencia acessos por perfil (CREDS e Escala), unidades e limpeza seletiva.
Mapeamento de colunas fiel ao esquema SQL public.usuarios.
==============================================================================
"""

import streamlit as st
import pandas as pd
import re
from core.database import supabase, registrar_audit_log, carregar_militares_supabase, extrair_bpm_mae
from core.auth import gerar_hash_senha

PERFIS_NIVEL_GERAL = [
    "PROGRAMADOR", 
    "ADMIN", 
    "GESTOR", 
    "P1", 
    "P3", 
    "COMANDANTE_CIA", 
    "CMT_PELOTAO", 
    "SARGENTEANTE", 
    "TROPA"
]

PERFIS_CREDS = ["GESTOR_UNIDADE", "GESTOR_CIA", "OPERADOR", "TROPA"]
PERFIS_ESCALA = ["CMT_CIA", "SARGENTIACAO", "AUXILIAR_CIA", "TROPA"]

def extrair_digitos_matricula(val):
    """Extrai apenas os números da matrícula para busca uniforme no Supabase."""
    if not val:
        return ""
    return re.sub(r'\D', '', str(val))

def formatar_matricula_pm_padrao(val):
    """Formata a matrícula limpa no padrão PMMG (123.456-7)."""
    dig = extrair_digitos_matricula(val)
    if len(dig) == 7:
        return f"{dig[:3]}.{dig[3:6]}-{dig[6]}"
    return str(val)

def cadastrar_novo_operador_supabase(num_policia, nome_guerra, nome_completo, posto_grad, unidade, perfil_creds, perfil_escala, nivel_acesso, senha_inicial="Pmmg@190"):
    """Cadastra um novo operador/militar diretamente na tabela 'usuarios' do Supabase usando o schema oficial."""
    if not supabase or not num_policia or not nome_guerra:
        return False, "Dados insuficientes para cadastro."

    m_digitos = extrair_digitos_matricula(num_policia)
    if not m_digitos:
        return False, "Número de polícia/matrícula inválido."

    try:
        res_check = supabase.table("usuarios").select("usuario_login").or_(
            f"usuario_login.eq.{m_digitos},usuario.eq.{m_digitos}"
        ).execute()

        if res_check and res_check.data and len(res_check.data) > 0:
            return False, f"O militar com a matrícula {m_digitos} já está cadastrado no SIOP."

        hash_senha = gerar_hash_senha(senha_inicial)
        
        # Payload com o mapeamento estrito das colunas existentes na tabela 'usuarios'
        payload_novo = {
            "usuario_login": m_digitos,
            "usuario": m_digitos,
            "nome_guerra": str(nome_guerra).strip().upper(),
            "nome_completo": str(nome_completo or nome_guerra).strip().upper(),
            "cargo_funcao": str(posto_grad).strip().upper(),
            "unidade": str(unidade).strip().upper(),
            "perfil_creds": perfil_creds,
            "perfil_escala": perfil_escala,
            "nivel_acesso": nivel_acesso,
            "senha": senha_inicial,
            "senha_hash": hash_senha,
            "ativo": True,
            "primeiro_acesso": True,
            "tentativas_erradas": 0,
            "termo_compliance_aceito": False
        }

        supabase.table("usuarios").insert(payload_novo).execute()
        
        try:
            carregar_militares_supabase.clear()
        except Exception:
            pass
        st.cache_data.clear()

        return True, f"Militar/Operador {nome_guerra} ({m_digitos}) cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro ao salvar no banco de dados: {e}"

def salvar_permissao_militar(matricula, perfil_creds=None, perfil_escala=None, nivel_acesso=None, ativo=True, posto="SD", nome="MILITAR", nome_completo=None):
    """Atualiza as permissões flexibilizando a busca nas colunas usuario_login e usuario."""
    if supabase and matricula:
        try:
            m_raw = str(matricula).strip().upper()
            m_digitos = extrair_digitos_matricula(m_raw)
            m_fmt = formatar_matricula_pm_padrao(m_digitos)
            
            payload_update = {"ativo": ativo}
            if perfil_creds is not None:
                payload_update["perfil_creds"] = perfil_creds
            if perfil_escala is not None:
                payload_update["perfil_escala"] = perfil_escala
            if nivel_acesso is not None:
                payload_update["nivel_acesso"] = nivel_acesso
            if nome_completo:
                payload_update["nome_completo"] = nome_completo

            condicao_busca = f"usuario_login.eq.{m_raw},usuario_login.eq.{m_digitos},usuario_login.eq.{m_fmt},usuario.eq.{m_raw},usuario.eq.{m_digitos}"
            supabase.table("usuarios").update(payload_update).or_(condicao_busca).execute()
            
            try:
                carregar_militares_supabase.clear()
            except Exception:
                pass
            st.cache_data.clear()
            return True
        except Exception as e:
            print(f"Erro ao salvar permissão do militar {matricula}: {e}")
            return False
    return False

def exibir_painel_gestao_unidades():
    st.markdown("##### 📋 Unidades Cadastradas no SIOP")
    st.caption("Visualização e administração global das unidades no Supabase.")

    if not supabase:
        st.error("⚠️ Conexão com o Supabase indisponível.")
        return

    bpms_mapa = {}
    try:
        res = supabase.table("unidades_config").select("*").execute()
        if res and res.data:
            for uni in res.data:
                bat = str(uni.get("batalhao", "")).strip().upper()
                if bat and bat not in ["NONE", "N/I", ""]:
                    bpms_mapa[bat] = {
                        "id": uni.get("id"),
                        "companhia": uni.get("companhia", "GERAL"),
                        "municipio": uni.get("municipio", "N/I")
                    }
    except Exception:
        pass

    mils = carregar_militares_supabase() or []
    for m in mils:
        lot_m = str(m.get("lotacao") or m.get("unidade") or "").strip().upper()
        if lot_m and lot_m not in ["NONE", "N/I", "UNIDADE N/I", ""]:
            bat_m = extrair_bpm_mae(lot_m)
            if bat_m not in bpms_mapa:
                bpms_mapa[bat_m] = {
                    "id": f"synced_{hash(bat_m)}",
                    "companhia": lot_m,
                    "municipio": str(m.get("cidade", "UBÁ")).strip().upper()
                }

    if not bpms_mapa:
        st.info("ℹ️ Nenhuma unidade cadastrada no momento.")
        return

    for bat_nome, dados in sorted(bpms_mapa.items()):
        cia_txt = dados["companhia"]
        mun_txt = dados["municipio"]

        with st.container():
            col_info, col_acao = st.columns([4, 1])
            with col_info:
                st.markdown(f"**🏛️ Unidade / Batalhão:** {bat_nome}")
                st.caption(f"📍 **Frações/Lotação:** {cia_txt} | **Município Sede:** {mun_txt}")
            
            with col_acao:
                if st.button("🗑️ Excluir", key=f"btn_del_uni_{bat_nome}", type="secondary"):
                    st.session_state[f"confirm_del_{bat_nome}"] = True

            if st.session_state.get(f"confirm_del_{bat_nome}"):
                st.warning(f"⚠️ Confirmar exclusão da unidade **{bat_nome}**?")
                c_sim, c_nao = st.columns(2)
                
                with c_sim:
                    if st.button("✅ Confirmar Exclusão", key=f"btn_conf_yes_{bat_nome}", type="primary"):
                        try:
                            supabase.table("unidades_config").delete().eq("batalhao", bat_nome).execute()
                            st.success(f"Unidade '{bat_nome}' excluída!")
                            st.session_state[f"confirm_del_{bat_nome}"] = False
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Erro ao excluir unidade: {ex}")
                            
                with c_nao:
                    if st.button("❌ Cancelar", key=f"btn_conf_no_{bat_nome}"):
                        st.session_state[f"confirm_del_{bat_nome}"] = False
                        st.rerun()

        st.divider()

def exibir_tela_gestao_usuarios():
    st.title("⚙ Painel de Gestão de Níveis de Acesso e Permissões SIOP")
    st.caption("Atribua perfis independentes por módulo (CREDS e Escalas), cadastre novos operadores e administre as unidades do sistema.")
    st.divider()

    if "gestao_usr_version" not in st.session_state:
        st.session_state["gestao_usr_version"] = 0

    usr = st.session_state.get("usuario_dados") or {}
    usr_id_operador = str(usr.get("usuario_login") or usr.get("usuario") or "123456").strip()

    st.markdown("### ➕ Cadastrar / Ativar Novo Operador no SIOP")
    with st.container(border=True):
        st.caption("Cadastre diretamente um militar no banco de dados para conceder acesso imediato aos módulos.")
        
        with st.form("form_cadastrar_novo_operador_direto", clear_on_submit=True):
            c_cad1, c_cad2, c_cad3 = st.columns(3)
            with c_cad1:
                novo_num_pm = st.text_input("Número de Polícia / Matrícula (Login):", placeholder="Ex: 123456").strip()
                novo_nome_guerra = st.text_input("Nome de Guerra:", placeholder="Ex: PEREIRA").strip().upper()
            with c_cad2:
                novo_nome_completo = st.text_input("Nome Completo:", placeholder="Ex: CARLOS ALBERTO PEREIRA").strip().upper()
                novo_posto = st.selectbox("Posto / Graduação:", ["SD", "CB", "3º SGT", "2º SGT", "1º SGT", "SUB TEN", "2º TEN", "1º TEN", "CAP", "MAJ", "TEN CEL", "CEL"])
            with c_cad3:
                unidade_usr = str(usr.get("unidade") or "35 CIA PM/21 BPM/4 RPM").strip().upper()
                nova_unidade = st.text_input("Unidade / Lotação:", value=unidade_usr).strip().upper()
                nova_senha_init = st.text_input("Senha Inicial de Acesso:", value="Pmmg@190", type="password")

            st.markdown("---")
            st.markdown("##### 🔐 Atribuição Inicial de Perfis e Permissões")
            c_perf1, c_perf2, c_perf3 = st.columns(3)
            with c_perf1:
                p_creds_cad = st.selectbox("Função CREDS / TCO:", PERFIS_CREDS, index=2, key="cad_p_creds_d")
            with c_perf2:
                p_escala_cad = st.selectbox("Função Escalas:", PERFIS_ESCALA, index=3, key="cad_p_escala_d")
            with c_perf3:
                p_geral_cad = st.selectbox("Nível Geral (Menu):", PERFIS_NIVEL_GERAL, index=8, key="cad_p_geral_d")

            btn_salvar_novo_op = st.form_submit_button("💾 Cadastrar e Ativar Operador no SIOP", type="primary", use_container_width=True)

            if btn_salvar_novo_op:
                if not novo_num_pm or not novo_nome_guerra:
                    st.error("⚠️ O Número de Polícia e o Nome de Guerra são obrigatórios.")
                else:
                    sucesso_cad, msg_cad = cadastrar_novo_operador_supabase(
                        num_policia=novo_num_pm,
                        nome_guerra=novo_nome_guerra,
                        nome_completo=novo_nome_completo,
                        posto_grad=novo_posto,
                        unidade=nova_unidade,
                        perfil_creds=p_creds_cad,
                        perfil_escala=p_escala_cad,
                        nivel_acesso=p_geral_cad,
                        senha_inicial=nova_senha_init
                    )
                    if sucesso_cad:
                        registrar_audit_log(usr_id_operador, novo_num_pm, "CADASTRAR_OPERADOR_DIRETO", f"Operador {novo_nome_guerra} cadastrado. CREDS: {p_creds_cad} | ESCALA: {p_escala_cad} | GERAL: {p_geral_cad}")
                        st.session_state["gestao_usr_version"] += 1
                        st.success(f"✅ {msg_cad}")
                        st.rerun()
                    else:
                        st.error(f"⛔ {msg_cad}")

    st.divider()

    abas_titulos = [
        "👥 Permissões do Efetivo",
        "🏛 Cadastrar Nova Unidade / Batalhão",
        "📋 Lista de Unidades Cadastradas",
        "🚨 Limpeza Seletiva (Programador)"
    ]

    abas = st.tabs(abas_titulos)
    efetivo_banco = carregar_militares_supabase() or []

    # ABA 1: GERENCIAMENTO DE ACESSOS EM LOTE E TABELA
    with abas[0]:
        st.markdown("##### 🎯 Alteração de Perfis em Lote")
        dict_mils_options = {}
        for m in efetivo_banco:
            num_pm = str(m.get("num_policia", "")).strip().upper()
            if num_pm and num_pm != "N/I":
                nome_comp = m.get("nome_completo") or f"{m.get('posto_grad','')} {m.get('nome_guerra','')}"
                status_txt = f"CREDS: {m.get('perfil_creds', 'TROPA')} | ESCALA: {m.get('perfil_escala', 'TROPA')} | GERAL: {m.get('nivel_acesso', 'TROPA')}"
                rotulo = f"[{num_pm}] {m.get('posto_grad','')} {nome_comp} - ({status_txt})"
                dict_mils_options[rotulo] = m

        if dict_mils_options:
            c_bl1, c_bl2, c_bl3, c_bl4 = st.columns([2.2, 1.2, 1.2, 1.4])
            with c_bl1:
                selecionados = st.multiselect("Selecione os Militares:", list(dict_mils_options.keys()))
            with c_bl2:
                perfil_creds_lote = st.selectbox("Função CREDS:", PERFIS_CREDS)
            with c_bl3:
                perfil_escala_lote = st.selectbox("Função ESCALA:", PERFIS_ESCALA)
            with c_bl4:
                idx_tropa = PERFIS_NIVEL_GERAL.index("TROPA") if "TROPA" in PERFIS_NIVEL_GERAL else 0
                nivel_geral_lote = st.selectbox("Nível Geral (Menu):", PERFIS_NIVEL_GERAL, index=idx_tropa)

            if st.button("⚡ Aplicar Perfis aos Selecionados", type="primary", use_container_width=True):
                if not selecionados:
                    st.warning("Selecione ao menos um militar.")
                else:
                    sucesso_qtd = 0
                    for label in selecionados:
                        m_obj = dict_mils_options[label]
                        num_pm = str(m_obj.get("num_policia")).strip().upper()
                        nome_comp_m = m_obj.get("nome_completo") or f"{m_obj.get('posto_grad','')} {m_obj.get('nome_guerra','')}"
                        if salvar_permissao_militar(
                            matricula=num_pm, 
                            perfil_creds=perfil_creds_lote,
                            perfil_escala=perfil_escala_lote,
                            nivel_acesso=nivel_geral_lote,
                            ativo=True,
                            posto=m_obj.get("posto_grad", "SD"),
                            nome=m_obj.get("nome_guerra", "MILITAR"),
                            nome_completo=nome_comp_m
                        ):
                            sucesso_qtd += 1
                            registrar_audit_log(usr_id_operador, num_pm, "ALTERAR_PERMISSAO_LOTE", f"CREDS: [{perfil_creds_lote}] | ESCALA: [{perfil_escala_lote}] | GERAL: [{nivel_geral_lote}].")
                    
                    st.session_state["gestao_usr_version"] += 1
                    st.success(f"✅ {sucesso_qtd} militar(es) atualizado(s) com sucesso!")
                    st.rerun()

        st.divider()

        # TABELA EDITÁVEL DE PERMISSÕES COM BARRA DE BUSCA
        with st.expander("📜 Tabela Geral de Permissões", expanded=True):
            c_src1, c_src2, c_src3 = st.columns([3, 1.5, 1])
            with c_src1:
                termo_busca_militar = st.text_input(
                    "🔍 Pesquisar por Nome, Matrícula/PM, Lotação ou Posto:", 
                    placeholder="Digite o nome, PM (ex: 123456) ou Cia...",
                    key="txt_busca_tabela_militar"
                ).strip().lower()
            
            with c_src2:
                filtro_perfil_ativo = st.selectbox(
                    "Filtrar por Nível Geral:",
                    options=["TODOS OS NÍVEIS"] + PERFIS_NIVEL_GERAL,
                    key="sb_filtro_nivel_geral_tabela"
                )
                
            with c_src3:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("🔄 Recarregar", use_container_width=True):
                    st.session_state["gestao_usr_version"] += 1
                    st.rerun()

            st.caption("💡 Edite qualquer permissão na tabela e as alterações serão gravadas imediatamente na tabela `usuarios`.")

            if efetivo_banco:
                linhas_display = []
                for m in efetivo_banco:
                    num_pm = str(m.get("num_policia", "N/I")).strip().upper()
                    nome_comp = m.get("nome_completo") or m.get("nome_guerra", "MILITAR")
                    lotacao_str = str(m.get("lotacao", m.get("unidade", "21º BPM")))
                    posto_str = str(m.get("posto_grad", "SD"))
                    nivel_geral_str = str(m.get("nivel_acesso", "TROPA"))

                    if termo_busca_militar:
                        num_pm_limpo = extrair_digitos_matricula(num_pm)
                        termo_limpo = extrair_digitos_matricula(termo_busca_militar)
                        
                        match_texto = (
                            termo_busca_militar in nome_comp.lower() or
                            termo_busca_militar in num_pm.lower() or
                            termo_busca_militar in lotacao_str.lower() or
                            termo_busca_militar in posto_str.lower()
                        )
                        match_num = (termo_limpo and termo_limpo in num_pm_limpo) if termo_limpo else False

                        if not (match_texto or match_num):
                            continue

                    if filtro_perfil_ativo != "TODOS OS NÍVEIS" and nivel_geral_str != filtro_perfil_ativo:
                        continue

                    linhas_display.append({
                        "MATRÍCULA": num_pm,
                        "POSTO/GRAD": posto_str,
                        "MILITAR": nome_comp,
                        "LOTAÇÃO": lotacao_str,
                        "FUNÇÃO CREDS": m.get("perfil_creds", "TROPA"),
                        "FUNÇÃO ESCALA": m.get("perfil_escala", "TROPA"),
                        "NÍVEL GERAL": nivel_geral_str,
                        "CONTA ATIVA": bool(m.get("ativo", True))
                    })

                if not linhas_display:
                    st.warning("🔍 Nenhum militar localizado com os parâmetros de pesquisa informados.")
                else:
                    df_display = pd.DataFrame(linhas_display)

                    config_cols = {
                        "MATRÍCULA": st.column_config.TextColumn("MATRÍCULA", disabled=True),
                        "POSTO/GRAD": st.column_config.TextColumn("POSTO/GRAD", disabled=True),
                        "MILITAR": st.column_config.TextColumn("NOME COMPLETO", disabled=True),
                        "LOTAÇÃO": st.column_config.TextColumn("LOTAÇÃO / CIA", disabled=True),
                        "FUNÇÃO CREDS": st.column_config.SelectboxColumn("FUNÇÃO CREDS", options=PERFIS_CREDS, required=True),
                        "FUNÇÃO ESCALA": st.column_config.SelectboxColumn("FUNÇÃO ESCALA", options=PERFIS_ESCALA, required=True),
                        "NÍVEL GERAL": st.column_config.SelectboxColumn("NÍVEL GERAL", options=PERFIS_NIVEL_GERAL, required=True),
                        "CONTA ATIVA": st.column_config.CheckboxColumn("CONTA ATIVA")
                    }

                    chave_editor = f"editor_acessos_v{st.session_state['gestao_usr_version']}"
                    df_editado = st.data_editor(
                        df_display, 
                        column_config=config_cols, 
                        hide_index=True, 
                        use_container_width=True, 
                        key=chave_editor
                    )

                    mapa_efetivo_digitos = {
                        extrair_digitos_matricula(m.get("num_policia")): m 
                        for m in efetivo_banco 
                        if m.get("num_policia")
                    }

                    houve_mudanca = False
                    for idx, row in df_editado.iterrows():
                        matr_raw = str(row["MATRÍCULA"])
                        matr_digitos = extrair_digitos_matricula(matr_raw)
                        
                        p_creds_novo = str(row["FUNÇÃO CREDS"])
                        p_escala_novo = str(row["FUNÇÃO ESCALA"])
                        p_geral_novo = str(row["NÍVEL GERAL"])
                        s_novo = bool(row["CONTA ATIVA"])
                        
                        m_orig = mapa_efetivo_digitos.get(matr_digitos, {})
                        
                        if (p_creds_novo != str(m_orig.get("perfil_creds", "TROPA")) or 
                            p_escala_novo != str(m_orig.get("perfil_escala", "TROPA")) or 
                            p_geral_novo != str(m_orig.get("nivel_acesso", "TROPA")) or 
                            s_novo != bool(m_orig.get("ativo", True))):
                            
                            nome_comp_m = m_orig.get("nome_completo") or row["MILITAR"]
                            if salvar_permissao_militar(
                                matricula=matr_raw, 
                                perfil_creds=p_creds_novo,
                                perfil_escala=p_escala_novo,
                                nivel_acesso=p_geral_novo, 
                                ativo=s_novo,
                                posto=m_orig.get("posto_grad", "SD"),
                                nome=m_orig.get("nome_guerra", "MILITAR"),
                                nome_completo=nome_comp_m
                            ):
                                registrar_audit_log(usr_id_operador, matr_raw, "ALTERAR_ACESSO_TABELA", f"CREDS: [{p_creds_novo}] | ESCALA: [{p_escala_novo}] | GERAL: [{p_geral_novo}]")
                                houve_mudanca = True

                    if houve_mudanca:
                        st.session_state["gestao_usr_version"] += 1
                        st.toast("✅ Permissões salvas com sucesso no Supabase!", icon="🟢")
                        st.rerun()

    # ABA 2: CADASTRO DE UNIDADES
    with abas[1]:
        st.markdown("##### 🏛 Cadastrar Nova Unidade / Batalhão (Multi-Tenant)")
        with st.form("form_nova_unidade_multitenant", clear_on_submit=True):
            c_un_a, c_un_b = st.columns(2)
            with c_un_a:
                nova_unidade_nome = st.text_input("Nome da Nova Unidade / Batalhão:", placeholder="Ex: 47º BPM / 4ª RPM").strip().upper()
                nova_subunidade_nome = st.text_input("Companhia / Subunidade Principal:", placeholder="Ex: 75ª CIA PM").strip().upper()
                novo_pelotao_nome = st.text_input("Pelotão / Subseção (Opcional):", placeholder="Ex: 1º PELOTÃO").strip().upper()
            with c_un_b:
                novo_municipio_nome = st.text_input("Município / Sede (OBRIGATÓRIO):", placeholder="Ex: CARANGOLA").strip().upper()
                nova_brasao_url = st.text_input("URL do Brasão da Unidade (Opcional):", value="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Bras%C3%A3o_PMMG.svg/500px-Bras%C3%A3o_PMMG.svg.png").strip()

            st.markdown("<br>", unsafe_allow_html=True)
            btn_cadastrar_unidade = st.form_submit_button("🏛️ Cadastrar Nova Unidade no SIOP", type="primary", use_container_width=True)

            if btn_cadastrar_unidade:
                if not nova_unidade_nome or not nova_subunidade_nome or not novo_municipio_nome:
                    st.error("⚠️ Preencha os campos obrigatórios: Batalhão, Companhia e Município/Sede.")
                else:
                    if supabase:
                        try:
                            payload_uni = {
                                "batalhao": nova_unidade_nome,
                                "companhia": nova_subunidade_nome,
                                "pelotao": novo_pelotao_nome if novo_pelotao_nome else "N/A",
                                "municipio": novo_municipio_nome,
                                "url_brasao": nova_brasao_url
                            }
                            supabase.table("unidades_config").upsert(payload_uni, on_conflict="batalhao,companhia,pelotao,municipio").execute()
                            st.cache_data.clear()
                            registrar_audit_log(usr_id_operador, None, "CADASTRAR_UNIDADE", f"Nova unidade cadastrada: {nova_unidade_nome} / {nova_subunidade_nome} ({novo_municipio_nome})")
                            st.success(f"✅ Unidade '{nova_unidade_nome} / {nova_subunidade_nome}' cadastrada no Supabase!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar unidade: {e}")

    # ABA 3: LISTAGEM E EXCLUSÃO DE UNIDADES
    with abas[2]:
        exibir_painel_gestao_unidades()

    # ABA 4: LIMPEZA SELETIVA DE DADOS
    with abas[3]:
        st.markdown("### 🚨 Limpeza Seletiva do Banco de Dados (Acesso Restrito ao Programador)")
        st.warning("⚠️ **ATENÇÃO:** Esta ferramenta exclui usuários da tabela **`usuarios`** do Supabase. O login do Programador (`123456`) **NUNCA** será apagado.")

        unidades_disponiveis = set()
        for m in efetivo_banco:
            u_m = str(m.get("lotacao") or m.get("unidade") or "").strip().upper()
            if u_m and u_m not in ["NONE", "N/I", ""]:
                unidades_disponiveis.add(u_m)
                bpm_m = extrair_bpm_mae(u_m)
                if bpm_m:
                    unidades_disponiveis.add(f"TODOS DO {bpm_m}")

        opcoes_limpeza = sorted(list(unidades_disponiveis)) + ["🔥 ZERAR TUDO (EXCETO PROGRAMADOR 123456)"]

        col_limp1, col_limp2 = st.columns([3, 2])
        with col_limp1:
            unidades_alvo = st.multiselect(
                "🎯 Selecione a(s) Unidade(s) ou Ação para Excluir:",
                options=opcoes_limpeza,
                placeholder="Selecione uma ou mais unidades..."
            )

        with col_limp2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            chk_trava_seguranca = st.checkbox("🔒 Desbloquear Botão de Exclusão Definitiva")

        if chk_trava_seguranca:
            if st.button("🚨 EXECUTAR EXCLUSÃO NO SUPABASE", type="primary", use_container_width=True):
                if not unidades_alvo:
                    st.error("⚠️ Selecione ao menos uma unidade para apagar.")
                else:
                    if not supabase:
                        st.error("Conexão com o Supabase indisponível.")
                    else:
                        try:
                            apagar_tudo = any("ZERAR TUDO" in u for u in unidades_alvo)

                            if apagar_tudo:
                                supabase.table("usuarios").delete().neq("usuario_login", "123456").neq("usuario", "123456").execute()
                                msg_sucesso = "✅ Todos os usuários foram excluídos do Supabase (mantido apenas o Programador 123456)!"
                            else:
                                mils_remover = []
                                for u_alvo in unidades_alvo:
                                    if u_alvo.startswith("TODOS DO "):
                                        bpm_alvo = u_alvo.replace("TODOS DO ", "").strip()
                                        mils_remover.extend([
                                            m for m in efetivo_banco 
                                            if extrair_bpm_mae(str(m.get("lotacao") or m.get("unidade") or "")) == bpm_alvo
                                        ])
                                    else:
                                        mils_remover.extend([
                                            m for m in efetivo_banco 
                                            if str(m.get("lotacao") or m.get("unidade") or "").strip().upper() == u_alvo
                                        ])

                                logins_remover = [
                                    str(m.get("num_policia")).strip().upper() 
                                    for m in mils_remover 
                                    if str(m.get("num_policia")).strip() != "123456"
                                ]

                                if logins_remover:
                                    supabase.table("usuarios").delete().in_("usuario_login", logins_remover).execute()
                                    msg_sucesso = f"✅ {len(logins_remover)} usuário(s) da(s) unidade(s) selecionada(s) foram apagados com sucesso!"
                                else:
                                    msg_sucesso = "ℹ️ Nenhum usuário encontrado para as unidades selecionadas."

                            try:
                                carregar_militares_supabase.clear()
                            except Exception:
                                pass
                            st.cache_data.clear()
                            carregar_militares_supabase()
                            registrar_audit_log(usr_id_operador, None, "LIMPEZA_SELETIVA_USUARIOS", f"Limpeza executada pelo programador: {unidades_alvo}")
                            st.success(msg_sucesso)
                            st.rerun()

                        except Exception as ex_limp:
                            st.error(f"Erro ao executar limpeza seletiva: {ex_limp}")