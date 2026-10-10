# SDA Sabbath School Management System

A runnable, single-church web application with a Python backend, SQLite persistence, and a responsive JavaScript interface. Local demonstrations need Python 3.10+ only. Production uses Waitress (one pinned dependency). Node.js is used for browser tests.

The prior `/mnt/data/ssms-app` and `/mnt/data/ssms-web-app.zip` were unavailable on this Windows host. The referenced conversation returned unresolved content-reference placeholders. This implementation therefore follows the modules explicitly requested in the current message; it does not claim to reproduce requirements hidden inside those placeholders.

## Quick start

Extract the source archive, open a terminal in `ssms-app`, and run:

```sh
export SSMS_DEMO_PASSWORD='<choose a unique local-only password of at least 12 characters>'
python server.py --demo
```

On PowerShell, set `$env:SSMS_DEMO_PASSWORD = '<your unique local-only password>'` before running `python server.py --demo`.

Open http://127.0.0.1:8000. Demonstration accounts use the password **you supplied**, with these synthetic usernames:

| Email | Role |
|---|---|
| admin@ssms.local | Administrator |
| secretary@ssms.local | Secretary |
| teacher@ssms.local | Berean Fellowship teacher |
| teacher2@ssms.local | Cornerstone Youth teacher |
| treasurer@ssms.local | Treasurer |
| viewer@ssms.local | Viewer |

Demo seed data are synthetic. No demonstration member starts with WhatsApp consent or a phone number. The browser-tested working directory may contain extra synthetic test records; the source ZIP excludes all database files and starts clean.

`--demo` seeds data only when the database has no users. Restarting preserves existing records. Do not use demo accounts for a real church. For another port, use `--port 8010`.

## Start a fresh church database

Configure environment variables before first startup. `.env.example` is a reference; the app does **not** automatically load `.env` files.

PowerShell:

```powershell
$env:SSMS_ADMIN_EMAIL = 'admin@yourchurch.org'
$env:SSMS_ADMIN_PASSWORD = '<choose a unique password of at least 12 characters>'
$env:SSMS_DB = './data/church.sqlite3'
python server.py
```

Linux/macOS:

```sh
export SSMS_ADMIN_EMAIL='admin@yourchurch.org'
export SSMS_ADMIN_PASSWORD='<choose a unique password of at least 12 characters>'
export SSMS_DB='./data/church.sqlite3'
python server.py
```

1. Sign in as administrator and create teacher and operational accounts in **People & roles**.
2. Create classes and assign an active teacher to each class. One teacher can teach multiple classes; each class has one primary teacher.
3. Add members to their classes. Enter international phone numbers and record consent only when a member has actually given it.
4. Teachers sign in with their own accounts and mark attendance for a Saturday. They can read and manage lessons and outreach for their assigned classes.
5. Record offerings, create events, register members, and use Reports for participation and CSV exports.
6. Change temporary passwords in **My account**. This signs out existing sessions.

## Implemented modules

| Module | Behavior |
|---|---|
| Overview | Current roster, attendance rate, real recorded attendance trend, classes, upcoming events, outreach impact |
| Members | Create/edit/search/filter, contact details, birthday, visitor/active/inactive status, class assignment, recorded WhatsApp consent |
| Classes | Create/edit, primary teacher, age group, meeting space, active status; archive classes with history |
| Attendance | Server-side assignment authorization, Saturday and future-date validation, present/absent/excused, study checkbox, notes, same-date updates, atomic batches |
| Lesson study | Class-specific lesson title, quarter, week, scripture, discussion summary, HTTPS resource link; study completion via attendance |
| Offerings | Integer minor-unit accounting (two decimal places), currency, category, receipt uniqueness, notes, audited corrections |
| Reports | Date filters, class participation, study and outreach statistics, currency-separated offering totals, attendance/offerings CSV, print view |
| Events | Dates, time, location, description, capacity, idempotent member registration and cancellation |
| Outreach | Activity, class, coordinator, date, status, people reached, care notes |
| People & roles | Create accounts, change roles, enable/disable, session revocation, protect current administrator, audit feed |
| WhatsApp | Consent-based individual template queue, personalization, dry-run/live adapter, daily rules, delivery statuses, cancel queued messages, review failed/uncertain sends |

Financial totals are never combined across currencies. Currency codes assume two decimal minor units; currencies with different minor-unit conventions need an extension. Attendance rates use all **marked** entries as the denominator, including excused. Unmarked estimates use the current roster and are clearly labeled; exact historical roster snapshots are not implemented.

## Access matrix

| Capability | Admin | Secretary | Teacher | Treasurer | Viewer |
|---|---|---|---|---|---|
| Read roster / ministry records | All | All | Assigned classes | All | All |
| Manage members/classes | Yes | Yes | No | No | No |
| Mark attendance | All | All | Assigned classes | No | No |
| Manage lessons/outreach | All | All | Assigned classes | No | No |
| Manage events | Yes | Yes | No | No | No |
| Manage event registrations | All | All | Own roster | No | No |
| Read/export offerings | Yes | Yes | No | Yes | No |
| Create/edit offerings | Yes | No | No | Yes | No |
| Delete offerings | Yes | No | No | No | No |
| Manage notifications | Yes | Yes | No | No | No |
| Manage accounts / view audit | Yes | No | No | No | No |

Restrictions are enforced by the backend; hiding a menu is not the security boundary. Operational read roles include access to member contact and care notes. Choose roles accordingly. Multi-church tenancy, member self-service accounts, SSO, MFA, and automatic password-recovery emails are not implemented.

## Automated tests

No test data touch your church database. The integration suite uses a temporary SQLite database and real HTTP requests:

```sh
python -m unittest discover -s tests -v
```

Optional browser suite (Node.js 18+, npm or pnpm):

```sh
npm install
npx playwright install chromium
npm run test:e2e
```

With pnpm, use `pnpm install`, `pnpm exec playwright install chromium`, and `pnpm test:e2e`.
If Python is not on PATH, set `PYTHON_BIN` to the absolute Python executable before running browser tests. Tests start their own server on port 8011 with a fresh `.e2e-data/` database. This port must be free. The suite covers all module screens, a member → attendance → reload → notification dry-run workflow, teacher attendance, and mobile layout.

See `TEST_RESULTS.md` for the checks actually performed and their limits.

## Runtime and deployment

The backend includes PBKDF2-SHA256 password hashes with individual salts, random eight-hour sessions stored as token hashes, HttpOnly/SameSite cookies, CSRF tokens for writes, login throttling, parameterized SQL, output escaping, CSP, and restricted static-file serving. Record edits check versions to reject stale writes. Attendance uses a unique `(class, member, date)` key and transactional updates. Deletes that would orphan attendance, notifications or registrations are blocked; deactivate members/classes instead.

Public hosting uses `wsgi:create_application()` or `python run_production.py`, with `pip install -r requirements.txt`. The production entrypoint fails closed unless `SSMS_ENV=production`, an explicit absolute `SSMS_DB`, exact HTTPS `SSMS_ORIGIN`, and `SSMS_SECURE_COOKIES=1` are configured. A new database also requires your administrator email and unique password. Demo databases are rejected. Remove the bootstrap password from the service environment after initialization; it is not needed for restarts.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the prepared Oracle Always Free VM route, HTTPS proxy, worker timer, persistent storage and backup/restore procedure. No cloud deployment has been performed. Python's built-in HTTP server is restricted to development; production must use WSGI. No penetration or high-volume load test has been performed.

Optional Docker build (not validated on this host):

```sh
docker build -t ssms .
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env -e SSMS_DB=/app/data/ssms.sqlite3 -v ssms-data:/app/data ssms
```

Set real environment values in your own `.env` before using `--env-file`; do not commit that file. The image runs as a non-root user. Docker supplies the variables; `server.py` itself still does not parse `.env`.

Use SQLite's backup API to make a consistent backup while the server runs:

```sh
python backup.py --output /secure-backups/ssms-backup.sqlite3
```

Use the same `SSMS_DB` as the server. Protect backups and database access with operating-system permissions. Restore by stopping both server and worker, setting `SSMS_DB` to a copy of the backup, and restarting. Test restoration before relying on backups. Neither SQLite data nor backups are encrypted by this app; use encrypted storage where required.

## WhatsApp configuration

See `WHATSAPP_ARCHITECTURE.md` for database, integration, worker scheduling, retries, and webhook setup. Default `WHATSAPP_MODE=dry_run` never calls Meta. Live operation requires your Meta business account, phone-number ID, access token, Graph API version, app secret, verification token, approved message templates, public HTTPS webhook, and a scheduled backend worker. No live delivery or real credentials were tested.

There is no unofficial WhatsApp Web automation, group broadcast shortcut, or credentials in the frontend. Each consenting member gets an individual template message through Meta's official Cloud API. This implementation supports text body parameters; templates requiring header media, buttons or additional component types require adapter extensions.
