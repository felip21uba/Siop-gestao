import streamlit as st
import time
import datetime
import json
import streamlit.components.v1 as components
from core.database import supabase

TEMPO_TIMEOUT_SEGUNDOS = 20 * 60

def renderizar_relogio_sessao(tempo_minutos=20):
    """Renderiza o relógio na sidebar e reinicia a contagem a cada clique do usuário."""
    tempo_segundos = tempo_minutos * 60
    ts_atual = time.time()
    
    html_relogio = f"""
    <!-- timestamp: {ts_atual} -->
    <div id="badge-sessao-box" style="
        background-color: #1e293b;
        color: #ffffff;
        padding: 8px 12px;
        border-radius: 8px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 13px;
        font-weight: 600;
        border: 1px solid #334155;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        margin-bottom: 10px;
    ">
        <div style="display: flex; align-items: center; gap: 6px;">
            <span id="sessao-icon" style="font-size: 14px;">⏱️</span>
            <span style="color: #94a3b8;">Sessão:</span>
        </div>
        <span id="sessao-timer" style="font-family: monospace; font-size: 14px; font-weight: bold; color: #38bdf8;">20:00</span>
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
                    if (boxDisplay) boxDisplay.style.borderColor = "rgba(239, 68, 68, 0.6)";
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
    with st.sidebar:
        components.html(html_relogio, height=48)

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
    """Controla a inatividade. Qualquer clique reseta o timer para 20 min."""
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

    # Atualiza o timestamp de ultima atividade a cada interacao
    st.session_state["ultima_atividade_ts"] = now_ts

    # Renderiza o relogio que reseta visualmente para 20:00
    renderizar_relogio_sessao(tempo_minutos=20)
    
    if usr_id:
        auto_salvar_rascunho_escala_supabase(usr_id)