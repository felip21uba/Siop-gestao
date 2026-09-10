import streamlit as st
import uuid
import datetime
import pandas as pd

def renderizar_painel_afastamentos(militares, padronizar_graduacao_func, pesos_dict):
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

        with st.form("form_lancar_afastamento_p3"):
            c_af1, c_af2, c_af3, c_af4 = st.columns([3, 2, 2, 2])
            
            with c_af1:
                mil_sel_label = st.selectbox("Militar:", list(mapa_select_mils_afast.keys()) if mapa_select_mils_afast else ["Nenhum militar cadastrado"])
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
                dt_inicio = st.date_input("Data Início:", datetime.date.today())
            with c_af4:
                dt_fim = st.date_input("Data Fim:", datetime.date.today())

            obs_afast = st.text_input("Observação / Publicação BG / Nota do Comando:")

            btn_salvar_afast = st.form_submit_button("📥 Creditar Afastamento / Dias Neutros", type="primary", use_container_width=True)

            if btn_salvar_afast and mapa_select_mils_afast:
                if dt_fim < dt_inicio:
                    st.error("🚨 A Data Fim não pode ser anterior à Data Início!")
                else:
                    sigla_codigo = tipo_afastamento.split()[0]
                    m_id_alvo = mapa_select_mils_afast[mil_sel_label]
                    
                    novo_afast = {
                        "id": uuid.uuid4().hex[:8],
                        "id_militar": m_id_alvo,
                        "nome_militar": mil_sel_label,
                        "sigla": sigla_codigo,
                        "tipo_extenso": tipo_afastamento,
                        "dt_inicio": dt_inicio.strftime("%d/%m/%Y"),
                        "dt_fim": dt_fim.strftime("%d/%m/%Y"),
                        "obs": obs_afast
                    }
                    
                    st.session_state["afastamentos_militares"].append(novo_afast)
                    
                    grade = st.session_state.get("grade_escala_lancamentos", {})
                    chaves_quadro = st.session_state.get("militares_no_quadro_chaves", [])
                    
                    dt_atual = dt_inicio
                    while dt_atual <= dt_fim:
                        ano_c = dt_atual.year
                        mes_c = dt_atual.month
                        dia_c = dt_atual.day
                        
                        for pair in chaves_quadro:
                            if isinstance(pair, (tuple, list)) and str(pair[0]) == str(m_id_alvo):
                                eq_nome = pair[1]
                                chave_celula = f"{m_id_alvo}_{eq_nome}_{ano_c}_{mes_c:02d}_{dia_c:02d}"
                                grade[chave_celula] = sigla_codigo

                        dt_atual += datetime.timedelta(days=1)

                    st.session_state["grade_escala_lancamentos"] = grade
                    st.toast(f"✅ Afastamento ({sigla_codigo}) registrado para {mil_sel_label}!", icon="🎉")
                    st.rerun()

        if st.session_state["afastamentos_militares"]:
            st.markdown("##### 📋 Afastamentos Cadastrados na Sessão:")
            df_afast = pd.DataFrame(st.session_state["afastamentos_militares"])
            df_afast["Excluir"] = False
            
            df_visual = df_afast[["nome_militar", "sigla", "dt_inicio", "dt_fim", "obs", "Excluir"]]
            
            df_edit_afast = st.data_editor(
                df_visual,
                column_config={
                    "nome_militar": st.column_config.TextColumn("Militar", disabled=True),
                    "sigla": st.column_config.TextColumn("Código", disabled=True),
                    "dt_inicio": st.column_config.TextColumn("Início", disabled=True),
                    "dt_fim": st.column_config.TextColumn("Fim", disabled=True),
                    "obs": st.column_config.TextColumn("Observação", disabled=True),
                    "Excluir": st.column_config.CheckboxColumn("🗑️ Remover", default=False)
                },
                hide_index=True,
                use_container_width=True,
                key="editor_remover_afastamentos_p3"
            )

            if any(df_edit_afast["Excluir"]):
                indices_manter = [i for i in range(len(df_edit_afast)) if not df_edit_afast.iloc[i]["Excluir"]]
                st.session_state["afastamentos_militares"] = [st.session_state["afastamentos_militares"][idx] for idx in indices_manter]
                st.toast("🗑️ Afastamento removido!", icon="✅")
                st.rerun()