"""Synthetic multilingual reports and theme-gate checks."""
import test_reports as base
from pathlib import Path
from io import BytesIO
from pypdf import PdfReader
samples={'en':'Additional symptoms for review.','ar':'أشعر بصداع وتعب منذ يومين.','es':'Tengo cansancio y dolor de cabeza.','hi':'मुझे दो दिनों से सिरदर्द और थकान है।','zh':'我这两天头痛和疲劳。'}
records=[]
for lang,note in samples.items():
    report={**base.report,'Language':lang,'Patient notes':note}
    data=base.ns['generate_pdf_report'](report,answers=base.answers)
    Path(f'tmp/pdfs/language_{lang}.pdf').write_bytes(data)
    assert len(PdfReader(BytesIO(data)).pages)>=1
    records.append({'report':report,'answers':base.answers})
Path('tmp/pdfs/multilingual_combined.pdf').write_bytes(base.ns['generate_patient_history_pdf']({},records))
# Existing tests create a complete app with synthetic model/translation adapters.
import test_experience as experience
from streamlit.testing.v1 import AppTest
with __import__('tempfile').TemporaryDirectory() as temp:
    import doctor_portal as care
    care.CARE_DB=temp+'/care.db'
    source=experience.prefix+experience.source
    app=AppTest.from_string(source,default_timeout=20).run()
    app.session_state['page']='language'
    app.run()
    assert not app.exception,app.exception
    next(b for b in app.button if b.key=='gate_theme_toggle').click().run()
    assert app.session_state['dark_mode'] is False
    next(b for b in app.button if b.key=='gate_theme_toggle').click().run()
    assert app.session_state['dark_mode'] is True
    app.session_state['page']='auth';app.run()
    assert not app.exception,app.exception
    markup='\n'.join(x.value for x in app.markdown)
    assert '.stApp .admin-banner :is(h1,h2,p)' in markup
    assert 'border:1px solid' in markup
print('PASS: five report languages, merged reports, Unicode notes, theme switching on language gate and auth styling.')
# Account-entry routes retain their original button keys and destinations.
with __import__('tempfile').TemporaryDirectory() as temp:
    for lang in ('en','ar','es','hi','zh'):
        for dark in (True,False):
            entry=AppTest.from_string(experience.prefix+experience.source,default_timeout=20).run()
            entry.session_state['page']='auth'
            entry.session_state['lang']=lang
            entry.session_state['dark_mode']=dark
            entry.run()
            assert not entry.exception,(lang,dark,entry.exception)
            assert {'auth_btn_login','auth_btn_register','auth_doctor_login','auth_doctor_register','auth_btn_admin','auth_link_back'} <= {b.key for b in entry.button}
    entry.session_state['lang']='en'
    for key,destination in [('auth_btn_login','login'),('auth_btn_register','register'),('auth_doctor_login','doctor_login'),('auth_doctor_register','doctor_register'),('auth_btn_admin','admin'),('auth_link_back','language')]:
        entry.session_state['page']='auth';entry.run()
        next(b for b in entry.button if b.key==key).click().run()
        assert not entry.exception,(key,entry.exception)
        assert entry.session_state['page']==destination
print('PASS: account entry in five languages and two themes, all six navigation routes retained.')
