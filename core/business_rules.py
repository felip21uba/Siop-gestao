import datetime
import calendar

# =========================================================================
# 1. TRAVA DE SEGURANÇA: IMPEDIMENTO DE MILITAR EM DOIS LUGARES
# =========================================================================
def verificar_conflito_militar(matriz_escala: dict, militar_id: str, dia: int, turno_novo: str) -> tuple[bool, str]:
    """
    Verifica se o militar já possui outro serviço marcado no mesmo dia.
    Evita escalar a mesma pessoa duas vezes ou gerar conflito de horário.
    """
    # Se o novo lançamento for Folga ou Licença, não há conflito
    if turno_novo in ["FOLGA", "NEUTRO", "LICENCA", "FERIAS", ""]:
        return False, "Sem conflito"

    # A chave na memória é formada por: IDdoMilitar_Dia do Mês (Ex: "m1_15")
    chave = f"{militar_id}_{dia}"
    turno_existente = matriz_escala.get(chave)

    # Se já existir algo marcado diferente de folga, aciona o bloqueio
    if turno_existente and turno_existente not in ["FOLGA", "NEUTRO", ""]:
        if turno_existente != turno_novo:
            return True, f"⚠️ IMPEDIMENTO: Militar já está escalado no dia {dia} no turno [{turno_existente}]."

    return False, "OK"


# =========================================================================
# 2. CÁLCULO DE JORNADA E PRÉ-TURNO (COM HORA NOTURNA REDUZIDA)
# =========================================================================
def calcular_horas_turno(h_inicio: str = "07:00", h_fim: str = "19:00", pre_turno_min: int = 0) -> float:
    """
    Calcula o total de horas trabalhadas em um turno.
    Leva em consideração o pré-turno de apresentação e o fator noturno (23h às 05h).
    """
    try:
        h_ini_h, h_ini_m = map(int, h_inicio.split(':'))
        h_fim_h, h_fim_m = map(int, h_fim.split(':'))
    except Exception:
        h_ini_h, h_ini_m = 7, 0
        h_fim_h, h_fim_m = 19, 0

    # Converter tudo para minutos
    t_ini = h_ini_h * 60 + h_ini_m - pre_turno_min
    t_fim = h_fim_h * 60 + h_fim_m

    # Se o turno virar a noite (ex: 19h às 07h do dia seguinte)
    if t_fim <= t_ini:
        t_fim += 24 * 60

    total_minutos_equivalentes = 0.0
    for m in range(t_ini, t_fim):
        minuto_do_dia = m % (24 * 60)
        # Entre 23:00 e 05:00 a hora passa mais rápido (Adicional noturno: 1 min vale 1.2 min)
        if minuto_do_dia >= 23 * 60 or minuto_do_dia < 5 * 60:
            total_minutos_equivalentes += 1.2
        else:
            total_minutos_equivalentes += 1.0

    return round(total_minutos_equivalentes / 60.0, 2)


# =========================================================================
# 3. PREENCHIMENTO AUTOMÁTICO DE ESCALAS (ADM, CICLOS E DOBRADINHA)
# =========================================================================
def gerar_grade_automatica(modalidade: str, ano: int, mes: int, semana_dobradinha: str = "SEMANA A") -> dict:
    """
    Preenche automaticamente os dias do mês inteiro de acordo com a regra selecionada.
    Retorna um dicionário indicando o turno de cada dia: {1: "08H AS 17H", 2: "FOLGA", ...}
    """
    # Descobre quantos dias o mês tem (28, 29, 30 ou 31)
    dias_no_mes = calendar.monthrange(ano, mes)[1]
    grade = {}

    for dia in range(1, dias_no_mes + 1):
        data_atual = datetime.date(ano, mes, dia)
        dia_da_semana = data_atual.weekday()  # 0 = Segunda-feira, 6 = Domingo

        # Regra 1: Expediente Administrativo (Segunda a Sexta-feira)
        if modalidade == "ADM":
            if dia_da_semana < 5:  # Segunda a Sexta
                grade[dia] = "08H AS 17H"
            else:
                grade[dia] = "FOLGA"

        # Regra 2: Ciclo 12x36 (Trabalha um dia sim, um dia não)
        elif modalidade == "CICLO 12X36H":
            if dia % 2 != 0:
                grade[dia] = "07H AS 19H"
            else:
                grade[dia] = "FOLGA"

        # Regra 3: Ciclo 12x72 (Trabalha 1 dia e folga 3 dias)
        elif modalidade == "CICLO 12X72H":
            if dia % 4 == 1:
                grade[dia] = "07H AS 19H"
            else:
                grade[dia] = "FOLGA"

        # Regra 4: Dobradinha PMMG (Alterna os dias de serviço a cada semana)
        elif modalidade == "DOBRADINHA":
            num_semana = data_atual.isocalendar()[1]
            semana_par = (num_semana % 2 == 0)

            if semana_dobradinha == "SEMANA A":
                trabalha = (dia_da_semana in [0, 2, 4]) if not semana_par else (dia_da_semana in [1, 3])
            else:
                trabalha = (dia_da_semana in [1, 3]) if not semana_par else (dia_da_semana in [0, 2, 4])

            if trabalha and dia_da_semana < 5:
                grade[dia] = "07H AS 19H"
            else:
                grade[dia] = "FOLGA"

        else:
            grade[dia] = "FOLGA"

    return grade