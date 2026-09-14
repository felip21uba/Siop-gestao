def gerar_template_alerta_deslocamento(nome_militar: str, posto_num: int, local: str, horario_inicio: str, horario_fim: str, missao: str, link_maps: str = None) -> str:
    """Monta a mensagem de alerta pré-deslocamento ajustada para 10 minutos."""
    msg = (
        f"🚨 *ALERTA SIOP - TROPA EM CAMPO*\n\n"
        f"Olá, *{nome_militar.upper()}*!\n"
        f"Faltam *10 minutos* para o seu próximo deslocamento programado.\n\n"
        f"📍 *Posto:* PE {posto_num:02d} - {local}\n"
        f"⏰ *Horário:* {horario_inicio} às {horario_fim}\n"
        f"🎯 *Missão Tática:* {missao}\n"
    )
    if link_maps:
        msg += f"\n🗺️ *Rota de Navegação GPS:* {link_maps}\n"

    msg += "\n_Mensagem automática enviada pela Central de Operações SIOP._"
    return msg