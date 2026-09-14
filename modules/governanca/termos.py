import streamlit as st
import pandas as pd
import datetime
from core.database import supabase, registrar_audit_log

def obter_texto_termo_ativo():
    if supabase:
        try:
            res = supabase.table("configuracoes_sistema").select("valor").eq("chave", "termo_compliance_texto").execute()
            if res.data and len(res.data) > 0:
                return res.data[0]["valor"]
        except Exception:
            pass
    return (
        "TERMO DE RESPONSABILIDADE E FIEL DEPÓSITO DE MATERIAIS - TCO\n\n"
        "Pelo presente termo, declaro estar ciente da custódia física dos materiais apreendidos sob minha responsabilidade, "
        "comprometendo-me a zelar pela integridade dos invólucros/lacres e cumprir rigorosamente as normas de tramitação "
        "do Decreto Estadual nº 48.243/2021 e Diretriz Institucional de Cadeia de Custódia."
    )

def salvar_texto_termo_ativo(novo_texto, operador_pm):
    if not supabase:
        return False
    try:
        supabase.table("configuracoes_sistema").upsert({
            "chave": "termo_compliance_texto",
            "valor": novo_texto,
            "atualizado_por": operador_pm,
            "data_atualizacao": datetime.datetime.now().isoformat()
        }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar termo: {e}")
        return False

def renderizar_aba_termos_aceites(eh_admin, cargo_operador, nome_operador):
    c_t1, c_t2 = st.columns([2, 2.2])

    with c_t1:
        with st.container(border=True):
            st.markdown("##### ✏️ Redação do Termo de Compliance TCO")
            st.caption("Atualize o texto oficial exigido aos militares no momento do aceite.")
            
            texto_atual = obter_texto_termo_ativo()
            novo_texto_termo = st.text_area(
                "Minuta do Termo de Fiel Depósito:", 
                value=texto_atual, 
                height=240, 
                disabled=not eh_admin
            )

            if eh_admin:
                if st.button("💾 Salvar Nova Versão do Termo", type="primary", use_container_width=True):
                    if salvar_texto_termo_ativo(novo_texto_termo, f"{cargo_operador} {nome_operador}"):
                        registrar_audit_log(
                            operador_pm=f"{cargo_operador} {nome_operador}",
                            alvo_pm="SISTEMA",
                            tipo_acao="ATUALIZAÇÃO TERMO COMPLIANCE",
                            descricao="Redação oficial do Termo de Compliance do TCO atualizada no banco de dados."
                        )
                        st.success("Termo de Compliance atualizado com sucesso!")
                        st.rerun()
            else:
                st.warning("🔒 Apenas Administradores e P1 podem editar a minuta oficial do termo.")

    with c_t2:
        with st.container(border=True):
            st.markdown("##### 🔍 Consultar Aceites Registrados")
            st.caption("Pesquise a concordância formal dos militares com o termo de custódia.")

            filtro_pm = st.text_input("Filtrar por Policial (Nome ou Nº PM):", placeholder="Ex: ASSUNCAO ou 145890").strip().upper()

            aceites_banco = []
            if supabase:
                try:
                    query = supabase.table("aceites_compliance").select("*")
                    if filtro_pm:
                        query = query.ilike("nome_militar", f"%{filtro_pm}%")
                    res_ac = query.order("data_aceite", desc=True).limit(50).execute()
                    aceites_banco = res_ac.data or []
                except Exception:
                    pass

            if aceites_banco:
                df_ac = pd.DataFrame(aceites_banco)
                st.dataframe(
                    df_ac[["data_aceite", "num_policia", "nome_militar", "unidade", "cargo_funcao"]],
                    column_config={
                        "data_aceite": "Data/Hora Aceite",
                        "num_policia": "Nº PM",
                        "nome_militar": "Nome do Militar",
                        "unidade": "Unidade Orgânica",
                        "cargo_funcao": "Cargo/Função"
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("Nenhum registro de aceite localizado com os filtros aplicados.")
                