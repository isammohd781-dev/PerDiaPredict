"""Separate, deny-by-default custodial disclosure gate for development deployment.
Local code/files owners can bypass this; production needs an independent custodian.
"""
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime,timezone
from io import BytesIO
from html import escape
import pandas as pd
import streamlit as st
import doctor_portal as care


def setting(key):
    try:
        value=st.secrets.get(key)
        if value is not None: return value
    except Exception: pass
    return os.environ.get('PERDIA_'+key,'')


def policy():
    password=str(setting('DISCLOSURE_PASSWORD') or '')
    raw=setting('DISCLOSURE_PERMITS')
    if not raw: raw=os.environ.get('PERDIA_DISCLOSURE_PERMITS_JSON','[]')
    try:
        permits=json.loads(raw) if isinstance(raw,str) else [dict(p) for p in raw]
        if not isinstance(permits,list): raise ValueError()
    except (ValueError,TypeError): permits=[]
    # No default credential, no inherited administrator password.
    if len(password)<16: raise PermissionError('Restricted access is not configured. An independent custodian must configure a separate password of at least 16 characters and approved permits.')
    fingerprint=hashlib.sha256((password+json.dumps(permits,sort_keys=True,default=str)).encode()).hexdigest()
    return password,permits,fingerprint


def utc_expiry(value):
    dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('Expiry must include a timezone')
    return dt.timestamp()


def subject_allowed(permit,patient):
    if permit.get('all_patients_in_country') is True:
        return True
    subjects=permit.get('patients')
    if isinstance(subjects,list):
        return any(isinstance(p,dict) and str(p.get('patient_id',''))==str(patient['patient_id'])
                   and care.email(p.get('patient_email'))==care.email(patient['email']) for p in subjects)
    return str(permit.get('patient_id',''))==str(patient['patient_id']) and care.email(permit.get('patient_email'))==care.email(patient['email'])


def approved_permit(permits,reference,patient,country,scope):
    for p in permits:
        try:
            if (str(p['permit_id'])==reference and p['medical_approved'] is True
                and subject_allowed(p,patient)
                and care.clean(p['country']).casefold()==care.clean(country).casefold()
                and care.clean(patient['country']).casefold()==care.clean(country).casefold()
                and scope in p['scopes'] and isinstance(p['scopes'],list)
                and all(care.clean(p.get(k)) for k in ('approved_by','authority','request_reference','purpose'))
                and utc_expiry(p['expires_at'])>time.time()):
                return p
        except (KeyError,TypeError,ValueError): pass
    raise PermissionError('Access denied. Credentials, patient details and an unexpired medical permit must match.')


def init_tables(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS disclosure_auth (scope TEXT PRIMARY KEY, failures INTEGER NOT NULL, locked_until REAL NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS disclosure_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_email TEXT NOT NULL, patient_id TEXT NOT NULL, country TEXT NOT NULL, permit_id TEXT NOT NULL, authority TEXT NOT NULL, request_reference TEXT NOT NULL, purpose TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL)')


def audit(patient,permit,action):
    with care.database() as conn:
        init_tables(conn)
        conn.execute('INSERT INTO disclosure_audit(patient_email,patient_id,country,permit_id,authority,request_reference,purpose,action,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
            (care.email(patient['email']),str(patient['patient_id']),patient['country'],permit['permit_id'],permit['authority'],permit['request_reference'],permit['purpose'],action,care.now()))


def authorize(password,reference,patient,country,scope):
    if st.session_state.get('admin_ok') is not True: raise PermissionError('Administrator sign-in required.')
    configured,permits,fingerprint=policy()
    failure=False
    with care.database() as conn:
        init_tables(conn)
        row=conn.execute('SELECT failures,locked_until FROM disclosure_auth WHERE scope=?',(scope,)).fetchone()
        if row and row['locked_until']>time.time(): raise PermissionError('Restricted access is temporarily locked after failed attempts. Try again later.')
        try:
            if not hmac.compare_digest(str(password).encode(),configured.encode()): raise PermissionError('Access denied.')
            permit=approved_permit(permits,reference,patient,country,scope)
        except PermissionError:
            failures=(row['failures'] if row and row['locked_until']==0 else 0)+1
            conn.execute('INSERT OR REPLACE INTO disclosure_auth VALUES(?,?,?)',(scope,failures,time.time()+600 if failures>=5 else 0))
            care.audit(conn,'restricted_access','disclosure_access_denied',scope)
            failure=True
        else: conn.execute('INSERT OR REPLACE INTO disclosure_auth VALUES(?,0,0)',(scope,))
    if failure: raise PermissionError('Access denied. Credentials, patient details and permit must match.')
    grant={'scope':scope,'patient_id':str(patient['patient_id']),'email':care.email(patient['email']),'country':country,'permit_id':reference,'expires':min(time.time()+300,utc_expiry(permit['expires_at'])),'fingerprint':fingerprint,'group':permit.get('all_patients_in_country') is True or isinstance(permit.get('patients'),list),'scopes':list(permit['scopes'])}
    audit(patient,permit,scope+'_access_granted')
    st.session_state['_disclosure_grant']=grant
    return grant


def validate(patient,scope):
    if st.session_state.get('admin_ok') is not True: raise PermissionError('Administrator sign-in required.')
    _,permits,fingerprint=policy()
    g=st.session_state.get('_disclosure_grant') or {}
    if ((scope not in g.get('scopes',[]) if g.get('group') else g.get('scope')!=scope)
        or (not g.get('group') and (g.get('patient_id')!=str(patient['patient_id']) or g.get('email')!=care.email(patient['email'])))
        or g.get('country')!=patient['country'] or g.get('fingerprint')!=fingerprint or g.get('expires',0)<=time.time()):
        raise PermissionError('This patient is locked. Authenticate with a matching permit.')
    return approved_permit(permits,g['permit_id'],patient,patient['country'],scope)


def patients(rows):
    with care.database() as conn:
        locations={care.email(r['email']):dict(r) for r in conn.execute('SELECT * FROM patient_locations')}
    result=[]
    for row in rows:
        p=dict(row);loc=locations.get(care.email(p.get('email')),{})
        p['country']=loc.get('country') or p.get('country') or 'Not recorded'
        if p.get('patient_id') and p.get('email'): result.append(p)
    return result


def gate(patient,scope):
    try:
        permit=validate(patient,scope)
    except PermissionError:
        st.info('Locked: separate custodial password and an approved medical disclosure permit are required.')
        try: policy()
        except PermissionError as exc: st.warning(str(exc));return None
        with st.form('disclosure_'+scope,clear_on_submit=True):
            password=st.text_input('Restricted access password',type='password',key='restricted_password_'+scope)
            reference=st.text_input('Approved medical permit reference',max_chars=100)
            st.caption('A typed reference alone grants no access. The independent custodian must have registered it in the access policy.')
            unlock=st.form_submit_button('Verify and unlock this patient',type='primary')
        if unlock:
            try: authorize(password,reference.strip(),patient,patient['country'],scope);st.rerun()
            except PermissionError as exc: st.error(str(exc))
        return None
    st.success('Temporary group access (maximum 5 minutes). Only subjects covered by this permit can be selected.' if st.session_state.get('_disclosure_grant',{}).get('group') else 'Temporary access to this patient only (maximum 5 minutes).')
    st.caption(f"Authority: {permit['authority']} | Request: {permit['request_reference']} | Medical permit: {permit['permit_id']}")
    if st.button('Lock restricted access',key='restricted_lock_'+scope):
        st.session_state.pop('_disclosure_grant',None);st.rerun()
    return permit


def render_reports(app,rows):
    choices=patients(rows)
    country=st.selectbox('Patient country',sorted({p['country'] for p in choices}),index=None,key='restricted_report_country')
    choices=[p for p in choices if p['country']==country]
    patient=st.selectbox('Patient',choices,index=None,
        format_func=lambda p:f"{p.get('first_name','')} {p.get('last_name','')} | {p['patient_id']}",key='restricted_report_patient')
    if not patient:return
    permit=gate(patient,'reports')
    if not permit:return
    permit=validate(patient,'reports')
    audit(patient,permit,'reports_list_viewed')
    records=app['load_patient_history'](patient)
    st.caption('Completed assessments for the authorized patient only. Old unverified Excel rows are excluded.')
    if not records:st.info('No completed reports for this patient.');return
    record=st.selectbox('Patient assessment',records,format_func=lambda r:r['report'].get('Timestamp',''))
    if st.button('Open authorized report'):
        permit=validate(patient,'reports');audit(patient,permit,'report_opened')
        app['render_medical_report'](record['report'],record.get('answers'))
    if st.button('Prepare all patient reports PDF',type='primary'):
        permit=validate(patient,'reports')
        data=app['generate_patient_history_pdf'](patient,records)
        audit(patient,permit,'reports_pdf_prepared')
        st.download_button('Download authorized reports PDF',data,file_name='Authorized_Patient_Reports.pdf',mime='application/pdf')


def activity(app,patient):
    validate(patient,'activity')
    events=[]
    path=app['AUDIT_LOG_FILE']
    if os.path.exists(path):
        frame=pd.read_excel(path,engine='openpyxl').fillna('')
        for row in frame.to_dict('records'):
            try: account_matches=float(patient.get('id',-2))>0 and float(row.get('Account ID',-1))==float(patient.get('id',-2))
            except (TypeError,ValueError): account_matches=False
            detail=str(row.get('Details',''))
            target_matches=detail in ('email='+care.email(patient['email']),'target_email='+care.email(patient['email']))
            if account_matches or target_matches:
                events.append({'Time':str(row.get('Timestamp','')),'Source':'Patient account','Actor':str(row.get('Account ID','')),'Action':str(row.get('Action','')),'Details':detail})
    owner=care.email(patient['email'])
    with care.database() as conn:
        for row in conn.execute('SELECT * FROM care_audit WHERE actor=? OR target=? ORDER BY id',(owner,owner)):
            events.append({'Time':row['created_at'],'Source':'Care team','Actor':row['actor'],'Action':row['action'],'Details':row['target']})
        init_tables(conn)
        for row in conn.execute('SELECT * FROM disclosure_audit WHERE patient_email=? AND patient_id=? ORDER BY id',(owner,str(patient['patient_id']))):
            events.append({'Time':row['created_at'],'Source':'Restricted disclosure','Actor':'Custodial access','Action':row['action'],'Details':f"Permit {row['permit_id']} | Request {row['request_reference']} | {row['authority']}"})
    def event_time(event):
        try:
            dt=datetime.fromisoformat(event['Time'].replace('Z','+00:00'))
            return dt.timestamp()
        except (ValueError,TypeError): return 0
    return sorted(events,key=event_time,reverse=True)


def activity_pdf(app,patient,permit,events):
    validate(patient,'activity')
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Spacer
    from report_locale import text
    lang=st.session_state.get('lang','en')
    font=app['_report_font']()
    style=ParagraphStyle('Activity',fontName=font,fontSize=9,leading=13,textColor=colors.HexColor('#243449'),alignment=2 if lang=='ar' else 0)
    heading=ParagraphStyle('Heading',parent=style,fontSize=18,leading=24,spaceAfter=14)
    para=lambda value:app['_report_paragraph'](text(value,lang),style)
    story=[app['_report_paragraph'](text('PATIENT ACTIVITY RECORD',lang),heading)]
    for key,val in [('Patient ID',patient['patient_id']),('Country',patient['country']),('Authority',permit['authority']),('Request reference',permit['request_reference']),('Medical permit',permit['permit_id']),('Approved by',permit['approved_by']),('Purpose',permit['purpose']),('Generated UTC',care.now())]:story.append(para(f'{text(key,lang)}: {val}'))
    story.extend([Spacer(1,14),para('Contains recorded application events only. It is not proof of all user actions or legal authorization.'),Spacer(1,14)])
    rows=[[para('Time / source'),para('Action / actor / details')]]
    for event in events:rows.append([para(event['Time']+'\n'+event['Source']),para(event['Action']+'\nActor: '+str(event.get('Actor','Not recorded'))+'\n'+event['Details'])])
    if not events:rows.append([para('No recorded events'),para('')])
    if lang=='ar': rows=[list(reversed(row)) for row in rows]
    table=Table(rows,colWidths=[340,170] if lang=='ar' else [170,340],repeatRows=1,hAlign='RIGHT' if lang=='ar' else 'LEFT',splitInRow=1)
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4f2f1')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f8fc')]),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dbe4eb')),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.append(table)
    buffer=BytesIO()
    def footer(canvas,doc):
        from report_branding import draw_report_header
        draw_report_header(canvas,A4[0],A4[1],'PATIENT ACTIVITY RECORD | CONFIDENTIAL',lang,app['_report_paragraph'])
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(42,25,'CONFIDENTIAL | Authorized disclosure');canvas.drawRightString(A4[0]-42,25,f'Page {doc.page}');canvas.restoreState()
    SimpleDocTemplate(buffer,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=94,bottomMargin=48).build(story,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()


def render_activity(app,rows):
    choices=patients(rows)
    country=st.selectbox('Country',sorted({p['country'] for p in choices}),index=None,key='activity_country')
    choices=[p for p in choices if p['country']==country]
    patient=st.selectbox('Patient',choices,index=None,format_func=lambda p:f"{p.get('first_name','')} {p.get('last_name','')} | {p['patient_id']}",key='activity_patient')
    if not patient:return
    permit=gate(patient,'activity')
    if not permit:return
    audit(patient,permit,'activity_viewed')
    events=activity(app,patient)
    st.caption(f"{len(events)} recorded events | Patient ID: {patient['patient_id']} | Country: {patient['country']}")
    if events:st.dataframe(pd.DataFrame(events),hide_index=True,use_container_width=True)
    else:st.info('No recorded events for this patient.')
    if st.button('Prepare all recorded activity PDF',type='primary'):
        permit=validate(patient,'activity')
        audit(patient,permit,'activity_pdf_prepared')
        events=activity(app,patient)
        data=activity_pdf(app,patient,permit,events)
        st.download_button('Download all recorded activity PDF',data,file_name='Authorized_Patient_Activity.pdf',mime='application/pdf')
