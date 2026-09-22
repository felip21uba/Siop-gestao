import streamlit as st
import uuid
import datetime
import pandas as pd

def renderizar_painel_afastamentos(militares, padronizar_graduacao_func, pesos_dict):
    """Renderiza o painel de lançamento de afastamentos e dias neutros no Passo 3."""
    if "afastamentos_militares" not in st.session_state:
        st.session_state["afastamentos_militares"] = []

    with st.expander("🏖️ Lançamento de Afastamentos & Dias Neutros (Férias, LM, Atestados)", expanded=False):
        st.caption("Cadastre afastamentos regulamentares para abater a meta mensal proporcional no Quadro (Passo 5) e Banco de Horas (Passo 7).")
        
        mils_ordenados_afast = sorted(militares, key=lambda x: (
            pesos_dict.get(padronizar_graduacao_func(x.get("posto_grad", "SD")), 99),
            x.get("nome_guerra", "")
        ))
        
        mapa_select_mils_afast = {
            f"{padronizar_graduacao_func(m.get('posto_grad'))} {m.get('nome_guerra')} ({m.get('num_policia', '')})": str(m["id"]) 
            for m in mils_ordenados_afast
        }

        with st.form("form_lancar_afastamento_p3_multi"):
            c_af1, c_af2, c_af3, c_af4 = st.columns([3.5, 2.5, 2, 2])
            
            with c_af1:
                mils_sel_labels = st.multiselect(
                    "Militar(es):", 
                    options=list(mapa_select_mils_afast.keys()),
                    placeholder="Selecione um ou mais militares..."
                )
            with c_af2:
                tipo_afastamento = st.selectbox(
                    "Tipo de Afastamento:",
                    [
                        "FE (Férias Regulamentares)", 
                        "LM (Licença Médica)", 
                        "ATE (Atestado Médico)", 
                        "LUT (Luto / Falecimento)", 
                        "NUP (Núpcias / Casamento)", 
                        "DN (Dia Neutro Institucional)", 
                        "DNT (Dia Neutro Trabalhado)"
                    ]
                )
            with c_af3:
                dt_inicio = st.date_input("Data Início:", datetime.date.today(), format="DD/MM/YYYY", key="p3_dt_ini")
            with c_af4:
                dt_fim = st.date_input("Data Fim:", datetime.date.today(), format="DD/MM/YYYY", key="p3_dt_fim")

            obs_afast = st.text_input("Observação / Publicação BG / Nota do Comando:")

            btn_salvar_afast = st.form_submit_button("📥 Creditar Afastamento / Dias Neutros", type="primary", use_container_width=True)

            if btn_salvar_afast:
                if not mils_sel_labels:
                    st.warning("⚠️ Selecione ao menos um militar!")
                elif dt_fim < dt_inicio:
                    st.error("🚨 A Data Fim não pode ser anterior à Data Início!")
                else:
                    sigla_codigo = tipo_afastamento.split()[0]
                    grade = st.session_state.get("grade_escala_lancamentos", {})
                    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
                    
                    for m_label in mils_sel_labels:
                        m_id_alvo = mapa_select_mils_afast[m_label]
                        
                        novo_afast = {
                            "id": uuid.uuid4().hex[:8],
                            "id_militar": m_id_alvo,
                            "nome_militar": m_label,
                            "sigla": sigla_codigo,
                            "tipo_extenso": tipo_afastamento,
                            "dt_inicio": dt_inicio.strftime("%d/%m/%Y"),
                            "dt_fim": dt_fim.strftime("%d/%m/%Y"),
                            "obs": obs_afast
                        }
                        
                        st.session_state["afastamentos_militares"].append(novo_afast)
                        
                        # Injeta a sigla nas células correspondentes do Quadro Geral (Passo 5)
                        dt_atual = dt_inicio
                        while dt_atual <= dt_fim:
                            ano_c, mes_c, dia_c = dt_atual.year, dt_atual.month, dt_atual.day
                            for pair in chaves_quadro:
                                if isinstance(pair, (tuple, list)) and str(pair[0]) == str(m_id_alvo):
                                    grade[f"{m_id_alvo}_{pair[1]}_{ano_c}_{mes_c:02d}_{dia_c:02d}"] = sigla_codigo
                            dt_atual += datetime.timedelta(days=1)

                    st.session_state["grade_escala_lancamentos"] = grade
                    st.toast(f"✅ Afastamento ({sigla_codigo}) registrado para {len(mils_sel_labels)} militar(es)!", icon="🎉")
                    st.rerun()

        if st.session_state["afastamentos_militares"]:
            st.markdown("##### 📋 Afastamentos Cadastrados na Sessão:")
            df_afast = pd.DataFrame(st.session_state["afastamentos_militares"])
            df_afast["Excluir"] = False
            
            df_edit_afast = st.data_editor(
                df_afast[["nome_militar", "sigla", "dt_inicio", "dt_fim", "obs", "Excluir"]],
                column_config={
                    "nome_militar": st.column_config.TextColumn("Militar", disabled=True),
                    "sigla": st.column_config.TextColumn("Código", disabled=True),
                    "dt_inicio": st.column_config.TextColumn("Início (DD/MM/YYYY)", disabled=True),
                    "dt_fim": st.column_config.TextColumn("Fim (DD/MM/YYYY)", disabled=True),
                    "obs": st.column_config.TextColumn("Observação", disabled=True),
                    "Excluir": st.column_config.CheckboxColumn("🗑️ Remover", default=False)
                },
                hide_index=True, use_container_width=True, key="editor_remover_afastamentos_p3"
            )

            if any(df_edit_afast["Excluir"]):
                indices_manter = [i for i in range(len(df_edit_afast)) if not df_edit_afast.iloc[i]["Excluir"]]
                st.session_state["afastamentos_militares"] = [st.session_state["afastamentos_militares"][idx] for idx in indices_manter]
                st.toast("🗑️ Afastamento removido!", icon="✅")
                st.rerun()