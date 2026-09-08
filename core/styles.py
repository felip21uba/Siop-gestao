import streamlit as st

def aplicar_estilo_visual():
    """Aplica o tema visual (DARK ou LIGHT) configurado na sessão do Streamlit"""
    if "tema_visual" not in st.session_state:
        st.session_state["tema_visual"] = "DARK"

    if st.session_state["tema_visual"] == "DARK":
        bg_cor, form_bg, text_cor, border_cor = "#0f172a", "#1e293b", "#f8fafc", "#4E442A"
        sec_bg, sec_text, sec_border = "#9D8B5C", "#000000", "#4E442A"  # Bege / Marrom claro
        pri_bg, pri_text, pri_border = "#4E442A", "#ffffff", "#9D8B5C"  # Marrom escuro
        expander_bg, input_bg, input_text, sidebar_bg = "#1e293b", "#0f172a", "#f8fafc", "#1e293b"
    else:
        bg_cor, form_bg, text_cor, border_cor = "#f1f5f9", "#ffffff", "#0f172a", "#cbd5e1"
        sec_bg, sec_text, sec_border = "#e2e8f0", "#1e293b", "#94a3b8"
        pri_bg, pri_text, pri_border = "#1e293b", "#ffffff", "#0f172a"
        expander_bg, input_bg, input_text, sidebar_bg = "#e2e8f0", "#ffffff", "#0f172a", "#ffffff"

    st.markdown(f"""
        <style>
            /* ESTILOS GERAIS DA APLICAÇÃO */
            .stApp {{ background-color: {bg_cor} !important; color: {text_cor} !important; }}
            section[data-testid="stSidebar"] {{ background-color: {sidebar_bg} !important; border-right: 1px solid {border_cor} !important; }}
            section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] div {{ color: {text_cor} !important; }}
            
            div[data-testid="stExpander"] {{ background-color: {form_bg} !important; border: 1px solid {border_cor} !important; border-radius: 8px !important; }}
            div[data-testid="stExpander"] summary, div[data-testid="stExpander"] details summary, div[data-testid="stExpander"] header {{ background-color: {expander_bg} !important; color: {text_cor} !important; }}
            
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
            /* 🎯 PADRONIZAÇÃO DE BOTÕES (SEM CORTAR TEXTO E SEM VERMELHO)        */
            /* ----------------------------------------------------------------- */
            .stButton > button {{
                min-height: 42px !important;
                height: auto !important; /* Permite que o botão cresça para caber 2 linhas */
                padding: 8px 10px !important;
                border-radius: 8px !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                box-sizing: border-box !important;
                margin: 0 !important;
                transition: all 0.2s ease !important;
            }}

            .stButton > button p {{
                font-size: 0.92rem !important;
                font-weight: 700 !important;
                line-height: 1.2 !important;
                margin: 0 !important;
                white-space: normal !important; /* Permite quebrar linha (remove reticências) */
                word-break: break-word !important;
                text-align: center !important;
            }}

            /* Estado Padrão (Secundário / Desmarcado) - Bege */
            .stButton > button[kind="secondary"] {{
                background-color: {sec_bg} !important;
                border: 2px solid {sec_border} !important;
                color: {sec_text} !important;
            }}
            .stButton > button[kind="secondary"] p {{ color: {sec_text} !important; }}

            /* Estado Selecionado (Primário / Marcado) - Marrom Escuro (ELIMINA O VERMELHO) */
            .stButton > button[kind="primary"], 
            .stButton > button[data-testid="stBaseButton-primary"],
            .stFormSubmitButton > button {{
                background-color: {pri_bg} !important;
                border: 2px solid {pri_border} !important;
                color: {pri_text} !important;
                box-shadow: 0px 2px 6px rgba(0, 0, 0, 0.2) !important;
            }}
            .stButton > button[kind="primary"] p, 
            .stButton > button[data-testid="stBaseButton-primary"] p,
            .stFormSubmitButton > button p {{ color: {pri_text} !important; }}

            /* Efeitos de Hover */
            .stButton > button[kind="secondary"]:hover {{
                background-color: {pri_bg} !important;
                border-color: {pri_border} !important;
            }}
            .stButton > button[kind="secondary"]:hover p {{ color: {pri_text} !important; }}

            .stButton > button[kind="primary"]:hover,
            .stButton > button[data-testid="stBaseButton-primary"]:hover {{
                background-color: {sec_bg} !important;
                border-color: {sec_border} !important;
            }}
            .stButton > button[kind="primary"]:hover p,
            .stButton > button[data-testid="stBaseButton-primary"]:hover p {{ color: {sec_text} !important; }}

            /* ----------------------------------------------------------------- */
            /* MULTISELECT, DROPDOWNS E TOGGLES (SEM COR VERMELHA)               */
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

            div[data-baseweb="tag"] {{
                background-color: {pri_bg} !important; 
                border: 1px solid {pri_border} !important;
                border-radius: 4px !important;
                padding: 2px 6px !important;
                margin: 2px !important;
            }}
            div[data-baseweb="tag"] span {{
                color: {pri_text} !important;
                background-color: transparent !important;
                font-weight: 700 !important;
                font-size: 0.85rem !important;
            }}
            div[data-baseweb="tag"] [role="presentation"] {{ background-color: transparent !important; }}
            div[data-baseweb="tag"] svg {{ fill: {pri_text} !important; }}

            /* Toggle Switch (Chavezinha) */
            div[data-testid="stToggle"] span[aria-checked="true"] {{
                background-color: {sec_bg} !important;
            }}

            /* ----------------------------------------------------------------- */
            /* CARDS DO PASSO 3 (HTML CUSTOMIZADO)                               */
            /* ----------------------------------------------------------------- */
            .card-militar-item {{
                background-color: {sec_bg} !important; /* Retorna à cor Bege original */
                color: {sec_text} !important;
                border: 2px solid {sec_border} !important;
                padding: 8px 10px !important;
                border-radius: 8px !important;
                text-align: center !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
                align-items: center !important;
                min-height: 58px !important;
                height: auto !important;
                position: relative !important;
                cursor: pointer !important;
                box-sizing: border-box !important;
                transition: all 0.2s ease !important;
            }}

            .card-militar-item.selecionado,
            .card-militar-item[data-selected="true"] {{
                background-color: {pri_bg} !important;
                border-color: {pri_border} !important;
                color: {pri_text} !important;
            }}

            .card-militar-item .grad-nome {{
                font-size: 0.88rem !important;
                line-height: 1.15 !important;
                text-transform: uppercase !important;
                font-weight: 700 !important;
                color: inherit !important;
                white-space: normal !important;
                word-break: break-word !important;
            }}

            .card-militar-item .num-pm {{
                font-size: 0.75rem !important;
                font-weight: 600 !important;
                opacity: 0.8 !important;
                margin-top: 3px !important;
                display: block !important;
            }}

            /* Tooltip de 3 segundos */
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
                font-size: 0.80rem;
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