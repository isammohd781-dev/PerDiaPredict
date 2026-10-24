"""Run: python test_inference.py. No patient files are read or written."""
from pathlib import Path
import ast,json
import numpy as np,pandas as pd
from screening_model import load_screening_artifacts,predict_screening
root=Path(__file__).resolve().parent
model,features,meta=load_screening_artifacts(root/'diabetes_model.pkl',root/'feature_columns.pkl')
df=pd.read_csv(root/'diabetes_data_upload.csv').drop_duplicates().reset_index(drop=True)
test=pd.read_csv(root/'heldout_predictions.csv')
for _,r in test.iterrows():
    raw=df.iloc[int(r.unique_row_index)][features].to_dict()
    # The heldout model evaluation includes out-of-training-range ages; deployment rejects them.
    if meta['age_range'][0]<=raw['Age']<=meta['age_range'][1]:
        label,p=predict_screening(model,features,meta,raw)
        assert np.isclose(p,r.probability) and label==r.predicted
raw={c:'No' for c in features if c not in ('Age','Gender')};raw.update(Age=45,Gender='Male')
_,p=predict_screening(model,features,meta,raw)
assert p>0, 'No-symptom screening must not be forced to zero.'
for key,value in [('Age',None),('Age',8),('Age',100),('Gender','Other'),('Itching',None)]:
    bad={**raw,key:value}
    try: predict_screening(model,features,meta,bad)
    except ValueError: pass
    else: raise AssertionError((key,value))
s=(root/'diabetes_app.py').read_text(encoding='utf-8');compile(s,'diabetes_app.py','exec')
assert 'symptom_factor' not in s and 'or 40' not in s
node=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=='compare_assessments')
env={'history_score':lambda r:float(r['report']['Probability'].strip('%'))}
exec(compile(ast.Module(body=[node],type_ignores=[]),'<test>','exec'),env)
a={'report':{'Probability':'80%','Model version':'old'},'answers':None}
b={'report':{'Probability':'20%','Model version':meta['model_version']},'answers':None}
lines=env['compare_assessments'](a,b)
assert any('Model version changed' in x for x in lines) and not any('percentage points' in x for x in lines)
print('PASS: heldout inference parity, no forced zero, unsupported inputs rejected, cross-version comparison protected.')
