# Deploying a public demo on Oracle Cloud Always Free

This runs the whole ResearchPilot stack on one free Oracle Cloud ARM server, with HTTPS from Let's Encrypt and password-reset email over real SMTP. It is meant for a portfolio demo used by invited testers, not a hardened public service (see [Limits](#limits-of-this-demo-setup)).

**What runs where.** Caddy is the only public entry point (ports 80 and 443). It forwards to the Nginx web container, which serves the React app and proxies `/api/v1` to FastAPI. PostgreSQL, Redis, the dispatcher and the Celery worker have no public ports. Production mode refuses to start without HTTPS, secure cookies and encrypted SMTP.

```
Internet ─► Caddy :443 (TLS) ─► web (Nginx) ─► api (FastAPI) ─► db (Postgres+pgvector), redis
                                               dispatcher ─► redis ─► worker
```

Files: `compose.prod.yaml` (production overlay), `deploy/Caddyfile`, `deploy/production.env.example`, `deploy/backup.sh`.

## 1. Push the code you want to deploy

The server clones from GitHub. Commit and push the branch you want to run (for example merge it into `main`). Uncommitted work on your PC will not be on the server.

## 2. Create the Oracle Cloud account

1. Sign up at https://www.oracle.com/cloud/free/. A card is required for identity verification; the Always Free resources do not charge it.
2. Choose your **home region** carefully: it cannot be changed, and Always Free ARM servers can only be created there. Pick one near your testers.

## 3. Create the server

In the Oracle Console: **Compute → Instances → Create instance**.

| Setting | Value |
|---|---|
| Image | Canonical Ubuntu 24.04 |
| Shape | Ampere → `VM.Standard.A1.Flex`, **2 OCPUs, 12 GB memory** (the current Always Free maximum) |
| Networking | Create a new virtual cloud network with a **public subnet**; assign a public IPv4 address |
| SSH keys | Generate a key pair and **download the private key** (you cannot download it later) |
| Boot volume | Specify a custom size, 100 GB (the free allowance is 200 GB in total) |

If you get **"Out of capacity"**, try another availability domain in the same region or retry later; ARM capacity in popular regions frees up over time.

Note the server's **public IP address** on the instance page.

## 4. Open ports 80 and 443

Two firewalls must allow web traffic.

**Oracle network (Security List).** Instance page → subnet link → Security Lists → Default Security List → **Add Ingress Rules**, source `0.0.0.0/0`:
- TCP, destination port `80`
- TCP, destination port `443`
- UDP, destination port `443` (HTTP/3, optional)

**Ubuntu's own firewall.** Oracle's Ubuntu image rejects everything except SSH by default. After connecting in step 6, run:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p udp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 5. Get a free domain name

HTTPS certificates need a hostname, not a bare IP. DuckDNS is free:

1. Sign in at https://www.duckdns.org and create a subdomain, for example `researchpilot-ahmad`.
2. Set its **current ip** to your server's public IP and click update.
3. Your domain is now `researchpilot-ahmad.duckdns.org`. Check with `nslookup researchpilot-ahmad.duckdns.org`; it should return the server IP.

If you own a domain, create an `A` record pointing at the server IP instead.

## 6. Connect and install Docker

From your PC (PowerShell or Git Bash), using the downloaded key:

```bash
ssh -i path/to/ssh-key.key ubuntu@YOUR_SERVER_IP
```

On Windows, if SSH complains that the key permissions are too open, right-click the key file → Properties → Security and leave only your own user with access.

On the server:

```bash
sudo apt-get update && sudo apt-get -y upgrade
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit
```

Reconnect with SSH so the `docker` group applies, then check `docker compose version`.

## 7. Get the code

```bash
git clone https://github.com/Ahmadd01211/Research-Pilot.git researchpilot
cd researchpilot
git checkout main   # or the branch you pushed
```

If the repository is private, create a read-only GitHub fine-grained personal access token for this repository (Contents: read) and use it as the password when `git clone` asks.

## 8. Configure email

Password reset needs a real SMTP account. The simplest free option for a demo is Gmail:

1. Turn on 2-Step Verification for the Google account.
2. Create an **App password** at https://myaccount.google.com/apppasswords.
3. Use `smtp.gmail.com`, port `587`, security `starttls`, your Gmail address as username and the 16-character app password.

Gmail limits daily sending and the sender address must be that Gmail account. For better deliverability later, use a transactional email provider with your own domain (SPF and DKIM configured).

## 9. Configure the app

```bash
cp deploy/production.env.example .env
openssl rand -hex 32        # copy this into POSTGRES_PASSWORD
nano .env
```

Fill in `POSTGRES_PASSWORD`, `RP_DOMAIN` (without `https://`), `RP_ACME_EMAIL`, and the SMTP values. Leave the AI settings off unless you accept that every tester's searches use, and bill, your Google key. Save with Ctrl+O, Enter, Ctrl+X. The `.env` file holds secrets: never commit it.

## 10. Start it

```bash
alias rp='docker compose -f compose.yaml -f compose.prod.yaml'
echo "alias rp='docker compose -f compose.yaml -f compose.prod.yaml'" >> ~/.bashrc
rp up -d --build
```

The first build takes several minutes on the ARM server. Migrations run automatically through the `migrate` service. Then check:

```bash
rp ps                                                   # all services healthy; migrate exited 0
curl -s https://YOUR_DOMAIN/api/v1/health/ready         # {"status":"ready"}
rp logs caddy --tail 30                                 # certificate obtained for YOUR_DOMAIN
```

Open `https://YOUR_DOMAIN`, create an account, upload a PDF, and test **Forgot password?** with a real inbox.

## 11. Update after new commits

```bash
cd ~/researchpilot
git pull
rp up -d --build
```

New migrations apply automatically. Volumes (database, uploaded PDFs, certificates) persist across rebuilds. Do not run `rp down -v`: `-v` deletes the database and uploaded PDFs.

## 12. Back up

`deploy/backup.sh` writes a database dump and an archive of uploaded PDFs to `~/researchpilot-backups`, keeping the newest seven of each. Run it daily at 03:00:

```bash
sh deploy/backup.sh                     # test once
crontab -e                              # then add the line below
0 3 * * * cd /home/ubuntu/researchpilot && sh deploy/backup.sh >> /home/ubuntu/researchpilot-backups/backup.log 2>&1
```

These backups live on the same server. Occasionally copy them to your PC: `scp -i key ubuntu@IP:researchpilot-backups/db-*.dump .`

Restore a database dump (replaces current data; take a fresh backup first):

```bash
rp exec -T db pg_restore -U rp -d rp_greenfield --clean --if-exists < ~/researchpilot-backups/db-STAMP.dump
```

## Keeping the free server

Oracle may reclaim Always Free instances that stay almost completely idle for a week. Check Oracle's current idle-instance policy for your account. Oracle also reduced the Always Free ARM allowance to 2 OCPUs and 12 GB in 2026; staying within those numbers avoids the server being stopped.

## Limits of this demo setup

Tell testers about the first three; the rest are on the release-hardening list in `docs/SECURITY.md`.

- **Do not upload confidential or paywalled papers you may not share.** PDFs are stored on your server, and removal is a soft delete with no purge yet.
- **No email verification.** Anyone can register any address; password reset only reaches the real owner of the address.
- **AI search and chat are off** unless you set a Google key, and there are no per-user budgets yet.
- **Shared rate limits.** The API sees every visitor as the same proxy address, so sign-up (30 per 15 minutes) and sign-in limits are shared by everyone. A burst of testers may see "Too many attempts". Fixing this needs trusted forwarded-address handling.
- **Single server.** No redundancy; backups are your recovery path.
- **Mailpit is not used in production.** The `mail` service only starts in development.
