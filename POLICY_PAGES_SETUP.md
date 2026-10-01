# Separate policy pages
Replace diabetes_app.py and app_policies.py. Keep visual_accessibility.py from the previous fields update and all existing report modules, fonts, model assets, translations.py, logo and databases. Restart Streamlit.

Footer links open separate in-application Program policy and Privacy policy pages. Both are public without login. Back returns to the previous route. Reading the pages does not record consent or grant access. The policy pages contain 12 program sections and 16 privacy sections in English, Arabic, Spanish, Hindi and Chinese.

The documents accurately describe the development build, including local unencrypted records, incomplete event logging, consented multi-doctor access, externally verified disclosure requests, optional photos/notes, PDF copies, external WhatsApp support, and the lack of automatic deletion or verified guardian workflows. They do not constitute legal/clinical approval. Operator identity, privacy contact, address, processing basis/jurisdiction, hosting/vendors, retention and request/incident procedures remain deployment-specific.

Optionally configure the POLICY_* root keys in the included policy_settings.example.toml. Add them before any [[DISCLOSURE_PERMITS]] or other table in your existing .streamlit/secrets.toml; do not replace existing settings or share secrets publicly. Blank settings display an explicit development placeholder. Merely filling these descriptions does not implement encryption, deletion, clinical approval or legal procedures. Confirm that the descriptions match actual operations before public release.

Tests used synthetic adapters and covered both policy routes in five languages, return navigation, anonymous full-application access and preserved identity/session state. They do not verify external documents or production compliance.

Reference for privacy-notice coverage (not an assertion that UK law governs this deployment): https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/the-right-to-be-informed/what-privacy-information-should-we-provide/
