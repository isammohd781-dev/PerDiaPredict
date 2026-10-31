# PerdiaPredict model evaluation report

Model version: `PP-grouped-2026-09-30-v1`. Selected model: Random Forest, 300 trees. Fixed threshold 0.5.

## Actual results on the held-out test set

| Metric | Result |
|---|---:|
| Records | 50 |
| Accuracy | 92.00% (46/50) |
| Approximate 95% confidence interval for accuracy | 81.2%–96.8% |
| Sensitivity (recall) | 97.14% (34/35) |
| Specificity | 80.00% (12/15) |
| Precision | 91.89% |
| F1 | 0.9444 |
| ROC AUC from probabilities | 0.9638 |
| Brier (lower is better) | 0.0732 |
| Log loss (lower is better) | 0.2320 |

34 true positives, 12 true negatives, 3 false positives, and one positive case the model missed.

## Method

The original file has 520 rows, of which 269 are exact duplicates. 251 distinct observations remained, forming 242 distinct groups of the ten inputs used. These are not confirmed counts of independent patients; the file contains no patient identifiers.

We removed exact duplicate rows, then grouped identical ten-input combinations together. The outer split is StratifiedGroupKFold with five folds, shuffle and seed=42; the first fold is the final test set (50) and the rest is for development (201). No group is shared between training and test. Models were compared with five-fold grouped validation inside development (seed=23). Sigmoid calibration uses three additional grouped folds (seed=71). Age processing is inside the pipeline and fitted separately in each fold. We chose the lowest development Brier, with log loss as tie-breaker, before computing the final test. The threshold and seed were not changed based on the test result.

| Model | Development validation accuracy | Brier | Log loss |
|---|---:|---:|---:|
| forest | 90.55% | 0.0674 | 0.2267 |
| forest_sigmoid | 91.04% | 0.0699 | 0.2392 |
| logistic | 88.06% | 0.0906 | 0.2847 |

Calibration did not improve the probability selection criterion, so the shipped version uses the plain Random Forest. We do not claim it is medically calibrated. Brier combines discrimination and probability quality and does not prove calibration on its own.

![Exploratory reliability](../model/reliability.png)

The curve is exploratory because the test set is small. The displayed probability is not the model's 92% accuracy, nor a confirmed chance that a specific individual has diabetes. The data sample comes from a single hospital in Sylhet, Bangladesh, and does not represent diabetes prevalence in the general population. Removing duplicates changes record weights and class balance. External testing with independent patient information and laboratory results, and a calibration review, are required before clinical use. This test does not demonstrate generalisation to another country, estimation of diabetes type, or future risk.

The ten features come from the previous system; their historical selection may have used the full dataset, so this is a held-out test within the current retraining, not a fully independent clinical study. The accuracy of the old model cannot be confirmed because its original split was not kept. We do not claim a measured improvement over the old model.

## Program changes

- Removed multiplying the percentage by a symptom-count factor and removed the automatic 0% when no symptoms are present.
- The percentage comes directly from the pipeline evaluated above. The tested development model was saved and was not retrained on the test set.
- Missing age is not replaced with 40, and an unsupported gender is not automatically replaced with male. The operating age range is 16–85, matching the training range. The research test included all held-out records even if age was outside the training range; the app refuses to estimate such cases.
- The model version, probability method and threshold are saved with the report. When versions differ, a difference in percentages is not interpreted as a change in the patient's health.
- Profile editing, history and report aggregation were kept, and saving happens only after a successful screening or a retry of that save.
- The model uses only the ten features in the metadata. Laboratory glucose and the extra questions are useful for the report but do not change the probability in this model; nothing should claim otherwise.

## Verification and limits

App probabilities matched the test results, rejection of unsupported inputs worked, zero is not forced, and version comparison protection works. Tests for saving a screening, preventing duplicates, isolating patient history and generating PDFs passed. All files were syntax-checked. The full Streamlit interface was not run in that environment because the package was not available.

## Sources

- UCI, Islam et al. (2020), DOI: 10.24432/C5VG8H, Early Stage Diabetes Risk Prediction, CC BY 4.0 licence: https://archive.ics.uci.edu/dataset/529/early+stage+diabetes+risk+prediction+dataset
- scikit-learn, Probability calibration: https://scikit-learn.org/stable/modules/calibration.html
- scikit-learn, Common pitfalls: https://scikit-learn.org/stable/common_pitfalls.html
- NIDDK, Diabetes Tests & Diagnosis: https://www.niddk.nih.gov/health-information/diabetes/overview/tests-diagnosis

The internet was used to check the evaluation method and the data source, not to add undocumented training cases or raise the percentage manually.
