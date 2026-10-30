# App Store and Google Play readiness — 2026-10-30

## Done in the code
| Requirement | Store | Status |
|---|---|---|
| In-app account deletion (full deletion, not deactivation) | Apple 5.1.1(v) and Google Play | Done: Edit profile → Delete account |
| Web link to delete the account without opening the app | Google Play (Data safety form) | Done: `<patient-app-url>/?account=delete` |
| Identity check before deletion | Expected in practice | Done: password + confirmation tick, locked after 5 wrong attempts |
| Download a copy of personal data | GDPR and good practice | Done: "Download my data" (JSON, no password data) |
| Privacy policy and terms inside the app | Both | Already present; deletion paragraph updated (EN and AR) |
| Notice that the app does not diagnose | Apple 1.4.1 (health apps) | Already present |
| Support contact | Both | Present (WhatsApp) |
| Acceptance of terms at registration | Both | Present |
| Sign out + automatic sign-out | — | Present |

### Exactly what is deleted
The account, profile photo, screening history, rows in saved_reports.xlsx, care location, doctor connections, doctors' notes, and the legacy account copy in perdiapredict.db if present.
Security logs and disclosure records are kept, but the email is replaced by an anonymous reference (`deleted-account-…`). A deleted patient ID is never given to a new patient. SQLite stores use secure_delete so deleted rows do not remain in the file.

## Needs your decision or work outside the code
1. **The app is currently a Streamlit website.** Apple usually rejects an app that is only a website inside a WebView (guideline 4.2). Google is more lenient. For Apple you need a real app (for example Flutter or React Native) that talks to the server, or at least native features (notifications, offline use, …).
2. **Deploy on HTTPS** with a fixed URL (nginx template in deploy/). Both stores require a public privacy policy URL and an account deletion URL.
3. **Google Play Console → Data safety:** declare collection of name, email, phone, date of birth, health information and photos. Add the deletion link above.
4. **App Store Connect → App Privacy:** the same data, "linked to the user", "not used for tracking".
5. **Demo account for the reviewer** (email and password) in the review notes.
6. **Age rating:** the app accepts a "child" status. If it targets children, Google's Families policy and Apple's Kids category apply with extra rules. Simplest: rate the app 17+ / adults, and obtain guardian consent outside the app.
7. **Health data:** Apple forbids using it for advertising or selling it (5.1.3). The app does neither; state this in the privacy policy after legal review.
8. **Server backups:** deletion does not reach them. Set a backup expiry and state it in the policy.
9. **Translations:** deletion screens are in Arabic and English; other languages show English. The updated policy paragraph is in Arabic and English only; Spanish, Hindi and Chinese still have the old text.
