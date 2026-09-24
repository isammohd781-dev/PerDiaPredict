"""
patient_id_patch.py
===================
تعديلان على diabetes_app.py:
  1. العمر يُحسب من تاريخ الميلاد في الحساب ولا يمكن تعديله.
  2. رقم تعريفي لكل مريض (PP-00001، PP-00002، ...) يظهر في التقرير.

طريقة الاستخدام:
    python patient_id_patch.py

سيأخذ نسخة احتياطية قبل أي تعديل.
"""

import os
import shutil
import sys
from datetime import datetime


APP_FILE = "diabetes_app.py"
BACKUP_FILE = f"app_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def replace_once(content, old, new, label):
    count = content.count(old)
    if count == 0:
        print(f"   ✗ [{label}] لم يتم العثور على النص.")
        return content, False
    if count > 1:
        print(f"   ✗ [{label}] وُجد {count} مرات (يجب مرة واحدة).")
        return content, False
    print(f"   ✓ [{label}]")
    return content.replace(old, new, 1), True


def main():
    if not os.path.exists(APP_FILE):
        print(f"✗ لم يتم العثور على {APP_FILE}")
        sys.exit(1)

    shutil.copy2(APP_FILE, BACKUP_FILE)
    print(f"✓ نسخة احتياطية: {BACKUP_FILE}\n")

    content = read_file(APP_FILE)
    ok = True

    # ============================================================
    # 1) إضافة دوال مساعدة لتوليد الرقم التعريفي
    #    نضيفها بعد دالة age_from_birth_date (الموجودة مسبقاً)
    # ============================================================
    print("1) إضافة دالة توليد الرقم التعريفي (generate_patient_id)...")
    content, r = replace_once(
        content,
        '''def age_from_birth_date(value):
    """Age in whole years from an ISO date string (YYYY-MM-DD), limited to 1-120.
    Returns None if the value is missing or not a valid date."""
    try:
        born = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    today = date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return max(1, min(120, years))
# DOB-HELPERS-END''',
        '''def age_from_birth_date(value):
    """Age in whole years from an ISO date string (YYYY-MM-DD), limited to 1-120.
    Returns None if the value is missing or not a valid date."""
    try:
        born = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    today = date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return max(1, min(120, years))


def generate_patient_id() -> str:
    """Return a unique patient ID like PP-00001, PP-00002, ...

    It reads the saved_reports.xlsx file (if it exists) and picks the next
    number after the highest ID already used. The IDs are short, memorable
    and stay stable for the same patient across visits.
    """
    prefix = "PP-"
    highest = 0
    if os.path.exists(SAVE_FILE_XLSX):
        try:
            existing = pd.read_excel(SAVE_FILE_XLSX, engine="openpyxl")
            if "Patient ID" in existing.columns:
                for value in existing["Patient ID"].dropna().astype(str):
                    value = value.strip()
                    if value.startswith(prefix):
                        try:
                            number = int(value[len(prefix):])
                            highest = max(highest, number)
                        except ValueError:
                            pass
        except Exception:
            pass
    return f"{prefix}{highest + 1:05d}"
# DOB-HELPERS-END''',
        "دالة generate_patient_id",
    )
    ok &= r

    # ============================================================
    # 2) تغيير حقل العمر إلى حقل ثابت (disabled)
    # ============================================================
    print("2) تعديل حقل العمر في الصفحة الرئيسية (ثابت)...")
    content, r = replace_once(
        content,
        '''        with c5:
            age = st.number_input(tr("age"), min_value=1, max_value=120, step=1, key="basic_age")''',
        '''        with c5:
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
            )''',
        "حقل العمر الثابت",
    )
    ok &= r

    # ============================================================
    # 3) إزالة السطر الذي كان يملأ basic_age (لم نعد نحتاجه)
    # ============================================================
    print("3) تنظيف مفتاح basic_age القديم...")
    content, r = replace_once(
        content,
        '''    if "basic_age" not in st.session_state:
        st.session_state["basic_age"] = age_from_birth_date(_user.get("birth_date")) or 40''',
        '''    st.session_state.pop("basic_age", None)  # old key, no longer used''',
        "تنظيف basic_age",
    )
    ok &= r

    # ============================================================
    # 4) إضافة Patient ID إلى التقرير (build_report)
    # ============================================================
    print("4) إضافة Patient ID إلى التقرير (build_report)...")
    content, r = replace_once(
        content,
        '''    return {
        "Timestamp": timestamp,
        "First name": first,''',
        '''    return {
        "Patient ID": patient_id,
        "Timestamp": timestamp,
        "First name": first,''',
        "Patient ID في build_report",
    )
    ok &= r

    # ============================================================
    # 5) إضافة patient_id كمعامل لدالة build_report
    # ============================================================
    print("5) إضافة patient_id كمعامل في build_report...")
    content, r = replace_once(
        content,
        '''def build_report(lang, timestamp, first, last, phone, address, type_key,
                 age, gender, result, probability, symptom_values, extra_values,
                 gender_values=None, freq_key=None, marital_status_key=None,
                 birth_sex=None, glucose=None) -> dict:''',
        '''def build_report(lang, timestamp, first, last, phone, address, type_key,
                 age, gender, result, probability, symptom_values, extra_values,
                 gender_values=None, freq_key=None, marital_status_key=None,
                 birth_sex=None, glucose=None, patient_id="") -> dict:''',
        "معامل patient_id",
    )
    ok &= r

    # ============================================================
    # 6) توليد patient_id عند الضغط على "Predict"
    # ============================================================
    print("6) توليد Patient ID عند التنبؤ...")
    content, r = replace_once(
        content,
        '''            type_key = DIABETES_TYPE_KEYS[[tr(k) for k in DIABETES_TYPE_KEYS].index(diabetes_type)]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            report_args = dict(''',
        '''            type_key = DIABETES_TYPE_KEYS[[tr(k) for k in DIABETES_TYPE_KEYS].index(diabetes_type)]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            # Assign a unique patient ID the first time and reuse it afterwards.
            if not st.session_state.get("current_patient_id"):
                st.session_state["current_patient_id"] = generate_patient_id()
            patient_id = st.session_state["current_patient_id"]

            report_args = dict(''',
        "توليد Patient ID",
    )
    ok &= r

    # ============================================================
    # 7) تمرير patient_id إلى build_report
    # ============================================================
    print("7) تمرير patient_id إلى build_report...")
    content, r = replace_once(
        content,
        '''                birth_sex=sex_at_birth,
                glucose=glucose,
            )''',
        '''                birth_sex=sex_at_birth,
                glucose=glucose,
                patient_id=patient_id,
            )''',
        "تمرير patient_id",
    )
    ok &= r

    # ============================================================
    # 8) عرض Patient ID في بطاقة النتيجة
    # ============================================================
    print("8) عرض Patient ID في بطاقة النتيجة...")
    content, r = replace_once(
        content,
        '''        st.markdown(
            f"""
            <div class="result-card {css_class}">
                <div class="result-label">{tr('result')}</div>''',
        '''        patient_id_display = report.get("Patient ID", "")
        st.markdown(
            f"""
            <div class="result-card {css_class}">
                <div class="result-label">{tr('result')}</div>
                <div style="font-size:.8rem;color:var(--muted);margin-bottom:6px;">
                    Patient ID: <strong>{patient_id_display}</strong>
                </div>''',
        "عرض Patient ID",
    )
    ok &= r

    # ============================================================
    # 9) تنظيف current_patient_id عند logout/restart
    # ============================================================
    print("9) تنظيف current_patient_id عند تسجيل الخروج...")
    content, r = replace_once(
        content,
        '''    st.session_state["lang"] = new_lang if new_lang in LANGUAGES else "en"
    st.session_state["dark_mode"] = keep_dark
    st.session_state["page"] = page''',
        '''    st.session_state["lang"] = new_lang if new_lang in LANGUAGES else "en"
    st.session_state["dark_mode"] = keep_dark
    st.session_state["page"] = page
    st.session_state.pop("current_patient_id", None)''',
        "تنظيف current_patient_id",
    )
    ok &= r

    # ============================================================
    # الحفظ
    # ============================================================
    if not ok:
        print("\n⚠️  بعض التعديلات لم تُطبَّق. لم يتم حفظ الملف.")
        print(f"   الملف الأصلي سليم. النسخة الاحتياطية: {BACKUP_FILE}")
        sys.exit(2)

    write_file(APP_FILE, content)
    print(f"\n✅ تم تطبيق جميع التعديلات بنجاح على {APP_FILE}")
    print(f"   نسخة احتياطية: {BACKUP_FILE}")
    print("\nالخطوة التالية:")
    print("  streamlit run diabetes_app.py")


if __name__ == "__main__":
    main()