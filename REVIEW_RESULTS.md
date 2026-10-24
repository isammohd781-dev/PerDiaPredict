# Review results, 2026-10-01

Passed all ten check scripts with no uncaught app execution errors on the final run. The real bundled model passes held-out parity and unsupported-input checks. A separate clean-copy smoke test loads the real model, renders registration in all ten languages, and checks the main, history, care, admin and auth pages. A generated medical PDF was rendered and inspected with the supplied app logo.

Changes: complete runtime dependency list; safe Docker/Dev Container configuration; application-relative asset/data paths; fail-closed unconfigured admin access; corrected current-flow tests and test temporary-directory lifetime; removal of unused PDF font downloader; original trained model preserved byte-for-byte; original app logo preserved byte-for-byte; no saved runtime patient or doctor data, private secrets or approved permits.

Known limits: some workflow/policy translations are unfinished; no clinical validation or production security certification was performed; data is not encrypted at rest. See README.md and TEN_LANGUAGE_STATUS.md.

Removed files:

- .streamlit/secrets.toml
- Dockerfile.txt
- Early_Stage_Diabetes_Prediction.ipynb
- INSTALL.txt
- LOGO_SETUP.md
- MODERN_ENTRY_SETUP.md
- POLICY_STYLE_SETUP.md
- PerdiaPredict_Concise_EN.pptx
- README.txt
- RESTORE_ENTRY.md
- SENTENCE_FRAMES_SETUP.md
- VISUAL_LANGUAGE_SETUP.md
- __pycache__/admin_dashboard.cpython-313.pyc
- __pycache__/app_experience.cpython-313.pyc
- __pycache__/app_policies.cpython-313.pyc
- __pycache__/auth_design.cpython-313.pyc
- __pycache__/disclosure_access.cpython-313.pyc
- __pycache__/doctor_portal.cpython-313.pyc
- __pycache__/report_branding.cpython-313.pyc
- __pycache__/report_locale.cpython-313.pyc
- __pycache__/screening_model.cpython-313.pyc
- __pycache__/translations.cpython-313.pyc
- __pycache__/visual_accessibility.cpython-313.pyc
- accounts.xlsx
- age_scaler.pkl
- audit_log.xlsx
- auth_design.py
- care_team.db
- fonts/NotoSans-Bold.ttf
- fonts/NotoSans-Regular.ttf
- fonts/NotoSansArabic-Bold.ttf
- fonts/NotoSansArabic-Regular.ttf
- fonts/NotoSansDevanagari-Bold.ttf
- fonts/NotoSansSC-Bold.otf
- fonts/NotoSansSC-Regular.otf
- gender_patch.py
- patient_history.db
- reliability.png
- requirements_additions.txt
- requirements_pdf.txt
- result.txt
- saved_reports.xlsx
