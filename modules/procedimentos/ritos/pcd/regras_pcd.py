"""
SIOP PMMG - REGRAS E FLUXO DO PROCEDIMENTO PCD (PROCESSO DE COMUNICAÇÃO DISCIPLINAR)
Regulamentado pelo CEDM (Lei Estadual 14.310/2002) e MAPPA.
"""
from typing import Dict, Any, List

# Ordem natural cronológica dos atos processuais no PCD
ETAPAS_PCD_ORDEM = [
    {
        "id": "COMUNICACAO",
        "nome": "1. Comunicação Disciplinar",
        "fls_sugerida": "Fls. 01",
        "descricao": "Peça de informação e notícia da transgressão."
    },
    {
        "id": "PORTARIA",
        "nome": "2. Despacho/Portaria PCD",
        "fls_sugerida": "Fls. 02",
        "descricao": "Ato de instauração e delegação com prazo de 15 dias contínuos."
    },
    {
        "id": "TAV",
        "nome": "3. T.A.V. (Abertura de Vista)",
        "fls_sugerida": "Fls. 03 e 04",
        "descricao": "Notificação formal do comunicado com abertura do prazo de 5 dias úteis."
    },
    {
        "id": "TESTEMUNHAS_ACUS",
        "nome": "4. Testemunhas da Administração",
        "fls_sugerida": "Fls. 05 a 10",
        "descricao": "Inquirição de até 3 testemunhas indicadas pelo comunicante/autoridade."
    },
    {
        "id": "TESTEMUNHAS_DEF",
        "nome": "5. Testemunhas da Defesa",
        "fls_sugerida": "Fls. 11 a 16",
        "descricao": "Inquirição de até 3 testemunhas indicadas pela defesa."
    },
    {
        "id": "OITIVA_COMUNICADO",
        "nome": "6. Oitiva do Comunicado",
        "fls_sugerida": "Fls. 17 a 19",
        "descricao": "Último ato oral probatório da instrução."
    },
    {
        "id": "DEFESA_ESCRITA",
        "nome": "7. Alegações / Razões de Defesa",
        "fls_sugerida": "Fls. 20 a 24",
        "descricao": "Juntada das razões defensórias ou certidão de revelia."
    },
    {
        "id": "RELATORIO",
        "nome": "8. Relatório Conclusivo",
        "fls_sugerida": "Fls. 25 a 28",
        "descricao": "Análise analítica das provas pelo Encarregado em até 20 linhas por tese."
    },
    {
        "id": "SOLUCAO",
        "nome": "9. Solução da Autoridade",
        "fls_sugerida": "Fls. 29",
        "descricao": "Decisão do Comandante após deliberação ou parecer do CEDMU."
    }
]

def calcular_limites_testemunhas(total_acusacao: int, total_defesa: int) -> Dict[str, Any]:
    """Valida o limite processual de até 3 testemunhas por polo no PCD."""
    valido_acusacao = total_acusacao <= 3
    valido_defesa = total_defesa <= 3
    
    return {
        "valido": valido_acusacao and valido_defesa,
        "acusacao_restantes": max(0, 3 - total_acusacao),
        "defesa_restantes": max(0, 3 - total_defesa),
        "motivo": "" if (valido_acusacao and valido_defesa) else "O rito do PCD comporta o teto de até 3 testemunhas de acusação e 3 de defesa."
    }

def validar_ordem_oitiva(etapa_atual_id: str, tipo_oitiva: str) -> Dict[str, Any]:
    """
    Impede a audição antecipada do comunicado antes do término das testemunhas,
    salvaguardando a ampla defesa e o contraditório.
    """
    etapas_impedidas = ["COMUNICACAO", "PORTARIA", "TAV", "TESTEMUNHAS_ACUS"]
    if tipo_oitiva.upper() == "COMUNICADO" and etapa_atual_id in etapas_impedidas:
        return {
            "permitido": False,
            "motivo": "Bloqueio do Rito: A oitiva/interrogatório do comunicado deve ocorrer estritamente após a conclusão de todas as testemunhas arroladas."
        }
    return {
        "permitido": True,
        "motivo": "Sequência instrutória regular."
    }

def obter_status_regua_ia(etapa_atual_id: str) -> List[Dict[str, Any]]:
    """Gera o estado dos nós para a Régua da IA renderizar no topo do ecrã."""
    achou_ativo = False
    regua_montada = []

    for etapa in ETAPAS_PCD_ORDEM:
        if etapa["id"] == etapa_atual_id:
            estado = "EM_ANDAMENTO"
            achou_ativo = True
        elif not achou_ativo:
            estado = "CONCLUIDO"
        else:
            estado = "PENDENTE"

        regua_montada.append({
            "id": etapa["id"],
            "nome": etapa["nome"],
            "fls": etapa["fls_sugerida"],
            "descricao": etapa["descricao"],
            "estado": estado
        })

    return regua_montada