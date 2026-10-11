# Render + Neon: persistent free pilot

Selected on 11 October 2026. Full Python app on Render Free; persistent external PostgreSQL on Neon Free; optional hourly notification worker through GitHub Actions. This is a constrained demonstration/small pilot, not uninterrupted production hosting. Render explicitly advises against free-tier production use. Oracle is no longer the selected provider.

## Accounts and free limits

[Render signup](https://dashboard.render.com/register), [Neon signup](https://console.neon.tech/signup). Use GitHub sign-in if convenient and complete email verification/MFA yourself. Neon advertises free signup without a credit card; Render's first-deploy guide says no payment is required. Account-specific verification can still appear: stop if a required payment/card prompt appears; do not select paid resources to bypass it. Never put passwords, connection strings or Meta tokens into chat or the repository.

- Render Free: 750 shared web-service hours/month, sleeps after 15 minutes idle, cold start about a minute, ephemeral files, no free background workers/cron, quota-related suspension and possible external-traffic suspension. Use the assigned HTTPS onrender.com URL; no purchased domain is necessary. Do not choose Render's free Postgres: it expires after 30 days.
- Neon Free's 2 October 2026 update states 1 GB database storage/project, 100 CU-hours/month/project, scaling up to 2 CU, 10 branches and a six-hour instant restore window. Idle compute can sleep; wakeup and monthly compute limits can interrupt access. Check your actual console quota display, monitor usage and make independent backups. Do not add a paid plan.
- GitHub Actions standard runners are free in public repositories. The included hourly schedule is best effort: runs can be delayed/dropped and schedules in public repos disable after 60 days without repository activity. It is not a continuously running worker or a guaranteed delivery clock. More frequent polling increases database usage; no keepalive workaround is included.

Sources: [Render limits](https://render.com/docs/free), [Render no-payment first deployment](https://render.com/docs/your-first-deploy), [Neon current free limits](https://neon.com/blog/neon-free-plan-1-gb-per-project), [Neon no-card signup](https://neon.com/variable-load), [Actions billing](https://docs.github.com/en/actions/concepts/billing-and-usage), [scheduled workflow limits](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## 1. Neon persistent database

Create one **Free** project, e.g. sabbath-school, preferably in the same geographic region available on Render. Start with a fresh database as requested. A synthetic demonstration remains reproducible locally with --demo and a unique local password; production rejects demonstration databases.

In Neon's Connect dialog, choose your application database and role. Use an SSL-enabled PostgreSQL connection string with `sslmode=require` or stricter. Prefer the direct (non-pooler) endpoint for this small deployment; every app connection is short-lived. Copy the private URL directly into Render's secret environment field named DATABASE_URL. Do not send it to chat or commit it. The URL includes a database password. The app initializes its tables transactionally on first startup; there is no manual SQL import needed for a fresh database. Existing local SQLite church data are not automatically transferred; back them up and plan a separately tested import before changing a real deployment.

## 2. Render Python web service

After Render email verification, create **New → Web Service** from `samuelenoh/sabbath-school-app`, branch main. If GitHub installation permission is needed, restrict Render to this repository. The user must authorize the new provider access directly. Select **Python** and **Free**, not Static Site, Starter or paid Postgres. Leave Root Directory blank.

| Setting | Value |
|---|---|
| Build command | pip install -r requirements.txt |
| Start command | python run_production.py |
| Health check | /healthz |
| Python version | 3.12.12 |
| Auto deploy | Off until initial CI and deployment acceptance pass |

Set server environment variables in Render's Environment UI:

| Variable | Value |
|---|---|
| DATABASE_URL | Your private Neon SSL connection string |
| SSMS_ENV | production |
| SSMS_SECURE_COOKIES | 1 |
| SSMS_HOST | 0.0.0.0 |
| SSMS_ADMIN_EMAIL | Your administrator email |
| SSMS_ADMIN_PASSWORD | A unique long password you enter directly |
| WHATSAPP_MODE | dry_run |

Render supplies PORT and RENDER_EXTERNAL_URL automatically. The latter becomes the exact allowed HTTPS origin when SSMS_ORIGIN is unset. For a custom domain later, explicitly set SSMS_ORIGIN to its exact HTTPS origin and update monitoring accordingly. Do not set SSMS_DB or store SQLite files on this free service. The included render.yaml declares the same free service for reference; manual setup makes plan selection and secret entry reviewable.

Once it starts, open its assigned HTTPS URL and sign in. Only your administrator is created in this fresh database. Change your bootstrap password in My account, remove SSMS_ADMIN_PASSWORD from Render's environment, and redeploy. Existing users remain in Neon across redeploys. Do not share your administrator credentials for a public demo; create restricted viewer/teacher accounts if needed.

## 3. Notification worker (optional, initially disabled)

`.github/workflows/notifications.yml` is disabled unless repository variable SSMS_WORKER_ENABLED equals `true`. It runs around minute 17 of each UTC hour; actual timing is not guaranteed. Enable only after the app database exists and dry-run behavior has been checked.

In GitHub repository **Settings → Secrets and variables → Actions**, enter directly:

- Secret SSMS_DATABASE_URL: the same private Neon URL.
- Variable SSMS_ORIGIN: the actual Render HTTPS origin.
- Variable WHATSAPP_MODE: dry_run.
- Variable SSMS_WORKER_ENABLED: true when ready.

Run the Notification worker manually from the Actions tab once and inspect its result. Rules and queue share Neon with the web app even while Render sleeps. The worker does not ping the web app to prevent sleeping. Local jobs are deduplicated and transactionally claimed. Status callbacks persist in Neon; Meta must retry callbacks during web-service cold starts. External delivery can still be uncertain, requiring reconciliation.

Live WhatsApp additionally needs Meta secrets, approved templates, consent and reachable signed webhooks as described in WHATSAPP_ARCHITECTURE.md. Put tokens/app secret/verify token/phone-number ID in GitHub secrets and Render's private environment; put the Graph version in both configured environments. No live operation is currently verified or enabled.

## Persistence, security and backups

The app supports SQLite locally and PostgreSQL when DATABASE_URL is configured. PostgreSQL schema creation uses identity keys, double precision session timestamps, foreign keys and unique constraints. Bound parameters, rollback, serialized advisory-lock transactions and atomic queue claiming preserve the existing teacher and finance authorization paths. Reads and writes are serialized for this modest single-church app; this is not a high-scale multi-instance design.

`backup.py` backs up SQLite only and explicitly refuses PostgreSQL. For Neon, use a compatible PostgreSQL client `pg_dump` to export an encrypted/protected off-host backup; retain it independently of the six-hour provider restore window. Run the dump with the private connection URL supplied through PGDATABASE in your local environment, not typed into a public log. Use `pg_dump --format=custom --file=/secure-path/ssms.backup` with a client version at least as new as your database server. Restore to a separate test database with pg_restore, verify records and permissions, and then plan any real restoration. Never upload backup files to GitHub or public Actions artifacts. Automating protected backups remains an operator task.

## Deployment acceptance

Before entering real member data, verify valid HTTPS, /healthz, administrator login, Secure/HttpOnly cookies, teacher class restrictions and financial role restrictions. Create only temporary synthetic acceptance records, then confirm they survive a Render redeploy. Test a backup restore and monitor provider quotas. Run the dry-run worker once; leave live Meta mode disabled. Successful code tests alone do not prove these deployed checks passed.

Automated tests include the existing SQLite/WSGI/browser suites and the same HTTP integration suite against PostgreSQL in CI, including two simultaneous queue workers claiming a job once. PostgreSQL tests only accept a disposable local `_test` database. They must never be pointed at your Neon application database.
