# PerdiaPredict — Complete Update

## Installation and Update

1. Back up your current application folder.
2. Extract the update package and copy its files into the application folder. Keep your existing patient and account files: `accounts.xlsx`, `audit_log.xlsx`, `saved_reports.xlsx`, and `patient_history.db`. Also keep any existing images and fonts. The package does not include account or patient data.
3. Copy all three model files, `model_metadata.json`, and `screening_model.py` together with the application. Do not mix files from the old and new model versions.
4. Install the required dependencies and start the application:

```bash
python -m pip install -r requirements.txt
streamlit run diabetes_app.py
```

## Inference Verification

Run the following command to verify model inference:

```bash
python test_inference.py
```

## Training and Evaluation

To reproduce model training and evaluation, run:

```bash
python train_model.py
```

**Note:** This command overwrites the model and evaluation files in the current folder.

The following files document the evaluation:

- `MODEL_EVALUATION.md`: Results, limitations, and sources.
- `heldout_predictions.csv`: Detailed predictions for the held-out evaluation data.
- `model_metadata.json`: Evaluation metrics, model version, and file fingerprints.

The requirements pin scikit-learn to version **1.8.0**, which was used to produce the model.

`age_scaler.pkl` is retained for compatibility only. Age preprocessing is handled inside the model, so do not apply the scaler a second time.

## Educational Use

This application is an educational screening system. A diabetes diagnosis requires medical testing; the model's predicted percentage is not a diagnosis.

A change in the predicted percentage between different model versions does not establish that a patient's condition has improved or worsened.

## Report Design Update

The report header has a white background and displays the application logo, with the screening date and time shown separately. The header repeats on longer reports.

Patient details appear in a table, followed by the screening result, clinical presentation, and model information.

To apply this design update, copy the updated `diabetes_app.py` file and keep your existing `logo.png`.

UTF-8 encoding in `test_inference.py` has also been corrected for Windows compatibility. This report design update does not require model retraining.
