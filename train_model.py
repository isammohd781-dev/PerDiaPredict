"""Reproducible group-isolated evaluation; no model selection on final test."""
from pathlib import Path
import json, hashlib, math
import numpy as np
import pandas as pd
import sklearn, joblib
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, brier_score_loss, log_loss, confusion_matrix
ROOT=Path(__file__).resolve().parent
FEATURES=['Polyuria','Polydipsia','Age','Gender','partial paresis','sudden weight loss','Irritability','delayed healing','Alopecia','Itching']
def make_model(kind, X, y, groups):
    transform=ColumnTransformer([('age',MinMaxScaler(),['Age'])],remainder='passthrough')
    estimator=LogisticRegression(C=1,max_iter=2000,random_state=42) if kind=='logistic' else RandomForestClassifier(n_estimators=300,random_state=42,n_jobs=-1)
    pipe=Pipeline([('preprocess',transform),('classifier',estimator)])
    if kind=='forest_sigmoid':
        folds=list(StratifiedGroupKFold(3,shuffle=True,random_state=71).split(X,y,groups))
        for a,b in folds: assert not set(groups[a])&set(groups[b])
        return CalibratedClassifierCV(pipe,method='sigmoid',cv=folds)
    return pipe

def metrics(y,p):
    prediction=p>=.5
    tn,fp,fn,tp=confusion_matrix(y,prediction,labels=[0,1]).ravel()
    n=len(y); a=accuracy_score(y,prediction); z=1.96
    centre=(a+z*z/(2*n))/(1+z*z/n)
    margin=z*math.sqrt(a*(1-a)/n+z*z/(4*n*n))/(1+z*z/n)
    return dict(n=n,accuracy=a,accuracy_95CI=[centre-margin,centre+margin],precision=precision_score(y,prediction,zero_division=0),recall=recall_score(y,prediction),specificity=float(tn/(tn+fp)),f1=f1_score(y,prediction),roc_auc=roc_auc_score(y,p),brier=brier_score_loss(y,p),log_loss=log_loss(y,p),confusion_matrix=[[int(tn),int(fp)],[int(fn),int(tp)]])

def main():
    raw=pd.read_csv(ROOT/'diabetes_data_upload.csv')
    df=raw.drop_duplicates().reset_index(drop=True)
    assert not df.isna().any().any()
    X=df[FEATURES].copy()
    X['Gender']=X.Gender.map({'Female':0,'Male':1})
    for c in FEATURES:
        if c not in ['Age','Gender']: X[c]=X[c].map({'No':0,'Yes':1})
    assert not X.isna().any().any()
    y=df['class'].map({'Negative':0,'Positive':1}).to_numpy()
    groups=pd.factorize(pd.MultiIndex.from_frame(X))[0]
    dev,test=next(StratifiedGroupKFold(5,shuffle=True,random_state=42).split(X,y,groups))
    assert not set(groups[dev])&set(groups[test])
    xd=X.iloc[dev].reset_index(drop=True); yd=y[dev]; gd=groups[dev]
    folds=list(StratifiedGroupKFold(5,shuffle=True,random_state=23).split(xd,yd,gd))
    scores={}
    for kind in ['forest','forest_sigmoid','logistic']:
        p=np.zeros(len(yd))
        for a,b in folds:
            assert not set(gd[a])&set(gd[b])
            m=make_model(kind,xd.iloc[a],yd[a],gd[a]); m.fit(xd.iloc[a],yd[a]); p[b]=m.predict_proba(xd.iloc[b])[:,1]
        scores[kind]=metrics(yd,p)
        print(kind,json.dumps(scores[kind]),flush=True)
    selected=min(scores,key=lambda k:(scores[k]['brier'],scores[k]['log_loss']))
    model=make_model(selected,xd,yd,gd); model.fit(xd,yd)
    p=model.predict_proba(X.iloc[test])[:,1]
    heldout=metrics(y[test],p)
    joblib.dump(model,ROOT/'diabetes_model.pkl')
    joblib.dump(FEATURES,ROOT/'feature_columns.pkl')
    # Compatibility artifact only: actual scaling occurs within the saved pipeline.
    meta={'model_version':'PP-grouped-2026-09-30-v1','sklearn_version':sklearn.__version__,'preprocessing_in_model':True,'selected_model':selected,'features':FEATURES,'threshold':.5,'age_range':[int(xd.Age.min()),int(xd.Age.max())],'clinically_validated':False,'model_sha256':hashlib.sha256((ROOT/'diabetes_model.pkl').read_bytes()).hexdigest(),'dataset_sha256':hashlib.sha256((ROOT/'diabetes_data_upload.csv').read_bytes()).hexdigest(),'original_rows':len(raw),'unique_full_rows':len(df),'unique_feature_groups':len(set(groups)),'development_rows':len(dev),'test_rows':len(test),'selection':'minimum development group-CV Brier score; tie-break log loss','development_cv':scores,'heldout':heldout}
    (ROOT/'model_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    pd.DataFrame({'unique_row_index':test,'group':groups[test],'actual':y[test],'probability':p,'predicted':(p>=.5).astype(int)}).to_csv(ROOT/'heldout_predictions.csv',index=False)
    print('SELECTED',selected,'HELDOUT',json.dumps(heldout),flush=True)
if __name__=='__main__': main()
