"""
gender_patch.py — Simplified gender patch (v2).

- Gender: Male / Female / Other
- "Other" gets general questions.
- Age, Gender, Marital status locked on the main page.

NOTE: The GENDER_OPTIONS block was already edited manually, so this script
skips step 1 and starts from gender_label.
"""

import os
import shutil
import sys
from datetime import datetime

APP_FILE = "diabetes_app.py"
BACKUP_FILE = f"app_backup_simple_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def replace_once(content, old, new, label):
    n = content.count(old)
    if n == 0:
        print(f"   X [{label}] not found")
        return content, False
    if n > 1:
        print(f"   X [{label}] found {n} times (must be 1)")
        return content, False
    print(f"   OK [{label}]")
    return content.replace(old, new, 1), True


def main():
    if not os.path.exists(APP_FILE):
        print(f"X {APP_FILE} not found")
        sys.exit(1)

    shutil.copy2(APP_FILE, BACKUP_FILE)
    print(f"OK Backup: {BACKUP_FILE}\n")

    content = read_file(APP_FILE)
    ok = True

    # ============================================================
    # 1) gender_label (skip gender options — done manually)
    # ============================================================
    print("1) Simplify gender_label...")
    content, r = replace_once(
        content,
        '''def gender_label(value: str, lang: str = None) -> str:
    """Display text for sex-at-birth or gender-identity value (respectful terms)."""
    mapping = {
        "Male": "male",
        "Female": "female",
        "Intersex": "intersex",
        "Unknown": "unknown",
        "Non-binary": "non_binary",
        "Genderqueer": "genderqueer",
        "Another gender category": "another_gender",
        "Prefer not to disclose": "prefer_not_disclose",
    }
    return tr(mapping.get(value, "male"), lang)''',
        '''def gender_label(value: str, lang: str = None) -> str:
    """Display text for a gender value (Male / Female / Other)."""
    mapping = {
        "Male": "male",
        "Female": "female",
        "Other": "other_gender",
    }
    return tr(mapping.get(value, "male"), lang)''',
        "gender_label",
    )
    ok &= r

    # ============================================================
    # 2) Translations for Other
    # ============================================================
    print("2) Add translations for Other...")

    content, r = replace_once(
        content,
        '        "transgender": "Transgender",',
        '''        "transgender": "Transgender",
        "other_gender": "Other",
        "other_section": "General questions",
        "other_section_help": "These are general questions for patients who prefer not to specify male or female. They do not change the estimated probability.",
        "other_fatigue": "Constant fatigue or tiredness",
        "other_vision": "Blurred or unclear vision",
        "other_thirst": "Excessive thirst",
        "other_weight": "Unexplained weight change",
        "other_healing": "Slow healing of wounds",
        "other_infections": "Frequent infections",''',
        "EN other",
    )
    ok &= r

    content, r = replace_once(
        content,
        '        "transgender": "عابر جنسيًا (Transgender)",',
        '''        "transgender": "عابر جنسيًا (Transgender)",
        "other_gender": "آخر",
        "other_section": "أسئلة عامة",
        "other_section_help": "هذه أسئلة عامة للمرضى الذين لا يرغبون في تحديد ذكر أو أنثى. لا تغيّر نسبة الاحتمال المقدَّرة.",
        "other_fatigue": "إرهاق أو تعب مستمر",
        "other_vision": "تشوش أو ضعف في الرؤية",
        "other_thirst": "عطش شديد",
        "other_weight": "تغير غير مبرر في الوزن",
        "other_healing": "بطء في التئام الجروح",
        "other_infections": "التهابات متكررة",''',
        "AR other",
    )
    ok &= r

    content, r = replace_once(
        content,
        '        "transgender": "Transgénero",',
        '''        "transgender": "Transgénero",
        "other_gender": "Otro",
        "other_section": "Preguntas generales",
        "other_section_help": "Preguntas generales para pacientes que prefieren no especificar hombre o mujer. No modifican la probabilidad estimada.",
        "other_fatigue": "Fatiga o cansancio constante",
        "other_vision": "Visión borrosa o poco clara",
        "other_thirst": "Sed excesiva",
        "other_weight": "Cambio de peso sin explicación",
        "other_healing": "Curación lenta de heridas",
        "other_infections": "Infecciones frecuentes",''',
        "ES other",
    )
    ok &= r

    # ============================================================
    # 3) ACCOUNT_FIELDS — single "gender"
    # ============================================================
    print("3) Update ACCOUNT_FIELDS...")
    content, r = replace_once(
        content,
        '''ACCOUNT_FIELDS = [
    "id", "first_name", "last_name", "email", "birth_date",
    "sex_at_birth", "gender_identity", "marital_status",
    "password_hash", "created_at", "last_login", "failed_attempts", "locked_until",
]
ACCOUNT_HEADERS = [
    "ID", "First name", "Last name", "Email", "Birth date",
    "Sex at Birth", "Gender Identity", "Marital status",
    "Password hash", "Created at", "Last login", "Failed attempts", "Locked until",
]''',
        '''ACCOUNT_FIELDS = [
    "id", "first_name", "last_name", "email", "birth_date",
    "gender", "marital_status",
    "password_hash", "created_at", "last_login", "failed_attempts", "locked_until",
]
ACCOUNT_HEADERS = [
    "ID", "First name", "Last name", "Email", "Birth date",
    "Gender", "Marital status",
    "Password hash", "Created at", "Last login", "Failed attempts", "Locked until",
]''',
        "ACCOUNT_FIELDS",
    )
    ok &= r

    # ============================================================
    # 4) _rows_from_sheet
    # ============================================================
    print("4) Update _rows_from_sheet...")
    content, r = replace_once(
        content,
        '''            "birth_date": get(raw, "birth_date"),
            "sex_at_birth": get(raw, "sex_at_birth"),
            "gender_identity": get(raw, "gender_identity"),
            "marital_status": get(raw, "marital_status"),
            "password_hash": pw_hash,''',
        '''            "birth_date": get(raw, "birth_date"),
            "gender": get(raw, "gender"),
            "marital_status": get(raw, "marital_status"),
            "password_hash": pw_hash,''',
        "_rows_from_sheet",
    )
    ok &= r

    # ============================================================
    # 5) _save_rows widths
    # ============================================================
    print("5) Update column widths...")
    content, r = replace_once(
        content,
        "widths = [7, 16, 16, 32, 13, 14, 22, 16, 60, 20, 20, 15, 20]",
        "widths = [7, 16, 16, 32, 13, 10, 16, 60, 20, 20, 15, 20]",
        "column widths",
    )
    ok &= r

    # ============================================================
    # 6) _import_old_sqlite
    # ============================================================
    print("6) Update _import_old_sqlite...")
    content, r = replace_once(
        content,
        '''            "birth_date": r["birth_date"] or "",
            "sex_at_birth": "",
            "gender_identity": "",
            "marital_status": "",
            "password_hash": r["password_hash"] or "",''',
        '''            "birth_date": r["birth_date"] or "",
            "gender": "",
            "marital_status": "",
            "password_hash": r["password_hash"] or "",''',
        "_import_old_sqlite",
    )
    ok &= r

    # ============================================================
    # 7) create_user signature + body
    # ============================================================
    print("7) Update create_user...")
    content, r = replace_once(
        content,
        '''def create_user(first_name: str, last_name: str, email: str, birth_date: date,
                password: str, sex_at_birth: str, gender_identity: str,
                marital_status: str = "single"):''',
        '''def create_user(first_name: str, last_name: str, email: str, birth_date: date,
                password: str, gender: str, marital_status: str = "single"):''',
        "create_user signature",
    )
    ok &= r

    content, r = replace_once(
        content,
        '''                "birth_date": birth_date.isoformat(),
                "sex_at_birth": sex_at_birth,
                "gender_identity": gender_identity,
                "marital_status": marital_status,
                "password_hash": password_hash,''',
        '''                "birth_date": birth_date.isoformat(),
                "gender": gender,
                "marital_status": marital_status,
                "password_hash": password_hash,''',
        "create_user body",
    )
    ok &= r

    # ============================================================
    # 8) authenticate
    # ============================================================
    print("8) Update authenticate...")
    content, r = replace_once(
        content,
        '''            "birth_date": row["birth_date"],
            "sex_at_birth": row.get("sex_at_birth", ""),
            "gender_identity": row.get("gender_identity", ""),
            "marital_status": row.get("marital_status", "single"),
        }, "ok"''',
        '''            "birth_date": row["birth_date"],
            "gender": row.get("gender", "Male"),
            "marital_status": row.get("marital_status", "single"),
        }, "ok"''',
        "authenticate",
    )
    ok &= r

    # ============================================================
    # 9) Admin table
    # ============================================================
    print("9) Update admin table...")
    content, r = replace_once(
        content,
        '''                "Email": r["email"], "Birth date": r["birth_date"],
                "Sex at Birth": r.get("sex_at_birth", ""),
                "Gender Identity": r.get("gender_identity", ""),
                "Marital status": r.get("marital_status", ""),
                "Created at": r["created_at"], "Last login": r["last_login"],''',
        '''                "Email": r["email"], "Birth date": r["birth_date"],
                "Gender": r.get("gender", ""),
                "Marital status": r.get("marital_status", ""),
                "Created at": r["created_at"], "Last login": r["last_login"],''',
        "admin table",
    )
    ok &= r

    # ============================================================
    # 10) Register page
    # ============================================================
    print("10) Update register page...")
    content, r = replace_once(
        content,
        '''            sex_at_birth_reg = st.selectbox(
                f"{tr('sex_at_birth')} *",
                SEX_AT_BIRTH_OPTIONS,
                format_func=gender_label,
                key="reg_sex_at_birth",
                help=tr("sex_at_birth_help"),
            )
            gender_identity_reg = st.selectbox(
                f"{tr('gender_identity')} *",
                GENDER_IDENTITY_OPTIONS,
                format_func=gender_label,
                key="reg_gender_identity",
                help=tr("gender_identity_help"),
            )
            marital_status_reg = st.selectbox(
                f"{tr('marital_status')} *",
                MARITAL_STATUS_ORDER,
                format_func=lambda k: marital_status_label(k, sex_at_birth_reg),
                key="reg_marital",
            )''',
        '''            gender_reg = st.selectbox(
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
            )''',
        "register gender field",
    )
    ok &= r

    content, r = replace_once(
        content,
        '''            if not (clean_first and clean_last and clean_email and dob_chosen
                    and password and password2 and sex_at_birth_reg
                    and gender_identity_reg and marital_status_reg):
                errors.append(tr("reg_fill_all"))''',
        '''            if not (clean_first and clean_last and clean_email and dob_chosen
                    and password and password2 and gender_reg and marital_status_reg):
                errors.append(tr("reg_fill_all"))''',
        "register validation",
    )
    ok &= r

    content, r = replace_once(
        content,
        '''                ok, error_key = create_user(
                    clean_first, clean_last, clean_email, birth, password,
                    sex_at_birth_reg, gender_identity_reg, marital_status_reg
                )''',
        '''                ok, error_key = create_user(
                    clean_first, clean_last, clean_email, birth, password,
                    gender_reg, marital_status_reg
                )''',
        "register create_user call",
    )
    ok &= r

    # ============================================================
    # 11) Main page gender field
    # ============================================================
    print("11) Update main page gender field...")
    content, r = replace_once(
        content,
        '''        with c6:
            # Sex at Birth and Gender Identity come from the account.
            sex_at_birth = _user.get("sex_at_birth", "") or "Male"
            gender_identity = _user.get("gender_identity", "") or "Male"

            st.text_input(
                tr("sex_at_birth"),
                value=gender_label(sex_at_birth),
                disabled=True,
                key="basic_sex_at_birth_locked",
            )
            st.text_input(
                tr("gender_identity"),
                value=gender_label(gender_identity),
                disabled=True,
                key="basic_gender_identity_locked",
            )
            if sex_at_birth not in ("Male", "Female"):
                sex_at_birth = "Male"''',
        '''        with c6:
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
            sex_at_birth = gender if gender in ("Male", "Female") else "Male"''',
        "main page gender field",
    )
    ok &= r

    # ============================================================
    # 12) Gender question section
    # ============================================================
    print("12) Update gender question section...")
    content, r = replace_once(
        content,
        '''        gender_values = {}
        if is_child:
            gender_keys = child_question_keys(sex_at_birth)
            gender_title = tr("child_section")
            key_kind = f"child_{sex_at_birth}"
        elif gender_identity in ("Non-binary", "Genderqueer", "Another gender category"):
            gender_keys = list(TRANS_SYMPTOM_KEYS)
            gender_title = tr("trans_section")
            key_kind = "trans"
        else:
            gender_keys = gender_question_keys(sex_at_birth, ever_married)
            gender_title = tr("male_section" if sex_at_birth == "Male" else "female_section")
            key_kind = f"adult_{sex_at_birth}"''',
        '''        gender_values = {}
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
            key_kind = f"adult_{gender}"''',
        "gender question section",
    )
    ok &= r

    content, r = replace_once(
        content,
        '''        st.markdown(f'<div class="section-title">{gender_title}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-subtitle">{tr("gender_section_help")}</div>', unsafe_allow_html=True)''',
        '''        st.markdown(f'<div class="section-title">{gender_title}</div>', unsafe_allow_html=True)
        help_key = "other_section_help" if gender == "Other" and not is_child else "gender_section_help"
        st.markdown(f'<div class="section-subtitle">{tr(help_key)}</div>', unsafe_allow_html=True)''',
        "gender section help",
    )
    ok &= r

    # ============================================================
    # 13) Cleanup
    # ============================================================
    print("13) Clean up old keys...")
    content, r = replace_once(
        content,
        '''    st.session_state["page"] = page
    st.session_state.pop("current_patient_id", None)''',
        '''    st.session_state["page"] = page
    st.session_state.pop("current_patient_id", None)
    st.session_state.pop("basic_gender", None)''',
        "restart cleanup",
    )
    ok &= r

    # ============================================================
    # Done
    # ============================================================
    if not ok:
        print("\nX Some patches failed. File NOT saved.")
        print(f"   Backup: {BACKUP_FILE}")
        sys.exit(2)

    write_file(APP_FILE, content)
    print(f"\nOK All patches applied to {APP_FILE}")
    print(f"   Backup: {BACKUP_FILE}")
    print("\nNext:")
    print("  1. del accounts.xlsx")
    print("  2. streamlit run diabetes_app.py")


if __name__ == "__main__":
    main()