"""
==============================================================================
SIOP PMMG - ORQUESTRADOR PRINCIPAL DO MÓDULO DE PROCEDIMENTOS
Gerencia a autenticação comercial/licenças, navegação lateral e montagem de tela.
Isolado: não interfere nos módulos de Escalas ou TCO.
==============================================================================
"""
from typing import Dict, Any, List, Optional
from datetime import date, datetime
import json

from .core.auth_licenca import verificar_licenca_procedimentos
from .core.prazos_engine import calcular_prazo_continuo_cedm, calcular_prazo_defesa_tav
from .ritos.pcd.regras_pcd import obter_status_regua_ia, ETAPAS_PCD_ORDEM
from .ritos.pcd.modelos_pcd import renderizar_tav, renderizar_termo_oitiva, renderizar_relatorio_pcd
from .ritos.pcd.view_pcd import renderizar_visual_pcd_completo


def renderizar_modulo_procedimentos_html(
    supabase_client,
    usuario_matricula: str,
    procedimentos_ativos: List[Dict[str, Any]],
    procedimento_selecionado: Optional[Dict[str, Any]] = None,
    etapa_ativa_id: str = "TAV"
) -> str:
    """
    Renderiza o ecrã completo do Módulo de Procedimentos.
    Se o militar não tiver licença comercial ativa, devolve um ecrã de bloqueio elegante.
    """
    # 1. Validação da Licença Comercial Dedicada
    validacao_licenca = verificar_licenca_procedimentos(supabase_client, usuario_matricula)
    if not validacao_licenca.get("autorizado", False):
        motivo = validacao_licenca.get("motivo", "Acesso restrito.")
        return f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>SIOP PMMG - Módulo Bloqueado</title>
            <style>
                body {{ background: #030712; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                .card-bloqueio {{ background: #0b1120; border: 1px solid #1e293b; padding: 40px; border-radius: 8px; max-width: 500px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.6); }}
                .icone-trava {{ font-size: 3rem; margin-bottom: 16px; color: #f59e0b; }}
                .btn-contato {{ background: #00f0ff; color: #0b1120; border: none; padding: 12px 24px; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 24px; text-decoration: none; display: inline-block; }}
            </style>
        </head>
        <body>
            <div class="card-bloqueio">
                <div class="icone-trava">🔒</div>
                <h2 style="margin-bottom: 12px; color: #f8fafc;">Módulo de Procedimentos Administrativos</h2>
                <p style="color: #94a3b8; font-size: 0.95rem; line-height: 1.5;">{motivo}</p>
                <p style="color: #64748b; font-size: 0.8rem; margin-top: 14px;">Para adquirir ou renovar a licença deste módulo comercial, solicite a ativação com a administração do sistema.</p>
                <a href="mailto:suporte@sioppmmg.com.br" class="btn-contato">Solicitar Liberação de Licença</a>
            </div>
        </body>
        </html>
        """

    # 2. Construção da Lista Lateral (Em Andamento)
    itens_sidebar = ""
    for proc in procedimentos_ativos:
        num = proc.get("numero_pcd", "PCD")
        dias = proc.get("dias_restantes", 0)
        selecionado = "border-left: 3px solid #00f0ff; background: #1e293b;" if (procedimento_selecionado and proc.get("id") == procedimento_selecionado.get("id")) else ""
        cor_badge = "#00f0ff" if dias > 5 else ("#f59e0b" if dias > 2 else "#ef4444")
        
        itens_sidebar += f"""
        <div style="padding: 10px 14px; margin-bottom: 4px; border-radius: 4px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; {selecionado}" onclick="selecionarProcedimento('{proc.get('id')}')">
            <span style="font-size: 0.85rem; color: #f8fafc;">{num}</span>
            <span style="font-size: 0.75rem; background: rgba(0,0,0,0.3); color: {cor_badge}; padding: 2px 6px; border-radius: 4px; font-weight: bold;">{dias}d</span>
        </div>
        """

    # 3. Preparação do Procedimento Ativo
    if not procedimento_selecionado and procedimentos_ativos:
        procedimento_selecionado = procedimentos_ativos[0]

    conteudo_principal = ""
    if procedimento_selecionado:
        data_rec = procedimento_selecionado.get("data_recebimento_autos", date.today())
        if isinstance(data_rec, str):
            data_rec = datetime.strptime(data_rec, "%Y-%m-%d").date()
        
        prazo_dias = procedimento_selecionado.get("prazo_dias_estipulado", 15)
        calc_prazo = calcular_prazo_continuo_cedm(data_rec, prazo_dias)
        status_etapas = obter_status_regua_ia(etapa_ativa_id)

        # Seleciona o modelo da peça ativa
        titulo_peca = "Termo de Abertura de Vista (TAV)"
        fls_peca = "Fls. 04"
        peca_texto = renderizar_tav(procedimento_selecionado)

        if etapa_ativa_id in ["TESTEMUNHAS_ACUS", "TESTEMUNHAS_DEF", "OITIVA_COMUNICADO"]:
            titulo_peca = "Termo de Oitiva e Depoimento"
            fls_peca = "Fls. 05"
            peca_texto = renderizar_termo_oitiva(procedimento_selecionado)
        elif etapa_ativa_id == "RELATORIO":
            titulo_peca = "Relatório Conclusivo de PCD"
            fls_peca = "Fls. 25"
            peca_texto = renderizar_relatorio_pcd(procedimento_selecionado)

        conteudo_principal = renderizar_visual_pcd_completo(
            dados_pcd=procedimento_selecionado,
            calculo_prazo=calc_prazo,
            status_etapas=status_etapas,
            peca_ativa_html=peca_texto,
            titulo_peca=titulo_peca,
            fls_peca=fls_peca
        )
    else:
        conteudo_principal = """
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #64748b; font-size: 1rem;">
            Nenhum procedimento selecionado. Escolha um na barra lateral ou clique em "Novo Procedimento".
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>SIOP PMMG - Procedimentos Administrativos</title>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            body {{ background: #030712; color: #f8fafc; height: 100vh; display: flex; overflow: hidden; }}
            
            /* BARRA LATERAL INDEPENDENTE */
            .sidebar-procedimentos {{ width: 280px; background: #080e1a; border-right: 1px solid #1e293b; display: flex; flex-direction: column; }}
            .sidebar-header {{ padding: 18px 16px; border-bottom: 1px solid #1e293b; }}
            .user-tag {{ font-size: 0.75rem; color: #00f0ff; background: rgba(0, 240, 255, 0.1); padding: 3px 8px; border-radius: 4px; display: inline-block; margin-top: 6px; font-weight: 600; }}
            .nav-section-title {{ font-size: 0.7rem; font-weight: 700; color: #64748b; text-transform: uppercase; padding: 14px 16px 6px; letter-spacing: 0.5px; }}
            .btn-novo-proc {{ margin: 12px 16px; padding: 10px; background: #1e293b; border: 1px solid #334155; color: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.2s; }}
            .btn-novo-proc:hover {{ background: #00f0ff; color: #0b1120; border-color: #00f0ff; }}
            
            /* ÁREA CENTRAL PRINCIPAL */
            .main-content {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
            
            /* BALÃO FLUTUANTE DA IA */
            .ia-bubble-btn {{ position: fixed; bottom: 20px; right: 24px; width: 48px; height: 48px; border-radius: 50%; background: #00f0ff; color: #0b1120; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; cursor: pointer; box-shadow: 0 4px 15px rgba(0,240,255,0.4); border: none; z-index: 1000; transition: transform 0.2s; }}
            .ia-bubble-btn:hover {{ transform: scale(1.05); }}
            .ia-modal {{ display: none; position: fixed; bottom: 80px; right: 24px; width: 340px; background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.7); z-index: 1000; }}
        </style>
    </head>
    <body>
        <!-- 1. BARRA LATERAL -->
        <div class="sidebar-procedimentos">
            <div class="sidebar-header">
                <div style="font-size: 0.95rem; font-weight: bold; color: #f8fafc;">SIOP PROCEDIMENTOS</div>
                <div class="user-tag">LICENÇA ATIVA • {validacao_licenca.get('plano')}</div>
            </div>

            <button class="btn-novo-proc" onclick="abrirModalNovoProcedimento()">➕ Novo Procedimento</button>

            <div class="nav-section-title">⏳ Em Andamento</div>
            <div style="flex: 1; overflow-y: auto; padding: 0 8px;">
                {itens_sidebar}
            </div>

            <div class="nav-section-title">🔒 Encerrados</div>
            <div style="padding: 10px 16px; font-size: 0.8rem; color: #475569;">
                Nenhum arquivado no ciclo atual.
            </div>
        </div>

        <!-- 2. ÁREA CENTRAL -->
        <div class="main-content">
            {conteudo_principal}
        </div>

        <!-- 3. BALÃO FLUTUANTE DA IA -->
        <button class="ia-bubble-btn" onclick="toggleIaModal()" title="Assistente da Régua da IA">💡</button>
        <div class="ia-modal" id="iaModal">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <span style="font-size: 0.85rem; font-weight: bold; color: #00f0ff;">Assistente Tático MAPPA/CEDM</span>
                <span style="cursor: pointer; color: #94a3b8; font-size: 0.9rem;" onclick="toggleIaModal()">✖</span>
            </div>
            <div style="font-size: 0.8rem; color: #cbd5e1; line-height: 1.4;">
                <p style="margin-bottom: 8px;">• <strong>Prazos:</strong> O prazo contínuo de 15 dias do PCD iniciou-se no 1º dia útil após o recebimento dos autos (Art. 86 CEDM).</p>
                <p style="margin-bottom: 8px;">• <strong>Defesa Prévia (T.A.V.):</strong> O comunicado tem 5 dias úteis contados a partir da ciência formal.</p>
                <p>• <strong>Ordem Instrutória:</strong> Ouça primeiro as testemunhas arroladas. O interrogatório do militar investigado deve ser impreterivelmente o último ato oral.</p>
            </div>
        </div>

        <script>
            function toggleIaModal() {{
                const m = document.getElementById('iaModal');
                m.style.display = (m.style.display === 'block') ? 'none' : 'block';
            }}
            function selecionarProcedimento(pcdId) {{
                window.location.href = '?proc_id=' + pcdId;
            }}
            function abrirModalNovoProcedimento() {{
                alert('Abertura de formulário de novo procedimento.');
            }}
        </script>
    </body>
    </html>
    """