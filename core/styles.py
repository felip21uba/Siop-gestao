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
            /* 🪖 CORREÇÃO DEFINITIVA DOS CARDS DE MILITARES (FUNDO BEGE)        */
            /* ----------------------------------------------------------------- */
            .card-militar-item,
            div[data-testid="stColumn"] button,
            div[data-testid="stColumn"] button[kind="secondary"],
            div[data-testid="stColumn"] button[data-testid="stBaseButton-secondary"] {{
                background-color: {sec_bg} !important;
                color: {sec_text} !important;
                border: 2px solid {sec_border} !important;
                border-radius: 8px !important;
                padding: 8px 10px !important;
                text-align: center !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
                align-items: center !important;
                min-height: 58px !important;
                height: auto !important;
                box-sizing: border-box !important;
                position: relative !important;
                cursor: pointer !important;
                transition: background-color 0.2s ease, border-color 0.2s ease !important;
            }}

            /* Força o texto interno dos cards a ser preto e quebrar linha em 2 linhas */
            .card-militar-item p,
            .card-militar-item span,
            div[data-testid="stColumn"] button p,
            div[data-testid="stColumn"] button span {{
                color: {sec_text} !important;
                font-weight: 700 !important;
                white-space: normal !important;
                word-break: break-word !important;
                line-height: 1.25 !important;
                font-size: 0.85rem !important;
                margin: 0 !important;
                text-align: center !important;
            }}

            .card-militar-item .num-pm {{
                font-size: 0.75rem !important;
                opacity: 0.8 !important;
                margin-top: 3px !important;
                display: block !important;
            }}

            /* Card Selecionado / Pressionado (Alterna para Marrom Escuro) */
            .card-militar-item.selecionado,
            div[data-testid="stColumn"] button[kind="primary"],
            div[data-testid="stColumn"] button[data-testid="stBaseButton-primary"] {{
                background-color: {pri_bg} !important;
                border-color: {pri_border} !important;
            }}
            .card-militar-item.selecionado p,
            div[data-testid="stColumn"] button[kind="primary"] p {{
                color: {pri_text} !important;
            }}

            /* ----------------------------------------------------------------- */
            /* ⏱️ TOOLTIP DOS CARDS: AGUARDA EXATOS 3 SEGUNDOS DE HOVER         */
            /* ----------------------------------------------------------------- */
            .card-militar-item[data-nome]::after {{
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
                transition: opacity 0.2s ease 0s, visibility 0.2s ease 0s; 
            }}

            .card-militar-item[data-nome]:hover::after {{
                opacity: 1;
                visibility: visible;
                transition: opacity 0.3s ease 3s, visibility 0.3s ease 3s; 
            }}

            /* ----------------------------------------------------------------- */
            /* BOTÕES DE FORMULÁRIO E AÇÕES DIVERSAS                              */
            /* ----------------------------------------------------------------- */
            .stButton > button {{
                min-height: 42px !important;
                height: auto !important;
                padding: 8px 18px !important;
                border-radius: 8px !important;
            }}

            /* ----------------------------------------------------------------- */
            /* DROPDOWNS E MULTISELECT (SEM BLOCOS VERMELHOS E SEM VAZAMENTOS)   */
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

            div[data-testid="stToggle"] span[aria-checked="true"] {{
                background-color: {sec_bg} !important;
            }}
        </style>
    """, unsafe_allow_html=True)