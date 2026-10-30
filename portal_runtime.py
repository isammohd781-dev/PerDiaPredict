"""Role is fixed by the entry script, never by a browser query parameter."""
import time

import streamlit as st

# Every signed-in session (patient, doctor, admin) ends this many minutes after sign-in.
SESSION_MINUTES = 15
IDLE_MINUTES = SESSION_MINUTES  # kept for older imports

PAGES = {
    'patient': {'auth', 'login', 'register', 'main', 'patient_history', 'patient_care', 'profile_edit', 'splash', 'delete_account'},
    'doctor': {'doctor_login', 'doctor_register', 'doctor_dashboard'},
    'admin': {'admin'},
}
ENTRY = {'patient': 'auth', 'doctor': 'doctor_login', 'admin': 'admin'}
COMMON = {'program_policy', 'privacy_policy', 'language', 'splash'}
# Session keys kept when a session is reset (sign-out, timeout, role change).
KEEP_ON_RESET = ('lang', 'dark_mode', '_splash_seen')


def initialise(role):
    if role not in PAGES:
        raise ValueError('Unknown application role')
    own = {'patient':'user', 'doctor':'doctor_user', 'admin':'admin_ok'}[role]
    foreign = any(st.session_state.get(key) for key in ('user','doctor_user','admin_ok') if key != own)
    if st.session_state.get('_fixed_role') not in (None, role) or foreign:
        retained = {k: st.session_state.get(k) for k in KEEP_ON_RESET if k in st.session_state}
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


SIGNED_IN_KEYS = ('user', 'doctor_user', 'admin_ok')
SIGNED_OUT_NOTICE = 'Your session ended after %d minutes. Please sign in again.'


def _signed_in():
    return any(st.session_state.get(key) for key in SIGNED_IN_KEYS)


def _sign_out(role, minutes):
    retained = {k: st.session_state.get(k) for k in KEEP_ON_RESET if k in st.session_state}
    st.session_state.clear()
    st.session_state.update(retained)
    st.session_state['_fixed_role'] = role
    st.session_state['page'] = ENTRY[role]
    st.session_state['_ux_notice'] = SIGNED_OUT_NOTICE % minutes


def start_with_splash(role):
    """Show the logo screen before the first sign-in page of each app (patient, doctor, admin).

    It appears once per visit; a language change shows it again (restart_app clears the flag).
    Links that open a specific page (policy, account deletion, a sign-out reload) skip it."""
    if st.session_state.get('_splash_seen'):
        return
    st.session_state['_splash_seen'] = True
    direct_link = any(key in st.query_params for key in ('policy', 'account', 'expired'))
    if not direct_link and not _signed_in():
        st.session_state['page'] = 'splash'


def expire_idle(role, minutes=SESSION_MINUTES):
    """Fixed session length for patient, doctor and admin: signed out `minutes` after sign-in,
    whether or not the person is active. render_session_timer() does it on screen at that moment;
    this check also enforces it on the server for any request that arrives later."""
    reason = st.query_params.get('expired')
    if reason in ('1', 'back'):
        # The browser timer or the Back button reloaded the page; a reload always starts a signed-out session.
        st.query_params.pop('expired', None)
        if not _signed_in():
            st.session_state['_ux_notice'] = (SIGNED_OUT_NOTICE % minutes if reason == '1'
                                              else 'You were signed out. Please sign in again.')
    if not _signed_in():
        st.session_state.pop('_signed_in_at', None)
        return
    started = st.session_state.setdefault('_signed_in_at', time.time())
    if time.time() - started >= minutes * 60:
        _sign_out(role, minutes)


def _history_guard_script():
    """Browser Back never returns to a signed-in page.

    While signed in, Back (or a page restored from the browser's back/forward cache) reloads
    the app on a fresh, signed-out session, which opens the sign-in page (patient, doctor)
    or the password page (admin). Language and theme are kept."""
    import json
    keep = {'lang': st.session_state.get('lang', 'en'),
            'theme': 'dark' if st.session_state.get('dark_mode') else 'light', 'expired': 'back'}
    return ("var signed=" + json.dumps(_signed_in()) + ",keep=" + json.dumps(keep) + ";"
            "w.__ppSignedIn=signed;"
            "w.__ppSignOutUrl=function(){var u=new URL(w.location.href);u.search='';u.hash='';"
            "for(var k in keep){u.searchParams.set(k,keep[k]);}return u.toString();};"
            "if(!w.__ppGuard){w.__ppGuard=true;"
            "w.addEventListener('popstate',function(){if(w.__ppSignedIn){w.__ppSignedIn=false;w.location.replace(w.__ppSignOutUrl());}});"
            "w.addEventListener('pageshow',function(e){if(e.persisted){w.location.replace(w.__ppSignOutUrl());}});}"
            "if(signed&&!(w.history.state&&w.history.state.ppGuard)){w.history.pushState({ppGuard:true},'',w.location.href);}")


def render_session_timer(minutes=SESSION_MINUTES):
    """Browser-side timer that ends the session exactly at the deadline, without a click."""
    import json
    import streamlit.components.v1 as components
    started = st.session_state.get('_signed_in_at')
    remaining_ms = int(max(0, started + minutes * 60 - time.time()) * 1000) if (started and _signed_in()) else -1
    components.html(
        "<script>(function(){var w=window.parent;" + _history_guard_script() +
        "if(w.__ppSessionTimer){w.clearTimeout(w.__ppSessionTimer);w.__ppSessionTimer=null;}"
        "var ms=" + json.dumps(remaining_ms) + ";if(ms<0)return;"
        "w.__ppSessionTimer=w.setTimeout(function(){"
        "var u=new URL(w.location.href);u.searchParams.set('expired','1');w.location.replace(u.toString());"
        "},ms);})();</script>",
        height=0,
    )
