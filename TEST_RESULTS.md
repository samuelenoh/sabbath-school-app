# Verification record

Verified locally on Windows on 10–11 October 2026:

- 24 Python tests passed: 16 real HTTP/SQLite integration tests and 8 production WSGI/security/consent/UTC/configuration tests.
- 4 Chromium end-to-end tests passed in 6.0 seconds: all module screens, member creation/attendance persistence/notification dry run, assigned-teacher attendance, and mobile navigation/dialog layout.
- Production tests cover secure cookies and HTTPS origin enforcement, password whitespace, host checking, HEAD/method handling, body limits, distributed login throttling, invalid configuration/demo database rejection, strict consent booleans and early delivery-status replay.
- Integration tests cover atomic attendance, role isolation, stale edits, financial precision, receipt uniqueness, event capacity, consent withdrawal, message deduplication, notification review/cancellation, HMAC webhook authentication, monotonic delivery status and mocked Meta success/timeout handling.

Tests create temporary synthetic data and random local passwords. They never use a real church database or contact Meta. Source packaging excludes databases, secrets, installed dependencies and test artifacts.

Commands: `python -m unittest discover -s tests -v`, followed by `npm run test:e2e` after installing Playwright/Chromium. The production runtime smoke test uses Waitress with a temporary database.

Not verified: Docker build, installation of the Linux systemd/Caddy files, live WhatsApp credentials/templates/delivery, high-volume load and independent penetration testing. These require operator configuration and acceptance testing before real church use.

On 11 October 2026, [GitHub CI run 38118364342](https://github.com/samuelenoh/sabbath-school-app/actions/runs/38118364342) passed on application commit `c1afcf93673e4598d6ec307e75604cba93d62dfd`:

- PostgreSQL 16: 17 real HTTP integration checks passed in 3.468 seconds, including simultaneous workers claiming one notification once.
- SQLite/WSGI: 24 checks passed; 17 PostgreSQL checks were intentionally skipped in this separate job.
- Chromium: all 4 end-to-end workflows passed in 5.3 seconds.

This verifies 45 executed checks across the two CI jobs. Local PostgreSQL tests are skipped because this Windows host has no PostgreSQL server. Live Meta delivery remains unverified; hosted acceptance checks are recorded below.

## Hosted deployment: 11 October 2026

Render Free deployed application commit `3c0d33aa0b6accfe3f842bb6231c491abcb25f79` successfully at https://sabbath-school-app.onrender.com/. Python 3.12.12, Waitress and the PostgreSQL adapter built and started; schema initialization completed against the configured Neon database. Neon console confirms a Free project using PostgreSQL 18.

Verified from the public HTTPS endpoint:

- `/healthz` returns HTTP 200 with `{"status":"ok"}`.
- `/` returns HTTP 200 and the Sabbath School sign-in interface renders in the browser.
- `/api/me`, `/api/members` and `/api/offerings` return HTTP 401 without authentication.
- Content Security Policy prohibits framing and limits scripts/connect sources; X-Content-Type-Options is nosniff.

Not yet independently verified on the hosted instance: authenticated cookie flags, teacher/financial role checks, independent backup restore and notification-worker execution. Cookie and role behavior are covered by the automated WSGI/HTTP suites; backup and worker acceptance remain operator tasks. The worker remains initially disabled and WhatsApp is dry_run. Render Free can sleep; this is not a guarantee of uninterrupted production hosting.

Passwords and connection strings are excluded from this verification record. The administrator password should be unique, unshared and at least 16 characters; remove the bootstrap password environment variable after changing it through My account.

### Completed hosted acceptance and cleanup

At 06:56 UTC on 11 October 2026, Render confirmed a second successful deployment of `3c0d33a` after the bootstrap password environment variable was removed. No new password was entered by the agent; the user reported changing it through My account.

- The user-authenticated administrator session was available and remained authenticated after the actual redeploy.
- A clearly labelled synthetic event was created through the hosted UI and verified present after redeployment and a full app reload. This confirms database writes and Neon persistence across a service restart.
- The synthetic event was deleted afterward; the event list returned to empty. Audit history of the test remains.
- All ten hosted module screens rendered without an in-page alert: members, classes, attendance, lesson study, offerings, reports, events, outreach, WhatsApp and people/roles.
- The HTTPS health endpoint and app page returned HTTP 200 after the second deployment.
- The obsolete SSMS_ADMIN_PASSWORD environment variable was removed and saved in Render. Existing administrator records were retained; bootstrap configuration was not used to reset the live login password.

No provider payment or upgrade was selected. Render Free sleeping/quota limits and Neon Free quotas still apply. The hourly notification workflow is initially disabled until repository variables/secrets are configured, and live Meta credentials/templates/delivery are not enabled or verified. No real members, attendance or offerings were created during acceptance testing.

## Registers, quarterly books, annual report, programme and import update

Local verification on 11 October 2026:

- 38 executed Python checks passed: 26 real HTTP/SQLite checks, eight WSGI/security/configuration checks and four independent annual-arithmetic/import fixtures. The separate 27-check PostgreSQL suite is skipped locally because this host has no PostgreSQL server.
- Nine Chromium workflows passed in 15.3 seconds after integration fixes; subsequent final rerun includes the reviewed roster screen, all prior workflows, contributions with duplicate/zero handling, teacher book requests/staff tracking, independent template/week history, honest WhatsApp dry runs, annual print/CSV/privacy, and mobile layouts.
- Private local staging imported 24 photographed roster members and repeated the import with zero new records. Five rows carry source-review notes. Printed phone strings and unknown join dates were retained; no consent, login accounts or messages were created. Private data are outside the repository/source ZIP; automated fixtures and screenshots remain synthetic.
- New HTTP checks cover cross-class teacher access, concurrent contribution uniqueness, book status/version rules, report year/currency/privacy, template/week versioning, stale queued assignments, notification deduplication, consent, actual completion, additive restart preservation and atomic reviewed import conflicts.

Generated annual and quarter PDFs exercise browser print CSS. Source-only packaging excludes private roster previews, databases and test artifacts. Hosted and PostgreSQL results for this release are recorded after actual verification; the earlier hosted commit is not evidence that new screens are deployed.
