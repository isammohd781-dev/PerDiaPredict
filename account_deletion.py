"""Permanent patient account deletion and personal-data export.

Required by both app stores: an app that lets people create an account must let them
delete it from inside the app (Apple App Store Review Guideline 5.1.1(v)) and must offer
a web link where deletion can be requested (Google Play account deletion policy).

Deletion removes the account and every record tied to it. Security logs are kept only
in pseudonymised form: the email address is replaced by a one-way reference, so the log
stays consistent without identifying the person.

This module has no Streamlit dependency so it can be tested directly.
"""
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone


def pseudonym(email):
    """Stable, non-reversible stand-in for an email address in retained security logs."""
    digest = hashlib.sha256(("perdiapredict-deleted:" + (email or "").strip().lower()).encode()).hexdigest()
    return "deleted-account-" + digest[:16]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tables(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _clean_id(value):
    text = "" if value is None else str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def purge_history(history_db, email):
    """Delete every saved assessment owned by this account."""
    if not os.path.exists(history_db):
        return 0
    with closing(sqlite3.connect(history_db, timeout=30)) as conn:
        # Overwrite deleted content on disk instead of only marking pages free.
        conn.execute("PRAGMA secure_delete=ON")
        if "patient_assessments" not in _tables(conn):
            return 0
        with conn:
            removed = conn.execute("DELETE FROM patient_assessments WHERE owner_email=?", (email,)).rowcount
    return removed


def purge_care(care_db, email, patient_id):
    """Remove doctor links, notes and care location; pseudonymise retained audit rows."""
    if not os.path.exists(care_db):
        return {}
    alias = pseudonym(email)
    counts = {}
    with closing(sqlite3.connect(care_db, timeout=30)) as conn:
        conn.execute("PRAGMA secure_delete=ON")
        tables = _tables(conn)
        with conn:
            for table, column in (("care_notes", "patient_email"), ("care_links", "patient_email"),
                                  ("patient_locations", "email")):
                if table in tables:
                    counts[table] = conn.execute(f"DELETE FROM {table} WHERE {column}=?", (email,)).rowcount
            if "care_audit" in tables:
                conn.execute("UPDATE care_audit SET actor=? WHERE actor=?", (alias, email))
                conn.execute("UPDATE care_audit SET target=? WHERE target=?", (alias, email))
                conn.execute("INSERT INTO care_audit(actor,action,target,created_at) VALUES(?,?,?,?)",
                             (alias, "patient_account_deleted", alias, _now()))
            if "disclosure_audit" in tables:
                # Records of disclosures already made to an authority are kept, without the email.
                conn.execute("UPDATE disclosure_audit SET patient_email=? WHERE patient_email=?", (alias, email))
            # Patient IDs are never reissued, so a retained log line can never point at a new person.
            conn.execute("CREATE TABLE IF NOT EXISTS retired_patient_ids (patient_id TEXT PRIMARY KEY, retired_at TEXT NOT NULL)")
            if patient_id:
                conn.execute("INSERT OR IGNORE INTO retired_patient_ids VALUES(?,?)", (str(patient_id), _now()))
    return counts


def retired_patient_ids(care_db):
    if not os.path.exists(care_db):
        return set()
    with closing(sqlite3.connect(care_db, timeout=30)) as conn:
        if "retired_patient_ids" not in _tables(conn):
            return set()
        return {_clean_id(row[0]) for row in conn.execute("SELECT patient_id FROM retired_patient_ids")}


def purge_reports_sheet(reports_xlsx, patient_id, write_excel):
    """Remove the account's rows from the saved reports workbook."""
    if not patient_id or not os.path.exists(reports_xlsx):
        return 0
    import pandas as pd
    frame = pd.read_excel(reports_xlsx, engine="openpyxl", dtype=str)
    if "Patient ID" not in frame.columns:
        return 0
    keep = frame["Patient ID"].map(_clean_id) != _clean_id(patient_id)
    removed = int((~keep).sum())
    if removed:
        write_excel(frame[keep], reports_xlsx)
    return removed


def pseudonymise_audit_sheet(audit_xlsx, email, write_excel):
    """Replace the email inside retained application log lines."""
    if not email or not os.path.exists(audit_xlsx):
        return 0
    import pandas as pd
    frame = pd.read_excel(audit_xlsx, engine="openpyxl", dtype=str)
    if "Details" not in frame.columns:
        return 0
    details = frame["Details"].fillna("")
    hits = details.str.contains(email, regex=False, case=False)
    if hits.any():
        frame["Details"] = details.str.replace(email, pseudonym(email), regex=False, case=False)
        write_excel(frame, audit_xlsx)
    return int(hits.sum())


def purge_legacy_sqlite(db_file, email):
    """Older releases kept accounts in SQLite; make sure no copy survives there."""
    if not os.path.exists(db_file):
        return 0
    with closing(sqlite3.connect(db_file, timeout=15)) as conn:
        conn.execute("PRAGMA secure_delete=ON")
        if "users" not in _tables(conn):
            return 0
        with conn:
            return conn.execute("DELETE FROM users WHERE lower(trim(email))=?", (email,)).rowcount


def remove_photo(photos_dir, name, still_used):
    """Delete the profile photo unless another account uses the identical image."""
    if not name or os.path.basename(name) != name or name in still_used:
        return False
    path = os.path.join(photos_dir, name)
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False


EXPORT_ACCOUNT_FIELDS = ("patient_id", "first_name", "last_name", "email", "birth_date", "gender",
                         "marital_status", "diabetes_type", "country", "dial_code", "phone",
                         "created_at", "last_login")


def export_bundle(account, history, care_location, care_links, care_notes):
    """Everything the app holds about the patient, as readable JSON. No password data."""
    bundle = {
        "exported_at": _now(),
        "application": "PerdiaPredict",
        "account": {key: account.get(key, "") for key in EXPORT_ACCOUNT_FIELDS},
        "has_profile_photo": bool(account.get("profile_photo")),
        "care_location": care_location or {},
        "doctor_connections": care_links or [],
        "doctor_notes": care_notes or [],
        "screening_history": history or [],
    }
    return json.dumps(bundle, ensure_ascii=False, indent=2, default=str).encode("utf-8")
