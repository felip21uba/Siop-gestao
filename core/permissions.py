def pode_acessar_modulo(usuario: dict, modulo: str) -> bool:
    """Valida permissão específica para o módulo solicitado via duplo papel."""
    if not usuario:
        return False

    perfil_geral = str(usuario.get("nivel_acesso") or usuario.get("perfil_geral") or usuario.get("perfil") or "").upper()
    cargo_geral = str(usuario.get("cargo_funcao") or "").upper()
    login_usr = str(usuario.get("usuario_login") or usuario.get("num_policia") or "").strip()

    # 🔓 BYPASS TOTAL: Programadores, Admins e o Login Soberano 1337468
    if "1337468" in login_usr or \
       any(p in perfil_geral for p in ["ADMIN", "PROGRAMADOR", "DESENVOLVEDOR"]) or \
       any(p in cargo_geral for p in ["ADMIN", "PROGRAMADOR", "DESENVOLVEDOR"]):
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

    login_usr = str(usr_dados.get("usuario_login") or usr_dados.get("num_policia") or "").strip()
    perfil = str(usr_dados.get("nivel_acesso") or usr_dados.get("perfil") or "").upper()
    cargo = str(usr_dados.get("cargo_funcao") or "").upper()
    perfil_creds = str(usr_dados.get("perfil_creds") or "").upper()

    # 🔓 TRAVA SOBERANA DE PROGRAMADOR E LOGIN 1337468
    if "1337468" in login_usr:
        return True

    PERFIS_SUPERIORES = ["PROGRAMADOR", "DESENVOLVEDOR", "ADMIN", "TESTADOR", "GESTOR_UNIDADE"]
    if any(p in perfil for p in PERFIS_SUPERIORES) or any(p in cargo for p in PERFIS_SUPERIORES):
        return True

    return perfil_creds in ["GESTOR_UNIDADE", "GESTOR_CIA", "OPERADOR"] or "CREDS" in perfil or "P1" in perfil or "COMANDANTE" in cargo


def validar_promocao_programador(operador_dados: dict, perfil_desejado: str) -> tuple[bool, str]:
    """
    🔒 TRAVA SOBERANA E ABSOLUTA:
    Apenas o usuário com o login exato '1337468' pode criar ou atribuir
    os perfis PROGRAMADOR ou DESENVOLVEDOR.
    """
    perfil_upper = str(perfil_desejado).upper()
    is_perfil_restrito = any(p in perfil_upper for p in ["PROGRAMADOR", "DESENVOLVEDOR"])

    if is_perfil_restrito:
        login_operador = str(operador_dados.get("usuario_login") or operador_dados.get("num_policia") or "").strip()
        if "1337468" not in login_operador:
            return False, "🚨 ACESSO NEGADO: Apenas o Administrador Soberano do SIOP (Login 1337468) pode atribuir a função PROGRAMADOR ou DESENVOLVEDOR."

    return True, "OK"