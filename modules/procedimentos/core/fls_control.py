"""
CONTROLE DE NUMERAÇÃO DE FOLHAS E JUNTADAS (SIOP - PROCEDIMENTOS)
Mantém o índice de fls. contínuo e auditável em conformidade com o MAPPA.
"""
from typing import Dict, Any, List, Optional

class GerenciadorFolhasAutos:
    def __init__(self, folha_inicial: int = 1):
        self.proxima_folha = folha_inicial

    def reservar_folhas(self, qtd_folhas: int) -> Dict[str, Any]:
        """
        Reserva uma faixa de folhas para uma peça ou juntada.
        Ex: Se a próxima for 5 e a peça tiver 2 folhas, reserva 5 e 6.
        """
        if qtd_folhas < 1:
            qtd_folhas = 1

        fls_inicio = self.proxima_folha
        fls_fim = self.proxima_folha + qtd_folhas - 1
        self.proxima_folha = fls_fim + 1

        rotulo = f"Fls. {fls_inicio:02d}" if fls_inicio == fls_fim else f"Fls. {fls_inicio:02d} a {fls_fim:02d}"

        return {
            "folha_inicial": fls_inicio,
            "folha_final": fls_fim,
            "rotulo_formatado": rotulo,
            "qtd_folhas": qtd_folhas
        }

    def ajustar_folha_atual(self, nova_folha_proxima: int):
        """Permite ao encarregado reajustar manualmente a numeração caso necessário."""
        if nova_folha_proxima >= 1:
            self.proxima_folha = nova_folha_proxima

    def obter_folha_atual(self) -> int:
        return self.proxima_folha