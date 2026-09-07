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
        </style>
    """, unsafe_allow_html=True)