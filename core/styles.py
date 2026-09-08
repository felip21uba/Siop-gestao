import streamlit as st

def aplicar_estilo_visual():
    """Aplica o tema visual (DARK ou LIGHT) configurado na sessão do Streamlit"""
    if "tema_visual" not in st.session_state:
        st.session_state["tema_visual"] = "DARK"

    if st.session_state["tema_visual"] == "DARK":
        bg_cor, form_bg, text_cor, border_cor = "#0f172a", "#1e293b", "#f8fafc", "#4E442A"
        sec_bg, sec_text, sec_border = "#9D8B5C", "#000000", "#4E442A"
        pri_bg, pri_text, pri_border = "#4E442A", "#ffffff", "#9D8B5C"
        expander_bg, input_bg, input_text, sidebar_bg = "#1e293b", "#0f172a", "#f8fafc", "#1e293b"
    else:
        bg_cor, form_bg, text_cor, border_cor = "#f1f5f9", "#ffffff", "#0f172a", "#cbd5e1"
        sec_bg, sec_text, sec_border = "#e2e8f0", "#1e293b", "#94a3b8"
        pri_bg, pri_text, pri_border = "#1e293b", "#ffffff", "#0f172a"
        expander_bg, input_bg, input_text, sidebar_bg = "#e2e8f0", "#ffffff", "#0f172a", "#ffffff"

    st.markdown(f"""
        <style>
            /* ESTILOS GERAIS */
            .stApp {{ background-color: {bg_cor} !important; color: {text_cor} !important; }}
            section[data-testid="stSidebar"] {{ background-color: {sidebar_bg} !important; border-right: 1px solid {border_cor} !important; }}
            section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] div {{ color: {text_cor} !important; }}
            
            div[data-testid="stExpander"] {{ background-color: {form_bg} !important; border: 1px solid {border_cor} !important; border-radius: 8px !important; }}
            div[data-testid="stExpander"] summary, div[data-testid="stExpander"] details summary, div[data-testid="stExpander"] header {{ background-color: {expander_bg} !important; color: {text_cor} !important; }}
            
            /* CAIXAS DE ENTRADA (INPUT) */
            div[data-baseweb="input"], div[data-baseweb="select"] > div {{ 
                background-color: {input_bg} !important; 
                color: {input_text} !important; 
                border: 1px solid {border_cor} !important; 
                border-radius: 6px !important; 
            }}
            div[data-baseweb="input"] input, div[data-baseweb="select"] span {{ color: {input_text} !important; }}
            
            .stForm, div[data-testid="stForm"] {{ background-color: {form_bg} !important; border: 2px solid {border_cor} !important; border-radius: 12px !important; padding: 20px !important; }}
            .stForm label, p, h1, h2, h3, h4, h5, h6, span, label {{ color: {text_cor} !important; }}

            /* ----------------------------------------------------------------- */
            /* BOTÕES GERAIS DO SISTEMA                                          */
            /* ----------------------------------------------------------------- */
            .stButton > button[kind="secondary"] {{ background-color: {sec_bg} !important; border: 1px solid {sec_border} !important; opacity: 1 !important; }}
            .stButton > button[kind="secondary"] p {{ color: {sec_text} !important; font-weight: 700 !important; }}
            
            .stButton > button[kind="primary"], .stFormSubmitButton > button {{ background-color: {pri_bg} !important; border: 2px solid {pri_border} !important; box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.15) !important; opacity: 1 !important; }}
            .stButton > button[kind="primary"] p, .stFormSubmitButton > button p {{ color: {pri_text} !important; font-weight: 800 !important; }}
            
            .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover {{ background-color: {sec_bg} !important; }}

            /* ----------------------------------------------------------------- */
            /* 1. ISOLAMENTO DAS CAIXAS DE SELEÇÃO E DROPDOWNS (NÃO AFETADOS)    */
            /* ----------------------------------------------------------------- */
            div[data-baseweb="select"] button,
            div[data-baseweb="select"] [role="button"],
            div[data-baseweb="select"] div[data-testid="stBaseButton-secondary"] {{
                background-color: transparent !important;
                border: none !important;
                box-shadow: none !important;
                height: 100% !important;
                min-height: unset !important;
                padding: 0 6px !important;
                margin: 0 !important;
                border-radius: 0 !important;
            }}
            
            div[data-baseweb="select"] svg {{
                width: 18px !important;
                height: 18px !important;
                fill: {sec_bg} !important; 
            }}

            /* TAGS DO MULTISELECT */
            div[data-baseweb="tag"] {{
                background-color: #ef4444 !important; 
                border: none !important;
                border-radius: 4px !important;
                padding: 2px 4px !important;
                margin: 2px 4px 2px 0 !important;
            }}
            div[data-baseweb="tag"] span {{
                color: white !important;
                background-color: transparent !important;
                font-weight: 600 !important;
            }}
            div[data-baseweb="tag"] [role="presentation"] {{
                background-color: transparent !important; 
                border-radius: 0 !important;
            }}
            div[data-baseweb="tag"] svg {{ fill: white !important; }}

            /* ----------------------------------------------------------------- */
            /* 2. CARDS DO PASSO 3 (MILITARES) - MARROM PADRÃO E QUEBRA DE LINHA */
            /* ----------------------------------------------------------------- */
            .grid-efetivo {{
                display: grid !important;
                grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)) !important;
                gap: 10px !important;
                margin-top: 10px !important;
                margin-bottom: 15px !important;
            }}

            /* Formata os botões dentro de colunas (Passo 3) e o HTML dos cards */
            .card-militar-item, 
            div[data-testid="stColumn"] button[kind="secondary"] {{
                background-color: {sec_bg} !important;
                color: {sec_text} !important;
                border: 1px solid {sec_border} !important;
                padding: 8px 10px !important;
                border-radius: 8px !important;
                text-align: center !important;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.25) !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
                align-items: center !important;
                min-height: 58px !important;
                height: auto !important;
                position: relative !important;
                cursor: pointer !important;
            }}

            /* Força o texto (Graduação + Nome \n Número) a quebrar linha e centralizar */
            .card-militar-item p,
            div[data-testid="stColumn"] button[kind="secondary"] p {{
                white-space: normal !important;
                word-break: break-word !important;
                line-height: 1.25 !important;
                font-size: 0.82rem !important;
                color: {sec_text} !important;
                font-weight: 700 !important;
                margin: 0 !important;
            }}

            /* Estilos específicos para quando o card é montado em HTML */
            .card-militar-item .grad-nome {{
                font-size: 0.82rem !important;
                line-height: 1.15 !important;
                text-transform: uppercase !important;
                color: {sec_text} !important;
                font-weight: 700 !important;
            }}

            .card-militar-item .num-pm {{
                font-size: 0.72rem !important;
                font-weight: 600 !important;
                color: rgba(0,0,0,0.7) !important; /* Tom um pouco mais escuro para diferenciar o número */
                margin-top: 3px !important;
                display: block !important;
            }}

            /* Efeito Hover Escurecido */
            .card-militar-item:hover,
            div[data-testid="stColumn"] button[kind="secondary"]:hover {{
                background-color: #8a7a51 !important; 
            }}

            /* Tooltip de 3 segundos (Aparece ao repousar o mouse) */
            .card-militar-item[data-nome]:hover::after {{
                content: attr(data-nome);
                position: absolute;
                bottom: 108%;
                left: 50%;
                transform: translateX(-50%);
                background-color: #0f172a;
                color: #f8fafc;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 0.78rem;
                font-weight: 600;
                white-space: nowrap;
                box-shadow: 0px 4px 12px rgba(0,0,0,0.5);
                border: 1px solid {sec_bg};
                z-index: 9999;
                pointer-events: none;
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s ease 3s, visibility 0.3s ease 3s; 
            }}

            .card-militar-item[data-nome]:hover::after {{
                opacity: 1;
                visibility: visible;
            }}
        </style>
    """, unsafe_allow_html=True)