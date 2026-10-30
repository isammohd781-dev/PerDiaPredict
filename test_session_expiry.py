"""Fixed 15-minute sessions: signed out at the deadline whether active or not, for every role."""
import sys, time, types

class State(dict):
    def __getattr__(self, k): return self[k]
    def __setattr__(self, k, v): self[k] = v

fake = types.ModuleType('streamlit')
fake.session_state = State()
fake.query_params = {}
sys.modules.setdefault('streamlit', fake)
import portal_runtime as rt
rt.st = fake
assert rt.SESSION_MINUTES == 15

for role, key, value in (('patient', 'user', {'email': 'p@example.com'}), ('doctor', 'doctor_user', {'id': 'd1'}), ('admin', 'admin_ok', True)):
    fake.session_state.clear(); fake.session_state.update(lang='en', dark_mode=True, page='x', _fixed_role=role)
    fake.session_state[key] = value
    rt.expire_idle(role)                                   # sign-in time recorded
    started = fake.session_state['_signed_in_at']
    fake.session_state['_signed_in_at'] = started - 14 * 60  # active for 14 minutes: still signed in
    rt.expire_idle(role)
    assert fake.session_state.get(key), role
    fake.session_state['_signed_in_at'] = started - 15 * 60  # 15 minutes reached, even while active
    rt.expire_idle(role)
    assert not fake.session_state.get(key), role
    assert fake.session_state['page'] == rt.ENTRY[role] and fake.session_state['lang'] == 'en' and fake.session_state['dark_mode'] is True
    assert '15 minutes' in fake.session_state['_ux_notice']
    assert '_signed_in_at' not in fake.session_state

# A browser reload from the on-screen timer shows the notice and stays signed out.
fake.session_state.clear(); fake.query_params['expired'] = '1'
rt.expire_idle('patient')
assert 'expired' not in fake.query_params and '15 minutes' in fake.session_state['_ux_notice']
fake.session_state.clear(); fake.query_params['expired'] = 'back'
rt.expire_idle('admin')
assert 'expired' not in fake.query_params and 'signed out' in fake.session_state['_ux_notice']
# Logo screen: first visit only, never on direct links, kept across sign-out.
fake.query_params.clear(); fake.session_state.clear(); fake.session_state['page'] = 'doctor_login'
rt.start_with_splash('doctor'); assert fake.session_state['page'] == 'splash'
fake.session_state['page'] = 'doctor_login'; rt.start_with_splash('doctor'); assert fake.session_state['page'] == 'doctor_login'
fake.session_state['doctor_user'] = {'id': 'd1'}; fake.session_state['_signed_in_at'] = 0
rt.expire_idle('doctor'); assert fake.session_state.get('_splash_seen') and fake.session_state['page'] == 'doctor_login'
fake.session_state.clear(); fake.session_state['page'] = 'admin'; fake.query_params['policy'] = 'privacy'
rt.start_with_splash('admin'); assert fake.session_state['page'] == 'admin'
fake.query_params.clear()
print('PASS: logo screen first; Back button signs out; 15-minute fixed session for patient, doctor and admin; reload notice.')
