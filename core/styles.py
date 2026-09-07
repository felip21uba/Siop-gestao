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
            .stApp {{ background-color: {bg_cor} !important; color: {text_cor} !important; }}
            section[data-testid="stSidebar"] {{ background-color: {sidebar_bg} !important; border-right: 1px solid {border_cor} !important; }}
            section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] div {{ color: {text_cor} !important; }}
            div[data-testid="stExpander"] {{ background-color: {form_bg} !important; border: 1px solid {border_cor} !important; border-radius: 8px !important; }}
            div[data-testid="stExpander"] summary, div[data-testid="stExpander"] details summary, div[data-testid="stExpander"] header {{ background-color: {expander_bg} !important; color: {text_cor} !important; }}
            div[data-baseweb="input"], div[data-baseweb="select"] > div {{ background-color: {input_bg} !important; color: {input_text} !important; border: 1px solid {border_cor} !important; border-radius: 6px !important; }}
            div[data-baseweb="input"] input, div[data-baseweb="select"] span {{ color: {input_text} !important; }}
            .stForm, div[data-testid="stForm"] {{ background-color: {form_bg} !important; border: 2px solid {border_cor} !important; border-radius: 12px !important; padding: 20px !important; }}
            .stForm label, p, h1, h2, h3, h4, h5, h6, span, label {{ color: {text_cor} !important; }}
            div[data-testid="stColumn"] button[kind="secondary"], div[data-testid="stElementContainer"] button[kind="secondary"] {{ background-color: {sec_bg} !important; border: 1px solid {sec_border} !important; opacity: 1 !important; }}
            div[data-testid="stColumn"] button[kind="secondary"] p, div[data-testid="stElementContainer"] button[kind="secondary"] p {{ color: {sec_text} !important; font-weight: 700 !important; }}
            div[data-testid="stColumn"] button[kind="primary"], div[data-testid="stElementContainer"] button[kind="primary"], .stFormSubmitButton > button {{ background-color: {pri_bg} !important; border: 2px solid {pri_border} !important; box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.15) !important; opacity: 1 !important; }}
            div[data-testid="stColumn"] button[kind="primary"] p, div[data-testid="stElementContainer"] button[kind="primary"] p, .stFormSubmitButton > button p {{ color: {pri_text} !important; font-weight: 800 !important; }}
            div[data-testid="stColumn"] button[kind="primary"]:hover, .stFormSubmitButton > button:hover {{ background-color: {sec_bg} !important; }}

            /* ----------------------------------------------------------------- */
            /* 🪖 CORREÇÃO VISUAL DOS CARDS DE MILITARES (PASSO 3 E SELEÇÕES)    */
            /* ----------------------------------------------------------------- */
            .grid-efetivo {{
                display: grid !important;
                grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)) !important;
                gap: 10px !important;
                margin-top: 10px !important;
                margin-bottom: 15px !important;
            }}

            .card-militar-item, div[data-testid="stColumn"] button {{
                background-color: #a38f51 !important;
                color: #0f172a !important;
                padding: 8px 10px !important;
                border-radius: 8px !important;
                text-align: center !important;
                font-weight: 700 !important;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.25) !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
                align-items: center !important;
                min-height: 58px !important;
                height: auto !important;
                white-space: normal !important;
                word-break: break-word !important;
                overflow: visible !important;
            }}

            /* Força a quebra de linha dos textos de botões/cards sem truncar com '...' */
            div[data-testid="stColumn"] button p, 
            div[data-testid="stElementContainer"] button p,
            .card-militar-item p,
            .card-militar-item span {{
                white-space: normal !important;
                word-break: break-word !important;
                text-overflow: unset !important;
                overflow: visible !important;
                line-height: 1.25 !important;
                font-size: 0.82rem !important;
            }}

            .card-militar-item .grad-nome {{
                font-size: 0.82rem !important;
                line-height: 1.15 !important;
                text-transform: uppercase !important;
                color: #0f172a !important;
                word-wrap: break-word !important;
            }}

            .card-militar-item .num-pm {{
                font-size: 0.72rem !important;
                font-weight: 600 !important;
                color: #1e293b !important;
                margin-top: 3px !important;
                display: block !important;
            }}

            /* ----------------------------------------------------------------- */
            /* 🎯 AJUSTE DE TAMANHO DOS BOTÕES DE DROPDOWN (MULTISELECT/SELECT)  */
            /* ----------------------------------------------------------------- */
            div[data-baseweb="select"] div[role="button"],
            div[data-baseweb="select"] [data-testid="stBaseButton-secondary"],
            div[data-baseweb="select"] button {{
                background-color: transparent !important;
                border: none !important;
                height: auto !important;
                min-height: unset !important;
                max-height: 38px !important;
                padding: 0 8px !important;
                margin: 0 !important;
                box-shadow: none !important;
                border-radius: 0 !important;
            }}

            div[data-baseweb="select"] svg {{
                width: 16px !important;
                height: 16px !important;
                fill: #c5a059 !important;
            }}
        </style>
    """, unsafe_allow_html=True)