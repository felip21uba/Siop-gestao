def verificar_trava_sobreposicao():
    """
    Auditoria individual por militar:
    1. Bloqueia choque de horários (mesmo militar em dois lugares ao mesmo tempo).
    2. Alerta descanso interjornada inferior a 6 horas para o mesmo militar.
    """
    if st.session_state.get("limpar_avisos_manual", False):
        st.session_state["lista_bloqueios_auditoria"] = []
        st.session_state["lista_avisos_descanso"] = []
        return

    bloqueios = []
    avisos_descanso = []

    grade = st.session_state.get("grade_escala_lancamentos", {})
    chaves = st.session_state.get("militares_no_quadro_chaves", [])
    mils = st.session_state.get("lista_militares", [])
    m_ano = st.session_state.get("ano_escala", datetime.date.today().year)
    m_mes = st.session_state.get("mes_escala", datetime.date.today().month)
    num_dias = calendar.monthrange(m_ano, m_mes)[1]

    # Mapeia os militares por ID único
    mils_map = {
        str(m.get("id")).strip(): f"{padronizar_graduacao(m.get('posto_grad'))} {m.get('nome_guerra')}"
        for m in mils if m.get("id")
    }

    # VARRE ESTRITAMENTE MILITAR POR MILITAR (ISOLADO)
    for m_id_alvo, nome_mil in mils_map.items():
        todos_intervalos_militar = []

        # 1. Coleta TODOS os turnos lançados APENAS para este militar
        for d in range(1, num_dias + 1):
            dt_ref = datetime.date(m_ano, m_mes, d)
            
            # Identifica todas as equipes onde ESTE MILITAR específico tem lançamento
            eqs_deste_militar = [
                str(p[1]) for p in chaves
                if isinstance(p, (tuple, list)) and str(p[0]).strip() == m_id_alvo
            ]

            for eq in eqs_deste_militar:
                val = grade.get(f"{m_id_alvo}_{eq}_{m_ano}_{m_mes:02d}_{d:02d}", "F")
                val_clean = str(val).strip().upper()

                if val_clean in SIGLAS_DIAS_NEUTROS or val_clean in ["", "NONE", "NAN", "F", "D", "X"]:
                    continue

                intervalos = extrair_intervalos_horarios(val_clean, dt_ref)
                for inter in intervalos:
                    todos_intervalos_militar.append({
                        "dia": d,
                        "equipe": eq,
                        "inicio": inter[0],
                        "fim": inter[1],
                        "texto_raw": val_clean
                    })

        if not todos_intervalos_militar:
            continue

        # 2. VERIFICA SOBREPOSIÇÃO / CHOQUE DE HORÁRIOS (APENAS ENTRE TURNOS DO MESMO MILITAR)
        for i in range(len(todos_intervalos_militar)):
            for j in range(i + 1, len(todos_intervalos_militar)):
                t1 = todos_intervalos_militar[i]
                t2 = todos_intervalos_militar[j]

                # Condição matemática de sobreposição de intervalos no tempo
                if (t1["inicio"] < t2["fim"]) and (t1["fim"] > t2["inicio"]):
                    bloqueios.append({
                        "militar": nome_mil,
                        "mensagem": f"Choque no Dia {t1['dia']:02d}/{m_mes:02d}: Lançamento [{t1['equipe']}] ({t1['texto_raw']}) e [{t2['equipe']}] ({t2['texto_raw']}) se sobrepõem no mesmo horário!"
                    })

        # 3. VERIFICA DESCANSO INTERJORNADA < 6 HORAS (LINHA DO TEMPO CRONOLÓGICA DO MESMO MILITAR)
        intervalos_ordenados = sorted(todos_intervalos_militar, key=lambda x: x["inicio"])
        for i in range(len(intervalos_ordenados) - 1):
            atual = intervalos_ordenados[i]
            proximo = intervalos_ordenados[i + 1]

            if proximo["inicio"] >= atual["fim"]:
                diferenca_horas = (proximo["inicio"] - atual["fim"]).total_seconds() / 3600.0
                if diferenca_horas < 6.0:
                    avisos_descanso.append({
                        "militar": nome_mil,
                        "mensagem": f"Intervalo de descanso curto: Término no Dia {atual['dia']:02d} ({atual['texto_raw']}) e Início no Dia {proximo['dia']:02d} ({proximo['texto_raw']}) com apenas {diferenca_horas:.1f}h de descanso (mínimo: 6h)."
                    })

    st.session_state["lista_bloqueios_auditoria"] = bloqueios
    st.session_state["lista_avisos_descanso"] = avisos_descanso