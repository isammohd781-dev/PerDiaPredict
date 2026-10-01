import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path('test_ui_deps').resolve()))
from streamlit.testing.v1 import AppTest
import doctor_portal as care

with tempfile.TemporaryDirectory() as temp:
    care.CARE_DB=temp+'/ui.db'
    setup=f'''import streamlit as st\nimport doctor_portal as care\ncare.CARE_DB={care.CARE_DB!r}\ndef go_to(page):\n    st.session_state['page']=page\n    st.rerun()\n'''
    register=AppTest.from_string(setup+"care.doctor_auth_page('doctor_register',go_to,['Uganda','Sudan'])").run()
    inputs={"Full name *":"Demo Doctor","Professional email *":"ui-doctor@example.com","Specialty *":"General practice","Professional license / registration number *":"UI001","Phone including country code *":"+256771234567","Licensing / registration authority *":"Demo authority","City *":"Kampala","Hospital / clinic affiliation *":"Demo Hospital","Password *":"Secret123","Confirm password *":"Secret123"}
    for widget in register.text_input: widget.set_value(inputs[widget.label])
    register.selectbox[0].select('Uganda')
    register.checkbox[0].check()
    register.button[-1].click().run()
    assert not register.exception,register.exception
    assert register.success,'Doctor registration failed'
    with care.database() as conn: doctor=dict(conn.execute('SELECT * FROM doctors').fetchone())
    admin=AppTest.from_string(setup+"st.session_state['admin_ok']=True\ncare.render_doctor_admin()\ncare.ux.render_confirmation()").run()
    admin.checkbox[0].check();admin.text_area[0].set_value('Synthetic professional affiliation reviewed')
    admin.button[0].click().run()
    next(b for b in admin.button if b.label=='Confirm').click().run()
    assert not admin.exception,admin.exception
    assert not admin.exception,admin.exception
    assert not admin.error,[e.value for e in admin.error]
    assert care.doctor_session(doctor['id'])['status']=='approved'
    login=AppTest.from_string(setup+"care.doctor_auth_page('doctor_login',go_to,['Uganda'])").run()
    login.text_input[0].set_value('ui-doctor@example.com');login.text_input[1].set_value('Secret123')
    login.button[1].click().run()
    assert not login.exception,login.exception
    assert login.session_state['doctor_user']['id']==doctor['id']
    patient={'email':'patient@example.com','patient_id':'26100101','first_name':'Demo','last_name':'Patient','country':'Uganda'}
    patient_ui=AppTest.from_string(setup+f"user={patient!r}\ncare.render_patient_care(user,go_to,['Uganda','Sudan'])\ncare.ux.render_confirmation()").run()
    patient_ui.text_input[0].set_value('Patient Clinic');patient_ui.button[1].click().run()
    assert not patient_ui.exception,patient_ui.exception
    assert next(b for b in patient_ui.button if b.label=='Connect').disabled
    patient_ui.text_input[1].set_value('INVALID').run()
    assert next(b for b in patient_ui.button if b.label=='Connect').disabled
    patient_ui.text_input[1].set_value(doctor['invite_code']).run()
    assert not next(b for b in patient_ui.button if b.label=='Connect').disabled
    next(b for b in patient_ui.button if b.label=='Connect').click().run()
    patient_ui.checkbox[0].check()
    next(b for b in patient_ui.button if b.label=='Request follow-up').click().run()
    assert not patient_ui.exception,patient_ui.exception
    assert care.patient_links(patient)==[]
    next(b for b in patient_ui.button if b.label=='Confirm').click().run()
    assert care.patient_links(patient)[0]['status']=='pending'
    dashboard=AppTest.from_string(setup+f"st.session_state['doctor_user']={{'id':{doctor['id']!r}}}\ncare.render_doctor_dashboard(go_to,lambda:None,lambda *a:None,lambda *a,**kw:b'%PDF-test',{temp+'/history.db'!r})\ncare.ux.render_confirmation()").run()
    assert not dashboard.exception,dashboard.exception
    dashboard.radio[0].set_value('Requests').run()
    next(b for b in dashboard.button if b.label=='Accept').click().run()
    assert care.patient_links(patient)[0]['status']=='pending'
    next(b for b in dashboard.button if b.label=='Cancel').click().run()
    assert care.patient_links(patient)[0]['status']=='pending'
    next(b for b in dashboard.button if b.label=='Accept').click().run()
    next(b for b in dashboard.button if b.label=='Confirm').click().run()
    assert not dashboard.exception,dashboard.exception
    assert care.patient_links(patient)[0]['status']=='active'
    dashboard.radio[0].set_value('Patients').run()
    dashboard.text_area[0].set_value('Follow-up guidance for the patient.')
    next(b for b in dashboard.button if b.label=='Review and save note').click().run()
    assert not dashboard.exception,dashboard.exception
    assert len(care.patient_notes(patient))==0
    next(b for b in dashboard.button if b.label=='Confirm').click().run()
    assert len(care.patient_notes(patient))==1
    dashboard.radio[0].set_value('My profile').run()
    dashboard.text_input[0].set_value('Sudan')
    dashboard.text_input[1].set_value('Demo New Hospital')
    next(b for b in dashboard.button if b.label=='Save work location').click().run()
    next(b for b in dashboard.button if b.label=='Confirm').click().run()
    assert care.doctor_work_location(doctor['id'])['hospital']=='Demo New Hospital'
    dashboard.radio[0].set_value('Patients').run()
    dashboard.toggle[0].set_value(True).run()
    assert not dashboard.exception,dashboard.exception
    assert any('No matching' in i.value for i in dashboard.info)
    dashboard.toggle[0].set_value(False).run()
    assert len(dashboard.text_area)==1
    patient_ui.run()
    next(b for b in patient_ui.button if b.label=='Revoke / cancel access').click().run()
    assert not patient_ui.exception,patient_ui.exception
    dashboard.run()
    assert not dashboard.exception,dashboard.exception
    assert care.doctor_patients(doctor['id'])
    next(b for b in patient_ui.button if b.label=='Confirm').click().run()
    assert care.doctor_patients(doctor['id'])==[]
    print('PASS: real Streamlit forms for doctor registration, admin approval, login, patient location, consent, acceptance, notes and revocation.')
