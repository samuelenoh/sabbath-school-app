# Verification record

Verified locally on Windows on 10 October 2026:

- 21 Python tests passed: 16 real HTTP/SQLite integration tests and 5 production WSGI/security tests.
- 4 Chromium end-to-end tests passed in 6.1 seconds: all module screens, member creation/attendance persistence/notification dry run, assigned-teacher attendance, and mobile navigation/dialog layout.
- Production tests cover secure cookies and HTTPS origin enforcement, password whitespace, host checking, HEAD/method handling, body limits, distributed login throttling, invalid configuration/demo database rejection, strict consent booleans and early delivery-status replay.
- Integration tests cover atomic attendance, role isolation, stale edits, financial precision, receipt uniqueness, event capacity, consent withdrawal, message deduplication, notification review/cancellation, HMAC webhook authentication, monotonic delivery status and mocked Meta success/timeout handling.

Tests create temporary synthetic data and random local passwords. They never use a real church database or contact Meta. Source packaging excludes databases, secrets, installed dependencies and test artifacts.

Commands: `python -m unittest discover -s tests -v`, followed by `npm run test:e2e` after installing Playwright/Chromium. The production runtime smoke test uses Waitress with a temporary database.

Not verified: Docker build, installation of the Linux systemd/Caddy files, real cloud provisioning/HTTPS, live WhatsApp credentials/templates/delivery, high-volume load and independent penetration testing. These require operator configuration and acceptance testing before real church use.
