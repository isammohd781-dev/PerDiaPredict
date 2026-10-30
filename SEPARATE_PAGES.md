# Separate pages — PerdiaPredict

This version is built on the attached PerdiaPredict-improved.zip and keeps its field styling, translations and medical logic. Role pages are separated into independent files and applications, not switched by a parameter in the link.

| Page | Page file | Windows launcher | Local link |
|---|---|---|---|
| Patient | patient.py | START_PATIENT.bat | http://127.0.0.1:8501/ |
| Doctor | doctor.py | START_DOCTOR.bat | http://127.0.0.1:8502/ |
| Administration | admin.py | START_ADMIN.bat | http://127.0.0.1:8503/ |

## Running

1. Stop the old version and any old server using ports 8501–8503.
2. Extract the file into a new folder and open the project folder.
3. Double-click START_ALL.bat to run all three. The patient app opens automatically; open the doctor and admin apps from the links above.
4. To run one page only, use its own START file. Do not run START_ALL and then separate launchers on the same ports.
5. Keep the launcher window open. Ctrl+C stops the processes that launcher started.

The launcher looks for Python 3.12, then 3.11, then 3.13. The first time, it creates .venv and installs requirements.txt, which needs internet. After that it reuses the environment and only reinstalls when the requirements change. If your old environment uses an unsupported version, rename .venv to .venv_backup; do not delete data files.

From PowerShell inside the project folder, using the Python version you have:

```powershell
py -3.11 launch.py all
```

Or choose one page:

```powershell
py -3.11 launch.py patient
py -3.11 launch.py doctor
py -3.11 launch.py admin
```

These three commands are alternatives for running each page on its own, not commands to run one after another in the same window. You can also run manually with `python -m streamlit run patient.py --server.port=8501`, and likewise doctor.py on 8502 and admin.py on 8503, from an environment where the libraries are installed.

## Separation and links between apps

- The patient does not see doctor registration or admin links. They only have their account, assessments, reports and care team.
- The doctor has separate registration and sign-in, and sees patients who consented to follow-up after admin approval and acceptance. The doctor app has no admin page or patient account.
- Administration has its own sign-in and no public admin registration. Set ADMIN_PASSWORD in `.streamlit/secrets.toml` or PERDIA_ADMIN_PASSWORD in the server settings. There is no default password.
- Signing in to one app grants no access in the other two. Old parameters such as `?portal=admin` do not change the app or the role; use the correct port.
- Databases and files are shared within the same project folder. Doctor approval, follow-up requests and notes appear in the other apps when the page is reopened or refreshed. There are no live push notifications.
- Restricted medical content for administration remains subject to the separate disclosure permissions in your version.

## Moving your data

Do not create three copies of the project folder; keep the three files inside the same project so they read the same data stores. Before moving, stop the programs and take a full backup. Copy your current data files to the same locations in the new folder, such as accounts.xlsx, patient_history.db, care_team.db, saved_reports.xlsx, audit_log.xlsx and perdiapredict.db if present, and copy your private settings securely. This package contains no user accounts or records.

Do not copy data from another release into this version at random. If you use a private_data folder or documents.db from a different version, keep it with its original version, because this version has its own format and paths. Nothing is deleted or migrated automatically for stores that were not in the uploaded file.

diabetes_app.py contains the shared logic and medical interface to avoid duplicated code. patient.py, doctor.py and admin.py contain each app's page routing. Running diabetes_app.py directly remains a legacy entry for the patient only, not a way to open the three roles.

The links are local to the computer. Public deployment or phone access from outside the computer needs hosting and HTTPS setup; the project was not deployed as part of this change.
