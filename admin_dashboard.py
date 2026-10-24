"""Administrator dashboard presentation; uses existing application storage/actions."""
import json
from html import escape
import pandas as pd
import streamlit as st
import doctor_portal as care
import app_experience as ux
import disclosure_access as disclosure


def render(app):
    if st.session_state.get('admin_ok') is not True:
        st.error('Administrator sign-in required.')
        return
    rows=app['_load_rows']()
    with care.database() as conn:
        doctors=[care.public_doctor(row) for row in conn.execute('SELECT * FROM doctors ORDER BY created_at DESC')]
        links=[dict(row) for row in conn.execute('SELECT status,doctor_id,patient_email FROM care_links')]
    completed=0
    with app['history_connection']() as conn:
        for row in conn.execute('SELECT payload FROM patient_assessments'):
            try:
                if json.loads(row[0]).get('completed_prediction') is True: completed+=1
            except (ValueError,TypeError): pass
    approved=sum(d['status']=='approved' for d in doctors)
    pending=sum(d['status']=='pending' for d in doctors)
    st.markdown('<div class="admin-banner"><h1>Administration</h1><p>Patient accounts, doctor reviews and activity.</p></div>',unsafe_allow_html=True)
    nav,body=st.columns([1.15,4.85],gap='large')
    with nav:
        with st.container(key='admin_menu'):
            st.caption('Sections')
            section=st.radio('Admin navigation',['Overview','Patients','Doctors','Reports','Activity'],key='admin_section',label_visibility='collapsed')
            grant=st.session_state.get('_disclosure_grant')
            required_scope={'Reports':'reports','Activity':'activity'}.get(section)
            if grant and (not required_scope or (required_scope not in grant.get('scopes',[]) if grant.get('group') else grant.get('scope')!=required_scope)):
                st.session_state.pop('_disclosure_grant',None)
            st.divider()
            st.caption('Private administrator session')
            if st.button('Lock dashboard',key='admin_lock',use_container_width=True):
                st.session_state['admin_ok']=False
                st.session_state.pop('admin_pw',None)
                st.session_state.pop('_disclosure_grant',None)
                st.session_state.pop('_pending_confirmation',None)
                st.rerun()
    with body:
        with st.container(key='admin_content'):
            st.subheader(section)
            if section=='Overview':
                a,b=st.columns(2);c,d=st.columns(2)
                a.metric('Registered patients',len(rows));b.metric('Approved doctors',approved)
                c.metric('Doctors awaiting review',pending);d.metric('Completed assessments',completed)
                with st.container(border=True):
                    st.subheader('Your next actions')
                    if pending: st.warning(f'{pending} doctor account(s) need a professional review.')
                    else: st.success('No doctor accounts are waiting for review.')
                    st.caption(f"{sum(l['status']=='active' for l in links)} active care connections · {sum(l['status']=='pending' for l in links)} patient requests awaiting doctor acceptance")
                    a,b=st.columns(2)
                    if a.button('Review doctors',key='admin_review_shortcut',use_container_width=True):
                        st.session_state['_admin_next_section']='Doctors';st.rerun()
                    if b.button('View patients',key='admin_patients_shortcut',use_container_width=True):
                        st.session_state['_admin_next_section']='Patients';st.rerun()
                with st.container(border=True):
                    st.subheader('Recent doctor registrations')
                    if doctors:
                        st.dataframe(pd.DataFrame([{'Name':d['name'],'Specialty':d['specialty'],'Hospital':d['hospital'],'Country':d['country'],'Status':d['status']} for d in doctors[:5]]),hide_index=True,use_container_width=True)
                    else: st.info('New registrations will appear here.')
                st.caption('Counts reflect stored accounts and completed assessments. Review decisions do not verify credentials automatically.')
            elif section=='Patients':
                st.caption('Search the account directory. Medical data and credential recovery are separated from ordinary administrator access.')
                app['render_accounts_admin']()
            elif section=='Doctors':
                a,b,c=st.columns(3)
                a.metric('All doctors',len(doctors));b.metric('Approved',approved);c.metric('Awaiting review',pending)
                care.render_doctor_admin()
            elif section=='Reports':
                disclosure.render_reports(app,rows)
            elif section=='Activity':
                disclosure.render_activity(app,rows)


def search_frame(frame,query):
    if not str(query).strip(): return frame
    mask=frame.fillna('').astype(str).apply(lambda col:col.str.contains(str(query).strip(),case=False,regex=False)).any(axis=1)
    return frame[mask]
