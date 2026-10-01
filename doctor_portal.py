"""Development care-team portal: approved doctors, patient consent and follow-up."""
import app_experience as ux
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

CARE_DB = os.environ.get("PERDIA_CARE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "care_team.db"))


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def database():
    conn = sqlite3.connect(CARE_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS doctors (
        id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
        phone TEXT NOT NULL, specialty TEXT NOT NULL, license_number TEXT NOT NULL,
        licensing_body TEXT NOT NULL, country TEXT NOT NULL, hospital TEXT NOT NULL,
        city TEXT NOT NULL, password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        invite_code TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, review_note TEXT NOT NULL DEFAULT '',
        reviewed_at TEXT, failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS patient_locations (
        email TEXT PRIMARY KEY, patient_id TEXT NOT NULL, name TEXT NOT NULL,
        country TEXT NOT NULL, hospital TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS care_links (
        doctor_id TEXT NOT NULL REFERENCES doctors(id), patient_email TEXT NOT NULL,
        status TEXT NOT NULL, requested_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        consent_text TEXT NOT NULL, PRIMARY KEY(doctor_id,patient_email)
    );
    CREATE TABLE IF NOT EXISTS care_notes (
        id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL REFERENCES doctors(id),
        patient_email TEXT NOT NULL, assessment_id TEXT NOT NULL, text TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS doctor_work_locations (
        doctor_id TEXT PRIMARY KEY REFERENCES doctors(id), country TEXT NOT NULL,
        hospital TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS care_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL,
        target TEXT NOT NULL, created_at TEXT NOT NULL
    );
    """)
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
    finally:
        conn.close()


def audit(conn, actor, action, target):
    conn.execute("INSERT INTO care_audit(actor,action,target,created_at) VALUES(?,?,?,?)", (actor, action, target, now()))


def clean(value):
    return " ".join(str(value or "").split())


def email(value):
    return clean(value).lower()


def password_hash(value):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode(), bytes.fromhex(salt), 260000).hex()
    return salt + "$" + digest


def password_ok(value, stored):
    try:
        salt, digest = stored.split("$")
        result = hashlib.pbkdf2_hmac("sha256", value.encode(), bytes.fromhex(salt), 260000).hex()
        return hmac.compare_digest(result, digest)
    except (ValueError, TypeError):
        return False


def public_doctor(row):
    return {k: row[k] for k in ("id", "email", "name", "phone", "specialty", "license_number", "licensing_body", "country", "hospital", "city", "status", "invite_code", "created_at", "review_note")}


def approved(conn, doctor_id):
    row = conn.execute("SELECT * FROM doctors WHERE id=? AND status='approved'", (doctor_id,)).fetchone()
    if not row:
        raise PermissionError("Your doctor account is awaiting review, suspended or unavailable.")
    return row


def create_doctor(details, password, confirmation, declaration):
    fields = ("email", "name", "phone", "specialty", "license_number", "licensing_body", "country", "hospital", "city")
    values = {k: clean(details.get(k)) for k in fields}
    values["email"] = email(values["email"])
    if any(not v or len(v) > 254 for v in values.values()):
        raise ValueError("Complete all fields (maximum 254 characters per field).")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"]):
        raise ValueError("Enter a valid email address.")
    if not re.fullmatch(r"\+[1-9][0-9]{5,14}", values["phone"]):
        raise ValueError("Enter a phone number with the country code, for example +256771234567.")
    if not 8 <= len(password) <= 128 or not password.strip():
        raise ValueError("Use a password of 8 to 128 characters.")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    if not declaration:
        raise ValueError("Confirm your professional details and the development-use notice.")
    identifier = secrets.token_hex(16)
    hashed = password_hash(password)
    with database() as conn:
        duplicate = conn.execute("SELECT id FROM doctors WHERE email=? OR (license_number=? AND licensing_body=?)", (values["email"], values["license_number"], values["licensing_body"])).fetchone()
        if duplicate:
            raise ValueError("The email or professional license is already registered.")
        conn.execute("INSERT INTO doctors(id,email,name,phone,specialty,license_number,licensing_body,country,hospital,city,password_hash,invite_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (identifier, *(values[k] for k in fields), hashed, secrets.token_hex(6).upper(), now()))
        audit(conn, identifier, "doctor_registration", identifier)
    return identifier


def login_doctor(address, password):
    with database() as conn:
        row = conn.execute("SELECT * FROM doctors WHERE email=?", (email(address),)).fetchone()
        if not row:
            return None, "Invalid email or password."
        if row["locked_until"] and row["locked_until"] > now():
            return None, "Too many attempts. Try again after five minutes."
        if not password_ok(password, row["password_hash"]):
            attempts = row["failed_attempts"] + 1
            locked = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="seconds") if attempts >= 5 else ""
            conn.execute("UPDATE doctors SET failed_attempts=?,locked_until=? WHERE id=?", (0 if locked else attempts, locked, row["id"]))
            return None, "Invalid email or password."
        conn.execute("UPDATE doctors SET failed_attempts=0,locked_until='' WHERE id=?", (row["id"],))
        if row["status"] != "approved":
            return None, "Your account is " + row["status"] + ". Contact the app administrator."
        audit(conn, row["id"], "doctor_login", row["id"])
        return public_doctor(row), None


def doctor_session(identifier):
    with database() as conn:
        return public_doctor(approved(conn, identifier))


def review_doctor(identifier, status, note, verified=False):
    import streamlit as st
    if st.session_state.get("admin_ok") is not True:
        raise PermissionError("Administrator access required.")
    if status not in ("approved", "rejected", "suspended") or len(clean(note)) < 5:
        raise ValueError("Select a review decision and enter a review note.")
    if status == "approved" and not verified:
        raise ValueError("Confirm that professional credentials and hospital affiliation were checked.")
    with database() as conn:
        result = conn.execute("UPDATE doctors SET status=?,review_note=?,reviewed_at=? WHERE id=?", (status, clean(note), now(), identifier))
        if result.rowcount != 1:
            raise ValueError("Doctor account not found.")
        audit(conn, "administrator", "doctor_" + status, identifier)


def patient_location(user):
    with database() as conn:
        row = conn.execute("SELECT * FROM patient_locations WHERE email=?", (email(user.get("email")),)).fetchone()
        return dict(row) if row else {"country": user.get("country", ""), "hospital": ""}


def save_patient_location(user, country, hospital):
    owner = email(user.get("email"))
    if not owner or not user.get("patient_id") or not clean(country) or not clean(hospital):
        raise ValueError("Country and hospital are required. Enter 'Not assigned' if no hospital follows you.")
    if max(len(clean(country)), len(clean(hospital))) > 254:
        raise ValueError("Keep the country and hospital under 255 characters.")
    with database() as conn:
        conn.execute("INSERT INTO patient_locations VALUES(?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET patient_id=excluded.patient_id,name=excluded.name,country=excluded.country,hospital=excluded.hospital,updated_at=excluded.updated_at",
                     (owner, str(user["patient_id"]), clean(user.get("first_name", "") + " " + user.get("last_name", "")), clean(country), clean(hospital), now()))
        audit(conn, owner, "patient_location_updated", owner)


CONSENT = "I allow this doctor to view my saved screening history, answers and notes until I revoke access."


def find_doctor(code):
    with database() as conn:
        row = conn.execute("SELECT * FROM doctors WHERE invite_code=? AND status='approved'", (clean(code).upper(),)).fetchone()
        return public_doctor(row) if row else None


def request_care(user, doctor_id, consent):
    if not consent:
        raise ValueError("Patient consent is required.")
    owner = email(user.get("email"))
    if not owner or not user.get("patient_id"):
        raise ValueError("A signed-in patient account is required.")
    with database() as conn:
        approved(conn, doctor_id)
        location = conn.execute("SELECT email FROM patient_locations WHERE email=?", (owner,)).fetchone()
        if not location:
            raise ValueError("Save your country and hospital first.")
        existing = conn.execute("SELECT status FROM care_links WHERE doctor_id=? AND patient_email=?", (doctor_id, owner)).fetchone()
        if existing and existing["status"] in ("pending", "active"):
            raise ValueError("You already have a pending or active request with this doctor.")
        conn.execute("INSERT INTO care_links VALUES(?,?,?,?,?,?) ON CONFLICT(doctor_id,patient_email) DO UPDATE SET status='pending',requested_at=excluded.requested_at,updated_at=excluded.updated_at,consent_text=excluded.consent_text",
                     (doctor_id, owner, "pending", now(), now(), CONSENT))
        audit(conn, owner, "patient_consent_requested", doctor_id)


def patient_links(user):
    with database() as conn:
        return [dict(r) for r in conn.execute("SELECT d.id,d.name,d.specialty,d.hospital,d.country,d.status AS doctor_status,l.status,l.updated_at FROM care_links l JOIN doctors d ON d.id=l.doctor_id WHERE l.patient_email=? ORDER BY l.updated_at DESC", (email(user.get("email")),))]


def revoke_care(user, doctor_id):
    owner = email(user.get("email"))
    with database() as conn:
        conn.execute("UPDATE care_links SET status='revoked',updated_at=? WHERE doctor_id=? AND patient_email=?", (now(), doctor_id, owner))
        audit(conn, owner, "patient_access_revoked", doctor_id)


def doctor_patients(doctor_id):
    with database() as conn:
        approved(conn, doctor_id)
        return [dict(r) for r in conn.execute("SELECT p.*,l.status FROM care_links l JOIN patient_locations p ON p.email=l.patient_email WHERE l.doctor_id=? AND l.status IN ('pending','active') ORDER BY p.name", (doctor_id,))]


def decide_care(doctor_id, owner, accept):
    with database() as conn:
        approved(conn, doctor_id)
        result = conn.execute("UPDATE care_links SET status=?,updated_at=? WHERE doctor_id=? AND patient_email=? AND status='pending'", ("active" if accept else "declined", now(), doctor_id, email(owner)))
        if result.rowcount != 1:
            raise ValueError("This request is no longer pending.")
        audit(conn, doctor_id, "care_accepted" if accept else "care_declined", email(owner))


def active_patient(conn, doctor_id, owner):
    approved(conn, doctor_id)
    row = conn.execute("SELECT p.* FROM care_links l JOIN patient_locations p ON p.email=l.patient_email WHERE l.doctor_id=? AND l.patient_email=? AND l.status='active'", (doctor_id, email(owner))).fetchone()
    if not row:
        raise PermissionError("This patient has not granted active access to you.")
    return dict(row)


def doctor_reports(doctor_id, owner, history_db="patient_history.db"):
    with database() as conn:
        patient = active_patient(conn, doctor_id, owner)
        audit(conn, doctor_id, "patient_history_view", email(owner))
    if not os.path.exists(history_db):
        return []
    # Open history read-only: the doctor cannot modify the patient's assessments.
    from pathlib import Path
    uri = Path(history_db).resolve().as_uri() + "?mode=ro"
    history = sqlite3.connect(uri, uri=True, timeout=30)
    try:
        exists = history.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='patient_assessments'").fetchone()
        if not exists:
            return []
        rows = history.execute("SELECT payload FROM patient_assessments WHERE owner_email=? AND patient_id=? ORDER BY recorded_at DESC,rowid DESC", (email(owner), patient["patient_id"])).fetchall()
        result = []
        for row in rows:
            try:
                record = json.loads(row[0])
                if record.get("completed_prediction") is True and isinstance(record.get("report"), dict):
                    result.append(record)
            except (ValueError, TypeError, AttributeError):
                continue
        return result
    finally:
        history.close()


def add_care_note(doctor_id, owner, text, assessment_id="", history_db="patient_history.db"):
    text = str(text or "").strip()
    if not 1 <= len(text) <= 3000:
        raise ValueError("Enter a follow-up note of 1 to 3000 characters.")
    if assessment_id and assessment_id not in {r["record_id"] for r in doctor_reports(doctor_id, owner, history_db)}:
        raise PermissionError("The selected assessment is not available to this doctor.")
    with database() as conn:
        active_patient(conn, doctor_id, owner)
        conn.execute("INSERT INTO care_notes VALUES(?,?,?,?,?,?)", (secrets.token_hex(16), doctor_id, email(owner), assessment_id, text, now()))
        audit(conn, doctor_id, "follow_up_note_added", email(owner))


def patient_notes(user):
    with database() as conn:
        return [dict(r) for r in conn.execute("SELECT n.*,d.name AS doctor_name,d.hospital FROM care_notes n JOIN doctors d ON d.id=n.doctor_id WHERE n.patient_email=? ORDER BY n.created_at DESC", (email(user.get("email")),))]


def doctor_notes(doctor_id, owner):
    with database() as conn:
        active_patient(conn, doctor_id, owner)
        return [dict(r) for r in conn.execute("SELECT * FROM care_notes WHERE doctor_id=? AND patient_email=? ORDER BY created_at DESC", (doctor_id, email(owner)))]


def doctor_auth_page(page, go_to, countries):
    import streamlit as st
    if st.button("Back to account selection", key="doctor_auth_back"):
        go_to("auth")
    if page == "doctor_login":
        st.title("Doctor sign in")
        with st.form("doctor_login_form"):
            address = st.text_input("Email", max_chars=254)
            password = st.text_input("Password", type="password", max_chars=128)
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            doctor, error = login_doctor(address, password)
            if error:
                st.error(error)
            else:
                # Clear previous role-specific patient reports and cached PDFs.
                retained = {k: st.session_state[k] for k in ("lang", "dark_mode") if k in st.session_state}
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.session_state.update(retained)
                st.session_state["doctor_user"] = doctor
                go_to("doctor_dashboard")
        if st.button("Register as a doctor"):
            go_to("doctor_register")
        return
    st.title("Doctor registration")
    st.caption("Development version. Registration is reviewed manually before patient access is enabled.")
    with st.form("doctor_registration_form", clear_on_submit=False):
        st.subheader("Personal and professional details")
        a, b = st.columns(2)
        with a:
            name = st.text_input("Full name *", max_chars=100)
            address = st.text_input("Professional email *", max_chars=254)
            specialty = st.text_input("Specialty *", max_chars=120)
            license_number = st.text_input("Professional license / registration number *", max_chars=120)
        with b:
            phone = st.text_input("Phone including country code *", placeholder="+256771234567", max_chars=16)
            licensing_body = st.text_input("Licensing / registration authority *", max_chars=120)
            country = st.selectbox("Country of practice *", countries, index=None)
            city = st.text_input("City *", max_chars=100)
        hospital = st.text_input("Hospital / clinic affiliation *", max_chars=180)
        st.subheader("Account security")
        a, b = st.columns(2)
        with a:
            password = st.text_input("Password *", type="password", max_chars=128)
        with b:
            confirmation = st.text_input("Confirm password *", type="password", max_chars=128)
        declared = st.checkbox("I confirm that these details are accurate and understand this is a development screening assistant, not an approved clinical service.")
        submitted = st.form_submit_button("Submit for administrator review", type="primary", use_container_width=True)
    if submitted:
        try:
            create_doctor(dict(name=name,email=address,phone=phone,specialty=specialty,license_number=license_number,licensing_body=licensing_body,country=country,hospital=hospital,city=city),password,confirmation,declared)
            st.success("Registration submitted. You can sign in after administrator approval.")
        except (ValueError, sqlite3.Error) as exc:
            st.error(str(exc))


def render_doctor_admin():
    import streamlit as st
    if st.session_state.get("admin_ok") is not True:
        return
    st.subheader("Doctor account reviews")
    with database() as conn:
        rows = [public_doctor(r) for r in conn.execute("SELECT * FROM doctors ORDER BY created_at DESC")]
    if not rows:
        st.info("No doctor registrations yet.")
    a,b=st.columns(2)
    status=a.selectbox("Doctor status",["All","pending","approved","rejected","suspended"],key="admin_doctor_status")
    query=b.text_input("Search doctors",placeholder="Name, hospital or country",key="admin_doctor_search").strip().casefold()
    rows=[d for d in rows if (status=="All" or d["status"]==status) and query in " ".join(str(d[k]) for k in ("name","email","hospital","country","specialty")).casefold()]
    st.caption(f"{len(rows)} matching doctor accounts")
    if not rows:
        st.info("No doctors match these filters.")
    for doctor in rows:
        with st.expander(f"{doctor['name']} | {doctor['status']} | {doctor['hospital']}"):
            st.caption(f"{doctor['specialty']} | {doctor['country']} | {doctor['city']}")
            left,right=st.columns(2)
            for i,(key,label) in enumerate((("email","Professional email"),("phone","Phone"),("license_number","License number"),("licensing_body","Licensing authority"),("hospital","Registered hospital"),("review_note","Previous review note"))):
                with (left if i%2==0 else right):
                    st.caption(label)
                    st.write(doctor[key] or "Not recorded")
            with st.form("review_" + doctor["id"]):
                decision = st.selectbox("Decision", ["approved","rejected","suspended"])
                verified = st.checkbox("I checked the professional credentials and hospital affiliation using reliable evidence.")
                note = st.text_area("Review record / reason *", max_chars=1000)
                save = st.form_submit_button("Save review decision")
            if save:
                try:
                    ux.confirm_action("Confirm doctor account decision?", "This changes whether the doctor can access their workspace.", lambda doctor_id=doctor["id"],decision=decision,note=note,verified=verified:review_doctor(doctor_id,decision,note,verified), {"Doctor":doctor["name"],"Decision":decision,"Review note":note})
                except (ValueError,PermissionError) as exc:
                    st.error(str(exc))


def render_patient_care(user, go_to, countries):
    import streamlit as st
    if not user.get("email"):
        go_to("auth")
        return
    st.title("My doctor and care team")
    if st.button("Back to screening"):
        go_to("main")
    location_tab, connections_tab, notes_tab = st.tabs(["Care location", "My doctors", "Doctor notes"])
    with location_tab:
        location = patient_location(user)
        with st.form("patient_care_location"):
            st.subheader("Where you receive care")
            current = location.get("country") or user.get("country")
            country = st.selectbox("Patient country", countries, index=countries.index(current) if current in countries else None)
            hospital = st.text_input("Patient hospital / clinic",value=location.get("hospital", ""), max_chars=180,
                                     help="Enter Not assigned if you do not currently attend a hospital or clinic.")
            save = st.form_submit_button("Save care location")
        if save:
            try:
                save_patient_location(user,country,hospital)
                st.success("Care location saved. Future reports will use this location.")
            except ValueError as exc:
                st.error(str(exc))
    with connections_tab:
        with st.container(key="care_connect_panel"):
            st.subheader("Connect with a doctor")
            code = st.text_input("Doctor follow-up code",max_chars=12).strip().upper()
            doctor = find_doctor(code) if code else None
            if st.session_state.get("care_revealed_code") != code or not doctor:
                st.session_state.pop("care_revealed_code", None)
            if code and not doctor:
                st.warning("No approved doctor matches this code.")
            if st.button("Connect", key="care_connect_button", disabled=doctor is None,
                         type="primary" if doctor else "secondary", use_container_width=True):
                st.session_state["care_revealed_code"] = code
            if doctor and st.session_state.get("care_revealed_code") == code:
                st.write(f"Dr {doctor['name']} | {doctor['specialty']} | {doctor['hospital']} | {doctor['country']}")
                consent = st.checkbox(CONSENT)
                if st.button("Request follow-up",type="primary"):
                    try:
                        if not consent:
                            raise ValueError("Patient consent is required.")
                        ux.confirm_action("Share your screening history?", CONSENT, lambda:request_care(user,doctor["id"],consent), {"Doctor":doctor["name"],"Hospital":doctor["hospital"],"Country":doctor["country"]})
                    except (ValueError,PermissionError) as exc:
                        st.error(str(exc))
        st.subheader("Your care connections")
        st.caption("You may connect with several doctors. Each connection has its own consent and access controls.")
        for link in patient_links(user):
            with st.container(key="care_connection_" + link["id"]):
                st.write(f"Dr {link['name']} | {link['hospital']} | {link['country']} | Follow-up: {link['status']} | Account: {link['doctor_status']}")
                if link["status"] in ("active","pending") and st.button("Revoke / cancel access",key="revoke_"+link["id"]):
                    ux.confirm_action("Revoke doctor access?", "This doctor will lose access to your saved reports. Your reports remain in your account.", lambda doctor_id=link["id"]:revoke_care(user,doctor_id), {"Doctor":link["name"],"Hospital":link["hospital"]})
    with notes_tab:
        st.subheader("Your doctor's follow-up notes")
        notes = patient_notes(user)
        if not notes:
            st.info("No follow-up notes yet.")
        for note_index, note in enumerate(notes):
            with st.container(key="care_note_" + str(note_index)):
                st.caption(f"Dr {note['doctor_name']} | {note['hospital']} | {note['created_at']}")
                if note["assessment_id"]:
                    st.caption("Assessment reference: " + note["assessment_id"])
                st.write(note["text"])


def doctor_work_location(doctor_id):
    with database() as conn:
        doctor = approved(conn, doctor_id)
        row = conn.execute("SELECT country,hospital FROM doctor_work_locations WHERE doctor_id=?", (doctor_id,)).fetchone()
        return dict(row) if row else {"country":doctor["country"], "hospital":doctor["hospital"]}


def save_doctor_work_location(doctor_id, country, hospital):
    country, hospital = clean(country), clean(hospital)
    if not country or not hospital or len(country)>100 or len(hospital)>180:
        raise ValueError("Enter a country and hospital / clinic (up to 180 characters).")
    with database() as conn:
        approved(conn, doctor_id)
        conn.execute("INSERT INTO doctor_work_locations VALUES(?,?,?,?) ON CONFLICT(doctor_id) DO UPDATE SET country=excluded.country,hospital=excluded.hospital,updated_at=excluded.updated_at", (doctor_id,country,hospital,now()))
        audit(conn, doctor_id, "work_location_updated", hospital)


def filter_care_patients(patients, country="All countries", hospital="All hospitals", query=""):
    query=clean(query).casefold()
    return [p for p in patients if p["status"]=="active"
            and (country=="All countries" or clean(p["country"]).casefold()==clean(country).casefold())
            and (hospital=="All hospitals" or clean(p["hospital"]).casefold()==clean(hospital).casefold())
            and query in " ".join(str(p[k]) for k in ("name","patient_id","country","hospital")).casefold()]


def render_doctor_dashboard(go_to, logout, render_report, pdf_report, history_db):
    import streamlit as st
    from html import escape
    try:
        doctor = doctor_session((st.session_state.get("doctor_user") or {}).get("id", ""))
    except PermissionError as exc:
        st.error(str(exc))
        if st.button("Return to doctor sign in"):
            st.session_state.pop("doctor_user",None)
            go_to("doctor_login")
        return
    location=doctor_work_location(doctor["id"])
    st.markdown(f'<div class="ux-hero"><h2>Welcome, Dr {escape(doctor["name"])}</h2><p>{escape(doctor["specialty"])} · {escape(location["hospital"])} · {escape(location["country"])}</p></div>',unsafe_allow_html=True)
    patients=doctor_patients(doctor["id"])
    active=[p for p in patients if p["status"]=="active"]
    pending=[p for p in patients if p["status"]=="pending"]
    a,b,c=st.columns(3)
    a.metric("Active patients",len(active));b.metric("New requests",len(pending));c.metric("Work country",location["country"])
    section=st.radio("Workspace",["Patients","Requests","My profile"],horizontal=True,key="doctor_section",label_visibility="collapsed")
    if section=="My profile":
        with st.container(border=True):
            st.subheader("Your professional profile")
            st.write(f"{doctor['name']} · {doctor['specialty']}")
            st.caption(f"Registered affiliation: {doctor['hospital']} | {doctor['country']}")
            st.caption("Current work location is self-reported. Updating it does not change your approved professional credentials or grant patient access.")
            with st.form("doctor_work_location"):
                country=st.text_input("Current work country",value=location["country"],max_chars=100)
                hospital=st.text_input("Current hospital / clinic",value=location["hospital"],max_chars=180)
                save=st.form_submit_button("Save work location",type="primary")
            if save:
                ux.confirm_action("Update work location?","Your patient list can be filtered using this location.",lambda:save_doctor_work_location(doctor["id"],country,hospital),{"Country":country,"Hospital":hospital})
        st.subheader("Patient invitation")
        st.code(doctor["invite_code"],language=None)
        st.caption("Share this code with your patient. Patient consent and your acceptance are both required.")
        if st.button("Log out",key="doctor_logout"):
            ux.confirm_action("Log out?","End this doctor session?",logout)
        return
    if section=="Requests":
        st.subheader("Pending follow-up requests")
        if not pending: st.info("You are up to date. No pending requests.")
        for patient in pending:
            with st.container(border=True):
                st.subheader(patient["name"])
                st.caption(f"{patient['patient_id']} | {patient['country']} | {patient['hospital']}")
                a,b=st.columns(2)
                for col,accept in ((a,True),(b,False)):
                    if col.button("Accept" if accept else "Decline",key=f"decide_{accept}_{patient['email']}"):
                        ux.confirm_action("Accept patient?" if accept else "Decline request?",
                            "Accepting grants access to the patient's completed screening history." if accept else "The patient can submit a new request later.",
                            lambda p=patient,accept=accept:decide_care(doctor["id"],p["email"],accept),{"Patient":patient["name"],"Patient ID":patient["patient_id"]})
        return
    st.subheader("Patients under your supervision")
    with st.expander("Search and hospital filters",expanded=True):
        a,b=st.columns(2)
        countries=["All countries"]+sorted({p["country"] for p in active}|{location["country"]})
        country=a.selectbox("Patient country filter",countries)
        hospitals=["All hospitals"]+sorted({p["hospital"] for p in active}|{location["hospital"]})
        hospital=b.selectbox("Patient hospital filter",hospitals)
        if st.toggle("Use my current hospital",key="use_current_hospital"):
            country,hospital=location["country"],location["hospital"]
            st.caption(f"Current work filter: {country} · {hospital}")
        query=st.text_input("Search patient name or ID")
    matching=filter_care_patients(patients,country,hospital,query)
    st.caption(f"{len(matching)} matching patients · Only active, consented connections")
    if not matching:
        st.info("No matching patients. Clear the filters or review Requests to accept a new connection.")
        return
    patient=st.selectbox("Select a patient",matching,format_func=lambda p:f"{p['name']} | {p['patient_id']}")
    try:
        records=doctor_reports(doctor["id"],patient["email"],history_db)
        with st.container(border=True):
            st.subheader(patient["name"])
            a,b,c=st.columns(3)
            a.metric("Patient ID",patient["patient_id"]);b.metric("Country",patient["country"]);c.metric("Saved assessments",len(records))
            st.caption("Hospital / clinic: "+patient["hospital"])
        reports_tab,notes_tab=st.tabs(["Screening reports","Follow-up notes"])
        with reports_tab:
            if records:
                selected=st.selectbox("Saved assessment",records,format_func=lambda r:f"{r['report'].get('Timestamp','')} | {r['report'].get('Probability','')}")
                a,b=st.columns(2)
                if a.button("Open patient report",key="doctor_open_report",use_container_width=True):
                    allowed=doctor_reports(doctor["id"],patient["email"],history_db)
                    if selected["record_id"] not in {r["record_id"] for r in allowed}: raise PermissionError("This report is no longer accessible.")
                    st.session_state["_doctor_open_record"]=(patient["email"],selected["record_id"])
                data=pdf_report(selected["report"],answers=selected.get("answers"))
                b.download_button("Download patient PDF",data=data,file_name=f"Patient_Report_{selected['record_id']}.pdf",mime="application/pdf",use_container_width=True)
                if st.session_state.get("_doctor_open_record")== (patient["email"],selected["record_id"]):
                    render_report(selected["report"],selected.get("answers"))
            else: st.info("No completed screening yet.")
        with notes_tab:
            with st.form("doctor_follow_up"):
                st.subheader("Add a follow-up note")
                options=[""]+[r["record_id"] for r in records]
                target=st.selectbox("Assessment reference (optional)",options,format_func=lambda v:v or "General follow-up")
                note=st.text_area("Guidance / follow-up note",max_chars=3000,height=140)
                save=st.form_submit_button("Review and save note",type="primary")
            if save:
                if not note.strip(): st.error("Write a note before saving.")
                else: ux.confirm_action("Send this note to the patient?","The patient will be able to read this note in their care page.",lambda:add_care_note(doctor["id"],patient["email"],note,target,history_db),{"Patient":patient["name"],"Assessment":target or "General follow-up","Note":note})
            for note in doctor_notes(doctor["id"],patient["email"]):
                with st.container(border=True):
                    st.caption(note["created_at"]);st.write(note["text"])
    except (ValueError,PermissionError,sqlite3.Error,RuntimeError,ImportError) as exc:
        st.error(str(exc))
