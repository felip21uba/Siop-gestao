def pode_acessar_modulo(usuario: dict, modulo: str) -> bool:
    """Valida permissão específica para o módulo solicitado via duplo papel."""
    if not usuario:
        return False

    # Gestor Geral / Admin / Programador possui bypass total
    perfil_geral = usuario.get("nivel_acesso") or usuario.get("perfil_geral") or usuario.get("perfil")
    cargo_geral = usuario.get("cargo_funcao") or ""
    
    if any(p in str(perfil_geral).upper() for p in ["ADMIN", "PROGRAMADOR", "DESENVOLVEDOR"]) or \
       any(p in str(cargo_geral).upper() for p in ["ADMIN", "PROGRAMADOR", "DESENVOLVEDOR"]):
        return True

    if modulo == "creds":
        perfil = usuario.get("perfil_creds", "TROPA")
        return perfil in ["GESTOR_UNIDADE", "GESTOR_CIA", "OPERADOR"]

    elif modulo == "escalas":
        perfil = usuario.get("perfil_escala", "TROPA")
        return perfil in ["CMT_CIA", "SARGENTIACAO", "AUXILIAR_CIA"]

    return False


def usuario_eh_gestor_creds(usr_dados: dict) -> bool:
    """Verifica se o usuário possui acesso de gestor/programador irrestrito ao TCO/CREDS."""
    if not usr_dados or not isinstance(usr_dados, dict):
        return False

    perfil = str(usr_dados.get("nivel_acesso") or usr_dados.get("perfil") or "").upper()
    cargo = str(usr_dados.get("cargo_funcao") or "").upper()
    perfil_creds = str(usr_dados.get("perfil_creds") or "").upper()

    # 🔓 ACESSO IRRESTRITO E SOBERANO PARA PROGRAMADORES E ADMINISTRADORES
    PERFIS_SUPERIORES = ["PROGRAMADOR", "DESENVOLVEDOR", "ADMIN", "TESTADOR", "GESTOR_UNIDADE"]
    if any(p in perfil for p in PERFIS_SUPERIORES) or any(p in cargo for p in PERFIS_SUPERIORES):
        return True

    # Demais perfis operacionais do CREDS
    return perfil_creds in ["GESTOR_UNIDADE", "GESTOR_CIA", "OPERADOR"] or "CREDS" in perfil or "P1" in perfil or "COMANDANTE" in cargo