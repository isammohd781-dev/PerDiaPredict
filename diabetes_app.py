import base64
import calendar
import unicodedata
import hashlib
from io import BytesIO
from html import escape as html_escape
import hmac
import json
import os
import re
import secrets
import sqlite3
import tempfile
import time
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta

import joblib
import doctor_portal as care
import app_experience as ux
import admin_dashboard
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from translations import LANGUAGES, T
from screening_model import load_screening_artifacts, predict_screening

# =============================================================================
# PERDIAPREDICT - MULTILINGUAL VERSION
# Flow: splash -> language gate (continue / change language) -> app
# =============================================================================

_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
_page_icon = _icon_path if os.path.exists(_icon_path) else None

st.set_page_config(
    page_title="PerdiaPredict",
    page_icon=_page_icon,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Files / configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "diabetes_model.pkl")
COLUMNS_PATH = os.path.join(BASE_DIR, "feature_columns.pkl")
SAVE_FILE_XLSX = os.path.join(BASE_DIR, "saved_reports.xlsx")
AUDIT_LOG_FILE = os.path.join(BASE_DIR, "audit_log.xlsx")
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")


def _get_secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get("PERDIA_" + key, os.environ.get(key, default))


ADMIN_PASSWORD = _get_secret("ADMIN_PASSWORD","EsamDiku12345")


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
# -----------------------------------------------------------------------------
POLYURIA_FREQ_KEYS = ["freq_8_10", "freq_11_15", "freq_15_plus", "freq_unsure"]

MALE_SYMPTOM_KEYS = [
    "male_erectile", "male_libido", "male_muscle", "male_genital_itch", "male_fertility",
]
FEMALE_SYMPTOM_KEYS = [
    "female_yeast", "female_uti", "female_periods", "female_hair", "female_dryness", "female_gdm",
]

MALE_INTIMATE_KEYS = ["male_erectile", "male_libido", "male_fertility"]
FEMALE_INTIMATE_KEYS = ["female_dryness", "female_gdm"]


def gender_question_keys(gender: str, ever_married: bool) -> list:
    """Adult questions are independent of relationship status."""
    if gender == "Other":
        return list(OTHER_GENERAL_SYMPTOM_KEYS)
    return list(MALE_SYMPTOM_KEYS if gender == "Male" else FEMALE_SYMPTOM_KEYS)



# -----------------------------------------------------------------------------
# Marital status, gender-agreeing.
# -----------------------------------------------------------------------------
MARITAL_STATUS_ORDER = ["single", "married", "divorced", "widowed", "separated", "prefer_not", "child"]

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


for _code, _labels in {
    "en": ("Widowed", "Separated", "Prefer not to say"),
    "ar": ("أرمل / أرملة", "منفصل / منفصلة", "أفضل عدم الإجابة"),
    "es": ("Viudo/a", "Separado/a", "Prefiero no decirlo"),
}.items():
    for _key, _label in zip(("widowed", "separated", "prefer_not"), _labels):
        MARITAL_STATUS_TEXT[_code][_key] = dict.fromkeys(GENDER_OPTIONS if "GENDER_OPTIONS" in globals() else ["Male", "Female", "Other"], _label)
MARITAL_STATUS_TEXT["en"]["divorced"] = dict.fromkeys(["Male", "Female"], "Divorced (or widowed in an existing account)")
MARITAL_STATUS_TEXT["ar"]["divorced"] = {"Male": "مطلّق (أو أرمل في الحسابات السابقة)", "Female": "مطلّقة (أو أرملة في الحسابات السابقة)"}

def marital_status_label(status: str, gender: str, lang: str = None) -> str:
    """Gender-agreeing label for a marital-status option."""
    lang = lang or st.session_state.get("lang", "en")
    if gender == "Other" and lang == "ar":
        return {"single":"غير متزوج", "married":"متزوج", "divorced":"مطلّق / مطلّقة (أو أرمل سابقًا)", "widowed":"أرمل / أرملة", "separated":"منفصل / منفصلة", "prefer_not":"أفضل عدم الإجابة", "child":"طفل / طفلة"}.get(status, status)
    gender = gender if gender in ("Male", "Female") else "Male"
    table = MARITAL_STATUS_TEXT.get(lang) or MARITAL_STATUS_TEXT["en"]
    entry = table.get(status) or MARITAL_STATUS_TEXT["en"][status]
    return entry.get(gender, entry.get("Male", ""))


# -----------------------------------------------------------------------------
# Pediatric questions.
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


# -----------------------------------------------------------------------------
# Gender options: Male / Female / Other
# -----------------------------------------------------------------------------
GENDER_OPTIONS = ["Male", "Female", "Other"]

OTHER_GENERAL_SYMPTOM_KEYS = [
    "other_fatigue",
    "other_vision",
    "other_thirst",
    "other_weight",
    "other_healing",
    "other_infections",
]
BIRTH_SEX_OPTIONS = ["Male", "Female"]

TRANS_SYMPTOM_KEYS = [
    "trans_hormones", "trans_weight", "trans_surgery", "trans_infections", "trans_periods",
]


def gender_label(value: str, lang: str = None) -> str:
    """Display text for a gender value (Male / Female / Other)."""
    mapping = {
        "Male": "male",
        "Female": "female",
        "Other": "other_gender",
    }
    return tr(mapping.get(value, "male"), lang)


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
        "transgender": "Transgender",
        "other_gender": "Other",
        "other_section": "General questions",
        "other_section_help": "These are general questions for patients who prefer not to specify male or female. They do not change the estimated probability.",
        "other_fatigue": "Constant fatigue or tiredness",
        "other_vision": "Blurred or unclear vision",
        "other_thirst": "Excessive thirst",
        "other_weight": "Unexplained weight change",
        "other_healing": "Slow healing of wounds",
        "other_infections": "Frequent infections",
        "sex_at_birth": "Sex Assigned at Birth",
        "gender_identity": "Gender Identity",
        "intersex": "Intersex",
        "unknown": "Unknown / Prefer not to say",
        "non_binary": "Non-binary",
        "genderqueer": "Genderqueer",
        "another_gender": "Another gender category",
        "prefer_not_disclose": "Prefer not to disclose",
        "sex_at_birth_help": "Sex recorded on your original birth certificate. Used for medical assessment only.",
        "gender_identity_help": "How you describe your gender identity. Added to your report to help your doctor.",
        "birth_sex": "Sex assigned at birth",
        "birth_sex_short": "at birth",
        "trans_section": "Questions specific to transgender patients",
        "trans_hormones": "Currently taking gender-affirming hormones (estrogen or testosterone)",
        "trans_weight": "Weight gain or increased body fat since starting hormone therapy",
        "trans_surgery": "Previous gender-affirming surgery",
        "trans_infections": "Repeated genital or urinary tract infections",
        "trans_periods": "Irregular or absent menstrual periods (if applicable)",
        "skin_tags": "Skin tags (small, soft growths on the skin)",
        "glycosuria": "Sugar in the urine (glycosuria)",
        "hyperglycemia": "High blood sugar readings (hyperglycemia)",
        "sweet_craving": "Craving for sweet things",
        "glucose_level": "Blood sugar / glucose level",
        "patient_id_label": "Patient ID",
        "glucose_unit": "Unit",
        "glucose_help": "Leave it empty if you have not measured it. It is added to your report but does not change the estimated probability.",
        "glucose_invalid": "Please enter a realistic blood glucose value for the selected unit, or leave it empty.",
        "diet_preference": "Diet preference",
        "diet_nonveg": "Non-vegetarian",
        "diet_veg": "Vegetarian",
        "auth_pill": "Secure access",
        "auth_title": "Sign in or create an account",
        "auth_intro": "Are you already registered with us, or are you new? Choose an option to continue.",
        "auth_registered": "I'm already registered",
        "auth_new": "I'm a new user",
        "login_title": "Sign in",
        "login_intro": "Enter your email and password to continue.",
        "auth_email": "Email address",
        "auth_password": "Password",
        "auth_confirm_password": "Confirm password",
        "login_button": "Sign in",
        "login_fill": "Please enter your email and password.",
        "login_invalid": "Incorrect email or password.",
        "login_locked": "Too many failed attempts. Please try again in a few minutes, or contact technical support.",
        "support_title": "Technical support",
        "support_text": "Need help or forgot your password? Contact us on WhatsApp:",
        "reg_title": "Create your account",
        "reg_intro": "Your information is protected and kept strictly confidential.",
        "dob": "Date of birth",
        "dob_day": "Day",
        "dob_month": "Month",
        "dob_year": "Year",
        "dob_choose": "Type or choose",
        "reg_warn_title": "Important warning",
        "reg_warn_text": "There is no 'Forgot password' option. We protect your data with complete confidentiality, so passwords cannot be viewed or recovered by anyone. If you forget your password, please contact technical support only.",
        "reg_accept": "I have read and understood this warning",
        "reg_button": "Create account",
        "reg_fill_all": "Please fill in all the required fields.",
        "reg_email_invalid": "Please enter a valid email address.",
        "reg_pw_short": "The password must be at least 8 characters long.",
        "reg_pw_mismatch": "The passwords do not match.",
        "reg_dob_invalid": "Please choose a valid date of birth.",
        "reg_accept_required": "Please tick the box to confirm that you understood the warning.",
        "auth_email_taken": "This email is already registered. Please sign in instead.",
        "auth_db_error": "Could not save your account. Please try again or contact technical support.",
        "logout": "Log out",
        "change_password_title": "Set a new password",
        "change_password_intro": "For security, you must set a new password before continuing.",
        "new_password": "New password",
        "confirm_new_password": "Confirm new password",
        "save_new_password": "Save new password",
        "password_changed": "Password changed successfully!",
        "foods_items_veg": [
            "Non-starchy vegetables: leafy greens, broccoli, cauliflower, cucumber, tomatoes",
            "Legumes: lentils, chickpeas, beans, moong dal",
            "Plant proteins and dairy: tofu, paneer or cottage cheese, plain low-fat yogurt",
            "Whole grains: oats, brown rice, quinoa, whole-wheat bread and roti",
            "Nuts and seeds in small portions: almonds, walnuts, flax and chia seeds",
            "Low-sugar fruits in moderation: berries, apples, guava, pears",
            "Healthy fats: olive oil, avocado",
        ],
        "meal_plan_rows_veg": [
            ["Day 1", "Oats porridge with nuts and cinnamon", "Lentil soup, cucumber salad and a small portion of brown rice", "Grilled paneer with sautéed vegetables", "Water, unsweetened green tea"],
            ["Day 2", "Whole-wheat toast with avocado and tomato", "Chickpea salad with mixed vegetables and 1 whole-wheat roti", "Vegetable soup with baked tofu", "Water, unsweetened herbal tea"],
            ["Day 3", "Plain yogurt with chia seeds and berries", "Kidney bean curry, a small portion of brown rice and salad", "Bell peppers stuffed with quinoa", "Water, unsweetened buttermilk"],
            ["Day 4", "Chickpea-flour pancake (besan chilla) with mint chutney", "Vegetable and lentil stew with 1 whole-wheat roti", "Grilled vegetables with hummus", "Water, cinnamon tea"],
            ["Day 5", "Vegetable poha with a few peanuts (small portion)", "Spinach and paneer curry with a side salad", "Moong dal soup with steamed vegetables", "Water, unsweetened green tea"],
            ["Day 6", "Overnight oats with flaxseed and apple slices", "Quinoa and vegetable pulao with plain yogurt", "Tofu and broccoli stir-fry", "Water, lemon water without sugar"],
            ["Day 7", "Whole-wheat sandwich with vegetables and cottage cheese", "Black bean and vegetable bowl with a small portion of brown rice", "Cauliflower and pea curry with 1 roti", "Water, unsweetened herbal tea"],
        ],
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
        "transgender": "عابر جنسيًا (Transgender)",
        "other_gender": "آخر",
        "other_section": "أسئلة عامة",
        "other_section_help": "هذه أسئلة عامة للمرضى الذين لا يرغبون في تحديد ذكر أو أنثى. لا تغيّر نسبة الاحتمال المقدَّرة.",
        "other_fatigue": "إرهاق أو تعب مستمر",
        "other_vision": "تشوش أو ضعف في الرؤية",
        "other_thirst": "عطش شديد",
        "other_weight": "تغير غير مبرر في الوزن",
        "other_healing": "بطء في التئام الجروح",
        "other_infections": "التهابات متكررة",
        "sex_at_birth": "الجنس المسجّل عند الولادة",
        "gender_identity": "الهوية الجنسية",
        "intersex": "ثنائي الجنس",
        "unknown": "غير معروف / أفضّل عدم الذكر",
        "non_binary": "ثنائي غير محدّد",
        "genderqueer": "جندري كوير",
        "another_gender": "فئة جندرية أخرى",
        "prefer_not_disclose": "أفضّل عدم الإفصاح",
        "sex_at_birth_help": "الجنس المسجّل في شهادة ميلادك الأصلية. يُستخدم للتقييم الطبي فقط.",
        "gender_identity_help": "كيف تصف هويتك الجنسية. تُضاف إلى تقريرك لمساعدة طبيبك.",
        "birth_sex": "الجنس المحدد عند الولادة",
        "birth_sex_short": "عند الولادة",
        "trans_section": "أسئلة خاصة بالمرضى العابرين جنسيًا",
        "trans_hormones": "تناول هرمونات تأكيد الجنس حاليًا (إستروجين أو تستوستيرون)",
        "trans_weight": "زيادة في الوزن أو الدهون منذ بدء العلاج الهرموني",
        "trans_surgery": "إجراء عملية تأكيد الجنس سابقًا",
        "trans_infections": "التهابات متكررة في المنطقة التناسلية أو المسالك البولية",
        "trans_periods": "اضطراب أو انقطاع الدورة الشهرية (إن وُجدت)",
        "skin_tags": "زوائد جلدية (Skin tags)",
        "glycosuria": "وجود سكر في البول (Glycosuria)",
        "hyperglycemia": "ارتفاع سكر الدم (Hyperglycemia)",
        "sweet_craving": "اشتهاء شديد للحلويات والسكريات",
        "glucose_level": "مستوى السكر / الجلوكوز في الدم",
        "patient_id_label": "الرقم التعريفي للمريض",
        "glucose_unit": "الوحدة",
        "glucose_help": "اتركه فارغًا إن لم تقم بقياسه. يُضاف إلى التقرير ولا يغيّر نسبة الاحتمال المقدَّرة.",
        "glucose_invalid": "يرجى إدخال قيمة سكر منطقية للوحدة المختارة، أو اتركه فارغًا.",
        "diet_preference": "نوع النظام الغذائي",
        "diet_nonveg": "غير نباتي (يشمل اللحوم والأسماك)",
        "diet_veg": "نباتي",
        "auth_pill": "دخول آمن",
        "auth_title": "تسجيل الدخول أو إنشاء حساب",
        "auth_intro": "هل أنت مسجّل لدينا أم مستخدم جديد؟ اختر أحد الخيارات للمتابعة.",
        "auth_registered": "أنا مسجّل لديكم",
        "auth_new": "أنا مستخدم جديد",
        "login_title": "تسجيل الدخول",
        "login_intro": "أدخل بريدك الإلكتروني وكلمة المرور للمتابعة.",
        "auth_email": "البريد الإلكتروني",
        "auth_password": "كلمة المرور",
        "auth_confirm_password": "تأكيد كلمة المرور",
        "login_button": "دخول",
        "login_fill": "يرجى إدخال البريد الإلكتروني وكلمة المرور.",
        "login_invalid": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
        "login_locked": "محاولات خاطئة كثيرة. حاول مجددًا بعد بضع دقائق، أو تواصل مع الدعم الفني.",
        "support_title": "الدعم الفني",
        "support_text": "تحتاج مساعدة أو نسيت كلمة المرور؟ تواصل معنا عبر واتساب:",
        "reg_title": "إنشاء حساب جديد",
        "reg_intro": "بياناتك محمية وتُحفظ بسرية تامة.",
        "dob": "تاريخ الميلاد",
        "dob_day": "اليوم",
        "dob_month": "الشهر",
        "dob_year": "السنة",
        "dob_choose": "اكتب أو اختر",
        "reg_warn_title": "تحذير مهم",
        "reg_warn_text": "لا يوجد خيار «نسيت كلمة المرور»، لأننا نحمي بياناتكم بسرية تامة ولا يمكن لأي أحد الاطلاع على كلمات المرور أو استرجاعها.",
        "reg_accept": "قرأتُ التحذير وفهمته",
        "reg_button": "إنشاء الحساب",
        "reg_fill_all": "يرجى تعبئة جميع الحقول المطلوبة.",
        "reg_email_invalid": "يرجى إدخال بريد إلكتروني صحيح.",
        "reg_pw_short": "يجب ألا تقل كلمة المرور عن 8 أحرف.",
        "reg_pw_mismatch": "كلمتا المرور غير متطابقتين.",
        "reg_dob_invalid": "يرجى اختيار تاريخ ميلاد صحيح.",
        "reg_accept_required": "يرجى تحديد المربع لتأكيد أنك فهمت التحذير.",
        "auth_email_taken": "هذا البريد الإلكتروني مسجّل مسبقًا. يرجى تسجيل الدخول بدلًا من ذلك.",
        "auth_db_error": "تعذّر حفظ الحساب. حاول مرة أخرى أو تواصل مع الدعم الفني.",
        "logout": "تسجيل الخروج",
        "change_password_title": "تعيين كلمة مرور جديدة",
        "change_password_intro": "لأسباب أمنية، يجب تعيين كلمة مرور جديدة قبل المتابعة.",
        "new_password": "كلمة المرور الجديدة",
        "confirm_new_password": "تأكيد كلمة المرور الجديدة",
        "save_new_password": "حفظ كلمة المرور الجديدة",
        "password_changed": "تم تغيير كلمة المرور بنجاح!",
        "foods_items_veg": [
            "خضروات غير نشوية: ورقيات، بروكلي، قرنبيط، خيار، طماطم",
            "البقوليات: عدس، حمص، فاصوليا، فول",
            "بروتينات نباتية وألبان: توفو، جبنة قريش، لبن زبادي قليل الدسم",
            "حبوب كاملة: شوفان، أرز بني، كينوا، خبز القمح الكامل",
            "مكسرات وبذور بكميات صغيرة: لوز، جوز، بذور الكتان والشيا",
            "فواكه قليلة السكر باعتدال: توت، تفاح، جوافة، كمثرى",
            "دهون صحية: زيت الزيتون، أفوكادو",
        ],
        "meal_plan_rows_veg": [
            ["اليوم 1", "شوفان بالمكسرات والقرفة", "شوربة عدس مع سلطة خيار وحصة صغيرة من الأرز البني", "جبنة قريش مشوية مع خضار سوتيه", "ماء، شاي أخضر بدون سكر"],
            ["اليوم 2", "خبز أسمر محمص مع أفوكادو وطماطم", "سلطة حمص مع خضار متنوعة ورغيف صغير من القمح الكامل", "شوربة خضار مع توفو مشوي", "ماء، شاي أعشاب بدون سكر"],
            ["اليوم 3", "زبادي سادة مع بذور الشيا والتوت", "فاصوليا حمراء مع حصة صغيرة من الأرز البني وسلطة", "فلفل ملون محشو بالكينوا", "ماء، عيران (لبن رائب) بدون سكر"],
            ["اليوم 4", "فطيرة رقيقة من دقيق الحمص مع صلصة النعناع", "يخنة عدس وخضار مع رغيف قمح كامل", "خضار مشوية مع حمص", "ماء، شاي بالقرفة"],
            ["اليوم 5", "بوها الخضار مع قليل من الفول السوداني (حصة صغيرة)", "سبانخ مع جبنة قريش وسلطة جانبية", "شوربة ماش مع خضار مطهوة على البخار", "ماء، شاي أخضر بدون سكر"],
            ["اليوم 6", "شوفان منقوع طوال الليل مع بذور الكتان وشرائح التفاح", "كينوا بالخضار مع زبادي سادة", "توفو مقلّب مع البروكلي بقليل من الزيت", "ماء، ماء بالليمون بدون سكر"],
            ["اليوم 7", "ساندويتش خبز أسمر بالخضار والجبنة القريش", "طبق فاصوليا سوداء وخضار مع حصة صغيرة من الأرز البني", "قرنبيط وبازلاء مطبوخة مع رغيف صغير", "ماء، شاي أعشاب بدون سكر"],
        ],
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
        "transgender": "Transgénero",
        "other_gender": "Otro",
        "other_section": "Preguntas generales",
        "other_section_help": "Preguntas generales para pacientes que prefieren no especificar hombre o mujer. No modifican la probabilidad estimada.",
        "other_fatigue": "Fatiga o cansancio constante",
        "other_vision": "Visión borrosa o poco clara",
        "other_thirst": "Sed excesiva",
        "other_weight": "Cambio de peso sin explicación",
        "other_healing": "Curación lenta de heridas",
        "other_infections": "Infecciones frecuentes",
        "sex_at_birth": "Sexo asignado al nacer",
        "gender_identity": "Identidad de género",
        "intersex": "Intersexual",
        "unknown": "Desconocido / Prefiero no decir",
        "non_binary": "No binario",
        "genderqueer": "Genderqueer",
        "another_gender": "Otra categoría de género",
        "prefer_not_disclose": "Prefiero no divulgarlo",
        "sex_at_birth_help": "Sexo registrado en tu certificado de nacimiento. Solo para evaluación médica.",
        "gender_identity_help": "Cómo describes tu identidad de género. Se añade a tu informe.",
        "birth_sex": "Sexo asignado al nacer",
        "birth_sex_short": "al nacer",
        "trans_section": "Preguntas específicas para pacientes transgénero",
        "trans_hormones": "Toma actualmente hormonas de afirmación de género (estrógeno o testosterona)",
        "trans_weight": "Aumento de peso o de grasa corporal desde que inició la terapia hormonal",
        "trans_surgery": "Cirugía de afirmación de género previa",
        "trans_infections": "Infecciones genitales o urinarias repetidas",
        "trans_periods": "Menstruación irregular o ausente (si aplica)",
        "skin_tags": "Acrocordones (pequeños crecimientos blandos en la piel)",
        "glycosuria": "Azúcar en la orina (glucosuria)",
        "hyperglycemia": "Azúcar alta en sangre (hiperglucemia)",
        "sweet_craving": "Antojo de dulces",
        "glucose_level": "Nivel de azúcar / glucosa en sangre",
        "patient_id_label": "ID del paciente",
        "glucose_unit": "Unidad",
        "glucose_help": "Déjalo vacío si no lo has medido. Se añade al informe pero no modifica la probabilidad estimada.",
        "glucose_invalid": "Introduce un valor de glucosa realista para la unidad elegida, o déjalo vacío.",
        "diet_preference": "Preferencia alimentaria",
        "diet_nonveg": "No vegetariano",
        "diet_veg": "Vegetariano",
        "auth_pill": "Acceso seguro",
        "auth_title": "Inicia sesión o crea una cuenta",
        "auth_intro": "¿Ya estás registrado con nosotros o eres un usuario nuevo? Elige una opción para continuar.",
        "auth_registered": "Ya estoy registrado",
        "auth_new": "Soy un usuario nuevo",
        "login_title": "Iniciar sesión",
        "login_intro": "Introduce tu correo electrónico y tu contraseña para continuar.",
        "auth_email": "Correo electrónico",
        "auth_password": "Contraseña",
        "auth_confirm_password": "Confirmar contraseña",
        "login_button": "Entrar",
        "login_fill": "Introduce tu correo electrónico y tu contraseña.",
        "login_invalid": "Correo electrónico o contraseña incorrectos.",
        "login_locked": "Demasiados intentos fallidos. Inténtalo de nuevo en unos minutos o contacta con el soporte técnico.",
        "support_title": "Soporte técnico",
        "support_text": "¿Necesitas ayuda u olvidaste tu contraseña? Escríbenos por WhatsApp:",
        "reg_title": "Crea tu cuenta",
        "reg_intro": "Tu información está protegida y se mantiene en estricta confidencialidad.",
        "dob": "Fecha de nacimiento",
        "dob_day": "Día",
        "dob_month": "Mes",
        "dob_year": "Año",
        "dob_choose": "Escribe o elige",
        "reg_warn_title": "Advertencia importante",
        "reg_warn_text": "No existe la opción 'Olvidé mi contraseña'. Protegemos tus datos con total confidencialidad.",
        "reg_accept": "He leído y entendido esta advertencia",
        "reg_button": "Crear cuenta",
        "reg_fill_all": "Completa todos los campos obligatorios.",
        "reg_email_invalid": "Introduce un correo electrónico válido.",
        "reg_pw_short": "La contraseña debe tener al menos 8 caracteres.",
        "reg_pw_mismatch": "Las contraseñas no coinciden.",
        "reg_dob_invalid": "Elige una fecha de nacimiento válida.",
        "reg_accept_required": "Marca la casilla para confirmar que entendiste la advertencia.",
        "auth_email_taken": "Este correo ya está registrado. Inicia sesión en su lugar.",
        "auth_db_error": "No se pudo guardar la cuenta. Inténtalo de nuevo o contacta con el soporte técnico.",
        "logout": "Cerrar sesión",
        "change_password_title": "Establecer una nueva contraseña",
        "change_password_intro": "Por seguridad, debes establecer una nueva contraseña antes de continuar.",
        "new_password": "Nueva contraseña",
        "confirm_new_password": "Confirmar nueva contraseña",
        "save_new_password": "Guardar nueva contraseña",
        "password_changed": "¡Contraseña cambiada exitosamente!",
        "foods_items_veg": [
            "Verduras sin almidón: hojas verdes, brócoli, coliflor, pepino, tomate",
            "Legumbres: lentejas, garbanzos, frijoles, dal de moong",
            "Proteínas vegetales y lácteos: tofu, queso fresco o paneer, yogur natural bajo en grasa",
            "Cereales integrales: avena, arroz integral, quinoa, pan integral y roti",
            "Frutos secos y semillas en porciones pequeñas: almendras, nueces, semillas de lino y chía",
            "Frutas bajas en azúcar con moderación: frutos rojos, manzana, guayaba, pera",
            "Grasas saludables: aceite de oliva, aguacate",
        ],
        "meal_plan_rows_veg": [
            ["Día 1", "Avena con frutos secos y canela", "Sopa de lentejas, ensalada de pepino y una porción pequeña de arroz integral", "Queso paneer a la plancha con verduras salteadas", "Agua, té verde sin azúcar"],
            ["Día 2", "Tostada integral con aguacate y tomate", "Ensalada de garbanzos con verduras y 1 roti integral", "Sopa de verduras con tofu al horno", "Agua, infusión sin azúcar"],
            ["Día 3", "Yogur natural con semillas de chía y frutos rojos", "Frijoles rojos con una porción pequeña de arroz integral y ensalada", "Pimientos rellenos de quinoa", "Agua, suero de mantequilla sin azúcar"],
            ["Día 4", "Tortita de harina de garbanzo (besan chilla) con salsa de menta", "Estofado de verduras y lentejas con 1 roti integral", "Verduras asadas con hummus", "Agua, té de canela"],
            ["Día 5", "Poha de verduras con unos pocos cacahuetes (porción pequeña)", "Curry de espinacas y paneer con ensalada", "Sopa de moong dal con verduras al vapor", "Agua, té verde sin azúcar"],
            ["Día 6", "Avena de la noche anterior con linaza y rodajas de manzana", "Pulao de quinoa y verduras con yogur natural", "Salteado de tofu y brócoli", "Agua, agua con limón sin azúcar"],
            ["Día 7", "Sándwich integral con verduras y queso fresco", "Bol de frijoles negros y verduras con una porción pequeña de arroz integral", "Curry de coliflor y guisantes con 1 roti", "Agua, infusión sin azúcar"],
        ],
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


PROFILE_COPY = {
    "en": {"edit":"Edit profile", "save":"Save changes", "cancel":"Cancel", "doctor":"Type confirmed by a doctor", "type_help":"Type 1 (the body makes little or no insulin) · Type 2 (the body does not use insulin well)", "type_locked":"The recorded type can only be set once from ‘Not sure’ after a doctor confirms it.", "question_title":"Questions for your recorded type", "question_note":"These answers are added to the report; they do not change the trained model's percentage.", "general_title":"General questions", "error":"Please enter a valid phone number and country."},
    "ar": {"edit":"تعديل الملف الشخصي", "save":"حفظ التغييرات", "cancel":"إلغاء", "doctor":"أكد الطبيب نوع السكري", "type_help":"النوع الأول (الجسم ينتج القليل من الإنسولين أو لا ينتجه) · النوع الثاني (الجسم لا يستخدم الإنسولين جيدًا)", "type_locked":"يمكن تحديد النوع مرة واحدة فقط من «لا أعرف» بعد تأكيد الطبيب.", "question_title":"أسئلة حسب النوع المسجّل", "question_note":"تُضاف الإجابات إلى التقرير ولا تغيّر نسبة النموذج المدرّب.", "general_title":"أسئلة عامة", "error":"أدخل دولة ورقم هاتف صحيحين."},
    "es": {"edit":"Editar perfil", "save":"Guardar cambios", "cancel":"Cancelar", "doctor":"Tipo confirmado por un médico", "type_help":"Tipo 1 (el cuerpo produce poca o ninguna insulina) · Tipo 2 (el cuerpo no usa bien la insulina)", "type_locked":"Solo se puede establecer una vez desde «No sé», tras confirmación médica.", "question_title":"Preguntas según el tipo registrado", "question_note":"Estas respuestas se añaden al informe; no cambian el porcentaje del modelo.", "general_title":"Preguntas generales", "error":"Introduce un país y teléfono válidos."},
    "hi": {"edit":"प्रोफ़ाइल बदलें", "save":"बदलाव सहेजें", "cancel":"रद्द करें", "doctor":"डॉक्टर ने प्रकार बताया", "type_help":"टाइप 1 (शरीर बहुत कम या कोई इंसुलिन नहीं बनाता) · टाइप 2 (शरीर इंसुलिन का सही उपयोग नहीं करता)", "type_locked":"डॉक्टर की पुष्टि के बाद केवल ‘पता नहीं’ से एक बार बदल सकते हैं।", "question_title":"दर्ज प्रकार के सवाल", "question_note":"ये जवाब रिपोर्ट में जुड़ते हैं; मॉडल का प्रतिशत नहीं बदलते।", "general_title":"सामान्य सवाल", "error":"सही देश और फ़ोन नंबर दें।"},
    "zh": {"edit":"编辑资料", "save":"保存更改", "cancel":"取消", "doctor":"医生已确认类型", "type_help":"1型（身体产生很少或不产生胰岛素）· 2型（身体不能有效利用胰岛素）", "type_locked":"医生确认后，只能从“不确定”设置一次。", "question_title":"针对已登记类型的问题", "question_note":"答案会加入报告，不改变模型的预测百分比。", "general_title":"一般问题", "error":"请输入有效的国家和电话号码。"},
}

EDIT_TEXT = {
    "en": {"photo":"Profile photo", "upload":"Choose a photo from your device", "remove":"Remove current photo", "photo_help":"JPG, PNG or WebP, up to 5 MB.", "bad_photo":"Choose a valid image up to 5 MB.", "confirm":"Confirm changes", "confirm_save":"Save these profile changes?", "lock_warning":"You are recording a doctor-confirmed diabetes type. After saving, you cannot change it or return to ‘Not sure’. Are you sure?", "yes_save":"Yes, save changes", "no_save":"No, keep editing", "personal":"Personal details", "contact":"Contact details", "health":"Health information", "security":"Account security", "required":"Fields marked * are required.", "optional":"Answer the questions that apply to you. Relationship status does not determine your symptoms."},
    "ar": {"photo":"الصورة الشخصية", "upload":"اختر صورة من جهازك", "remove":"حذف الصورة الحالية", "photo_help":"JPG أو PNG أو WebP، حتى 5 ميجابايت.", "bad_photo":"اختر صورة صحيحة لا تتجاوز 5 ميجابايت.", "confirm":"تأكيد التغييرات", "confirm_save":"هل تريد حفظ تعديلات الملف الشخصي؟", "lock_warning":"ستسجّل نوع السكري الذي أكّده الطبيب. بعد الحفظ لا يمكنك تغيير النوع أو الرجوع إلى «لا أعرف». هل أنت متأكد؟", "yes_save":"نعم، احفظ التغييرات", "no_save":"لا، متابعة التعديل", "personal":"البيانات الشخصية", "contact":"بيانات التواصل", "health":"المعلومات الصحية", "security":"أمان الحساب", "required":"الحقول التي تحمل * مطلوبة.", "optional":"أجب عن الأسئلة التي تنطبق عليك. الحالة الاجتماعية لا تحدد الأعراض."},
}

def edit_text(key):
    return EDIT_TEXT.get(st.session_state.get("lang"), EDIT_TEXT["en"])[key]


def profile_photo_bytes(user):
    name = user.get("profile_photo", "")
    if not name or os.path.basename(name) != name:
        return None
    path = os.path.join(BASE_DIR, "profile_photos", name)
    try:
        with open(path, "rb") as photo:
            return photo.read()
    except OSError:
        return None


def commit_profile_changes(changes):
    user = st.session_state.get("user") or {}
    changes.pop("warn_unknown", None)
    photo_data = changes.pop("photo_data", None)
    photo_name = changes.pop("photo_name", None)
    if photo_data is not None:
        os.makedirs(os.path.join(BASE_DIR, "profile_photos"), exist_ok=True)
        photo_name = hashlib.sha256(photo_data).hexdigest() + ".png"
        target = os.path.join(BASE_DIR, "profile_photos", photo_name)
        with open(target + ".tmp", "wb") as out:
            out.write(photo_data)
        os.replace(target + ".tmp", target)
    saved = update_user_profile(user.get("email", ""), **changes, profile_photo=photo_name)
    if not saved:
        st.error(profile_copy("error"))
        return
    user.update({key: saved.get(key, "") for key in
                 ("marital_status", "country", "dial_code", "phone", "diabetes_type", "profile_photo")})
    st.session_state.pop("pending_profile_changes", None)
    go_to(st.session_state.pop("profile_return_page", "main"))



def inject_profile_layout_css():
    dark = st.session_state.get("dark_mode", True)
    bg, ink, border, muted = ("#111c2e", "#eef4ff", "#34465e", "#aabbd2") if dark else ("#ffffff", "#172b45", "#d8e2ee", "#586b82")
    st.markdown(f"""<style>
    [data-testid="stDialog"] [role="dialog"] {{
        position:fixed !important; top:50% !important; left:50% !important;
        transform:translate(-50%, -50%) !important; margin:0 !important;
        width:min(520px, calc(100vw - 32px)) !important; max-width:520px !important;
        max-height:calc(100dvh - 48px) !important; overflow:auto !important;
        background:{bg} !important; color:{ink} !important;
        border:1px solid {border} !important; border-radius:22px !important;
        box-shadow:0 24px 80px rgba(0,0,0,.38) !important; padding:24px !important;
    }}
    [data-testid="stDialog"] [role="dialog"] [data-testid="stMarkdownContainer"],
    [data-testid="stDialog"] [role="dialog"] h2 {{color:{ink} !important;}}
    [data-testid="stDialog"] [role="dialog"] h2 {{font-size:1.3rem !important;padding:0 0 16px !important;}}
    [data-testid="stDialog"] [role="dialog"] [data-testid="stVerticalBlock"] {{gap:16px !important;}}
    [data-testid="stDialog"] [role="dialog"] button {{min-height:46px !important;border-radius:12px !important;}}
    [data-testid="stDialog"] [role="dialog"] button[kind="primary"] {{background:#2563eb !important;border:1px solid #2563eb !important;color:white !important;}}
    [data-testid="stDialog"] [role="dialog"] button[kind="secondary"] {{background:{bg} !important;border:1px solid {border} !important;color:{ink} !important;}}
    [data-testid="stDialog"] [role="dialog"] [data-testid="stAlert"] {{border-radius:12px !important;}}
    .st-key-profile_editor [data-testid="stForm"] {{border:1px solid {border} !important;border-radius:22px !important;padding:24px !important;background:{bg} !important;}}
    .st-key-profile_editor [data-testid="stForm"] [data-testid="stVerticalBlock"] {{gap:16px !important;}}
    .st-key-profile_editor h3 {{font-size:1.05rem !important;margin:0 !important;padding:8px 0 !important;color:{ink} !important;}}
    .st-key-profile_edit_actions button {{width:100%;min-height:46px;border-radius:12px;}}
    .st-key-profile_editor .profile-edit-avatar {{width:112px;height:112px;border-radius:50%;object-fit:cover;border:3px solid {border};display:block;margin:12px auto;}}
    .profile-edit-description {{color:{muted};margin:0 0 20px;font-size:.95rem;}}
    @media(max-width:640px) {{
        .st-key-profile_editor [data-testid="stForm"] {{padding:16px !important;}}
        [data-testid="stDialog"] [role="dialog"] {{padding:20px !important;}}
    }}
    </style>""", unsafe_allow_html=True)


@st.dialog("تأكيد التغييرات" if st.session_state.get("lang") == "ar" else "Confirm changes")
def confirm_profile_changes():
    inject_profile_layout_css()
    changes = st.session_state.get("pending_profile_changes")
    if not changes:
        return
    st.write(edit_text("confirm_save"))
    if changes.get("warn_unknown"):
        if changes.get("confirmed_type"):
            st.warning(edit_text("lock_warning"))
        else:
            st.warning("Your diabetes type is still recorded as ‘Not sure’. Choose a type only after a doctor confirms it. Once confirmed and saved, it cannot be changed back." if st.session_state.get("lang") != "ar" else "نوع السكري ما زال مسجّلًا «لا أعرف». لا تحدّد النوع إلا بعد تأكيد الطبيب. بعد تأكيد النوع وحفظه، لا يمكن تغييره أو الرجوع إلى «لا أعرف».")
    yes, no = st.columns(2)
    if yes.button(edit_text("yes_save"), type="primary", use_container_width=True):
        commit_profile_changes(dict(changes))
    if no.button(edit_text("no_save"), use_container_width=True):
        st.session_state.pop("pending_profile_changes", None)
        st.rerun()

TYPE_QUESTIONS = {
    "type1": ["t1_insulin", "t1_low_glucose", "t1_ketones"],
    "type2": ["t2_family", "t2_activity", "t2_high_glucose"],
}
TYPE_QUESTION_TEXT = {
    "en": {"t1_insulin":"Has a doctor prescribed insulin for you?", "t1_low_glucose":"Have you had episodes of low blood sugar?", "t1_ketones":"Have you ever been told your ketones were high?", "t2_family":"Does a parent or sibling have type 2 diabetes?", "t2_activity":"Are you physically active on most days?", "t2_high_glucose":"Have you previously been told your blood sugar was high?"},
    "ar": {"t1_insulin":"هل وصف لك الطبيب الإنسولين؟", "t1_low_glucose":"هل مررت بنوبات انخفاض سكر الدم؟", "t1_ketones":"هل أخبرك الطبيب بأن الكيتونات مرتفعة؟", "t2_family":"هل لدى أحد والديك أو إخوتك سكري النوع الثاني؟", "t2_activity":"هل تمارس نشاطًا بدنيًا في معظم الأيام؟", "t2_high_glucose":"هل أُخبرت سابقًا بأن سكر الدم مرتفع؟"},
    "es": {"t1_insulin":"¿Te recetó insulina un médico?", "t1_low_glucose":"¿Has tenido episodios de azúcar baja?", "t1_ketones":"¿Te han dicho que tus cetonas estaban altas?", "t2_family":"¿Tu padre, madre o hermano tiene diabetes tipo 2?", "t2_activity":"¿Haces actividad física la mayoría de los días?", "t2_high_glucose":"¿Te han dicho antes que tu azúcar estaba alta?"},
    "hi": {"t1_insulin":"क्या डॉक्टर ने आपको इंसुलिन दी है?", "t1_low_glucose":"क्या आपका ब्लड शुगर कभी कम हुआ है?", "t1_ketones":"क्या आपको कभी बताया गया कि कीटोन अधिक हैं?", "t2_family":"क्या माता-पिता या भाई-बहन को टाइप 2 है?", "t2_activity":"क्या आप अधिकतर दिन व्यायाम करते हैं?", "t2_high_glucose":"क्या पहले आपका ब्लड शुगर अधिक बताया गया था?"},
    "zh": {"t1_insulin":"医生给您开过胰岛素吗？", "t1_low_glucose":"您发生过低血糖吗？", "t1_ketones":"有人告诉您酮体偏高吗？", "t2_family":"父母或兄弟姐妹有2型糖尿病吗？", "t2_activity":"您大多数日子进行体育活动吗？", "t2_high_glucose":"以前有人告诉您血糖偏高吗？"},
}
for _lang, _questions in TYPE_QUESTION_TEXT.items():
    EXTRA_TEXT.setdefault(_lang, {}).update(_questions)

def profile_copy(key, lang=None):
    return PROFILE_COPY.get(lang or st.session_state.get("lang"), PROFILE_COPY["en"]).get(key, PROFILE_COPY["en"].get(key, key))

TYPE_EXPLANATIONS = {
    "en": {"type1": "the body makes little or no insulin", "type2": "the body does not use insulin well"},
    "ar": {"type1": "الجسم ينتج القليل من الإنسولين أو لا ينتجه", "type2": "الجسم لا يستخدم الإنسولين جيدًا"},
    "es": {"type1": "el cuerpo produce poca o ninguna insulina", "type2": "el cuerpo no usa bien la insulina"},
    "hi": {"type1": "शरीर बहुत कम या कोई इंसुलिन नहीं बनाता", "type2": "शरीर इंसुलिन का सही उपयोग नहीं करता"},
    "zh": {"type1": "身体产生很少或不产生胰岛素", "type2": "身体不能有效利用胰岛素"},
}

def diabetes_type_label(key, lang=None):
    lang = lang or st.session_state.get("lang", "en")
    explanation = TYPE_EXPLANATIONS.get(lang, TYPE_EXPLANATIONS["en"]).get(key)
    return f"{tr(key, lang)} ({explanation})" if explanation else tr(key, lang)

SPACING_OFF_LANGS = {"ar", "hi", "zh"}


def _init_theme():
    if "dark_mode" in st.session_state:
        return
    code = None
    try:
        code = st.query_params.get("theme")
    except Exception:
        pass
    st.session_state["dark_mode"] = code == "dark"


_init_theme()


def _toggle_theme():
    is_dark = not st.session_state.get("dark_mode", True)
    st.session_state["dark_mode"] = is_dark
    try:
        st.query_params["theme"] = "dark" if is_dark else "light"
    except Exception:
        pass


def is_rtl(lang: str = None) -> bool:
    lang = lang or st.session_state.get("lang", "en")
    return bool(LANGUAGES.get(lang, {}).get("rtl", False))


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
    "skin_tags": "skin_tags",
    "glycosuria": "glycosuria",
    "hyperglycemia": "hyperglycemia",
    "sweet_craving": "sweet_craving",
}

GENERAL_QUESTION_KEYS = ["family_diabetes", "previous_high_sugar", "blood_pressure", "sleep_difficulty", "regular_medicine"]
GENERAL_QUESTION_TEXT = {
    "en": ["Does a parent or sibling have diabetes?", "Has a previous blood test shown high blood sugar?", "Has a doctor told you that you have high blood pressure?", "Do you often have trouble sleeping?", "Do you take any medicines regularly?"],
    "ar": ["هل لدى أحد والديك أو إخوتك مرض السكري؟", "هل أظهر فحص دم سابق ارتفاع سكر الدم؟", "هل أخبرك الطبيب بأن لديك ارتفاعًا في ضغط الدم؟", "هل تواجه صعوبة في النوم بصورة متكررة؟", "هل تتناول أي أدوية بانتظام؟"],
    "es": ["¿Un padre o hermano tiene diabetes?", "¿Un análisis previo mostró azúcar alta?", "¿Un médico te ha diagnosticado presión alta?", "¿Sueles tener problemas para dormir?", "¿Tomas medicamentos regularmente?"],
    "hi": ["क्या माता-पिता या भाई-बहन को मधुमेह है?", "क्या पहले की जाँच में शुगर अधिक थी?", "क्या डॉक्टर ने उच्च रक्तचाप बताया है?", "क्या अक्सर नींद में परेशानी होती है?", "क्या आप नियमित दवाएँ लेते हैं?"],
    "zh": ["父母或兄弟姐妹患有糖尿病吗？", "之前的血液检查显示血糖偏高吗？", "医生告诉您患有高血压吗？", "您经常难以入睡吗？", "您定期服用药物吗？"],
}
for _code, _values in GENERAL_QUESTION_TEXT.items():
    EXTRA_TEXT.setdefault(_code, {}).update(dict(zip(GENERAL_QUESTION_KEYS, _values)))
extra_symptom_keys.update({key: key for key in GENERAL_QUESTION_KEYS})
REPORT_EXTRA_KEYS = list(extra_symptom_keys) + [key for keys in TYPE_QUESTIONS.values() for key in keys]

DIABETES_TYPE_KEYS = ["not_sure", "type1", "type2"]

# African Union member states (including Western Sahara), with E.164 calling codes.
# Western Sahara uses +212; there is no separate assigned international code.
COUNTRY_DIAL_CODES = [
    ("🇩🇿", "Algeria", "+213"), ("🇦🇴", "Angola", "+244"),
    ("🇧🇯", "Benin", "+229"), ("🇧🇼", "Botswana", "+267"),
    ("🇧🇫", "Burkina Faso", "+226"), ("🇧🇮", "Burundi", "+257"),
    ("🇨🇻", "Cabo Verde", "+238"), ("🇨🇲", "Cameroon", "+237"),
    ("🇨🇫", "Central African Republic", "+236"), ("🇹🇩", "Chad", "+235"),
    ("🇰🇲", "Comoros", "+269"), ("🇨🇬", "Congo (Republic)", "+242"),
    ("🇨🇩", "Congo (DRC)", "+243"), ("🇨🇮", "Côte d’Ivoire", "+225"),
    ("🇩🇯", "Djibouti", "+253"), ("🇪🇬", "Egypt", "+20"),
    ("🇬🇶", "Equatorial Guinea", "+240"), ("🇪🇷", "Eritrea", "+291"),
    ("🇸🇿", "Eswatini", "+268"), ("🇪🇹", "Ethiopia", "+251"),
    ("🇬🇦", "Gabon", "+241"), ("🇬🇲", "Gambia", "+220"),
    ("🇬🇭", "Ghana", "+233"), ("🇬🇳", "Guinea", "+224"),
    ("🇬🇼", "Guinea-Bissau", "+245"), ("🇰🇪", "Kenya", "+254"),
    ("🇱🇸", "Lesotho", "+266"), ("🇱🇷", "Liberia", "+231"),
    ("🇱🇾", "Libya", "+218"), ("🇲🇬", "Madagascar", "+261"),
    ("🇲🇼", "Malawi", "+265"), ("🇲🇱", "Mali", "+223"),
    ("🇲🇷", "Mauritania", "+222"), ("🇲🇺", "Mauritius", "+230"),
    ("🇲🇦", "Morocco", "+212"), ("🇲🇿", "Mozambique", "+258"),
    ("🇳🇦", "Namibia", "+264"), ("🇳🇪", "Niger", "+227"),
    ("🇳🇬", "Nigeria", "+234"), ("🇷🇼", "Rwanda", "+250"),
    ("🇸🇹", "São Tomé and Príncipe", "+239"), ("🇸🇳", "Senegal", "+221"),
    ("🇸🇨", "Seychelles", "+248"), ("🇸🇱", "Sierra Leone", "+232"),
    ("🇸🇴", "Somalia", "+252"), ("🇿🇦", "South Africa", "+27"),
    ("🇸🇸", "South Sudan", "+211"), ("🇸🇩", "Sudan", "+249"),
    ("🇹🇿", "Tanzania", "+255"), ("🇹🇬", "Togo", "+228"),
    ("🇹🇳", "Tunisia", "+216"), ("🇺🇬", "Uganda", "+256"),
    ("🇪🇭", "Western Sahara", "+212"), ("🇿🇲", "Zambia", "+260"),
    ("🇿🇼", "Zimbabwe", "+263"),
    # Additional countries offered in the earlier version.
    ("🇦🇺", "Australia", "+61"), ("🇧🇩", "Bangladesh", "+880"),
    ("🇨🇦", "Canada", "+1"), ("🇨🇳", "China", "+86"),
    ("🇫🇷", "France", "+33"), ("🇩🇪", "Germany", "+49"),
    ("🇮🇳", "India", "+91"), ("🇵🇰", "Pakistan", "+92"),
    ("🇶🇦", "Qatar", "+974"), ("🇸🇦", "Saudi Arabia", "+966"),
    ("🇪🇸", "Spain", "+34"), ("🇦🇪", "United Arab Emirates", "+971"),
    ("🇬🇧", "United Kingdom", "+44"), ("🇺🇸", "United States", "+1"),
]

REGISTRATION_TEXT = {
    "en": ("Country", "Country calling code", "Phone number", "Enter a valid phone number (6–15 digits)."),
    "ar": ("الدولة", "مفتاح البلد", "رقم الهاتف", "أدخل رقم هاتف صحيحًا (من 6 إلى 15 رقمًا)."),
    "es": ("País", "Prefijo telefónico", "Número de teléfono", "Introduce un número válido (6 a 15 dígitos)."),
    "hi": ("देश", "देश कोड", "फ़ोन नंबर", "सही फ़ोन नंबर दर्ज करें (6–15 अंक)।"),
    "zh": ("国家", "国家区号", "电话号码", "请输入有效电话号码（6–15 位）。"),
}


def registration_text(index):
    return REGISTRATION_TEXT.get(st.session_state.get("lang"), REGISTRATION_TEXT["en"])[index]


GLUCOSE_UNITS = ["mg/dL", "mmol/L"]
GLUCOSE_RANGE = {"mg/dL": (20.0, 1000.0), "mmol/L": (1.1, 55.0)}


# =============================================================================
# Accounts database (Excel: accounts.xlsx)
# =============================================================================
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.xlsx")
DB_FILE = os.path.join(BASE_DIR, "perdiapredict.db")
PBKDF2_ITERATIONS = 260_000
MIN_PASSWORD_LEN = 8
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 5
SUPPORT_WHATSAPP_NUMBER = "+256771715275"
SUPPORT_WHATSAPP_URL = "https://wa.me/256771715275"
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ACCOUNT_FIELDS = [
    "id", "patient_id", "first_name", "last_name", "email", "birth_date",
    "gender", "marital_status", "diabetes_type", "country", "dial_code", "phone",
    "password_hash", "created_at", "last_login", "failed_attempts", "locked_until",
    "must_change_password", "profile_photo",
]
ACCOUNT_HEADERS = [
    "ID", "Patient ID", "First name", "Last name", "Email", "Birth date",
    "Gender", "Marital status", "Diabetes type", "Country", "Dial code", "Phone",
    "Password hash", "Created at", "Last login", "Failed attempts", "Locked until",
    "Must change password", "Profile photo",
]
_FIELD_BY_HEADER = dict(zip(ACCOUNT_HEADERS, ACCOUNT_FIELDS))


@st.cache_resource
def _accounts_store():
    import threading
    return {"lock": threading.RLock(), "mtime": None, "rows": []}


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def normalize_person_name(value: str) -> str:
    return " ".join((value or "").split())


def valid_person_name(value: str) -> bool:
    return (1 <= len(value) <= 60 and any(c.isalpha() for c in value)
            and all(c.isalpha() or unicodedata.category(c).startswith("M")
                    or c in " '-’" for c in value))


def normalize_registration_phone(value: str, dial_code: str) -> str:
    """Accept a local number or an international number for the selected country."""
    number = "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c
                     for c in (value or "").strip())
    number = re.sub(r"[\s()\-]", "", number)
    if not re.fullmatch(r"\+[1-9][0-9]{0,3}", dial_code or ""):
        raise ValueError("Invalid country code")
    if number.startswith("00"):
        number = "+" + number[2:]
    if number.startswith("+"):
        if not number.startswith(dial_code):
            raise ValueError("Country code does not match")
        local = number[len(dial_code):].lstrip("0")
    else:
        local = number.lstrip("0")
    full = dial_code + local
    if not re.fullmatch(r"[0-9]{4,14}", local) or not 6 <= len(full[1:]) <= 15:
        raise ValueError("Invalid phone number")
    return full


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iterations, salt_hex, hash_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _rows_from_sheet(ws) -> list:
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if not header:
        return []

    index = {}
    for i, name in enumerate(header):
        field = _FIELD_BY_HEADER.get(_cell_text(name))
        if field:
            index[field] = i
    if "email" not in index or "password_hash" not in index:
        return []

    def get(raw, field):
        i = index.get(field)
        return _cell_text(raw[i]) if i is not None and i < len(raw) else ""

    def as_int(text):
        try:
            return int(float(text))
        except (TypeError, ValueError):
            return 0

    out = []
    for raw in rows_iter:
        email = normalize_email(get(raw, "email"))
        pw_hash = get(raw, "password_hash")
        if not email or not pw_hash:
            continue
        out.append({
            "id": as_int(get(raw, "id")),
            "patient_id": get(raw, "patient_id"),
            "first_name": get(raw, "first_name"),
            "last_name": get(raw, "last_name"),
            "email": email,
            "birth_date": get(raw, "birth_date"),
            "gender": get(raw, "gender"),
            "marital_status": get(raw, "marital_status"),
            "diabetes_type": get(raw, "diabetes_type"),
            "country": get(raw, "country"),
            "dial_code": get(raw, "dial_code"),
            "phone": get(raw, "phone"),
            "profile_photo": get(raw, "profile_photo"),
            "password_hash": pw_hash,
            "must_change_password": 1 if get(raw, "must_change_password") == "1" else 0,
            "created_at": get(raw, "created_at"),
            "last_login": get(raw, "last_login"),
            "failed_attempts": as_int(get(raw, "failed_attempts")),
            "locked_until": get(raw, "locked_until"),
        })

    seen, next_id = set(), max([r["id"] for r in out] + [0]) + 1
    for r in out:
        if r["id"] <= 0 or r["id"] in seen:
            r["id"] = next_id
            next_id += 1
        seen.add(r["id"])
    return out


def _save_rows(rows: list):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "users"
    ws.append(ACCOUNT_HEADERS)
    for r in rows:
        ws.append([r.get(f, "") for f in ACCOUNT_FIELDS])

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"

    head_fill = PatternFill("solid", fgColor="2563EB")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    widths = [7, 13, 16, 16, 32, 13, 10, 16, 20, 22, 13, 19, 60, 20, 20, 15, 20, 18]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
    ws.freeze_panes = "A2"

    directory = os.path.dirname(os.path.abspath(ACCOUNTS_FILE))
    fd, tmp = tempfile.mkstemp(prefix="accounts_", suffix=".xlsx", dir=directory)
    os.close(fd)
    try:
        wb.save(tmp)
        os.replace(tmp, ACCOUNTS_FILE)
    finally:
        wb.close()
        if os.path.exists(tmp):
            os.remove(tmp)

    store = _accounts_store()
    store["rows"] = [dict(r) for r in rows]
    store["mtime"] = os.path.getmtime(ACCOUNTS_FILE)


def _import_old_sqlite() -> list:
    if not os.path.exists(DB_FILE):
        return []
    try:
        with closing(sqlite3.connect(DB_FILE, timeout=15)) as conn:
            conn.row_factory = sqlite3.Row
            found = conn.execute("SELECT * FROM users").fetchall()
        return [{
            "id": int(r["id"]),
            "first_name": r["first_name"] or "",
            "last_name": r["last_name"] or "",
            "email": normalize_email(r["email"]),
            "birth_date": r["birth_date"] or "",
            "gender": "",
            "marital_status": "",
            "password_hash": r["password_hash"] or "",
            "created_at": r["created_at"] or "",
            "last_login": r["last_login"] or "",
            "failed_attempts": int(r["failed_attempts"] or 0),
            "locked_until": r["locked_until"] or "",
        } for r in found if r["email"] and r["password_hash"]]
    except Exception:
        return []


def _load_rows() -> list:
    store = _accounts_store()
    with store["lock"]:
        if not os.path.exists(ACCOUNTS_FILE):
            old = _import_old_sqlite()
            if old:
                _save_rows(old)
                return [dict(r) for r in old]
            store["rows"], store["mtime"] = [], None
            return []

        mtime = os.path.getmtime(ACCOUNTS_FILE)
        if store["mtime"] != mtime:
            from openpyxl import load_workbook

            wb = load_workbook(ACCOUNTS_FILE, read_only=True, data_only=True)
            try:
                store["rows"] = _rows_from_sheet(wb.active)
            finally:
                wb.close()
            store["mtime"] = mtime
        return [dict(r) for r in store["rows"]]


def _update_account(email: str, **changes):
    store = _accounts_store()
    with store["lock"]:
        rows = _load_rows()
        for r in rows:
            if r["email"] == email:
                r.update(changes)
                _save_rows(rows)
                return


def create_user(first_name: str, last_name: str, email: str, birth_date: date,
                password: str, gender: str, marital_status: str = "single",
                diabetes_type: str = "", country: str = "", dial_code: str = "", phone: str = ""):
    email = normalize_email(email)
    first_name, last_name = normalize_person_name(first_name), normalize_person_name(last_name)
    if not (valid_person_name(first_name) and valid_person_name(last_name)
            and gender in GENDER_OPTIONS and marital_status in MARITAL_STATUS_ORDER
            and diabetes_type in DIABETES_TYPE_KEYS and country.strip()):
        return False, "reg_fill_all"
    if len(email) > 254 or not EMAIL_REGEX.fullmatch(email):
        return False, "reg_email_invalid"
    if not isinstance(birth_date, date) or not date(1900, 1, 1) <= birth_date < date.today():
        return False, "reg_dob_invalid"
    if len(password) < MIN_PASSWORD_LEN or not password.strip() or len(password) > 128:
        return False, "reg_pw_short"
    try:
        phone = normalize_registration_phone(phone, dial_code)
    except ValueError:
        return False, "reg_phone_invalid"
    try:
        password_hash = hash_password(password)
        store = _accounts_store()
        with store["lock"]:
            rows = _load_rows()
            if any(r["email"] == email for r in rows):
                return False, "auth_email_taken"
            new_patient_id = generate_patient_id()
            rows.append({
                "id": max([r["id"] for r in rows] + [0]) + 1,
                "patient_id": new_patient_id,
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "email": email,
                "birth_date": birth_date.isoformat(),
                "gender": gender,
                "marital_status": marital_status,
                "diabetes_type": diabetes_type,
                "country": country,
                "dial_code": dial_code,
                "phone": phone,
                "password_hash": password_hash,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "last_login": "",
                "failed_attempts": 0,
                "locked_until": "",
                "must_change_password": 0,
            })
            _save_rows(rows)
        return True, None
    except Exception:
        return False, "auth_db_error"


def update_user_profile(email, marital_status, country, dial_code, phone, confirmed_type=None, profile_photo=None):
    """Persist allowed profile changes; type can only move from unknown to known."""
    if marital_status not in MARITAL_STATUS_ORDER or not country.strip():
        return None
    digits = phone.removeprefix("+")
    if not digits.isascii() or not digits.isdigit() or not 6 <= len(digits) <= 15:
        return None
    store = _accounts_store()
    with store["lock"]:
        rows = _load_rows()
        row = next((r for r in rows if r["email"] == normalize_email(email)), None)
        if row is None:
            return None
        current_type = row.get("diabetes_type") or "not_sure"
        if confirmed_type is not None:
            if current_type != "not_sure" or confirmed_type not in ("type1", "type2"):
                return None
            row["diabetes_type"] = confirmed_type
        row.update(marital_status=marital_status, country=country.strip(),
                   dial_code=dial_code, phone=phone)
        if profile_photo is not None:
            row["profile_photo"] = profile_photo
        _save_rows(rows)
        return dict(row)


def authenticate(email: str, password: str):
    # Serialize the read/modify/write sequence across Streamlit sessions.
    with _accounts_store()["lock"]:
        return _authenticate_locked(email, password)


def _authenticate_locked(email: str, password: str):
    email = normalize_email(email)
    now = datetime.now()

    row = next((r for r in _load_rows() if r["email"] == email), None)
    if row is None:
        return None, "invalid"

    if row["locked_until"]:
        try:
            if datetime.fromisoformat(row["locked_until"]) > now:
                return None, "locked"
        except ValueError:
            pass

    if verify_password(password, row["password_hash"]):
        _update_account(
            email, failed_attempts=0, locked_until="",
            last_login=now.isoformat(timespec="seconds"),
        )
        if not row.get("patient_id"):
            row["patient_id"] = generate_patient_id()
            _update_account(email, patient_id=row["patient_id"])
        log_action(row["id"], "login", f"email={email}")
        return {
            "id": row["id"],
            "patient_id": row.get("patient_id", ""),
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "email": row["email"],
            "birth_date": row["birth_date"],
            "gender": row.get("gender", "Male"),
            "marital_status": row.get("marital_status", "single"),
            "diabetes_type": row.get("diabetes_type", ""),
            "country": row.get("country", ""),
            "dial_code": row.get("dial_code", ""),
            "phone": row.get("phone", ""),
            "profile_photo": row.get("profile_photo", ""),
            "must_change_password": int(row.get("must_change_password", 0)),
        }, "ok"

    attempts = int(row["failed_attempts"] or 0) + 1
    locked_until, status = "", "invalid"
    if attempts >= MAX_FAILED_LOGINS:
        locked_until = (now + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds")
        attempts, status = 0, "locked"
    _update_account(email, failed_attempts=attempts, locked_until=locked_until)
    return None, status


# =============================================================================
# Audit Log + Password Reset
# =============================================================================

def log_action(account_id: int, action: str, details: str = ""):
    """Log a sensitive action to audit_log.xlsx."""
    try:
        new_row = pd.DataFrame([{
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
            "Account ID": account_id,
            "Action": action,
            "Details": details,
        }])

        if os.path.exists(AUDIT_LOG_FILE):
            existing = pd.read_excel(AUDIT_LOG_FILE, engine="openpyxl")
            combined = pd.concat([existing, new_row], ignore_index=True)
        else:
            combined = new_row

        combined.to_excel(AUDIT_LOG_FILE, index=False, engine="openpyxl")
    except Exception:
        pass


def reset_user_password(email: str) -> str:
    """Reset a user's password to a temporary one. Returns the temp password."""
    temp_password = secrets.token_urlsafe(12)
    password_hash = hash_password(temp_password)
    _update_account(
        email,
        password_hash=password_hash,
        must_change_password=1,
        failed_attempts=0,
        locked_until="",
    )
    log_action(0, "password_reset", f"target_email={email}")
    return temp_password


def render_accounts_admin():
    if st.session_state.get("admin_ok") is not True:
        st.error("Administrator sign-in required.")
        return
    rows = _load_rows()
    st.caption("Account directory only. Medical records require separate authorization. Credential recovery and full account backup access belong to an independent custodian.")
    if not rows:
        st.info("No accounts yet.")
        return
    query = st.text_input("Search patients", placeholder="Name, patient ID, email or country", key="admin_patient_search")
    table = pd.DataFrame([{"Patient ID":r.get("patient_id", ""), "Name":r.get("first_name", "")+" "+r.get("last_name", ""),
                           "Email":r.get("email", ""), "Country":r.get("country", ""),
                           "Created at":r.get("created_at", ""), "Last login":r.get("last_login", "")} for r in rows])
    filtered = admin_dashboard.search_frame(table, query)
    st.caption(f"{len(filtered)} of {len(table)} registered accounts")
    st.dataframe(filtered, use_container_width=True, hide_index=True)


# =============================================================================
# Responsive / modern UI
# =============================================================================

def inject_hover_css():
    if st.session_state.get("dark_mode", True):
        h_bg, h_border, h_text, h_glow = "rgba(56,189,248,.16)", "#38bdf8", "#bae6fd", "rgba(56,189,248,.30)"
    else:
        h_bg, h_border, h_text, h_glow = "rgba(14,165,233,.13)", "#0ea5e9", "#075985", "rgba(14,165,233,.30)"

    header = '[data-testid="stHorizontalBlock"]:has(.brand)'
    st.markdown(
        f"""
        <style>
        .stApp button[kind="secondary"],
        .stApp [data-testid="stBaseButton-secondary"],
        .stApp .stDownloadButton > button {{
            transition: background-color .15s ease, border-color .15s ease,
                        box-shadow .15s ease, color .15s ease, transform .15s ease;
        }}
        .stApp button[kind="secondary"]:hover,
        .stApp [data-testid="stBaseButton-secondary"]:hover,
        .stApp .stDownloadButton > button:hover,
        {header} .stButton > button:hover {{
            background: {h_bg} !important;
            border-color: {h_border} !important;
            box-shadow: 0 0 0 3px {h_glow}, 0 10px 24px rgba(14,165,233,.18) !important;
        }}
        .stApp button[kind="secondary"]:hover p,
        .stApp button[kind="secondary"]:hover span,
        .stApp [data-testid="stBaseButton-secondary"]:hover p,
        .stApp .stDownloadButton > button:hover p {{
            color: {h_text} !important;
            -webkit-text-fill-color: {h_text} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_css():
    is_dark = st.session_state.get("dark_mode", True)
    rtl = is_rtl()
    no_spacing = st.session_state.get("lang", "en") in SPACING_OFF_LANGS

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

    if rtl:
        rtl_css = """
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {
            direction: rtl;
            text-align: right;
        }
        .hero, .brand, .section-card, .result-card, .status-card, .notice,
        .section-title, .section-subtitle, .footer, .support-card {
            direction: rtl;
        }
        .hero, .section-card, .result-card, .status-card, .notice,
        .section-title, .section-subtitle, .support-card {
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
        rtl_css += f"""
        {HEADER} .brand-name,
        {HEADER} .brand-tagline {{
            direction: rtl;
            text-align: right !important;
        }}
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

        html, body, .stApp, [data-testid="stAppViewContainer"] {{
            max-width: 100% !important;
            overflow-x: hidden !important;
        }}

        header[data-testid="stHeader"] {{
            background: color-mix(in srgb, var(--page) 88%, transparent) !important;
            color: var(--text) !important;
        }}

        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {{
            color: var(--text) !important;
        }}

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

        {HEADER} > [data-testid="stColumn"]:nth-child(1) {{
            flex: 1 1 0 !important;
            width: auto !important;
            min-width: 0 !important;
        }}

        {HEADER} > [data-testid="stColumn"]:nth-child(2) {{
            flex: 0 0 172px !important;
            width: 172px !important;
            min-width: 172px !important;
            max-width: 172px !important;
        }}

        {HEADER} > [data-testid="stColumn"]:nth-child(3),
        {HEADER} > [data-testid="stColumn"]:nth-child(4) {{
            flex: 0 0 48px !important;
            width: 48px !important;
            min-width: 48px !important;
            max-width: 48px !important;
        }}

        {HEADER} [data-testid="stElementContainer"],
        {HEADER} [data-testid="stMarkdownContainer"] {{
            margin: 0 !important;
            padding: 0 !important;
        }}

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

        {HEADER} .stButton {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
        }}

        {HEADER} .stButton > button,
        {HEADER} .stButton > button > * {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
        }}

        {HEADER} .stButton > button p {{
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1 !important;
            text-align: center !important;
        }}

        {HEADER} > [data-testid="stColumn"]:nth-child(2) .stButton > button p {{
            transform: translateY(-1px);
        }}

        {HEADER} > [data-testid="stColumn"]:nth-child(3) .stButton > button p,
        {HEADER} > [data-testid="stColumn"]:nth-child(4) .stButton > button p {{
            font-size: 1.3rem !important;
        }}

        [data-testid="stForm"],
        .st-key-patient_card {{
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 22px !important;
            padding: 22px 20px !important;
            box-shadow: var(--shadow) !important;
        }}

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

        .support-card {{
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 18px;
            padding: 16px 18px;
            margin: 16px 0;
            box-shadow: var(--shadow);
        }}

        .support-title {{
            font-weight: 800;
            color: var(--text) !important;
            margin-bottom: 2px;
        }}

        .support-text {{
            color: var(--muted) !important;
            font-size: .86rem;
            line-height: 1.5;
            margin-bottom: 10px;
        }}

        .support-card a.support-link,
        .support-card a.support-link * {{
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            text-decoration: none !important;
        }}

        .support-card a.support-link {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 16px;
            border-radius: 14px;
            background: #16a34a;
            font-weight: 800;
        }}

        .support-card a.support-link:hover {{
            background: #15803d;
        }}

        .footer {{
            text-align:center;
            color:var(--muted) !important;
            font-size:.75rem;
            padding:24px 0 4px;
        }}

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

        .stApp input:-webkit-autofill,
        .stApp input:-webkit-autofill:hover,
        .stApp input:-webkit-autofill:focus {{
            -webkit-box-shadow: 0 0 0 1000px var(--input) inset !important;
            -webkit-text-fill-color: var(--input-text, var(--text)) !important;
            caret-color: var(--primary) !important;
        }}

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

        [data-testid="stMarkdownContainer"] hr {{
            margin: .5rem 0 !important;
            border: 0 !important;
            border-top: 1px solid var(--border) !important;
            opacity: 1 !important;
        }}

        [data-testid="stForm"] [data-testid="stVerticalBlock"],
        .st-key-patient_card {{
            gap: .85rem !important;
        }}

        .st-key-basic_age_locked [data-testid="stNumberInputStepDown"],
        .st-key-basic_age_locked [data-testid="stNumberInputStepUp"],
        .st-key-basic_age_locked button[aria-label*="Decrement"],
        .st-key-basic_age_locked button[aria-label*="Increment"],
        .st-key-basic_age_locked button[aria-label*="Reduce"],
        .st-key-basic_age_locked button[aria-label*="Increase"] {{
            display: none !important;
        }}

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

        [data-testid="stAlert"] {{
            background:var(--surface) !important;
            border:1px solid var(--border) !important;
            color:var(--text) !important;
        }}

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {{
            background:var(--surface) !important;
            color:var(--text) !important;
        }}

        [data-testid="stFileUploaderDropzone"] {{
            background:var(--surface) !important;
            border:1px dashed var(--border) !important;
            color:var(--text) !important;
        }}

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

            [data-testid="stForm"],
            .st-key-patient_card {{
                padding: 16px 12px !important;
                border-radius: 18px !important;
            }}
        }}

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
    try:
        loaded_model, columns, metadata = load_screening_artifacts(MODEL_PATH, COLUMNS_PATH)
        return loaded_model, None, columns, metadata
    except Exception as exc:
        st.error(str(exc))
        st.stop()


model, scaler, feature_columns, model_metadata = load_artifacts()

binary_columns = [c for c in feature_columns if c not in ("Age", "Gender")]


# =============================================================================
# Session state
# =============================================================================

if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False
if "page" not in st.session_state:
    st.session_state["page"] = "splash"
if "choosing_language" not in st.session_state:
    st.session_state["choosing_language"] = False
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
    patient = st.session_state.get("user") or {}
    if patient.get("email") and page_name not in ("admin", "auth", "login", "register"):
        log_action(patient.get("id", 0), "page_opened", "page="+page_name)
    st.session_state["page"] = page_name
    st.rerun()


def restart_app(new_lang: str, page: str = "splash"):
    keep_dark = st.session_state.get("dark_mode", True)

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state["lang"] = new_lang if new_lang in LANGUAGES else "en"
    st.session_state["dark_mode"] = keep_dark
    st.session_state["page"] = page
    st.session_state.pop("current_patient_id", None)
    st.session_state.pop("basic_gender", None)

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
        logo_html = "PP"

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

    time.sleep(5.2)
    go_to("language")


# =============================================================================
# Language gate
# =============================================================================

def render_language_gate():
    mode_label = {"en":"Switch appearance", "ar":"تبديل الوضع النهاري والليلي", "es":"Cambiar apariencia", "hi":"दिन और रात का मोड बदलें", "zh":"切换明暗模式", "fr":"Changer le thème", "de":"Darstellung wechseln", "tr":"Görünümü değiştir", "pt":"Alterar aparência", "ru":"Сменить тему"}.get(st.session_state.get("lang"), "Switch appearance")
    st.button(mode_label, key="gate_theme_toggle", icon=":material/light_mode:" if st.session_state.get("dark_mode",True) else ":material/dark_mode:", on_click=_toggle_theme)

    lang = st.session_state["lang"]
    current_name = LANGUAGES[lang]["native"]

    st.markdown(
        f"""
        <div class="hero">
            <div class="pill">{tr('current_language')}: {current_name}</div>
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
                f"{tr('continue')}",
                type="primary",
                use_container_width=True,
                key="gate_continue",
            ):
                go_to("auth")

        with col_change:
            if st.button(
                f"{tr('change_language')}",
                use_container_width=True,
                key="gate_change",
            ):
                st.session_state["choosing_language"] = True
                st.rerun()
    else:
        st.markdown(
            f"""
            <div class="section-card">
                <div class="section-title">{tr('select_language')}</div>
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
                    restart_app(code)

        if st.button(f"{tr('back')}", key="gate_back", use_container_width=True):
            st.session_state["choosing_language"] = False
            st.rerun()


# =============================================================================
# Header
# =============================================================================

def render_header():
    left, admin_col, theme_col = st.columns([6, 3, 1], vertical_alignment="center")

    with left:
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, "rb") as _logo_file:
                _logo_b64 = base64.b64encode(_logo_file.read()).decode()
            brand_icon_html = (
                f'<img src="data:image/png;base64,{_logo_b64}" '
                'style="width:100%;height:100%;object-fit:cover;border-radius:inherit;" />'
            )
        else:
            brand_icon_html = "PP"

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

    with admin_col:
        if st.session_state["page"] == "admin":
            if st.button(f"{tr('back')}", key="admin_back", use_container_width=True):
                go_to("auth")
        else:
            if st.button(f"{tr('logout')}", key="logout_btn", use_container_width=True):
                ux.confirm_action("Log out?", "End this patient session?", logout)

    with theme_col:
        is_dark = st.session_state.get("dark_mode", True)
        st.button(
            "",
            icon=":material/light_mode:" if is_dark else ":material/dark_mode:",
            key="theme_btn",
            help=tr("light") if is_dark else tr("dark"),
            use_container_width=True,
            on_click=_toggle_theme,
        )


# =============================================================================
# Sign-in / login / registration
# =============================================================================

def logout():
    patient = st.session_state.get("user") or {}
    if patient.get("email"):
        log_action(patient.get("id", 0), "logout", "patient_id="+str(patient.get("patient_id", "")))
    restart_app(st.session_state.get("lang", "en"), page="auth")


def render_support_card():
    st.markdown(
        f"""
        <div class="support-card">
            <div class="support-title">{tr('support_title')}</div>
            <div class="support-text">{tr('support_text')}</div>
            <a class="support-link" href="{SUPPORT_WHATSAPP_URL}" target="_blank" rel="noopener noreferrer">
                WhatsApp <span dir="ltr">{SUPPORT_WHATSAPP_NUMBER}</span>
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


_AUTH_UI_TEXT = {
    "en": {
        "welcome_title": "Welcome!",
        "welcome_back": "Welcome Back!",
        "welcome_back_sub": "Sign in to access your account",
        "welcome_new": "Join PerdiaPredict",
        "welcome_new_sub": "Create your account to start your early diabetes risk screening",
    },
    "ar": {
        "welcome_title": "أهلًا بك!",
        "welcome_back": "أهلًا بعودتك!",
        "welcome_back_sub": "سجّل الدخول للوصول إلى حسابك",
        "welcome_new": "انضم إلى PerdiaPredict",
        "welcome_new_sub": "أنشئ حسابك لتبدأ الفحص المبكر لخطر السكري",
    },
    "es": {
        "welcome_title": "¡Bienvenido!",
        "welcome_back": "¡Bienvenido de nuevo!",
        "welcome_back_sub": "Inicia sesión para acceder a tu cuenta",
        "welcome_new": "Únete a PerdiaPredict",
        "welcome_new_sub": "Crea tu cuenta para empezar tu evaluación temprana del riesgo de diabetes",
    },
}
for _code, _vals in _AUTH_UI_TEXT.items():
    EXTRA_TEXT.setdefault(_code, {}).update(_vals)

_MEAL_DL_TEXT = {
    "en": {"download_meal_plan": "Download the meal plan (Excel)"},
    "ar": {"download_meal_plan": "تنزيل جدول النظام الغذائي (Excel)"},
    "es": {"download_meal_plan": "Descargar el plan de comidas (Excel)"},
}
for _code, _vals in _MEAL_DL_TEXT.items():
    EXTRA_TEXT.setdefault(_code, {}).update(_vals)


@st.cache_data(show_spinner=False)
def _auth_logo_html() -> str:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as _f:
            _b64 = base64.b64encode(_f.read()).decode()
        return f'<img src="data:image/png;base64,{_b64}" alt="PerdiaPredict" />'
    return '<span class="auth-logo-fallback">PP</span>'


def inject_auth_css():
    is_dark = st.session_state.get("dark_mode", True)
    rtl = is_rtl()
    no_spacing = rtl or st.session_state.get("lang", "en") in SPACING_OFF_LANGS
    letter = "0" if no_spacing else "-.02em"

    if is_dark:
        h_bg, h_border, h_text, h_glow = "rgba(56,189,248,.16)", "#38bdf8", "#bae6fd", "rgba(56,189,248,.30)"
    else:
        h_bg, h_border, h_text, h_glow = "rgba(14,165,233,.13)", "#0ea5e9", "#075985", "rgba(14,165,233,.30)"

    form_side = "left" if rtl else "right"

    if is_dark:
        backdrop = """
            radial-gradient(900px 520px at 12% -8%, rgba(37,99,235,.38), transparent 60%),
            radial-gradient(800px 520px at 100% 105%, rgba(14,165,233,.28), transparent 60%),
            #060b18
        """
        card_shadow = "0 30px 80px rgba(0,0,0,.55), 0 0 0 1px rgba(148,163,184,.10)"
    else:
        backdrop = """
            radial-gradient(900px 520px at 12% -8%, rgba(37,99,235,.20), transparent 60%),
            radial-gradient(800px 520px at 100% 105%, rgba(14,165,233,.18), transparent 60%),
            #e9f1fb
        """
        card_shadow = "0 30px 70px rgba(30,64,175,.22), 0 0 0 1px rgba(148,163,184,.25)"

    art_svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 460 460'>"
        "<defs>"
        "<radialGradient id='g' cx='50%' cy='50%' r='50%'>"
        "<stop offset='0' stop-color='#38bdf8' stop-opacity='.55'/>"
        "<stop offset='.6' stop-color='#2563eb' stop-opacity='.22'/>"
        "<stop offset='1' stop-color='#2563eb' stop-opacity='0'/>"
        "</radialGradient>"
        "<linearGradient id='l' x1='0' x2='1' y1='0' y2='0'>"
        "<stop offset='0' stop-color='#7dd3fc' stop-opacity='0'/>"
        "<stop offset='.22' stop-color='#7dd3fc' stop-opacity='.9'/>"
        "<stop offset='.78' stop-color='#7dd3fc' stop-opacity='.9'/>"
        "<stop offset='1' stop-color='#7dd3fc' stop-opacity='0'/>"
        "</linearGradient>"
        "</defs>"
        "<circle cx='230' cy='230' r='228' fill='url(#g)'/>"
        "<circle cx='230' cy='230' r='172' fill='none' stroke='#fff' stroke-opacity='.14'/>"
        "<path d='M6 238 H70 l10 -16 l12 34 l14 -70 l12 52 l9 -14 H310 l9 14 l12 -52 l14 70 l12 -34 l10 16 H454' "
        "fill='none' stroke='url(#l)' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'/>"
        "<g fill='#fff' fill-opacity='.30'>"
        "<path transform='translate(74 116)' d='M0 -16 C9 -3 13 3 13 9 A13 13 0 0 1 -13 9 C-13 3 -9 -3 0 -16Z'/>"
        "<path transform='translate(392 104) scale(.8)' d='M0 -16 C9 -3 13 3 13 9 A13 13 0 0 1 -13 9 C-13 3 -9 -3 0 -16Z'/>"
        "<path transform='translate(380 356) scale(1.1)' d='M0 -16 C9 -3 13 3 13 9 A13 13 0 0 1 -13 9 C-13 3 -9 -3 0 -16Z'/>"
        "<path transform='translate(84 346) scale(.7)' d='M0 -16 C9 -3 13 3 13 9 A13 13 0 0 1 -13 9 C-13 3 -9 -3 0 -16Z'/>"
        "</g>"
        "<g stroke='#fff' stroke-opacity='.38' stroke-width='2' stroke-linecap='round'>"
        "<path d='M405 196h12M411 190v12'/>"
        "<path d='M40 190h10M45 185v10'/>"
        "<path d='M330 60h10M335 55v10'/>"
        "<path d='M120 410h10M125 405v10'/>"
        "</g>"
        "<g fill='#fff' fill-opacity='.26'>"
        "<circle cx='150' cy='70' r='2.5'/><circle cx='300' cy='400' r='2.5'/>"
        "<circle cx='430' cy='300' r='2'/><circle cx='30' cy='280' r='2'/>"
        "</g>"
        "</svg>"
    )
    orbit_svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 460 460'>"
        "<circle cx='230' cy='230' r='205' fill='none' stroke='#fff' stroke-opacity='.24' stroke-dasharray='3 9'/>"
        "<circle cx='435' cy='230' r='6' fill='#7dd3fc' fill-opacity='.95'/>"
        "<circle cx='127.5' cy='407.5' r='4' fill='#fff' fill-opacity='.7'/>"
        "<circle cx='127.5' cy='52.5' r='5' fill='#38bdf8' fill-opacity='.9'/>"
        "</svg>"
    )

    def _data_uri(mime, raw_bytes):
        return f"data:{mime};base64," + base64.b64encode(raw_bytes).decode()

    art_uri = _data_uri("image/svg+xml", art_svg.encode("utf-8"))
    orbit_uri = _data_uri("image/svg+xml", orbit_svg.encode("utf-8"))

    art_mask = ""
    for _fname, _mime in (
        ("auth_art.png", "image/png"),
        ("auth_art.webp", "image/webp"),
        ("auth_art.jpg", "image/jpeg"),
        ("auth_art.jpeg", "image/jpeg"),
        ("auth_art.svg", "image/svg+xml"),
    ):
        _found = None
        for _dir in (BASE_DIR, "."):
            _p = os.path.join(_dir, _fname)
            if os.path.exists(_p):
                _found = _p
                break
        if _found:
            try:
                with open(_found, "rb") as _f:
                    art_uri = _data_uri(_mime, _f.read())
                art_mask = (
                    "opacity:.55;"
                    "-webkit-mask-image:radial-gradient(circle, #000 50%, transparent 72%);"
                    "mask-image:radial-gradient(circle, #000 50%, transparent 72%);"
                )
                break
            except Exception:
                pass

    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {backdrop} !important;
        }}
        header[data-testid="stHeader"] {{
            background: transparent !important;
        }}
        .block-container {{
            max-width: 1000px !important;
            padding-top: 3.4rem !important;
        }}

        .st-key-auth_card {{
            border-radius: 28px;
            overflow: hidden;
            padding: 0 !important;
            border: 0 !important;
            box-shadow: {card_shadow};
            background:
                linear-gradient(var(--surface), var(--surface)) {form_side} top / 50% 100% no-repeat,
                linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px) 0 0 / 100% 38px repeat-y,
                linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px) 0 0 / 38px 100% repeat-x,
                radial-gradient(circle at 14% 8%, rgba(96,165,250,.45), transparent 42%),
                radial-gradient(circle at 46% 100%, rgba(14,165,233,.40), transparent 46%),
                linear-gradient(135deg, #020617 0%, #172554 55%, #075985 100%);
            animation: authRise .55s cubic-bezier(.2,.8,.2,1) both;
        }}
        @keyframes authRise {{
            from {{ opacity: 0; transform: translateY(14px); }}
            to   {{ opacity: 1; transform: none; }}
        }}
        @keyframes authOrbit {{
            to {{ transform: rotate(360deg); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .st-key-auth_card {{ animation: none; }}
            .auth-logo-circle::after {{ animation: none !important; }}
        }}

        [data-testid="stHorizontalBlock"]:has(.st-key-auth_left) {{
            gap: 0 !important;
        }}

        @media (min-width: 641px) {{
            [data-testid="stHorizontalBlock"]:has(.st-key-auth_left) {{
                flex-wrap: nowrap !important;
                align-items: stretch !important;
            }}
            [data-testid="stHorizontalBlock"]:has(.st-key-auth_left) > [data-testid="stColumn"] {{
                flex: 1 1 0 !important;
                width: 50% !important;
                min-width: 0 !important;
            }}
            .st-key-auth_right [data-testid="stHorizontalBlock"] {{
                flex-wrap: nowrap !important;
                gap: .8rem !important;
            }}
            .st-key-auth_right [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
                flex: 1 1 0 !important;
                min-width: 0 !important;
            }}
        }}

        .st-key-auth_left {{
            position: relative;
            min-height: 660px;
            padding: 56px 36px 0 !important;
            justify-content: flex-start;
            align-items: center;
            text-align: center;
        }}
        .st-key-auth_left [data-testid="stElementContainer"],
        .st-key-auth_left [data-testid="stMarkdown"],
        .st-key-auth_left [data-testid="stMarkdownContainer"],
        .auth-welcome {{
            position: static !important;
        }}
        .st-key-auth_left [data-testid="stMarkdownContainer"] {{
            width: 100%;
        }}
        .st-key-auth_left [data-testid="stMarkdownContainer"] p {{
            margin: 0 !important;
        }}
        .stApp .st-key-auth_left,
        .stApp .st-key-auth_left * {{
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }}
        .auth-welcome {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            width: 100%;
        }}
        .auth-pill {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            margin: 0 0 22px;
            border-radius: 999px;
            background: rgba(255,255,255,.10);
            border: 1px solid rgba(255,255,255,.22);
            backdrop-filter: blur(6px);
            font-size: .8rem;
            font-weight: 650;
            line-height: 1.2;
        }}
        .auth-welcome-title {{
            font-size: 2.35rem;
            font-weight: 800;
            line-height: 1.15;
            letter-spacing: {letter};
            text-align: center;
            margin: 0 0 14px;
        }}
        .auth-welcome-sub {{
            font-size: .97rem;
            line-height: 1.7;
            text-align: center;
            opacity: .9;
            max-width: 330px;
            margin: 0 auto;
        }}

        .auth-logo-circle {{
            position: absolute;
            top: calc(50% + 30px);
            left: 50%;
            transform: translate(-50%, -50%);
            isolation: isolate;
            width: 176px;
            height: 176px;
            flex: 0 0 176px;
            border-radius: 50%;
            overflow: visible;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #2563eb, #0ea5e9);
            border: 3px solid rgba(255,255,255,.45);
            box-shadow:
                0 0 0 12px rgba(255,255,255,.07),
                0 0 0 26px rgba(255,255,255,.04),
                0 0 60px rgba(56,189,248,.45),
                0 26px 60px rgba(2,6,23,.55);
        }}
        .auth-logo-circle::before,
        .auth-logo-circle::after {{
            content: "";
            position: absolute;
            inset: -112px;
            z-index: -1;
            pointer-events: none;
            background-position: center;
            background-repeat: no-repeat;
            background-size: contain;
        }}
        .auth-logo-circle::before {{
            background-image: url("{art_uri}");
            {art_mask}
        }}
        .auth-logo-circle::after {{
            background-image: url("{orbit_uri}");
            animation: authOrbit 90s linear infinite;
        }}
        .auth-logo-circle img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 50%;
        }}
        .auth-logo-fallback {{ font-size: 80px; }}

        .st-key-auth_right {{
            min-height: 660px;
            padding: 48px 46px 32px;
            justify-content: center;
            gap: 1rem !important;
        }}
        .st-key-auth_right [data-testid="stMarkdownContainer"] p {{
            margin: 0;
        }}
        .auth-form-title {{
            font-size: 1.7rem;
            font-weight: 800;
            letter-spacing: {letter};
            line-height: 1.25;
            margin: 0 0 20px;
            color: var(--text) !important;
            text-align: center;
        }}
        .auth-form-sub {{
            font-size: .92rem;
            line-height: 1.6;
            margin: 0 0 6px;
            color: var(--muted) !important;
            text-align: center;
        }}
        .auth-form-title:has(+ .auth-form-sub) {{
            margin-bottom: 6px;
        }}
        .auth-sep {{
            height: 1px;
            background: var(--border);
            margin: .4rem 0;
        }}

        .st-key-auth_right [data-testid="stForm"] {{
            border: 0 !important;
            padding: 0 !important;
            box-shadow: none !important;
            background: transparent !important;
        }}
        .st-key-auth_right [data-testid="stForm"] [data-testid="stVerticalBlock"] {{
            gap: .9rem !important;
        }}

        .stApp .st-key-auth_right div[data-baseweb="input"],
        .stApp .st-key-auth_right div[data-baseweb="select"],
        .stApp .st-key-auth_right [data-testid="stTextInputRootElement"] {{
            min-height: 50px;
            border-radius: 14px !important;
        }}
        .stApp .st-key-auth_right input {{
            font-size: .95rem !important;
            padding-top: 12px !important;
            padding-bottom: 12px !important;
        }}
        .stApp .st-key-auth_right div[data-baseweb="input"]:focus-within,
        .stApp .st-key-auth_right [data-testid="stTextInputRootElement"]:focus-within,
        .stApp .st-key-auth_right div[data-baseweb="select"]:focus-within {{
            border-color: #2563eb !important;
            box-shadow: 0 0 0 4px rgba(37,99,235,.20) !important;
        }}

        .stApp .st-key-auth_right button[kind="primary"],
        .stApp .st-key-auth_right [data-testid="stBaseButton-primary"],
        .stApp .st-key-auth_right [data-testid="stBaseButton-primaryFormSubmit"] {{
            min-height: 52px !important;
            border-radius: 14px !important;
            border: 0 !important;
            background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%) !important;
            box-shadow: 0 10px 26px rgba(37,99,235,.38) !important;
            transition: transform .15s ease, box-shadow .15s ease, filter .15s ease;
        }}
        .stApp .st-key-auth_right button[kind="primary"]:hover,
        .stApp .st-key-auth_right [data-testid="stBaseButton-primary"]:hover,
        .stApp .st-key-auth_right [data-testid="stBaseButton-primaryFormSubmit"]:hover {{
            transform: translateY(-1px);
            filter: brightness(1.06);
            box-shadow: 0 14px 32px rgba(37,99,235,.48) !important;
        }}
        .stApp .st-key-auth_right button[kind="primary"] p,
        .stApp .st-key-auth_right [data-testid="stBaseButton-primary"] p,
        .stApp .st-key-auth_right [data-testid="stBaseButton-primaryFormSubmit"] p {{
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-weight: 750 !important;
            text-decoration: none !important;
        }}

        .stApp .st-key-auth_right button[kind="secondary"],
        .stApp .st-key-auth_right [data-testid="stBaseButton-secondary"] {{
            min-height: 52px !important;
            border-radius: 14px !important;
            background: rgba(37,99,235,.07) !important;
            border: 1px solid rgba(96,165,250,.45) !important;
            box-shadow: none !important;
            transition: background .15s ease, border-color .15s ease, transform .15s ease;
        }}
        .stApp .st-key-auth_right button[kind="secondary"]:hover,
        .stApp .st-key-auth_right [data-testid="stBaseButton-secondary"]:hover {{
            background: {h_bg} !important;
            border-color: {h_border} !important;
            box-shadow: 0 0 0 3px {h_glow}, 0 10px 24px rgba(14,165,233,.18) !important;
            transform: translateY(-1px);
        }}
        .stApp .st-key-auth_right button[kind="secondary"]:hover p,
        .stApp .st-key-auth_right [data-testid="stBaseButton-secondary"]:hover p {{
            color: {h_text} !important;
            -webkit-text-fill-color: {h_text} !important;
        }}
        .stApp .st-key-auth_right button[kind="secondary"] p,
        .stApp .st-key-auth_right [data-testid="stBaseButton-secondary"] p {{
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            font-weight: 700 !important;
            text-decoration: none !important;
        }}

        .stApp .st-key-auth_right [class*="st-key-auth_link"] button,
        .stApp .st-key-auth_right [class*="st-key-auth_swap"] button,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button {{
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            transform: none !important;
            min-height: 38px !important;
            width: auto !important;
            padding: 0 12px !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_link"] button p,
        .stApp .st-key-auth_right [class*="st-key-auth_swap"] button p,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button p {{
            text-decoration: none !important;
            font-size: .9rem !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_link"] button p,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button p {{
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
            font-weight: 650 !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_swap"]:not([class*="admin"]) button p {{
            color: #60a5fa !important;
            -webkit-text-fill-color: #60a5fa !important;
            font-weight: 750 !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_link"] button:hover,
        .stApp .st-key-auth_right [class*="st-key-auth_swap"] button:hover,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button:hover {{
            background: {h_bg} !important;
            border-radius: 10px !important;
            box-shadow: 0 0 0 2px {h_glow} !important;
        }}
        .stApp .st-key-auth_right [class*="st-key-auth_link"] button:hover p,
        .stApp .st-key-auth_right [class*="st-key-auth_swap"] button:hover p,
        .stApp .st-key-auth_right [class*="st-key-auth_"][class*="admin"] button:hover p {{
            color: {h_text} !important;
            -webkit-text-fill-color: {h_text} !important;
        }}

        .st-key-auth_right > [class*="st-key-auth_link"],
        .st-key-auth_right > [class*="st-key-auth_"][class*="admin"] {{
            display: flex;
            justify-content: center;
        }}
        .st-key-auth_right > [class*="st-key-auth_"][class*="admin"] {{
            margin-top: .5rem;
        }}
        .st-key-auth_right [data-testid="stColumn"] [class*="st-key-auth_link"] {{
            display: flex; justify-content: flex-start;
        }}
        .st-key-auth_right [data-testid="stColumn"] [class*="st-key-auth_swap"] {{
            display: flex; justify-content: flex-end;
        }}

        .st-key-auth_right .support-card {{
            background: transparent !important;
            box-shadow: none !important;
            border: 0 !important;
            border-top: 1px solid var(--border) !important;
            border-radius: 0 !important;
            padding: 16px 0 4px !important;
            margin: 8px 0 0 !important;
            text-align: center !important;
        }}

        .stApp .st-key-reg_day div[data-baseweb="select"] input,
        .stApp .st-key-reg_month div[data-baseweb="select"] input,
        .stApp .st-key-reg_year div[data-baseweb="select"] input {{
            caret-color: #60a5fa !important;
            cursor: text !important;
        }}

        @media (max-width: 640px) {{
            .block-container {{ padding: 1.4rem .6rem 2rem !important; }}
            .st-key-auth_card {{ background: var(--surface) !important; border-radius: 22px; }}
            .st-key-auth_left {{
                min-height: 0;
                padding: 30px 18px 26px !important;
                justify-content: center;
                background:
                    radial-gradient(circle at 15% 0%, rgba(96,165,250,.42), transparent 45%),
                    linear-gradient(135deg, #020617 0%, #172554 56%, #075985 100%);
            }}
            .auth-pill {{ margin-bottom: 14px; }}
            .auth-welcome-title {{ font-size: 1.6rem; margin-bottom: 10px; }}
            .auth-logo-circle {{
                position: relative;
                top: auto;
                left: auto;
                transform: none;
                margin: 92px auto 70px;
                width: 110px;
                height: 110px;
                flex-basis: 110px;
                box-shadow: 0 0 0 8px rgba(255,255,255,.07), 0 18px 40px rgba(2,6,23,.5);
            }}
            .auth-logo-circle::before,
            .auth-logo-circle::after {{ inset: -70px; }}
            .st-key-auth_right {{ min-height: 0; padding: 26px 18px 22px; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def auth_card(title: str, subtitle: str, compact: bool = False):
    inject_auth_css()
    if compact:
        with st.container(key="registration_card"):
            with st.container(key="auth_right"):
                st.caption(subtitle)
                yield
        return
    with st.container(key="auth_card"):
        left, right = st.columns(2, gap="small")
        with left:
            with st.container(key="auth_left"):
                st.markdown(
                    f"""
                    <div class="auth-welcome">
                        <div class="auth-welcome-title">{title}</div>
                        <div class="auth-welcome-sub">{subtitle}</div>
                        <div class="auth-logo-circle">{_auth_logo_html()}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        with right:
            with st.container(key="auth_right"):
                yield


def _form_title(text: str):
    st.markdown(f'<div class="auth-form-title">{text}</div>', unsafe_allow_html=True)


def render_auth_page():
    st.session_state.pop("admin_ok", None)

    with auth_card(tr("welcome_title"), tr("auth_intro")):
        _form_title(tr("auth_title"))

        if st.button(f"{tr('auth_registered')}", type="primary",
                     use_container_width=True, key="auth_btn_login"):
            go_to("login")
        if st.button(f"{tr('auth_new')}", use_container_width=True, key="auth_btn_register"):
            go_to("register")
        st.markdown("---")
        if st.button("Doctor sign in", use_container_width=True, key="auth_doctor_login"):
            go_to("doctor_login")
        if st.button("Doctor registration", use_container_width=True, key="auth_doctor_register"):
            go_to("doctor_register")
        if st.button(f"{tr('admin')}", use_container_width=True, key="auth_btn_admin"):
            go_to("admin")
        if st.button(f"{tr('back')}", use_container_width=True, key="auth_link_back"):
            go_to("language")

        from app_policies import render as render_policy_links
        render_policy_links()


def render_login_page():
    with auth_card(tr("welcome_back"), tr("welcome_back_sub")):
        _form_title(tr("login_title"))

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                tr("auth_email"), key="login_email", max_chars=254,
                placeholder=tr("auth_email"), label_visibility="visible",
            )
            password = st.text_input(
                tr("auth_password"), type="password", key="login_pw", max_chars=128,
                placeholder=tr("auth_password"), label_visibility="visible",
            )
            submitted = st.form_submit_button(
                f"{tr('login_button')}", type="primary", use_container_width=True
            )

        if submitted:
            if not email.strip() or not password:
                st.error(tr("login_fill"))
            else:
                try:
                    user, status = authenticate(email, password)
                except Exception:
                    user, status = None, "error"
                if status == "ok":
                    st.session_state.pop("doctor_user", None)
                    st.session_state["user"] = user
                    go_to("main")
                elif status == "locked":
                    st.error(tr("login_locked"))
                elif status == "error":
                    st.error(tr("auth_db_error"))
                else:
                    st.error(tr("login_invalid"))

        if st.button(f"{tr('auth_new')}", key="auth_link_register"):
            go_to("register")

        render_support_card()

        if st.button(f"{tr('back')}", key="auth_link_back_login"):
            go_to("auth")


MONTH_NAMES = {
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
           "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
    "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
           "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
}


def month_label(month_number, lang: str = None) -> str:
    lang = lang or st.session_state.get("lang", "en")
    names = MONTH_NAMES.get(lang) or MONTH_NAMES["en"]
    return names[int(month_number) - 1]


def age_from_birth_date(value):
    try:
        born = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    today = date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return max(1, min(120, years))


def generate_patient_id() -> str:
    """Allocate the next YYMMDD sequence, including IDs already used in reports."""
    prefix = date.today().strftime("%y%m%d")
    used = {str(r.get("patient_id", "")).strip() for r in _load_rows()}
    if os.path.exists(SAVE_FILE_XLSX):
        # A read failure must stop creation instead of silently reusing an ID.
        existing = pd.read_excel(SAVE_FILE_XLSX, engine="openpyxl", dtype=str)
        if "Patient ID" in existing.columns:
            used.update(existing["Patient ID"].dropna().str.strip())
    sequences = []
    for value in used:
        value = re.sub(r"\.0$", "", value)
        if value.startswith(prefix) and value[len(prefix):].isdigit():
            sequences.append(int(value[len(prefix):]))
    return f"{prefix}{max(sequences, default=0) + 1:02d}"


def _build_birth_date(day, month, year):
    if day is None or month is None or year is None:
        return None
    try:
        born = date(int(year), int(month), int(day))
    except ValueError:
        return None
    return born if date(1900, 1, 1) <= born < date.today() else None


T.setdefault("en", {}).update({"reg_phone_invalid": "Enter a valid phone number matching the selected country."})
T.setdefault("ar", {}).update({"reg_phone_invalid": "أدخل رقم هاتف صحيحًا يطابق البلد المختار."})
T.setdefault("en", {}).update({"welcome_new":"Create your account", "welcome_new_sub":"Enter your details to start your screening.", "reg_title":"Patient registration", "reg_button":"Create account", "auth_registered":"Sign in", "auth_new":"Create account", "auth_confirm_password":"Confirm password", "reg_accept":"I have read and agree to the notice above.", "reg_warn_title":"Password and account access", "reg_warn_text":"Use a password of at least 8 characters and keep it safe. If you forget it, contact support to request a reset. This app provides educational screening and does not diagnose diabetes."})
T.setdefault("ar", {}).update({"welcome_new":"إنشاء حساب جديد", "welcome_new_sub":"أدخل بياناتك لبدء التقييم.", "reg_title":"تسجيل بيانات المريض", "reg_button":"إنشاء الحساب", "auth_registered":"تسجيل الدخول", "auth_new":"إنشاء حساب", "auth_confirm_password":"تأكيد كلمة المرور", "reg_accept":"قرأت التنبيه أعلاه وأوافق عليه.", "reg_warn_title":"كلمة المرور والوصول إلى الحساب", "reg_warn_text":"استخدم كلمة مرور من 8 أحرف على الأقل واحتفظ بها في مكان آمن. إذا نسيتها، تواصل مع الدعم لطلب إعادة تعيينها. التطبيق للتقييم التوعوي ولا يشخّص مرض السكري."})

def render_register_page():
    if st.session_state.pop("clear_registration_fields", False):
        for key in ("reg_first", "reg_last", "reg_email", "reg_gender", "reg_marital",
                    "reg_year", "reg_month", "reg_day", "reg_diabetes_type", "reg_country",
                    "reg_phone", "reg_pw", "reg_pw2", "reg_accept", "reg_hospital"):
            st.session_state.pop(key, None)
    with auth_card(tr("welcome_new"), tr("welcome_new_sub"), compact=True):
        _form_title(tr("reg_title"))

        st.markdown("""<style>
        .stApp .st-key-registration_card {max-width:760px;margin:0 auto;background:var(--surface);border:1px solid var(--border);border-radius:22px;overflow:hidden;}
        .stApp .st-key-registration_card .st-key-auth_right {min-height:0 !important;}
        .stApp .st-key-register_form {padding:0 !important;}
        .stApp .st-key-register_form [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"]:empty) {display:none;}
        .stApp .st-key-register_form [data-testid="stMarkdownContainer"] p {margin:0 !important;}
        .stApp .st-key-register_form div[data-baseweb="select"] {min-height:46px !important;}
        .stApp .st-key-register_form [data-testid="stCheckbox"] label {align-items:flex-start;}
        .stApp .st-key-register_form [data-testid="stCheckbox"] p {line-height:1.5 !important;}
        .stApp .st-key-registration_card .support-card {margin-top:0 !important;}
        .stApp .st-key-register_form .reg-section {text-align:start;}
        .stApp .st-key-register_form input {height:46px;box-sizing:border-box;}
        .stApp .st-key-register_form [data-testid="stVerticalBlock"] {gap:14px !important;}
        .stApp .st-key-register_form [data-testid="stHorizontalBlock"] {gap:16px !important;}
        .stApp .st-key-register_form [data-testid="stWidgetLabel"] {min-height:unset !important;margin:0 0 6px !important;}
        .stApp .st-key-register_form [data-testid="stWidgetLabel"] p {font-size:.9rem !important;line-height:1.4 !important;font-weight:600 !important;}
        .stApp .st-key-register_form div[data-baseweb="input"],
        .stApp .st-key-register_form [data-testid="stTextInputRootElement"],
        .stApp .st-key-register_form div[data-baseweb="select"] > div {min-height:46px !important;border-radius:12px !important;}
        .stApp .st-key-register_form input {font-size:.95rem !important;line-height:1.4 !important;padding:10px 12px !important;}
        .stApp .st-key-register_form button {min-height:46px !important;border-radius:12px !important;}
        .stApp .st-key-register_form .reg-section {display:flex;align-items:center;gap:10px;border-top:1px solid var(--border);padding-top:18px;margin:8px 0 0;}
        .stApp .st-key-register_form .reg-section-first {border:0;padding-top:2px;margin-top:0;}
        .stApp .st-key-register_form .reg-step {display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;flex:0 0 26px;border-radius:8px;background:rgba(59,130,246,.13);color:var(--text);font-size:.75rem;font-weight:700;}
        .stApp .st-key-register_form .reg-section-title {font-size:1rem;font-weight:700;line-height:1.4;color:var(--text);}
        .stApp .st-key-register_form .reg-field-title {font-size:.9rem;font-weight:600;margin:0;line-height:1.4;color:var(--text);}
        .stApp .st-key-register_form .notice {padding:14px 16px !important;margin:4px 0 0 !important;border-radius:12px !important;line-height:1.6 !important;font-size:.85rem !important;}
        .stApp .st-key-auth_right:has(.st-key-register_form) {gap:14px !important;padding:32px !important;justify-content:flex-start !important;}
        .stApp .st-key-auth_right:has(.st-key-register_form) .auth-form-title {font-size:1.5rem;margin-bottom:0 !important;line-height:1.3;}
        @media(max-width:640px) {
          .stApp .st-key-auth_right:has(.st-key-register_form) {padding:22px 16px !important;}
          .stApp .st-key-register_form [data-testid="stHorizontalBlock"] {gap:12px !important;}
          .stApp .st-key-register_form .reg-section {padding-top:16px;}
        }
        </style>""", unsafe_allow_html=True)
        def registration_section(number, key):
            first_class = " reg-section-first" if number == 1 else ""
            st.markdown(f'<div class="reg-section{first_class}"><span class="reg-step">{number:02}</span><span class="reg-section-title">{html_escape(edit_text(key))}</span></div>', unsafe_allow_html=True)
        this_year = date.today().year
        with st.container(key="register_form"):
            st.caption(edit_text("required"))
            is_ar = st.session_state.get("lang") == "ar"
            registration_section(1, "personal")
            c1, c2 = st.columns(2)
            with c1:
                first_name = st.text_input(f"{tr('first_name')} *", key="reg_first", max_chars=60)
            with c2:
                last_name = st.text_input(f"{tr('last_name')} *", key="reg_last", max_chars=60)

            email = st.text_input(f"{tr('auth_email')} *", key="reg_email", max_chars=254, placeholder="name@example.com")

            gender_col, marital_col = st.columns(2)
            with gender_col:
                gender_reg = st.selectbox(
                    f"{tr('gender')} *",
                    GENDER_OPTIONS, index=None, placeholder=tr("gender"),
                    format_func=gender_label,
                    key="reg_gender",
                )
            with marital_col:
                marital_status_reg = st.selectbox(
                    f"{tr('marital_status')} *",
                    MARITAL_STATUS_ORDER, index=None, placeholder=tr("marital_status"),
                    format_func=lambda k: marital_status_label(k, gender_reg or "Male"),
                    key="reg_marital",
                )
            st.markdown(
                f'<div class="reg-field-title">{tr("dob")} *</div>',
                unsafe_allow_html=True,
            )
            d1, d2, d3 = st.columns(3)
            with d3:
                year = st.selectbox(
                    tr("dob_year"), list(range(this_year, 1899, -1)), index=None,
                    placeholder=tr("dob_year"), key="reg_year",
                )
            with d2:
                month = st.selectbox(
                    tr("dob_month"), list(range(1, 13)), index=None, format_func=month_label,
                    placeholder=tr("dob_month"), key="reg_month",
                )
            max_day = calendar.monthrange(year or 2000, month or 1)[1]
            if st.session_state.get("reg_day") is not None and st.session_state["reg_day"] > max_day:
                st.session_state["reg_day"] = None
            with d1:
                day = st.selectbox(
                    tr("dob_day"), list(range(1, max_day + 1)), index=None,
                    placeholder=tr("dob_day"), key="reg_day",
                )

            registration_section(2, "health")
            diabetes_type_reg = st.selectbox(
                ("Doctor-confirmed diabetes type *" if st.session_state["lang"] != "ar" else "نوع السكري المؤكّد من الطبيب *"), DIABETES_TYPE_KEYS,
                format_func=diabetes_type_label, index=None,
                placeholder="Select an option" if not is_ar else "اختر الخيار المناسب",
                key="reg_diabetes_type",
            )

            registration_section(3, "contact")
            country_choice = st.selectbox(
                f"{registration_text(0)} *", COUNTRY_DIAL_CODES,
                index=COUNTRY_DIAL_CODES.index(("🇺🇬", "Uganda", "+256")),
                format_func=lambda item: f"{item[0]} {item[1]}",
                key="reg_country",
            )
            hospital_reg = st.text_input(
                "Hospital / clinic (enter Not assigned if none)", value="Not assigned",
                key="reg_hospital", max_chars=180)
            dial_choice = country_choice
            phone_reg = st.text_input(
                f"{registration_text(2)} ({dial_choice[2]}) *", key="reg_phone", max_chars=24,
                placeholder="771234567",
                help="Enter your local number. The country code is added automatically." if st.session_state["lang"] != "ar" else "أدخل الرقم المحلي. يُضاف مفتاح البلد تلقائيًا.",
            )

            registration_section(4, "security")
            password = st.text_input(
                f"{tr('auth_password')} *", type="password", key="reg_pw", max_chars=128,
                help="Use at least 8 characters." if st.session_state["lang"] != "ar" else "استخدم 8 أحرف على الأقل."
            )
            password2 = st.text_input(
                f"{tr('auth_confirm_password')} *", type="password", key="reg_pw2", max_chars=128
            )

            st.markdown(
                f"""
                <div class="notice">
                    <strong>{tr('reg_warn_title')}</strong><br>
                    {tr('reg_warn_text')}
                </div>
                """,
                unsafe_allow_html=True,
            )
            accepted = st.checkbox(tr("reg_accept"), key="reg_accept")

            submitted = st.button(
                f"{tr('reg_button')}", type="primary", use_container_width=True
            )

        if submitted:
            clean_first = normalize_person_name(first_name)
            clean_last = normalize_person_name(last_name)
            clean_email = normalize_email(email)
            birth = _build_birth_date(day, month, year)
            dob_chosen = day is not None and month is not None and year is not None
            clean_country = country_choice[1]
            errors = []
            full_phone = ""
            if not (clean_first and clean_last and clean_email and dob_chosen
                    and password and password2 and gender_reg and marital_status_reg
                    and clean_country and phone_reg.strip() and diabetes_type_reg):
                errors.append(tr("reg_fill_all"))
            for value, label in ((clean_first, tr("first_name")), (clean_last, tr("last_name"))):
                if value and not valid_person_name(value):
                    errors.append(f"{label}: " + ("Enter a name using letters, spaces, apostrophes or hyphens."
                                                if not is_ar else "أدخل اسمًا صحيحًا باستخدام الحروف."))
            if phone_reg.strip():
                try:
                    full_phone = normalize_registration_phone(phone_reg, dial_choice[2])
                except ValueError:
                    errors.append(registration_text(3))
            if clean_email and not EMAIL_REGEX.match(clean_email):
                errors.append(tr("reg_email_invalid"))
            if dob_chosen and birth is None:
                errors.append(tr("reg_dob_invalid"))
            if password and (len(password) < MIN_PASSWORD_LEN or not password.strip()):
                errors.append(tr("reg_pw_short"))
            if password and password2 and password != password2:
                errors.append(tr("reg_pw_mismatch"))
            if not accepted:
                errors.append(tr("reg_accept_required"))

            if errors:
                for message in errors:
                    st.error(message)
            else:
                ok, error_key = create_user(
                    clean_first, clean_last, clean_email, birth, password,
                    gender_reg, marital_status_reg, diabetes_type_reg,
                    clean_country, dial_choice[2], full_phone
                )
                if ok:
                    try:
                        user, status = authenticate(clean_email, password)
                    except Exception:
                        user, status = None, "error"
                    if user is not None and status == "ok":
                        try:
                            care.save_patient_location(user, clean_country, hospital_reg.strip() or "Not assigned")
                        except Exception:
                            st.warning("You can complete your hospital details on My doctor and care team.")
                        st.session_state.pop("doctor_user", None)
                        st.session_state["user"] = user
                        st.session_state["clear_registration_fields"] = True
                        go_to("main")
                    else:
                        st.success("Account created. Please sign in."
                                   if not is_ar else "تم إنشاء الحساب. يرجى تسجيل الدخول.")
                        st.session_state["clear_registration_fields"] = True
                else:
                    st.error(tr(error_key))

        if st.button(f"{tr('auth_registered')}", key="auth_link_login"):
            go_to("login")

        render_support_card()

        if st.button(f"{tr('back')}", key="auth_link_back_register"):
            go_to("auth")


def _admin_password_ok(candidate: str) -> bool:
    return bool(ADMIN_PASSWORD and candidate) and hmac.compare_digest(candidate.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))


def render_admin_page():
    if not ADMIN_PASSWORD:
        st.warning("Configure ADMIN_PASSWORD in .streamlit/secrets.toml before using the admin panel."
                   if st.session_state.get("lang") != "ar" else
                   "اضبط ADMIN_PASSWORD في ملف .streamlit/secrets.toml قبل استخدام لوحة الإدارة.")
        if st.button(tr("back"), key="admin_config_back"):
            go_to("auth")
        return
    if not st.session_state.get("admin_ok"):
        with auth_card(tr("admin_title"), tr("admin_help")):
            _form_title(tr("admin_title"))

            with st.form("admin_form", clear_on_submit=False):
                admin_pw = st.text_input(
                    tr("password"), type="password", key="admin_pw",
                    placeholder=tr("password"), label_visibility="collapsed",
                )
                unlock = st.form_submit_button(
                    f"{tr('login_button')}", type="primary", use_container_width=True
                )

            if unlock:
                if _admin_password_ok(admin_pw):
                    st.session_state["admin_ok"] = True
                    st.rerun()
                else:
                    st.error(tr("incorrect"))
        return

    if st.session_state.get("_admin_next_section"):
        st.session_state["admin_section"] = st.session_state.pop("_admin_next_section")
    admin_dashboard.render(globals())


# =============================================================================
# Prediction
# =============================================================================

def _model_probability(raw_input: dict) -> float:
    return predict_screening(model, feature_columns, model_metadata, raw_input)[1]


def predict_new_patient(raw_input: dict):
    return predict_screening(model, feature_columns, model_metadata, raw_input)


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
    extra_yes = [tr(key, lang) for key in REPORT_EXTRA_KEYS if extra_values.get(key) == "Yes"]
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


def build_report(lang, timestamp, first, last, phone, address, type_key,
                 age, gender, result, probability, symptom_values, extra_values,
                 gender_values=None, freq_key=None, marital_status_key=None,
                 birth_sex=None, glucose=None, patient_id="", patient_notes="", hospital="") -> dict:
    """Build the report dictionary in the requested language."""
    gender_values = gender_values or {}
    any_extra = any(v == "Yes" for v in extra_values.values()) or any(
        v == "Yes" for v in gender_values.values()
    )
    gender_yes = [tr(k, lang) for k, v in gender_values.items() if v == "Yes"]

    gender_text = gender_label(gender, lang)

    return {
        "Language": lang,
        "Patient ID": patient_id,
        "Timestamp": timestamp,
        "First name": first,
        "Last name": last,
        "Phone": phone,
        "Country": address,
        "Hospital": hospital or "Not assigned",
        "Reported diabetes type": tr(type_key, lang),
        "Age": age,
        "Gender": gender_text,
        "Marital status": (
            marital_status_label(marital_status_key, birth_sex or gender, lang)
            if marital_status_key else ""
        ),
        "Result": tr("positive_high" if result == 1 else "negative_low", lang),
        "Probability": f"{probability * 100:.1f}%",
        "Model version": model_metadata["model_version"],
        "Probability method": model_metadata["selected_model"] + " / tested pipeline predict_proba",
        "Decision threshold": str(model_metadata["threshold"]),
        "Clinical interpretation": "Educational screening estimate; not a diagnosis or an externally validated individual risk.",
        "Notable extra symptoms": tr("yes" if any_extra else "no", lang),
        "Urination frequency": tr(freq_key, lang) if freq_key else "",
        "Glucose level": f"{glucose[0]:g} {glucose[1]}" if glucose else "",
        "Gender-specific symptoms": ", ".join(gender_yes),
        "Type-specific answers": "; ".join(
            f"{tr(key, lang)}: {tr(value.lower(), lang)}"
            for key, value in extra_values.items() if key in TYPE_QUESTION_TEXT["en"]
        ),
        "Patient notes": str(patient_notes or "").strip(),
        "Symptom narrative": build_symptom_narrative(
            symptom_values, extra_values, lang, gender_values=gender_values, freq_key=freq_key
        ),
    }


# =============================================================================
# Health guide
# =============================================================================

def _meal_plan_excel(df: pd.DataFrame, rtl: bool = False) -> bytes:
    import io
    from openpyxl.styles import Alignment, Font, PatternFill

    sheet = re.sub(r"[\\/*?:\[\]]", " ", str(tr("meal_plan"))).strip()[:31] or "Meal plan"
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet)
        ws = writer.sheets[sheet]
        if rtl:
            ws.sheet_view.rightToLeft = True

        head_fill = PatternFill("solid", fgColor="2563EB")
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = head_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 24

        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(
                    vertical="top", wrap_text=True, horizontal="right" if rtl else "left"
                )
            row[0].font = Font(bold=True)

        ws.column_dimensions["A"].width = 12
        for letter in "BCDE":
            ws.column_dimensions[letter].width = 38
    return buffer.getvalue()


def render_meal_plan(veg: bool = False):
    st.markdown(f'<div class="section-title">{tr("meal_plan")}</div>', unsafe_allow_html=True)

    df = pd.DataFrame(
        tr("meal_plan_rows_veg" if veg else "meal_plan_rows"),
        columns=[tr("meal_plan"), tr("breakfast"), tr("lunch"), tr("dinner"), tr("drinks")],
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.download_button(
        tr("download_meal_plan"),
        data=_meal_plan_excel(df, is_rtl()),
        file_name="Weekly_Meal_Plan_" + ("veg" if veg else "nonveg") + ".xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="meal_plan_download",
        use_container_width=True,
    )


def _bullets(key: str) -> str:
    return "\n".join(f"- {item}" for item in tr(key))


def render_offline_health_guide():
    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">{tr('health_guide')}</div>
            <div class="section-subtitle">{tr('offline')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    diet_choice = st.radio(
        tr("diet_preference"),
        ["nonveg", "veg"],
        format_func=lambda k: tr("diet_veg" if k == "veg" else "diet_nonveg"),
        horizontal=True,
        key="diet_pref",
    )
    veg = diet_choice == "veg"

    with st.expander(f"{tr('plate')}", expanded=True):
        st.markdown(_bullets("plate_items"))

    with st.expander(f"{tr('foods')}"):
        st.markdown(_bullets("foods_items_veg" if veg else "foods_items"))

    with st.expander(f"⚠️ {tr('limit')}"):
        st.markdown(_bullets("limit_items"))

    with st.expander(f"{tr('habits')}"):
        st.markdown(_bullets("habits_items"))

    with st.expander(f"{tr('meal_plan')}"):
        render_meal_plan(veg)


# =============================================================================
# PDF
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
def _report_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    if "ReportRegular" in pdfmetrics.getRegisteredFontNames():
        return "ReportRegular"
    paths = [
        (os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans.ttf"), os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans-Bold.ttf")),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        (os.path.join("fonts", "NotoSans-Regular.ttf"), os.path.join("fonts", "NotoSans-Bold.ttf")),
        (os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "arial.ttf"),
         os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "arialbd.ttf")),
    ]
    for regular, bold in paths:
        if os.path.isfile(regular) and os.path.isfile(bold):
            pdfmetrics.registerFont(TTFont("ReportRegular", regular))
            pdfmetrics.registerFont(TTFont("ReportBold", bold))
            addMapping("ReportRegular", 1, 0, "ReportBold")
            return "ReportRegular"
    # English reports can still be generated without external font downloads.
    return "Helvetica"


def _report_paragraph(value, style):
    from reportlab.platypus import Paragraph
    value = str(value or "Not recorded")
    value = "".join(c for c in value if c in "\n\t" or ord(c) >= 32)
    if re.search(r"[\u0600-\u06ff]", value):
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            value = "\n".join(get_display(arabic_reshaper.reshape(line)) for line in value.split("\n"))
        except ImportError as exc:
            raise RuntimeError("Arabic PDF text requires arabic-reshaper and python-bidi.") from exc
    if style.fontName == "Helvetica" and any(ord(c) > 255 for c in value):
        raise RuntimeError("Install a Unicode font in fonts/ to include all patient text.")
    from report_locale import unicode_markup
    if re.search(r"[\u0900-\u097f]",value):
        from copy import copy
        style=copy(style)
        style.shaping=True
    if re.search(r"[\u0600-\u06ff\ufb50-\ufeff]", value):
        from copy import copy
        style=copy(style)
        style.alignment=2
    return Paragraph(unicode_markup(value, style.fontName), style)


def _medical_report_story(report, answers=None):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Table, TableStyle, Spacer, KeepTogether
    from report_locale import report_language, text
    lang=report_language(report,st.session_state.get("lang","en"))
    font = _report_font()
    body = ParagraphStyle("ReportBody", fontName=font, fontSize=9, leading=13, spaceAfter=4,
                          textColor=colors.HexColor("#243449"), alignment=2 if lang=="ar" else 0, splitLongWords=True)
    label = ParagraphStyle("ReportLabel", parent=body, fontSize=8, leading=11, textColor=colors.HexColor("#64748b"))
    heading = ParagraphStyle("ReportHeading", parent=body, fontSize=11, leading=16,
                             textColor=colors.HexColor("#127382"), spaceBefore=8, spaceAfter=4, keepWithNext=True)
    story=[]
    def para(value, style=body, translate=True): return _report_paragraph(text(value,lang) if translate else value, style)
    def framed_content(content):
        if not isinstance(content,Table):
            framed=Table([[content]],colWidths=[510],splitInRow=1)
            framed.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,colors.HexColor("#dbe4eb")),("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#f5f8fc")),("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            content=framed
        return content
    def section(title, content):
        story.extend([para(title, heading), framed_content(content)])
    def table(rows, widths):
        if lang=="ar":
            rows=[list(reversed(row)) for row in rows]
            widths=list(reversed(widths))
        obj=Table(rows, colWidths=widths, hAlign="RIGHT" if lang=="ar" else "LEFT")
        obj.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                ("BOX",(0,0),(-1,-1),.5,colors.HexColor("#dbe4eb")),
                                ("LINEBELOW",(0,0),(-1,-1),.3,colors.HexColor("#dbe4eb")),
                                ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,colors.HexColor("#f5f8fc")]),
                                ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
                                ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        return obj
    name=" ".join(str(report.get(k) or "") for k in ("First name","Last name"))
    info=[[("Patient ID",report.get("Patient ID")),("Patient name",name)],
          [("Age / Gender",f"{report.get('Age','')} / {report.get('Gender','')}"),("Marital status",report.get("Marital status"))],
          [("Phone",report.get("Phone")),("Country",report.get("Country"))],
          [("Assessment date",report.get("Timestamp")),("Recorded diabetes type",report.get("Reported diabetes type"))]]
    info.append([("Hospital / clinic",report.get("Hospital") or "Not assigned"), ("Care information", "Patient-reported location")])
    section("PATIENT INFORMATION",table([[[para(k,label),para(v)] for k,v in row] for row in info],[255,255]))
    score=history_score({"report":report})
    threshold=float(report.get("Decision threshold") or .5)*100
    accent="#b42318" if score is not None and score>=threshold else "#12735a"
    score_style=ParagraphStyle("Score",parent=body,fontSize=22,leading=28,textColor=colors.HexColor(accent))
    result=table([[[para("SCREENING RESULT",label),para(report.get("Result"))],
                   [para("ESTIMATED RISK",label),para(report.get("Probability"),score_style)]]],[255,255])
    result.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#f1f7f7"))]))
    section("RISK ASSESSMENT",result)
    story.append(para("Educational screening estimate. This result is not a medical diagnosis.",label))
    if report.get("Glucose level"): story.append(para(str(text("Glucose reading",lang))+": "+str(report["Glucose level"])))
    section("REPORTED SYMPTOMS",para(report.get("Symptom narrative") or text("Not recorded",lang),translate=False))
    if report.get("Type-specific answers"): story.append(para(report["Type-specific answers"]))
    import textwrap
    notes=str(report.get("Patient notes") or "No additional notes provided.")
    note_chunks=[]
    for line in notes.splitlines():
        note_chunks.extend(textwrap.wrap(line,width=550,replace_whitespace=False,drop_whitespace=False) or [" "])
    section("PATIENT NOTES / ADDITIONAL SYMPTOMS",para(note_chunks[0],translate=not bool(report.get("Patient notes"))))
    story.extend(framed_content(para(chunk,translate=False)) for chunk in note_chunks[1:])
    if answers:
        rows=[[para("Question",label),para("Answer",label)]]
        rows += [[para(k),para(v)] for k,v in answers.items()]
        detail=table(rows,[410,100]);detail.repeatRows=1
        story.append(para("SCREENING ANSWERS",heading));story.append(detail)
    section("RECOMMENDATION",para(tr("high_recommendation" if score is not None and score>=threshold else "low_recommendation",lang)))
    story.append(Spacer(1,8))
    story.append(para(str(text("Model version",lang))+": "+str(report.get("Model version") or "Not recorded"),label))
    story.append(para("Patient notes and additional questions are included for reference and do not change the model score.",label))
    return story


def _build_medical_pdf(reports):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, PageBreak, Flowable
    from report_locale import report_language
    class LanguageMarker(Flowable):
        width=0
        height=0
        def __init__(self,lang):
            super().__init__()
            self.lang=lang
        def draw(self): self.canv._medical_language=self.lang
    class MedicalDocument(SimpleDocTemplate):
        def handle_pageEnd(self):
            frame(self.canv,self)
            super().handle_pageEnd()
    buffer=BytesIO()
    doc=MedicalDocument(buffer,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=94,bottomMargin=60,
                          title="PerdiaPredict - Patient Screening Report",author="PerdiaPredict")
    def frame(canvas, document):
        canvas.saveState()
        from report_branding import draw_report_header
        draw_report_header(canvas,A4[0],A4[1],"PATIENT SCREENING REPORT | CONFIDENTIAL",getattr(canvas,"_medical_language","en"),_report_paragraph)
        canvas.setLineWidth(.5)
        canvas.setStrokeColor(colors.HexColor("#dbe4eb"));canvas.line(42,43,A4[0]-42,43)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.setFont("Helvetica",8)
        from report_locale import text
        footer_style=__import__('reportlab.lib.styles',fromlist=['ParagraphStyle']).ParagraphStyle("Footer",fontName=_report_font(),fontSize=7,leading=9,textColor=colors.HexColor("#64748b"))
        footer=_report_paragraph(text("Educational screening. This report is not a medical diagnosis.",getattr(canvas,"_medical_language","en")),footer_style)
        footer.wrap(A4[0]-150,20);footer.drawOn(canvas,42,26)
        canvas.drawRightString(A4[0]-42,29,f"Page {document.page}")
        canvas.restoreState()
    story=[]
    for index,(report,answers) in enumerate(reports):
        if index: story.append(PageBreak())
        story.append(LanguageMarker(report_language(report,st.session_state.get("lang","en"))))
        story.extend(_medical_report_story(report,answers))
    if not story: raise ValueError("No completed assessments to export.")
    doc.build(story)
    data=buffer.getvalue()
    if not data.startswith(b"%PDF-"): raise ValueError("Invalid PDF output")
    return data


def generate_pdf_report(report_data, lang="en", is_high=False, symptoms=None, answers=None):
    return _build_medical_pdf([(report_data,answers)])


def generate_patient_history_pdf(user, records):
    return _build_medical_pdf([(r["report"],r.get("answers")) for r in records])


def cached_report_pdf(report, answers=None):
    owner=normalize_email((st.session_state.get("user") or {}).get("email", ""))
    signature=hashlib.sha256(json.dumps([owner,st.session_state.get("lang","en"),report,answers],sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
    cache=st.session_state.setdefault("medical_pdf_cache",{})
    if signature not in cache:
        data=generate_pdf_report(report,answers=answers)
        if len(cache)>=24: cache.clear()
        cache[signature]=data
    return cache[signature]


def render_medical_report(report, answers=None):
    from report_branding import logo_html
    from report_locale import report_language, text, localize_html
    lang=report_language(report,st.session_state.get("lang","en"))
    report_direction="rtl" if lang=="ar" else "ltr"
    def field(label,value):
        return f'<div class="medical-field"><span>{html_escape(str(text(label,lang)))}</span><strong>{html_escape(str(value or text("Not recorded",lang)))}</strong></div>'
    st.markdown("""<style>
      .medical-report{padding:24px;border:1px solid var(--border);border-radius:18px;background:var(--surface);margin:16px 0;}
      .medical-report h2{color:#ffffff;margin:0;padding:20px 24px 4px;background:#0f233f;border-radius:14px 14px 0 0}.medical-report h2+p{margin-top:0;padding:0 24px 18px;background:#0f233f;color:#cbd5e1;border-bottom:3px solid #38d5d0;border-radius:0 0 14px 14px}.medical-report h3{font-size:1rem;margin:20px 0 10px;color:var(--text)}
      .medical-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.medical-field span{display:block;font-size:.8rem;color:var(--muted)}
      .medical-field strong{display:block;color:var(--text);overflow-wrap:anywhere}.medical-report p{white-space:pre-wrap;overflow-wrap:anywhere;color:var(--text)}
      .medical-result{padding:22px;background:linear-gradient(120deg,#0891b218,#6366f110);border:1px solid #0891b244;border-radius:16px;font-size:1.5rem;font-weight:700;color:var(--text)}
      @media(max-width:640px){.medical-grid{grid-template-columns:1fr}.medical-report{padding:18px}}
    </style>""",unsafe_allow_html=True)
    name=" ".join(str(report.get(k) or "") for k in ("First name","Last name"))
    fields=[("Patient ID",report.get("Patient ID")),("Patient name",name),("Assessment date",report.get("Timestamp")),
            ("Age / Gender",f"{report.get('Age','')} / {report.get('Gender','')}"),("Phone",report.get("Phone")),
            ("Country",report.get("Country")),("Hospital / clinic",report.get("Hospital") or "Not assigned"),("Marital status",report.get("Marital status")),("Recorded diabetes type",report.get("Reported diabetes type"))]
    st.markdown(localize_html(f'<div class="medical-report" dir="{report_direction}" lang="{lang}"><h2>{logo_html()}PerdiaPredict</h2><p>PATIENT SCREENING REPORT</p><h3>PATIENT INFORMATION</h3><div class="medical-grid">'+
                "".join(field(k,v) for k,v in fields)+
                f'</div><h3>RISK ASSESSMENT</h3><div class="medical-result">{html_escape(str(report.get("Result","")))} · {html_escape(str(report.get("Probability","")))}</div>'+
                f'<p>{html_escape(str(text("Glucose reading",lang)))}: {html_escape(str(report.get("Glucose level") or "Not recorded"))}</p><h3>REPORTED SYMPTOMS</h3><p>{html_escape(str(report.get("Symptom narrative") or "Not recorded"))}</p>'+
                f'<p>{html_escape(str(report.get("Type-specific answers") or ""))}</p><h3>PATIENT NOTES / ADDITIONAL SYMPTOMS</h3><p>{html_escape(str(report.get("Patient notes") or "No additional notes provided."))}</p>'+
                f'<h3>RECOMMENDATION</h3><p>{html_escape(str(tr("high_recommendation" if (history_score({"report":report}) or 0)>=float(report.get("Decision threshold") or .5)*100 else "low_recommendation",lang)))}</p><p>{html_escape(str(text("Model version",lang)))}: {html_escape(str(report.get("Model version") or "Not recorded"))}</p><p>Educational screening. This report is not a medical diagnosis.</p></div>',lang),unsafe_allow_html=True)
    if answers:
        with st.expander(history_text("Screening answers","إجابات الفحص")):
            for question,answer in answers.items(): st.write(f"{question}: {answer}")


# =============================================================================
# Storage
# =============================================================================

def save_report_to_excel(report: dict):
    new_row = pd.DataFrame([report])
    if os.path.exists(SAVE_FILE_XLSX):
        existing = pd.read_excel(SAVE_FILE_XLSX, engine="openpyxl")
        existing = existing.drop(columns=["Email"], errors="ignore")
        assessment_id = report.get("Assessment ID")
        if assessment_id and "Assessment ID" in existing.columns:
            if existing["Assessment ID"].fillna("").astype(str).eq(str(assessment_id)).any():
                return
        combined = pd.concat([existing, new_row], ignore_index=True)
    else:
        combined = new_row
    combined.to_excel(SAVE_FILE_XLSX, index=False, engine="openpyxl")


# =============================================================================
# Main app
# =============================================================================

# Patient history: immutable assessments scoped to the signed-in account.
HISTORY_DB = os.path.join(BASE_DIR, "patient_history.db")


def history_text(en, ar):
    return ar if st.session_state.get("lang") == "ar" else en


@contextmanager
def history_connection():
    with closing(sqlite3.connect(HISTORY_DB, timeout=30)) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS patient_assessments (
            record_id TEXT PRIMARY KEY, owner_email TEXT NOT NULL,
            patient_id TEXT NOT NULL, recorded_at TEXT NOT NULL, payload TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS history_owner ON patient_assessments(owner_email, recorded_at)")
        with conn:
            yield conn


def record_assessment(user, report, answers=None, record_id=None):
    owner = normalize_email(user.get("email", ""))
    if not owner:
        raise ValueError("A signed-in account is required to save history.")
    score=history_score({"report":report})
    if (score is None or not 0 <= score <= 100 or not report.get("Timestamp")
            or str(report.get("Patient ID") or "") != str(user.get("patient_id") or "")
            or not report.get("Patient ID") or not answers):
        raise ValueError("Only a completed prediction can be saved.")
    record_id = record_id or secrets.token_hex(16)
    payload = {"report": report, "answers": answers,
               "completed_prediction": True, "record_id": record_id}
    with history_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO patient_assessments VALUES (?, ?, ?, ?, ?)",
                     (record_id, owner, str(report.get("Patient ID", "")),
                      str(report.get("Timestamp", "")), json.dumps(payload, ensure_ascii=False)))
    return record_id


def load_patient_history(user):
    owner=normalize_email(user.get("email", ""))
    patient_id=str(user.get("patient_id") or "").strip()
    if not owner or not patient_id: return []
    with history_connection() as conn:
        rows=conn.execute("SELECT payload FROM patient_assessments WHERE owner_email=? AND patient_id=? ORDER BY recorded_at, rowid",(owner,patient_id)).fetchall()
    records=[]
    for row in rows:
        try:
            record=json.loads(row[0])
            if record.get("completed_prediction") is True and history_score(record) is not None:
                records.append(record)
        except (ValueError,TypeError,KeyError,AttributeError):
            continue
    return records


def history_score(record):
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)%?\s*", str(record["report"].get("Probability", "")))
    return float(match.group(1)) if match else None


def compare_assessments(old, new, arabic=False):
    lines = []
    a, b = history_score(old), history_score(new)
    comparable = old["report"].get("Model version", "legacy") == new["report"].get("Model version", "legacy")
    if not comparable:
        lines.append("تغيّر إصدار النموذج؛ لا يصح تفسير فرق النسب كتغيّر في حالة المريض." if arabic else "Model version changed; the score difference cannot be interpreted as a patient health change.")
    if comparable and a is not None and b is not None:
        delta = b - a
        direction = ("ارتفعت" if delta > 0 else "انخفضت" if delta < 0 else "لم تتغير") if arabic else ("increased" if delta > 0 else "decreased" if delta < 0 else "was unchanged")
        lines.append(f"نسبة النموذج {direction}: {a:.1f}% ← {b:.1f}%؛ الفرق {delta:+.1f} نقطة مئوية." if arabic else f"Model score {direction}: {a:.1f}% to {b:.1f}% ({delta:+.1f} percentage points).")
    for field in ("Result", "Glucose level", "Reported diabetes type", "Urination frequency"):
        before, after = str(old["report"].get(field) or ""), str(new["report"].get(field) or "")
        if before != after:
            lines.append(f"{field}: {before or 'Not recorded'} -> {after or 'Not recorded'}")
    if old.get("answers") is not None and new.get("answers") is not None:
        before, after = old["answers"], new["answers"]
        added = [key for key in after if key in before and before[key] != "Yes" and after[key] == "Yes"]
        removed = [key for key in before if key in after and before[key] == "Yes" and after[key] != "Yes"]
        newly_recorded = [key for key in after if key not in before]
        omitted = [key for key in before if key not in after]
        lines.append(("أعراض أُبلغ عنها حديثًا: " if arabic else "Newly reported symptoms: ") + (", ".join(added) or ("لا يوجد" if arabic else "None")))
        lines.append(("أعراض لم يعد المريض يبلغ عنها: " if arabic else "Symptoms no longer reported: ") + (", ".join(removed) or ("لا يوجد" if arabic else "None")))
        if newly_recorded:
            lines.append("New questions recorded (no earlier answer): " + ", ".join(newly_recorded))
        if omitted:
            lines.append("Questions not asked in the newer assessment: " + ", ".join(omitted))
    else:
        lines.append("لا توجد إجابات تفصيلية في بعض السجلات القديمة؛ راجع وصف الأعراض في التقريرين." if arabic else "Detailed answers are unavailable for some legacy records; compare the symptom narratives in both reports.")
    lines.append("هذه مقارنة لبيانات الفحص المبلّغ عنها وليست تشخيصًا أو إثباتًا للتحسّن أو التدهور الطبي." if arabic else "This compares screening data and self-reported symptoms; it does not establish diagnosis, recovery or clinical deterioration.")
    return lines


def render_patient_history_page():
    user=st.session_state.get("user") or {}
    if user.get("must_change_password",0)==1:
        render_change_password_page(); st.stop()
    st.subheader(history_text("Patient history","سجل المريض"))
    if st.button(tr("back"),key="history_back"): go_to("main")
    try: records=load_patient_history(user)
    except Exception:
        st.error(history_text("History could not be loaded. Please try again.","تعذّر تحميل السجل. حاول مرة أخرى.")); return
    if not records:
        st.info(history_text("No completed predictions yet. Use Predict risk to save an assessment.","لا توجد توقعات مكتملة بعد. اضغط توقع الخطر لحفظ تقييم.")); return
    st.caption(history_text("Reports are saved only after a completed risk prediction.","تُحفظ التقارير بعد إكمال توقع الخطر فقط."))
    for record in reversed(records):
        report=record["report"];key=record["record_id"]
        with st.container(border=True):
            st.write(f"{report.get('Timestamp','')} · {report.get('Probability','')}")
            open_col,download_col=st.columns(2)
            with open_col:
                if st.button(history_text("Open report","فتح التقرير"),key=f"open_{key}",use_container_width=True):
                    log_action(user.get("id",0), "report_opened", "assessment_id="+key)
                    st.session_state["open_history_record"]=key
            with download_col:
                try:
                    data=cached_report_pdf(report,record.get("answers"))
                    st.download_button(history_text("Download PDF","تنزيل PDF"),data=data,
                                       file_name=f"Report_{re.sub(r'[^A-Za-z0-9_-]','_',key)}.pdf",mime="application/pdf",key=f"download_{key}",use_container_width=True,on_click=log_action,args=(user.get("id",0),"report_download_requested","assessment_id="+key))
                except Exception as exc:
                    st.error(history_text("PDF unavailable: ","تعذّر تجهيز PDF: ")+str(exc))
            if st.session_state.get("open_history_record")==key:
                render_medical_report(report,record.get("answers"))
                if st.button(history_text("Close report","إغلاق التقرير"),key=f"close_{key}"):
                    st.session_state.pop("open_history_record",None);st.rerun()
    try:
        signature=hashlib.sha256(json.dumps([normalize_email(user.get("email","")),records],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if st.session_state.get("history_pdf_signature")!=signature:
            st.session_state["history_pdf"]=generate_patient_history_pdf(user,records)
            st.session_state["history_pdf_signature"]=signature
        safe_id=re.sub(r"[^A-Za-z0-9_-]","_",str(user.get("patient_id") or "patient"))
        st.download_button(history_text("Download all reports (PDF)","تنزيل جميع التقارير PDF"),
                           data=st.session_state["history_pdf"],file_name=f"Patient_Reports_{safe_id}.pdf",mime="application/pdf",
                           key="download_all_reports_pdf",type="primary",use_container_width=True,on_click=log_action,args=(user.get("id",0),"all_reports_download_requested","patient_id="+str(user.get("patient_id",""))))
    except Exception as exc:
        st.error(history_text("Combined PDF unavailable: ","تعذّر تجهيز PDF المجمّع: ")+str(exc))


def render_profile_edit_page():
    lang = st.session_state["lang"]
    _user = st.session_state.get("user") or {}
    if _user.get("must_change_password", 0) == 1:
        render_change_password_page()
        st.stop()
    gender = _user.get("gender") or "Male"
    sex_at_birth = gender
    marital_status_key = _user.get("marital_status") or "single"
    if marital_status_key not in MARITAL_STATUS_ORDER:
        marital_status_key = "single"
    country = _user.get("country") or ""
    phone = _user.get("phone") or ""
    type_key = _user.get("diabetes_type") or "not_sure"
    if type_key not in DIABETES_TYPE_KEYS:
        type_key = "not_sure"
    inject_profile_layout_css()
    st.subheader(profile_copy("edit"))
    st.markdown(f'<p class="profile-edit-description">{html_escape("Update your photo, contact details and health information." if lang != "ar" else "عدّل صورتك وبيانات التواصل والمعلومات الصحية.")}</p>', unsafe_allow_html=True)
    with st.container(key="profile_editor"):
        with st.form("profile_edit_form", clear_on_submit=False):
            st.markdown(f"### {edit_text('photo')}")
            current_photo = profile_photo_bytes(_user)
            preview_col, upload_col = st.columns([1, 3], vertical_alignment="center")
            with preview_col:
                if current_photo:
                    photo_uri = base64.b64encode(current_photo).decode("ascii")
                    st.markdown(f'<img class="profile-edit-avatar" src="data:image/png;base64,{photo_uri}" alt="Profile photo">', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="profile-edit-avatar" style="background:#253b57;display:flex;align-items:center;justify-content:center"><svg width="72" height="72" viewBox="0 0 80 80" fill="#c6dcf5"><circle cx="40" cy="25" r="13"/><path d="M12 67c0-15 12.5-24 28-24s28 9 28 24v2H12z"/></svg></div>', unsafe_allow_html=True)
            with upload_col:
                uploaded_photo = st.file_uploader(edit_text("upload"), type=["jpg", "jpeg", "png", "webp"], key="edit_profile_photo")
                st.caption(edit_text("photo_help"))
            photo_data = None
            invalid_photo = False
            if uploaded_photo is not None:
                try:
                    from PIL import Image, ImageOps
                    if uploaded_photo.size > 5 * 1024 * 1024:
                        raise ValueError("Image too large")
                    image = Image.open(uploaded_photo)
                    if image.width * image.height > 20_000_000:
                        raise ValueError("Image dimensions too large")
                    image = ImageOps.exif_transpose(image).convert("RGB")
                    image.thumbnail((512, 512))
                    photo_buffer = BytesIO()
                    image.save(photo_buffer, format="PNG")
                    photo_data = photo_buffer.getvalue()
                    st.image(photo_data, width=140)
                except Exception:
                    invalid_photo = True
                    st.error(edit_text("bad_photo"))
            remove_photo = st.checkbox(edit_text("remove"), key="remove_profile_photo") if current_photo else False
            st.divider()
            st.markdown(f"### {edit_text('personal')}")
            edited_marital = st.selectbox(
                tr("marital_status"), MARITAL_STATUS_ORDER,
                index=MARITAL_STATUS_ORDER.index(marital_status_key),
                format_func=lambda k: marital_status_label(k, sex_at_birth, lang),
            )
            st.divider()
            st.markdown(f"### {edit_text('contact')}")
            country_options = [item[1] for item in COUNTRY_DIAL_CODES]
            edited_country = st.selectbox(
                registration_text(0), country_options,
                index=country_options.index(country) if country in country_options else 0,
            )
            dial_index = next((i for i, item in enumerate(COUNTRY_DIAL_CODES)
                               if item[2] == (_user.get("dial_code") or "")), 0)
            dial_col, phone_col = st.columns([1, 2])
            with dial_col:
                edited_dial = st.selectbox(
                    registration_text(1), COUNTRY_DIAL_CODES, index=dial_index,
                    format_func=lambda item: f"{item[0]} {item[1]} ({item[2]})",
                )
            with phone_col:
                edited_phone = st.text_input(registration_text(2), value=phone, max_chars=24)
            st.divider()
            st.markdown(f"### {edit_text('health')}")
            confirmed = None
            if type_key == "not_sure":
                st.caption(profile_copy("type_help"))
                confirmed = st.selectbox(profile_copy("doctor"),
                                         ["not_sure", "type1", "type2"],
                                         format_func=diabetes_type_label)
            else:
                st.caption(profile_copy("type_locked"))
            st.divider()
            with st.container(key="profile_edit_actions"):
                save_col, cancel_col = st.columns(2)
                with save_col:
                    save_edit = st.form_submit_button(profile_copy("save"), type="primary", use_container_width=True)
                with cancel_col:
                    cancel_edit = st.form_submit_button(profile_copy("cancel"), use_container_width=True)
    if cancel_edit:
        st.session_state.pop("pending_profile_changes", None)
        go_to(st.session_state.pop("profile_return_page", "main"))
    if save_edit:
        digits = re.sub(r"[\s()\-]", "", edited_phone.strip())
        if digits.startswith("+"):
            full_phone = digits
        else:
            full_phone = edited_dial[2] + digits.lstrip("0")
        change_type = confirmed if confirmed in ("type1", "type2") else None
        if invalid_photo:
            return
        if not edited_country.strip() or not full_phone.removeprefix("+").isascii() or not full_phone.removeprefix("+").isdigit() or not 6 <= len(full_phone.removeprefix("+")) <= 15:
            st.error(profile_copy("error"))
            return
        changes = dict(marital_status=edited_marital, country=edited_country,
                       dial_code=edited_dial[2], phone=full_phone, confirmed_type=change_type,
                       photo_data=None if remove_photo else photo_data,
                       photo_name="" if remove_photo else None)
        changes["warn_unknown"] = type_key == "not_sure"
        st.session_state["pending_profile_changes"] = changes
        confirm_profile_changes()



def persist_completed_assessment(user):
    """Persist an explicitly completed assessment or an explicit save retry."""
    state = st.session_state
    record_id = state.get("assessment_id")
    report = state.get("last_report_en")
    if (not record_id or not report
            or state.get("assessment_owner") != normalize_email(user.get("email", ""))):
        return
    with _accounts_store()["lock"]:
        if not state.get("history_saved", False):
            try:
                record_assessment(user, report, state.get("assessment_answers"), record_id)
                state["history_saved"] = True
            except Exception:
                st.warning(history_text("History saving failed. You can retry saving this assessment.", "تعذّر حفظ السجل. يمكنك إعادة حفظ الفحص نفسه."))
        if not state.get("report_saved", False):
            try:
                save_report_to_excel({**report, "Assessment ID": record_id})
                state["report_saved"] = True
            except Exception:
                st.warning(history_text("Excel saving failed. You can retry saving this assessment.", "تعذّر حفظ تقرير Excel. يمكنك إعادة حفظ الفحص نفسه."))


def render_main_app():
    lang = st.session_state["lang"]

    _check_user = st.session_state.get("user") or {}
    if _check_user.get("must_change_password", 0) == 1:
        render_change_password_page()
        st.stop()

    _user = st.session_state.get("user") or {}
    if st.session_state.get("last_report") and st.session_state.get("assessment_owner") != normalize_email(_user.get("email", "")):
        for key in list(st.session_state.keys()):
            if key.startswith(("last_", "assessment_", "pdf_", "history_pdf")) or key in ("medical_pdf_cache", "main_report_open", "history_saved", "report_saved"):
                st.session_state.pop(key, None)
    first_name = (_user.get("first_name") or "").strip()
    last_name = (_user.get("last_name") or "").strip()
    age = age_from_birth_date(_user.get("birth_date"))
    gender = _user.get("gender") or "Male"
    if gender not in GENDER_OPTIONS:
        gender = "Male"
    sex_at_birth = gender
    marital_status_key = _user.get("marital_status") or "single"
    if marital_status_key not in MARITAL_STATUS_ORDER:
        marital_status_key = "single"
    is_child = marital_status_key == "child"
    ever_married = marital_status_key in ("married", "divorced")
    phone = _user.get("phone") or ""
    country = _user.get("country") or ""
    care_location = care.patient_location(_user)
    country = care_location.get("country") or country
    patient_hospital = care_location.get("hospital") or "Not assigned"
    type_key = _user.get("diabetes_type") or "not_sure"
    if type_key not in DIABETES_TYPE_KEYS:
        type_key = "not_sure"

    # WhatsApp-inspired default avatar: category colors describe the chosen
    # account type, not a clinical result or model prediction.
    avatar_colors = {
        "not_sure": ("#244c59", "#b9e5e6"),
        "type1": ("#5b3d65", "#ead5f0"),
        "type2": ("#31577b", "#d5eaff"),
    }
    avatar_bg, avatar_ink = avatar_colors[type_key]
    stored_patient_id = _user.get("patient_id", "")
    if not stored_patient_id:
        # Fallback for old accounts created before this feature
        account_id = _user.get("id")
        stored_patient_id = f"PP-{int(account_id):06d}" if account_id else "Not recorded"
    account_id_display = stored_patient_id
    profile_items = [
        (tr("first_name"), first_name), (tr("last_name"), last_name),
        (tr("age"), str(age)), (tr("gender"), gender_label(gender, lang)),
        (tr("marital_status"), marital_status_label(marital_status_key, sex_at_birth, lang)),
        (tr("phone"), phone), (registration_text(0), country), ("Hospital / clinic", patient_hospital),
        (tr("diabetes_type"), diabetes_type_label(type_key, lang)),
    ]
    profile_html = "".join(
        f'<div class="profile-detail"><span>{html_escape(str(label))}</span>'
        f'<strong>{html_escape(str(value or "Not recorded"))}</strong></div>'
        for label, value in profile_items
    )
    st.markdown(f"""
        <style>
        .st-key-profile_summary {{
            display:block;
            align-items:center; padding:28px; margin:12px 0 22px;
            border:1px solid var(--border, #334155); border-radius:26px;
            background:linear-gradient(125deg, #111c30, #19304b 70%, #244661);
            color:#f8fafc; box-shadow:0 18px 42px rgba(2,6,23,.16);
        }}
        .profile-avatar {{
            width:108px; height:108px; display:grid; place-items:center;
            border-radius:50%; background:{avatar_bg}; color:{avatar_ink};
            box-shadow:0 0 0 6px rgba(255,255,255,.1);
        }}
        .profile-avatar svg {{ width:65px; height:65px; }}
        .profile-content {{ min-width:0; }}
        .profile-heading {{ font-size:1.55rem; font-weight:800; line-height:1.2; margin:0 0 6px; }}
        .profile-name-row {{display:flex; flex-wrap:wrap; align-items:center; gap:6px 16px; margin-bottom:8px;}}
        .profile-name-row .profile-heading {{margin:0;}}
        .profile-id {{font-size:.83rem; color:#dbeafe; padding:5px 10px; border-radius:999px; background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.15);}}
        .profile-subtitle {{ color:#cbd5e1; margin:0 0 16px; font-size:.92rem; }}
        .profile-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:9px 22px; }}
        .profile-detail {{ min-width:0; display:flex; flex-direction:column; gap:2px; }}
        .profile-detail span {{ color:#a9c0df; font-size:.75rem; }}
        .profile-detail strong {{ color:#fff; font-size:.94rem; overflow-wrap:anywhere; }}
        /* Keep the dark profile card readable despite global light-theme rules. */
        .st-key-profile_summary h1.profile-heading {{
            color:#f8fafc !important;
            -webkit-text-fill-color:#f8fafc !important;
        }}
        .st-key-profile_summary .profile-id {{
            color:#f8fafc !important;
            background:#334b65 !important;
            border-color:#60738c !important;
            font-weight:600;
            unicode-bidi:isolate;
        }}
        .st-key-profile_summary .profile-subtitle {{ color:#cbd5e1 !important; }}
        .st-key-profile_summary .profile-detail span {{ color:#b8cee8 !important; }}
        .st-key-profile_summary .profile-detail strong {{ color:#fff !important; }}
        .st-key-profile_summary .profile-edit-text {{ color:#e2e8f0 !important; }}
        .profile-avatar-actions {{display:none;}}
        .profile-edit-text {{
            display:none;
        }}
        @media(max-width:640px) {{
            .st-key-profile_summary {{padding:22px 18px;}}
            .profile-avatar {{width:92px;height:92px;}}
            .profile-grid {{text-align:start; gap:12px;}}
            .profile-name-row {{justify-content:center;}}
            .profile-heading {{font-size:1.3rem;}}
            .profile-avatar-actions {{
                display:block;
                margin-top:12px;
            }}
            .profile-edit-text {{
                display:inline-block;
                padding:8px 14px;
                border-radius:10px;
                background:rgba(255,255,255,.10);
                border:1px solid rgba(255,255,255,.20);
                color:#e2e8f0;
                font-size:.85rem;
                font-weight:600;
                cursor:pointer;
            }}
        }}
        .st-key-profile_summary .profile-avatar {{margin:0 auto 18px;}}
        .st-key-profile_summary [data-testid="stButton"] button {{font-size:.82rem; padding:.4rem .6rem;}}
        </style>
    """, unsafe_allow_html=True)
    with st.container(key="profile_summary"):
        avatar_col, info_col = st.columns([1, 5], vertical_alignment="center")
        with avatar_col:
            photo = profile_photo_bytes(_user)
            if photo:
                photo_uri = base64.b64encode(photo).decode("ascii")
                st.markdown(f'<div class="profile-avatar"><img src="data:image/png;base64,{photo_uri}" alt="{html_escape(edit_text("photo"))}" style="width:100%;height:100%;object-fit:cover;border-radius:50%"></div>', unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="profile-avatar" aria-hidden="true">
                    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="40" cy="25" r="13" fill="currentColor"/>
                        <path d="M12 67c0-15 12.5-24 28-24s28 9 28 24v2H12v-2z" fill="currentColor"/>
                    </svg>
                </div>
                """, unsafe_allow_html=True)
            if st.button(profile_copy("edit"), key="profile_edit_toggle", use_container_width=True):
                st.session_state["profile_return_page"] = st.session_state["page"]
                go_to("profile_edit")
        with info_col:
            st.markdown(f"""
            <div class="profile-content">
                <div class="profile-name-row"><h1 class="profile-heading">{html_escape((first_name + ' ' + last_name).strip() or tr('personal'))}</h1><span class="profile-id">{html_escape(tr('patient_id_label'))}: {html_escape(account_id_display)}</span></div>
                <p class="profile-subtitle">{html_escape(tr('assessment_intro'))}</p>
                <div class="profile-grid">{profile_html}</div>
            </div>

            """, unsafe_allow_html=True)
    st.markdown(f'<div class="status-card">{tr("privacy")}</div>', unsafe_allow_html=True)

    with st.container(key="patient_card"):
        st.markdown("---")
        st.markdown(f'<div class="section-title">{profile_copy("general_title") if type_key == "not_sure" else tr("core")}</div>', unsafe_allow_html=True)
        st.caption("Answers start at No. Change symptoms you have to Yes, then review all answers before prediction." if lang != "ar" else "تبدأ الإجابات بلا. غيّر الأعراض التي تشعر بها إلى نعم ثم راجع جميع الإجابات قبل التوقع.")

        symptom_values = {}
        freq_key = None
        s_col1, s_col2 = st.columns(2)

        for i, col in enumerate(binary_columns):
            key = display_labels.get(col, col)
            label = tr(key)
            target_col = s_col1 if i % 2 == 0 else s_col2
            with target_col:
                if col == "Polyuria":
                    freq_options = [tr("no")] + [f"{tr('yes')} - {tr(k)}" for k in POLYURIA_FREQ_KEYS]
                    selected = st.selectbox(label, freq_options, index=0, key="core_polyuria_freq")
                    if selected is None:
                        symptom_values[col] = None
                    elif selected == freq_options[0]:
                        symptom_values[col] = "No"
                    else:
                        symptom_values[col] = "Yes"
                        freq_key = POLYURIA_FREQ_KEYS[freq_options.index(selected) - 1]
                else:
                    selected = st.selectbox(
                        label,
                        [tr("no"), tr("yes")],
                        index=0, key=f"core_{col}",
                    )
                    symptom_values[col] = "Yes" if selected == tr("yes") else "No" if selected == tr("no") else None

        st.markdown("---")
        st.markdown(f'<div class="section-title">{tr("additional")}</div>', unsafe_allow_html=True)
        st.caption("Answer every question with Yes or No. These answers are included in your report." if lang != "ar" else "أجب عن جميع الأسئلة بنعم أو لا. تُضاف الإجابات إلى تقريرك.")

        extra_values = {}
        e_col1, e_col2 = st.columns(2)

        for i, key in enumerate(extra_symptom_keys):
            target_col = e_col1 if i % 2 == 0 else e_col2
            with target_col:
                selected = st.selectbox(
                    tr(key),
                    [tr("no"), tr("yes")],
                    index=0, key=f"extra_{key}",
                )
                extra_values[key] = "Yes" if selected == tr("yes") else "No" if selected == tr("no") else None

        if type_key in TYPE_QUESTIONS:
            st.markdown("---")
            st.markdown(f'<div class="section-title">{profile_copy("question_title")}</div>', unsafe_allow_html=True)
            st.caption(profile_copy("question_note"))
            tq1, tq2 = st.columns(2)
            for i, question_key in enumerate(TYPE_QUESTIONS[type_key]):
                with (tq1 if i % 2 == 0 else tq2):
                    answer = st.selectbox(tr(question_key), [tr("no"), tr("yes")],
                                          index=0, key=f"type_{type_key}_{question_key}")
                    extra_values[question_key] = "Yes" if answer == tr("yes") else "No" if answer == tr("no") else None

        glu_col1, glu_col2 = st.columns([2, 1])
        with glu_col1:
            glucose_value = st.number_input(
                tr("glucose_level"),
                min_value=0.0,
                max_value=1000.0,
                value=None,
                step=0.1,
                format="%.1f",
                help=tr("glucose_help"),
                key="glucose_value",
            )
        with glu_col2:
            glucose_unit = st.selectbox(tr("glucose_unit"), GLUCOSE_UNITS, key="glucose_unit")

        gender_values = {}
        if is_child:
            gender_keys = child_question_keys(sex_at_birth)
            gender_title = tr("child_section")
            key_kind = f"child_{sex_at_birth}"
        elif gender == "Other":
            gender_keys = list(OTHER_GENERAL_SYMPTOM_KEYS)
            gender_title = tr("other_section")
            key_kind = "other"
        else:
            gender_keys = gender_question_keys(gender, ever_married)
            gender_title = tr("male_section" if gender == "Male" else "female_section")
            key_kind = f"adult_{gender}"

        st.markdown("---")
        st.markdown(f'<div class="section-title">{gender_title}</div>', unsafe_allow_html=True)
        help_key = "other_section_help" if gender == "Other" and not is_child else "gender_section_help"
        st.markdown(f'<div class="section-subtitle">{tr(help_key)}</div>', unsafe_allow_html=True)

        st.caption("Please answer every question." if lang != "ar" else "يرجى الإجابة عن جميع الأسئلة.")
        g_col1, g_col2 = st.columns(2)
        for i, key in enumerate(gender_keys):
            target_col = g_col1 if i % 2 == 0 else g_col2
            with target_col:
                selected = st.selectbox(
                    tr(key),
                    [tr("no"), tr("yes")],
                    index=0, key=f"gender_{key_kind}_{key}",
                )
                gender_values[key] = "Yes" if selected == tr("yes") else "No" if selected == tr("no") else None

        patient_notes = st.text_area(
            history_text("Additional symptoms or patient notes (optional)","أعراض إضافية أو ملاحظات المريض (اختياري)"),
            placeholder=history_text("Describe any symptom that was not included in the questions.","اكتب أي عرض لم تتضمنه الأسئلة."),
            help=history_text("Saved in every report. These notes do not change the model score.","تُحفظ في جميع التقارير ولا تغيّر نسبة النموذج."),
            key="patient_notes",max_chars=3000,height=120)
        submitted = st.button(
            f"{tr('predict')}",
            use_container_width=True,
            type="primary",
            key="predict_btn",
        )

    import hashlib
    review_snapshot = json.dumps({"patient":_user.get("patient_id"), "core":symptom_values,
                                  "extra":extra_values,"gender":gender_values,"notes":patient_notes,
                                  "glucose":glucose_value,"unit":glucose_unit,"age":age,"sex":sex_at_birth},sort_keys=True)
    review_token = hashlib.sha256(review_snapshot.encode()).hexdigest()
    confirmed = st.session_state.pop("_confirmed_screening", None)
    if submitted:
        positive = [k for values in (symptom_values,extra_values,gender_values) for k,v in values.items() if v=="Yes"]
        ux.confirm_action("Review screening answers", "Answers start at No. Confirm that all symptoms you currently have are marked Yes. The completed prediction will be saved in your history.",
                          lambda:st.session_state.update({"_confirmed_screening":review_token}),
                          {"Symptoms marked Yes":", ".join(positive) or "None", "Patient notes":patient_notes or "No additional notes", "Other symptom answers":"No"})
        submitted = False
    if confirmed == review_token:
        submitted = True

    if submitted:
        clean_first_name = first_name.strip()
        clean_last_name = last_name.strip()
        clean_phone = phone.strip()

        errors = []
        if any(value is None for answers in (symptom_values, extra_values, gender_values) for value in answers.values()):
            errors.append("Please answer every question before continuing." if lang != "ar" else "يرجى الإجابة عن جميع الأسئلة قبل المتابعة.")
        for value, label in [
            (clean_first_name, tr("first_name")),
            (clean_last_name, tr("last_name")),
            (clean_phone, tr("phone")),
        ]:
            if not value:
                errors.append(f"{label} {tr('required')}")

        glucose = None
        if glucose_value:
            low, high = GLUCOSE_RANGE[glucose_unit]
            if low <= glucose_value <= high:
                glucose = (float(glucose_value), glucose_unit)
            else:
                errors.append(tr("glucose_invalid"))

        lo, hi = model_metadata["age_range"]
        if age is None or not lo <= age <= hi:
            errors.append(f"العمر المدعوم للنموذج: {lo}–{hi}." if lang == "ar" else f"Supported model age: {lo}–{hi}.")
        if sex_at_birth not in ("Male", "Female"):
            errors.append("بيانات النموذج تدعم ذكر/أنثى فقط؛ لا يمكن تقدير النسبة لهذا الإدخال." if lang == "ar" else "Model data supports Male/Female only; this input cannot be scored.")
        if errors:
            st.error(tr("required_fields"))
            for error in errors:
                st.warning(error)
        else:
            raw_input = {"Age": age, "Gender": sex_at_birth, **symptom_values}
            result, probability = predict_new_patient(raw_input)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Use the patient's stored ID for consistency with the profile.
            patient_id = _user.get("patient_id") or generate_patient_id()

            report_args = dict(
                timestamp=timestamp,
                first=clean_first_name,
                last=clean_last_name,
                phone=clean_phone,
                address=country,
                type_key=type_key,
                age=age,
                gender=sex_at_birth,
                result=result,
                probability=probability,
                symptom_values=symptom_values,
                extra_values=extra_values,
                gender_values=gender_values,
                freq_key=freq_key,
                marital_status_key=marital_status_key,
                birth_sex=sex_at_birth,
                glucose=glucose,
                patient_id=patient_id,
                patient_notes=patient_notes,
                hospital=patient_hospital,
            )

            st.session_state["last_report"] = build_report(lang, **report_args)
            st.session_state["last_report_en"] = build_report("en", **report_args)

            st.session_state["last_extra"] = any(v == "Yes" for v in extra_values.values())
            st.session_state["last_symptoms"] = {
                "core": [c for c in display_labels if symptom_values.get(c) == "Yes"],
                "extra": [k for k in REPORT_EXTRA_KEYS if extra_values.get(k) == "Yes"],
                "gender": [k for k, v in gender_values.items() if v == "Yes"],
                "gender_kind": sex_at_birth if is_child else sex_at_birth,
                "is_child": is_child,
                "freq": freq_key,
            }
            st.session_state["last_result"] = int(result)
            st.session_state["last_probability"] = float(probability)
            st.session_state["report_saved"] = False
            st.session_state["assessment_id"] = secrets.token_hex(16)
            st.session_state["history_saved"] = False
            st.session_state["assessment_answers"] = {
                **{str(tr(display_labels.get(k, k), "en")): v for k, v in symptom_values.items()},
                **{str(tr(k, "en")): v for k, v in extra_values.items()},
                **{str(tr(k, "en")): v for k, v in gender_values.items()},
            }

            st.session_state["assessment_owner"] = normalize_email(_user.get("email", ""))
            # Write only after an explicit successful screening submission.
            persist_completed_assessment(_user)

            log_action(
                _user.get("id", 0),
                "predict",
                f"patient_id={patient_id}, result={result}, prob={probability:.2f}",
            )

            components.html(
                """
                <script>
                window.parent.scrollTo({top: 0, behavior: 'smooth'});
                </script>
                """,
                height=0,
            )

    if st.session_state.get("last_report"):
        report = st.session_state["last_report"]
        report_en = st.session_state["last_report_en"]
        result = st.session_state["last_result"]
        probability = st.session_state["last_probability"]

        st.markdown("---")
        st.markdown(f'<div class="section-title">{tr("result")}</div>', unsafe_allow_html=True)

        css_class = "result-high" if result == 1 else "result-low"
        title = tr("high_risk") if result == 1 else tr("low_risk")

        patient_id_display = report.get("Patient ID", "")
        st.markdown(
            f"""
            <div class="result-card {css_class}">
                <div class="result-label">{tr('result')}</div>
                <div style="font-size:.8rem;color:var(--muted);margin-bottom:6px;">
                    Patient ID: <strong>{patient_id_display}</strong>
                </div>
                <div class="result-title">{'⚠️' if result == 1 else '✅'} {title}</div>
                <div class="score">{probability * 100:.1f}%</div>
                <div class="score-caption">{tr('probability')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption("هذه نسبة تقديرية من نموذج فحص، وليست دقة النموذج أو تشخيصًا طبيًا. لم تُثبت صلاحيتها على مرضى خارج بيانات التدريب." if lang == "ar" else "Estimated screening probability, not model accuracy or a diagnosis. External patient validation has not been established.")
        st.caption("النموذج يستخدم العمر والجنس والأعراض الثمانية المختارة فقط؛ قراءة السكر والأسئلة الإضافية تظهر في التقرير ولا تدخل في حساب النسبة." if lang == "ar" else "The model uses age, sex and the eight selected symptoms. Glucose and additional questions appear in the report but do not affect this probability.")
        st.progress(min(max(probability, 0.0), 1.0))

        with st.expander(f"{tr('symptom_summary')}", expanded=True):
            st.write(report.get("Symptom narrative", ""))
            if report.get("Type-specific answers"):
                st.write(report["Type-specific answers"])
            if report.get("Patient notes"):
                st.markdown("**"+history_text("Patient notes","ملاحظات المريض")+"**")
                st.write(report["Patient notes"])

        with st.expander(f"{tr('recommendation')}", expanded=True):
            if result == 1:
                st.warning(tr("high_recommendation"))
            else:
                st.success(tr("low_recommendation"))

            if st.session_state.get("last_extra", False):
                st.info(tr("extra_notice"))

        # Viewing a previous result never writes a new assessment.
        render_offline_health_guide()
        if (st.session_state.get("assessment_id")
                and st.session_state.get("assessment_owner") == normalize_email(_user.get("email", ""))
                and not (st.session_state.get("history_saved") and st.session_state.get("report_saved"))):
            st.warning(history_text("The assessment was not fully saved. Use Retry saving to save this same assessment.", "لم يكتمل حفظ الفحص. اضغط إعادة الحفظ لحفظ الفحص نفسه."))
            if st.button(history_text("Retry saving", "إعادة الحفظ"), key="retry_assessment_save"):
                persist_completed_assessment(_user)

        st.markdown("---")
        st.markdown(f'<div class="section-title">{tr("download")}</div>', unsafe_allow_html=True)

        if st.button(history_text("Open report","فتح التقرير"),key="main_open_report",use_container_width=True):
            log_action(_user.get("id",0), "report_view_toggled", "assessment_id="+str(st.session_state.get("assessment_id", "")))
            st.session_state["main_report_open"]=not st.session_state.get("main_report_open",False)
        if st.session_state.get("main_report_open"):
            render_medical_report(report_en,st.session_state.get("assessment_answers"))
        try:
            pdf_data=cached_report_pdf(report_en,st.session_state.get("assessment_answers"))
            safe_id=re.sub(r"[^A-Za-z0-9_-]","_",str(report_en.get("Patient ID") or "patient"))
            st.download_button(history_text("Download report PDF","تنزيل التقرير PDF"),data=pdf_data,
                               file_name=f"Diabetes_Report_{safe_id}_{st.session_state.get('assessment_id','result')}.pdf",
                               mime="application/pdf",key="main_download_pdf",type="primary",use_container_width=True,on_click=log_action,args=(_user.get("id",0),"report_download_requested","assessment_id="+str(st.session_state.get("assessment_id",""))))
        except Exception as exc:
            st.error(history_text("The PDF could not be prepared: ","تعذّر تجهيز PDF: ")+str(exc))

        st.markdown(
            f'<div class="notice">⚠️ {tr("medical_notice_long")}</div>',
            unsafe_allow_html=True,
        )


# =============================================================================
# Password Change (Forced)
# =============================================================================

def render_change_password_page():
    """Force the patient to set a new password after admin reset."""
    user = st.session_state.get("user") or {}

    with auth_card(tr("welcome_back"), tr("change_password_intro")):
        _form_title(tr("change_password_title"))

        with st.form("change_password_form", clear_on_submit=False):
            new_pw = st.text_input(
                tr("new_password"),
                type="password",
                key="cp_new",
                max_chars=128,
            )
            confirm_pw = st.text_input(
                tr("confirm_new_password"),
                type="password",
                key="cp_confirm",
                max_chars=128,
            )
            submitted = st.form_submit_button(
                tr("save_new_password"),
                type="primary",
                use_container_width=True,
            )

        if submitted:
            errors = []
            if not new_pw or not confirm_pw:
                errors.append(tr("reg_fill_all"))
            if new_pw and len(new_pw) < MIN_PASSWORD_LEN:
                errors.append(tr("reg_pw_short"))
            if new_pw and confirm_pw and new_pw != confirm_pw:
                errors.append(tr("reg_pw_mismatch"))

            if errors:
                for msg in errors:
                    st.error(msg)
            else:
                try:
                    store = _accounts_store()
                    with store["lock"]:
                        rows = _load_rows()
                        for r in rows:
                            if r["email"] == user.get("email"):
                                r["password_hash"] = hash_password(new_pw)
                                r["must_change_password"] = 0
                                break
                        _save_rows(rows)

                    st.session_state["user"]["must_change_password"] = 0
                    log_action(
                        user.get("id", 0),
                        "password_changed",
                        f"email={user.get('email')}",
                    )
                    st.success(tr("password_changed"))
                    time.sleep(1.5)
                    go_to("main")
                except Exception as exc:
                    st.error(f"{tr('auth_db_error')} {exc}")


# =============================================================================
# App router
# =============================================================================

_ENTER_NAV_JS = r"""
(function () {
  if (window.__ppEnterNav) return;
  window.__ppEnterNav = true;

  var SKIP = ['checkbox', 'radio', 'button', 'submit', 'reset', 'file', 'hidden', 'image', 'range', 'color'];
  var BLOCK = '[data-testid="stElementContainer"], [data-testid="element-container"], .element-container';

  function isField(inp) {
    if (!inp || inp.tagName !== 'INPUT') return false;
    var type = (inp.getAttribute('type') || 'text').toLowerCase();
    if (SKIP.indexOf(type) !== -1) return false;
    if (inp.disabled) return false;
    return inp.offsetParent !== null;
  }

  function fieldsIn(scope) {
    var list = Array.prototype.filter.call(scope.querySelectorAll('input'), isField);
    var rtl = window.getComputedStyle(scope).direction === 'rtl';
    var items = list.map(function (inp) {
      var box = inp.closest(BLOCK) || inp;
      var r = box.getBoundingClientRect();
      return { el: inp, top: r.top, left: r.left };
    });
    items.sort(function (a, b) { return a.top - b.top; });
    var rows = [], cur = null;
    items.forEach(function (it) {
      if (cur && Math.abs(it.top - cur.top) < 32) { cur.items.push(it); }
      else { cur = { top: it.top, items: [it] }; rows.push(cur); }
    });
    var out = [];
    rows.forEach(function (row) {
      row.items.sort(function (a, b) { return rtl ? b.left - a.left : a.left - b.left; });
      row.items.forEach(function (it) { out.push(it.el); });
    });
    return out;
  }

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' || e.shiftKey || e.ctrlKey || e.altKey || e.metaKey || e.isComposing) return;
    var el = e.target;
    if (!isField(el)) return;

    var scope = el.closest('[data-testid="stForm"]') ||
                el.closest('.st-key-patient_card') ||
                el.closest('[data-testid="stMainBlockContainer"]');
    if (!scope) return;

    var inForm = scope.getAttribute('data-testid') === 'stForm';
    var predictBtn = function () { return scope.querySelector('.st-key-predict_btn button'); };
    var fields = fieldsIn(scope);
    var idx = fields.indexOf(el);
    if (idx === -1) return;

    var isLast = idx === fields.length - 1;
    if (isLast && (inForm || !predictBtn())) return;

    function go() {
      var next = fieldsIn(scope)[idx + 1];
      if (next) {
        next.focus();
        try { next.select(); } catch (_) {}
      } else {
        var b = predictBtn();
        if (b) b.focus();
      }
    }

    if (el.closest('[data-baseweb="select"]')) {
      setTimeout(go, 90);
    } else {
      e.preventDefault();
      e.stopPropagation();
      go();
    }
  }, true);
})();
"""


def inject_enter_navigation():
    import json

    components.html(
        "<script>(function(){"
        "var d=window.parent.document;"
        "if(d.getElementById('pp-enter-nav'))return;"
        "var s=d.createElement('script');"
        "s.id='pp-enter-nav';"
        "s.text=" + json.dumps(_ENTER_NAV_JS) + ";"
        "d.head.appendChild(s);"
        "})();</script>",
        height=0,
    )


def render_footer():
    ux.render_confirmation()
    inject_enter_navigation()
    from visual_accessibility import inject_visual_accessibility
    inject_visual_accessibility()
    from app_policies import render as render_policies
    if st.session_state.get("page") not in ("auth", "language"):
        render_policies()
    st.markdown(
        f"""
        <div class="footer">
            {tr('brand')} · {tr('medical_notice')}
        </div>
        """,
        unsafe_allow_html=True,
    )


inject_css()
inject_hover_css()
ux.inject_experience()

from app_policies import route_from_query
route_from_query()
current_page = st.session_state["page"]

if current_page in ("program_policy", "privacy_policy"):
    from app_policies import render_page as render_policy_page
    render_policy_page()
    render_footer()
    st.stop()

if current_page == "splash":
    render_splash()
    st.stop()

if current_page == "language":
    render_language_gate()
    render_footer()
    st.stop()

if current_page == "auth":
    render_auth_page()
    render_footer()
    st.stop()

if current_page == "login":
    render_login_page()
    render_footer()
    st.stop()

if current_page == "register":
    render_register_page()
    render_footer()
    st.stop()

if current_page in ("doctor_register", "doctor_login"):
    care.doctor_auth_page(current_page, go_to, sorted({item[1] for item in COUNTRY_DIAL_CODES}))
    render_footer()
    st.stop()

if current_page == "doctor_dashboard":
    care.render_doctor_dashboard(go_to, logout, render_medical_report, generate_pdf_report, HISTORY_DB)
    render_footer()
    st.stop()

if current_page != "admin" and not st.session_state.get("user"):
    go_to("auth")

render_header()
if current_page != "admin":
    nav = st.columns(3)
    for col, label, route in zip(nav, ["Screening", "My reports", "My care team"], ["main", "patient_history", "patient_care"]):
        if col.button(label, key="ux_nav_"+route, use_container_width=True, type="primary" if current_page==route else "secondary"):
            go_to(route)

if current_page == "admin":
    render_admin_page()
elif current_page == "patient_care":
    care.render_patient_care(st.session_state.get("user") or {}, go_to, sorted({item[1] for item in COUNTRY_DIAL_CODES}))
elif current_page == "patient_history":
    render_patient_history_page()
elif current_page == "profile_edit":
    render_profile_edit_page()
else:
    render_main_app()

render_footer()
