import ast, calendar, hashlib, hmac, os, re, secrets, sqlite3, tempfile, threading, unicodedata
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
source=Path(__file__).resolve().with_name('diabetes_app.py').read_text()
tree=ast.parse(source)
names={'normalize_email','normalize_person_name','valid_person_name','normalize_registration_phone','hash_password','verify_password','_cell_text','_rows_from_sheet','_save_rows','_import_old_sqlite','_load_rows','_update_account','create_user','authenticate','_authenticate_locked','generate_patient_id','_build_birth_date','age_from_birth_date'}
module=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
ns=dict(globals())
for n in tree.body:
    if isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'ACCOUNT_FIELDS','ACCOUNT_HEADERS','_FIELD_BY_HEADER','MARITAL_STATUS_ORDER','GENDER_OPTIONS','DIABETES_TYPE_KEYS','EMAIL_REGEX','MIN_PASSWORD_LEN','MAX_FAILED_LOGINS','LOCK_MINUTES','PBKDF2_ITERATIONS'} for t in n.targets):
        exec(compile(ast.Module(body=[n],type_ignores=[]),'constants','exec'),ns)
store={'lock':threading.RLock(),'mtime':None,'rows':[]}
ns['_accounts_store']=lambda:store
ns['log_action']=lambda *a:None
exec(compile(module,'isolated_backend','exec'),ns)
with tempfile.TemporaryDirectory() as temp:
    ns.update(ACCOUNTS_FILE=temp+'/accounts.xlsx',DB_FILE=temp+'/old.db',SAVE_FILE_XLSX=temp+'/reports.xlsx')
    phone=ns['normalize_registration_phone']
    for value in ['0771 234 567','+256771234567','00256771234567','٠٧٧١٢٣٤٥٦٧']:
        assert phone(value,'+256')=='+256771234567',value
    for value in ['+249771234567','abc','000','+256','123+456']:
        try: phone(value,'+256')
        except ValueError: pass
        else: raise AssertionError(value)
    assert ns['_build_birth_date'](29,2,2024)==date(2024,2,29)
    assert ns['_build_birth_date'](29,2,2025) is None
    assert ns['_build_birth_date'](31,4,2000) is None
    assert ns['_build_birth_date'](1,1,2100) is None
    def register(email='patient@example.com',**changes):
        args=dict(first_name='  Esam   Ali ',last_name='Mohamed',email=email,birth_date=date(2000,1,1),password='Secret123',gender='Male',marital_status='single',diabetes_type='not_sure',country='Uganda',dial_code='+256',phone='0771234567')
        args.update(changes)
        return ns['create_user'](**args)
    assert register()==(True,None)
    assert register(' PATIENT@EXAMPLE.COM ')==(False,'auth_email_taken')
    assert register('bad@example.com',password='        ')==(False,'reg_pw_short')
    assert register('bad',password='Secret123')==(False,'reg_email_invalid')
    assert register('bad@example.com',first_name='123')==(False,'reg_fill_all')
    user,status=ns['authenticate'](' PATIENT@EXAMPLE.COM ','Secret123')
    assert status=='ok' and user['first_name']=='Esam Ali'
    first_id=user['patient_id']
    assert first_id==date.today().strftime('%y%m%d')+'01'
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(register,['p2@example.com','p3@example.com','p4@example.com']))
    assert all(ok for ok,_ in results)
    rows=ns['_load_rows']()
    assert len({r['patient_id'] for r in rows})==4
    assert sorted(r['patient_id'] for r in rows)[-1].endswith('04')
    prefix=date.today().strftime('%y%m%d')
    pd.DataFrame({'Patient ID':[prefix+'08',prefix+'100']}).to_excel(ns['SAVE_FILE_XLSX'],index=False)
    assert ns['generate_patient_id']()==prefix+'101'
    assert register('report@example.com')==(True,None)
    store.update(mtime=None,rows=[])
    assert ns['authenticate']('report@example.com','Secret123')[1]=='ok'
    for _ in range(ns['MAX_FAILED_LOGINS']):
        status=ns['authenticate']('report@example.com','wrong')[1]
    assert status=='locked'
    assert ns['authenticate']('report@example.com','Secret123')[1]=='locked'
    print('PASS: phone formats, invalid dates/names/passwords/email, duplicate email, Excel persistence, concurrent registration, sequential patient IDs, report IDs, login and lockout.')
# Exercise the actual registration renderer with Streamlit's widget API simulated.
from contextlib import nullcontext
class FakeStreamlit:
    def __init__(self, values, submit=True):
        self.session_state={'lang':'en',**values};self.messages=[];self.submit=submit
    def container(self,**kw): return nullcontext()
    def columns(self,n): return [nullcontext() for _ in range(n)]
    def markdown(self,*a,**kw): pass
    def caption(self,*a,**kw): pass
    def text_input(self,*a,key,**kw): return self.session_state.get(key,'')
    def selectbox(self,label,options,key,index=0,**kw):
        val=self.session_state.get(key,options[index] if index is not None else None)
        if val is not None: assert val in options,(key,val)
        return val
    def checkbox(self,*a,key,**kw): return self.session_state.get(key,False)
    def button(self,*a,**kw): return self.submit and kw.get('type')=='primary'
    def error(self,message): self.messages.append(('error',message))
    def success(self,message): self.messages.append(('success',message))
render=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_register_page')
from types import SimpleNamespace
ui=dict(ns)
ui["care"]=SimpleNamespace(save_patient_location=lambda *a:None)
from html import escape as html_escape
ui["html_escape"]=html_escape
ui.update(auth_card=lambda *a,**kw:nullcontext(),tr=lambda key:key,edit_text=lambda key:key,
          _form_title=lambda *a:None,gender_label=lambda x:x,marital_status_label=lambda *a:a[0],
          month_label=lambda x:x,diabetes_type_label=lambda x:x,registration_text=lambda n:str(n),
          COUNTRY_DIAL_CODES=[('🇺🇬','Uganda','+256')],render_support_card=lambda:None)
exec(compile(ast.Module(body=[render],type_ignores=[]),'registration_ui','exec'),ui)
values=dict(reg_first='Esam',reg_last='Mohamed',reg_email='test@example.com',reg_gender='Male',
            reg_marital='single',reg_year=2000,reg_month=1,reg_day=1,reg_diabetes_type='not_sure',
            reg_country=('🇺🇬','Uganda','+256'),reg_phone='+256771234567',reg_pw='Secret123',reg_pw2='Secret123',reg_accept=True)
ui['st']=FakeStreamlit({});ui['create_user']=lambda *a:(_ for _ in ()).throw(AssertionError('Invalid input saved'))
ui['render_register_page']()
assert len(ui['st'].messages)>=2
for mode in ['ok','error']:
    pages=[];ui['st']=FakeStreamlit(values);ui['create_user']=lambda *a:(True,None)
    ui['authenticate']=lambda *a:({'id':1},'ok') if mode=='ok' else (None,'error')
    ui['go_to']=pages.append
    ui['render_register_page']()
    assert not any(t=='error' for t,_ in ui['st'].messages)
    if mode=='ok': assert pages==['main']
    else: assert pages==[] and ui['st'].messages[0][0]=='success'
ui['st']=FakeStreamlit({**values,'reg_month':4,'reg_day':31},submit=False)
ui['render_register_page']()
assert ui['st'].session_state['reg_day'] is None
print('PASS: registration rendering, empty submission, successful sign-in, sign-in failure recovery, invalid day reset.')
