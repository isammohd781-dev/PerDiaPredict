# Group disclosure access

## Reports selection

Reports now has a Country dropdown followed by a Patient dropdown. Patients are filtered using their current care country. A selected patient's completed assessments are read using their exact email and patient ID; no combined-country export is offered.

## One permit for a country - synthetic local tests

In your existing private `.streamlit/secrets.toml`, inside the same `[[DISCLOSURE_PERMITS]]` block, replace the individual `patient_id` and `patient_email` lines with:

    all_patients_in_country = true

Keep the country, permit reference, scope list, expiry, medical approval flag, approver, purpose and requesting-authority metadata. Restart the application. Authenticate once with the same restricted password and permit reference, then select other covered patients. The same temporary group grant works in Reports and Activity if the permit includes both scopes.

This flag explicitly covers ALL CURRENT AND FUTURE patients whose current care country matches that permit. For local testing use synthetic data only. With real data, a country-wide approval must truly authorize this entire set; merely typing this flag is not medical or legal approval. An independent custodian must verify and configure the actual approved scope.

## Safer option: an explicitly approved patient group

Instead of country-wide scope, remove individual patient_id/patient_email lines and specify:

    patients = [
        { patient_id = "DEMO-001", patient_email = "demo1@example.com" },
        { patient_id = "DEMO-002", patient_email = "demo2@example.com" }
    ]

Keep the country and other permit metadata. Only these exact ID/email pairs in the approved country are included. Future patients are not automatically added.

Individual permits are still supported. Old single-patient configurations remain valid and cannot access a different patient or scope.

The group grant expires after the original five-minute window or permit expiry, whichever comes first. Selecting another patient does not extend it. Leaving Reports/Activity for another administrator section locks it. Each patient read/export rechecks policy and logs the selected subject. Code/config/files owners remain outside the protection boundary described in SECURITY_SETUP.md.
