"""Real entry scripts: independent roles, shared consented follow-up, no cross-role navigation."""
import os as _os, sys as _sys
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent  # project folder; tests live in tests/
_sys.path.insert(0, str(ROOT_DIR)); _sys.path.insert(1, str(_Path(__file__).resolve().parent)); _os.chdir(ROOT_DIR)
from pathlib import Path
from types import SimpleNamespace
import os,sys,tempfile,shutil,hashlib
import pandas as pd
ROOT=ROOT_DIR
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    for p in ROOT.iterdir():
        if p.suffix in ('.py','.pkl','.json','.png'):
            shutil.copy2(p,root/p.name)
    (root/'fonts').symlink_to(ROOT/'fonts',target_is_directory=True)
    (root/'model').symlink_to(ROOT/'model',target_is_directory=True)
    os.environ['PERDIA_ADMIN_PASSWORD']='SyntheticAdminTest123'
    os.environ['PERDIA_CARE_DB']=str(root/'care_team.db')
    sys.path.insert(0,str(root))
    import streamlit as st
    import doctor_portal as care
    user={'id':1,'email':'patient@example.com','patient_id':'26100101','first_name':'Demo','last_name':'Patient','birth_date':'2000-01-01','gender':'Male','marital_status':'single','country':'Uganda','phone':'+256700000000'}
    details={'email':'doctor@example.com','name':'Test Doctor','phone':'+256700000000','specialty':'General medicine','license_number':'SYNTHETIC-01','licensing_body':'Test Board','country':'Uganda','hospital':'Test Clinic','city':'Kampala'}
    identifier=care.create_doctor(details,'SyntheticDoctor123','SyntheticDoctor123',True)
    assert care.login_doctor(details['email'],'SyntheticDoctor123')[0] is None
    sys.modules['streamlit']=SimpleNamespace(session_state={'admin_ok':True})
    care.review_doctor(identifier,'approved','Synthetic professional review',True)
    sys.modules['streamlit']=st
    care.save_patient_location(user,'Uganda','Test Clinic')
    care.request_care(user,identifier,True)
    pd.DataFrame([{'ID':1,'Patient ID':user['patient_id'],'Email':user['email'],'First name':'Demo','Last name':'Patient','Birth date':'2000-01-01','Gender':'Male','Marital status':'single','Country':'Uganda','Phone':'+256700000000','Password hash':'pbkdf2_sha256$260000$'+'00'*16+'$'+hashlib.pbkdf2_hmac('sha256',b'SyntheticPatient123',b'\0'*16,260000).hex(),'Created at':'2026-10-01','Failed attempts':0,'Must change password':0}]).to_excel(root/'accounts.xlsx',index=False)
    from streamlit.testing.v1 import AppTest
    patient=AppTest.from_file(str(root/'patient.py'),default_timeout=25).run()
    assert not patient.exception,patient.exception
    assert {'auth_btn_login','auth_btn_register'} <= {b.key for b in patient.button}
    assert not {'auth_doctor_login','auth_doctor_register','auth_btn_admin'}.intersection({b.key for b in patient.button})
    patient.query_params['portal']='admin';patient.run()
    assert patient.session_state['_fixed_role']=='patient'
    next(b for b in patient.button if b.key=='auth_btn_login').click().run()
    next(w for w in patient.text_input if w.key=='login_email').set_value(user['email'])
    next(w for w in patient.text_input if w.key=='login_pw').set_value('SyntheticPatient123')
    next(b for b in patient.button if b.key and 'FormSubmitter:login_form' in b.key).click().run()
    assert patient.session_state['user']['email']==user['email']
    assert not patient.exception,patient.exception
    patient.session_state['page']='admin';patient.run()
    assert patient.session_state['page']=='auth' and not patient.metric
    patient.session_state['page']='doctor_dashboard';patient.run()
    assert patient.session_state['page']=='auth'
    doctor=AppTest.from_file(str(root/'doctor.py'),default_timeout=25).run()
    assert not doctor.exception,doctor.exception
    assert doctor.session_state['page']=='doctor_login'
    assert 'user' not in doctor.session_state
    next(w for w in doctor.text_input if w.label=='Email').set_value(details['email'])
    next(w for w in doctor.text_input if w.label=='Password').set_value('SyntheticDoctor123')
    next(b for b in doctor.button if b.key and 'FormSubmitter:doctor_login_form' in b.key).click().run()
    assert doctor.session_state['page']=='doctor_dashboard' and not doctor.exception,doctor.exception
    assert len(care.doctor_patients(identifier))==1
    # An approved doctor accepts the patient's request; the patient sees the shared result.
    care.decide_care(identifier,user['email'],True)
    care.add_care_note(identifier,user['email'],'Synthetic follow-up guidance')
    patient.session_state['page']='patient_care';patient.run()
    assert not patient.exception,patient.exception
    assert any('Synthetic follow-up guidance' in m.value for m in patient.markdown)
    doctor.session_state['page']='admin';doctor.run()
    assert doctor.session_state['page']=='doctor_login' and not doctor.metric
    doctor.session_state['page']='register';doctor.run()
    assert doctor.session_state['page']=='doctor_login'
    admin=AppTest.from_file(str(root/'admin.py'),default_timeout=25).run()
    assert not admin.exception,admin.exception
    assert admin.session_state['page']=='admin'
    next(w for w in admin.text_input if w.key=='admin_pw').set_value('SyntheticAdminTest123')
    next(b for b in admin.button if b.key and 'FormSubmitter:admin_form' in b.key).click().run()
    assert admin.session_state['admin_ok'] is True and not admin.exception,admin.exception
    assert any(m.label=='Registered patients' and m.value=='1' for m in admin.metric)
    assert any(m.label=='Approved doctors' and m.value=='1' for m in admin.metric)
    admin.session_state['page']='main';admin.run()
    assert admin.session_state['page']=='admin'
    assert 'user' not in admin.session_state and 'doctor_user' not in admin.session_state
    assert patient.session_state['user']['email']==user['email']
    print('PASS: three real entry files; independent sessions; patient/doctor cannot enter admin; shared approval, care and notes; administrator sees shared account counts.')
