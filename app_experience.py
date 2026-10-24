"""Application styling and review-before-action dialogs."""

_BUTTONS = {
    'en': ('Confirm', 'Cancel'), 'ar': ('تأكيد', 'إلغاء'), 'fr': ('Confirmer', 'Annuler'),
    'es': ('Confirmar', 'Cancelar'), 'de': ('Bestätigen', 'Abbrechen'), 'tr': ('Onayla', 'İptal'),
    'hi': ('पुष्टि करें', 'रद्द करें'), 'pt': ('Confirmar', 'Cancelar'), 'ru': ('Подтвердить', 'Отмена'),
    'zh': ('确认', '取消'),
}


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
        confirm_label, cancel_label = _BUTTONS.get(st.session_state.get('lang'), _BUTTONS['en'])
        a, b = st.columns(2)
        if a.button(confirm_label, type='primary', use_container_width=True):
            try:
                action()
            except (ValueError, PermissionError, RuntimeError) as exc:
                st.error(str(exc))
            else:
                st.session_state.pop('_pending_confirmation', None)
                st.session_state['_ux_notice'] = 'Confirmed.'
                st.rerun()
        if b.button(cancel_label, use_container_width=True):
            st.session_state.pop('_pending_confirmation', None)
            st.rerun()
    review()


def inject_experience():
    """Shows the one-off confirmation toast. Styling lives in theme.py."""
    import streamlit as st
    if st.session_state.get('_ux_notice'):
        st.toast(st.session_state.pop('_ux_notice'))
