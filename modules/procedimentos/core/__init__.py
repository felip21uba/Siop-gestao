"""
==============================================================================
SIOP PMMG - MÓDULO PROCEDIMENTOS
Sub-módulo Core: Regras de negócio, autorização e motores centrais de prazos.
==============================================================================
"""

from .auth_licenca import verificar_licenca_procedimentos, registrar_ou_atualizar_licenca
from .prazos_engine import calcular_prazo_continuo_cedm, calcular_prazo_defesa_tav
from .fls_control import GerenciadorFolhasAutos

__all__ = [
    "verificar_licenca_procedimentos",
    "registrar_ou_atualizar_licenca",
    "calcular_prazo_continuo_cedm",
    "calcular_prazo_defesa_tav",
    "GerenciadorFolhasAutos",
]