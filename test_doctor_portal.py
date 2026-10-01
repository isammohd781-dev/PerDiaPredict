import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import doctor_portal as care

fake_st=SimpleNamespace(session_state={'admin_ok':True})
sys.modules['streamlit']=fake_st
with tempfile.TemporaryDirectory() as temp:
    care.CARE_DB=temp+'/care.db'
    history_path=temp+'/history.db'
    details=dict(email='doctor@example.com',name='Demo Doctor',phone='+256771234567',specialty='General practice',license_number='TEST001',licensing_body='Demo licensing authority',country='Uganda',hospital='Demo Hospital',city='Kampala')
    doctor=care.create_doctor(details,'Secret123','Secret123',True)
    assert care.login_doctor(details['email'],'Secret123')[0] is None
    try: care.create_doctor(details,'Secret123','Secret123',True)
    except ValueError: pass
    else: raise AssertionError('Duplicate doctor accepted')
    for admin,verified in [(False,True),(True,False)]:
        fake_st.session_state['admin_ok']=admin
        try: care.review_doctor(doctor,'approved','Credentials verified for testing',verified)
        except (ValueError,PermissionError): pass
        else: raise AssertionError('Review authorization bypassed')
    fake_st.session_state['admin_ok']=True
    care.review_doctor(doctor,'approved','Synthetic credentials checked in test',True)
    authenticated,error=care.login_doctor(' DOCTOR@EXAMPLE.COM ','Secret123')
    assert not error and authenticated['status']=='approved' and 'password_hash' not in authenticated
    other=care.create_doctor({**details,'email':'other@example.com','license_number':'TEST002'},'Secret123','Secret123',True)
    care.review_doctor(other,'approved','Synthetic credentials checked in test',True)
    patient=dict(email='patient@example.com',patient_id='26100101',first_name='Demo',last_name='Patient',country='Sudan')
    care.save_patient_location(patient,'Uganda','Patient Clinic')
    location=care.patient_location(patient)
    assert location['hospital']=='Patient Clinic' and location['country']=='Uganda'
    assert care.find_doctor(authenticated['invite_code'])['id']==doctor
    try: care.request_care(patient,doctor,False)
    except ValueError: pass
    else: raise AssertionError('Missing consent accepted')
    care.request_care(patient,doctor,True)
    assert care.doctor_patients(doctor)[0]['status']=='pending'
    try: care.doctor_reports(doctor,patient['email'],history_path)
    except PermissionError: pass
    else: raise AssertionError('Pending access allowed')
    care.decide_care(doctor,patient['email'],True)
    report=dict(record_id='test-report',completed_prediction=True,report={'Patient ID':'26100101','Probability':'25%','Patient notes':'Additional symptom','Hospital':'Patient Clinic'},answers={'Thirst':'No'})
    with sqlite3.connect(history_path) as conn:
        conn.execute('CREATE TABLE patient_assessments(record_id TEXT,owner_email TEXT,patient_id TEXT,recorded_at TEXT,payload TEXT)')
        conn.execute('INSERT INTO patient_assessments VALUES(?,?,?,?,?)',('test-report',patient['email'],patient['patient_id'],'2026-10-01',json.dumps(report)))
        conn.execute('INSERT INTO patient_assessments VALUES(?,?,?,?,?)',('other-report','other-patient@example.com','different-id','2026-10-01',json.dumps({**report,'record_id':'other-report'})))
    records=care.doctor_reports(doctor,patient['email'],history_path)
    assert len(records)==1 and records[0]['record_id']=='test-report'
    for target in [(other,patient['email']),(doctor,'other-patient@example.com')]:
        try: care.doctor_reports(*target,history_path)
        except PermissionError: pass
        else: raise AssertionError('Cross-patient or cross-doctor access allowed')
    try: care.add_care_note(doctor,patient['email'],'Test guidance','other-report',history_path)
    except PermissionError: pass
    else: raise AssertionError('Wrong assessment accepted')
    care.add_care_note(doctor,patient['email'],'Please discuss these symptoms at your follow-up.','test-report',history_path)
    assert care.patient_notes(patient)[0]['assessment_id']=='test-report'
    assert len(care.doctor_notes(doctor,patient['email']))==1
    care.revoke_care(patient,doctor)
    for operation in [lambda:care.doctor_reports(doctor,patient['email'],history_path),lambda:care.add_care_note(doctor,patient['email'],'No access'),lambda:care.doctor_notes(doctor,patient['email'])]:
        try: operation()
        except PermissionError: pass
        else: raise AssertionError('Revocation not enforced')
    care.request_care(patient,doctor,True)
    care.decide_care(doctor,patient['email'],True)
    care.review_doctor(doctor,'suspended','Access suspended for test',False)
    try: care.doctor_reports(doctor,patient['email'],history_path)
    except PermissionError: pass
    else: raise AssertionError('Suspended doctor accessed reports')
    assert care.login_doctor(details['email'],'Secret123')[0] is None
    assert care.find_doctor(authenticated['invite_code']) is None
    for _ in range(5): care.login_doctor('other@example.com','wrong')
    assert 'five minutes' in care.login_doctor('other@example.com','Secret123')[1]
    print('PASS: pending registration, duplicate credentials, admin review authorization, consent, acceptance, ownership isolation, report access, notes, revocation, suspension and lockout.')
