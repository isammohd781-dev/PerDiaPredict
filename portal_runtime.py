"""Role is fixed by the entry script, never by a browser query parameter."""
import time

import streamlit as st

IDLE_MINUTES = 30

PAGES = {
    'patient': {'auth', 'login', 'register', 'main', 'patient_history', 'patient_care', 'profile_edit', 'splash'},
    'doctor': {'doctor_login', 'doctor_register', 'doctor_dashboard'},
    'admin': {'admin'},
}
ENTRY = {'patient': 'auth', 'doctor': 'doctor_login', 'admin': 'admin'}
COMMON = {'program_policy', 'privacy_policy', 'language'}


def initialise(role):
    if role not in PAGES:
        raise ValueError('Unknown application role')
    own = {'patient':'user', 'doctor':'doctor_user', 'admin':'admin_ok'}[role]
    foreign = any(st.session_state.get(key) for key in ('user','doctor_user','admin_ok') if key != own)
    if st.session_state.get('_fixed_role') not in (None, role) or foreign:
        retained = {k: st.session_state.get(k) for k in ('lang','dark_mode') if k in st.session_state}
        st.session_state.clear()
        st.session_state.update(retained)
        st.session_state['page'] = ENTRY[role]
    st.session_state['_fixed_role'] = role
    st.session_state.setdefault('page', ENTRY[role])
    # Legacy links cannot select another role on this application.
    for key in ('portal', 'role', 'page'):
        st.query_params.pop(key, None)


def enforce(role):
    page = st.session_state.get('page', ENTRY[role])
    if page not in PAGES[role] | COMMON:
        st.session_state.pop('_pending_confirmation', None)
        st.session_state.pop('_disclosure_grant', None)
        st.session_state['page'] = ENTRY[role]
        st.rerun()
    if role == 'patient' and page in {'main','patient_history','patient_care','profile_edit'} and not st.session_state.get('user'):
        st.session_state['page'] = ENTRY[role]
        st.rerun()
    if role == 'doctor' and page == 'doctor_dashboard' and not st.session_state.get('doctor_user'):
        st.session_state['page'] = ENTRY[role]
        st.rerun()


def expire_idle(role, minutes=IDLE_MINUTES):
    """Sign out a session left untouched for `minutes` (shared or unattended computers)."""
    now = time.time()
    last = st.session_state.get('_last_activity')
    signed_in = any(st.session_state.get(key) for key in ('user', 'doctor_user', 'admin_ok'))
    if signed_in and last is not None and now - last > minutes * 60:
        retained = {k: st.session_state.get(k) for k in ('lang', 'dark_mode') if k in st.session_state}
        st.session_state.clear()
        st.session_state.update(retained)
        st.session_state['_fixed_role'] = role
        st.session_state['page'] = ENTRY[role]
        st.session_state['_ux_notice'] = 'You were signed out after %d minutes without activity.' % minutes
    st.session_state['_last_activity'] = now
