"""Independent administration application; no public account registration."""
from pathlib import Path
import runpy
import sys


def render(app):
    app['render_header']()
    app['render_admin_page']()
    app['render_footer']()


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root))
    runpy.run_path(str(root / 'diabetes_app.py'), init_globals={'APP_ROLE':'admin', 'APP_RENDER':render})
