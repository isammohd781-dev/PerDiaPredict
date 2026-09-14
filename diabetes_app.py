import os
import re
from datetime import datetime
from io import BytesIO
from html import escape

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
# Languages: English, Arabic, Hindi, Spanish
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
# Translation system — English / Arabic only
# =============================================================================

LANGUAGES = {
    "English": "en",
    "العربية": "ar",
}

T = {
    "en": {
        "brand": "PerdiaPredict",
        "tagline": "AI-powered early-stage diabetes screening",
        "language": "Language",
        "admin": "Admin Panel",
        "back": "Back",
        "email_title": "Early-Stage Diabetes Screening",
        "email_intro": "Enter your email address to start your assessment.",
        "email": "Email address",
        "email_required": "Email address is required.",
        "email_invalid": "Please enter a valid email address.",
        "continue": "Continue",
        "medical_notice": "Educational screening only — this tool is not a medical diagnosis.",
        "medical_notice_long": "This application is for educational and demonstration purposes only. It does not replace a qualified healthcare professional or a clinical diagnosis.",
        "assessment": "Diabetes Risk Assessment",
        "assessment_intro": "Complete the form below. Your answers are analyzed by the trained machine-learning model.",
        "personal": "Personal Information",
        "first_name": "First name",
        "last_name": "Last name",
        "phone": "Phone number",
        "address": "Residential address (city / area)",
        "diabetes_type": "Which type of diabetes do you believe you have?",
        "not_sure": "Not sure / I don't know",
        "type1": "Type 1",
        "type2": "Type 2",
        "gestational": "Gestational diabetes",
        "prediabetes": "Prediabetes",
        "basic": "Basic Information",
        "age": "Age",
        "gender": "Gender",
        "male": "Male",
        "female": "Female",
        "core": "Core Symptoms",
        "core_help": "Select Yes or No for every symptom.",
        "yes": "Yes",
        "no": "No",
        "additional": "Additional Symptoms",
        "optional": "Optional — these symptoms enrich the report but do not directly change the model probability.",
        "predict": "Predict My Risk",
        "required_fields": "Please complete the required fields.",
        "required": "is required.",
        "result": "Assessment Result",
        "high_risk": "Higher estimated risk of early-stage diabetes",
        "low_risk": "Lower estimated risk based on this screening",
        "probability": "Estimated probability",
        "symptom_summary": "Symptoms Summary",
        "recommendation": "Recommendation",
        "high_recommendation": "Because the estimated risk is high, please arrange a medical evaluation. Do not use this screening as a substitute for professional diagnosis.",
        "low_recommendation": "The current screening result is low risk. Continue healthy habits and speak with a healthcare professional if symptoms persist or concern you.",
        "extra_notice": "Some additional symptoms were selected. If they persist, consider speaking with a healthcare professional.",
        "health_guide": "Healthy Lifestyle & Nutrition Guide",
        "offline": "Built into the app — no external website is required.",
        "plate": "Healthy Plate Method",
        "foods": "Foods to Prefer",
        "limit": "Foods & Drinks to Limit",
        "habits": "Daily Lifestyle Habits",
        "meal_plan": "Weekly Meal Plan",
        "tips": "General Health Tips",
        "download": "Download Assessment Report",
        "download_pdf": "Download PDF Report",
        "saved": "Report saved successfully.",
        "admin_title": "Admin Panel",
        "admin_help": "Restricted area for viewing submitted assessment records.",
        "password": "Admin password",
        "access": "Access granted.",
        "incorrect": "Incorrect password.",
        "no_records": "No saved records yet.",
        "download_excel": "Download Excel file",
        "clean": "Clear Data",
        "confirm": "Are you sure you want to delete all saved records? This action cannot be undone.",
        "delete": "Yes, Delete Data",
        "cancel": "Cancel",
        "deleted": "All data cleared successfully.",
        "theme": "Dark mode",
        "readiness": "Ready",
        "model_status": "Machine-learning model loaded",
        "privacy": "Your information is used only by this application for the assessment/report workflow.",
        "patient_denies": "The patient denies all core and additional symptoms assessed in this screening.",
        "patient_reports": "The patient reports",
        "further": "On further questioning, the patient also reports",
        "no_core": "The patient denies any of the core symptoms assessed in this screening.",
        "constant_fatigue": "Constant fatigue / tiredness",
        "blurry_vision": "Blurry or unclear vision",
        "frequent_infections": "Frequent infections (skin / gum / urinary)",
        "tingling_numbness": "Tingling or numbness in hands or feet",
        "polyuria": "Frequent urination",
        "polydipsia": "Excessive thirst",
        "weight_loss": "Sudden weight loss",
        "irritability": "Irritability",
        "healing": "Delayed wound healing",
        "paresis": "Partial muscle weakness",
        "alopecia": "Abnormal hair loss",
        "itching": "Itching",
        "breakfast": "Breakfast",
        "lunch": "Lunch",
        "dinner": "Dinner",
        "drinks": "Drinks",
        "saturday": "Saturday",
        "sunday": "Sunday",
        "monday": "Monday",
        "tuesday": "Tuesday",
        "wednesday": "Wednesday",
        "thursday": "Thursday",
        "friday": "Friday",
        "half_vegetables": "½ vegetables",
        "quarter_protein": "¼ lean protein",
        "quarter_grains": "¼ whole grains or a moderate starch portion",
        "water_unsweetened": "Water or unsweetened drinks instead of sugary drinks",
        "food_vegetables": "Vegetables and salads",
        "food_legumes": "Beans, lentils and chickpeas",
        "food_grains": "Whole grains and high-fiber foods",
        "food_protein": "Fish, skinless chicken and lean proteins",
        "food_yogurt": "Plain / low-sugar yogurt",
        "food_nuts": "Small portions of nuts",
        "food_fruit": "Whole fruit in moderate portions rather than juice",
        "limit_soft": "Sugary soft drinks and packaged juices",
        "limit_sugar": "Added sugar and very sweet desserts",
        "limit_refined": "Large portions of refined white bread or rice",
        "limit_processed": "Highly processed foods",
        "limit_meals": "Very large meals or unnecessary snacking",
        "habit_activity": "Aim for regular physical activity appropriate for your health.",
        "habit_meals": "Keep consistent meal times.",
        "habit_hydration": "Stay hydrated.",
        "habit_glucose": "If you monitor blood glucose, follow your healthcare professional's advice.",
        "habit_help": "Seek professional advice for persistent or concerning symptoms.",
        "pdf_title": "Early-Stage Diabetes Assessment Report",
        "generated": "Generated",
        "patient_details": "Patient Details",
        "name": "Name",
        "age_gender": "Age / Gender",
        "reported_type": "Reported Type",
        "clinical_presentation": "Clinical Presentation",
        "assessment_result": "Assessment Result",
        "risk_assessment": "Risk Assessment",
        "additional_symptoms": "Additional Symptoms",
        "yes_value": "Yes",
        "no_value": "No",
        "positive_high": "Positive (higher risk)",
        "negative_low": "Negative (lower risk)",
        "disclaimer": "Disclaimer: This report is generated by a machine-learning model for educational and demonstration purposes only. It is NOT a medical diagnosis. Consult a qualified healthcare professional for clinical evaluation.",
        "could_not_save": "Could not save the report.",
        "could_not_read": "Could not read saved records.",
        "missing_files": "Missing required file(s):",
        "missing_files_suffix": "Put the model files in the same folder as the Streamlit app.",
        "email_placeholder": "you@example.com",
    },
    "ar": {
        "brand": "PerdiaPredict",
        "tagline": "فحص مبكر لخطر السكري مدعوم بالذكاء الاصطناعي",
        "language": "اللغة",
        "admin": "لوحة الإدارة",
        "back": "رجوع",
        "email_title": "الفحص المبكر لخطر السكري",
        "email_intro": "أدخل بريدك الإلكتروني لبدء التقييم.",
        "email": "البريد الإلكتروني",
        "email_required": "البريد الإلكتروني مطلوب.",
        "email_invalid": "يرجى إدخال بريد إلكتروني صحيح.",
        "continue": "متابعة",
        "medical_notice": "للتثقيف والفحص الأولي فقط — هذا النظام لا يقدم تشخيصًا طبيًا.",
        "medical_notice_long": "هذا التطبيق لأغراض تعليمية وتجريبية فقط، ولا يحل محل الطبيب أو التشخيص السريري.",
        "assessment": "تقييم خطر السكري",
        "assessment_intro": "أكمل النموذج أدناه. يقوم نموذج التعلم الآلي المدرب بتحليل إجاباتك.",
        "personal": "المعلومات الشخصية",
        "first_name": "الاسم الأول",
        "last_name": "اسم العائلة",
        "phone": "رقم الهاتف",
        "address": "عنوان السكن (المدينة / المنطقة)",
        "diabetes_type": "ما نوع السكري الذي تعتقد أنك مصاب به؟",
        "not_sure": "غير متأكد / لا أعرف",
        "type1": "النوع الأول",
        "type2": "النوع الثاني",
        "gestational": "سكري الحمل",
        "prediabetes": "مقدمات السكري",
        "basic": "المعلومات الأساسية",
        "age": "العمر",
        "gender": "الجنس",
        "male": "ذكر",
        "female": "أنثى",
        "core": "الأعراض الأساسية",
        "core_help": "اختر نعم أو لا لكل عرض.",
        "yes": "نعم",
        "no": "لا",
        "additional": "أعراض إضافية",
        "optional": "اختياري — هذه الأعراض تثري التقرير لكنها لا تغير احتمالية النموذج مباشرة.",
        "predict": "احسب مستوى الخطر",
        "required_fields": "يرجى إكمال الحقول المطلوبة.",
        "required": "مطلوب.",
        "result": "نتيجة التقييم",
        "high_risk": "احتمالية مرتفعة وفقًا للفحص الحالي",
        "low_risk": "احتمالية منخفضة وفقًا للفحص الحالي",
        "probability": "الاحتمالية المقدرة",
        "symptom_summary": "ملخص الأعراض",
        "recommendation": "التوصية",
        "high_recommendation": "نظرًا لارتفاع مستوى الخطر المقدر، يُنصح بإجراء تقييم طبي. لا تعتمد على هذا الفحص بدل التشخيص الطبي.",
        "low_recommendation": "نتيجة الفحص الحالية تشير إلى خطر منخفض. استمر في العادات الصحية واستشر الطبيب إذا استمرت الأعراض أو كان لديك قلق.",
        "extra_notice": "تم اختيار بعض الأعراض الإضافية. إذا استمرت، فكر في استشارة مختص صحي.",
        "health_guide": "دليل التغذية ونمط الحياة الصحي",
        "offline": "مدمج داخل التطبيق — لا يحتاج إلى موقع خارجي.",
        "plate": "طريقة الطبق الصحي",
        "foods": "أطعمة يُفضل تناولها",
        "limit": "أطعمة ومشروبات يُفضل الحد منها",
        "habits": "عادات يومية صحية",
        "meal_plan": "خطة الوجبات الأسبوعية",
        "tips": "نصائح صحية عامة",
        "download": "تحميل تقرير التقييم",
        "download_pdf": "تحميل تقرير PDF",
        "saved": "تم حفظ التقرير بنجاح.",
        "admin_title": "لوحة الإدارة",
        "admin_help": "منطقة مقيدة لعرض سجلات التقييمات المرسلة.",
        "password": "كلمة مرور الإدارة",
        "access": "تم السماح بالدخول.",
        "incorrect": "كلمة المرور غير صحيحة.",
        "no_records": "لا توجد سجلات محفوظة حتى الآن.",
        "download_excel": "تحميل ملف Excel",
        "clean": "مسح البيانات",
        "confirm": "هل أنت متأكد من حذف جميع السجلات؟ لا يمكن التراجع عن هذا الإجراء.",
        "delete": "نعم، احذف البيانات",
        "cancel": "إلغاء",
        "deleted": "تم حذف جميع البيانات بنجاح.",
        "theme": "الوضع الداكن",
        "readiness": "جاهز",
        "model_status": "نموذج التعلم الآلي محمل",
        "privacy": "تُستخدم معلوماتك داخل التطبيق فقط لأغراض التقييم والتقرير.",
        "patient_denies": "ينفي المريض جميع الأعراض الأساسية والإضافية التي تم تقييمها في هذا الفحص.",
        "patient_reports": "يفيد المريض بوجود",
        "further": "وعند السؤال بشكل إضافي، أفاد المريض بوجود",
        "no_core": "ينفي المريض وجود أي من الأعراض الأساسية التي تم تقييمها.",
        "constant_fatigue": "التعب أو الإرهاق المستمر",
        "blurry_vision": "تشوش أو ضبابية الرؤية",
        "frequent_infections": "التهابات متكررة (الجلد / اللثة / المسالك البولية)",
        "tingling_numbness": "وخز أو تنميل في اليدين أو القدمين",
        "polyuria": "كثرة التبول",
        "polydipsia": "العطش الشديد",
        "weight_loss": "فقدان الوزن المفاجئ",
        "irritability": "التهيج أو العصبية",
        "healing": "بطء التئام الجروح",
        "paresis": "ضعف جزئي في العضلات",
        "alopecia": "تساقط الشعر غير الطبيعي",
        "itching": "الحكة",
        "breakfast": "الإفطار",
        "lunch": "الغداء",
        "dinner": "العشاء",
        "drinks": "المشروبات",
        "saturday": "السبت",
        "sunday": "الأحد",
        "monday": "الاثنين",
        "tuesday": "الثلاثاء",
        "wednesday": "الأربعاء",
        "thursday": "الخميس",
        "friday": "الجمعة",
        "half_vegetables": "½ خضروات",
        "quarter_protein": "¼ بروتين قليل الدهون",
        "quarter_grains": "¼ حبوب كاملة أو كمية معتدلة من النشويات",
        "water_unsweetened": "الماء أو المشروبات غير المحلاة بدلًا من المشروبات السكرية",
        "food_vegetables": "الخضروات والسلطات",
        "food_legumes": "الفاصوليا والعدس والحمص",
        "food_grains": "الحبوب الكاملة والأطعمة الغنية بالألياف",
        "food_protein": "السمك والدجاج منزوع الجلد والبروتينات قليلة الدهون",
        "food_yogurt": "الزبادي الطبيعي أو قليل السكر",
        "food_nuts": "كميات صغيرة من المكسرات",
        "food_fruit": "الفاكهة الكاملة بكميات معتدلة بدلًا من العصير",
        "limit_soft": "المشروبات الغازية السكرية والعصائر المعلبة",
        "limit_sugar": "السكر المضاف والحلويات شديدة الحلاوة",
        "limit_refined": "الكميات الكبيرة من الخبز الأبيض أو الأرز المكرر",
        "limit_processed": "الأطعمة شديدة التصنيع",
        "limit_meals": "الوجبات الكبيرة جدًا أو تناول الوجبات الخفيفة دون حاجة",
        "habit_activity": "مارس نشاطًا بدنيًا منتظمًا ومناسبًا لحالتك الصحية.",
        "habit_meals": "حافظ على أوقات منتظمة للوجبات.",
        "habit_hydration": "احرص على شرب كمية كافية من السوائل.",
        "habit_glucose": "إذا كنت تراقب مستوى سكر الدم، فاتبع إرشادات المختص الصحي.",
        "habit_help": "اطلب المشورة الطبية إذا استمرت الأعراض أو كانت مقلقة.",
        "pdf_title": "تقرير تقييم خطر السكري في مراحله المبكرة",
        "generated": "تاريخ الإنشاء",
        "patient_details": "بيانات المريض",
        "name": "الاسم",
        "age_gender": "العمر / الجنس",
        "reported_type": "النوع المذكور",
        "clinical_presentation": "الأعراض والحالة المبلغ عنها",
        "assessment_result": "نتيجة التقييم",
        "risk_assessment": "تقييم الخطر",
        "additional_symptoms": "أعراض إضافية",
        "yes_value": "نعم",
        "no_value": "لا",
        "positive_high": "إيجابي (احتمالية أعلى)",
        "negative_low": "سلبي (احتمالية أقل)",
        "disclaimer": "تنبيه: تم إنشاء هذا التقرير بواسطة نموذج تعلم آلي لأغراض تعليمية وتجريبية فقط. لا يُعد تشخيصًا طبيًا. يُرجى استشارة مختص صحي لإجراء التقييم السريري.",
        "could_not_save": "تعذر حفظ التقرير.",
        "could_not_read": "تعذر قراءة السجلات المحفوظة.",
        "missing_files": "الملفات المطلوبة غير موجودة:",
        "missing_files_suffix": "ضع ملفات النموذج في المجلد نفسه مع تطبيق Streamlit.",
        "email_placeholder": "you@example.com",
    },
}


def tr(key: str) -> str:
    lang = st.session_state.get("lang", "en")
    return T.get(lang, T["en"]).get(key, T["en"].get(key, key))


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
# Model
# =============================================================================

@st.cache_resource
def load_artifacts():
    missing = [p for p in [MODEL_PATH, SCALER_PATH, COLUMNS_PATH] if not os.path.exists(p)]
    if missing:
        st.error(
            tr("missing_files") + " "
            + ", ".join(missing) + ". "
            + tr("missing_files_suffix")
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

if "lang" not in st.session_state:
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
# Responsive / modern UI
# =============================================================================

def inject_css():
    rtl = st.session_state.get("lang", "en") == "ar"
    direction = "rtl" if rtl else "ltr"
    theme = "dark" if st.session_state.get("dark_mode", True) else "light"

    st.markdown(
        f"""
        <style>
        :root {{
            --primary:#2563eb;
            --primary-2:#06b6d4;
            --text:#0f172a;
            --muted:#64748b;
            --surface:#ffffff;
            --surface-2:#f8fafc;
            --surface-soft:#eef4ff;
            --border:#dbe3ef;
            --input:#ffffff;
            --success:#16a34a;
            --danger:#dc2626;
            --warning-bg:#fff7ed;
            --warning-border:#fed7aa;
            --warning-text:#9a3412;
            --info-bg:#eff6ff;
            --info-border:#bfdbfe;
            --info-text:#1e40af;
            --shadow:0 18px 45px rgba(15,23,42,.08);
        }}
        html[data-perdia-theme="dark"] {{
            --text:#f8fafc;
            --muted:#94a3b8;
            --surface:#111827;
            --surface-2:#172033;
            --surface-soft:#070d18;
            --border:#334155;
            --input:#0b1220;
            --warning-bg:#422006;
            --warning-border:#92400e;
            --warning-text:#fde68a;
            --info-bg:#172554;
            --info-border:#1d4ed8;
            --info-text:#bfdbfe;
            --shadow:0 18px 45px rgba(0,0,0,.28);
        }}
        html, body, [class*="css"] {{
            font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans","Noto Sans Arabic",Arial,sans-serif;
        }}
        html[data-perdia-theme="dark"], html[data-perdia-theme="dark"] body {{
            color-scheme:dark;
            background:#070d18 !important;
        }}
        html[data-perdia-theme="light"], html[data-perdia-theme="light"] body {{
            color-scheme:light;
            background:#f3f7fc !important;
        }}
        .stApp {{
            min-height:100vh;
            background:
                radial-gradient(circle at 5% 0%, rgba(37,99,235,.14), transparent 28%),
                radial-gradient(circle at 100% 8%, rgba(6,182,212,.10), transparent 25%),
                var(--surface-soft) !important;
            color:var(--text) !important;
        }}
        [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"] {{
            background:transparent !important;
            color:var(--text) !important;
        }}
        .block-container {{ max-width:1040px !important; padding:1.1rem 1rem 4rem !important; }}
        header[data-testid="stHeader"] {{
            background:color-mix(in srgb,var(--surface-soft) 90%,transparent) !important;
        }}
        .brand {{ display:flex; align-items:center; gap:12px; padding:8px 2px 4px; }}
        .brand-icon {{
            width:50px;height:50px;border-radius:16px;display:flex;align-items:center;justify-content:center;
            background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff !important;font-size:25px;
            box-shadow:0 10px 24px rgba(37,99,235,.22);
        }}
        .brand-name {{ font-size:1.2rem;font-weight:850;letter-spacing:-.025em;color:var(--text) !important; }}
        .brand-tagline {{ font-size:.78rem;color:var(--muted) !important;margin-top:2px; }}
        .hero {{
            background:linear-gradient(135deg,#071226 0%,#172554 55%,#075985 100%);
            color:#fff !important;border-radius:28px;padding:34px 30px;margin:18px 0;
            box-shadow:0 20px 50px rgba(2,6,23,.28);overflow:hidden;position:relative;
        }}
        .hero:after {{
            content:"";position:absolute;width:240px;height:240px;border-radius:50%;
            background:rgba(125,211,252,.12);right:-80px;top:-95px;
        }}
        .hero:before {{
            content:"";position:absolute;width:120px;height:120px;border-radius:50%;
            border:1px solid rgba(255,255,255,.10);right:55px;bottom:-65px;
        }}
        .hero h1 {{ color:#fff !important;font-size:clamp(1.8rem,4vw,2.75rem);line-height:1.12;margin:0 0 10px;letter-spacing:-.04em;position:relative;z-index:1; }}
        .hero p {{ color:rgba(255,255,255,.84) !important;margin:0;max-width:760px;line-height:1.7;position:relative;z-index:1; }}
        .pill {{
            display:inline-flex;align-items:center;gap:7px;padding:7px 12px;border-radius:999px;
            background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.18);
            color:#f8fafc !important;font-size:.76rem;font-weight:700;margin-bottom:15px;position:relative;z-index:1;
        }}
        .section-card,.result-card {{
            background:var(--surface) !important;border:1px solid var(--border) !important;
            color:var(--text) !important;box-shadow:var(--shadow) !important;
        }}
        .section-card {{ border-radius:22px;padding:22px;margin:14px 0; }}
        .section-title {{ font-size:1.14rem;font-weight:850;color:var(--text) !important;margin-bottom:4px; }}
        .section-subtitle {{ color:var(--muted) !important;font-size:.86rem;line-height:1.6;margin-bottom:14px; }}
        .status-card {{
            display:flex;align-items:center;gap:10px;padding:13px 15px;border-radius:16px;
            background:var(--info-bg) !important;border:1px solid var(--info-border) !important;
            color:var(--info-text) !important;font-size:.84rem;line-height:1.5;margin:12px 0 18px;
        }}
        .result-card {{ border-radius:24px;padding:26px;margin:14px 0; }}
        .result-high {{ border-left:6px solid var(--danger) !important; }}
        .result-low {{ border-left:6px solid var(--success) !important; }}
        .result-label {{ color:var(--muted) !important;font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.07em; }}
        .result-title {{ font-size:clamp(1.2rem,3vw,1.6rem);font-weight:850;margin:6px 0 16px;color:var(--text) !important; }}
        .score {{ font-size:clamp(2.2rem,7vw,3.7rem);line-height:1;font-weight:900;letter-spacing:-.055em;color:var(--text) !important; }}
        .score-caption {{ color:var(--muted) !important;font-size:.82rem;margin-top:7px; }}
        .notice {{ border-radius:16px;padding:14px 16px;background:var(--warning-bg) !important;border:1px solid var(--warning-border) !important;color:var(--warning-text) !important;font-size:.84rem;line-height:1.6;margin:12px 0; }}
        .footer {{ text-align:center;color:var(--muted) !important;font-size:.74rem;padding:26px 0 4px; }}
        .stMarkdown,[data-testid="stMarkdownContainer"],[data-testid="stWidgetLabel"],label,p,li,span {{ color:var(--text); }}
        [data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p {{ color:var(--muted) !important; }}
        input,textarea,div[data-baseweb="select"] > div,div[data-baseweb="input"] > div,
        [data-testid="stNumberInput"] input,[data-testid="stTextInput"] input {{
            background:var(--input) !important;color:var(--text) !important;border:1px solid var(--border) !important;
            border-radius:13px !important;caret-color:var(--primary) !important;
        }}
        input::placeholder,textarea::placeholder {{ color:#64748b !important;opacity:1 !important; }}
        input:focus,textarea:focus,div[data-baseweb="select"] > div:focus-within {{
            border-color:var(--primary) !important;box-shadow:0 0 0 3px rgba(37,99,235,.14) !important;
        }}
        [data-baseweb="select"] *,[role="listbox"] *,[role="option"] {{ color:var(--text) !important; }}
        div[data-baseweb="popover"],div[data-baseweb="menu"],[role="listbox"] {{
            background:var(--surface) !important;border:1px solid var(--border) !important;
        }}
        [role="option"]:hover,[role="option"][aria-selected="true"] {{ background:var(--surface-2) !important; }}
        [data-testid="stRadio"],[data-testid="stCheckbox"],[data-testid="stToggle"] {{ color:var(--text) !important; }}
        [data-testid="stRadio"] label,[data-testid="stCheckbox"] label,[data-testid="stToggle"] label {{ color:var(--text) !important; }}
        .stButton > button,.stDownloadButton > button,button[kind="primary"] {{
            border-radius:14px !important;min-height:46px !important;font-weight:750 !important;
            transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease;
        }}
        .stButton > button:hover,.stDownloadButton > button:hover {{
            transform:translateY(-1px);border-color:var(--primary) !important;box-shadow:0 9px 20px rgba(0,0,0,.14) !important;
        }}
        .stButton > button[kind="primary"],button[kind="primary"] {{
            background:linear-gradient(135deg,#2563eb,#0284c7) !important;color:#fff !important;border:none !important;
        }}
        [data-testid="stMetric"] {{ background:var(--surface) !important;border:1px solid var(--border) !important;border-radius:18px;padding:14px;color:var(--text) !important; }}
        [data-testid="stMetricValue"],[data-testid="stMetricLabel"],[data-testid="stMetricDelta"] {{ color:var(--text) !important; }}
        .stExpander,[data-testid="stExpander"] {{ border-radius:16px !important;border:1px solid var(--border) !important;background:var(--surface) !important;color:var(--text) !important; }}
        .stExpander details,.stExpander summary {{ background:var(--surface) !important;color:var(--text) !important; }}
        [data-testid="stAlert"] {{ background:var(--surface) !important;border:1px solid var(--border) !important;color:var(--text) !important; }}
        [data-testid="stDataFrame"],[data-testid="stTable"] {{ background:var(--surface) !important;color:var(--text) !important; }}
        @media (max-width:640px) {{
            .block-container {{ padding:.65rem .7rem 3rem !important; }}
            .hero {{ border-radius:21px;padding:24px 19px;margin:10px 0 14px; }}
            .hero h1 {{ font-size:1.75rem; }}
            .section-card {{ border-radius:18px;padding:16px;margin:10px 0; }}
            .brand-icon {{ width:43px;height:43px;border-radius:13px;font-size:22px; }}
            .brand-name {{ font-size:1rem; }}
            .brand-tagline {{ font-size:.68rem; }}
            .stButton > button,.stDownloadButton > button {{ min-height:50px !important; }}
            div[data-testid="stHorizontalBlock"] {{ gap:.55rem !important; }}
            .score {{ font-size:2.65rem; }}
        }}
        [dir="rtl"],.rtl {{ direction:rtl;text-align:right; }}
        [dir="rtl"] .hero,[dir="rtl"] .status-card,[dir="rtl"] .section-card,[dir="rtl"] .result-card {{ text-align:right; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    components.html(
        f"""
        <script>
        const root = window.parent.document.documentElement;
        root.setAttribute("dir", "{direction}");
        root.setAttribute("data-perdia-theme", "{theme}");
        </script>
        """,
        height=0,
    )


# =============================================================================
# Header
# =============================================================================

def render_header():
    left, theme_col, right = st.columns([2.5, 1.2, 2.0], vertical_alignment="center")

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
            f"🌙 {tr('theme')}",
            value=st.session_state.get("dark_mode", True),
            key="dark_mode",
            help=tr("theme"),
        )

    with right:
        options = list(LANGUAGES.keys())
        current_label = next(k for k, v in LANGUAGES.items() if v == st.session_state["lang"])
        selected = st.selectbox(
            f"🌐 {tr('language')}",
            options,
            index=options.index(current_label),
            key="language_selector",
        )
        new_lang = LANGUAGES[selected]
        if new_lang != st.session_state["lang"]:
            st.session_state["lang"] = new_lang
            st.rerun()

    if st.session_state["page"] == "admin":
        if st.button(f"⬅️ {tr('back')}", use_container_width=True):
            go_to("main" if st.session_state["user_email"] else "email_gate")
    else:
        if st.button(f"🔒 {tr('admin')}", use_container_width=True):
            go_to("admin")


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
    lang = st.session_state["lang"]

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

    core_yes = [tr(key) for col, key in core_keys.items() if symptom_values.get(col) == "Yes"]
    extra_yes = [tr(key) for key in extra_symptom_keys if extra_values.get(key) == "Yes"]

    if not core_yes and not extra_yes:
        return tr("patient_denies")

    sentences = []
    if core_yes:
        if lang == "ar":
            sentences.append(tr("patient_reports") + " " + "، ".join(core_yes) + ".")
        else:
            sentences.append(tr("patient_reports") + " " + _join(core_yes) + ".")
    else:
        sentences.append(tr("no_core"))

    if extra_yes:
        if lang == "ar":
            sentences.append(tr("further") + " " + "، ".join(extra_yes) + ".")
        else:
            sentences.append(tr("further") + " " + _join(extra_yes) + ".")

    return " ".join(sentences)


# =============================================================================
# Health guide
# =============================================================================

MEAL_PLANS = {
    "en": [
        ("saturday", "Boiled eggs + whole-grain bread + cucumber & tomato", "Grilled chicken + brown rice + green salad", "Grilled fish + vegetables", "Water / unsweetened tea"),
        ("sunday", "Oatmeal + low-fat milk + berries", "Lentil soup + fresh salad", "Lean grilled meat + vegetables", "Water / mint tea"),
        ("monday", "Plain yogurt + whole-grain cereal + nuts", "Tuna salad + whole-grain bread", "Stuffed peppers/zucchini + small rice portion", "Water / herbal tea"),
        ("tuesday", "Vegetable omelet + whole-grain bread", "Chicken + quinoa/bulgur + salad", "Vegetable soup + low-fat cheese", "Water / green tea"),
        ("wednesday", "Greek yogurt + chia + low-sugar fruit", "Grilled fish + leafy salad", "Lentils/chickpeas + vegetables", "Water / hibiscus tea"),
        ("thursday", "Whole-grain bread + low-fat cheese + vegetables", "Lean meat/chicken + vegetables + brown rice", "Large salad + chicken/tuna", "Water / mint tea"),
        ("friday", "Oatmeal or eggs + raw nuts", "Fish/chicken + vegetables + salad", "Light vegetable soup + cheese", "Water / herbal tea"),
    ],
    "ar": [
        ("saturday", "بيض مسلوق + خبز كامل الحبوب + خيار وطماطم", "دجاج مشوي + أرز بني + سلطة خضراء", "سمك مشوي + خضروات", "ماء / شاي غير محلى"),
        ("sunday", "شوفان + حليب قليل الدسم + توت", "شوربة عدس + سلطة طازجة", "لحم مشوي قليل الدهون + خضروات", "ماء / شاي بالنعناع"),
        ("monday", "زبادي طبيعي + حبوب كاملة + مكسرات", "سلطة تونة + خبز كامل الحبوب", "فلفل أو كوسا محشية + كمية صغيرة من الأرز", "ماء / شاي أعشاب"),
        ("tuesday", "عجة بالخضروات + خبز كامل الحبوب", "دجاج + كينوا أو برغل + سلطة", "شوربة خضروات + جبن قليل الدسم", "ماء / شاي أخضر"),
        ("wednesday", "زبادي يوناني + بذور الشيا + فاكهة قليلة السكر", "سمك مشوي + سلطة ورقية", "عدس أو حمص + خضروات", "ماء / كركديه غير محلى"),
        ("thursday", "خبز كامل الحبوب + جبن قليل الدسم + خضروات", "لحم أو دجاج قليل الدهون + خضروات + أرز بني", "سلطة كبيرة + دجاج أو تونة", "ماء / شاي بالنعناع"),
        ("friday", "شوفان أو بيض + مكسرات غير مملحة", "سمك أو دجاج + خضروات + سلطة", "شوربة خضروات خفيفة + جبن", "ماء / شاي أعشاب"),
    ],
}


def render_meal_plan():
    st.markdown(f'<div class="section-title">📅 {tr("meal_plan")}</div>', unsafe_allow_html=True)

    rows = []
    for day_key, breakfast, lunch, dinner, drinks in MEAL_PLANS[st.session_state["lang"]]:
        rows.append([
            tr(day_key), breakfast, lunch, dinner, drinks
        ])

    df = pd.DataFrame(
        rows,
        columns=[tr("meal_plan"), tr("breakfast"), tr("lunch"), tr("dinner"), tr("drinks")],
    )
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
            f"- {tr('half_vegetables')}\n"
            f"- {tr('quarter_protein')}\n"
            f"- {tr('quarter_grains')}\n"
            f"- {tr('water_unsweetened')}"
        )

    with st.expander(f"🥗 {tr('foods')}"):
        st.markdown(
            f"- {tr('food_vegetables')}\n"
            f"- {tr('food_legumes')}\n"
            f"- {tr('food_grains')}\n"
            f"- {tr('food_protein')}\n"
            f"- {tr('food_yogurt')}\n"
            f"- {tr('food_nuts')}\n"
            f"- {tr('food_fruit')}"
        )

    with st.expander(f"⚠️ {tr('limit')}"):
        st.markdown(
            f"- {tr('limit_soft')}\n"
            f"- {tr('limit_sugar')}\n"
            f"- {tr('limit_refined')}\n"
            f"- {tr('limit_processed')}\n"
            f"- {tr('limit_meals')}"
        )

    with st.expander(f"🏃 {tr('habits')}"):
        st.markdown(
            f"- {tr('habit_activity')}\n"
            f"- {tr('habit_meals')}\n"
            f"- {tr('habit_hydration')}\n"
            f"- {tr('habit_glucose')}\n"
            f"- {tr('habit_help')}"
        )

    with st.expander(f"📅 {tr('meal_plan')}"):
        render_meal_plan()


# =============================================================================
# PDF
# =============================================================================

def _pdf_text(value):
    """Escape text before inserting user/content values into ReportLab Paragraphs."""
    return escape(str(value or "")).replace("\n", "<br/>")


def generate_pdf_report(report_data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=tr("pdf_title"),
        author=tr("brand"),
    )

    styles = getSampleStyleSheet()
    pdf_font = "Helvetica"
    if st.session_state.get("lang") == "ar":
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        arabic_font_path = "/usr/share/fonts/truetype/noto/NotoSansArabicUI-Regular.ttf"
        arabic_bold_path = "/usr/share/fonts/truetype/noto/NotoSansArabicUI-Bold.ttf"
        if os.path.exists(arabic_font_path):
            pdfmetrics.registerFont(TTFont("PerdiaArabic", arabic_font_path))
            pdf_font = "PerdiaArabic"
        if os.path.exists(arabic_bold_path):
            pdfmetrics.registerFont(TTFont("PerdiaArabicBold", arabic_bold_path))

    bold_font = "PerdiaArabicBold" if pdf_font == "PerdiaArabic" and os.path.exists("/usr/share/fonts/truetype/noto/NotoSansArabicUI-Bold.ttf") else pdf_font
    align = 2 if st.session_state.get("lang") == "ar" else 0

    title_style = ParagraphStyle(
        "DocTitle", parent=styles["Title"], fontName=bold_font, fontSize=18,
        textColor=colors.HexColor("#0d3b66"), spaceAfter=4, alignment=align
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle", parent=styles["Normal"], fontName=pdf_font, fontSize=11,
        textColor=colors.HexColor("#555555"), alignment=align
    )
    heading_style = ParagraphStyle(
        "Heading2Custom", parent=styles["Heading2"], fontName=bold_font, fontSize=12,
        textColor=colors.HexColor("#0d3b66"), spaceBefore=10, spaceAfter=6, alignment=align
    )
    body_style = ParagraphStyle(
        "BodyCustom", parent=styles["Normal"], fontName=pdf_font, fontSize=9.5,
        leading=14, alignment=align
    )

    elements = []
    title = Paragraph(f"<b>{_pdf_text(tr('brand'))}</b>", title_style)
    subtitle = Paragraph(_pdf_text(tr("pdf_title")), subtitle_style)

    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=55, height=55)
        header = Table([[logo, [title, subtitle]]], colWidths=[70, 470])
    else:
        header = Table([[[title, subtitle]]], colWidths=[540])

    header.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    elements.append(header)

    divider = Table([[""]], colWidths=[540], rowHeights=[2])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2563eb"))]))
    elements.append(divider)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(
        f"<b>{_pdf_text(tr('generated'))}:</b> {_pdf_text(report_data.get('Timestamp', ''))}",
        body_style
    ))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(_pdf_text(tr("patient_details")), heading_style))

    patient_info = [
        [f"{tr('name')}:", _pdf_text(f"{report_data.get('First name', '')} {report_data.get('Last name', '')}")],
        [f"{tr('age_gender')}:", _pdf_text(f"{report_data.get('Age', '')} / {report_data.get('Gender', '')}")],
        [f"{tr('phone')}:", _pdf_text(report_data.get("Phone", ""))],
        [f"{tr('email')}:", _pdf_text(report_data.get("Email", "N/A"))],
        [f"{tr('address')}:", _pdf_text(report_data.get("Address", ""))],
        [f"{tr('reported_type')}:", _pdf_text(report_data.get("Reported diabetes type", ""))],
    ]

    # Use Paragraphs in table cells so Arabic text uses the selected font.
    patient_info = [
        [Paragraph(_pdf_text(a), body_style), Paragraph(_pdf_text(b), body_style)]
        for a, b in patient_info
    ]
    t1 = Table(patient_info, colWidths=[145, 395])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f4f8")),
        ("FONTNAME", (0, 0), (0, -1), bold_font),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(t1)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(_pdf_text(tr("clinical_presentation")), heading_style))
    elements.append(Paragraph(_pdf_text(report_data.get("Symptom narrative", "")), body_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(_pdf_text(tr("assessment_result")), heading_style))
    is_positive = "Positive" in report_data.get("Result", "")
    result_color = colors.HexColor("#dc2626") if is_positive else colors.HexColor("#16a34a")
    display_result = tr("positive_high") if is_positive else tr("negative_low")

    t2 = Table(
        [
            [Paragraph(_pdf_text(tr("risk_assessment")), body_style), Paragraph(_pdf_text(display_result), body_style)],
            [Paragraph(_pdf_text(tr("probability")), body_style), Paragraph(_pdf_text(report_data.get("Probability", "")), body_style)],
            [Paragraph(_pdf_text(tr("additional_symptoms")), body_style), Paragraph(_pdf_text(tr("yes_value") if report_data.get("Notable extra symptoms") == "Yes" else tr("no_value")), body_style)],
        ],
        colWidths=[175, 365],
    )
    t2.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), bold_font),
        ("TEXTCOLOR", (1, 0), (1, 0), result_color),
        ("FONTNAME", (1, 0), (1, 0), bold_font),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 18))

    elements.append(Paragraph(f"<b>{_pdf_text(tr('disclaimer'))}</b>", body_style))

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

    with st.form("email_gate_form", clear_on_submit=False):
        email_input = st.text_input(
            tr("email"),
            value=st.session_state.get("user_email") or "",
            placeholder=tr("email_placeholder"),
        )
        continue_clicked = st.form_submit_button(
            f"🚀 {tr('continue')}",
            use_container_width=True,
            type="primary",
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
        st.markdown(f'<div class="section-subtitle">{tr("email_intro")}</div>', unsafe_allow_html=True)

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
                st.success(tr("saved"))
            except Exception:
                st.warning(tr("could_not_save"))

        st.markdown("---")
        st.markdown(f'<div class="section-title">📄 {tr("download")}</div>', unsafe_allow_html=True)

        pdf_data = generate_pdf_report(report)
        safe_first = re.sub(r"[^\w\-]+", "_", report["First name"]).strip("_") or "Patient"
        safe_last = re.sub(r"[^\w\-]+", "_", report["Last name"]).strip("_") or "Report"
        file_name_pdf = f"Diabetes_Report_{safe_first}_{safe_last}.pdf"

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

                except Exception:
                    st.warning(tr("could_not_read"))
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
