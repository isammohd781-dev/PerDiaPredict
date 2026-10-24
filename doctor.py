"""Independent doctor application: no patient-account or administration pages."""
from pathlib import Path
import runpy
import sys


def render(app):
    st = app['st']
    page = st.session_state['page']
    if page in ('doctor_login','doctor_register'):
        app['care'].doctor_auth_page(page, app['go_to'], sorted({item[1] for item in app['COUNTRY_DIAL_CODES']}))
    else:
        app['render_header']()
        app['care'].render_doctor_dashboard(app['go_to'], app['logout'], app['render_medical_report'], app['generate_pdf_report'], app['HISTORY_DB'])
    app['render_footer']()


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    runpy.run_path(str(root / 'diabetes_app.py'), init_globals={'APP_ROLE':'doctor', 'APP_RENDER':render})
