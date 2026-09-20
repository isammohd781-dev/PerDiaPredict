import base64
import os
import re
import shutil
import tempfile
import time
import urllib.request
from datetime import datetime

import joblib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from fpdf import FPDF

from translations import LANGUAGES, T

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


# -----------------------------------------------------------------------------
# Gender-specific questions + urination frequency.
# The texts live here (English / Arabic / Spanish); any other language falls
# back to English automatically (see tr()). To translate them, copy the keys
# below into translations.py.
# These answers are added to the report for the doctor; they are NOT features of
# the trained model, so they do not change the estimated probability.
# -----------------------------------------------------------------------------
POLYURIA_FREQ_KEYS = ["freq_8_10", "freq_11_15", "freq_15_plus", "freq_unsure"]

MALE_SYMPTOM_KEYS = [
    "male_erectile", "male_libido", "male_muscle", "male_genital_itch", "male_fertility",
]
FEMALE_SYMPTOM_KEYS = [
    "female_yeast", "female_uti", "female_periods", "female_hair", "female_dryness", "female_gdm",
]

# Sensitive questions (sexual health / fertility / past pregnancy). They are only
# asked when the patient is or has been married; someone who never married only
# gets the general questions above.
MALE_INTIMATE_KEYS = ["male_erectile", "male_libido", "male_fertility"]
FEMALE_INTIMATE_KEYS = ["female_dryness", "female_gdm"]


def gender_question_keys(gender: str, ever_married: bool) -> list:
    """Questions to show for this gender (all of them only if ever married)."""
    keys = MALE_SYMPTOM_KEYS if gender == "Male" else FEMALE_SYMPTOM_KEYS
    if ever_married:
        return list(keys)
    intimate = MALE_INTIMATE_KEYS if gender == "Male" else FEMALE_INTIMATE_KEYS
    return [k for k in keys if k not in intimate]


# -----------------------------------------------------------------------------
# Marital status, gender-agreeing.
#
# "status" is one of: single / married / divorced / child. "child" is not a
# marital status at all - it lets a parent fill in the form for a child
# patient, which then shows pediatric questions instead of the adult
# male/female section below.
#
# Each label is written separately for a male ("Male") and a female
# ("Female") patient so Arabic (and Spanish) agree in gender, e.g.
# "أعزب" vs "عزباء", "متزوج" vs "متزوجة", "طفل" vs "طفلة". English does not
# need two forms, so the same text is reused for both.
# -----------------------------------------------------------------------------
MARITAL_STATUS_ORDER = ["single", "married", "divorced", "child"]

MARITAL_STATUS_TEXT = {
    "en": {
        "single": {"Male": "Single (never married)", "Female": "Single (never married)"},
        "married": {"Male": "Married", "Female": "Married"},
        "divorced": {"Male": "Divorced or widowed", "Female": "Divorced or widowed"},
        "child": {"Male": "Child", "Female": "Child"},
    },
    "ar": {
        "single": {"Male": "أعزب", "Female": "عزباء"},
        "married": {"Male": "متزوج", "Female": "متزوجة"},
        "divorced": {"Male": "مطلّق أو أرمل", "Female": "مطلّقة أو أرملة"},
        "child": {"Male": "طفل", "Female": "طفلة"},
    },
    "es": {
        "single": {"Male": "Soltero", "Female": "Soltera"},
        "married": {"Male": "Casado", "Female": "Casada"},
        "divorced": {"Male": "Divorciado o viudo", "Female": "Divorciada o viuda"},
        "child": {"Male": "Niño", "Female": "Niña"},
    },
}


def marital_status_label(status: str, gender: str, lang: str = None) -> str:
    """Gender-agreeing label for a marital-status option, with an English fallback
    for languages that have not been given their own wording yet."""
    lang = lang or st.session_state.get("lang", "en")
    gender = gender if gender in ("Male", "Female") else "Male"
    table = MARITAL_STATUS_TEXT.get(lang) or MARITAL_STATUS_TEXT["en"]
    entry = table.get(status) or MARITAL_STATUS_TEXT["en"][status]
    return entry.get(gender, entry.get("Male", ""))


# -----------------------------------------------------------------------------
# Pediatric questions, shown instead of the adult male/female section whenever
# the marital status is "child". They are informational only (like the adult
# gender-specific questions) and do not change the estimated probability.
# -----------------------------------------------------------------------------
CHILD_COMMON_SYMPTOM_KEYS = [
    "child_bedwetting", "child_growth", "child_fatigue_school", "child_skin_infections",
]
CHILD_BOY_EXTRA_KEYS: list = []
CHILD_GIRL_EXTRA_KEYS = ["child_yeast"]


def child_question_keys(gender: str) -> list:
    """Pediatric questions for this child, by their gender."""
    extra = CHILD_GIRL_EXTRA_KEYS if gender == "Female" else CHILD_BOY_EXTRA_KEYS
    return list(CHILD_COMMON_SYMPTOM_KEYS) + list(extra)

EXTRA_TEXT = {
    "en": {
        "freq_8_10": "8-10 times a day",
        "freq_11_15": "11-15 times a day",
        "freq_15_plus": "more than 15 times a day",
        "freq_unsure": "not sure how many times",
        "gender_hint": "Choose your gender and marital status: the questions below adapt to them.",
        "marital_status": "Marital status",
        "male_section": "Symptoms specific to men",
        "female_section": "Symptoms specific to women",
        "child_section": "Questions specific to children",
        "gender_section_help": "These answers are added to your report to help your doctor. They do not change the estimated probability.",
        "male_erectile": "Difficulty getting or keeping an erection",
        "male_libido": "Reduced sex drive",
        "male_muscle": "Loss of muscle mass or strength",
        "male_genital_itch": "Repeated itching, redness or infection of the genitals",
        "male_fertility": "Fertility problems (difficulty having children)",
        "female_yeast": "Recurrent vaginal yeast infections",
        "female_uti": "Frequent urinary tract infections",
        "female_periods": "Irregular menstrual periods",
        "female_hair": "Excess facial or body hair",
        "female_dryness": "Vaginal dryness or painful intercourse",
        "female_gdm": "Diabetes during a previous pregnancy",
        "child_bedwetting": "New bedwetting after being previously toilet-trained",
        "child_growth": "Poor weight gain or slowed growth",
        "child_fatigue_school": "Unusual tiredness or trouble concentrating at school",
        "child_skin_infections": "Repeated skin infections or slow-healing sores",
        "child_yeast": "Recurrent yeast infections",
    },
    "ar": {
        "freq_8_10": "من 8 إلى 10 مرات في اليوم",
        "freq_11_15": "من 11 إلى 15 مرة في اليوم",
        "freq_15_plus": "أكثر من 15 مرة في اليوم",
        "freq_unsure": "لا أعرف عدد المرات",
        "gender_hint": "اختر الجنس والحالة الاجتماعية لتظهر لك الأسئلة المناسبة.",
        "marital_status": "الحالة الاجتماعية",
        "male_section": "أعراض خاصة بالرجال",
        "female_section": "أعراض خاصة بالنساء",
        "child_section": "أسئلة خاصة بالأطفال",
        "gender_section_help": "تُضاف هذه الإجابات إلى التقرير لمساعدة الطبيب، ولا تغيّر نسبة الاحتمال المقدَّرة.",
        "male_erectile": "صعوبة في الانتصاب أو الحفاظ عليه",
        "male_libido": "انخفاض الرغبة الجنسية",
        "male_muscle": "فقدان الكتلة أو القوة العضلية",
        "male_genital_itch": "حكة أو احمرار أو التهابات متكررة في المنطقة التناسلية",
        "male_fertility": "مشاكل في الخصوبة (صعوبة الإنجاب)",
        "female_yeast": "التهابات فطرية مهبلية متكررة",
        "female_uti": "التهابات متكررة في المسالك البولية",
        "female_periods": "عدم انتظام الدورة الشهرية",
        "female_hair": "زيادة شعر الوجه أو الجسم",
        "female_dryness": "جفاف مهبلي أو ألم أثناء الجماع",
        "female_gdm": "الإصابة بسكري الحمل في حمل سابق",
        "child_bedwetting": "التبول اللاإرادي المفاجئ بعد التحكم به سابقًا",
        "child_growth": "ضعف في زيادة الوزن أو تباطؤ في النمو",
        "child_fatigue_school": "تعب غير معتاد أو صعوبة في التركيز في المدرسة",
        "child_skin_infections": "التهابات جلدية متكررة أو بطء التئام الجروح",
        "child_yeast": "التهابات فطرية متكررة",
    },
    "es": {
        "freq_8_10": "de 8 a 10 veces al día",
        "freq_11_15": "de 11 a 15 veces al día",
        "freq_15_plus": "más de 15 veces al día",
        "freq_unsure": "no sé cuántas veces",
        "gender_hint": "Elige tu sexo y estado civil: las preguntas de abajo se adaptan a tu elección.",
        "marital_status": "Estado civil",
        "male_section": "Síntomas específicos de los hombres",
        "female_section": "Síntomas específicos de las mujeres",
        "child_section": "Preguntas específicas para niños",
        "gender_section_help": "Estas respuestas se añaden al informe para ayudar a tu médico. No modifican la probabilidad estimada.",
        "male_erectile": "Dificultad para lograr o mantener una erección",
        "male_libido": "Disminución del deseo sexual",
        "male_muscle": "Pérdida de masa o fuerza muscular",
        "male_genital_itch": "Picazón, enrojecimiento o infecciones repetidas en los genitales",
        "male_fertility": "Problemas de fertilidad (dificultad para tener hijos)",
        "female_yeast": "Infecciones vaginales por hongos recurrentes",
        "female_uti": "Infecciones urinarias frecuentes",
        "female_periods": "Menstruación irregular",
        "female_hair": "Exceso de vello en la cara o el cuerpo",
        "female_dryness": "Sequedad vaginal o dolor en las relaciones sexuales",
        "female_gdm": "Diabetes durante un embarazo anterior",
        "child_bedwetting": "Nuevos episodios de enuresis tras haber controlado esfínteres",
        "child_growth": "Poco aumento de peso o crecimiento más lento de lo normal",
        "child_fatigue_school": "Cansancio inusual o dificultad para concentrarse en la escuela",
        "child_skin_infections": "Infecciones cutáneas repetidas o heridas que sanan lentamente",
        "child_yeast": "Infecciones por hongos recurrentes",
    },
}


def tr(key: str, lang: str = None):
    """Translate a key. Falls back to English, then to the key itself."""
    lang = lang or st.session_state.get("lang", "en")
    value = T.get(lang, {}).get(key)
    if value is None:
        value = EXTRA_TEXT.get(lang, {}).get(key)
    if value is None:
        value = T["en"].get(key)
    if value is None:
        value = EXTRA_TEXT["en"].get(key, key)
    return value


# Scripts where letter-spacing must be off (it breaks joining / conjuncts).
SPACING_OFF_LANGS = {"ar", "hi", "zh"}

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
            --input-hover: #172033;
            --input-text: #f8fafc;
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
        # right, both text lines right-aligned next to it). The three buttons
        # read from left to right as:  Restart | Day/Night | Admin Panel
        # (the reverse of the other languages). On phones the brand stays on
        # the first row.
        rtl_css += f"""
        {HEADER} .brand-name,
        {HEADER} .brand-tagline {{
            direction: rtl;
            text-align: right !important;
        }}

        /* Buttons, left -> right: restart (col 4), day/night (col 3), admin (col 2) */
        {HEADER} > [data-testid="stColumn"]:nth-child(4) {{ order: 1 !important; }}
        {HEADER} > [data-testid="stColumn"]:nth-child(3) {{ order: 2 !important; }}
        {HEADER} > [data-testid="stColumn"]:nth-child(2) {{ order: 3 !important; }}

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
           FORM FIELDS  (FIXED: readable text in Light Mode)

           Why it was broken: when the browser / OS is in dark mode,
           Streamlit paints its own dark background (#262730) on inputs,
           number fields and selectboxes. Our text was dark navy, so it
           became dark-on-dark. Different Streamlit versions use different
           wrapper elements, so here we style ALL of them
           (data-baseweb + data-testid) with a higher specificity
           (".stApp ...") so our colors always win.
           ================================================================ */

        /* 1) The visible frame - exactly ONE frame per field.
              Text / number / textarea: the wrapper element.
              Selectbox: the BaseWeb ROOT element (not its first child), so the
              frame is drawn no matter how this Streamlit version nests it. */
        .stApp div[data-baseweb="input"],
        .stApp div[data-baseweb="textarea"],
        .stApp div[data-baseweb="select"],
        .stApp [data-testid="stSelectbox"] [role="group"],
        .stApp [data-testid="stMultiSelect"] [role="group"],
        .stApp [data-testid="stSelectbox"] > div:has(> input),
        .stApp [data-testid="stMultiSelect"] > div:has(> input),
        .stApp [data-testid="stDateInput"] [role="group"],
        .stApp [data-testid="stTextInputRootElement"],
        .stApp [data-testid="stNumberInputContainer"],
        .stApp [data-testid="stTextAreaRootElement"] {{
            background: var(--input) !important;
            background-color: var(--input) !important;
            background-image: none !important;
            border: 1px solid var(--input-border) !important;
            border-radius: 12px !important;
            box-shadow: none !important;
            overflow: hidden;
            transition: background .15s ease, border-color .15s ease,
                        box-shadow .15s ease;
        }}

        /* 2) Everything nested inside a frame is transparent, so Streamlit's
              dark layers can never show through and no double borders appear. */
        .stApp div[data-baseweb="input"] [data-baseweb],
        .stApp div[data-baseweb="textarea"] [data-baseweb],
        .stApp [data-testid="stTextInputRootElement"] [data-baseweb],
        .stApp [data-testid="stNumberInputContainer"] [data-baseweb],
        .stApp [data-testid="stTextAreaRootElement"] [data-baseweb],
        .stApp div[data-baseweb="select"] *:not(svg):not(path):not([data-baseweb="tag"]) {{
            background: transparent !important;
            background-color: transparent !important;
            background-image: none !important;
            border: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }}

        /* 3) Hover / focus (our blue focus ring replaces Streamlit's red one) */
        .stApp div[data-baseweb="input"]:hover,
        .stApp div[data-baseweb="select"]:hover,
        .stApp [data-testid="stSelectbox"] [role="group"]:hover,
        .stApp [data-testid="stMultiSelect"] [role="group"]:hover,
        .stApp [data-testid="stTextInputRootElement"]:hover,
        .stApp [data-testid="stNumberInputContainer"]:hover {{
            background: var(--input-hover, var(--input)) !important;
            background-color: var(--input-hover, var(--input)) !important;
        }}

        .stApp div[data-baseweb="input"]:focus-within,
        .stApp div[data-baseweb="textarea"]:focus-within,
        .stApp div[data-baseweb="select"]:focus-within,
        .stApp [data-testid="stSelectbox"] [role="group"]:focus-within,
        .stApp [data-testid="stSelectbox"] [role="group"][data-focus-within],
        .stApp [data-testid="stMultiSelect"] [role="group"]:focus-within,
        .stApp [data-testid="stMultiSelect"] [role="group"][data-focus-within],
        .stApp [data-testid="stTextInputRootElement"]:focus-within,
        .stApp [data-testid="stNumberInputContainer"]:focus-within,
        .stApp [data-testid="stTextAreaRootElement"]:focus-within {{
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 3px rgba(37,99,235,.16) !important;
        }}

        /* 4) Text typed inside inputs (dark navy in light mode, white in dark mode).
              -webkit-text-fill-color is needed because the browser can otherwise
              keep its own dark-theme text color. */
        .stApp input,
        .stApp textarea {{
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: var(--input-text, var(--text)) !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
            caret-color: var(--primary) !important;
            opacity: 1 !important;
        }}

        .stApp input[type="number"] {{
            color: var(--input-text, var(--text)) !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
        }}

        .stApp input::placeholder,
        .stApp textarea::placeholder {{
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
            opacity: .8 !important;
        }}

        /* Browser autofill would otherwise repaint the field yellow/blue. */
        .stApp input:-webkit-autofill,
        .stApp input:-webkit-autofill:hover,
        .stApp input:-webkit-autofill:focus {{
            -webkit-box-shadow: 0 0 0 1000px var(--input) inset !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
            caret-color: var(--primary) !important;
        }}

        /* 5) Selectbox: the chosen value (Yes / No / Male ...) stays readable,
              and the blinking text cursor is hidden (it is a dropdown, not a text box). */
        .stApp div[data-baseweb="select"],
        .stApp div[data-baseweb="select"] *,
        .stApp div[data-baseweb="select"] [role="combobox"],
        .stApp div[data-baseweb="select"] [role="combobox"] *,
        .stApp div[data-baseweb="select"] [role="button"],
        .stApp div[data-baseweb="select"] [role="button"] *,
        .stApp div[data-baseweb="select"] span,
        .stApp div[data-baseweb="select"] input {{
            color: var(--input-text, var(--text)) !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
            opacity: 1 !important;
        }}

        .stApp div[data-baseweb="select"] input,
        .stApp [data-testid="stSelectbox"] input {{
            caret-color: transparent !important;
        }}

        .stApp [data-testid="stSelectbox"] [role="group"] *,
        .stApp [data-testid="stMultiSelect"] [role="group"] * {{
            color: var(--input-text, var(--text)) !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
            opacity: 1 !important;
        }}

        /* 6) Small buttons inside fields (number - / + and password eye) */
        .stApp div[data-baseweb="input"] button,
        .stApp [data-testid="stNumberInputContainer"] button,
        .stApp [data-testid="stNumberInputStepDown"],
        .stApp [data-testid="stNumberInputStepUp"] {{
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: var(--muted) !important;
            opacity: 1 !important;
        }}

        .stApp div[data-baseweb="input"] button:hover,
        .stApp [data-testid="stNumberInputContainer"] button:hover,
        .stApp [data-testid="stNumberInputStepDown"]:hover,
        .stApp [data-testid="stNumberInputStepUp"]:hover {{
            background: var(--input-hover, var(--surface-soft)) !important;
            color: var(--primary) !important;
        }}

        .stApp div[data-baseweb="input"] button svg,
        .stApp [data-testid="stNumberInputContainer"] button svg,
        .stApp div[data-baseweb="select"] svg,
        .stApp [data-testid="stSelectbox"] [role="group"] button,
        .stApp [data-testid="stSelectbox"] [role="group"] button svg,
        .stApp [data-testid="stMultiSelect"] [role="group"] button,
        .stApp [data-testid="stMultiSelect"] [role="group"] button svg {{
            background: transparent !important;
            fill: var(--muted) !important;
            color: var(--muted) !important;
            opacity: 1 !important;
        }}

        /* 7) Dropdown list (Yes / No options).
              It is rendered in a "portal" OUTSIDE .stApp, so these rules
              intentionally do NOT use the .stApp prefix. */
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] > div,
        div[data-baseweb="popover"] ul,
        div[data-baseweb="menu"],
        ul[role="listbox"],
        [data-testid="stSelectboxVirtualDropdown"],
        [role="listbox"] {{
            background: var(--surface) !important;
            background-color: var(--surface) !important;
            border-color: var(--border) !important;
            color: var(--text) !important;
        }}

        div[data-baseweb="popover"] li,
        div[data-baseweb="menu"] li,
        [data-testid="stSelectboxVirtualDropdown"] li,
        [role="listbox"] li,
        [role="option"] {{
            background: var(--surface) !important;
            background-color: var(--surface) !important;
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
        }}

        div[data-baseweb="popover"] li *,
        div[data-baseweb="menu"] li *,
        [data-testid="stSelectboxVirtualDropdown"] li *,
        [role="listbox"] li *,
        [role="option"] * {{
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            background: transparent !important;
        }}

        [role="option"] [data-item-hl] {{
            background: transparent !important;
            background-color: transparent !important;
        }}

        [role="option"][data-hovered] [data-item-hl],
        [role="option"][data-focused] [data-item-hl],
        [role="option"][aria-selected="true"] [data-item-hl],
        [role="option"]:hover [data-item-hl] {{
            background: var(--surface-soft) !important;
            background-color: var(--surface-soft) !important;
        }}

        [data-testid="stSelectboxVirtualDropdown"],
        [data-testid="stMultiSelectDropdown"] {{
            border: 1px solid var(--border) !important;
            box-shadow: var(--shadow) !important;
        }}

        [data-testid="stMultiSelectDropdown"] {{
            background: var(--surface) !important;
        }}

        div[data-baseweb="popover"] li:hover,
        div[data-baseweb="menu"] li:hover,
        [data-testid="stSelectboxVirtualDropdown"] li:hover,
        [role="listbox"] li:hover,
        [role="option"]:hover,
        [role="option"][aria-selected="true"],
        li[aria-selected="true"] {{
            background: var(--surface-soft) !important;
            background-color: var(--surface-soft) !important;
        }}

        /* 8) Tooltips (hover text of the day/night and restart buttons, help= icons).
              Streamlit paints them dark; our global text rule made the text dark too,
              so the label was invisible in Light Mode. They render in a portal, so no
              .stApp prefix here. */
        [data-testid="stTooltipContent"],
        [role="tooltip"] [data-testid="stTooltipContent"],
        div[data-baseweb="tooltip"],
        div[data-baseweb="tooltip"] > div {{
            background: var(--surface) !important;
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            box-shadow: var(--shadow) !important;
        }}

        [data-testid="stTooltipContent"] *,
        div[data-baseweb="tooltip"] * {{
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            background: transparent !important;
            font-weight: 600 !important;
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
        .stFormSubmitButton > button,
        [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-secondaryFormSubmit"],
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

        .stApp .stButton > button[kind="primary"],
        .stApp .stFormSubmitButton > button[kind="primary"],
        .stApp .stDownloadButton > button[kind="primary"],
        .stApp button[kind="primary"],
        .stApp [data-testid="stBaseButton-primary"],
        .stApp [data-testid="stBaseButton-primaryFormSubmit"] {{
            background:linear-gradient(135deg,#2563eb,#0284c7) !important;
            color:white !important;
            border:none !important;
        }}

        .stApp button[kind="primary"] p,
        .stApp button[kind="primary"] span,
        .stApp [data-testid="stBaseButton-primary"] p,
        .stApp [data-testid="stBaseButton-primary"] span,
        .stApp [data-testid="stBaseButton-primaryFormSubmit"] p,
        .stApp [data-testid="stBaseButton-primaryFormSubmit"] span {{
            color:#ffffff !important;
            -webkit-text-fill-color:#ffffff !important;
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


def build_symptom_narrative(symptom_values: dict, extra_values: dict, lang: str = None,
                            gender_values: dict = None, freq_key: str = None) -> str:
    lang = lang or st.session_state.get("lang", "en")

    core_yes = []
    for col, key in display_labels.items():
        if symptom_values.get(col) == "Yes":
            label = tr(key, lang)
            if col == "Polyuria" and freq_key:
                label = f"{label} ({tr(freq_key, lang)})"
            core_yes.append(label)
    extra_yes = [tr(key, lang) for key in extra_symptom_keys if extra_values.get(key) == "Yes"]
    extra_yes += [tr(key, lang) for key, value in (gender_values or {}).items() if value == "Yes"]

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
                 age, gender, result, probability, symptom_values, extra_values,
                 gender_values=None, freq_key=None, marital_status_key=None) -> dict:
    """Build the report dictionary in the requested language."""
    gender_values = gender_values or {}
    any_extra = any(v == "Yes" for v in extra_values.values()) or any(
        v == "Yes" for v in gender_values.values()
    )
    gender_yes = [tr(k, lang) for k, v in gender_values.items() if v == "Yes"]
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
        "Marital status": marital_status_label(marital_status_key, gender, lang) if marital_status_key else "",
        "Result": tr("positive_high" if result == 1 else "negative_low", lang),
        "Probability": f"{probability * 100:.1f}%",
        "Notable extra symptoms": tr("yes" if any_extra else "no", lang),
        "Urination frequency": tr(freq_key, lang) if freq_key else "",
        "Gender-specific symptoms": ", ".join(gender_yes),
        "Symptom narrative": build_symptom_narrative(
            symptom_values, extra_values, lang, gender_values=gender_values, freq_key=freq_key
        ),
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
# The report is built with fpdf2 + HarfBuzz:
#       pip install fpdf2 uharfbuzz
# HarfBuzz shapes Arabic and Hindi correctly and the layout mirrors for
# right-to-left languages, so the report follows the app language.
#
# Fonts (Noto Sans family) are read from the "fonts" folder next to this file.
# Any missing font is downloaded once, automatically, the first time it is
# needed (internet required). To work fully offline, copy the font files into
# the "fonts" folder yourself. Fonts used:
#   NotoSans-Regular/Bold.ttf            Latin, Cyrillic, Greek, Turkish ...
#   NotoSansArabic-Regular/Bold.ttf      Arabic
#   NotoSansDevanagari-Regular/Bold.ttf  Hindi
#   NotoSansSC-Regular/Bold.otf          Chinese

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE_DIR, "fonts")
TMP_FONT_DIR = os.path.join(tempfile.gettempdir(), "perdiapredict_fonts")  # if the app folder is read-only

try:
    import uharfbuzz  # noqa: F401

    SHAPING_OK = True
except Exception:
    SHAPING_OK = False

_NOTO_URL = "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts"
_CJK_URL = "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/SubsetOTF/SC"

# script -> (font family name, (regular file, bold file), download folder URL)
PDF_FONTS = {
    "latin": (
        "NotoSans",
        ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf"),
        f"{_NOTO_URL}/NotoSans/hinted/ttf/",
    ),
    "arabic": (
        "NotoSansArabic",
        ("NotoSansArabic-Regular.ttf", "NotoSansArabic-Bold.ttf"),
        f"{_NOTO_URL}/NotoSansArabic/hinted/ttf/",
    ),
    "devanagari": (
        "NotoSansDevanagari",
        ("NotoSansDevanagari-Regular.ttf", "NotoSansDevanagari-Bold.ttf"),
        f"{_NOTO_URL}/NotoSansDevanagari/hinted/ttf/",
    ),
    "cjk": (
        "NotoSansSC",
        ("NotoSansSC-Regular.otf", "NotoSansSC-Bold.otf"),
        f"{_CJK_URL}/",
    ),
}

# Language code -> main non-Latin script of that language.
LANG_SCRIPT = {
    "ar": "arabic",
    "fa": "arabic",
    "ur": "arabic",
    "hi": "devanagari",
    "mr": "devanagari",
    "ne": "devanagari",
    "zh": "cjk",
}

# Used to detect scripts typed by the patient (e.g. an Arabic name inside an
# English report) so the right font is loaded for those characters too.
SCRIPT_REGEX = {
    "arabic": re.compile("[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"),
    "devanagari": re.compile("[\u0900-\u097F]"),
    "cjk": re.compile("[\u2E80-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF]"),
}

# Report colors
C_NAVY = (11, 31, 77)
C_BLUE = (37, 99, 235)
C_SKY = (14, 165, 233)
C_TEXT = (19, 35, 63)
C_MUTED = (100, 116, 139)
C_BORDER = (219, 228, 240)
C_SOFT = (245, 248, 255)
C_GREEN = (22, 163, 74)
C_GREEN_BG = (240, 253, 244)
C_GREEN_BD = (187, 247, 208)
C_RED = (220, 38, 38)
C_RED_BG = (254, 242, 242)
C_RED_BD = (254, 202, 202)
C_AMBER_BG = (255, 251, 235)
C_AMBER_BD = (245, 217, 139)
C_AMBER_TX = (120, 80, 0)
C_PILL_BG = (239, 246, 255)
C_PILL_BD = (191, 219, 254)
C_XPILL_BG = (255, 247, 237)
C_XPILL_BD = (253, 215, 170)
C_ORANGE = (234, 88, 12)
C_GPILL_BG = (245, 243, 255)
C_GPILL_BD = (221, 214, 254)
C_VIOLET = (124, 58, 237)


@st.cache_resource(show_spinner=False, ttl=900)
def _font_file(script: str, bold: bool):
    """Path of a font file: local 'fonts' folder first, otherwise download it once."""
    _family, files, base_url = PDF_FONTS[script]
    name = files[1 if bold else 0]

    for directory in (FONT_DIR, "fonts", BASE_DIR, ".", TMP_FONT_DIR):
        path = os.path.join(directory, name)
        if os.path.exists(path) and os.path.getsize(path) > 10_000:
            return path

    for folder in (FONT_DIR, TMP_FONT_DIR):
        target = os.path.join(folder, name)
        tmp = target + ".part"
        try:
            os.makedirs(folder, exist_ok=True)
            with urllib.request.urlopen(base_url + name, timeout=40) as response, open(tmp, "wb") as out:
                shutil.copyfileobj(response, out)
            if os.path.getsize(tmp) < 10_000:
                raise OSError("downloaded font is too small")
            os.replace(tmp, target)
            return target
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
    return None


def pick_pdf_language(lang: str) -> str:
    """Return the language the PDF can really be produced in on this server.

    It is the app language whenever the needed fonts are available (or can be
    downloaded); otherwise it falls back to English.
    """
    if lang == "en":
        return "en"

    script = LANG_SCRIPT.get(lang, "latin")
    if script in ("arabic", "devanagari") and not SHAPING_OK:
        return "en"

    for needed in {"latin", script}:
        for bold in (False, True):
            if not _font_file(needed, bold):
                return "en"
    return lang


def _rgb(color):
    return color[0], color[1], color[2]


def generate_pdf_report(report_data: dict, lang: str = "en", is_high: bool = False,
                        symptoms: dict = None) -> bytes:
    """Build the one-page A4 report.

    The normal layout is tried first. If the content is too long for a single
    page (many symptoms, long address, wordy language ...), the report is
    rebuilt with a tighter layout (level 1, then 2) so it still fits on one page.

    `symptoms` = {"core": [...], "extra": [...], "gender": [...],
                  "gender_kind": "Male"/"Female", "freq": key}
    (the answers the patient marked "Yes"). When it is missing, the report
    falls back to the text paragraph in report_data["Symptom narrative"].
    """
    best = None
    for level in (0, 1, 2):
        data, pages = _render_pdf_report(report_data, lang, is_high, symptoms, level)
        if pages <= 1:
            return data
        if best is None or pages < best[1]:
            best = (data, pages)
    return best[0]


def _render_pdf_report(report_data: dict, lang: str, is_high: bool,
                       symptoms, level: int = 0):
    """Returns (pdf_bytes, number_of_pages)."""
    rtl = is_rtl(lang)

    def t(key):
        return tr(key, lang)

    # ------------------------------------------------------- symptom labels
    core_texts, extra_texts, gender_texts = [], [], []
    gender_head = ""
    if symptoms:
        for c in symptoms.get("core", []):
            if c not in display_labels:
                continue
            label = t(display_labels[c])
            if c == "Polyuria" and symptoms.get("freq"):
                label = f"{label}\n{t(symptoms['freq'])}"   # name + times per day
            core_texts.append(label)
        extra_texts = [t(k) for k in symptoms.get("extra", []) if k in extra_symptom_keys]
        kind = symptoms.get("gender_kind")
        if symptoms.get("is_child"):
            g_keys = child_question_keys(kind)
            gender_head = t("child_section")
        else:
            g_keys = MALE_SYMPTOM_KEYS if kind == "Male" else FEMALE_SYMPTOM_KEYS
            gender_head = t("male_section" if kind == "Male" else "female_section")
        gender_texts = [t(k) for k in symptoms.get("gender", []) if k in g_keys]

    # ------------------------------------------------------------------ fonts
    values = [str(v) for v in report_data.values()]
    texts = values + core_texts + extra_texts + gender_texts + [gender_head] + [
        t(k)
        for k in (
            "pdf_title", "pdf_generated", "pdf_patient", "pdf_name", "pdf_age_gender",
            "phone", "pdf_email", "pdf_address", "pdf_type", "pdf_clinical",
            "pdf_assessment", "pdf_risk", "probability", "pdf_extra",
            "pdf_disclaimer_label", "pdf_disclaimer", "medical_notice", "brand",
            "no_core",
        )
    ]
    blob = " ".join(texts)

    main_script = LANG_SCRIPT.get(lang, "latin")
    scripts = {"latin", main_script}
    for name, rx in SCRIPT_REGEX.items():
        if rx.search(blob):
            scripts.add(name)

    pdf = _ReportPDF(rtl=rtl)
    families = {}
    for script in sorted(scripts):
        regular = _font_file(script, False)
        bold = _font_file(script, True)
        if not (regular and bold):
            continue
        family = PDF_FONTS[script][0]
        pdf.add_font(family, "", regular)
        pdf.add_font(family, "B", bold)
        families[script] = family

    unicode_ok = "latin" in families
    if not unicode_ok:
        # No font files at all: use the built-in font (Latin-1 only).
        base_font = "helvetica"
    else:
        base_font = families.get(main_script, families["latin"])
        fallbacks = [f for s, f in families.items() if f != base_font]
        if fallbacks:
            pdf.set_fallback_fonts(fallbacks, exact_match=True)

    if SHAPING_OK and unicode_ok:
        pdf.set_text_shaping(True)

    def safe(text):
        text = str(text)
        return text if unicode_ok else text.encode("latin-1", "replace").decode("latin-1")

    wrap = "CHAR" if lang == "zh" else "WORD"
    align = "R" if rtl else "L"

    pdf.base_font = base_font
    pdf.footer_notice = safe(t("medical_notice"))
    pdf.footer_brand = safe(t("brand"))
    pdf.set_auto_page_break(True, margin=26)
    pdf.set_margins(14, 14, 14)
    pdf.alias_nb_pages()
    pdf.add_page()

    page_w = pdf.w
    left = pdf.l_margin
    width = page_w - pdf.l_margin - pdf.r_margin
    right = left + width

    # ------------------------------------------------------------- dimensions
    # Level 0 = normal; levels 1 and 2 squeeze the spacing to keep one page.
    if level >= 2:      # dense: many symptoms + long texts
        band_h, after_band, card_h = 27, 4, 34
        sec_top, sec_after = 2.5, 7
        row_extra, card_pad = 2.8, 3.2
        pill_min, pill_gap_y, pill_pad_v, pill_size, pill_lh = 6.4, 1.4, 2.2, 8.2, 3.9
        head_h, head_size, sep = 4.6, 8.2, 4.2
        dis_gap, dis_size, dis_lh = 3, 7.8, 4.0
    elif level == 1:    # compact
        band_h, after_band, card_h = 30, 5, 35
        sec_top, sec_after = 3.2, 7.5
        row_extra, card_pad = 3.2, 3.8
        pill_min, pill_gap_y, pill_pad_v, pill_size, pill_lh = 6.8, 1.6, 2.4, 8.5, 4.1
        head_h, head_size, sep = 4.8, 8.5, 4.6
        dis_gap, dis_size, dis_lh = 3.5, 8.0, 4.2
    else:               # normal
        band_h, after_band, card_h = 34, 8, 37
        sec_top, sec_after = 5.5, 9
        row_extra, card_pad = 4.3, 5
        pill_min, pill_gap_y, pill_pad_v, pill_size, pill_lh = 8.0, 2.4, 2.8, 8.8, 4.4
        head_h, head_size, sep = 5.5, 8.8, 6.5
        dis_gap, dis_size, dis_lh = 6, 8.6, 4.7

    # ---------------------------------------------------------------- helpers
    def font(style="", size=10, color=C_TEXT):
        pdf.set_font(base_font, style, size)
        pdf.set_text_color(*_rgb(color))

    def measure(text, w, size, style="", lh=5.4):
        """Height needed to print `text` in a box `w` mm wide."""
        font(style, size)
        lines = pdf.multi_cell(
            w, lh, safe(text), align=align, wrapmode=wrap, dry_run=True, output="LINES"
        )
        return max(1, len(lines)) * lh

    def put(text, x, y, w, size=10, style="", color=C_TEXT, lh=5.4, text_align=None):
        """Print text (wrapped) with its box at x..x+w, top at y. Returns the height."""
        font(style, size, color)
        pdf.set_xy(x, y)
        pdf.multi_cell(
            w, lh, safe(text), align=text_align or align, wrapmode=wrap,
            new_x="LEFT", new_y="NEXT",
        )
        return pdf.get_y() - y

    def box(x, y, w, h, fill, border=None, radius=3.0, line=0.3):
        pdf.set_fill_color(*_rgb(fill))
        if border:
            pdf.set_draw_color(*_rgb(border))
            pdf.set_line_width(line)
            style = "DF"
        else:
            style = "F"
        pdf.rect(x, y, w, h, style=style, round_corners=True, corner_radius=radius)

    def ensure(height):
        if pdf.get_y() + height > pdf.h - 26:
            pdf.add_page()
            pdf.set_y(16)

    def section(title, need=0):
        """Section title. `need` = height of the content below, so title and
        content are never separated by a page break."""
        ensure(sec_top + sec_after + 4 + need)
        y = pdf.get_y() + sec_top
        bar_x = right - 1.6 if rtl else left
        pdf.set_fill_color(*_rgb(C_BLUE))
        pdf.rect(bar_x, y, 1.6, 6, style="F")
        text_x = left if rtl else left + 4.5
        put(title, text_x, y + 0.2, width - 4.5, size=12.5, style="B", color=C_NAVY, lh=6)
        pdf.set_y(y + sec_after)

    # -------------------------------------------------------- header (banner)
    steps = 105
    for i in range(steps):
        ratio = i / (steps - 1)
        col = (
            int(C_NAVY[0] + (14 - C_NAVY[0]) * ratio),
            int(C_NAVY[1] + (84 - C_NAVY[1]) * ratio),
            int(C_NAVY[2] + (150 - C_NAVY[2]) * ratio),
        )
        pdf.set_fill_color(*col)
        pdf.rect(page_w * i / steps, 0, page_w / steps + 0.4, band_h, style="F")
    pdf.set_fill_color(*_rgb(C_SKY))
    pdf.rect(0, band_h, page_w, 1.3, style="F")

    logo_size = band_h - 10
    logo_y = (band_h - logo_size) / 2
    logo_x = right - logo_size if rtl else left
    has_logo = os.path.exists(LOGO_PATH)
    if has_logo:
        try:
            pdf.image(LOGO_PATH, x=logo_x, y=logo_y, w=logo_size, h=logo_size)
        except Exception:
            has_logo = False

    gap = 6
    stamp_w = 52
    text_w = width - (logo_size + gap if has_logo else 0) - stamp_w - 6
    if rtl:
        text_x = right - (logo_size + gap if has_logo else 0) - text_w
    else:
        text_x = left + (logo_size + gap if has_logo else 0)

    put("PERDIAPREDICT", text_x, logo_y + 2, text_w, size=21, style="B",
        color=(255, 255, 255), lh=9)
    put(t("pdf_title"), text_x, logo_y + 12.5, text_w, size=10, color=(191, 219, 254), lh=5)

    stamp_x = left if rtl else right - stamp_w
    stamp_align = "L" if rtl else "R"
    put(t("pdf_generated"), stamp_x, band_h / 2 - 7, stamp_w, size=8,
        color=(147, 197, 253), lh=4, text_align=stamp_align)
    put(report_data.get("Timestamp", ""), stamp_x, band_h / 2 - 2.6, stamp_w, size=11,
        style="B", color=(255, 255, 255), lh=6, text_align=stamp_align)

    pdf.set_y(band_h + after_band)

    # ------------------------------------------------ risk result (main card)
    accent = C_RED if is_high else C_GREEN
    tint = C_RED_BG if is_high else C_GREEN_BG
    tint_border = C_RED_BD if is_high else C_GREEN_BD

    try:
        probability = float(re.search(r"[\d.]+", str(report_data.get("Probability", "0"))).group())
    except Exception:
        probability = 0.0
    probability = max(0.0, min(100.0, probability))

    ensure(card_h)
    cy = pdf.get_y()
    box(left, cy, width, card_h, tint, tint_border, radius=4)

    pad = 6
    icon = 16
    icon_x = right - pad - icon if rtl else left + pad
    box(icon_x, cy + pad, icon, icon, accent, radius=4)
    pdf.set_draw_color(255, 255, 255)
    pdf.set_line_width(1.3)
    if is_high:
        pdf.line(icon_x + icon / 2, cy + pad + 3.5, icon_x + icon / 2, cy + pad + 9.5)
        pdf.set_fill_color(255, 255, 255)
        pdf.ellipse(icon_x + icon / 2 - 0.9, cy + pad + 11.2, 1.8, 1.8, style="F")
    else:
        pdf.line(icon_x + 4, cy + pad + 8.5, icon_x + 7, cy + pad + 11.5)
        pdf.line(icon_x + 7, cy + pad + 11.5, icon_x + 12.2, cy + pad + 4.8)

    prob_w = 46
    info_w = width - 2 * pad - icon - 5 - prob_w - 4
    if rtl:
        info_x = right - pad - icon - 5 - info_w
        prob_x = left + pad
    else:
        info_x = left + pad + icon + 5
        prob_x = right - pad - prob_w

    put(t("pdf_risk"), info_x, cy + pad - 0.5, info_w, size=8.5, color=C_MUTED, lh=4.2)
    put(report_data.get("Result", ""), info_x, cy + pad + 4.6, info_w, size=13.5,
        style="B", color=accent, lh=6.4)

    prob_align = "L" if rtl else "R"
    put(f"{probability:.1f}%", prob_x, cy + pad - 1.5, prob_w, size=27, style="B",
        color=accent, lh=12, text_align=prob_align)
    put(t("probability"), prob_x, cy + pad + 11.2, prob_w, size=8.5, color=C_MUTED,
        lh=4.2, text_align=prob_align)

    bar_x = left + pad
    bar_w = width - 2 * pad
    bar_y = cy + card_h - pad - 3.4
    box(bar_x, bar_y, bar_w, 3.4, (226, 232, 240), radius=1.7)
    fill_w = max(3.4, bar_w * probability / 100.0) if probability > 0 else 0
    if fill_w:
        fill_x = bar_x + bar_w - fill_w if rtl else bar_x
        box(fill_x, bar_y, fill_w, 3.4, accent, radius=1.7)

    pdf.set_y(cy + card_h + 2)

    # ----------------------------------------------------------- patient card
    name = f"{report_data.get('First name', '')} {report_data.get('Last name', '')}".strip()
    age_gender = f"{report_data.get('Age', '')} / {report_data.get('Gender', '')}"
    rows = [
        [(t("pdf_name"), name), (t("pdf_age_gender"), age_gender)],
        [(t("phone"), report_data.get("Phone", "")), (t("pdf_email"), report_data.get("Email", t("na")))],
        [(t("pdf_address"), report_data.get("Address", "")),
         (t("pdf_type"), report_data.get("Reported diabetes type", ""))],
    ]

    inner_w = width - 2 * pad
    col_gap = 8
    col_w = (inner_w - col_gap) / 2
    label_h = 4.4
    value_lh = 5.6

    layouts = []
    total_h = pad - 1
    for row in rows:
        cell_w = col_w if len(row) == 2 else inner_w
        heights = [label_h + measure(v, cell_w, 10.5, "B", value_lh) for _, v in row]
        row_height = max(heights) + row_extra
        layouts.append((row, cell_w, row_height))
        total_h += row_height
    total_h += pad - row_extra

    section(t("pdf_patient"), need=total_h)
    py = pdf.get_y()
    box(left, py, width, total_h, (255, 255, 255), C_BORDER, radius=4)

    cursor = py + pad - 1
    for index, (row, cell_w, row_height) in enumerate(layouts):
        for i, (label, value) in enumerate(row):
            slot = (1 - i) if rtl else i
            cx = left + pad + slot * (col_w + col_gap) if len(row) == 2 else left + pad
            put(label, cx, cursor, cell_w, size=8.3, color=C_MUTED, lh=label_h)
            put(value, cx, cursor + label_h, cell_w, size=10.5, style="B",
                color=C_TEXT, lh=value_lh)
        cursor += row_height
        if index < len(layouts) - 1:
            pdf.set_draw_color(*_rgb(C_BORDER))
            pdf.set_line_width(0.2)
            pdf.line(left + pad, cursor - row_extra / 2, right - pad, cursor - row_extra / 2)
    pdf.set_y(py + total_h)

    # ------------------------------------------------- clinical presentation
    narrative = report_data.get("Symptom narrative", "")
    have_pills = bool(core_texts or extra_texts or gender_texts)

    if not have_pills:
        # Text version: used when the patient answered "No" to everything, or
        # when no symptom list was passed in.
        text_w = width - 2 * pad - 2
        text_h = measure(narrative, text_w, 10, "", 5.9)
        ch = text_h + 2 * 5
        section(t("pdf_clinical"), need=ch)
        cy2 = pdf.get_y()
        box(left, cy2, width, ch, C_SOFT, C_BORDER, radius=4)
        stripe_x = right - 1.6 - 0.2 if rtl else left + 0.2
        pdf.set_fill_color(*_rgb(C_BLUE))
        pdf.rect(stripe_x, cy2 + 4, 1.6, ch - 8, style="F")
        text_x2 = left + pad - 1 if rtl else left + pad + 2
        put(narrative, text_x2, cy2 + 5, text_w, size=10, color=C_TEXT, lh=5.9)
        pdf.set_y(cy2 + ch)
    else:
        # Symptom "pills" in a tidy grid. Groups: core symptoms, additional
        # symptoms, and (if any) the symptoms specific to the patient's gender.
        gap_x = 3.2
        icon_d = 4.0 if level >= 2 else 4.4
        icon_zone = 8.4 if level >= 2 else 9.0
        all_texts = core_texts + extra_texts + gender_texts

        def pill_text_w(cols):
            return (inner_w - (cols - 1) * gap_x) / cols - icon_zone - 2

        def wraps(cols):
            tw_ = pill_text_w(cols)
            return any(
                measure(part, tw_, pill_size, "B", pill_lh) > pill_lh + 0.1
                for x in all_texts for part in x.split("\n")
            )

        cols = 3 if wraps(4) else 4
        pw = (inner_w - (cols - 1) * gap_x) / cols
        tw = pill_text_w(cols)

        def plan(items):
            cells = [
                (x, max(pill_min, measure(x, tw, pill_size, "B", pill_lh) + pill_pad_v))
                for x in items
            ]
            grid = [cells[i:i + cols] for i in range(0, len(cells), cols)]
            heights = [max(h for _, h in r) for r in grid]
            return grid, heights

        def block_height(heights):
            return sum(heights) + pill_gap_y * (len(heights) - 1) if heights else 0

        blocks = [
            {"head": None, "texts": core_texts, "colors": (C_PILL_BG, C_PILL_BD, C_BLUE),
             "empty": ("text", t("no_core"))},
            {"head": t("pdf_extra"), "texts": extra_texts, "colors": (C_XPILL_BG, C_XPILL_BD, C_ORANGE),
             "empty": ("value", t("no"))},
        ]
        if gender_texts:
            blocks.append({"head": gender_head, "texts": gender_texts,
                           "colors": (C_GPILL_BG, C_GPILL_BD, C_VIOLET), "empty": None})

        for b_ in blocks:
            b_["grid"], b_["hs"] = plan(b_["texts"])
            if b_["texts"]:
                b_["h"] = (head_h + 2 if b_["head"] else 0) + block_height(b_["hs"])
            elif b_["empty"][0] == "text":
                b_["h"] = measure(b_["empty"][1], inner_w, 9.5, "", 5)
            else:
                b_["h"] = head_h

        ch = 2 * card_pad + sum(b_["h"] for b_ in blocks) + sep * (len(blocks) - 1)

        def draw_pills(grid, heights, fill, border, dot, y0):
            y_cur = y0
            for row_cells, rh in zip(grid, heights):
                for i, (txt, _h) in enumerate(row_cells):
                    slot = (cols - 1 - i) if rtl else i
                    px = left + pad + slot * (pw + gap_x)
                    box(px, y_cur, pw, rh, fill, border, radius=2.6, line=0.25)
                    ix = px + pw - 2.8 - icon_d if rtl else px + 2.8
                    iy = y_cur + (rh - icon_d) / 2
                    pdf.set_fill_color(*_rgb(dot))
                    pdf.ellipse(ix, iy, icon_d, icon_d, style="F")
                    mx, my = ix + icon_d / 2, iy + icon_d / 2
                    pdf.set_draw_color(255, 255, 255)
                    pdf.set_line_width(0.5)
                    pdf.line(mx - 1.2, my + 0.1, mx - 0.3, my + 1.0)
                    pdf.line(mx - 0.3, my + 1.0, mx + 1.3, my - 0.9)
                    th = measure(txt, tw, pill_size, "B", pill_lh)
                    tx = px + 2 if rtl else px + icon_zone
                    put(txt, tx, y_cur + (rh - th) / 2, tw, size=pill_size, style="B",
                        color=C_TEXT, lh=pill_lh)
                y_cur += rh + pill_gap_y
            return y_cur - pill_gap_y

        section(t("pdf_clinical"), need=ch)
        cy2 = pdf.get_y()
        box(left, cy2, width, ch, (255, 255, 255), C_BORDER, radius=4)
        y = cy2 + card_pad

        label_w = inner_w * 0.62
        value_w = inner_w - label_w
        label_x = right - pad - label_w if rtl else left + pad
        value_x = left + pad if rtl else right - pad - value_w

        for idx, b_ in enumerate(blocks):
            if idx:
                pdf.set_draw_color(*_rgb(C_BORDER))
                pdf.set_line_width(0.2)
                pdf.line(left + pad, y + sep / 2, right - pad, y + sep / 2)
                y += sep
            if b_["head"]:
                put(b_["head"], label_x, y, label_w, size=head_size, style="B", color=C_MUTED, lh=4.4)
            if b_["texts"]:
                top = y + (head_h + 2 if b_["head"] else 0)
                y = draw_pills(b_["grid"], b_["hs"], *b_["colors"], top)
            elif b_["empty"][0] == "text":
                put(b_["empty"][1], left + pad, y, inner_w, size=9.5, color=C_MUTED, lh=5)
                y += b_["h"]
            else:
                put(b_["empty"][1], value_x, y, value_w, size=9.5, style="B", color=C_TEXT,
                    lh=4.4, text_align="L" if rtl else "R")
                y += b_["h"]
        pdf.set_y(cy2 + ch)

    # --------------------------------------------------------------- disclaimer
    pdf.ln(dis_gap)
    label = t("pdf_disclaimer_label")
    body = t("pdf_disclaimer")
    dis_w = width - 2 * pad
    label_height = 5
    body_height = measure(body, dis_w, dis_size, "", dis_lh)
    dh = label_height + body_height + 2 * 5 - 1
    ensure(dh)
    dy = pdf.get_y()
    box(left, dy, width, dh, C_AMBER_BG, C_AMBER_BD, radius=3.5)
    put(label, left + pad, dy + 4.6, dis_w, size=9.2, style="B", color=C_AMBER_TX, lh=5)
    put(body, left + pad, dy + 4.6 + label_height, dis_w, size=dis_size, color=C_AMBER_TX, lh=dis_lh)
    pdf.set_y(dy + dh)

    return bytes(pdf.output()), pdf.page_no()


class _ReportPDF(FPDF):
    """A4 report page with a footer (notice + brand + page number)."""

    def __init__(self, rtl: bool = False):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.rtl = rtl
        self.base_font = "helvetica"
        self.footer_notice = ""
        self.footer_brand = "PerdiaPredict"

    def footer(self):
        left = self.l_margin
        right = self.w - self.r_margin
        width = right - left

        self.set_y(-21)
        self.set_draw_color(*_rgb(C_BORDER))
        self.set_line_width(0.3)
        self.line(left, self.get_y(), right, self.get_y())

        align = "R" if self.rtl else "L"
        self.set_font(self.base_font, "", 7.2)
        self.set_text_color(*_rgb(C_MUTED))
        self.set_xy(left, self.get_y() + 1.8)
        self.multi_cell(width, 3.5, self.footer_notice, align=align, new_x="LEFT", new_y="NEXT")

        y = self.get_y() + 0.8
        # Brand at the start side, page number at the end side (mirrored for RTL).
        self.set_font(self.base_font, "B", 7.8)
        self.set_text_color(*_rgb(C_BLUE))
        self.set_xy(left + width / 2 if self.rtl else left, y)
        self.cell(width / 2, 4, self.footer_brand, align="R" if self.rtl else "L")

        self.set_font(self.base_font, "", 7.8)
        self.set_text_color(*_rgb(C_MUTED))
        self.set_xy(left if self.rtl else left + width / 2, y)
        self.cell(width / 2, 4, f"{self.page_no()} / {{nb}}", align="L" if self.rtl else "R")


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

    # Age and gender are asked OUTSIDE the form on purpose: a widget inside a
    # form does not refresh the page, and the gender choice must refresh it
    # immediately so the questions specific to men / women can appear.
    st.markdown(f'<div class="section-title">📋 {tr("basic")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-subtitle">{tr("gender_hint")}</div>', unsafe_allow_html=True)

    c5, c6, c7 = st.columns(3)
    with c5:
        age = st.number_input(tr("age"), min_value=1, max_value=120, value=40, step=1, key="basic_age")
    with c6:
        gender_label = st.selectbox(tr("gender"), [tr("male"), tr("female")], key="basic_gender")
        gender = "Male" if gender_label == tr("male") else "Female"
    with c7:
        # Labels agree in gender with the "Gender" choice above (e.g. "أعزب" for a
        # male patient vs "عزباء" for a female one), and include a "Child" option
        # that switches the last section of the form to pediatric questions.
        marital_labels = [marital_status_label(k, gender, lang) for k in MARITAL_STATUS_ORDER]
        marital_label = st.selectbox(tr("marital_status"), marital_labels, key="basic_marital")
        marital_status_key = MARITAL_STATUS_ORDER[marital_labels.index(marital_label)]
        is_child = marital_status_key == "child"
        # Sensitive adult questions only appear once married or divorced/widowed.
        ever_married = marital_status_key in ("married", "divorced")

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
        st.markdown(f'<div class="section-title">🩺 {tr("core")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{tr("core_help")}</div>', unsafe_allow_html=True)

        symptom_values = {}
        freq_key = None
        s_col1, s_col2 = st.columns(2)

        for i, col in enumerate(binary_columns):
            key = display_labels.get(col, col)
            label = tr(key)
            target_col = s_col1 if i % 2 == 0 else s_col2
            with target_col:
                if col == "Polyuria":
                    # "No", or "Yes" together with how many times a day the patient urinates.
                    freq_options = [tr("no")] + [f"{tr('yes')} - {tr(k)}" for k in POLYURIA_FREQ_KEYS]
                    selected = st.selectbox(label, freq_options, key="core_polyuria_freq")
                    if selected == freq_options[0]:
                        symptom_values[col] = "No"
                    else:
                        symptom_values[col] = "Yes"
                        freq_key = POLYURIA_FREQ_KEYS[freq_options.index(selected) - 1]
                else:
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

        # Questions that depend on the gender chosen above (adult male/female
        # section), or - if the patient is a child - pediatric questions
        # chosen by the child's gender instead.
        gender_values = {}
        if is_child:
            gender_keys = child_question_keys(gender)
            gender_icon = "🧒" if gender == "Male" else "👧"
            gender_title = tr("child_section")
        else:
            gender_keys = gender_question_keys(gender, ever_married)
            gender_icon = "♂️" if gender == "Male" else "♀️"
            gender_title = tr("male_section" if gender == "Male" else "female_section")

        st.markdown("---")
        st.markdown(f'<div class="section-title">{gender_icon} {gender_title}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{tr("gender_section_help")}</div>', unsafe_allow_html=True)

        g_col1, g_col2 = st.columns(2)
        for i, key in enumerate(gender_keys):
            target_col = g_col1 if i % 2 == 0 else g_col2
            with target_col:
                selected = st.selectbox(
                    tr(key),
                    [tr("no"), tr("yes")],
                    key=f"gender_{gender}_{'child' if is_child else 'adult'}_{key}",
                )
                gender_values[key] = "Yes" if selected == tr("yes") else "No"

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
                gender_values=gender_values,
                freq_key=freq_key,
                marital_status_key=marital_status_key,
            )

            # Shown to the user (current language) ...
            st.session_state["last_report"] = build_report(lang, **report_args)
            # ... and the same record in English, so the admin Excel file stays consistent.
            st.session_state["last_report_en"] = build_report("en", **report_args)

            st.session_state["last_extra"] = any(v == "Yes" for v in extra_values.values())
            st.session_state["last_symptoms"] = {
                "core": [c for c in display_labels if symptom_values.get(c) == "Yes"],
                "extra": [k for k in extra_symptom_keys if extra_values.get(k) == "Yes"],
                "gender": [k for k, v in gender_values.items() if v == "Yes"],
                "gender_kind": gender,
                "is_child": is_child,
                "freq": freq_key,
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

        # The report follows the app language. It is generated once per result
        # (not on every rerun) and falls back to English only if the fonts for
        # this language are unavailable.
        pdf_lang = pick_pdf_language(lang)
        pdf_report = report if pdf_lang == lang else report_en
        pdf_symptoms = st.session_state.get("last_symptoms")
        cache_key = (
            pdf_lang,
            int(result),
            tuple(sorted((k, str(v)) for k, v in pdf_report.items())),
            repr(pdf_symptoms) if pdf_symptoms else None,
        )

        if st.session_state.get("pdf_cache_key") != cache_key:
            try:
                pdf_bytes = generate_pdf_report(
                    pdf_report, pdf_lang, is_high=(result == 1), symptoms=pdf_symptoms
                )
            except Exception:
                if pdf_lang == "en":
                    raise
                pdf_lang = "en"
                pdf_report = report_en
                pdf_bytes = generate_pdf_report(
                    pdf_report, "en", is_high=(result == 1), symptoms=pdf_symptoms
                )
            st.session_state["pdf_cache_key"] = cache_key
            st.session_state["pdf_cache_data"] = pdf_bytes
            st.session_state["pdf_cache_lang"] = pdf_lang

        pdf_data = st.session_state["pdf_cache_data"]
        pdf_lang = st.session_state["pdf_cache_lang"]

        if pdf_lang != lang:
            st.caption(tr("pdf_fallback"))

        safe_name = re.sub(r'[\\/:*?"<>|\s]+', "_", f"{report['First name']}_{report['Last name']}")
        file_name_pdf = f"Diabetes_Report_{safe_name}.pdf"

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
