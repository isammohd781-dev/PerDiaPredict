"""
apply_audit_patch.py
====================
يطبّق باقي تعديلات Audit Log + Password Reset على diabetes_app.py.

الاستخدام:
    python apply_audit_patch.py
"""

import os
import shutil
import sys
from datetime import datetime

APP_FILE = "diabetes_app.py"
BACKUP_FILE = f"app_backup_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"


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
    # 1) AUDIT_LOG_FILE constant
    # ============================================================
    print("1) Add AUDIT_LOG_FILE constant...")
    content, r = replace_once(
        content,
        'SAVE_FILE_XLSX = "saved_reports.xlsx"\nLOGO_PATH = "logo.png"',
        'SAVE_FILE_XLSX = "saved_reports.xlsx"\nAUDIT_LOG_FILE = "audit_log.xlsx"\nLOGO_PATH = "logo.png"',
        "AUDIT_LOG_FILE",
    )
    ok &= r

    # ============================================================
    # 2) EN translations
    # ============================================================
    print("2) Add EN translations...")
    content, r = replace_once(
        content,
        '        "glucose_level": "Blood sugar / glucose level",',
        '''        "glucose_level": "Blood sugar / glucose level",
        "change_password_title": "Set a new password",
        "change_password_intro": "For security, you must set a new password before continuing.",
        "new_password": "New password",
        "confirm_new_password": "Confirm new password",
        "save_new_password": "Save new password",
        "password_changed": "Password changed successfully!",''',
        "EN translations",
    )
    ok &= r

    # ============================================================
    # 3) AR translations
    # ============================================================
    print("3) Add AR translations...")
    content, r = replace_once(
        content,
        '        "glucose_level": "مستوى السكر / الجلوكوز في الدم",',
        '''        "glucose_level": "مستوى السكر / الجلوكوز في الدم",
        "change_password_title": "تعيين كلمة مرور جديدة",
        "change_password_intro": "لأسباب أمنية، يجب تعيين كلمة مرور جديدة قبل المتابعة.",
        "new_password": "كلمة المرور الجديدة",
        "confirm_new_password": "تأكيد كلمة المرور الجديدة",
        "save_new_password": "حفظ كلمة المرور الجديدة",
        "password_changed": "تم تغيير كلمة المرور بنجاح!",''',
        "AR translations",
    )
    ok &= r

    # ============================================================
    # 4) ES translations
    # ============================================================
    print("4) Add ES translations...")
    content, r = replace_once(
        content,
        '        "glucose_level": "Nivel de azúcar / glucosa en sangre",',
        '''        "glucose_level": "Nivel de azúcar / glucosa en sangre",
        "change_password_title": "Establecer una nueva contraseña",
        "change_password_intro": "Por seguridad, debes establecer una nueva contraseña antes de continuar.",
        "new_password": "Nueva contraseña",
        "confirm_new_password": "Confirmar nueva contraseña",
        "save_new_password": "Guardar nueva contraseña",
        "password_changed": "¡Contraseña cambiada exitosamente!",''',
        "ES translations",
    )
    ok &= r

    # ============================================================
    # 5) ACCOUNT_FIELDS
    # ============================================================
    print("5) Update ACCOUNT_FIELDS...")
    content, r = replace_once(
        content,
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
        '''ACCOUNT_FIELDS = [
    "id", "first_name", "last_name", "email", "birth_date",
    "gender", "marital_status",
    "password_hash", "created_at", "last_login", "failed_attempts", "locked_until",
    "must_change_password",
]
ACCOUNT_HEADERS = [
    "ID", "First name", "Last name", "Email", "Birth date",
    "Gender", "Marital status",
    "Password hash", "Created at", "Last login", "Failed attempts", "Locked until",
    "Must change password",
]''',
        "ACCOUNT_FIELDS + HEADERS",
    )
    ok &= r

    # ============================================================
    # 6) _rows_from_sheet
    # ============================================================
    print("6) Update _rows_from_sheet...")
    content, r = replace_once(
        content,
        '''            "gender": get(raw, "gender"),
            "marital_status": get(raw, "marital_status"),
            "password_hash": pw_hash,
            "created_at": get(raw, "created_at"),''',
        '''            "gender": get(raw, "gender"),
            "marital_status": get(raw, "marital_status"),
            "password_hash": pw_hash,
            "must_change_password": 1 if get(raw, "must_change_password") == "1" else 0,
            "created_at": get(raw, "created_at"),''',
        "_rows_from_sheet",
    )
    ok &= r

    # ============================================================
    # 7) _save_rows widths
    # ============================================================
    print("7) Update _save_rows widths...")
    content, r = replace_once(
        content,
        "    widths = [7, 16, 16, 32, 13, 10, 16, 60, 20, 20, 15, 20]",
        "    widths = [7, 16, 16, 32, 13, 10, 16, 60, 20, 20, 15, 20, 18]",
        "_save_rows widths",
    )
    ok &= r

    # ============================================================
    # 8) create_user — add must_change_password
    # ============================================================
    print("8) Update create_user...")
    content, r = replace_once(
        content,
        '''                "failed_attempts": 0,
                "locked_until": "",
            })
            _save_rows(rows)''',
        '''                "failed_attempts": 0,
                "locked_until": "",
                "must_change_password": 0,
            })
            _save_rows(rows)''',
        "create_user",
    )
    ok &= r

    # ============================================================
    # 9) authenticate — add log + must_change_password
    # ============================================================
    print("9) Update authenticate...")
    content, r = replace_once(
        content,
        '''        _update_account(
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
        }, "ok"''',
        '''        _update_account(
            email, failed_attempts=0, locked_until="",
            last_login=now.isoformat(timespec="seconds"),
        )
        log_action(row["id"], "login", f"email={email}")
        return {
            "id": row["id"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "email": row["email"],
            "birth_date": row["birth_date"],
            "gender": row.get("gender", "Male"),
            "marital_status": row.get("marital_status", "single"),
            "must_change_password": int(row.get("must_change_password", 0)),
        }, "ok"''',
        "authenticate",
    )
    ok &= r

    # ============================================================
    # 10) render_main_app — force password change check
    # ============================================================
    print("10) Update render_main_app...")
    content, r = replace_once(
        content,
        '''def render_main_app():
    lang = st.session_state["lang"]

    _user = st.session_state.get("user") or {}''',
        '''def render_main_app():
    lang = st.session_state["lang"]

    # Force password change if admin reset it
    _check_user = st.session_state.get("user") or {}
    if _check_user.get("must_change_password", 0) == 1:
        render_change_password_page()
        st.stop()

    _user = st.session_state.get("user") or {}''',
        "render_main_app check",
    )
    ok &= r

    # ============================================================
    # 11) render_main_app — log predict
    # ============================================================
    print("11) Log predict action...")
    content, r = replace_once(
        content,
        '''            st.session_state["report_saved"] = False

            components.html(''',
        '''            st.session_state["report_saved"] = False

            log_action(
                _user.get("id", 0),
                "predict",
                f"patient_id={patient_id}, result={result}, prob={probability:.2f}",
            )

            components.html(''',
        "log predict",
    )
    ok &= r

    # ============================================================
    # 12) render_accounts_admin — add reset UI
    # ============================================================
    print("12) Add reset UI to admin...")
    content, r = replace_once(
        content,
        '''        st.dataframe(table, use_container_width=True, hide_index=True)
        with open(ACCOUNTS_FILE, "rb") as f:''',
        '''        st.dataframe(table, use_container_width=True, hide_index=True)

        # ---- Password Reset Section ----
        st.markdown("---")
        st.markdown("### Password Reset")

        user_emails = [r["email"] for r in rows]
        user_labels = [f'{r["first_name"]} {r["last_name"]} ({r["email"]})' for r in rows]

        selected_label = st.selectbox(
            "Select patient",
            options=[""] + user_labels,
            index=0,
            key="reset_pw_select",
        )

        if selected_label:
            idx = user_labels.index(selected_label)
            selected_email = user_emails[idx]

            if st.button("Reset password", key="reset_pw_btn"):
                try:
                    temp = reset_user_password(selected_email)
                    st.success("Password reset successful")
                    st.info(
                        f"Temporary password: `{temp}`\\n\\n"
                        "Send this to the patient. They will be forced to change it."
                    )
                    st.warning("Save this password NOW - it won't be shown again!")
                except Exception as exc:
                    st.error(f"Failed: {exc}")

        st.markdown("---")

        with open(ACCOUNTS_FILE, "rb") as f:''',
        "admin reset UI",
    )
    ok &= r

    # ============================================================
    # 13) render_admin_page — add audit log section
    # ============================================================
    print("13) Add audit log section to admin...")
    content, r = replace_once(
        content,
        '''    st.success(tr("access"))
    render_accounts_admin()''',
        '''    st.success(tr("access"))
    render_accounts_admin()

    # ---- Audit Log Section ----
    st.markdown("---")
    st.markdown("### Audit Log")

    if os.path.exists(AUDIT_LOG_FILE):
        try:
            log_df = pd.read_excel(AUDIT_LOG_FILE, engine="openpyxl")
            log_df = log_df.sort_values("Timestamp", ascending=False)

            col_filter, col_export = st.columns([3, 1])
            with col_filter:
                action_filter = st.selectbox(
                    "Filter by action",
                    ["All"] + sorted(log_df["Action"].unique().tolist()),
                    key="audit_filter",
                )
            with col_export:
                with open(AUDIT_LOG_FILE, "rb") as f:
                    st.download_button(
                        "Export Excel",
                        data=f.read(),
                        file_name=AUDIT_LOG_FILE,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_audit",
                    )

            if action_filter != "All":
                log_df = log_df[log_df["Action"] == action_filter]

            st.dataframe(log_df, use_container_width=True, hide_index=True)
            st.caption(f"Total records: {len(log_df)}")
        except Exception as exc:
            st.warning(f"Could not read log: {exc}")
    else:
        st.info("No audit records yet.")''',
        "audit log section",
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