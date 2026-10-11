# Deployment and free hosting

Prepared and checked on 10 October 2026. This is a single-church, modest-traffic application. Hosting has not been provisioned and live WhatsApp has not been verified.

## Selected free pilot: Render + Neon

The current selected route is Render Free web hosting with external Neon PostgreSQL and an optional GitHub Actions worker. Follow [deploy/RENDER_NEON.md](deploy/RENDER_NEON.md). It preserves the full Python app and persistent data but has cold starts, quotas and best-effort scheduling. Render advises against free-tier production use. No live deployment has been verified.

## Alternative VM route: Oracle Always Free Ubuntu VM

Use an Always Free eligible Ubuntu VM in your home region, with persistent boot storage. An A1 allocation of 1 OCPU / 2 GB and a 50 GB boot volume is enough to begin testing this app, subject to available capacity and measured load. This recommendation is an engineering judgment, not a provider uptime guarantee. Oracle's current A1 allowance is 1,500 OCPU hours and 9,000 GB hours/month (2 OCPUs / 12 GB equivalent), with 200 GB combined boot/block storage. Keep all resources inside the displayed Always Free allowance; trial credits expire and paid resources can incur charges. Signup may require card/phone verification. Capacity shortages and reclamation of idle VMs can interrupt service, so maintain off-host backups.

Source: [Oracle Always Free resource limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [Oracle Free Tier FAQ](https://www.oracle.com/cloud/free/faq/).

Render's free service loses local SQLite data when its ephemeral filesystem resets, and free persistent disks are unavailable. Its free Postgres expires after 30 days. The selected route now uses external Neon PostgreSQL through the app's new DATABASE_URL support. [Render free-service limitations](https://render.com/docs/free).

PythonAnywhere's free plan can support a small manual pilot, but new free accounts have no scheduled tasks and the provider discourages SQLite for production. That leaves the automatic notification worker unresolved. [Free account features](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), [database guidance](https://help.pythonanywhere.com/pages/KindsOfDatabases). A static host alone cannot run this backend.

For the selected fresh-database deployment, begin with the account, VM, DNS and acceptance checklist in [deploy/VM_SETUP.md](deploy/VM_SETUP.md).

## Ubuntu installation

You must supply your cloud account, SSH access and an HTTPS hostname. Point the hostname's DNS to the VM. Allow TCP 80/443 in both the OCI network rules and OS firewall; restrict SSH to your administration IP. Do not expose port 8000. Obtain a hostname you control; domain registration is not included in the hosting allowance.

Run these on your VM as an administrator, reviewing your paths first:

```sh
sudo apt update
sudo apt install -y python3 python3-venv git caddy
sudo useradd --system --home /var/lib/ssms --shell /usr/sbin/nologin ssms
sudo install -d -m 700 -o ssms -g ssms /var/lib/ssms
sudo install -d -m 750 -o root -g ssms /etc/ssms
sudo git clone https://github.com/samuelenoh/sabbath-school-app.git /opt/ssms
sudo python3 -m venv /opt/ssms/.venv
sudo /opt/ssms/.venv/bin/pip install -r /opt/ssms/requirements.txt
sudo install -m 640 -o root -g ssms /opt/ssms/.env.example /etc/ssms/ssms.env
sudo nano /etc/ssms/ssms.env
```

In the private environment file, replace the example administrator email/password and SSMS_ORIGIN with your exact HTTPS origin (no trailing slash), keep an absolute SSMS_DB on the persistent volume and SSMS_SECURE_COOKIES=1. Leave WhatsApp in dry_run until Meta is configured. Do not deploy a demonstration database or use --demo. The application does not load .env files itself; systemd supplies these values. Keep the environment file outside the repository.

Install the included service/timer units and edit the Caddy hostname:

```sh
sudo install -m 644 /opt/ssms/deploy/ssms.service /etc/systemd/system/ssms.service
sudo install -m 644 /opt/ssms/deploy/ssms-worker.service /etc/systemd/system/ssms-worker.service
sudo install -m 644 /opt/ssms/deploy/ssms-worker.timer /etc/systemd/system/ssms-worker.timer
sudo install -m 644 /opt/ssms/deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable --now ssms.service
sudo systemctl enable --now ssms-worker.timer
sudo systemctl reload caddy
```

Caddy must finish issuing a valid certificate. Check `https://YOUR-HOST/healthz` returns `{"status":"ok"}`; sign in over HTTPS, change your bootstrap password, and remove SSMS_ADMIN_PASSWORD from the private environment file once initialization succeeds. Restart the web service afterward. Check `systemctl status ssms` and `journalctl -u ssms -u ssms-worker` if startup fails. The services use restrictive filesystem permissions and expose Waitress on loopback. Only the local proxy is trusted for forwarded headers. If your architecture uses another proxy address, configure its exact IP; never trust arbitrary clients.

## Backups, restoration and updates

With the same SSMS_DB setting, `python backup.py --output /secure-path/backup.sqlite3` creates a consistent SQLite backup. Use a restrictive umask, a path owned by your operator, and encrypted storage where required. Schedule a daily backup with your operating system, rotate retained copies and copy them off this VM. Backups contain private church data and must never enter Git. The app does not install a backup scheduler or external monitoring for you. Monitor disk space and HTTPS /healthz; test restoration before entering real member information.

Restore into a separate absolute database path after stopping both the web service and worker timer/service. Verify the backup with SQLite `PRAGMA integrity_check`, set SSMS_DB to the restored copy, ensure ssms owns it, then restart both services and verify login, roster, attendance and offerings. Keep the original database for recovery until the restored copy is validated. Never overwrite a running SQLite database or separately copy its WAL files.

Before upgrades, back up the database, stop web and worker services, pull reviewed source, update the virtualenv requirements, run tests with an isolated database, then restart and check /healthz. Tables are initialized additively; there is no general versioned schema migration framework. Multi-instance hosting across different disks is unsupported. SQLite serializes writes; measure capacity before increasing usage.

## WhatsApp activation

Follow WHATSAPP_ARCHITECTURE.md. Set all five Meta values only in the private server environment, provision approved templates and consenting recipients, and configure the signed public webhook. The included timer runs one worker at a time approximately each minute; rules use UTC dates. Test live delivery and webhook updates before enabling staff campaigns. Hosting being free does not make Meta messaging free. No real Meta credentials, approved templates, provider delivery, Linux service installation, Docker build or public cloud deployment were tested here.

## Current deployment and updates

The existing service uses Render Free and Neon Free PostgreSQL; see deploy/RENDER_NEON.md. It has persistent external storage and manual deployments. The older verification record in TEST_RESULTS.md documents its initial hosted acceptance. Do not change plans or replace DATABASE_URL when updating source.

The new registers, books, annual reports and programme use the existing JSON records table. Startup adds only the default saved template setting if missing; existing users, passwords, sessions, attendance, offerings and other records are preserved. No church roster or programme week is seeded automatically. Docker includes the new annual_report.py, programme.py and import_roster.py modules. Back up the database before an operator rollout; verify /healthz, authentication and the module screens afterward. Import a reviewed private roster through the authenticated Members screen into the correct existing class. Retain unknown dates and absent consent rather than guessing.

The local release checks are 38 executed Python tests and nine Chromium workflows, with dedicated PostgreSQL verification in GitHub CI. Live Meta delivery, Docker execution, Linux service installation, high-volume testing and backup restoration still require operator verification. No production certification is claimed. Meta credentials/templates are separate from hosting, and dry-run results are never proof of delivery.
