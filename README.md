# PerdiaPredict
Development Streamlit application for educational diabetes risk screening.

## Local setup
Use Python 3.12 or 3.13. Extract this release into a NEW folder to begin with empty data. Do not merge the old folder or copy its databases, XLSX files, profile photos or secrets into this release.

Windows PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run diabetes_app.py
```
If activation is unavailable, use `.\.venv\Scripts\python.exe` directly for the pip and Streamlit commands.

All runtime records are created automatically as needed. No patient accounts, doctor accounts, reports, consent links, notes, audit events or active disclosure permits are bundled.

## Admin configuration
Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml`. Set ADMIN_PASSWORD to a new private password. Admin access is disabled until a password is configured; there is no built-in admin password. Set DISCLOSURE_PASSWORD independently (at least 16 characters) only when configuring restricted reports/activity access. Keep root settings above permit tables. Read SECURITY_SETUP.md and GROUP_ACCESS_SETUP.md before configuring any permit.
Environment alternatives include PERDIA_ADMIN_PASSWORD and PERDIA_DISCLOSURE_PASSWORD.
Private secrets and runtime data are excluded by the supplied git/Docker ignore rules.

## Starting again
Register a new patient through the application. Register a new doctor, approve the doctor in Admin / Doctors after reviewing the submitted details, then sign in as the doctor. Obtain the doctor's generated follow-up code from their dashboard. A patient enters that code, presses Enter and uses Connect to view the doctor, then gives consent and confirms the follow-up request. The doctor accepts the request to obtain access.
No pre-created demo doctor is included.

## Tests
```powershell
python -m pip install -r requirements-dev.txt
python run_checks.py
```
Tests use temporary synthetic accounts, records and adapters. test_inference.py additionally verifies the actual bundled model against the supplied held-out predictions. Generated test PDFs are placed in tmp/.

## Assets and limitations
Keep the trained model, feature columns, model_metadata.json, logo, fonts and font license files together. Scaling is already inside the model pipeline, so a separate age_scaler.pkl is unnecessary.
Training data, train_model.py, held-out evaluation and MODEL_EVALUATION.md are retained for reproducibility; they are not patient account records entered in this application.
The model supports ages 16 to 85. It is not clinically validated and does not diagnose diabetes. Model probabilities are preserved; an all-No screening is not artificially forced to zero.
Read TEN_LANGUAGE_STATUS.md for actual translation coverage. Some newer workflows and five additional policy-body translations remain incomplete.
App access restrictions do not encrypt files at rest or prevent the code/machine owner from bypassing them. Deployment approvals and production controls remain outside this prototype review.
