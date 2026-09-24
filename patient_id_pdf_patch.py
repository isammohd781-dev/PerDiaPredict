"""
patient_id_pdf_patch.py — v2
============================
يضيف الرقم التعريفي (Patient ID) إلى تقرير PDF.
لا يعتمد على الترجمات — يستخدم "Patient ID" مباشرة.
"""

import os
import shutil
import sys
from datetime import datetime

APP_FILE = "diabetes_app.py"
BACKUP_FILE = f"app_backup_pid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"


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
    # Add "patient_id" key to each language dict in EXTRA_TEXT
    # (using the existing "sex_at_birth" line as anchor, which exists)
    # ============================================================
    print("1) Add 'patient_id_label' translations...")

    # English — anchor on "glucose_level" which exists in every lang block
    content, r = replace_once(
        content,
        '        "glucose_level": "Blood sugar / glucose level",',
        '''        "glucose_level": "Blood sugar / glucose level",
        "patient_id_label": "Patient ID",''',
        "EN patient_id_label",
    )
    ok &= r

    content, r = replace_once(
        content,
        '        "glucose_level": "مستوى السكر / الجلوكوز في الدم",',
        '''        "glucose_level": "مستوى السكر / الجلوكوز في الدم",
        "patient_id_label": "الرقم التعريفي للمريض",''',
        "AR patient_id_label",
    )
    ok &= r

    content, r = replace_once(
        content,
        '        "glucose_level": "Nivel de azúcar / glucosa en sangre",',
        '''        "glucose_level": "Nivel de azúcar / glucosa en sangre",
        "patient_id_label": "ID del paciente",''',
        "ES patient_id_label",
    )
    ok &= r

    # ============================================================
    # Add Patient ID to the PDF patient card
    # ============================================================
    print("2) Add Patient ID to PDF patient card...")

    content, r = replace_once(
        content,
        '''    rows = [
        [(t("pdf_name"), name), (t("pdf_age_gender"), age_gender)],
        [(t("phone"), report_data.get("Phone", "")),
         (t("marital_status"), report_data.get("Marital status", ""))],
        [(t("pdf_address"), report_data.get("Address", "")),
         (t("pdf_type"), report_data.get("Reported diabetes type", ""))],
    ]''',
        '''    patient_id_text = report_data.get("Patient ID", "")
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
    ])''',
        "patient card with ID",
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
    print("  streamlit run diabetes_app.py")


if __name__ == "__main__":
    main()