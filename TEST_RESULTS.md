# Verification record

Verified locally on Windows on 10–11 October 2026:

- 24 Python tests passed: 16 real HTTP/SQLite integration tests and 8 production WSGI/security/consent/UTC/configuration tests.
- 4 Chromium end-to-end tests passed in 6.0 seconds: all module screens, member creation/attendance persistence/notification dry run, assigned-teacher attendance, and mobile navigation/dialog layout.
- Production tests cover secure cookies and HTTPS origin enforcement, password whitespace, host checking, HEAD/method handling, body limits, distributed login throttling, invalid configuration/demo database rejection, strict consent booleans and early delivery-status replay.
- Integration tests cover atomic attendance, role isolation, stale edits, financial precision, receipt uniqueness, event capacity, consent withdrawal, message deduplication, notification review/cancellation, HMAC webhook authentication, monotonic delivery status and mocked Meta success/timeout handling.

Tests create temporary synthetic data and random local passwords. They never use a real church database or contact Meta. Source packaging excludes databases, secrets, installed dependencies and test artifacts.

Commands: `python -m unittest discover -s tests -v`, followed by `npm run test:e2e` after installing Playwright/Chromium. The production runtime smoke test uses Waitress with a temporary database.

Not verified: Docker build, installation of the Linux systemd/Caddy files, real cloud provisioning/HTTPS, live WhatsApp credentials/templates/delivery, high-volume load and independent penetration testing. These require operator configuration and acceptance testing before real church use.

On 11 October 2026, [GitHub CI run 38118364342](https://github.com/samuelenoh/sabbath-school-app/actions/runs/38118364342) passed on application commit `c1afcf93673e4598d6ec307e75604cba93d62dfd`:

- PostgreSQL 16: 17 real HTTP integration checks passed in 3.468 seconds, including simultaneous workers claiming one notification once.
- SQLite/WSGI: 24 checks passed; 17 PostgreSQL checks were intentionally skipped in this separate job.
- Chromium: all 4 end-to-end workflows passed in 5.3 seconds.

This verifies 45 executed checks across the two CI jobs. Local PostgreSQL tests are skipped because this Windows host has no PostgreSQL server. The cloud database, Render deployment and live Meta delivery remain unverified.
