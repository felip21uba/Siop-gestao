import streamlit as st
import time
import datetime
import json
import streamlit.components.v1 as components
from core.database import supabase

# ⏱️ 20 minutos = 1.200 segundos
TEMPO_TIMEOUT_SEGUNDOS = 20 * 60

def renderizar_relogio_sessao(tempo_minutos=20):
    """Renderiza o relógio flutuante de contagem regressiva no canto inferior direito."""
    tempo_segundos = tempo_minutos * 60
    
    html_relogio = f"""
    <div id="badge-sessao-box" style="
        position: fixed;
        bottom: 12px;
        right: 12px;
        z-index: 999999;
        background-color: rgba(15, 23, 42, 0.88);
        color: #ffffff;
        padding: 5px 12px;
        border-radius: 20px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 11px;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.12);
        display: flex;
        align-items: center;
        gap: 6px;
        user-select: none;
        pointer-events: none;
    ">
        <span id="sessao-icon" style="font-size: 12px;">⏱️</span>
        <span>Sessão: <span id="sessao-timer" style="font-family: monospace; font-size: 12px; font-weight: bold; color: #38bdf8;">20:00</span></span>
    </div>

    <script>
        (function() {{
            var totalSeconds = {tempo_segundos};
            var timerDisplay = document.getElementById('sessao-timer');
            var iconDisplay = document.getElementById('sessao-icon');
            var boxDisplay = document.getElementById('badge-sessao-box');

            function atualizarContagem() {{
                var minutos = Math.floor(totalSeconds / 60);
                var segundos = totalSeconds % 60;

                var minStr = minutos < 10 ? "0" + minutos : minutos;
                var secStr = segundos < 10 ? "0" + segundos : segundos;

                if (timerDisplay) {{
                    timerDisplay.innerText = minStr + ":" + secStr;
                }}

                if (totalSeconds <= 300 && totalSeconds > 0) {{
                    if (timerDisplay) timerDisplay.style.color = "#ef4444";
                    if (boxDisplay) boxDisplay.style.border = "1px solid rgba(239, 68, 68, 0.5)";
                }}

                if (totalSeconds <= 0) {{
                    if (timerDisplay) {{
                        timerDisplay.innerText = "Expirada";
                        timerDisplay.style.color = "#ef4444";
                    }}
                    if (iconDisplay) iconDisplay.innerText = "⚠️";
                    return;
                }}

                totalSeconds--;
                setTimeout(atualizarContagem, 1000);
            }}

            atualizarContagem();
        }})();
    </script>
    """
    components.html(html_relogio, height=0, width=0)

def auto_salvar_rascunho_escala_supabase(usuario_id):
    """Salva automaticamente o progresso da escala no Supabase."""
    if not supabase or not usuario_id or usuario_id == "default_user":
        return
    try:
        now_iso = datetime.datetime.now().isoformat()
        estado_escala = {
            "grade_escala_lancamentos": st.session_state.get("grade_escala_lancamentos", {}),
            "militares_selecionados_ids": st.session_state.get("militares_selecionados_ids", []),
            "afastamentos_militares": st.session_state.get("afastamentos_militares", []),
            "subunidade": st.session_state.get("cfg_subunidade", "")
        }
        
        payload = {
            "usuario_id": str(usuario_id),
            "estado_json": json.dumps(estado_escala, ensure_ascii=False),
            "ultima_atividade": now_iso
        }
        
        supabase.table("escalas_sessao_rascunho").upsert(payload, on_conflict="usuario_id").execute()
    except Exception:
        pass

def restaurar_rascunho_escala_supabase(usuario_id):
    """Restaura os dados do rascunho de onde o operador parou."""
    if not supabase or not usuario_id or st.session_state.get("escala_restaurada", False):
        return
    try:
        res = supabase.table("escalas_sessao_rascunho").select("*").eq("usuario_id", str(usuario_id)).execute()
        if res.data and len(res.data) > 0:
            rec = res.data[0]
            estado = json.loads(rec.get("estado_json", "{}"))
            
            if estado.get("grade_escala_lancamentos"):
                st.session_state["grade_escala_lancamentos"] = estado["grade_escala_lancamentos"]
            if estado.get("militares_selecionados_ids"):
                st.session_state["militares_selecionados_ids"] = estado["militares_selecionados_ids"]
            if estado.get("afastamentos_militares"):
                st.session_state["afastamentos_militares"] = estado["afastamentos_militares"]
            
            st.toast("🔄 Rascunho da escala anterior restaurado!", icon="ℹ️")
    except Exception:
        pass
    finally:
        st.session_state["escala_restaurada"] = True

def gerenciar_timeout_sessao():
    """Controla a inatividade de 20 minutos usando Epoch Timestamp (imune a fuso horário)."""
    if not st.session_state.get("autenticado", False):
        return

    usr_logado = st.session_state.get("usuario_dados", {})
    usr_id = str(usr_logado.get("id") or usr_logado.get("usuario_login") or "").strip()
    now_ts = time.time()

    ultima_ts = st.session_state.get("ultima_atividade_ts")

    if ultima_ts is not None:
        tempo_inativo_seg = now_ts - ultima_ts
        
        if tempo_inativo_seg >= TEMPO_TIMEOUT_SEGUNDOS:
            if usr_id:
                auto_salvar_rascunho_escala_supabase(usr_id)
            
            # Limpa sessão
            st.session_state["autenticado"] = False
            st.session_state["usuario_autenticado"] = False
            st.session_state["mfa_pendente"] = False
            st.session_state["mfa_setup_mode"] = False
            st.session_state["usuario_dados"] = {}
            st.session_state["token_sessao_local"] = None
            st.session_state["escala_restaurada"] = False
            st.session_state["ultima_atividade_ts"] = None
            
            st.error("⌛ Sua sessão expirou por inatividade (20 min). Seu rascunho foi salvo automaticamente!")
            time.sleep(2)
            st.rerun()

    st.session_state["ultima_atividade_ts"] = now_ts

    # Exibe o relógio flutuante se estiver autenticado
    renderizar_relogio_sessao(tempo_minutos=20)
    
    # Salva o progresso
    if usr_id:
        auto_salvar_rascunho_escala_supabase(usr_id)