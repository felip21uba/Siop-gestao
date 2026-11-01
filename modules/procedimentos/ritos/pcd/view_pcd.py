"""
==============================================================================
SIOP PMMG - CAMADA VISUAL DESACOPLADA DO PCD (PROCESSO DE COMUNICAÇÃO DISCIPLINAR)
Exibe a interface de trabalho do PCD com a Régua da IA contínua e foco em documento único.
Não interfere no visual do PAD, SAD ou outros módulos do sistema.
==============================================================================
"""
from typing import Dict, Any, List
import json


def renderizar_regua_ia_html(calculo_prazo: Dict[str, Any], status_etapas: List[Dict[str, Any]]) -> str:
    """
    Gera o HTML da Régua da IA com o termómetro contínuo do Art. 86 do CEDM
    e o estado cronológico dos atos instrutórios.
    """
    dias_restantes = calculo_prazo.get("dias_restantes", 0)
    status_prazo = calculo_prazo.get("status_prazo", "NO_PRAZO")
    pct_decorrido = calculo_prazo.get("porcentagem_decorrida", 0.0)

    # Determinação da cor da barra de prazo
    cor_barra = "#00f0ff"
    if status_prazo == "ALERTA":
        cor_barra = "#f59e0b"
    elif status_prazo in ["CRITICO", "VENCIDO"]:
        cor_barra = "#ef4444"

    etapas_html = ""
    for etapa in status_etapas:
        estado = etapa["estado"]
        badge_cor = "background: #1e293b; color: #64748b; border: 1px solid #334155;"
        icone = "○"

        if estado == "CONCLUIDO":
            badge_cor = "background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid #10b981;"
            icone = "✔"
        elif estado == "EM_ANDAMENTO":
            badge_cor = "background: rgba(0, 240, 255, 0.15); color: #00f0ff; border: 1px solid #00f0ff; box-shadow: 0 0 10px rgba(0,240,255,0.3);"
            icone = "●"

        etapas_html += f"""
        <div class="regua-no" style="display: flex; flex-direction: column; align-items: center; min-width: 110px; cursor: pointer; margin: 0 6px;" onclick="trocarEtapaPCD('{etapa['id']}')">
            <span style="font-size: 0.65rem; color: #94a3b8; margin-bottom: 2px;">{etapa['fls']}</span>
            <div style="width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: bold; {badge_cor}">
                {icone}
            </div>
            <span style="font-size: 0.72rem; color: #f8fafc; margin-top: 4px; text-align: center; white-space: nowrap;">{etapa['nome']}</span>
        </div>
        """

    return f"""
    <div class="regua-ia-container" style="background: #0b1120; border-bottom: 1px solid #1e293b; padding: 12px 24px;">
        <!-- Bloco de Prazos Contínuos e Alertas da IA -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="background: rgba(0,240,255,0.1); color: #00f0ff; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; border: 1px solid rgba(0,240,255,0.3);">
                    RÉGUA IA - ART. 86 CEDM
                </span>
                <span style="font-size: 0.8rem; color: #94a3b8;">
                    Receção Formal: <strong style="color: #f8fafc;">{calculo_prazo.get('data_recebimento', '--')}</strong> | 
                    Início: <strong style="color: #f8fafc;">{calculo_prazo.get('inicio_contagem', '--')}</strong> | 
                    Data Fatal: <strong style="color: #f8fafc;">{calculo_prazo.get('data_fatal_real', '--')}</strong>
                </span>
            </div>
            <div style="font-size: 0.85rem; font-weight: 600; color: {cor_barra};">
                ⏳ {dias_restantes} DIAS RESTANTES ({status_prazo})
            </div>
        </div>

        <!-- Termómetro Visual de Percentual -->
        <div style="width: 100%; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; margin-bottom: 12px;">
            <div style="width: {pct_decorrido}%; height: 100%; background: {cor_barra}; transition: width 0.4s ease;"></div>
        </div>

        <!-- Sequência de Nós dos Atos Processuais -->
        <div style="display: flex; align-items: flex-start; justify-content: space-between; overflow-x: auto; padding-bottom: 4px;">
            {etapas_html}
        </div>
    </div>
    """


def renderizar_visual_pcd_completo(dados_pcd: Dict[str, Any], calculo_prazo: Dict[str, Any], status_etapas: List[Dict[str, Any]], peca_ativa_html: str, titulo_peca: str, fls_peca: str) -> str:
    """
    Retorna a estrutura completa do ecrã de operação do PCD:
    Régua no topo + Folha de trabalho limpa e barra de ações.
    """
    regua_html = renderizar_regua_ia_html(calculo_prazo, status_etapas)

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>SIOP PMMG - Procedimento {dados_pcd.get('numero_pcd', '')}</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
            body {{ background: #030712; color: #f8fafc; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
            
            /* Área Central da Folha Digital */
            .work-area {{ flex: 1; overflow-y: auto; background: #080e1a; padding: 24px; display: flex; justify-content: center; }}
            .folha-a4 {{ width: 820px; min-height: 1100px; background: #ffffff; color: #111827; padding: 60px 70px; border-radius: 2px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); position: relative; }}
            .carimbo-fls {{ position: absolute; top: 35px; right: 50px; border: 1.5px solid #111827; padding: 4px 10px; font-size: 0.8rem; font-weight: bold; letter-spacing: 0.5px; }}
            
            /* Barra de Ações do Documento */
            .doc-action-bar {{ display: flex; justify-content: space-between; align-items: center; width: 820px; margin-bottom: 12px; }}
            .btn-action {{ background: #1e293b; color: #f8fafc; border: 1px solid #334155; padding: 8px 14px; border-radius: 6px; font-size: 0.8rem; cursor: pointer; transition: all 0.2s; }}
            .btn-action:hover {{ background: #334155; border-color: #00f0ff; }}
            .btn-primary {{ background: #00f0ff; color: #0b1120; font-weight: 600; border: none; }}
            .btn-primary:hover {{ background: #38bdf8; }}
        </style>
    </head>
    <body>
        <!-- 1. RÉGUA CONTÍNUA DA IA -->
        {regua_html}

        <!-- 2. PAINEL DE OPERAÇÃO DO DOCUMENTO EM FOCO -->
        <div class="work-area">
            <div>
                <div class="doc-action-bar">
                    <div>
                        <span style="font-size: 0.9rem; font-weight: 600; color: #f8fafc;">{titulo_peca}</span>
                        <span style="font-size: 0.8rem; color: #94a3b8; margin-left: 8px;">({fls_peca})</span>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn-action" onclick="abrirSegundaTelaDepoente('{dados_pcd.get('id', '')}')">🖥️ 2ª Tela (Depoente)</button>
                        <button class="btn-action" onclick="baixarDocx()">📥 Baixar Word (.docx)</button>
                        <button class="btn-action" onclick="baixarPdf()">📄 Baixar PDF</button>
                        <button class="btn-action btn-primary" onclick="salvarAlteracoesPCD()">💾 Salvar Ato</button>
                    </div>
                </div>

                <!-- Folha Limpa com o Modelo Oficial -->
                <div class="folha-a4">
                    <div class="carimbo-fls">{fls_peca}</div>
                    <div id="corpo-documento-editavel" contenteditable="true" style="outline: none; line-height: 1.6; font-size: 0.95rem; white-space: pre-wrap;">{peca_ativa_html}</div>
                </div>
            </div>
        </div>

        <script>
            function trocarEtapaPCD(etapaId) {{
                window.parent.postMessage({{ tipo: 'NAVEGAR_ETAPA_PCD', etapaId: etapaId }}, '*');
            }}
            function salvarAlteracoesPCD() {{
                const textoAtualizado = document.getElementById('corpo-documento-editavel').innerText;
                window.parent.postMessage({{ tipo: 'SALVAR_DOCUMENTO_PCD', conteudo: textoAtualizado }}, '*');
            }}
            function abrirSegundaTelaDepoente(pcdId) {{
                window.open('/procedimentos/depoente/' + pcdId, 'DepoenteScreen', 'width=1000,height=800');
            }}
            function baixarDocx() {{
                window.parent.postMessage({{ tipo: 'EXPORTAR_DOCX_PCD' }}, '*');
            }}
            function baixarPdf() {{
                window.parent.postMessage({{ tipo: 'EXPORTAR_PDF_PCD' }}, '*');
            }}
        </script>
    </body>
    </html>
    """