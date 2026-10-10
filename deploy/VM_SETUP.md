# Free VM setup: fresh church database

Prepared on 10 October 2026. Selected route: Oracle Cloud Always Free Ubuntu VM. The source is already published at https://github.com/samuelenoh/sabbath-school-app. No cloud account, VM, DNS name or production database has been provisioned. The intended hosted database is **fresh**, with your own secure administrator credentials; synthetic demo mode remains available locally only.

## 1. Create your Oracle account

Start at [Oracle Free Tier signup](https://signup.cloud.oracle.com/). Complete your own identity, contact, card verification and account terms. Oracle may place a temporary card authorization hold. Its free tier has no SLA; capacity and idle-resource reclamation can affect availability. Do not upgrade to a paid account or choose paid resources to resolve capacity shortages if you intend to remain free.

Choose your home region carefully; Always Free compute and volumes must be in that region. Free availability varies by region and tenancy. I cannot verify allocatable capacity until your account exists. The 30-day trial credit is separate from ongoing Always Free resources. [Oracle signup and billing FAQ](https://www.oracle.com/cloud/free/faq/), [Always Free limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

## 2. Create an Always Free Ubuntu VM

In the OCI console, open **Compute → Instances → Create instance**. Use these settings, checking the final cost/eligibility display before creation:

| Setting | Choice |
|---|---|
| Name | sabbath-school-web |
| Region | Your account's home region |
| Image | Ubuntu 24.04 platform image, marked eligible; not a paid marketplace image |
| Shape | VM.Standard.A1.Flex, 1 OCPU and 2 GB memory, within your tenancy's free allowance |
| Alternative | VM.Standard.E2.1.Micro if its Always Free capacity is available; lower performance |
| Capacity | On-demand; keep the Always Free eligibility display |
| Boot disk | 50 GB; total boot/block storage across your tenancy must stay within 200 GB |
| Network | Public subnet with an internet gateway and assigned public IPv4 address |
| SSH | Your OpenSSH public key, or an OCI-generated pair whose private key you save securely |

Do not select Ampere A2 or an arbitrary default shape. Check other resources already in the tenancy: free allowances are shared. Oracle currently documents an A1 total equivalent of 2 OCPUs/12 GB (1,500 OCPU hours/9,000 GB hours per month). An unavailable A1 shape is not a reason to substitute paid compute. Try another availability domain in the home region, an eligible micro shape, or wait. [Official instance-creation guide](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm).

Keep the private SSH key outside this repository and ZIP. Never paste it, the administrator password, or Meta tokens into chat. Confirm the server's SSH host fingerprint through your cloud access before trusting the first connection.

## 3. Configure network access and a hostname

In the VM's network security group or subnet security list, allow stateful incoming TCP:

- Port 22 from your own administrator public IP/CIDR only.
- Ports 80 and 443 from internet clients (0.0.0.0/0 for IPv4).
- Keep port 8000 private: the app listens on loopback behind Caddy.

Also allow 80/443 through the guest OS firewall. Preserve SSH access while modifying rules; use OCI console access if you lock yourself out. Do not flush the OS firewall or replace OCI image firewall rules blindly.

Use a hostname/subdomain you control and create its DNS A record pointing to the VM's public IPv4 address. Domain registration is separate and may cost money; an existing subdomain avoids another purchase. Free compute does not supply a custom domain. Remove stale AAAA records unless working IPv6 is configured. Verify DNS resolves before requesting HTTPS. Caddy will obtain a certificate after the hostname and incoming 80/443 are correct.

From Windows PowerShell, connect using your actual local key path and VM public IP:

```powershell
ssh -i 'C:\path\to\your-private-key' ubuntu@YOUR_VM_PUBLIC_IP
```

## 4. Install the application securely

Follow **Ubuntu installation** in [DEPLOYMENT.md](../DEPLOYMENT.md) after SSH connects. It contains the exact package, repository, virtualenv, environment-file, Caddy and systemd commands. Application source is `/opt/ssms`; SQLite data are `/var/lib/ssms`; private configuration is `/etc/ssms/ssms.env`. Do not upload an existing local database.

Set these server-only environment values, using your real email and hostname:

```text
SSMS_ENV=production
SSMS_DB=/var/lib/ssms/ssms.sqlite3
SSMS_ORIGIN=https://YOUR_HOSTNAME
SSMS_SECURE_COOKIES=1
SSMS_HOST=127.0.0.1
SSMS_TRUSTED_PROXY=127.0.0.1
SSMS_ADMIN_EMAIL=YOUR_ADMIN_EMAIL
SSMS_ADMIN_PASSWORD=YOUR_UNIQUE_LONG_PASSWORD
WHATSAPP_MODE=dry_run
```

The environment file must remain mode 640, owned root:ssms. Keep all Meta values empty until you are ready to configure the provider. The application creates only your administrator on the fresh production database; create teacher accounts/classes/members after signing in. Do not run --demo on this VM. Remove the bootstrap password from the service environment after successful initialization and restart the web service. It is unnecessary for later startup.

## 5. Acceptance checks before real member data

These are required deployment checks, not results already obtained:

1. Open `https://YOUR_HOSTNAME/healthz`: valid TLS certificate and `{"status":"ok"}`.
2. Sign in with your private administrator credentials. Confirm the roster is empty and create your teacher account and class.
3. Confirm HTTP redirects to HTTPS and the session cookie has Secure, HttpOnly and SameSite attributes. Port 8000 must not be reachable publicly.
4. Using synthetic temporary test records only, mark attendance from the assigned teacher. Confirm another teacher cannot access that roster or mark its attendance.
5. Restart the web service and worker and confirm the same test records persist in the configured database. Reboot the VM and check the enabled services start again.
6. Make a SQLite backup, validate integrity, and test restoring a separate copy with the services stopped. Configure daily protected backups, off-host copies, retention and monitoring before entering real records. Never commit databases/backups.
7. Confirm the worker timer is active and notification dry runs do not contact Meta. Live operation requires separately verified Meta credentials, templates and signed webhooks.

Clean up synthetic acceptance records where no history prevents deletion, or start a new production database before entering actual member data. Production readiness is not established until the deployed HTTPS, private configuration, persistent data and restore checks pass. No cloud deployment or live WhatsApp delivery has occurred here.

## Information needed to continue deployment

After the VM is running, provide its public IP, SSH username (normally ubuntu), the **local path** to the private key (not its contents), and the intended HTTPS hostname. You must first confirm the target VM is yours and authorize its configuration. Enter private administrator and Meta values directly on the server. If you do not have a hostname yet, settle that before the production installation; the app intentionally requires an HTTPS origin.
