import ast, base64, hashlib, json, os, re, secrets, sqlite3, tempfile
from contextlib import closing, contextmanager
from datetime import datetime
from html import escape as html_escape
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from pypdf import PdfReader
source=Path('diabetes_app.py').read_text();tree=ast.parse(source)
names={'normalize_email','history_text','history_connection','record_assessment','load_patient_history','history_score','_report_font','_report_paragraph','_medical_report_story','_build_medical_pdf','generate_pdf_report','generate_patient_history_pdf','cached_report_pdf','render_medical_report'}
ns=dict(globals());ns['st']=SimpleNamespace(session_state={'lang':'en','user':{'email':'patient@example.com'}})
ns['tr']=lambda k,lang=None: {'high_recommendation':'Consult a qualified healthcare professional for further assessment.','low_recommendation':'Maintain healthy habits and consult a healthcare professional if symptoms persist.'}.get(k,k)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'report_functions','exec'),ns)
report={'Patient ID':'26100101','Timestamp':'2026-10-01 04:00:00','First name':'Esam','Last name':'Mohamed','Age':22,'Gender':'Male','Marital status':'Single','Phone':'+256771234567','Country':'Uganda','Reported diabetes type':'Not sure','Result':'Low risk','Probability':'13.9%','Decision threshold':'0.5','Model version':'test-v1','Symptom narrative':'Patient reports itching and denies excessive thirst and frequent urination.','Glucose level':'Not recorded','Patient notes':'I have had a headache for two days.\nPlease review this additional symptom.'}
answers={'Itching':'Yes','Excessive thirst':'No','Frequent urination':'No'}
Path('tmp/pdfs').mkdir(parents=True,exist_ok=True)
data=ns['generate_pdf_report'](report,answers=answers);Path('tmp/pdfs/sample_report.pdf').write_bytes(data)
text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)
assert 'headache for two days' in text and '26100101' in text and '13.9%' in text
long_report={**report,'Patient notes':('Additional symptom described in detail. '*85)+'END OF NOTES','Timestamp':'2026-10-01 05:00:00'}
long_pdf=ns['generate_pdf_report'](long_report,answers=answers);Path('tmp/pdfs/long_report.pdf').write_bytes(long_pdf)
assert 'END OF NOTES' in ' '.join(' '.join(p.extract_text() for p in PdfReader(BytesIO(long_pdf)).pages).split())
records=[{'report':report,'answers':answers,'record_id':'one'},{'report':long_report,'answers':answers,'record_id':'two'}]
combined=ns['generate_patient_history_pdf']({},records);Path('tmp/pdfs/all_reports.pdf').write_bytes(combined)
combined_text=' '.join(' '.join(p.extract_text() for p in PdfReader(BytesIO(combined)).pages).split())
assert 'headache for two days' in combined_text and 'END OF NOTES' in combined_text
assert len(PdfReader(BytesIO(combined)).pages)==len(PdfReader(BytesIO(data)).pages)+len(PdfReader(BytesIO(long_pdf)).pages)
with tempfile.TemporaryDirectory() as temp:
    ns['HISTORY_DB']=temp+'/history.db';user={'email':'patient@example.com','patient_id':'26100101'}
    with ns['history_connection']() as conn:
        conn.execute('INSERT INTO patient_assessments VALUES (?,?,?,?,?)',('legacy',user['email'],user['patient_id'],report['Timestamp'],json.dumps({'report':report,'record_id':'legacy'})))
    assert ns['load_patient_history'](user)==[]
    for _ in range(2): ns['record_assessment'](user,report,answers,'new-assessment')
    saved=ns['load_patient_history'](user)
    assert len(saved)==1 and saved[0]['report']['Patient notes']==report['Patient notes']
    assert ns['load_patient_history']({'email':'other@example.com','patient_id':'26100101'})==[]
    assert ns['load_patient_history']({'email':user['email'],'patient_id':'different'})==[]
    for _ in range(3): assert len(ns['load_patient_history'](user))==1
    for bad in [{}, {**report,'Probability':'101%'}, {**report,'Timestamp':''}]:
        try: ns['record_assessment'](user,bad,answers)
        except ValueError: pass
        else: raise AssertionError('Incomplete assessment saved')
    ns['record_assessment'](user,{**report,'Probability':'0%'},answers,'zero')
    assert len(ns['load_patient_history'](user))==2
print('PASS: legacy exclusion, completed-only saves, idempotency, account isolation, 0% completed results, PDF notes, complete merged PDF, long-note pagination.')
# Test Arabic notes with the same report renderer and shaping dependencies.
import sys
sys.path.insert(0,str(Path('test_deps').resolve()))
arabic={**report,'Patient notes':'أشعر بصداع وتعب منذ يومين.\nلم يرد هذا العرض في الأسئلة.'}
data=ns['generate_pdf_report'](arabic,answers=answers)
Path('tmp/pdfs/arabic_notes.pdf').write_bytes(data)
assert len(PdfReader(BytesIO(data)).pages)==1
print('PASS: Arabic notes render into a valid PDF with shaping.')
# Exercise the history UI without rendering its old tables or saving on view.
from contextlib import nullcontext
class UI:
    def __init__(self): self.session_state={'lang':'en','user':{'email':'patient@example.com','patient_id':'26100101'}};self.downloads=[];self.open=True
    def columns(self,n): return [nullcontext() for _ in range(n)]
    def container(self,**kw): return nullcontext()
    def expander(self,*a,**kw): return nullcontext()
    def subheader(self,*a): pass
    def caption(self,*a): pass
    def write(self,*a): pass
    def markdown(self,*a,**kw): pass
    def button(self,*a,**kw): return self.open and kw.get('key')=='open_one'
    def download_button(self,*a,**kw):
        assert kw['mime']=='application/pdf' and kw['data'].startswith(b'%PDF-')
        self.downloads.append(kw['key'])
    def error(self,*a): raise AssertionError(a)
ui=UI();ns['st']=ui;ns['load_patient_history']=lambda user:records
ns['go_to']=lambda page:None
ns['log_action']=lambda *a:None
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_patient_history_page')
exec(compile(ast.Module(body=[node],type_ignores=[]),'history_ui','exec'),ns)
ns['render_patient_history_page']()
assert ui.session_state['open_history_record']=='one'
assert ui.downloads==['download_two','download_one','download_all_reports_pdf']
ui.open=False;ns['render_patient_history_page']()
print('PASS: open report, individual downloads, PDF-only combined download and repeat rendering.')
