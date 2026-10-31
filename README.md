# PerdiaPredict

Educational diabetes risk screening built with Streamlit. Three separate apps share one data folder:

| App | Port | Start on Windows |
|---|---|---|
| Patient | 8501 | `START_ALL.bat` (all three) or `scripts/START_PATIENT.bat` |
| Doctor | 8502 | `scripts/START_DOCTOR.bat` |
| Administration | 8503 | `scripts/START_ADMIN.bat` |

Or from a terminal: `python launch.py all` (Python 3.11–3.13). The first run creates `.venv` and installs `requirements.txt`.

This is not a medical device. It does not diagnose diabetes and is not clinically validated.

## Project layout

```
patient.py, doctor.py, admin.py   entry point of each app
diabetes_app.py                   shared app logic and screens
*.py (other)                      features: accounts, doctor portal, policies, reports, theme, translations
model/                            trained model, metadata, training data and train_model.py
fonts/  logo.png                  report fonts (with licences) and the logo
.streamlit/                       config.toml and *.example.toml settings templates
tests/                            automated checks (run tests/run_checks.py)
docs/                             setup, security, store readiness, model evaluation and change log
scripts/                          one-app Windows launchers
deploy/  Dockerfile               nginx HTTPS template and container build
```

## Admin password

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and set `ADMIN_PASSWORD` to your own private password. Admin access stays disabled until it is set; there is no default password. On a server, use the `PERDIA_ADMIN_PASSWORD` environment variable instead. Restricted report access (`DISCLOSURE_PASSWORD`, at least 16 characters) is optional; see `docs/SECURITY_SETUP.md` and `docs/GROUP_ACCESS_SETUP.md`. The other templates (`disclosure_secrets.example.toml`, `policy_settings.example.toml`) are in `.streamlit/` too.

Secrets and all runtime data (accounts, reports, databases, photos) are created locally and excluded by `.gitignore`. No accounts or records are included.

## First use

Register a patient. Register a doctor, approve them in Admin → Doctors, then sign in as the doctor and copy their follow-up code. The patient enters the code, connects, gives consent and sends the request; the doctor accepts it.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python tests/run_checks.py
```

Tests use temporary synthetic accounts. `tests/test_inference.py` also checks the bundled model against the held-out predictions in `model/`.

## More

- `docs/START_HERE.md` and `docs/SEPARATE_PAGES.md`: installation, ports, moving data
- `docs/STORE_READINESS.md`: App Store / Google Play checklist (account deletion link: `?account=delete`)
- `docs/MODEL_EVALUATION.md`: how the model was trained and tested
- `docs/TEN_LANGUAGE_STATUS.md`: translation coverage
- `docs/CHANGES.md`: change log
