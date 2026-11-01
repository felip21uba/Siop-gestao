"""
==============================================================================
SIOP PMMG - SUBMÓDULO DO RITO PCD (PROCESSO DE COMUNICAÇÃO DISCIPLINAR)
Isolado: alterações neste pacote não afetam o PAD, SAD, IPM ou outros módulos.
==============================================================================
"""

from .regras_pcd import (
    ETAPAS_PCD_ORDEM,
    validar_ordem_oitiva,
    obter_status_regua_ia,
    calcular_limites_testemunhas
)
from .modelos_pcd import (
    gerar_cabecalho_oficial,
    renderizar_tav,
    renderizar_termo_oitiva,
    renderizar_termo_juntada,
    renderizar_relatorio_pcd
)

__all__ = [
    "ETAPAS_PCD_ORDEM",
    "validar_ordem_oitiva",
    "obter_status_regua_ia",
    "calcular_limites_testemunhas",
    "gerar_cabecalho_oficial",
    "renderizar_tav",
    "renderizar_termo_oitiva",
    "renderizar_termo_juntada",
    "renderizar_relatorio_pcd"
]