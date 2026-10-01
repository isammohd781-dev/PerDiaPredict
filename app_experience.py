"""Application styling and review-before-action dialogs."""


def confirm_action(title, message, action, details=None):
    import streamlit as st
    st.session_state['_pending_confirmation'] = (title, message, action, details)
    st.rerun()


def render_confirmation():
    import streamlit as st
    pending = st.session_state.get('_pending_confirmation')
    if not pending:
        return
    title, message, action, details = pending
    @st.dialog(title, dismissible=False)
    def review():
        st.write(message)
        if details:
            with st.container(border=True):
                for label, value in details.items():
                    st.markdown('**' + label + '**')
                    st.write(value)
        a, b = st.columns(2)
        if a.button('Confirm', type='primary', use_container_width=True):
            try:
                action()
            except (ValueError, PermissionError, RuntimeError) as exc:
                st.error(str(exc))
            else:
                st.session_state.pop('_pending_confirmation', None)
                st.session_state['_ux_notice'] = 'Confirmed.'
                st.rerun()
        if b.button('Cancel', use_container_width=True):
            st.session_state.pop('_pending_confirmation', None)
            st.rerun()
    review()


def inject_experience():
    import streamlit as st
    st.markdown('''<style>
    .block-container {max-width:1120px;padding-top:2rem;padding-bottom:2rem;}
    h1 {font-size:2rem!important;letter-spacing:-.035em;}
    h2,h3 {letter-spacing:-.02em;}
    div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:20px!important;}
    button {border-radius:12px!important;transition:transform .15s ease,box-shadow .15s ease;}
    button:hover {transform:translateY(-1px);box-shadow:0 5px 18px #0891b222;}
    div[data-testid="stMetric"] {padding:18px;border:1px solid #94a3b833;border-radius:16px;background:#0891b20a;}
    div[data-testid="stAlert"] {border-radius:14px;}
    .ux-hero {padding:24px;border:1px solid #38bdf844;border-radius:22px;background:linear-gradient(115deg,#0891b222,#6366f115);margin:0 0 20px;}
    .ux-hero h2 {margin:0;font-size:1.65rem;}.ux-hero p {margin:8px 0 0;opacity:.8;}
    @media(max-width:640px){.block-container{padding:1rem;}h1{font-size:1.6rem!important;}button:hover{transform:none;}}
    @media(prefers-reduced-motion:reduce){button{transition:none;}button:hover{transform:none;}}
    </style>''', unsafe_allow_html=True)
    if st.session_state.get('_ux_notice'):
        st.toast(st.session_state.pop('_ux_notice'))
