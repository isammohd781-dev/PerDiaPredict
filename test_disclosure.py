import os,sys,json,tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path('test_ui_deps').resolve()))
import disclosure_access as d
from streamlit.testing.v1 import AppTest
from pypdf import PdfReader
import pandas as pd
import test_reports as report_test

with tempfile.TemporaryDirectory() as temp:
    d.care.CARE_DB=temp+'/care.db'
    session={'admin_ok':True}
    original_st=d.st
    d.st=SimpleNamespace(session_state=session,secrets={})
    patient={'id':1,'patient_id':'DEMO-001','email':'demo@example.com','country':'Uganda','first_name':'Demo','last_name':'Patient'}
    other={**patient,'id':2,'patient_id':'OTHER-002','email':'other@example.com'}
    os.environ.pop('PERDIA_DISCLOSURE_PASSWORD',None)
    try:d.authorize('','x',patient,'Uganda','reports')
    except PermissionError:pass
    else:raise AssertionError('Unconfigured access opened')
    os.environ['PERDIA_DISCLOSURE_PASSWORD']='Synthetic-Custodian-Only-123!'
    permit={'permit_id':'TEST-PERMIT','medical_approved':True,'approved_by':'Synthetic medical reviewer','authority':'Test authority','request_reference':'TEST-REQUEST','purpose':'Local software test','patient_id':patient['patient_id'],'patient_email':patient['email'],'country':'Uganda','scopes':['reports','activity'],'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    os.environ['PERDIA_DISCLOSURE_PERMITS_JSON']=json.dumps([permit])
    for pw,ref in [('wrong','TEST-PERMIT'),(os.environ['PERDIA_DISCLOSURE_PASSWORD'],'unknown')]:
        try:d.authorize(pw,ref,patient,'Uganda','reports')
        except PermissionError:pass
        else:raise AssertionError('Wrong credentials opened')
    d.authorize(os.environ['PERDIA_DISCLOSURE_PASSWORD'],'TEST-PERMIT',patient,'Uganda','reports')
    assert d.validate(patient,'reports')['permit_id']=='TEST-PERMIT'
    for p,scope in [(other,'reports'),(patient,'activity'),({**patient,'country':'Sudan'},'reports')]:
        try:d.validate(p,scope)
        except PermissionError:pass
        else:raise AssertionError('Subject/scope/country leak')
    session['_disclosure_grant']['expires']=0
    try:d.validate(patient,'reports')
    except PermissionError:pass
    else:raise AssertionError('Expired session opened')
    d.authorize(os.environ['PERDIA_DISCLOSURE_PASSWORD'],'TEST-PERMIT',patient,'Uganda','activity')
    os.environ['PERDIA_DISCLOSURE_PERMITS_JSON']=json.dumps([{**permit,'medical_approved':False}])
    try:d.validate(patient,'activity')
    except PermissionError:pass
    else:raise AssertionError('Revoked permit opened')
    os.environ['PERDIA_DISCLOSURE_PERMITS_JSON']=json.dumps([permit])
    d.authorize(os.environ['PERDIA_DISCLOSURE_PASSWORD'],'TEST-PERMIT',patient,'Uganda','activity')
    pd.DataFrame([{'Timestamp':'2026-10-01 12:00','Account ID':1,'Action':'login','Details':'email=demo@example.com'}, {'Timestamp':'2026-10-01 12:01','Account ID':2,'Action':'login','Details':'OTHER-PATIENT-SECRET'}, {'Timestamp':'2026-10-01 12:02','Account ID':0,'Action':'password_reset','Details':'target_email=demo@example.com'}]).to_excel(temp+'/audit.xlsx',index=False)
    with d.care.database() as conn:
        d.care.audit(conn,patient['email'],'patient_consent_requested','doctor-id')
        d.care.audit(conn,'doctor-id','patient_history_view',patient['email'])
        d.care.audit(conn,'doctor-id','patient_history_view',other['email'])
    app={'AUDIT_LOG_FILE':temp+'/audit.xlsx','_report_font':report_test.ns['_report_font'],'_report_paragraph':report_test.ns['_report_paragraph']}
    events=d.activity(app,patient)
    assert all('OTHER-PATIENT-SECRET' not in e['Details'] and e['Details']!=other['email'] for e in events)
    assert any(e['Action']=='password_reset' for e in events)
    data=d.activity_pdf(app,patient,permit,events)
    Path('tmp/pdfs/activity_record.pdf').write_bytes(data)
    from io import BytesIO
    text=' '.join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)
    assert 'DEMO-001' in text and 'TEST-PERMIT' in text and 'OTHER-PATIENT-SECRET' not in text
    group={k:v for k,v in permit.items() if k not in ('patient_id','patient_email')}
    group['all_patients_in_country']=True
    os.environ['PERDIA_DISCLOSURE_PERMITS_JSON']=json.dumps([group])
    d.authorize(os.environ['PERDIA_DISCLOSURE_PASSWORD'],'TEST-PERMIT',patient,'Uganda','reports')
    assert d.validate(other,'reports')
    assert d.validate(other,'activity')
    original_expiry=session['_disclosure_grant']['expires']
    assert d.validate(patient,'reports')
    assert session['_disclosure_grant']['expires']==original_expiry
    try:d.validate({**other,'country':'Sudan'},'reports')
    except PermissionError:pass
    else:raise AssertionError('Country-wide permit crossed country')
    group.pop('all_patients_in_country')
    group['patients']=[{'patient_id':patient['patient_id'],'patient_email':patient['email']},{'patient_id':other['patient_id'],'patient_email':other['email']}]
    os.environ['PERDIA_DISCLOSURE_PERMITS_JSON']=json.dumps([group])
    d.authorize(os.environ['PERDIA_DISCLOSURE_PASSWORD'],'TEST-PERMIT',patient,'Uganda','reports')
    assert d.validate(other,'activity')
    try:d.validate({**other,'patient_id':'NOT-IN-PERMIT'},'reports')
    except PermissionError:pass
    else:raise AssertionError('Explicit group leaked to unlisted patient')
    os.environ['PERDIA_DISCLOSURE_PERMITS_JSON']=json.dumps([permit])
    d.authorize(os.environ['PERDIA_DISCLOSURE_PASSWORD'],'TEST-PERMIT',patient,'Uganda','activity')
    session['admin_ok']=False
    try:d.activity(app,patient)
    except PermissionError:pass
    else:raise AssertionError('Admin lock bypassed')
    session['admin_ok']=True
    for _ in range(5):
        try:d.authorize('wrong','TEST-PERMIT',patient,'Uganda','reports')
        except PermissionError:pass
    try:d.authorize(os.environ['PERDIA_DISCLOSURE_PASSWORD'],'TEST-PERMIT',patient,'Uganda','reports')
    except PermissionError:pass
    else:raise AssertionError('Persistent lockout bypassed')
    # UI remains locked before credentials, and authorization is one subject only.
    with d.care.database() as conn:conn.execute('DELETE FROM disclosure_auth')
    d.st=original_st
    prefix=f'''import os,streamlit as st,disclosure_access as d
import doctor_portal as care
care.CARE_DB={temp+'/care.db'!r}
st.session_state['admin_ok']=True
patient={patient!r}
'''
    ui=AppTest.from_string(prefix+"d.gate(patient,'reports')").run()
    assert not ui.exception,ui.exception
    assert not ui.success
    ui.text_input[0].set_value(os.environ['PERDIA_DISCLOSURE_PASSWORD']);ui.text_input[1].set_value('TEST-PERMIT')
    ui.button[0].click().run()
    assert not ui.exception,ui.exception
    assert ui.success
    next(b for b in ui.button if b.label=='Lock restricted access').click().run()
    assert not ui.success
    dropdown=AppTest.from_string(prefix+f"d.render_reports({{'load_patient_history':lambda p:[]}},[{patient!r},{other!r}])").run()
    assert not dropdown.exception,dropdown.exception
    assert len(dropdown.selectbox)==2
    dropdown.selectbox[0].select('Uganda').run()
    assert not dropdown.exception,dropdown.exception
    assert len(dropdown.selectbox[1].options)==2
    os.environ.pop('PERDIA_DISCLOSURE_PASSWORD',None);os.environ.pop('PERDIA_DISCLOSURE_PERMITS_JSON',None)
print('PASS: default denial, password/permit check, exact patient/country/scope, TTL, revocation, persistent lockout, patient activity isolation, PDF, real UI unlock/lock, country/group scopes, unchanged TTL and Reports country-dependent patient dropdown.')
