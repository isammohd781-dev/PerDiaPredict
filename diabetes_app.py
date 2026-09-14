import os
import re
from datetime import datetime
from io import BytesIO

import joblib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


# =============================================================================
# PERDIAPREDICT - POLISHED RESPONSIVE VERSION
# Language: English only
# =============================================================================

st.set_page_config(
    page_title="PerdiaPredict",
    page_icon="🩺",
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
# English-only text
# =============================================================================

T = {
    "en": {'brand': 'PerdiaPredict',
 'tagline': 'AI-powered early-stage diabetes screening',
 'language': 'Language',
 'admin': 'Admin Panel',
 'back': 'Back',
 'email_title': 'Early Stage Diabetes Screening',
 'email_intro': 'Enter your email address to start your assessment.',
 'email': 'Email address',
 'email_required': 'Email address is required.',
 'email_invalid': 'Please enter a valid email address.',
 'continue': 'Continue',
 'medical_notice': 'Educational screening only — this tool is not a medical diagnosis.',
 'medical_notice_long': 'This application is for educational and demonstration purposes only. It '
                        'does not replace a qualified healthcare professional or a clinical '
                        'diagnosis.',
 'assessment': 'Diabetes Risk Assessment',
 'assessment_intro': 'Complete the form below. Your answers are analyzed by the trained '
                     'machine-learning model.',
 'personal': 'Personal Information',
 'first_name': 'First name',
 'last_name': 'Last name',
 'phone': 'Phone number',
 'address': 'Residential address (city / area)',
 'diabetes_type': 'Which type of diabetes do you believe you have?',
 'not_sure': "Not sure / I don't know",
 'type1': 'Type 1',
 'type2': 'Type 2',
 'gestational': 'Gestational diabetes',
 'prediabetes': 'Prediabetes',
 'basic': 'Basic Information',
 'age': 'Age',
 'gender': 'Gender',
 'male': 'Male',
 'female': 'Female',
 'core': 'Core Symptoms',
 'core_help': 'Please select Yes or No for every symptom.',
 'yes': 'Yes',
 'no': 'No',
 'additional': 'Additional Symptoms',
 'optional': 'Optional — these symptoms enrich the report but do not directly change the model '
             'probability.',
 'predict': 'Predict My Risk',
 'required_fields': 'Please complete the required fields.',
 'required': 'is required.',
 'result': 'Assessment Result',
 'high_risk': 'High risk of early-stage diabetes',
 'low_risk': 'Low risk of early-stage diabetes',
 'probability': 'Estimated probability',
 'symptom_summary': 'Symptoms Summary',
 'recommendation': 'Recommendation',
 'high_recommendation': 'Because the estimated risk is high, please arrange a medical evaluation. '
                        'Do not use this screening as a substitute for professional diagnosis.',
 'low_recommendation': 'The current screening result is low risk. Continue healthy habits and '
                       'speak with a healthcare professional if symptoms persist or concern you.',
 'extra_notice': 'Some additional symptoms were selected. If they persist, consider speaking with '
                 'a healthcare professional.',
 'health_guide': 'Healthy Lifestyle & Nutrition Guide',
 'offline': 'Built into the app — no external website is required.',
 'plate': 'Healthy Plate Method',
 'foods': 'Foods to Prefer',
 'limit': 'Foods & Drinks to Limit',
 'habits': 'Daily Lifestyle Habits',
 'meal_plan': 'Weekly Meal Plan',
 'tips': 'General Health Tips',
 'download': 'Download Assessment Report',
 'download_pdf': 'Download PDF Report',
 'saved': 'Report saved successfully.',
 'admin_title': 'Admin Panel',
 'admin_help': 'Restricted area for viewing submitted assessment records.',
 'password': 'Admin password',
 'access': 'Access granted.',
 'incorrect': 'Incorrect password.',
 'no_records': 'No saved records yet.',
 'download_excel': 'Download Excel file',
 'clean': 'Clean Data',
 'confirm': 'Are you sure you want to delete all saved records? This action cannot be undone.',
 'delete': 'Yes, Delete Data',
 'cancel': 'Cancel',
 'deleted': 'All data cleared successfully.',
 'readiness': 'Ready',
 'model_status': 'Machine-learning model loaded',
 'privacy': 'Your information is used only by this application for the assessment/report workflow.',
 'patient_denies': 'The patient denies all core and additional symptoms assessed in this '
                   'screening.',
 'patient_reports': 'The patient reports',
 'further': 'On further questioning, the patient also endorses',
 'no_core': 'The patient denies any of the core symptoms assessed in this screening.',
 'constant_fatigue': 'Constant fatigue / tiredness',
 'blurry_vision': 'Blurry or unclear vision',
 'frequent_infections': 'Frequent infections (skin / gum / urinary)',
 'tingling_numbness': 'Tingling or numbness in hands or feet',
 'polyuria': 'Polyuria (excessive urination)',
 'polydipsia': 'Polydipsia (excessive thirst)',
 'weight_loss': 'Sudden weight loss',
 'irritability': 'Irritability',
 'healing': 'Delayed wound healing',
 'paresis': 'Partial paresis (partial muscle weakness)',
 'alopecia': 'Alopecia (abnormal hair loss)',
 'itching': 'Itching'},
}


def tr(key: str) -> str:
    return T["en"].get(key, key)


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
}

DIABETES_TYPE_KEYS = ["not_sure", "type1", "type2", "gestational", "prediabetes"]


# =============================================================================
# Responsive / modern UI
# =============================================================================

def inject_css():
    direction = "ltr"
    is_dark = st.session_state.get("dark_mode", True)

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
        theme_vars = """
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --text: #172033;
            --muted: #64748b;
            --surface: #ffffff;
            --surface-2: #f8fafc;
            --surface-soft: #f1f5f9;
            --border: #e2e8f0;
            --input: #ffffff;
            --success: #16a34a;
            --danger: #dc2626;
            --warning-bg: #fffbeb;
            --warning-border: #fde68a;
            --warning-text: #713f12;
            --info-bg: #eff6ff;
            --info-border: #dbeafe;
            --info-text: #1e40af;
            --shadow: 0 10px 35px rgba(15,23,42,.08);
        """
        page_bg = "#f6f8fc"

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
                         "Noto Sans", Arial, sans-serif;
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
                var(--surface-soft) !important;
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

        /* Header */
        .brand {{
            min-width: 0 !important;
        }}

        /* Prevent the page from becoming wider than the browser window. */
        html, body, .stApp, [data-testid="stAppViewContainer"] {{
            max-width: 100% !important;
            overflow-x: hidden !important;
        }}

        /* Streamlit top bar / toolbar */
        header[data-testid="stHeader"] {{
            background: color-mix(in srgb, var(--surface-soft) 88%, transparent) !important;
            color: var(--text) !important;
        }}

        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {{
            color: var(--text) !important;
        }}

        /* Brand */
        .brand {{
            display:flex;
            align-items:center;
            gap:12px;
            padding:8px 2px 2px;
        }}

        .brand-icon {{
            width:48px;
            height:48px;
            border-radius:15px;
            display:flex;
            align-items:center;
            justify-content:center;
            background:linear-gradient(135deg,#2563eb,#0ea5e9);
            color:white !important;
            font-size:25px;
            box-shadow:0 8px 22px rgba(37,99,235,.25);
        }}

        .brand-name {{
            font-size:1.15rem;
            font-weight:800;
            letter-spacing:-.02em;
            color:var(--text) !important;
        }}

        .brand-tagline {{
            font-size:.78rem;
            color:var(--muted) !important;
            margin-top:1px;
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

        /* Inputs */
        input, textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        [data-testid="stNumberInput"] input,
        [data-testid="stTextInput"] input {{
            background:var(--input) !important;
            color:var(--text) !important;
            border:1px solid var(--border) !important;
            border-radius:12px !important;
            caret-color:var(--primary) !important;
        }}

        input::placeholder,
        textarea::placeholder {{
            color:#64748b !important;
            opacity:1 !important;
        }}

        input:focus, textarea:focus,
        div[data-baseweb="select"] > div:focus-within {{
            border-color:var(--primary) !important;
            box-shadow:0 0 0 2px rgba(96,165,250,.18) !important;
        }}

        /* Selectbox text + dropdown */
        [data-baseweb="select"] *,
        [role="listbox"] *,
        [role="option"] {{
            color:var(--text) !important;
        }}

        div[data-baseweb="popover"],
        div[data-baseweb="menu"],
        [role="listbox"] {{
            background:var(--surface) !important;
            border:1px solid var(--border) !important;
            color:var(--text) !important;
        }}

        [role="option"]:hover,
        [role="option"][aria-selected="true"] {{
            background:var(--surface-2) !important;
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

        /* Expanders */
        .stExpander,
        [data-testid="stExpander"] {{
            border-radius:16px !important;
            border:1px solid var(--border) !important;
            background:var(--surface) !important;
            color:var(--text) !important;
        }}

        .stExpander details,
        .stExpander summary {{
            background:var(--surface) !important;
            color:var(--text) !important;
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

        /* Mobile-only adjustments. Desktop is intentionally unchanged. */
        @media (max-width: 640px) {{
            .block-container {{
                width: 100% !important;
                max-width: 100% !important;
                box-sizing: border-box !important;
                padding: 2.60rem 0.65rem 2.5rem !important;
                overflow-x: hidden !important;
            }}

            /* The header is the first Streamlit horizontal block on the page.
               On phones: brand gets the full first row, controls share row two. */
            [data-testid="stHorizontalBlock"]:has(.brand) {{
                width: 100% !important;
                display: flex !important;
                flex-wrap: wrap !important;
                gap: 8px !important;
                align-items: center !important;
            }}

            [data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"] {{
                min-width: 0 !important;
                flex: 0 0 auto !important;
            }}

            [data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"]:first-child {{
                flex: 0 0 100% !important;
                width: 100% !important;
                max-width: 100% !important;
            }}

            [data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"]:nth-child(2),
            [data-testid="stHorizontalBlock"]:has(.brand) > [data-testid="stColumn"]:nth-child(3) {{
                flex: 1 1 calc(50% - 4px) !important;
                width: calc(50% - 4px) !important;
                max-width: calc(50% - 4px) !important;
            }}

            .brand {{
                padding: 4px 2px 4px !important;
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

            /* Mobile-only theme toggle: clear and visible in light mode. */
            [data-testid="stToggle"] {{
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                gap: 6px !important;
                min-height: 44px !important;
                border-radius: 14px !important;
                background: var(--surface) !important;
                border: 1px solid var(--border) !important;
                box-shadow: 0 3px 10px rgba(15,23,42,.08) !important;
                color: var(--text) !important;
                width: 100% !important;
                min-height: 44px !important;
                box-sizing: border-box !important;
                padding: 4px 6px !important;
            }}

            [data-testid="stToggle"] label,
            [data-testid="stToggle"] label * {{
                color: var(--text) !important;
                -webkit-text-fill-color: var(--text) !important;
                font-weight: 700 !important;
                opacity: 1 !important;
                visibility: visible !important;
            }}

            [data-testid="stToggle"] [role="switch"] {{
                width: 44px !important;
                min-width: 44px !important;
                height: 24px !important;
                opacity: 1 !important;
            }}

            [data-testid="stToggle"] label {{
                white-space: nowrap !important;
                font-size: 0.88rem !important;
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
        }}
        </style>
        <script>
        const root = window.parent.document.documentElement;
        root.setAttribute("dir", "{direction}");
        </script>
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
        st.error(
            "Missing required file(s): "
            + ", ".join(missing)
            + ". Put the model files in the same folder as the Streamlit app."
        )
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

st.session_state["lang"] = "en"
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = True
if "page" not in st.session_state:
    st.session_state["page"] = "email_gate"
if "user_email" not in st.session_state:
    st.session_state["user_email"] = None
if "last_report" not in st.session_state:
    st.session_state["last_report"] = None
if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "last_probability" not in st.session_state:
    st.session_state["last_probability"] = 0.0


def go_to(page_name: str):
    st.session_state["page"] = page_name
    st.rerun()


# =============================================================================
# Header
# =============================================================================

def render_header():
    # Desktop keeps the original 3-column layout.
    # Mobile CSS below rearranges these same columns without changing desktop.
    left, theme_col, right = st.columns([3.0, 1.0, 1.45], vertical_alignment="center")

    with left:
        st.markdown(
            f"""
            <div class="brand">
                <div class="brand-icon">🩺</div>
                <div>
                    <div class="brand-name">{tr('brand')}</div>
                    <div class="brand-tagline">{tr('tagline')}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with theme_col:
        st.toggle(
            "🌙 Dark / ☀️ Light",
            value=st.session_state.get("dark_mode", True),
            key="dark_mode",
        )

    with right:
        if st.session_state["page"] == "admin":
            if st.button(f"⬅️ {tr('back')}", use_container_width=True):
                go_to("main" if st.session_state["user_email"] else "email_gate")
        else:
            if st.button(f"🔒 {tr('admin')}", use_container_width=True):
                go_to("admin")


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
# Symptom narrative
# =============================================================================

def _join(items):
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def build_symptom_narrative(symptom_values: dict, extra_values: dict) -> str:
    lang = "en"

    core_keys = {
        "Polyuria": "polyuria",
        "Polydipsia": "polydipsia",
        "sudden weight loss": "weight_loss",
        "Irritability": "irritability",
        "delayed healing": "healing",
        "partial paresis": "paresis",
        "Alopecia": "alopecia",
        "Itching": "itching",
    }

    core_yes = [T["en"][key] for col, key in core_keys.items() if symptom_values.get(col) == "Yes"]
    extra_yes = [T["en"][key] for key in extra_symptom_keys if extra_values.get(key) == "Yes"]

    if not core_yes and not extra_yes:
        return tr("patient_denies")

    sentences = []
    if core_yes:
        sentences.append(tr("patient_reports") + " " + _join(core_yes) + ".")
    else:
        sentences.append(tr("no_core"))

    if extra_yes:
        sentences.append(tr("further") + " " + _join(extra_yes) + ".")

    return " ".join(sentences)


# =============================================================================
# Health guide
# =============================================================================

def render_meal_plan():
    st.markdown(f'<div class="section-title">📅 {tr("meal_plan")}</div>', unsafe_allow_html=True)

    plans = [
        ["Saturday", "Boiled eggs + whole-grain bread + cucumber & tomato", "Grilled chicken + brown rice + green salad", "Grilled fish + vegetables", "Water / unsweetened tea"],
        ["Sunday", "Oatmeal + low-fat milk + berries", "Lentil soup + fresh salad", "Lean grilled meat + vegetables", "Water / mint tea"],
        ["Monday", "Plain yogurt + whole-grain cereal + nuts", "Tuna salad + whole-grain bread", "Stuffed peppers/zucchini + small rice portion", "Water / herbal tea"],
        ["Tuesday", "Vegetable omelet + whole-grain bread", "Chicken + quinoa/bulgur + salad", "Vegetable soup + low-fat cheese", "Water / green tea"],
        ["Wednesday", "Greek yogurt + chia + low-sugar fruit", "Grilled fish + leafy salad", "Lentils/chickpeas + vegetables", "Water / hibiscus tea"],
        ["Thursday", "Whole-grain bread + low-fat cheese + vegetables", "Lean meat/chicken + vegetables + brown rice", "Large salad + chicken/tuna", "Water / mint tea"],
        ["Friday", "Oatmeal or eggs + raw nuts", "Fish/chicken + vegetables + salad", "Light vegetable soup + cheese", "Water / herbal tea"],
    ]


    df = pd.DataFrame(
        plans,
        columns=[tr("meal_plan"), "Breakfast", "Lunch", "Dinner", "Drinks"],
    )
    df[tr("meal_plan")] = [row[0] for row in plans]
    st.dataframe(df, use_container_width=True, hide_index=True)


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
        st.markdown(
            "- **½** vegetables\n"
            "- **¼** lean protein\n"
            "- **¼** whole grains or moderate starch\n"
            "- Water or unsweetened drinks instead of sugary drinks"
        )

    with st.expander(f"🥗 {tr('foods')}"):
        st.markdown(
            "- Vegetables and salads\n"
            "- Beans, lentils and chickpeas\n"
            "- Whole grains and high-fiber foods\n"
            "- Fish, skinless chicken and lean proteins\n"
            "- Plain / low-sugar yogurt\n"
            "- Small portions of nuts\n"
            "- Whole fruit in moderate portions rather than juice"
        )

    with st.expander(f"⚠️ {tr('limit')}"):
        st.markdown(
            "- Sugary soft drinks and packaged juices\n"
            "- Added sugar and very sweet desserts\n"
            "- Large portions of refined white bread/rice\n"
            "- Highly processed foods\n"
            "- Very large meals or unnecessary snacking"
        )

    with st.expander(f"🏃 {tr('habits')}"):
        st.markdown(
            "- Aim for regular physical activity appropriate for your health.\n"
            "- Keep consistent meal times.\n"
            "- Stay hydrated.\n"
            "- If you monitor blood glucose, follow your healthcare professional's advice.\n"
            "- Seek professional advice for persistent or concerning symptoms."
        )

    with st.expander(f"📅 {tr('meal_plan')}"):
        render_meal_plan()


# =============================================================================
# PDF
# =============================================================================

def generate_pdf_report(report_data: dict) -> bytes:
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
        fontSize=18,
        textColor=colors.HexColor("#0d3b66"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#555555"),
    )
    heading_style = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#0d3b66"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
    )

    elements = []
    title = Paragraph("<b>PERDIAPREDICT</b>", title_style)
    subtitle = Paragraph("Early Stage Diabetes Assessment Report", subtitle_style)

    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=55, height=55)
        header = Table([[logo, [title, subtitle]]], colWidths=[70, 470])
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

    elements.append(Paragraph(f"<b>Generated:</b> {report_data.get('Timestamp', '')}", body_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Patient Details", heading_style))

    patient_info = [
        ["Name:", f"{report_data.get('First name', '')} {report_data.get('Last name', '')}"],
        ["Age / Gender:", f"{report_data.get('Age', '')} / {report_data.get('Gender', '')}"],
        ["Phone:", report_data.get("Phone", "")],
        ["Email:", report_data.get("Email", "N/A")],
        ["Address:", report_data.get("Address", "")],
        ["Reported Type:", report_data.get("Reported diabetes type", "")],
    ]

    t1 = Table(patient_info, colWidths=[130, 410])
    t1.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f4f8")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ]
        )
    )
    elements.append(t1)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Clinical Presentation", heading_style))
    elements.append(Paragraph(report_data.get("Symptom narrative", ""), body_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Assessment Result", heading_style))
    is_positive = "Positive" in report_data.get("Result", "")
    result_color = colors.HexColor("#dc2626") if is_positive else colors.HexColor("#16a34a")

    t2 = Table(
        [
            ["Risk Assessment:", report_data.get("Result", "")],
            ["Estimated Probability:", report_data.get("Probability", "")],
            ["Additional Symptoms:", report_data.get("Notable extra symptoms", "")],
        ],
        colWidths=[170, 370],
    )
    t2.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (1, 0), (1, 0), result_color),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ]
        )
    )
    elements.append(t2)
    elements.append(Spacer(1, 18))

    elements.append(
        Paragraph(
            "<b>Disclaimer:</b> This report is generated by a machine-learning model for educational and demonstration purposes only. It is NOT a medical diagnosis. Consult a qualified healthcare professional for clinical evaluation.",
            body_style,
        )
    )

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
# Email screen
# =============================================================================

def render_email_gate():
    st.markdown(
        f"""
        <div class="hero">
            <div class="pill">🩺 {tr('brand')}</div>
            <h1>{tr('email_title')}</h1>
            <p>{tr('email_intro')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="notice">⚠️ {tr("medical_notice_long")}</div>',
        unsafe_allow_html=True,
    )

    # Keep the email gate outside a Streamlit form.
    # This makes the Continue button respond reliably after theme/CSS changes.
    email_input = st.text_input(
        tr("email"),
        value=st.session_state.get("user_email") or "",
        placeholder="you@example.com",
        key="email_gate_input",
    )

    continue_clicked = st.button(
        f"🚀 {tr('continue')}",
        use_container_width=True,
        type="primary",
        key="email_continue_button",
    )

    if continue_clicked:
        cleaned_email = email_input.strip()
        if not cleaned_email:
            st.error(tr("email_required"))
        elif not EMAIL_REGEX.match(cleaned_email):
            st.error(tr("email_invalid"))
        else:
            st.session_state["user_email"] = cleaned_email
            go_to("main")


# =============================================================================
# Main app
# =============================================================================

def render_main_app():
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

        c3, c4 = st.columns(2)
        with c3:
            phone = st.text_input(f"{tr('phone')} *")
        with c4:
            patient_email = st.text_input(
                tr("email"),
                value=st.session_state.get("user_email", ""),
            )

        address = st.text_input(f"{tr('address')} *")

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

        if errors:
            st.error(tr("required_fields"))
            for error in errors:
                st.warning(error)
        else:
            raw_input = {"Age": age, "Gender": gender, **symptom_values}
            result, probability = predict_new_patient(raw_input)

            any_extra_symptom = any(v == "Yes" for v in extra_values.values())
            symptom_narrative = build_symptom_narrative(symptom_values, extra_values)

            type_key = DIABETES_TYPE_KEYS[[tr(k) for k in DIABETES_TYPE_KEYS].index(diabetes_type)]

            st.session_state["last_report"] = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "First name": clean_first_name,
                "Last name": clean_last_name,
                "Phone": clean_phone,
                "Email": clean_email if clean_email else "N/A",
                "Address": clean_address,
                "Reported diabetes type": tr(type_key),
                "Age": age,
                "Gender": tr("male") if gender == "Male" else tr("female"),
                "Result": "Positive (high risk)" if result == 1 else "Negative (low risk)",
                "Probability": f"{probability * 100:.1f}%",
                "Notable extra symptoms": "Yes" if any_extra_symptom else "No",
                "Symptom narrative": symptom_narrative,
            }

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

            if report["Notable extra symptoms"] == "Yes":
                st.info(tr("extra_notice"))

        render_offline_health_guide()

        if not st.session_state.get("report_saved", False):
            try:
                save_report_to_excel(report)
                st.session_state["report_saved"] = True
            except Exception as exc:
                st.warning(f"Could not save the report: {exc}")

        st.markdown("---")
        st.markdown(f'<div class="section-title">📄 {tr("download")}</div>', unsafe_allow_html=True)

        pdf_data = generate_pdf_report(report)
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
                    st.warning(f"Could not read saved records: {exc}")
            else:
                st.info(tr("no_records"))
        else:
            st.error(tr("incorrect"))


# =============================================================================
# App router
# =============================================================================

inject_css()
render_header()

current_page = st.session_state["page"]

if current_page == "admin":
    render_admin_page()
elif current_page == "email_gate":
    render_email_gate()
else:
    render_main_app()

st.markdown(
    f"""
    <div class="footer">
        🩺 {tr('brand')} · {tr('medical_notice')}
    </div>
    """,
    unsafe_allow_html=True,
)
