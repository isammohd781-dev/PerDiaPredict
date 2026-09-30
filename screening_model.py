"""Validated inference; probability comes directly from the tested pipeline."""
from pathlib import Path
import hashlib, json
import joblib, pandas as pd, numpy as np, sklearn

def load_screening_artifacts(model_path, columns_path):
    meta=json.loads(Path(model_path).with_name('model_metadata.json').read_text(encoding='utf-8'))
    if sklearn.__version__ != meta['sklearn_version']:
        raise ValueError('Install requirements.txt: scikit-learn must be '+meta['sklearn_version'])
    if hashlib.sha256(Path(model_path).read_bytes()).hexdigest()!=meta['model_sha256']:
        raise ValueError('Model and metadata do not match. Copy all release files together.')
    model=joblib.load(model_path); columns=joblib.load(columns_path)
    if columns!=meta['features'] or list(model.classes_)!=[0,1]:
        raise ValueError('Unexpected model schema or class labels.')
    return model,columns,meta

def encode_inputs(raw, columns, meta):
    age=raw.get('Age')
    if isinstance(age,bool) or not isinstance(age,(int,float,np.number)) or not np.isfinite(age):
        raise ValueError('A valid age is required.')
    lo,hi=meta['age_range']
    if not lo<=age<=hi: raise ValueError(f'This model supports ages {lo}–{hi} only.')
    if raw.get('Gender') not in ('Male','Female'): raise ValueError('The training data supports Male/Female only; do not substitute another value.')
    values={'Age':float(age),'Gender':int(raw['Gender']=='Male')}
    for c in columns:
        if c not in values:
            if raw.get(c) not in ('Yes','No'): raise ValueError('Missing or invalid answer: '+c)
            values[c]=int(raw[c]=='Yes')
    return pd.DataFrame([values],columns=columns)

def predict_screening(model, columns, meta, raw):
    frame=encode_inputs(raw,columns,meta)
    p=float(model.predict_proba(frame)[0,list(model.classes_).index(1)])
    if not np.isfinite(p) or not 0<=p<=1: raise ValueError('Invalid model probability.')
    return int(p>=meta['threshold']),p
