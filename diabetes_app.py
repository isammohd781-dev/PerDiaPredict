import base64
import os
import re
import time
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape

import joblib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from translations import LANGUAGES, T

# Optional: needed only to draw Arabic correctly inside the PDF report.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    ARABIC_SHAPING_OK = True
except Exception:
    ARABIC_SHAPING_OK = False


# =============================================================================
# PERDIAPREDICT - MULTILINGUAL VERSION
# Flow: splash -> language gate (continue / change language) -> app
# =============================================================================

_page_icon = "logo.png" if os.path.exists("logo.png") else "🩺"

st.set_page_config(
    page_title="PerdiaPredict",
    page_icon=_page_icon,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Files / configuration
# ---------------------------------------------------------------------------
MODEL_PATH = "diabetes_model.pkl"
SCALER_PATH = "age_scaler.pkl"
COLUMNS_PATH = "feature_columns.pkl"
SAVE_FILE_XLSX = "saved_reports.xlsx"
LOGO_PATH = "logo.png"


def _get_secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


ADMIN_PASSWORD = _get_secret("ADMIN_PASSWORD", "admin123")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# =============================================================================
# Language handling
# =============================================================================

def _init_language():
    """Pick the language once per session (from ?lang=xx in the URL if present)."""
    if st.session_state.get("lang") in LANGUAGES:
        return
    code = None
    try:
        code = st.query_params.get("lang")
    except Exception:
        pass
    st.session_state["lang"] = code if code in LANGUAGES else "en"


_init_language()


def tr(key: str, lang: str = None):
    """Translate a key. Falls back to English, then to the key itself."""
    lang = lang or st.session_state.get("lang", "en")
    value = T.get(lang, {}).get(key)
    if value is None:
        value = T["en"].get(key, key)
    return value


# Scripts where letter-spacing must be off (it breaks joining / conjuncts).
SPACING_OFF_LANGS = {"ar", "hi", "zh"}

# Languages the built-in PDF font (DejaVu Sans) can render.
# Hindi and Chinese need special fonts, so their PDF is produced in English.
PDF_FONT_LANGS = {"en", "ar", "fr", "es", "de", "tr", "pt", "ru"}


def _init_theme():
    """Dark mode by default; ?theme=light in the URL keeps light mode after a refresh."""
    if "dark_mode" in st.session_state:
        return
    code = None
    try:
        code = st.query_params.get("theme")
    except Exception:
        pass
    st.session_state["dark_mode"] = code != "light"


_init_theme()


def _toggle_theme():
    """Called by the day/night button: flips between dark and light mode."""
    is_dark = not st.session_state.get("dark_mode", True)
    st.session_state["dark_mode"] = is_dark
    try:
        st.query_params["theme"] = "dark" if is_dark else "light"
    except Exception:
        pass


def is_rtl(lang: str = None) -> bool:
    lang = lang or st.session_state.get("lang", "en")
    return bool(LANGUAGES.get(lang, {}).get("rtl", False))


# Keep model feature names in the training language/format.
display_labels = {
    "Polyuria": "polyuria",
    "Polydipsia": "polydipsia",
    "sudden weight loss": "weight_loss",
    "Irritability": "irritability",
    "delayed healing": "healing",
    "partial paresis": "paresis",
    "Alopecia": "alopecia",
    "Itching": "itching",
}

extra_symptom_keys = {
    "constant_fatigue": "constant_fatigue",
    "blurry_vision": "blurry_vision",
    "frequent_infections": "frequent_infections",
    "tingling_numbness": "tingling_numbness",
    "increased_hunger": "increased_hunger",
}

DIABETES_TYPE_KEYS = ["not_sure", "type1", "type2", "gestational", "prediabetes"]


# =============================================================================
# Responsive / modern UI
# =============================================================================

def inject_css():
    is_dark = st.session_state.get("dark_mode", True)
    rtl = is_rtl()
    no_spacing = st.session_state.get("lang", "en") in SPACING_OFF_LANGS

    # HEADER = the header bar (the row that contains the brand logo/name).
    HEADER = '[data-testid="stHorizontalBlock"]:has(.brand)'

    spacing_css = ""
    if no_spacing:
        spacing_css = """
        .hero h1, .brand-name, .brand-tagline, .score, .result-title,
        .result-label, .section-title, .pill {
            letter-spacing: 0 !important;
            text-transform: none !important;
        }
        """

    # Keep the theme entirely in Streamlit/Python so the toggle reliably
    # changes the CSS on every rerun. Do not depend on JavaScript setting
    # attributes on Streamlit's parent document.
    if is_dark:
        theme_vars = """
            --primary: #60a5fa;
            --primary-dark: #3b82f6;
            --text: #f8fafc;
            --muted: #94a3b8;
            --surface: #111827;
            --surface-2: #172033;
            --surface-soft: #0f172a;
            --border: #334155;
            --input: #0b1220;
            --input-border: #334155;
            --page: #0f172a;
            --success: #4ade80;
            --danger: #f87171;
            --warning-bg: #422006;
            --warning-border: #92400e;
            --warning-text: #fde68a;
            --info-bg: #172554;
            --info-border: #1d4ed8;
            --info-text: #bfdbfe;
            --shadow: 0 16px 42px rgba(0,0,0,.28);
        """
        page_bg = "#080d18"
    else:
        # Light mode: clean white surfaces + a very soft warm ivory for
        # form fields. The darker navy text keeps every label/value readable.
        theme_vars = """
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --text: #13233f;
            --muted: #53657f;
            --surface: #ffffff;
            --surface-2: #f8fafc;
            --surface-soft: #eef5ff;
            --border: #d8e2ef;
            --input: #fffaf1;
            --input-border: #dfd2bd;
            --input-hover: #fff5e3;
            --input-text: #17253d;
            --page: #edf4fb;
            --success: #15803d;
            --danger: #dc2626;
            --warning-bg: #fff8e8;
            --warning-border: #efd58d;
            --warning-text: #694b00;
            --info-bg: #eaf3ff;
            --info-border: #bfd8fb;
            --info-text: #1e429f;
            --shadow: 0 12px 34px rgba(37,99,235,.10), 0 2px 8px rgba(15,29,53,.06);
        """
        page_bg = "#edf4fb"

    # Right-to-left languages (Arabic): mirror the layout and disable letter
    # spacing, which would otherwise break the joining of Arabic letters.
    if rtl:
        rtl_css = """
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {
            direction: rtl;
            text-align: right;
        }
        .hero, .brand, .section-card, .result-card, .status-card, .notice,
        .section-title, .section-subtitle, .footer {
            direction: rtl;
        }
        .hero, .section-card, .result-card, .status-card, .notice,
        .section-title, .section-subtitle {
            text-align: right;
        }
        .footer { text-align: center; }
        .hero:after { right: auto; left: -55px; }
        .result-high {
            border-left: 1px solid var(--border) !important;
            border-right: 6px solid var(--danger) !important;
        }
        .result-low {
            border-left: 1px solid var(--border) !important;
            border-right: 6px solid var(--success) !important;
        }
        .hero h1, .brand-name, .brand-tagline, .score, .result-title,
        .result-label, .section-title, .pill {
            letter-spacing: 0 !important;
            text-transform: none !important;
        }
        input, textarea { text-align: right; }
        """
        # Header in Arabic: the brand sits at the right edge (icon on the far
        # right, both text lines right-aligned next to it) while the three
        # buttons keep the same order on the left. On phones the brand stays on
        # the first row.
        rtl_css += f"""
        {HEADER} .brand-name,
        {HEADER} .brand-tagline {{
            direction: rtl;
            text-align: right !important;
        }}

        @media (min-width: 641px) {{
            {HEADER} > [data-testid="stColumn"]:nth-child(1) {{
                order: 5 !important;
            }}
        }}
        """
    else:
        rtl_css = ""

    st.markdown(
        f"""
        <style>
        /* ================================================================
           PerdiaPredict complete theme
           The theme is applied to the whole Streamlit interface, not only
           to text. This fixes the mixed light/dark appearance.
           ================================================================ */

        :root {{
            {theme_vars}
        }}

        html, body, [class*="css"] {{
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI",
                         "Noto Sans", "Noto Sans Arabic", Arial, sans-serif;
        }}

        html, body {{
            color-scheme: {"dark" if is_dark else "light"};
            background: {page_bg} !important;
        }}

        /* Main page */
        .stApp {{
            min-height: 100vh;
            background:
                radial-gradient(circle at 8% 0%, rgba(59,130,246,.13), transparent 30%),
                radial-gradient(circle at 100% 12%, rgba(14,165,233,.10), transparent 28%),
                var(--page) !important;
            color: var(--text) !important;
        }}

        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {{
            background: transparent !important;
            color: var(--text) !important;
        }}

        .block-container {{
            max-width: 980px !important;
            padding: 3.0rem 1rem 4rem !important;
        }}

        /* Prevent the page from becoming wider than the browser window. */
        html, body, .stApp, [data-testid="stAppViewContainer"] {{
            max-width: 100% !important;
            overflow-x: hidden !important;
        }}

        /* Streamlit top bar / toolbar */
        header[data-testid="stHeader"] {{
            background: color-mix(in srgb, var(--page) 88%, transparent) !important;
            color: var(--text) !important;
        }}

        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {{
            color: var(--text) !important;
        }}

        /* ================================================================
           HEADER BAR - one tidy frame, same order in every language:
           [ brand .............. ]  [ Admin Panel ]  [ ☀️ / 🌙 ]  [ 🔄 ]
           ================================================================ */
        {HEADER} {{
            direction: ltr !important;
            box-sizing: border-box !important;
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 22px !important;
            padding: 12px 18px !important;
            margin-bottom: 6px !important;
            gap: 12px !important;
            align-items: center !important;
            flex-wrap: nowrap !important;
            box-shadow: var(--shadow) !important;
        }}

        {HEADER} > [data-testid="stColumn"] {{
            min-width: 0 !important;
        }}

        /* Column 1: brand (takes all the free space) */
        {HEADER} > [data-testid="stColumn"]:nth-child(1) {{
            flex: 1 1 0 !important;
            width: auto !important;
            min-width: 0 !important;
        }}

        /* Column 2: Admin Panel (fixed width so it never jumps between languages) */
        {HEADER} > [data-testid="stColumn"]:nth-child(2) {{
            flex: 0 0 172px !important;
            width: 172px !important;
            min-width: 172px !important;
            max-width: 172px !important;
        }}

        /* Column 3 (day/night) and column 4 (restart): equal square buttons */
        {HEADER} > [data-testid="stColumn"]:nth-child(3),
        {HEADER} > [data-testid="stColumn"]:nth-child(4) {{
            flex: 0 0 48px !important;
            width: 48px !important;
            min-width: 48px !important;
            max-width: 48px !important;
        }}

        /* Remove default margins so everything sits on one centre line */
        {HEADER} [data-testid="stElementContainer"],
        {HEADER} [data-testid="stMarkdownContainer"] {{
            margin: 0 !important;
            padding: 0 !important;
        }}

        /* Brand */
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            min-width: 0;
            padding: 0;
        }}

        .brand-icon {{
            width: 48px;
            height: 48px;
            flex: 0 0 48px;
            border-radius: 15px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg,#2563eb,#0ea5e9);
            color: white !important;
            font-size: 25px;
            box-shadow: 0 8px 22px rgba(37,99,235,.25);
        }}

        .brand-name {{
            font-size: 1.15rem;
            font-weight: 800;
            letter-spacing: -.02em;
            line-height: 1.2;
            color: var(--text) !important;
        }}

        .brand-tagline {{
            font-size: .78rem;
            line-height: 1.3;
            color: var(--muted) !important;
            margin-top: 1px;
        }}

        /* All three header buttons share one look and one height. */
        {HEADER} .stButton > button {{
            width: 100% !important;
            height: 48px !important;
            min-height: 48px !important;
            border-radius: 14px !important;
            background: var(--surface-soft) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            font-weight: 750 !important;
            padding: 0 10px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            transition: border-color .15s ease, box-shadow .15s ease;
        }}

        {HEADER} .stButton > button:hover {{
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 3px rgba(96,165,250,.16) !important;
            transform: none !important;
        }}

        {HEADER} .stButton > button p {{
            margin: 0 !important;
            line-height: 1 !important;
        }}

        /* Day / night (column 3) and restart (column 4): bigger icons */
        {HEADER} > [data-testid="stColumn"]:nth-child(3) .stButton > button p,
        {HEADER} > [data-testid="stColumn"]:nth-child(4) .stButton > button p {{
            font-size: 1.3rem !important;
        }}

        /* The patient form: one complete rounded frame, visible in light AND dark mode */
        [data-testid="stForm"] {{
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 22px !important;
            padding: 22px 20px !important;
            box-shadow: var(--shadow) !important;
        }}

        /* Hero */
        .hero {{
            background:linear-gradient(135deg,#020617 0%,#172554 56%,#075985 100%);
            color:white !important;
            border-radius:26px;
            padding:30px 28px;
            margin:18px 0;
            box-shadow:0 18px 45px rgba(0,0,0,.32);
            overflow:hidden;
            position:relative;
        }}

        .hero:after {{
            content:"";
            position:absolute;
            width:190px;
            height:190px;
            border-radius:50%;
            background:rgba(96,165,250,.14);
            right:-55px;
            top:-65px;
        }}

        .hero h1 {{
            color:#ffffff !important;
            -webkit-text-fill-color:#ffffff !important;
            font-size:clamp(1.75rem,4vw,2.65rem);
            line-height:1.12;
            margin:0 0 10px;
            letter-spacing:-.035em;
            font-weight:800 !important;
        }}

        .hero p {{
            color:rgba(255,255,255,.90) !important;
            -webkit-text-fill-color:rgba(255,255,255,.90) !important;
            margin:0;
            max-width:720px;
            line-height:1.65;
        }}

        /* Keep every element inside the dark hero readable in Light Mode. */
        .hero,
        .hero *,
        .hero div,
        .hero span,
        .hero strong,
        .hero h1,
        .hero p {{
            color:#ffffff !important;
            -webkit-text-fill-color:#ffffff !important;
        }}

        .hero p {{
            color:rgba(255,255,255,.90) !important;
            -webkit-text-fill-color:rgba(255,255,255,.90) !important;
        }}

        .pill {{
            display:inline-flex;
            align-items:center;
            gap:7px;
            padding:7px 11px;
            border-radius:999px;
            background:rgba(255,255,255,.10);
            border:1px solid rgba(255,255,255,.18);
            color:#f8fafc !important;
            font-size:.78rem;
            margin-bottom:14px;
        }}

        /* Cards */
        .section-card,
        .result-card {{
            background:var(--surface) !important;
            border:1px solid var(--border) !important;
            color:var(--text) !important;
            box-shadow:var(--shadow) !important;
        }}

        .section-card {{
            border-radius:22px;
            padding:20px;
            margin:14px 0;
        }}

        .section-title {{
            font-size:1.12rem;
            font-weight:800;
            color:var(--text) !important;
            margin-bottom:3px;
        }}

        .section-subtitle {{
            color:var(--muted) !important;
            font-size:.86rem;
            line-height:1.5;
            margin-bottom:14px;
        }}

        .status-card {{
            display:flex;
            align-items:center;
            gap:10px;
            padding:11px 13px;
            border-radius:15px;
            background:var(--info-bg) !important;
            border:1px solid var(--info-border) !important;
            color:var(--info-text) !important;
            font-size:.85rem;
            margin:10px 0 16px;
        }}

        .result-card {{
            border-radius:24px;
            padding:24px;
            margin:14px 0;
        }}

        .result-high {{
            border-left:6px solid var(--danger) !important;
        }}

        .result-low {{
            border-left:6px solid var(--success) !important;
        }}

        .result-label {{
            color:var(--muted) !important;
            font-size:.82rem;
            font-weight:700;
            text-transform:uppercase;
            letter-spacing:.06em;
        }}

        .result-title {{
            font-size:clamp(1.2rem,3vw,1.55rem);
            font-weight:850;
            margin:5px 0 16px;
            color:var(--text) !important;
        }}

        .score {{
            font-size:clamp(2.1rem,7vw,3.5rem);
            line-height:1;
            font-weight:900;
            letter-spacing:-.05em;
            color:var(--text) !important;
        }}

        .score-caption {{
            color:var(--muted) !important;
            font-size:.82rem;
            margin-top:5px;
        }}

        .notice {{
            border-radius:16px;
            padding:13px 15px;
            background:var(--warning-bg) !important;
            border:1px solid var(--warning-border) !important;
            color:var(--warning-text) !important;
            font-size:.84rem;
            line-height:1.55;
            margin:12px 0;
        }}

        .footer {{
            text-align:center;
            color:var(--muted) !important;
            font-size:.75rem;
            padding:24px 0 4px;
        }}

        /* ALL normal Streamlit text */
        .stMarkdown, .stText, .stCaption,
        [data-testid="stMarkdownContainer"],
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        label, p, li, span {{
            color:var(--text) !important;
        }}

        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {{
            color:var(--muted) !important;
        }}

        /* ================================================================
           Form fields - one clean frame per field, identical logic in light
           and dark mode. Streamlit's own dark layers (#262730) are cleared so
           they can no longer show through as dark edges / dark side blocks.
           ================================================================ */

        /* 1) Clear Streamlit/BaseWeb's built-in dark layers. */
        [data-baseweb="input"],
        [data-baseweb="input"] > div,
        [data-baseweb="input"] div,
        [data-baseweb="base-input"],
        [data-baseweb="textarea"],
        [data-baseweb="textarea"] > div,
        [data-baseweb="textarea"] div,
        [data-baseweb="select"],
        [data-baseweb="select"] > div,
        [data-baseweb="select"] > div > div {{
            background: transparent !important;
        }}

        /* 2) The visible field frame.
           Light mode uses a subtle warm ivory/beige so fields are distinct
           from the white card without looking heavy. */
        div[data-baseweb="input"],
        div[data-baseweb="textarea"],
        div[data-baseweb="select"] > div {{
            background: var(--input) !important;
            border: 1px solid var(--input-border) !important;
            border-radius: 12px !important;
            overflow: hidden;
            box-shadow: none !important;
            transition: background .15s ease, border-color .15s ease,
                        box-shadow .15s ease;
        }}

        /* 3) Text inside inputs must stay dark in Light Mode.
           -webkit-text-fill-color is included because BaseWeb/Streamlit can
           otherwise keep the browser's dark-theme text color. */
        input, textarea {{
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: var(--input-text, var(--text)) !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
            caret-color: var(--primary) !important;
            opacity: 1 !important;
        }}

        input[type="number"] {{
            color: var(--input-text, var(--text)) !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
        }}

        /* BaseWeb Select: force the selected value and placeholder to remain
           readable instead of inheriting Streamlit's dark-mode text. */
        [data-baseweb="select"] [role="button"],
        [data-baseweb="select"] [role="button"] *,
        [data-baseweb="select"] [aria-selected="true"],
        [data-baseweb="select"] span {{
            color: var(--input-text, var(--text)) !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
            opacity: 1 !important;
        }}

        input::placeholder,
        textarea::placeholder {{
            color: var(--muted) !important;
            opacity: .8 !important;
        }}

        /* 4) focus */
        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="textarea"]:focus-within,
        div[data-baseweb="select"] > div:focus-within {{
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 3px rgba(37,99,235,.16) !important;
        }}

        /* 5) small buttons inside fields (number  - / +  and password eye) */
        [data-baseweb="input"] button {{
            background: transparent !important;
            border: 0 !important;
            color: var(--muted) !important;
        }}

        [data-baseweb="input"] button:hover {{
            background: var(--input-hover, var(--surface-soft)) !important;
            color: var(--primary) !important;
        }}

        /* Keep the +/- controls and their icons visible. */
        [data-baseweb="input"] button,
        [data-baseweb="input"] button span,
        [data-baseweb="input"] button svg {{
            opacity: 1 !important;
        }}

        [data-baseweb="input"] button svg,
        [data-baseweb="select"] svg {{
            fill: var(--muted) !important;
            color: var(--muted) !important;
        }}

        /* Selectbox text + dropdown */
        [data-baseweb="select"] *,
        [role="listbox"] *,
        [role="option"] {{
            color: var(--input-text, var(--text)) !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
        }}

        /* Dropdown arrow */
        [data-baseweb="select"] svg {{
            fill: var(--muted) !important;
            color: var(--muted) !important;
            opacity: 1 !important;
        }}

        div[data-baseweb="popover"],
        div[data-baseweb="menu"],
        [role="listbox"] {{
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            color: var(--text) !important;
        }}

        [role="option"]:hover,
        [role="option"][aria-selected="true"] {{
            background: var(--surface-soft) !important;
        }}

        /* Field labels */
        [data-testid="stWidgetLabel"] p {{
            font-weight: 700 !important;
            font-size: .88rem !important;
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
        }}

        [data-testid="stWidgetLabel"] span {{
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
        }}

        /* Divider lines inside the form: visible but compact */
        [data-testid="stMarkdownContainer"] hr {{
            margin: .5rem 0 !important;
            border: 0 !important;
            border-top: 1px solid var(--border) !important;
            opacity: 1 !important;
        }}

        [data-testid="stForm"] [data-testid="stVerticalBlock"] {{
            gap: .85rem !important;
        }}

        /* Radio buttons / checkboxes / toggles */
        [data-testid="stRadio"],
        [data-testid="stCheckbox"],
        [data-testid="stToggle"] {{
            color:var(--text) !important;
        }}

        [data-testid="stRadio"] label,
        [data-testid="stCheckbox"] label,
        [data-testid="stToggle"] label {{
            color:var(--text) !important;
        }}

        /* Buttons */
        .stButton > button,
        .stDownloadButton > button,
        button[kind="primary"] {{
            border-radius:14px !important;
            min-height:46px !important;
            font-weight:750 !important;
            color:var(--text) !important;
            background:var(--surface) !important;
            border:1px solid var(--border) !important;
            transition:transform .15s ease, box-shadow .15s ease, border-color .15s ease;
        }}

        .stButton > button:hover,
        .stDownloadButton > button:hover {{
            transform:translateY(-1px);
            border-color:var(--primary) !important;
            box-shadow:0 8px 18px rgba(0,0,0,.20) !important;
        }}

        .stButton > button[kind="primary"],
        button[kind="primary"] {{
            background:linear-gradient(135deg,#2563eb,#0284c7) !important;
            color:white !important;
            border:none !important;
        }}

        /* Metrics */
        [data-testid="stMetric"] {{
            background:var(--surface) !important;
            border:1px solid var(--border) !important;
            border-radius:18px;
            padding:14px;
            color:var(--text) !important;
        }}

        [data-testid="stMetricValue"],
        [data-testid="stMetricLabel"],
        [data-testid="stMetricDelta"] {{
            color:var(--text) !important;
        }}

        /* Expanders: one clean rounded border (no doubled / half lines) */
        .stExpander,
        [data-testid="stExpander"] {{
            border: 1px solid var(--border) !important;
            border-radius: 16px !important;
            background: var(--surface-2) !important;
            color: var(--text) !important;
            overflow: hidden;
        }}

        .stExpander details,
        .stExpander summary,
        [data-testid="stExpander"] details,
        [data-testid="stExpander"] summary {{
            background: transparent !important;
            border: 0 !important;
            color: var(--text) !important;
        }}

        [data-testid="stExpander"] summary:hover {{
            background: var(--surface-soft) !important;
        }}

        /* Alerts */
        [data-testid="stAlert"] {{
            background:var(--surface) !important;
            border:1px solid var(--border) !important;
            color:var(--text) !important;
        }}

        /* Dataframes / tables */
        [data-testid="stDataFrame"],
        [data-testid="stTable"] {{
            background:var(--surface) !important;
            color:var(--text) !important;
        }}

        /* File uploader */
        [data-testid="stFileUploaderDropzone"] {{
            background:var(--surface) !important;
            border:1px dashed var(--border) !important;
            color:var(--text) !important;
        }}

        /* ================================================================
           Mobile-only adjustments. Desktop is intentionally unchanged.
           Row 1: brand (full width).  Row 2: [ Admin Panel ] [ ☀️/🌙 ] [ 🔄 ]
           ================================================================ */
        @media (max-width: 640px) {{
            .block-container {{
                width: 100% !important;
                max-width: 100% !important;
                box-sizing: border-box !important;
                padding: 2.60rem 0.65rem 2.5rem !important;
                overflow-x: hidden !important;
            }}

            {HEADER} {{
                width: 100% !important;
                display: flex !important;
                flex-wrap: wrap !important;
                gap: 10px !important;
                padding: 10px !important;
                border-radius: 18px !important;
            }}

            {HEADER} > [data-testid="stColumn"]:nth-child(1) {{
                flex: 0 0 100% !important;
                width: 100% !important;
                max-width: 100% !important;
            }}

            {HEADER} > [data-testid="stColumn"]:nth-child(3),
            {HEADER} > [data-testid="stColumn"]:nth-child(4) {{
                flex: 0 0 46px !important;
                width: 46px !important;
                min-width: 46px !important;
                max-width: 46px !important;
            }}

            {HEADER} > [data-testid="stColumn"]:nth-child(2) {{
                flex: 1 1 0 !important;
                width: auto !important;
                min-width: 0 !important;
                max-width: none !important;
            }}

            {HEADER} .stButton > button {{
                height: 46px !important;
                min-height: 46px !important;
            }}

            {HEADER} > [data-testid="stColumn"]:nth-child(2) .stButton > button {{
                font-size: 0.85rem !important;
                padding: 0 6px !important;
                white-space: nowrap !important;
            }}

            .brand {{
                gap: 10px !important;
            }}

            .brand-icon {{
                width: 44px !important;
                height: 44px !important;
                border-radius: 13px !important;
                flex: 0 0 44px !important;
            }}

            .brand-name {{
                font-size: 1.05rem !important;
                line-height: 1.15 !important;
            }}

            .brand-tagline {{
                font-size: 0.78rem !important;
                line-height: 1.25 !important;
            }}

            .stButton > button {{
                width: 100% !important;
                min-height: 44px !important;
                padding: 7px 8px !important;
                white-space: nowrap !important;
                font-size: 0.88rem !important;
            }}

            .hero {{
                width: 100% !important;
                box-sizing: border-box !important;
                border-radius: 20px !important;
                padding: 22px 18px !important;
                margin: 10px 0 13px !important;
            }}

            .hero h1 {{
                font-size: clamp(2rem, 9vw, 2.7rem) !important;
                line-height: 1.08 !important;
                word-break: normal !important;
            }}

            .hero p {{
                font-size: 1rem !important;
                line-height: 1.5 !important;
            }}

            input, textarea, select {{
                max-width: 100% !important;
            }}

            [data-testid="stForm"] {{
                padding: 16px 12px !important;
                border-radius: 18px !important;
            }}
        }}

        /* Right-to-left languages */
        {rtl_css}
        {spacing_css}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# Model
# =============================================================================

@st.cache_resource
def load_artifacts():
    missing = [p for p in [MODEL_PATH, SCALER_PATH, COLUMNS_PATH] if not os.path.exists(p)]
    if missing:
        st.error(tr("err_missing").format(files=", ".join(missing)))
        st.stop()

    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    feature_columns = joblib.load(COLUMNS_PATH)
    return model, scaler, feature_columns


model, scaler, feature_columns = load_artifacts()
binary_columns = [c for c in feature_columns if c not in ("Age", "Gender")]


# =============================================================================
# Session state
# =============================================================================

if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = True
if "page" not in st.session_state:
    st.session_state["page"] = "splash"
if "choosing_language" not in st.session_state:
    st.session_state["choosing_language"] = False
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None
if "last_report" not in st.session_state:
    st.session_state["last_report"] = None
if "last_report_en" not in st.session_state:
    st.session_state["last_report_en"] = None
if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "last_probability" not in st.session_state:
    st.session_state["last_probability"] = 0.0
if "last_extra" not in st.session_state:
    st.session_state["last_extra"] = False


def go_to(page_name: str):
    st.session_state["page"] = page_name
    st.rerun()


def restart_app(new_lang: str):
    """Restart the app from the beginning (splash screen) in a new language."""
    keep_dark = st.session_state.get("dark_mode", True)

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state["lang"] = new_lang if new_lang in LANGUAGES else "en"
    st.session_state["dark_mode"] = keep_dark
    st.session_state["page"] = "splash"

    # Remember the language in the URL so a browser refresh keeps it.
    try:
        st.query_params["lang"] = st.session_state["lang"]
    except Exception:
        pass

    st.rerun()


# =============================================================================
# Animated splash screen
# =============================================================================

def render_splash():
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as _f:
            _b64 = base64.b64encode(_f.read()).decode()
        logo_html = (
            f'<img src="data:image/png;base64,{_b64}" '
            'style="width:100%;height:100%;object-fit:cover;border-radius:inherit;" />'
        )
    else:
        logo_html = "🩺"

    # Letter-spacing / uppercase would break Arabic letter joining.
    plain_script = is_rtl() or st.session_state.get("lang", "en") in SPACING_OFF_LANGS
    welcome_spacing = "0" if plain_script else ".35em"
    welcome_transform = "none" if plain_script else "uppercase"

    st.markdown(
        f"""
        <style>
        header[data-testid="stHeader"] {{ display:none !important; }}
        .splash {{
            position:fixed; inset:0; z-index:999999;
            display:flex; flex-direction:column; align-items:center; justify-content:center;
            background:
                radial-gradient(circle at 50% 38%, rgba(37,99,235,.35), transparent 45%),
                linear-gradient(160deg,#020617 0%,#0b1a3d 55%,#053a5c 100%);
            animation: splashOut .7s ease-in 4.5s forwards;
            overflow:hidden;
        }}
        .splash-particle {{
            position:absolute; border-radius:50%;
            background:rgba(96,165,250,.35);
            animation: floatUp linear infinite;
        }}
        .splash-particle:nth-child(1) {{ left:10%; width:8px; height:8px; animation-duration:7s; animation-delay:0s; }}
        .splash-particle:nth-child(2) {{ left:28%; width:5px; height:5px; animation-duration:9s; animation-delay:1s; }}
        .splash-particle:nth-child(3) {{ left:47%; width:10px; height:10px; animation-duration:8s; animation-delay:.5s; }}
        .splash-particle:nth-child(4) {{ left:66%; width:6px; height:6px; animation-duration:10s; animation-delay:2s; }}
        .splash-particle:nth-child(5) {{ left:82%; width:9px; height:9px; animation-duration:7.5s; animation-delay:1.5s; }}
        .splash-particle:nth-child(6) {{ left:92%; width:5px; height:5px; animation-duration:9.5s; animation-delay:.8s; }}

        .logo-stage {{
            position:relative; width:190px; height:190px;
            display:flex; align-items:center; justify-content:center;
        }}
        .logo-ring {{
            position:absolute; inset:0; border-radius:50%;
            border:2px solid rgba(96,165,250,.55);
            opacity:0; animation: ring 2.6s ease-out infinite;
        }}
        .logo-ring:nth-child(2) {{ animation-delay:.8s; }}
        .logo-ring:nth-child(3) {{ animation-delay:1.6s; }}
        .logo-box {{
            width:118px; height:118px; border-radius:30px;
            display:flex; align-items:center; justify-content:center;
            background:linear-gradient(135deg,#2563eb,#0ea5e9);
            font-size:60px; overflow:hidden;
            box-shadow:0 0 40px rgba(59,130,246,.65), 0 0 90px rgba(14,165,233,.35);
            opacity:0; transform:scale(.2) rotate(-200deg);
            animation:
                logoIn 1.3s cubic-bezier(.2,1.2,.3,1) .2s forwards,
                logoFloat 3s ease-in-out 1.5s infinite,
                glow 2.2s ease-in-out 1.5s infinite;
        }}
        .welcome-small {{
            margin-top:34px; color:#93c5fd;
            font-size:clamp(1rem,3.5vw,1.3rem); letter-spacing:{welcome_spacing}; text-transform:{welcome_transform};
            opacity:0; transform:translateY(16px);
            animation: fadeUp .8s ease-out 1.7s forwards;
        }}
        .welcome-name {{
            margin-top:6px; font-weight:900; letter-spacing:-.02em;
            font-size:clamp(2.1rem,8vw,3.6rem);
            background:linear-gradient(90deg,#60a5fa,#ffffff,#38bdf8,#60a5fa);
            background-size:250% 100%;
            -webkit-background-clip:text; background-clip:text;
            -webkit-text-fill-color:transparent; color:transparent;
            opacity:0; transform:translateY(20px) scale(.92);
            animation: fadeUp .9s ease-out 2.1s forwards, shimmer 3s linear 2.1s infinite;
        }}
        .welcome-tag {{
            margin-top:10px; color:#94a3b8; font-size:.95rem; text-align:center; padding:0 20px;
            opacity:0; animation: fadeUp .8s ease-out 2.9s forwards;
        }}
        .loader {{
            position:absolute; bottom:9%; width:min(240px,60vw); height:4px;
            background:rgba(255,255,255,.12); border-radius:99px; overflow:hidden;
        }}
        .loader div {{
            height:100%; width:0; border-radius:99px;
            background:linear-gradient(90deg,#2563eb,#38bdf8);
            animation: load 4s ease-in-out .4s forwards;
        }}
        @keyframes logoIn {{ to {{ opacity:1; transform:scale(1) rotate(0deg); }} }}
        @keyframes logoFloat {{ 0%,100% {{ transform:translateY(0); }} 50% {{ transform:translateY(-10px); }} }}
        @keyframes glow {{
            0%,100% {{ box-shadow:0 0 30px rgba(59,130,246,.55), 0 0 70px rgba(14,165,233,.25); }}
            50% {{ box-shadow:0 0 55px rgba(59,130,246,.95), 0 0 120px rgba(14,165,233,.55); }}
        }}
        @keyframes ring {{
            0% {{ transform:scale(.55); opacity:.8; }}
            100% {{ transform:scale(1.25); opacity:0; }}
        }}
        @keyframes fadeUp {{ to {{ opacity:1; transform:translateY(0) scale(1); }} }}
        @keyframes shimmer {{ 0% {{ background-position:0% 0; }} 100% {{ background-position:250% 0; }} }}
        @keyframes load {{ to {{ width:100%; }} }}
        @keyframes floatUp {{
            0% {{ bottom:-20px; opacity:0; }}
            15% {{ opacity:1; }}
            100% {{ bottom:105%; opacity:0; }}
        }}
        @keyframes splashOut {{ to {{ opacity:0; visibility:hidden; }} }}
        </style>
        <div class="splash">
            <div class="splash-particle"></div><div class="splash-particle"></div>
            <div class="splash-particle"></div><div class="splash-particle"></div>
            <div class="splash-particle"></div><div class="splash-particle"></div>
            <div class="logo-stage">
                <div class="logo-ring"></div><div class="logo-ring"></div><div class="logo-ring"></div>
                <div class="logo-box">{logo_html}</div>
            </div>
            <div class="welcome-small">{tr('welcome_to')}</div>
            <div class="welcome-name">PerdiaPredict</div>
            <div class="welcome-tag">{tr('tagline')}</div>
            <div class="loader"><div></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Let the animation play, then show the "continue / change language" screen.
    time.sleep(5.2)
    go_to("language")


# =============================================================================
# Language gate (shown right after the splash screen)
# =============================================================================

def render_language_gate():
    lang = st.session_state["lang"]
    current_name = LANGUAGES[lang]["native"]

    st.markdown(
        f"""
        <div class="hero">
            <div class="pill">🌐 {tr('current_language')}: {current_name}</div>
            <h1>{tr('gate_title')}</h1>
            <p>{tr('gate_intro')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.get("choosing_language", False):
        col_continue, col_change = st.columns(2)

        with col_continue:
            if st.button(
                f"▶️ {tr('continue')}",
                type="primary",
                use_container_width=True,
                key="gate_continue",
            ):
                go_to("main")

        with col_change:
            if st.button(
                f"🌐 {tr('change_language')}",
                use_container_width=True,
                key="gate_change",
            ):
                st.session_state["choosing_language"] = True
                st.rerun()
    else:
        st.markdown(
            f"""
            <div class="section-card">
                <div class="section-title">🌐 {tr('select_language')}</div>
                <div class="section-subtitle">{tr('restart_note')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cols = st.columns(2)
        for i, (code, info) in enumerate(LANGUAGES.items()):
            with cols[i % 2]:
                label = info["native"] + ("  ✓" if code == lang else "")
                if st.button(
                    label,
                    key=f"lang_{code}",
                    use_container_width=True,
                    type="primary" if code == lang else "secondary",
                ):
                    restart_app(code)  # restarts from the splash screen

        if st.button(f"⬅️ {tr('back')}", key="gate_back", use_container_width=True):
            st.session_state["choosing_language"] = False
            st.rerun()


# =============================================================================
# Header
# =============================================================================

def render_header():
    """Header bar:  brand | Admin Panel | day/night button | restart button.

    All the styling (alignment, sizes, mobile layout) lives in inject_css().
    The order of the three buttons is the same in every language; in Arabic the
    brand moves to the right edge (see rtl_css in inject_css()).
    """
    left, admin_col, theme_col, menu_col = st.columns([5, 3, 1, 1], vertical_alignment="center")

    with left:
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, "rb") as _logo_file:
                _logo_b64 = base64.b64encode(_logo_file.read()).decode()
            brand_icon_html = (
                f'<img src="data:image/png;base64,{_logo_b64}" '
                'style="width:100%;height:100%;object-fit:cover;border-radius:inherit;" />'
            )
        else:
            brand_icon_html = "🩺"

        st.markdown(
            f"""
            <div class="brand">
                <div class="brand-icon">{brand_icon_html}</div>
                <div>
                    <div class="brand-name">{tr('brand')}</div>
                    <div class="brand-tagline">{tr('tagline')}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with menu_col:
        # Restart arrow: clears the session and goes back to the splash screen.
        if st.button(
            "🔄",
            key="menu_restart",
            help=tr("menu_restart"),
            use_container_width=True,
        ):
            restart_app(st.session_state["lang"])

    with admin_col:
        if st.session_state["page"] == "admin":
            if st.button(f"⬅️ {tr('back')}", use_container_width=True):
                go_to("main")
        else:
            if st.button(f"🔒 {tr('admin')}", use_container_width=True):
                go_to("admin")

    with theme_col:
        # Shows the mode you will switch TO (sun while dark, moon while light).
        is_dark = st.session_state.get("dark_mode", True)
        st.button(
            "☀️" if is_dark else "🌙",
            key="theme_btn",
            help=tr("light") if is_dark else tr("dark"),
            use_container_width=True,
            on_click=_toggle_theme,
        )


# =============================================================================
# Prediction
# =============================================================================

def _model_probability(raw_input: dict) -> float:
    df_new = pd.DataFrame([raw_input])
    df_new["Gender"] = df_new["Gender"].map({"Male": 1, "Female": 0})

    for col in binary_columns:
        df_new[col] = df_new[col].map({"Yes": 1, "No": 0})

    df_new["Age"] = scaler.transform(df_new[["Age"]])
    df_new = df_new[feature_columns]
    return float(model.predict_proba(df_new)[0][1])


def predict_new_patient(raw_input: dict):
    # Important: all "No" answers must produce exactly 0%.
    yes_symptoms = [c for c in binary_columns if raw_input.get(c) == "Yes"]

    if not yes_symptoms:
        return 0, 0.0

    actual_probability = _model_probability(raw_input)

    baseline_input = dict(raw_input)
    for col in binary_columns:
        baseline_input[col] = "No"

    baseline_probability = _model_probability(baseline_input)

    contributions = []
    for col in yes_symptoms:
        one_symptom_input = dict(baseline_input)
        one_symptom_input[col] = "Yes"
        symptom_probability = _model_probability(one_symptom_input)
        contribution = max(0.0, symptom_probability - baseline_probability)
        contributions.append(contribution)

    total_positive_evidence = sum(contributions)

    if total_positive_evidence <= 0:
        symptom_factor = len(yes_symptoms) / max(len(binary_columns), 1)
    else:
        symptom_factor = min(total_positive_evidence / 0.50, 1.0)

    probability = actual_probability * symptom_factor
    probability = max(0.0, min(1.0, probability))
    prediction = 1 if probability >= 0.50 else 0

    return prediction, probability


# =============================================================================
# Symptom narrative / report
# =============================================================================

def _join(items, lang):
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return items[0] + tr("and_two", lang) + items[1]
    return tr("list_sep", lang).join(items[:-1]) + tr("and_last", lang) + items[-1]


def build_symptom_narrative(symptom_values: dict, extra_values: dict, lang: str = None) -> str:
    lang = lang or st.session_state.get("lang", "en")

    core_yes = [
        tr(key, lang)
        for col, key in display_labels.items()
        if symptom_values.get(col) == "Yes"
    ]
    extra_yes = [tr(key, lang) for key in extra_symptom_keys if extra_values.get(key) == "Yes"]

    if not core_yes and not extra_yes:
        return tr("patient_denies", lang)

    sp = tr("word_space", lang)
    end = tr("period", lang)

    sentences = []
    if core_yes:
        sentences.append(tr("patient_reports", lang) + sp + _join(core_yes, lang) + end)
    else:
        sentences.append(tr("no_core", lang))

    if extra_yes:
        sentences.append(tr("further", lang) + sp + _join(extra_yes, lang) + end)

    return (sp or "").join(sentences)


def build_report(lang, timestamp, first, last, phone, email, address, type_key,
                 age, gender, result, probability, symptom_values, extra_values) -> dict:
    """Build the report dictionary in the requested language."""
    any_extra = any(v == "Yes" for v in extra_values.values())
    return {
        "Timestamp": timestamp,
        "First name": first,
        "Last name": last,
        "Phone": phone,
        "Email": email if email else tr("na", lang),
        "Address": address,
        "Reported diabetes type": tr(type_key, lang),
        "Age": age,
        "Gender": tr("male" if gender == "Male" else "female", lang),
        "Result": tr("positive_high" if result == 1 else "negative_low", lang),
        "Probability": f"{probability * 100:.1f}%",
        "Notable extra symptoms": tr("yes" if any_extra else "no", lang),
        "Symptom narrative": build_symptom_narrative(symptom_values, extra_values, lang),
    }


# =============================================================================
# Health guide
# =============================================================================

def render_meal_plan():
    st.markdown(f'<div class="section-title">📅 {tr("meal_plan")}</div>', unsafe_allow_html=True)

    df = pd.DataFrame(
        tr("meal_plan_rows"),
        columns=[tr("meal_plan"), tr("breakfast"), tr("lunch"), tr("dinner"), tr("drinks")],
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


def _bullets(key: str) -> str:
    return "\n".join(f"- {item}" for item in tr(key))


def render_offline_health_guide():
    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">🌿 {tr('health_guide')}</div>
            <div class="section-subtitle">{tr('offline')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"🍽️ {tr('plate')}", expanded=True):
        st.markdown(_bullets("plate_items"))

    with st.expander(f"🥗 {tr('foods')}"):
        st.markdown(_bullets("foods_items"))

    with st.expander(f"⚠️ {tr('limit')}"):
        st.markdown(_bullets("limit_items"))

    with st.expander(f"🏃 {tr('habits')}"):
        st.markdown(_bullets("habits_items"))

    with st.expander(f"📅 {tr('meal_plan')}"):
        render_meal_plan()


# =============================================================================
# PDF
# =============================================================================
# The PDF needs a Unicode font for Turkish / Arabic characters. Put
# DejaVuSans.ttf (and DejaVuSans-Bold.ttf) inside a "fonts" folder next to
# this file. For Arabic also install: arabic-reshaper and python-bidi.
# If the font is missing, the PDF is generated in English automatically.

_FONT_DIRS = [
    "fonts",
    ".",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
]


def _find_font_file(filename: str):
    dirs = list(_FONT_DIRS)
    try:
        import matplotlib

        dirs.append(os.path.join(matplotlib.get_data_path(), "fonts", "ttf"))
    except Exception:
        pass

    for directory in dirs:
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return path
    return None


@st.cache_resource
def register_pdf_fonts() -> bool:
    regular = _find_font_file("DejaVuSans.ttf")
    if not regular:
        return False
    bold = _find_font_file("DejaVuSans-Bold.ttf") or regular

    try:
        pdfmetrics.registerFont(TTFont("PDFRegular", regular))
        pdfmetrics.registerFont(TTFont("PDFBold", bold))
        pdfmetrics.registerFontFamily(
            "PDFRegular",
            normal="PDFRegular",
            bold="PDFBold",
            italic="PDFRegular",
            boldItalic="PDFBold",
        )
        return True
    except Exception:
        return False


def pick_pdf_language(lang: str) -> str:
    """Return the language the PDF can actually be rendered in on this server."""
    if lang == "en":
        return "en"
    if lang not in PDF_FONT_LANGS:
        return "en"
    if not register_pdf_fonts():
        return "en"
    if is_rtl(lang) and not ARABIC_SHAPING_OK:
        return "en"
    return lang


def _shape(text) -> str:
    return get_display(arabic_reshaper.reshape(str(text)))


def _wrap_rtl(text: str, font_name: str, font_size: float, max_width: float) -> str:
    """Wrap Arabic text manually (line by line) so the visual order stays correct."""
    words = str(text).split()
    lines, current = [], []

    for word in words:
        trial = " ".join(current + [word])
        if current and pdfmetrics.stringWidth(_shape(trial), font_name, font_size) > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)

    if current:
        lines.append(" ".join(current))

    return "<br/>".join(xml_escape(_shape(line)) for line in lines)


def generate_pdf_report(report_data: dict, lang: str = "en", is_high: bool = False) -> bytes:
    rtl = is_rtl(lang)
    has_ttf = register_pdf_fonts()
    font = "PDFRegular" if has_ttf else "Helvetica"
    font_bold = "PDFBold" if has_ttf else "Helvetica-Bold"
    align = TA_RIGHT if rtl else TA_LEFT

    def t(key):
        return tr(key, lang)

    def shp(text):
        return _shape(text) if rtl else str(text)

    def flow(text, size=9.5, width=530):
        """Text for a Paragraph (escaped; manually wrapped for Arabic)."""
        return _wrap_rtl(text, font, size, width) if rtl else xml_escape(str(text))

    def label_paragraph(label, value_text):
        if rtl:
            return f"{xml_escape(shp(value_text))} :<b>{xml_escape(shp(label))}</b>"
        return f"<b>{xml_escape(str(label))}:</b> {xml_escape(str(value_text))}"

    def make_rows(pairs):
        rows = []
        for label, value in pairs:
            rows.append([shp(value), shp(label)] if rtl else [shp(label), shp(value)])
        return rows

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=18,
        textColor=colors.HexColor("#0d3b66"),
        spaceAfter=4,
        alignment=align,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName=font,
        fontSize=11,
        textColor=colors.HexColor("#555555"),
        alignment=align,
    )
    heading_style = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=12,
        textColor=colors.HexColor("#0d3b66"),
        spaceBefore=10,
        spaceAfter=6,
        alignment=align,
    )
    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["Normal"],
        fontName=font,
        fontSize=9.5,
        leading=13,
        alignment=align,
    )

    elements = []
    title = Paragraph("<b>PERDIAPREDICT</b>", title_style)
    subtitle = Paragraph(flow(t("pdf_title"), size=11, width=440), subtitle_style)

    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=55, height=55)
        if rtl:
            header = Table([[[title, subtitle], logo]], colWidths=[482, 58])
        else:
            header = Table([[logo, [title, subtitle]]], colWidths=[58, 482])
    else:
        header = Table([[[title, subtitle]]], colWidths=[540])

    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(header)

    divider = Table([[""]], colWidths=[540], rowHeights=[2])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2563eb"))]))
    elements.append(divider)
    elements.append(Spacer(1, 12))

    elements.append(
        Paragraph(label_paragraph(t("pdf_generated"), report_data.get("Timestamp", "")), body_style)
    )
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(xml_escape(shp(t("pdf_patient"))), heading_style))

    patient_info = make_rows(
        [
            (t("pdf_name"), f"{report_data.get('First name', '')} {report_data.get('Last name', '')}"),
            (t("pdf_age_gender"), f"{report_data.get('Age', '')} / {report_data.get('Gender', '')}"),
            (t("phone"), report_data.get("Phone", "")),
            (t("pdf_email"), report_data.get("Email", t("na"))),
            (t("pdf_address"), report_data.get("Address", "")),
            (t("pdf_type"), report_data.get("Reported diabetes type", "")),
        ]
    )

    label_col = 1 if rtl else 0
    t1 = Table(patient_info, colWidths=[410, 130] if rtl else [130, 410])
    t1.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("BACKGROUND", (label_col, 0), (label_col, -1), colors.HexColor("#f0f4f8")),
                ("FONTNAME", (label_col, 0), (label_col, -1), font_bold),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT" if rtl else "LEFT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ]
        )
    )
    elements.append(t1)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(xml_escape(shp(t("pdf_clinical"))), heading_style))
    elements.append(Paragraph(flow(report_data.get("Symptom narrative", "")), body_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(xml_escape(shp(t("pdf_assessment"))), heading_style))
    result_color = colors.HexColor("#dc2626") if is_high else colors.HexColor("#16a34a")

    result_rows = make_rows(
        [
            (t("pdf_risk"), report_data.get("Result", "")),
            (t("probability"), report_data.get("Probability", "")),
            (t("pdf_extra"), report_data.get("Notable extra symptoms", "")),
        ]
    )
    label_col2 = 1 if rtl else 0
    value_col2 = 0 if rtl else 1

    t2 = Table(result_rows, colWidths=[370, 170] if rtl else [170, 370])
    t2.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("FONTNAME", (label_col2, 0), (label_col2, -1), font_bold),
                ("TEXTCOLOR", (value_col2, 0), (value_col2, 0), result_color),
                ("FONTNAME", (value_col2, 0), (value_col2, 0), font_bold),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT" if rtl else "LEFT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ]
        )
    )
    elements.append(t2)
    elements.append(Spacer(1, 18))

    if rtl:
        disclaimer_text = flow(f"{t('pdf_disclaimer_label')}: {t('pdf_disclaimer')}")
    else:
        disclaimer_text = (
            f"<b>{xml_escape(t('pdf_disclaimer_label'))}:</b> {xml_escape(t('pdf_disclaimer'))}"
        )
    elements.append(Paragraph(disclaimer_text, body_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# =============================================================================
# Storage
# =============================================================================

def save_report_to_excel(report: dict):
    new_row = pd.DataFrame([report])

    if os.path.exists(SAVE_FILE_XLSX):
        try:
            existing = pd.read_excel(SAVE_FILE_XLSX, engine="openpyxl")
            combined = pd.concat([existing, new_row], ignore_index=True)
        except Exception:
            combined = new_row
    else:
        combined = new_row

    combined.to_excel(SAVE_FILE_XLSX, index=False, engine="openpyxl")


# =============================================================================
# Main app
# =============================================================================

def render_main_app():
    lang = st.session_state["lang"]

    st.markdown(
        f"""
        <div class="hero">
            <div class="pill">🤖 {tr('readiness')} • {tr('model_status')}</div>
            <h1>{tr('assessment')}</h1>
            <p>{tr('assessment_intro')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="status-card">🔐 {tr("privacy")}</div>',
        unsafe_allow_html=True,
    )

    with st.form("patient_form", clear_on_submit=False):
        st.markdown(f'<div class="section-title">👤 {tr("personal")}</div>', unsafe_allow_html=True)
        st.markdown("<div class='section-subtitle'></div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            first_name = st.text_input(f"{tr('first_name')} *")
        with c2:
            last_name = st.text_input(f"{tr('last_name')} *")

        phone = st.text_input(f"{tr('phone')} *")
        address = st.text_input(f"{tr('address')} *")

        # Email is optional and lives inside a collapsible section.
        with st.expander(f"➕ {tr('optional_info')}"):
            patient_email = st.text_input(
                tr("email_optional"),
                value=st.session_state.get("user_email") or "",
                placeholder="you@example.com",
            )

        diabetes_type = st.selectbox(
            tr("diabetes_type"),
            [tr(k) for k in DIABETES_TYPE_KEYS],
        )

        st.markdown("---")
        st.markdown(f'<div class="section-title">📋 {tr("basic")}</div>', unsafe_allow_html=True)

        c5, c6 = st.columns(2)
        with c5:
            age = st.number_input(tr("age"), min_value=1, max_value=120, value=40, step=1)
        with c6:
            gender_label = st.selectbox(tr("gender"), [tr("male"), tr("female")])
            gender = "Male" if gender_label == tr("male") else "Female"

        st.markdown("---")
        st.markdown(f'<div class="section-title">🩺 {tr("core")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{tr("core_help")}</div>', unsafe_allow_html=True)

        symptom_values = {}
        s_col1, s_col2 = st.columns(2)

        for i, col in enumerate(binary_columns):
            key = display_labels.get(col, col)
            label = tr(key)
            target_col = s_col1 if i % 2 == 0 else s_col2
            with target_col:
                selected = st.selectbox(
                    label,
                    [tr("no"), tr("yes")],
                    key=f"core_{col}",
                )
                symptom_values[col] = "Yes" if selected == tr("yes") else "No"

        st.markdown("---")
        st.markdown(f'<div class="section-title">➕ {tr("additional")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{tr("optional")}</div>', unsafe_allow_html=True)

        extra_values = {}
        e_col1, e_col2 = st.columns(2)

        for i, key in enumerate(extra_symptom_keys):
            target_col = e_col1 if i % 2 == 0 else e_col2
            with target_col:
                selected = st.selectbox(
                    tr(key),
                    [tr("no"), tr("yes")],
                    key=f"extra_{key}",
                )
                extra_values[key] = "Yes" if selected == tr("yes") else "No"

        submitted = st.form_submit_button(
            f"🔍 {tr('predict')}",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        clean_first_name = first_name.strip()
        clean_last_name = last_name.strip()
        clean_phone = phone.strip()
        clean_address = address.strip()
        clean_email = patient_email.strip()

        errors = []
        for value, label in [
            (clean_first_name, tr("first_name")),
            (clean_last_name, tr("last_name")),
            (clean_phone, tr("phone")),
            (clean_address, tr("address")),
        ]:
            if not value:
                errors.append(f"{label} {tr('required')}")

        # Email is optional: validate the format only if the user typed one.
        if clean_email and not EMAIL_REGEX.match(clean_email):
            errors.append(tr("email_invalid"))

        if errors:
            st.error(tr("required_fields"))
            for error in errors:
                st.warning(error)
        else:
            raw_input = {"Age": age, "Gender": gender, **symptom_values}
            result, probability = predict_new_patient(raw_input)

            type_key = DIABETES_TYPE_KEYS[[tr(k) for k in DIABETES_TYPE_KEYS].index(diabetes_type)]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            report_args = dict(
                timestamp=timestamp,
                first=clean_first_name,
                last=clean_last_name,
                phone=clean_phone,
                email=clean_email,
                address=clean_address,
                type_key=type_key,
                age=age,
                gender=gender,
                result=result,
                probability=probability,
                symptom_values=symptom_values,
                extra_values=extra_values,
            )

            # Shown to the user (current language) ...
            st.session_state["last_report"] = build_report(lang, **report_args)
            # ... and the same record in English, so the admin Excel file stays consistent.
            st.session_state["last_report_en"] = build_report("en", **report_args)

            st.session_state["last_extra"] = any(v == "Yes" for v in extra_values.values())
            st.session_state["last_result"] = int(result)
            st.session_state["last_probability"] = float(probability)
            st.session_state["report_saved"] = False

            components.html(
                """
                <script>
                window.parent.scrollTo({top: 0, behavior: 'smooth'});
                </script>
                """,
                height=0,
            )

    # Results
    if st.session_state.get("last_report"):
        report = st.session_state["last_report"]
        report_en = st.session_state["last_report_en"]
        result = st.session_state["last_result"]
        probability = st.session_state["last_probability"]

        st.markdown("---")
        st.markdown(f'<div class="section-title">📊 {tr("result")}</div>', unsafe_allow_html=True)

        css_class = "result-high" if result == 1 else "result-low"
        title = tr("high_risk") if result == 1 else tr("low_risk")

        st.markdown(
            f"""
            <div class="result-card {css_class}">
                <div class="result-label">{tr('result')}</div>
                <div class="result-title">{'⚠️' if result == 1 else '✅'} {title}</div>
                <div class="score">{probability * 100:.1f}%</div>
                <div class="score-caption">{tr('probability')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.progress(min(max(probability, 0.0), 1.0))

        with st.expander(f"🩺 {tr('symptom_summary')}", expanded=True):
            st.write(report.get("Symptom narrative", ""))

        with st.expander(f"💡 {tr('recommendation')}", expanded=True):
            if result == 1:
                st.warning(tr("high_recommendation"))
            else:
                st.success(tr("low_recommendation"))

            if st.session_state.get("last_extra", False):
                st.info(tr("extra_notice"))

        render_offline_health_guide()

        if not st.session_state.get("report_saved", False):
            try:
                save_report_to_excel(report_en)
                st.session_state["report_saved"] = True
            except Exception as exc:
                st.warning(f"{tr('save_failed')} {exc}")

        st.markdown("---")
        st.markdown(f'<div class="section-title">📄 {tr("download")}</div>', unsafe_allow_html=True)

        pdf_lang = pick_pdf_language(lang)
        pdf_report = report if pdf_lang == lang else report_en
        pdf_data = generate_pdf_report(pdf_report, pdf_lang, is_high=(result == 1))

        if pdf_lang != lang:
            st.caption(tr("pdf_fallback"))

        file_name_pdf = (
            f"Diabetes_Report_{report['First name']}_{report['Last name']}.pdf"
            .replace(" ", "_")
        )

        st.download_button(
            label=f"📥 {tr('download_pdf')}",
            data=pdf_data,
            file_name=file_name_pdf,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )

        st.markdown(
            f'<div class="notice">⚠️ {tr("medical_notice_long")}</div>',
            unsafe_allow_html=True,
        )


# =============================================================================
# Admin
# =============================================================================

def render_admin_page():
    st.markdown(
        f"""
        <div class="hero">
            <div class="pill">🔒 {tr('admin_title')}</div>
            <h1>{tr('admin_title')}</h1>
            <p>{tr('admin_help')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    admin_pw = st.text_input(tr("password"), type="password", key="admin_pw")

    if admin_pw:
        if admin_pw == ADMIN_PASSWORD:
            st.success(tr("access"))

            if os.path.exists(SAVE_FILE_XLSX):
                try:
                    history_df = pd.read_excel(SAVE_FILE_XLSX, engine="openpyxl")
                    st.dataframe(history_df, use_container_width=True, hide_index=True)

                    col_download, col_clean = st.columns(2)

                    with col_download:
                        with open(SAVE_FILE_XLSX, "rb") as f:
                            st.download_button(
                                tr("download_excel"),
                                data=f.read(),
                                file_name=SAVE_FILE_XLSX,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                            )

                    with col_clean:
                        if st.button(f"🗑️ {tr('clean')}", use_container_width=True):
                            st.session_state["confirm_clean"] = True

                    if st.session_state.get("confirm_clean", False):
                        st.warning(tr("confirm"))
                        col_yes, col_no = st.columns(2)

                        with col_yes:
                            if st.button(tr("delete"), type="primary", use_container_width=True):
                                try:
                                    os.remove(SAVE_FILE_XLSX)
                                    st.session_state["confirm_clean"] = False
                                    st.success(tr("deleted"))
                                    st.rerun()
                                except Exception as exc:
                                    st.error(str(exc))

                        with col_no:
                            if st.button(tr("cancel"), use_container_width=True):
                                st.session_state["confirm_clean"] = False
                                st.rerun()

                except Exception as exc:
                    st.warning(f"{tr('read_failed')} {exc}")
            else:
                st.info(tr("no_records"))
        else:
            st.error(tr("incorrect"))


# =============================================================================
# App router
# =============================================================================

def render_footer():
    st.markdown(
        f"""
        <div class="footer">
            🩺 {tr('brand')} · {tr('medical_notice')}
        </div>
        """,
        unsafe_allow_html=True,
    )


inject_css()

current_page = st.session_state["page"]

if current_page == "splash":
    render_splash()  # plays the animation, then opens the language gate
    st.stop()

if current_page == "language":
    render_language_gate()  # "Continue" or "Change language"
    render_footer()
    st.stop()

render_header()

if current_page == "admin":
    render_admin_page()
else:
    render_main_app()

render_footer()
