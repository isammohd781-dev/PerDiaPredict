# Separate portal verification — 2026-10-22

Scope: the uploaded PerdiaPredict-improved.zip; local source changes and synthetic tests. No deployment and no medical model changes.

Implemented:
- patient.py, doctor.py and admin.py have separate page routers and entry points.
- Each runs as an independent Streamlit server/session (8501, 8502, 8503).
- Role is fixed server-side by the entry script. Browser query parameters cannot change it.
- Foreign role identities are cleared, cross-role page navigation is rejected, and protected patient/doctor pages require their own sign-in.
- Doctor approval, consented patient follow-up, existing medical reports and administrator controls share the original storage.
- No user account/database file is bundled into the output.

Verification:
- All 11 check scripts passed: the 10 original test groups, with navigation expectations updated for independent portals, plus test_separate_pages.py.
- The new integration test uses the real entry files and model with synthetic accounts. It verifies independent login state, cross-role navigation rejection, shared administrator approval and account counts, patient consent and follow-up notes.
- Three actual HTTP servers started simultaneously on separate temporary test ports and returned successful health/home responses.
- AST comparison confirms registration, screening, report rendering, prediction, assessment saving and patient-history functions retain their implementation.
- Byte comparison confirms the model, metadata, translations and styling modules are unchanged from the uploaded archive.

The launcher includes a first-run dependency install, separate role shortcuts, an all-portals option, port-conflict checks and shutdown of its own child processes. Test suites do not certify external hosting, TLS, Windows policies, medical validity or every possible security issue. Existing storage-format and deployment limitations remain. No new claim about model accuracy is made.
