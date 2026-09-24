import base64
import hashlib
import hmac
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
import time
import urllib.request
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta

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

_page_icon = "logo.png" if os.path.exists("logo.png") else None

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
    """Questions to show for this gender (all of them only if ever married)."""
    keys = MALE_SYMPTOM_KEYS if gender == "Male" else FEMALE_SYMPTOM_KEYS
    if ever_married:
        return list(keys)
    intimate = MALE_INTIMATE_KEYS if gender == "Male" else FEMALE_INTIMATE_KEYS
    return [k for k in keys if k not in intimate]


# -----------------------------------------------------------------------------
# Marital status, gender-agreeing.
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
    """Gender-agreeing label for a marital-status option."""
    lang = lang or st.session_state.get("lang", "en")
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
# Gender options per USCDI v3 / HL7 Gender Harmony.
# -----------------------------------------------------------------------------
# Simple gender options: Male / Female / Other
GENDER_OPTIONS = ["Male", "Female", "Other"]

# General (neutral) questions for patients who choose "Other".
# These are informational only and do NOT change the estimated probability.
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


SPACING_OFF_LANGS = {"ar", "hi", "zh"}


def _init_theme():
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

DIABETES_TYPE_KEYS = ["not_sure", "type1", "type2", "prediabetes"]

GLUCOSE_UNITS = ["mg/dL", "mmol/L"]
GLUCOSE_RANGE = {"mg/dL": (20.0, 1000.0), "mmol/L": (1.1, 55.0)}


# =============================================================================
# Accounts database (Excel: accounts.xlsx)
# =============================================================================
ACCOUNTS_FILE = "accounts.xlsx"
DB_FILE = "perdiapredict.db"
PBKDF2_ITERATIONS = 260_000
MIN_PASSWORD_LEN = 8
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 5
SUPPORT_WHATSAPP_NUMBER = "+256771715275"
SUPPORT_WHATSAPP_URL = "https://wa.me/256771715275"
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ACCOUNT_FIELDS = [
    "id", "first_name", "last_name", "email", "birth_date",
    "gender", "marital_status",
    "password_hash", "created_at", "last_login", "failed_attempts", "locked_until",
]
ACCOUNT_HEADERS = [
    "ID", "First name", "Last name", "Email", "Birth date",
    "Gender", "Marital status",
    "Password hash", "Created at", "Last login", "Failed attempts", "Locked until",
]
_FIELD_BY_HEADER = dict(zip(ACCOUNT_HEADERS, ACCOUNT_FIELDS))


@st.cache_resource
def _accounts_store():
    import threading
    return {"lock": threading.RLock(), "mtime": None, "rows": []}


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


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
            "first_name": get(raw, "first_name"),
            "last_name": get(raw, "last_name"),
            "email": email,
            "birth_date": get(raw, "birth_date"),
            "gender": get(raw, "gender"),
            "marital_status": get(raw, "marital_status"),
            "password_hash": pw_hash,
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
    widths = [7, 16, 16, 32, 13, 10, 16, 60, 20, 20, 15, 20]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
    ws.freeze_panes = "A2"

    tmp = ACCOUNTS_FILE + ".tmp"
    wb.save(tmp)
    os.replace(tmp, ACCOUNTS_FILE)

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
                password: str, gender: str, marital_status: str = "single"):
    email = normalize_email(email)
    try:
        password_hash = hash_password(password)
        store = _accounts_store()
        with store["lock"]:
            rows = _load_rows()
            if any(r["email"] == email for r in rows):
                return False, "auth_email_taken"
            rows.append({
                "id": max([r["id"] for r in rows] + [0]) + 1,
                "first_name": first_name.strip(),
                "last_name": last_name.strip(),
                "email": email,
                "birth_date": birth_date.isoformat(),
                "gender": gender,
                "marital_status": marital_status,
                "password_hash": password_hash,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "last_login": "",
                "failed_attempts": 0,
                "locked_until": "",
            })
            _save_rows(rows)
        return True, None
    except Exception:
        return False, "auth_db_error"


def authenticate(email: str, password: str):
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
        return {
            "id": row["id"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "email": row["email"],
            "birth_date": row["birth_date"],
            "gender": row.get("gender", "Male"),
            "marital_status": row.get("marital_status", "single"),
        }, "ok"

    attempts = int(row["failed_attempts"] or 0) + 1
    locked_until, status = "", "invalid"
    if attempts >= MAX_FAILED_LOGINS:
        locked_until = (now + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds")
        attempts, status = 0, "locked"
    _update_account(email, failed_attempts=attempts, locked_until=locked_until)
    return None, status


def render_accounts_admin():
    rows = _load_rows()
    st.markdown(
        f'<div class="section-title">Registered accounts ({len(rows)})</div>',
        unsafe_allow_html=True,
    )

    if rows:
        table = pd.DataFrame([
            {
                "ID": r["id"], "First name": r["first_name"], "Last name": r["last_name"],
                "Email": r["email"], "Birth date": r["birth_date"],
                "Gender": r.get("gender", ""),
                "Marital status": r.get("marital_status", ""),
                "Created at": r["created_at"], "Last login": r["last_login"],
            }
            for r in rows
        ])
        st.dataframe(table, use_container_width=True, hide_index=True)
        with open(ACCOUNTS_FILE, "rb") as f:
            st.download_button(
                "Download accounts (Excel)",
                data=f.read(),
                file_name=ACCOUNTS_FILE,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_accounts",
            )
    else:
        st.info("No accounts yet.")

    with st.expander("Restore accounts from an Excel backup"):
        st.caption(
            "Upload a previously downloaded accounts.xlsx. Accounts whose email already "
            "exists are skipped, so nothing is overwritten."
        )
        upload = st.file_uploader("accounts.xlsx", type=["xlsx"], key="restore_accounts_file")
        if upload is not None and st.button("Restore now", key="restore_accounts_btn"):
            try:
                from io import BytesIO
                from openpyxl import load_workbook

                wb = load_workbook(BytesIO(upload.getvalue()), read_only=True, data_only=True)
                incoming = _rows_from_sheet(wb.active)
                wb.close()

                store = _accounts_store()
                with store["lock"]:
                    current = _load_rows()
                    known = {r["email"] for r in current}
                    next_id = max([r["id"] for r in current] + [0]) + 1
                    added = skipped = 0
                    for r in incoming:
                        if r["email"] in known or not r["password_hash"].startswith("pbkdf2_sha256$"):
                            skipped += 1
                            continue
                        r["id"] = next_id
                        next_id += 1
                        current.append(r)
                        known.add(r["email"])
                        added += 1
                    if added:
                        _save_rows(current)
                st.success(f"Restored {added} account(s); skipped {skipped}.")
            except Exception as exc:
                st.error(f"Could not read that file: {exc}")


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

        /* Hide +/- step buttons on the locked age field */
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

    with menu_col:
        if st.button(
            "",
            icon=":material/refresh:",
            key="menu_restart",
            help=tr("menu_restart"),
            use_container_width=True,
        ):
            restart_app(st.session_state["lang"])

    with admin_col:
        if st.session_state["page"] == "admin":
            if st.button(f"{tr('back')}", key="admin_back", use_container_width=True):
                go_to("auth")
        else:
            if st.button(f"{tr('logout')}", key="logout_btn", use_container_width=True):
                logout()

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
def auth_card(title: str, subtitle: str):
    inject_auth_css()
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
        if st.button(f"{tr('admin')}", use_container_width=True, key="auth_btn_admin"):
            go_to("admin")
        if st.button(f"{tr('back')}", use_container_width=True, key="auth_link_back"):
            go_to("language")


def render_login_page():
    with auth_card(tr("welcome_back"), tr("welcome_back_sub")):
        _form_title(tr("login_title"))

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                tr("auth_email"), key="login_email", max_chars=254,
                placeholder=tr("auth_email"), label_visibility="collapsed",
            )
            password = st.text_input(
                tr("auth_password"), type="password", key="login_pw", max_chars=128,
                placeholder=tr("auth_password"), label_visibility="collapsed",
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
    """Return a unique patient ID in the format YYMMDDNN.

    Format:
      YY  = last 2 digits of year      (26  = 2026)
      MM  = month, 2 digits            (09  = September)
      DD  = day,   2 digits            (19  = the 19th)
      NN  = patient number that day    (01, 02, 03, ...)

    Example: 26091901 = 2026-09-19, patient #01.
    """
    today = date.today()
    prefix = f"{today.year % 100:02d}{today.month:02d}{today.day:02d}"

    # Count how many patients have already been assigned today
    count_today = 0
    if os.path.exists(SAVE_FILE_XLSX):
        try:
            existing = pd.read_excel(SAVE_FILE_XLSX, engine="openpyxl")
            if "Patient ID" in existing.columns:
                for value in existing["Patient ID"].dropna().astype(str):
                    value = value.strip()
                    if value.startswith(prefix) and len(value) >= 10:
                        count_today += 1
        except Exception:
            pass

    next_num = count_today + 1
    if next_num > 99:
        # More than 99 patients in one day: extend gracefully
        return f"{prefix}{next_num:03d}"
    return f"{prefix}{next_num:02d}"


def _build_birth_date(day, month, year):
    if day is None or month is None or year is None:
        return None
    try:
        born = date(int(year), int(month), int(day))
    except ValueError:
        return None
    return born if date(1900, 1, 1) <= born < date.today() else None


def render_register_page():
    with auth_card(tr("welcome_new"), tr("welcome_new_sub")):
        _form_title(tr("reg_title"))

        this_year = date.today().year
        with st.form("register_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                first_name = st.text_input(f"{tr('first_name')} *", key="reg_first", max_chars=60)
            with c2:
                last_name = st.text_input(f"{tr('last_name')} *", key="reg_last", max_chars=60)

            email = st.text_input(f"{tr('auth_email')} *", key="reg_email", max_chars=254)

            gender_reg = st.selectbox(
                f"{tr('gender')} *",
                GENDER_OPTIONS,
                format_func=gender_label,
                key="reg_gender",
            )
            marital_status_reg = st.selectbox(
                f"{tr('marital_status')} *",
                MARITAL_STATUS_ORDER,
                format_func=lambda k: marital_status_label(k, gender_reg),
                key="reg_marital",
            )

            st.markdown(
                f'<div class="section-title" style="font-size:.95rem">{tr("dob")} *</div>',
                unsafe_allow_html=True,
            )
            d1, d2, d3 = st.columns(3)
            with d1:
                day = st.selectbox(
                    tr("dob_day"), list(range(1, 32)), index=None,
                    placeholder=tr("dob_choose"), key="reg_day",
                )
            with d2:
                month = st.selectbox(
                    tr("dob_month"), list(range(1, 13)), index=None, format_func=month_label,
                    placeholder=tr("dob_choose"), key="reg_month",
                )
            with d3:
                year = st.selectbox(
                    tr("dob_year"), list(range(this_year, 1899, -1)), index=None,
                    placeholder=tr("dob_choose"), key="reg_year",
                )

            password = st.text_input(
                f"{tr('auth_password')} *", type="password", key="reg_pw", max_chars=128
            )
            password2 = st.text_input(
                f"{tr('auth_confirm_password')} *", type="password", key="reg_pw2", max_chars=128
            )

            st.markdown(
                f"""
                <div class="notice">
                    <strong>⚠️ {tr('reg_warn_title')}</strong><br>
                    {tr('reg_warn_text')}
                </div>
                """,
                unsafe_allow_html=True,
            )
            accepted = st.checkbox(tr("reg_accept"), key="reg_accept")

            submitted = st.form_submit_button(
                f"{tr('reg_button')}", type="primary", use_container_width=True
            )

        if submitted:
            clean_first = first_name.strip()
            clean_last = last_name.strip()
            clean_email = normalize_email(email)
            birth = _build_birth_date(day, month, year)
            dob_chosen = day is not None and month is not None and year is not None

            errors = []
            if not (clean_first and clean_last and clean_email and dob_chosen
                    and password and password2 and gender_reg and marital_status_reg):
                errors.append(tr("reg_fill_all"))
            if clean_email and not EMAIL_REGEX.match(clean_email):
                errors.append(tr("reg_email_invalid"))
            if dob_chosen and birth is None:
                errors.append(tr("reg_dob_invalid"))
            if password and len(password) < MIN_PASSWORD_LEN:
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
                    gender_reg, marital_status_reg
                )
                if ok:
                    user, _status = authenticate(clean_email, password)
                    st.session_state["user"] = user
                    go_to("main")
                else:
                    st.error(tr(error_key))

        if st.button(f"{tr('auth_registered')}", key="auth_link_login"):
            go_to("login")

        render_support_card()

        if st.button(f"{tr('back')}", key="auth_link_back_register"):
            go_to("auth")


def _admin_password_ok(candidate: str) -> bool:
    return hmac.compare_digest(candidate.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))


def render_admin_page():
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

    st.markdown(
        f"""
        <div class="hero">
            <div class="pill">{tr('admin_title')}</div>
            <h1>{tr('admin_title')}</h1>
            <p>{tr('admin_help')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.success(tr("access"))
    render_accounts_admin()

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
                if st.button(f"{tr('clean')}", use_container_width=True):
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


def build_report(lang, timestamp, first, last, phone, address, type_key,
                 age, gender, result, probability, symptom_values, extra_values,
                 gender_values=None, freq_key=None, marital_status_key=None,
                 birth_sex=None, glucose=None, patient_id="") -> dict:
    """Build the report dictionary in the requested language."""
    gender_values = gender_values or {}
    any_extra = any(v == "Yes" for v in extra_values.values()) or any(
        v == "Yes" for v in gender_values.values()
    )
    gender_yes = [tr(k, lang) for k, v in gender_values.items() if v == "Yes"]

    gender_text = gender_label(gender, lang)

    return {
        "Patient ID": patient_id,
        "Timestamp": timestamp,
        "First name": first,
        "Last name": last,
        "Phone": phone,
        "Address": address,
        "Reported diabetes type": tr(type_key, lang),
        "Age": age,
        "Gender": gender_text,
        "Marital status": (
            marital_status_label(marital_status_key, birth_sex or gender, lang)
            if marital_status_key else ""
        ),
        "Result": tr("positive_high" if result == 1 else "negative_low", lang),
        "Probability": f"{probability * 100:.1f}%",
        "Notable extra symptoms": tr("yes" if any_extra else "no", lang),
        "Urination frequency": tr(freq_key, lang) if freq_key else "",
        "Glucose level": f"{glucose[0]:g} {glucose[1]}" if glucose else "",
        "Gender-specific symptoms": ", ".join(gender_yes),
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
FONT_DIR = os.path.join(BASE_DIR, "fonts")
TMP_FONT_DIR = os.path.join(tempfile.gettempdir(), "perdiapredict_fonts")

try:
    import uharfbuzz  # noqa: F401
    SHAPING_OK = True
except Exception:
    SHAPING_OK = False

_NOTO_URL = "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts"
_CJK_URL = "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/SubsetOTF/SC"

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

LANG_SCRIPT = {
    "ar": "arabic",
    "fa": "arabic",
    "ur": "arabic",
    "hi": "devanagari",
    "mr": "devanagari",
    "ne": "devanagari",
    "zh": "cjk",
}

SCRIPT_REGEX = {
    "arabic": re.compile("[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"),
    "devanagari": re.compile("[\u0900-\u097F]"),
    "cjk": re.compile("[\u2E80-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF]"),
}

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
    rtl = is_rtl(lang)

    def t(key):
        return tr(key, lang)

    core_texts, extra_texts, gender_texts = [], [], []
    gender_head = ""
    if symptoms:
        for c in symptoms.get("core", []):
            if c not in display_labels:
                continue
            label = t(display_labels[c])
            if c == "Polyuria" and symptoms.get("freq"):
                label = f"{label}\n{t(symptoms['freq'])}"
            core_texts.append(label)
        extra_texts = [t(k) for k in symptoms.get("extra", []) if k in extra_symptom_keys]
        kind = symptoms.get("gender_kind")
        if symptoms.get("is_child"):
            g_keys = child_question_keys(kind)
            gender_head = t("child_section")
        elif kind == "Transgender":
            g_keys = TRANS_SYMPTOM_KEYS
            gender_head = t("trans_section")
        else:
            g_keys = MALE_SYMPTOM_KEYS if kind == "Male" else FEMALE_SYMPTOM_KEYS
            gender_head = t("male_section" if kind == "Male" else "female_section")
        gender_texts = [t(k) for k in symptoms.get("gender", []) if k in g_keys]

    values = [str(v) for v in report_data.values()]
    texts = values + core_texts + extra_texts + gender_texts + [gender_head] + [
        t(k)
        for k in (
            "pdf_title", "pdf_generated", "pdf_patient", "pdf_name", "pdf_age_gender",
            "phone", "marital_status", "glucose_level", "pdf_address", "pdf_type", "pdf_clinical",
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

    if level >= 2:
        band_h, after_band, card_h = 27, 4, 34
        sec_top, sec_after = 2.5, 7
        row_extra, card_pad = 2.8, 3.2
        pill_min, pill_gap_y, pill_pad_v, pill_size, pill_lh = 6.4, 1.4, 2.2, 8.2, 3.9
        head_h, head_size, sep = 4.6, 8.2, 4.2
        dis_gap, dis_size, dis_lh = 3, 7.8, 4.0
    elif level == 1:
        band_h, after_band, card_h = 30, 5, 35
        sec_top, sec_after = 3.2, 7.5
        row_extra, card_pad = 3.2, 3.8
        pill_min, pill_gap_y, pill_pad_v, pill_size, pill_lh = 6.8, 1.6, 2.4, 8.5, 4.1
        head_h, head_size, sep = 4.8, 8.5, 4.6
        dis_gap, dis_size, dis_lh = 3.5, 8.0, 4.2
    else:
        band_h, after_band, card_h = 34, 8, 37
        sec_top, sec_after = 5.5, 9
        row_extra, card_pad = 4.3, 5
        pill_min, pill_gap_y, pill_pad_v, pill_size, pill_lh = 8.0, 2.4, 2.8, 8.8, 4.4
        head_h, head_size, sep = 5.5, 8.8, 6.5
        dis_gap, dis_size, dis_lh = 6, 8.6, 4.7

    def font(style="", size=10, color=C_TEXT):
        pdf.set_font(base_font, style, size)
        pdf.set_text_color(*_rgb(color))

    def measure(text, w, size, style="", lh=5.4):
        font(style, size)
        lines = pdf.multi_cell(
            w, lh, safe(text), align=align, wrapmode=wrap, dry_run=True, output="LINES"
        )
        return max(1, len(lines)) * lh

    def put(text, x, y, w, size=10, style="", color=C_TEXT, lh=5.4, text_align=None):
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
        ensure(sec_top + sec_after + 4 + need)
        y = pdf.get_y() + sec_top
        bar_x = right - 1.6 if rtl else left
        pdf.set_fill_color(*_rgb(C_BLUE))
        pdf.rect(bar_x, y, 1.6, 6, style="F")
        text_x = left if rtl else left + 4.5
        put(title, text_x, y + 0.2, width - 4.5, size=12.5, style="B", color=C_NAVY, lh=6)
        pdf.set_y(y + sec_after)

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

    name = f"{report_data.get('First name', '')} {report_data.get('Last name', '')}".strip()
    age_gender = f"{report_data.get('Age', '')} / {report_data.get('Gender', '')}"
    patient_id_text = report_data.get("Patient ID", "")
    rows = []
    if patient_id_text:
        # Fallback: use a simple English label if translations are missing.
        pid_label = t("patient_id_label")
        if pid_label == "patient_id_label":
            pid_label = "Patient ID"
        rows.append([(pid_label, patient_id_text)])
    rows.extend([
        [(t("pdf_name"), name), (t("pdf_age_gender"), age_gender)],
        [(t("phone"), report_data.get("Phone", "")),
         (t("marital_status"), report_data.get("Marital status", ""))],
        [(t("pdf_address"), report_data.get("Address", "")),
         (t("pdf_type"), report_data.get("Reported diabetes type", ""))],
    ])
    glucose_text = report_data.get("Glucose level", "")
    if glucose_text:
        rows.append([(t("glucose_level"), glucose_text)])

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

    narrative = report_data.get("Symptom narrative", "")
    have_pills = bool(core_texts or extra_texts or gender_texts)

    if not have_pills:
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
            existing = existing.drop(columns=["Email"], errors="ignore")
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

    _user = st.session_state.get("user") or {}
    st.session_state.pop("basic_gender", None)
    if "in_first_name" not in st.session_state:
        st.session_state["in_first_name"] = _user.get("first_name", "")
    if "in_last_name" not in st.session_state:
        st.session_state["in_last_name"] = _user.get("last_name", "")
    st.session_state.pop("basic_age", None)

    st.markdown(
        f"""
        <div class="hero">
            <div class="pill">{tr('readiness')} • {tr('model_status')}</div>
            <h1>{tr('assessment')}</h1>
            <p>{tr('assessment_intro')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="status-card">{tr("privacy")}</div>',
        unsafe_allow_html=True,
    )

    with st.container(key="patient_card"):
        # ------------------------------------------------ Personal information
        st.markdown(f'<div class="section-title">{tr("personal")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{tr("gender_hint")}</div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            first_name = st.text_input(f"{tr('first_name')} *", key="in_first_name")
        with c2:
            last_name = st.text_input(f"{tr('last_name')} *", key="in_last_name")

        c5, c6, c7 = st.columns(3)
        with c5:
            # Age comes from the account's date of birth and cannot be changed.
            calculated_age = age_from_birth_date(_user.get("birth_date")) or 40
            age = st.number_input(
                tr("age"),
                min_value=1,
                max_value=120,
                step=1,
                value=calculated_age,
                disabled=True,
                key="basic_age_locked",
            )
        with c6:
            # Gender comes from the account and cannot be changed here.
            gender = _user.get("gender", "") or "Male"
            if gender not in GENDER_OPTIONS:
                gender = "Male"

            st.text_input(
                tr("gender"),
                value=gender_label(gender),
                disabled=True,
                key="basic_gender_locked",
            )

            # The model only knows Male / Female -> "Other" falls back to "Male".
            sex_at_birth = gender if gender in ("Male", "Female") else "Male"
        with c7:
            # Marital status comes from the account.
            marital_status_key = _user.get("marital_status", "single") or "single"
            if marital_status_key not in MARITAL_STATUS_ORDER:
                marital_status_key = "single"

            st.text_input(
                tr("marital_status"),
                value=marital_status_label(marital_status_key, sex_at_birth, lang),
                disabled=True,
                key="basic_marital_locked",
            )

        is_child = marital_status_key == "child"
        ever_married = marital_status_key in ("married", "divorced")

        phone = st.text_input(f"{tr('phone')} *", key="in_phone")
        address = st.text_input(f"{tr('address')} *", key="in_address")

        diabetes_type = st.selectbox(
            tr("diabetes_type"),
            [tr(k) for k in DIABETES_TYPE_KEYS],
            key="in_diabetes_type",
        )

        # ------------------------------------------------------ Core symptoms
        st.markdown("---")
        st.markdown(f'<div class="section-title">{tr("core")}</div>', unsafe_allow_html=True)
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

        # ---------------------------------------------------- Additional symptoms
        st.markdown("---")
        st.markdown(f'<div class="section-title">{tr("additional")}</div>', unsafe_allow_html=True)
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

        # Optional blood sugar / glucose reading
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

        # ------------------------------- Questions that depend on the patient
        gender_values = {}
        if is_child:
            gender_keys = child_question_keys(sex_at_birth)
            gender_title = tr("child_section")
            key_kind = f"child_{sex_at_birth}"
        elif gender == "Other":
            # General neutral questions for the "Other" gender option.
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

        g_col1, g_col2 = st.columns(2)
        for i, key in enumerate(gender_keys):
            target_col = g_col1 if i % 2 == 0 else g_col2
            with target_col:
                selected = st.selectbox(
                    tr(key),
                    [tr("no"), tr("yes")],
                    key=f"gender_{key_kind}_{key}",
                )
                gender_values[key] = "Yes" if selected == tr("yes") else "No"

        submitted = st.button(
            f"{tr('predict')}",
            use_container_width=True,
            type="primary",
            key="predict_btn",
        )

    if submitted:
        clean_first_name = first_name.strip()
        clean_last_name = last_name.strip()
        clean_phone = phone.strip()
        clean_address = address.strip()

        errors = []
        for value, label in [
            (clean_first_name, tr("first_name")),
            (clean_last_name, tr("last_name")),
            (clean_phone, tr("phone")),
            (clean_address, tr("address")),
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

        if errors:
            st.error(tr("required_fields"))
            for error in errors:
                st.warning(error)
        else:
            raw_input = {"Age": age, "Gender": sex_at_birth, **symptom_values}
            result, probability = predict_new_patient(raw_input)

            type_key = DIABETES_TYPE_KEYS[[tr(k) for k in DIABETES_TYPE_KEYS].index(diabetes_type)]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            if not st.session_state.get("current_patient_id"):
                st.session_state["current_patient_id"] = generate_patient_id()
            patient_id = st.session_state["current_patient_id"]

            report_args = dict(
                timestamp=timestamp,
                first=clean_first_name,
                last=clean_last_name,
                phone=clean_phone,
                address=clean_address,
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
            )

            st.session_state["last_report"] = build_report(lang, **report_args)
            st.session_state["last_report_en"] = build_report("en", **report_args)

            st.session_state["last_extra"] = any(v == "Yes" for v in extra_values.values())
            st.session_state["last_symptoms"] = {
                "core": [c for c in display_labels if symptom_values.get(c) == "Yes"],
                "extra": [k for k in extra_symptom_keys if extra_values.get(k) == "Yes"],
                "gender": [k for k, v in gender_values.items() if v == "Yes"],
                "gender_kind": sex_at_birth if is_child else sex_at_birth,
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

        st.progress(min(max(probability, 0.0), 1.0))

        with st.expander(f"{tr('symptom_summary')}", expanded=True):
            st.write(report.get("Symptom narrative", ""))

        with st.expander(f"{tr('recommendation')}", expanded=True):
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
        st.markdown(f'<div class="section-title">{tr("download")}</div>', unsafe_allow_html=True)

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
            label=f"{tr('download_pdf')}",
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
    inject_enter_navigation()
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

current_page = st.session_state["page"]

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

if current_page != "admin" and not st.session_state.get("user"):
    go_to("auth")

render_header()

if current_page == "admin":
    render_admin_page()
else:
    render_main_app()

render_footer()