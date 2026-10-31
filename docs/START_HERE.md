# Running the separate-pages version

Start with START_ALL.bat, or scripts/START_PATIENT.bat, scripts/START_DOCTOR.bat or scripts/START_ADMIN.bat. Instructions and links are in SEPARATE_PAGES.md.

# Running the clean version

1. Extract the project into a new folder. Do not merge it with the old project folder, so its data does not come back.
2. Open the folder in VS Code, then open a Terminal.
3. Use Python 3.12 or 3.13 and install the requirements:

```powershell
python -m pip install -r requirements.txt
```

4. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and put your own new password in `ADMIN_PASSWORD`. Example of the format only:

```toml
ADMIN_PASSWORD = "put-your-own-password-here"
DISCLOSURE_PASSWORD = ""
DISCLOSURE_PERMITS = []
```

Do not upload `secrets.toml` to GitHub. Restricted report access needs a separate password of at least 16 characters and a valid permit; it can stay disabled while testing registration.

5. Run the app:

```powershell
python -m streamlit run diabetes_app.py
```

6. Register the patient and the doctor from scratch. Review and approve the doctor's account in the admin panel. The Connect code is generated inside the doctor's account; this version has no ready-made demo code or account.

Old patient and doctor accounts, reports, activity logs, follow-ups and permits were removed from this version. The program creates new stores when needed. The machine-learning model, research training data, logo and fonts remain; the training data is not user records entered in the app.

Libraries were unified, paths fixed, Docker updated, and duplicate files, unused old code and some unused fonts removed. There is no default admin password.

Some newer phrases and policy pages still need translation; details are in TEN_LANGUAGE_STATUS.md. Technical tests do not mean medical approval or security clearance for launch.
