"""
fix_admin_layout.py
===================
يحسّن تنسيق قسمي Password Reset و Audit Log في لوحة الأدمن.
"""

import os
import shutil
import sys
from datetime import datetime

APP_FILE = "diabetes_app.py"
BACKUP_FILE = f"app_backup_layout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"


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
        print(f"   X [{label}] found {n} times")
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
    # 1) Improve Password Reset layout
    # ============================================================
    print("1) Improve Password Reset layout...")
    content, r = replace_once(
        content,
        '''        # ============================================================
        # Password Reset Section (English)
        # ============================================================
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
                        f"**Temporary password**: `{temp}`\\n\\n"
                        "Send this to the patient. They will be forced to change it at next login."
                    )
                    st.warning("Save this password NOW - it will not be shown again!")
                except Exception as exc:
                    st.error(f"Failed: {exc}")

        st.markdown("---")''',
        '''        # ============================================================
        # Password Reset Section (English)
        # ============================================================
        with st.container(border=True):
            st.markdown("#### 🔑 Password Reset")

            user_emails = [r["email"] for r in rows]
            user_labels = [f'{r["first_name"]} {r["last_name"]} ({r["email"]})' for r in rows]

            col_select, col_btn = st.columns([4, 1])

            with col_select:
                selected_label = st.selectbox(
                    "Select patient",
                    options=[""] + user_labels,
                    index=0,
                    key="reset_pw_select",
                )

            with col_btn:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                reset_clicked = st.button(
                    "Reset",
                    key="reset_pw_btn",
                    use_container_width=True,
                    type="primary",
                )

            if reset_clicked and selected_label:
                idx = user_labels.index(selected_label)
                selected_email = user_emails[idx]

                try:
                    temp = reset_user_password(selected_email)
                    st.success("Password reset successful")
                    st.info(
                        f"**Temporary password**: `{temp}`\\n\\n"
                        "Send this to the patient. They will be forced to change it at next login."
                    )
                    st.warning("Save this password NOW - it will not be shown again!")
                except Exception as exc:
                    st.error(f"Failed: {exc}")''',
        "Password Reset layout",
    )
    ok &= r

    # ============================================================
    # 2) Improve Audit Log layout
    # ============================================================
    print("2) Improve Audit Log layout...")
    content, r = replace_once(
        content,
        '''    # ============================================================
    # Audit Log Section (English)
    # ============================================================
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
        '''    # ============================================================
    # Audit Log Section (English)
    # ============================================================
    with st.container(border=True):
        st.markdown("#### 📋 Audit Log")

        if os.path.exists(AUDIT_LOG_FILE):
            try:
                log_df = pd.read_excel(AUDIT_LOG_FILE, engine="openpyxl")
                log_df = log_df.sort_values("Timestamp", ascending=False)

                col_filter, col_export = st.columns([4, 1])

                with col_filter:
                    action_filter = st.selectbox(
                        "Filter by action",
                        ["All"] + sorted(log_df["Action"].unique().tolist()),
                        key="audit_filter",
                    )

                with col_export:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    with open(AUDIT_LOG_FILE, "rb") as f:
                        st.download_button(
                            "⬇️ Export",
                            data=f.read(),
                            file_name=AUDIT_LOG_FILE,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_audit",
                            use_container_width=True,
                        )

                if action_filter != "All":
                    log_df = log_df[log_df["Action"] == action_filter]

                st.dataframe(log_df, use_container_width=True, hide_index=True)
                st.caption(f"Total records: {len(log_df)}")
            except Exception as exc:
                st.warning(f"Could not read log: {exc}")
        else:
            st.info("No audit records yet.")''',
        "Audit Log layout",
    )
    ok &= r

    if not ok:
        print("\nX Some patches failed. File NOT saved.")
        print(f"   Backup: {BACKUP_FILE}")
        sys.exit(2)

    write_file(APP_FILE, content)
    print(f"\nOK Layout improved in {APP_FILE}")
    print(f"   Backup: {BACKUP_FILE}")
    print("\nNext: streamlit run diabetes_app.py")


if __name__ == "__main__":
    main()