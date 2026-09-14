def pode_acessar_modulo(usuario: dict, modulo: str) -> bool:
    """Valida permissão específica para o módulo solicitado via duplo papel."""
    if not usuario:
        return False

    # Gestor Geral / Admin possui bypass
    perfil_geral = usuario.get("nivel_acesso") or usuario.get("perfil_geral")
    if perfil_geral in ["ADMIN", "PROGRAMADOR"]:
        return True

    if modulo == "creds":
        perfil = usuario.get("perfil_creds", "TROPA")
        return perfil in ["GESTOR_UNIDADE", "GESTOR_CIA", "OPERADOR"]

    elif modulo == "escalas":
        perfil = usuario.get("perfil_escala", "TROPA")
        return perfil in ["CMT_CIA", "SARGENTIACAO", "AUXILIAR_CIA"]

    return False

def usuario_eh_gestor_creds(usuario: dict) -> bool:
    """Verifica se o usuário possui prerrogativa de gestão sobre o CREDS/TCO."""
    if not usuario:
        return False

    perfil_geral = usuario.get("nivel_acesso") or usuario.get("perfil_geral")
    perfil_creds = usuario.get("perfil_creds", "TROPA")
    perfil_escala = usuario.get("perfil_escala", "TROPA")

    return (
        perfil_geral in ["ADMIN", "PROGRAMADOR", "P1", "COMANDANTE", "COMANDANTE_CIA"]
        or perfil_creds in ["GESTOR_UNIDADE", "GESTOR_CIA"]
        or perfil_escala in ["CMT_CIA", "COMANDANTE_CIA"]
    )