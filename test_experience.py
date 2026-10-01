import sys,tempfile,ast,re
from contextlib import nullcontext
from pathlib import Path
sys.path.insert(0,str(Path('test_ui_deps').resolve()))
from streamlit.testing.v1 import AppTest
import app_experience as ux
# Exercise the complete patient page with synthetic model adapters, not clinical validation.
source=Path('diabetes_app.py').read_text()
_workspace = tempfile.TemporaryDirectory()
with nullcontext(_workspace.name) as temp:
    prefix=f'''import sys,types
import streamlit as st
import os
os.environ["PERDIA_ADMIN_PASSWORD"]="SyntheticAdminTest123"
import doctor_portal as care
care.CARE_DB={temp+'/care.db'!r}
t=types.ModuleType('translations')
t.LANGUAGES={{'en':{{'native':'English','rtl':False}}}}
t.T={{'en':{{'no':'No','yes':'Yes','predict':'Predict','positive_high':'High risk','negative_low':'Low risk','meal_plan_rows':[['Monday','Breakfast','Lunch','Dinner','Water']]}}}}
sys.modules['translations']=t
m=types.ModuleType('screening_model')
m.load_screening_artifacts=lambda *a:(object(),['Age','Gender','Polyuria','Polydipsia','Itching'],{{'age_range':(5,100),'model_version':'synthetic-test','selected_model':'stub','threshold':.5}})
m.predict_screening=lambda *a:(0,0.0)
sys.modules['screening_model']=m
if 'user' not in st.session_state:
    st.session_state.update({{'page':'main','lang':'en','dark_mode':True,'user':{{'id':1,'email':'patient@example.com','patient_id':'26100101','first_name':'Demo','last_name':'Patient','birth_date':'2000-01-01','gender':'Male','marital_status':'single','phone':'+256700000000','country':'Uganda'}}}})
'''
    for name,file in [('ACCOUNTS_FILE','accounts.xlsx'),('HISTORY_DB','history.db'),('SAVE_FILE_XLSX','reports.xlsx'),('AUDIT_LOG_FILE','log.xlsx')]:
        source=re.sub(r'^'+name+r' = .+$',lambda _:name+' = '+repr(temp+'/'+file),source,flags=re.MULTILINE)
    patient=AppTest.from_string(prefix+source,default_timeout=15).run()
    assert not patient.exception,patient.exception
    symptom_widgets=[w for w in patient.selectbox if w.key and w.key.startswith(('core_','extra_','gender_','type_'))]
    assert symptom_widgets and all(w.value=='No' for w in symptom_widgets)
    keys={b.key for b in patient.button}
    assert "profile_edit_toggle" in keys
    assert not keys.intersection({"patient_history_open","patient_care_open"})
    assert {"ux_nav_main","ux_nav_patient_history","ux_nav_patient_care"} <= keys
    assert not patient.chat_input
    next(b for b in patient.button if b.key=='predict_btn').click().run()
    assert not patient.exception,patient.exception
    assert patient.session_state['last_report'] is None
    next(b for b in patient.button if b.label=='Cancel').click().run()
    assert not patient.exception,patient.exception
    next(b for b in patient.button if b.key=='predict_btn').click().run()
    next(b for b in patient.button if b.label=='Confirm').click().run()
    assert not patient.exception,patient.exception
    assert patient.session_state['last_report']['Probability']=='0.0%'
    assert patient.session_state['history_saved']
    before=patient.session_state['assessment_id']
    patient.run()
    assert patient.session_state['assessment_id']==before
    patient.session_state['page']='admin'
    patient.session_state['admin_ok']=True
    patient.run()
    assert not patient.exception,patient.exception
    assert any(m.label=='Completed assessments' and m.value=='1' for m in patient.metric)
    next(b for b in patient.button if b.key=='admin_review_shortcut').click().run()
    assert not patient.exception,patient.exception
    assert patient.session_state['admin_section']=='Doctors'
    for section in ['Patients','Reports','Activity','Overview']:
        next(r for r in patient.radio if r.key=='admin_section').set_value(section).run()
        assert not patient.exception,(section,patient.exception)
    next(b for b in patient.button if b.key=='admin_lock').click().run()
    assert not patient.exception,patient.exception
    assert patient.session_state['admin_ok'] is False
    assert not patient.metric
print('PASS: no help chat, single patient navigation, Edit profile retained, full patient page No defaults, prediction review, cancel, confirm, 0% save and no duplicate on rerun; all admin sections, real counts, shortcut and session lock.')
