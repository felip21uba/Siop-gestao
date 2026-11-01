"""
MOTOR DE CÁLCULO DE PRAZOS PROCESSUAIS DA PMMG (ART. 86 LEI 14.310/2002)
Calcula prazos contínuos e úteis com base no recebimento formal dos autos.
"""
from datetime import date, timedelta
from typing import Dict, Any, List

def obter_feriados_padrao(ano: int) -> List[date]:
    """Retorna lista de feriados nacionais e fixos de Minas Gerais."""
    return [
        date(ano, 1, 1),    # Confraternização Universal
        date(ano, 4, 21),   # Tiradentes
        date(ano, 5, 1),    # Dia do Trabalho
        date(ano, 9, 7),    # Independência do Brasil
        date(ano, 10, 12),  # Nossa Senhora Aparecida
        date(ano, 11, 2),   # Finados
        date(ano, 11, 15),  # Proclamação da República
        date(ano, 11, 20),  # Dia da Consciência Negra
        date(ano, 12, 25),  # Natal
    ]

def eh_dia_util(d: date, feriados: List[date]) -> bool:
    """Verifica se uma data é dia útil (segunda a sexta e não feriado)."""
    if d.weekday() >= 5:  # 5 = Sábado, 6 = Domingo
        return False
    if d in feriados:
        return False
    return True

def proximo_dia_util(d: date, feriados: List[date]) -> date:
    """Avança para o primeiro dia útil imediato."""
    cur = d + timedelta(days=1)
    while not eh_dia_util(cur, feriados):
        cur += timedelta(days=1)
    return cur

def calcular_prazo_continuo_cedm(data_recebimento_autos: date, dias_estipulados: int = 15) -> Dict[str, Any]:
    """
    Calcula prazo contínuo de acordo com o Art. 86 do CEDM:
    - Marco zero: Data de recebimento formal/carga dos autos pelo encarregado.
    - Início: Primeiro dia útil seguinte ao recebimento formal.
    - Contagem: Contínua (inclui sábados, domingos e feriados).
    - Vencimento: Prorrogado para o primeiro dia útil subsequente se cair em dia não útil.
    """
    ano_atual = data_recebimento_autos.year
    feriados = obter_feriados_padrao(ano_atual) + obter_feriados_padrao(ano_atual + 1)

    inicio_contagem = proximo_dia_util(data_recebimento_autos, feriados)
    data_fatal_nominal = inicio_contagem + timedelta(days=dias_estipulados - 1)

    data_fatal_prorrogada = data_fatal_nominal
    prorrogado = False
    while not eh_dia_util(data_fatal_prorrogada, feriados):
        data_fatal_prorrogada += timedelta(days=1)
        prorrogado = True

    hoje = date.today()
    dias_restantes = (data_fatal_prorrogada - hoje).days
    total_dias_periodo = (data_fatal_prorrogada - inicio_contagem).days + 1
    dias_decorridos = (hoje - inicio_contagem).days if hoje >= inicio_contagem else 0

    porcentagem_decorrida = 0.0
    if total_dias_periodo > 0 and dias_decorridos > 0:
        porcentagem_decorrida = min(100.0, (dias_decorridos / total_dias_periodo) * 100.0)

    status_prazo = "NO_PRAZO"
    if dias_restantes < 0:
        status_prazo = "VENCIDO"
    elif dias_restantes <= 3:
        status_prazo = "CRITICO"
    elif dias_restantes <= 5:
        status_prazo = "ALERTA"

    return {
        "data_recebimento": data_recebimento_autos.strftime("%d/%m/%Y"),
        "inicio_contagem": inicio_contagem.strftime("%d/%m/%Y"),
        "data_fatal_nominal": data_fatal_nominal.strftime("%d/%m/%Y"),
        "data_fatal_real": data_fatal_prorrogada.strftime("%d/%m/%Y"),
        "prorrogado_art86": prorrogado,
        "dias_restantes": dias_restantes,
        "porcentagem_decorrida": round(porcentagem_decorrida, 1),
        "status_prazo": status_prazo
    }

def calcular_prazo_defesa_tav(data_abertura_vista: date, dias_uteis: int = 5) -> Dict[str, Any]:
    """
    Calcula o prazo estrito do T.A.V. (Art. 57, § 1º do CEDM): 5 dias úteis.
    Inicia-se no primeiro dia útil subsequente à intimação/notificação.
    """
    feriados = obter_feriados_padrao(data_abertura_vista.year) + obter_feriados_padrao(data_abertura_vista.year + 1)
    dia_atual = proximo_dia_util(data_abertura_vista, feriados)
    uteis_contados = 1

    while uteis_contados < dias_uteis:
        dia_atual += timedelta(days=1)
        if eh_dia_util(dia_atual, feriados):
            uteis_contados += 1

    hoje = date.today()
    dias_restantes = (dia_atual - hoje).days

    return {
        "data_notificacao_tav": data_abertura_vista.strftime("%d/%m/%Y"),
        "data_limite_defesa": dia_atual.strftime("%d/%m/%Y"),
        "dias_restantes_defesa": dias_restantes,
        "revelia_iminente": dias_restantes <= 0
    }