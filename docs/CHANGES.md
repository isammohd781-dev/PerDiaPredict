# Render deployment — 2026-10-31
- One Docker service runs the patient (/), doctor (/doctor/) and admin (/admin/) apps behind nginx, so all three share the same data. Files: render.yaml, Dockerfile, deploy/render-start.sh, deploy/nginx-render.conf; guide in docs/DEPLOY_RENDER.md.
- New setting PERDIA_DATA_DIR: runtime data (accounts, reports, databases, photos) can live on a persistent disk. Locally it still defaults to the project folder.
- render.yaml is set to the free plan for testing (no disk, data is lost on restart). The disk block is ready to enable on a paid plan.

# Tidier project layout — 2026-10-31
- Fewer files at the top level: documentation moved to docs/, tests to tests/, the model and its data to model/, the one-app launchers to scripts/, and the two extra settings templates to .streamlit/. START_ALL.bat, README.md and the app code stay at the top.
- Paths updated in the app, launchers and tests. Run tests with `python tests/run_checks.py`. Docker images exclude tests, docs and scripts.

# Account deletion, store requirements and field buttons — 2026-10-30

## Account deletion
- New "Your data and account" section at the bottom of Edit profile, with "Download my data" and "Delete account".
- The deletion page lists what is deleted and what is kept, and asks for the password and a confirmation tick. The delete button is red.
- Deletion removes every record of the patient from every store, replaces the email in security logs with an anonymous reference, and never reuses the patient ID.
- Public deletion link without sign-in (for Google Play): `?account=delete`.
- Details and the remaining launch checklist are in STORE_READINESS.md.

## Field buttons
- Password show/hide button: a centred 36px square inside the field.
- Glucose field − / + buttons: two equal buttons at full field height with a divider.
- Hidden Streamlit's "Press Enter to apply" hint, which overlapped the text and the eye button.
- Select arrows and the (?) help icon sit on the same line as the text.
- A button placed in a row beside a field now matches the field height (48px).
- The photo picker button is centred in the upload area.
- "Back" and any other button that is the first element on a page was half hidden under Streamlit's 60px top bar. Every page now starts below the bar, on desktop and mobile.

## Dialogs in dark mode
- Confirmation dialogs (Review screening answers, Log out, profile changes, doctor access) showed dark text on a dark panel and a white Cancel button. Streamlit renders dialogs outside the page container, so the stylesheet did not reach them. All text, button, field and notice styles now apply inside dialogs in both light and dark mode.

## Logo screen
- The app opens in dark mode by default. Light mode is used only when the person switches to it (the choice is kept in the link as ?theme=light).
- The logo screen has a loading bar and a modern background: slowly moving soft colour, a fine dot grid, a glucose curve that draws itself, and floating glass tiles with diabetes care icons (blood drop, glucose meter, insulin pen, tablet, test strip, capsule), all original vector art in splash_art.py. It lasts 2 seconds (SPLASH_SECONDS in diabetes_app.py).
- Optional photo background: put a photo named splash_background.jpg (or .jpeg / .png / .webp) in the project folder. It fills the logo screen, slightly blurred and shaded so the text stays readable, and is resized automatically. Without the file, the vector design is used. Use only a photo you own or have a licence for.
- The PerdiaPredict logo screen now appears before the sign-in page of all three apps (patient, doctor, admin password), once per visit, and again after the language is changed. It then goes straight to that app's sign-in page. Sign-out, the 15-minute timeout and direct links (policy pages, account deletion) do not show it again.

## Sessions and sign-in fields
- Every signed-in session (patient, doctor and admin) ends exactly 15 minutes after sign-in, even while the person is active. A browser timer signs out on screen at that moment without a click, and the server enforces the same limit on any later request. This replaces the previous 30-minute inactivity rule. Change SESSION_MINUTES in portal_runtime.py to adjust.
- The browser Back button never returns to a signed-in page. While signed in, Back ends the session and opens the sign-in page (patient, doctor) or the admin password page; language and theme are kept. Pages restored from the browser's back/forward cache are reloaded the same way.
- Sign-in fields (patient, doctor, admin, account deletion) ask the browser not to autofill, and are cleared after every attempt.
- New test_session_expiry.py (added to tests/run_checks.py).

## Admin setup
- When the admin password is missing, the admin page now says if the settings file was saved as secrets.toml.toml / secrets.toml.txt (Windows hides extensions), or if secrets.toml exists but ADMIN_PASSWORD is empty.

## Launcher
- launch.py detects a .venv without pip (left by an interrupted first run), repairs it, or rebuilds the environment. Data files are never touched.

## Tests
- New test_account_deletion.py (added to tests/run_checks.py); it passed together with test_registration.py and test_doctor_portal.py.
- UI tests need Streamlit, which could not be installed in the review environment. Run `python tests/run_checks.py` locally.

---

# New design and security — 2026-10-24

## Look
- One stylesheet, `theme.py`, replaces seven conflicting CSS layers.
- Direction: a clinic intake form and a lab result slip. Calm grey page, white panels with a hairline border; no gradients, glows, shadows or moving particles.
- Removed "AI-generated" signs: the "AI-powered" phrase in ten languages, all-caps headings, emoji such as ⚠️ ✅, "·" separators, button lift animation, and the long splash screen (5.2 s down to 1.2 s).
- Colours: dark medical green #0F6B5C for primary buttons, red for high risk, green for low risk, amber for warnings, light blue for information. Matching dark mode.
- Buttons: primary (filled), secondary (outlined) and text-style for links such as "Back". 44px high, 8px corners.
- Fields: 48px high, 6px between label and field, 16px between fields, about 32px between sections.
- Sign in and registration: one centred panel instead of the split screen and illustrations.
- Result: a lab-slip card showing the percentage and a bar marking its position against the decision threshold.
- Date of birth: one row (day / month / year) without repeated labels, also on phones.
- Arabic: numbers, phone numbers and dates display in the correct direction.

## Security
- Admin panel locks for 10 minutes after 5 wrong attempts (across all sessions; a new window does not bypass it).
- Automatic sign-out after 30 minutes without activity.
- Excel formula injection blocked (a note starting with = does not become a formula when opened), and writes are atomic so an interruption cannot corrupt the file.
- Sign-in response time does not reveal whether an email exists (patient and doctor).
- Error messages do not show file paths or internal details.
- Docker runs as a non-root user, and .gitignore excludes all secret files.
- nginx template in deploy/ adds HTTPS and security headers (CSP, HSTS, X-Frame-Options).

## Console and data protection (.streamlit/config.toml)
- showErrorDetails = none: no technical errors or paths shown in the browser.
- toolbarMode = viewer: hides the Deploy button and developer menu.
- gatherUsageStats = false: nothing is sent to Streamlit.
- magicEnabled = false: no variable is displayed on the page by mistake.
- logger level = error: the terminal shows errors only, and the app does not print patient data.

## Needs your decision
- Data is stored unencrypted on disk (xlsx and db). For real deployment: disk encryption or an encrypted database.
- Dependency vulnerability scan (pip-audit) was not run in the review environment (no internet). Run it locally: `pip install pip-audit` then `pip-audit -r requirements.txt`.
- Policy pages exist but must be reviewed by a lawyer before launch.

---

# Field and spacing improvements — 2026-10-21

## Spacing (one scale for every page)
- Uniform 48px height for all fields: text, number and select (previously 40 / 46 / 48 / 50 depending on the page).
- 1rem (16px) between fields in every form and card (previously 0.8 / 0.85 / 0.9 / 14px, conflicting).
- 6px between a field label and its field; label line height 1.4 instead of 1.65.
- Line height 1.55 for captions and checkboxes, 1.6 inside the notes box.
- Subtitles and captions stay attached to their section heading instead of a full gap away.
- Registration sections (01, 02, 03, 04) are separated more clearly from the fields inside them.
- Privacy card, notices and report fields: proportional padding instead of a fixed 22px.
- No colour, font or corner radius was changed.

## Fields
- Screening questions are rows of two questions aligned at the bottom, so fields do not shift when a question label wraps to two lines.
- Helpful placeholders instead of repeating the field name, in ten languages.
- Autocomplete for email, password, name and phone.
- The hospital field in registration is optional and empty instead of pre-filled with "Not assigned", and moved after the phone number.
- Edit profile: one country field that carries its calling code (country and code could previously disagree); the phone is validated with the same rules as registration.
- The admin password field now has a visible label.
- Navigation, doctor and confirmation-dialog buttons are translated.

## Fixes
- **Security:** removed a default admin password that was hard-coded even though the README said there was none. Admin is now disabled until `ADMIN_PASSWORD` is set.
- The change-password page no longer shows internal error details to the user.
- Removed a duplicate `BASE_DIR` definition and a variable used before it was defined.
