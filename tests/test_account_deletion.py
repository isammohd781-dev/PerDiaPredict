"""Account deletion removes every record of one patient, keeps others intact, and never reuses the ID."""
import os as _os, sys as _sys
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent  # project folder; tests live in tests/
_sys.path.insert(0, str(ROOT_DIR)); _sys.path.insert(1, str(_Path(__file__).resolve().parent)); _os.chdir(ROOT_DIR)
import ast, calendar, hashlib, hmac, json, os, re, secrets, sqlite3, tempfile, threading, unicodedata
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd

temp = tempfile.mkdtemp()
os.environ["PERDIA_CARE_DB"] = os.path.join(temp, "care_team.db")
import account_deletion
import doctor_portal as care

source = (ROOT_DIR/"diabetes_app.py").read_text()
tree = ast.parse(source)
names = {"normalize_email", "normalize_person_name", "valid_person_name", "normalize_registration_phone",
         "hash_password", "verify_password", "_cell_text", "_rows_from_sheet", "_save_rows", "_import_old_sqlite",
         "_load_rows", "_update_account", "create_user", "authenticate", "_authenticate_locked",
         "generate_patient_id", "write_excel_safely", "delete_patient_account", "history_connection"}
constants = {"ACCOUNT_FIELDS", "ACCOUNT_HEADERS", "_FIELD_BY_HEADER", "MARITAL_STATUS_ORDER", "GENDER_OPTIONS",
             "DIABETES_TYPE_KEYS", "EMAIL_REGEX", "MIN_PASSWORD_LEN", "MAX_FAILED_LOGINS", "LOCK_MINUTES",
             "PBKDF2_ITERATIONS", "_DUMMY_HASH"}
ns = dict(globals())
for n in tree.body:
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets):
        exec(compile(ast.Module(body=[n], type_ignores=[]), "constants", "exec"), ns)
store = {"lock": threading.RLock(), "mtime": None, "rows": []}
logged = []
ns.update(_accounts_store=lambda: store, log_action=lambda *a: logged.append(a), care=care,
          account_deletion=account_deletion, BASE_DIR=temp, HISTORY_DB=os.path.join(temp, "patient_history.db"),
          ACCOUNTS_FILE=os.path.join(temp, "accounts.xlsx"), DB_FILE=os.path.join(temp, "old.db"),
          SAVE_FILE_XLSX=os.path.join(temp, "saved_reports.xlsx"), AUDIT_LOG_FILE=os.path.join(temp, "audit_log.xlsx"))
module = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
exec(compile(module, "isolated_backend", "exec"), ns)

def register(email):
    ok, err = ns["create_user"]("Test", "Patient", email, date(1990, 1, 1), "Secret123", "Male", "single",
                                "not_sure", "Uganda", "+256", "0771234567")
    assert ok, err
    return next(r for r in ns["_load_rows"]() if r["email"] == email)

keep = register("keep@example.com")
gone = register("gone@example.com")
assert gone["patient_id"] > keep["patient_id"]

# Data in every store, for both patients.
photos = os.path.join(temp, "profile_photos"); os.makedirs(photos)
for name in ("own.png", "shared.png"):
    Path(photos, name).write_bytes(b"x")
ns["_update_account"]("gone@example.com", profile_photo="own.png")
ns["_update_account"]("keep@example.com", profile_photo="shared.png")
with ns["history_connection"]() as conn:
    for row in (keep, gone):
        conn.execute("INSERT INTO patient_assessments VALUES(?,?,?,?,?)",
                     (secrets.token_hex(4), row["email"], row["patient_id"], "2026-10-30", "{}"))
ns["write_excel_safely"](pd.DataFrame([{"Patient ID": keep["patient_id"], "Probability": "10%"},
                                       {"Patient ID": gone["patient_id"], "Probability": "90%"}]), ns["SAVE_FILE_XLSX"])
ns["write_excel_safely"](pd.DataFrame([{"Timestamp": "t", "Account ID": 2, "Action": "login", "Details": "email=gone@example.com"},
                                       {"Timestamp": "t", "Account ID": 1, "Action": "login", "Details": "email=keep@example.com"}]), ns["AUDIT_LOG_FILE"])
with care.database() as conn:
    conn.execute("INSERT INTO doctors(id,email,name,phone,specialty,license_number,licensing_body,country,hospital,city,password_hash,status,invite_code,created_at) VALUES('d1','d@example.com','Doc','1','GP','L','B','Uganda','H','K','x','approved','CODE1','t')")
    conn.execute("CREATE TABLE IF NOT EXISTS disclosure_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_email TEXT NOT NULL, patient_id TEXT NOT NULL, country TEXT NOT NULL, permit_id TEXT NOT NULL, authority TEXT NOT NULL, request_reference TEXT NOT NULL, purpose TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL)")
    for row in (keep, gone):
        e = row["email"]
        conn.execute("INSERT INTO patient_locations VALUES(?,?,?,?,?,?)", (e, row["patient_id"], "Test Patient", "Uganda", "H", "t"))
        conn.execute("INSERT INTO care_links VALUES('d1',?,'active','t','t','c')", (e,))
        conn.execute("INSERT INTO care_notes VALUES(?,'d1',?,'','note','t')", (secrets.token_hex(4), e))
        conn.execute("INSERT INTO care_audit(actor,action,target,created_at) VALUES(?,?,?,?)", (e, "x", "d1", "t"))
        conn.execute("INSERT INTO disclosure_audit(patient_email,patient_id,country,permit_id,authority,request_reference,purpose,action,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                     (e, row["patient_id"], "Uganda", "p", "a", "r", "u", "granted", "t"))

# Wrong password: nothing changes.
assert ns["delete_patient_account"]("gone@example.com", "wrong-pass") == (False, "invalid")
assert any(r["email"] == "gone@example.com" for r in ns["_load_rows"]())
assert ns["delete_patient_account"]("nobody@example.com", "Secret123") == (False, "invalid")

# Correct password: everything of this patient is removed.
assert ns["delete_patient_account"](" GONE@example.com ", "Secret123") == (True, None)
emails = {r["email"] for r in ns["_load_rows"]()}
assert emails == {"keep@example.com"}, emails
with closing(sqlite3.connect(ns["HISTORY_DB"])) as conn:
    assert [r[0] for r in conn.execute("SELECT owner_email FROM patient_assessments")] == ["keep@example.com"]
reports = pd.read_excel(ns["SAVE_FILE_XLSX"], dtype=str)
assert list(reports["Patient ID"]) == [keep["patient_id"]]
audit_text = pd.read_excel(ns["AUDIT_LOG_FILE"], dtype=str).to_string()
assert "gone@example.com" not in audit_text and "keep@example.com" in audit_text
alias = account_deletion.pseudonym("gone@example.com")
with closing(sqlite3.connect(os.environ["PERDIA_CARE_DB"])) as conn:
    for table, column in (("patient_locations", "email"), ("care_links", "patient_email"), ("care_notes", "patient_email")):
        assert [r[0] for r in conn.execute(f"SELECT {column} FROM {table}")] == ["keep@example.com"], table
    everything = json.dumps([list(r) for t in ("care_audit", "disclosure_audit") for r in conn.execute(f"SELECT * FROM {t}")])
    assert "gone@example.com" not in everything and alias in everything and "keep@example.com" in everything
assert not Path(photos, "own.png").exists() and Path(photos, "shared.png").exists()
assert ("account_deleted" in [a[1] for a in logged]) and not any("gone@example.com" in str(a) for a in logged if a[1] == "account_deleted")

# The deleted patient's ID is never given to a new patient.
newcomer = register("new@example.com")
assert newcomer["patient_id"] != gone["patient_id"] and newcomer["patient_id"] > gone["patient_id"]

# Deleting again is refused; the remaining patient can still sign in.
assert ns["delete_patient_account"]("gone@example.com", "Secret123") == (False, "invalid")
assert ns["authenticate"]("keep@example.com", "Secret123")[1] == "ok"

# The export never contains password or lockout data.
bundle = json.loads(account_deletion.export_bundle({**keep, "password_hash": "secret"}, [{"r": 1}], {}, [], []))
assert "password_hash" not in json.dumps(bundle) and bundle["account"]["email"] == "keep@example.com"
print("Account deletion checks passed.")
