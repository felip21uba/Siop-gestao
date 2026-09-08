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
            /* ================================================================= */
            /* 1. ESTILOS GERAIS DA APLICAÇÃO                                   */
            /* ================================================================= */
            .stApp {{ background-color: {bg_cor} !important; color: {text_cor} !important; }}
            section[data-testid="stSidebar"] {{ background-color: {sidebar_bg} !important; border-right: 1px solid {border_cor} !important; }}
            section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] div {{ color: {text_cor} !important; }}
            
            div[data-testid="stExpander"] {{ background-color: {form_bg} !important; border: 1px solid {border_cor} !important; border-radius: 8px !important; }}
            div[data-testid="stExpander"] summary, div[data-testid="stExpander"] details summary, div[data-testid="stExpander"] header {{ background-color: {expander_bg} !important; color: {text_cor} !important; }}
            
            .stForm, div[data-testid="stForm"] {{ background-color: {form_bg} !important; border: 2px solid {border_cor} !important; border-radius: 12px !important; padding: 20px !important; }}
            .stForm label, p, h1, h2, h3, h4, h5, h6, span, label {{ color: {text_cor} !important; }}

            /* ================================================================= */
            /* 2. ESTILIZAÇÃO COMPLETA DE CARDS E BOTÕES (PASSO 3 E PASSO 4)    */
            /* ================================================================= */
            div[data-testid="stButton"] > button,
            button[data-testid="stBaseButton-secondary"],
            button[data-testid="stBaseButton-primary"],
            .stFormSubmitButton > button {{
                min-height: 48px !important;
                height: auto !important;
                padding: 8px 10px !important;
                border-radius: 8px !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                box-sizing: border-box !important;
                margin: 0 !important;
                transition: all 0.2s ease !important;
            }}

            div[data-testid="stButton"] > button p,
            button[data-testid="stBaseButton-secondary"] p,
            button[data-testid="stBaseButton-primary"] p,
            .stFormSubmitButton > button p {{
                font-size: 0.88rem !important;
                font-weight: 700 !important;
                line-height: 1.25 !important;
                margin: 0 !important;
                white-space: pre-wrap !important;
                word-break: break-word !important;
                text-align: center !important;
            }}

            /* ESTADO SECUNDÁRIO / DESMARCADO -> BEGE / MARROM CLARO (#9D8B5C) */
            div[data-testid="stButton"] > button[kind="secondary"],
            button[data-testid="stBaseButton-secondary"] {{
                background-color: {sec_bg} !important;
                border: 2px solid {sec_border} !important;
                color: {sec_text} !important;
            }}
            div[data-testid="stButton"] > button[kind="secondary"] p,
            button[data-testid="stBaseButton-secondary"] p {{ 
                color: {sec_text} !important; 
            }}

            /* ESTADO PRIMÁRIO / SELECIONADO -> MARROM ESCURO (#4E442A) */
            div[data-testid="stButton"] > button[kind="primary"], 
            button[data-testid="stBaseButton-primary"],
            .stFormSubmitButton > button {{
                background-color: {pri_bg} !important;
                border: 2px solid {pri_border} !important;
                color: {pri_text} !important;
                box-shadow: 0px 2px 6px rgba(0, 0, 0, 0.2) !important;
            }}
            div[data-testid="stButton"] > button[kind="primary"] p, 
            button[data-testid="stBaseButton-primary"] p,
            .stFormSubmitButton > button p {{ 
                color: {pri_text} !important; 
            }}

            /* EFEITOS DE HOVER (INVERSÃO SUAVE DE CORES) */
            div[data-testid="stButton"] > button[kind="secondary"]:hover,
            button[data-testid="stBaseButton-secondary"]:hover {{
                background-color: {pri_bg} !important;
                border-color: {pri_border} !important;
            }}
            div[data-testid="stButton"] > button[kind="secondary"]:hover p,
            button[data-testid="stBaseButton-secondary"]:hover p {{ 
                color: {pri_text} !important; 
            }}

            div[data-testid="stButton"] > button[kind="primary"]:hover,
            button[data-testid="stBaseButton-primary"]:hover,
            .stFormSubmitButton > button:hover {{
                background-color: {sec_bg} !important;
                border-color: {sec_border} !important;
            }}
            div[data-testid="stButton"] > button[kind="primary"]:hover p,
            button[data-testid="stBaseButton-primary"]:hover p,
            .stFormSubmitButton > button:hover p {{ 
                color: {sec_text} !important; 
            }}

            /* ================================================================= */
            /* 3. ISOLAMENTO RIGOROSO DE SELECTBOX, MULTISELECT E CAIXAS TEXTO   */
            /* ================================================================= */
            div[data-baseweb="input"] {{
                background-color: {input_bg} !important; 
                color: {input_text} !important; 
                border: 1px solid {border_cor} !important; 
                border-radius: 6px !important;
                min-height: 42px !important;
            }}
            div[data-baseweb="input"] input {{ 
                color: {input_text} !important; 
            }}

            div[data-baseweb="select"] > div {{
                background-color: {input_bg} !important;
                color: {input_text} !important;
                border: 1px solid {border_cor} !important;
                border-radius: 6px !important;
                min-height: 42px !important;
                height: auto !important;
            }}

            /* Anula qualquer interferência CSS dos botões internos do SelectBox */
            div[data-baseweb="select"] button,
            div[data-baseweb="select"] [role="button"] {{
                background-color: transparent !important;
                border: none !important;
                box-shadow: none !important;
                height: auto !important;
                min-height: unset !important;
                padding: 0 4px !important;
                margin: 0 !important;
            }}

            div[data-baseweb="select"] svg {{
                width: 18px !important;
                height: 18px !important;
                fill: {sec_bg} !important; 
            }}

            /* Tags Internas do Multiselect */
            div[data-baseweb="tag"] {{
                background-color: {pri_bg} !important; 
                border: 1px solid {pri_border} !important;
                border-radius: 4px !important;
                padding: 2px 6px !important;
                margin: 2px !important;
                height: auto !important;
            }}
            div[data-baseweb="tag"] span {{
                color: {pri_text} !important;
                background-color: transparent !important;
                font-weight: 700 !important;
                font-size: 0.82rem !important;
            }}
            div[data-baseweb="tag"] [role="presentation"] {{ 
                background-color: transparent !important; 
            }}
            div[data-baseweb="tag"] svg {{ 
                fill: {pri_text} !important; 
            }}

            /* Chave do Toggle Switch */
            div[data-testid="stToggle"] span[aria-checked="true"] {{
                background-color: {sec_bg} !important;
            }}

            /* ================================================================= */
            /* 4. REGRAS EXCLUSIVAS PARA CARDS HTML CUSTOMIZADOS                 */
            /* ================================================================= */
            .card-militar-item,
            .card-dia-item,
            .card-calendario-item,
            .card-passo3-item,
            .card-passo4-item {{
                background-color: {sec_bg} !important;
                color: {sec_text} !important;
                border: 2px solid {sec_border} !important;
                padding: 8px 10px !important;
                border-radius: 8px !important;
                text-align: center !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
                align-items: center !important;
                min-height: 52px !important;
                height: auto !important;
                position: relative !important;
                cursor: pointer !important;
                box-sizing: border-box !important;
                transition: all 0.2s ease !important;
            }}

            .card-militar-item.selecionado,
            .card-militar-item[data-selected="true"],
            .card-dia-item.selecionado,
            .card-dia-item[data-selected="true"],
            .card-calendario-item.selecionado,
            .card-calendario-item[data-selected="true"],
            .card-passo3-item.selecionado,
            .card-passo3-item[data-selected="true"],
            .card-passo4-item.selecionado,
            .card-passo4-item[data-selected="true"] {{
                background-color: {pri_bg} !important;
                border-color: {pri_border} !important;
                color: {pri_text} !important;
            }}

            .card-militar-item .grad-nome,
            .card-dia-item .grad-nome,
            .card-calendario-item .grad-nome {{
                font-size: 0.88rem !important;
                line-height: 1.15 !important;
                text-transform: uppercase !important;
                font-weight: 700 !important;
                color: inherit !important;
                white-space: normal !important;
                word-break: break-word !important;
            }}

            .card-militar-item .num-pm,
            .card-dia-item .num-pm,
            .card-calendario-item .num-pm {{
                font-size: 0.75rem !important;
                font-weight: 600 !important;
                opacity: 0.8 !important;
                margin-top: 3px !important;
                display: block !important;
            }}

            /* Tooltip: Invisível por padrão */
            .card-militar-item[data-nome]::after,
            .card-dia-item[data-nome]::after,
            .card-calendario-item[data-nome]::after {{
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

            /* Tooltip: Exibe após atraso no Hover */
            .card-militar-item[data-nome]:hover::after,
            .card-dia-item[data-nome]:hover::after,
            .card-calendario-item[data-nome]:hover::after {{
                opacity: 1;
                visibility: visible;
                transition: opacity 0.3s ease 3s, visibility 0.3s ease 3s; 
            }}
        </style>
    """, unsafe_allow_html=True)