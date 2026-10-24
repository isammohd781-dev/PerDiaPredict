"""Browser colour-scheme hint for the chosen appearance. All other styling lives in theme.py."""


def inject_visual_accessibility():
    import streamlit as st
    dark = st.session_state.get('dark_mode', False)
    # 'only light' stops automatic browser darkening in light mode; forced-colour modes still apply.
    scheme = 'dark' if dark else 'only light'
    st.markdown(f'''<style>
    :root, html, body, #root, .stApp, [data-baseweb="popover"] {{color-scheme:{scheme}!important;}}
    .stApp :is(input,textarea,select,button) {{color-scheme:{scheme}!important;}}
    </style>''', unsafe_allow_html=True)
