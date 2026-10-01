PerdiaPredict report update

1. Replace your existing diabetes_app.py with this file.
2. Copy the fonts folder into the same project folder. Keep all other project files.
3. Install the PDF dependencies:
   python -m pip install -r requirements_pdf.txt
4. If you deploy with Streamlit Cloud, add these three dependencies to your existing requirements.txt.
5. Restart the app.

The report opens inside the app. Each completed prediction has an individual PDF download.
The complete-history download contains the same medical-style reports in a single PDF.
Patient notes are optional and are saved with the submitted assessment, including in every export.
Notes do not change the model score.

The history view starts with predictions completed using this update. Previous unmarked records
are excluded from the view; existing database and Excel files are preserved.

All model assets, translations.py, screening_model.py and other existing project files are still required.
