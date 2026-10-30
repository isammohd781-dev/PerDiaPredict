"""Independent patient application: screening, own reports and care connections."""
from pathlib import Path
import runpy
import sys


def render(app):
    st = app['st']
    page = st.session_state['page']
    public = {'splash':'render_splash', 'auth':'render_auth_page', 'login':'render_login_page', 'register':'render_register_page'}
    if page in public:
        app[public[page]]()
        app['render_footer']()
        return
    if page == 'delete_account' and not st.session_state.get('user'):
        # Public web page for account deletion (no sign-in header).
        app['render_delete_account_page']()
        app['render_footer']()
        return
    app['render_header']()
    nav = st.columns(3)
    for col, label, destination in zip(nav, [app['field_text']('nav_screening'), app['field_text']('nav_reports'), app['field_text']('nav_care')], ['main','patient_history','patient_care']):
        if col.button(label, key='ux_nav_' + destination, use_container_width=True, type='primary' if page == destination else 'secondary'):
            app['go_to'](destination)
    if page == 'patient_care':
        app['care'].render_patient_care(st.session_state['user'], app['go_to'], sorted({item[1] for item in app['COUNTRY_DIAL_CODES']}))
    elif page == 'patient_history':
        app['render_patient_history_page']()
    elif page == 'profile_edit':
        app['render_profile_edit_page']()
    elif page == 'delete_account':
        app['render_delete_account_page']()
    else:
        app['render_main_app']()
    app['render_footer']()


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    runpy.run_path(str(root / 'diabetes_app.py'), init_globals={'APP_ROLE':'patient', 'APP_RENDER':render})
