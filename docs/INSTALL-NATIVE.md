# Native Installation Guide (Production)

This guide installs Maquita Webmail **natively** (no Docker) on a single Debian
server, alongside a real Postfix + Dovecot mail stack. It mirrors the reference
production deployment.

> The bundled `docker-compose.yml` is a **demo** stack (PostgreSQL, Redis,
> backend, frontend) that connects to an *external* mail server. For a real
> mail platform you own end-to-end, follow this guide.

## Reference stack (tested)

| Component   | Version       | Role                                   |
|-------------|---------------|----------------------------------------|
| Debian      | 12 / 13       | Base OS                                |
| PostgreSQL  | 17            | Mailbox accounts + app data            |
| Dovecot     | 2.4           | IMAP/POP3, ManageSieve, master user    |
| Postfix     | 3.10          | SMTP MTA, LMTP delivery to Dovecot     |
| Redis       | 7 / 8         | Sessions & caches                      |
| Python      | 3.12+         | Backend (FastAPI / uvicorn)            |
| Node        | 20            | Frontend build (Vite)                  |
| nginx       | 1.24+         | TLS reverse proxy                      |
| SOGo        | 5 (optional)  | CalDAV/CardDAV (calendar & contacts)   |
| Ollama      | (optional)    | Local AI assistant                     |

## Architecture

```
            Internet :443 (TLS, nginx)
                       |
   /            -> frontend (static, /var/www/webmail)
   /api/        -> backend  127.0.0.1:8000  (uvicorn, systemd)
   /SOGo/       -> SOGo      127.0.0.1:20000 (optional)
                       |
   backend --IMAP/Sieve--> Dovecot 143/4190  (master user login)
   backend --SMTP-------->  Postfix 587       (per-user auth)
   backend --SQL-------->   PostgreSQL :5432
   backend --cache----->    Redis :6379
   Postfix --LMTP------->    Dovecot (delivery)
```

The backend never stores mailbox passwords: it reads any mailbox through the
**Dovecot master user** (`MASTER_PASSWORD`), and sends through Postfix
submission using the end user's own credentials.

---

## 1. System packages

```bash
sudo apt update
sudo apt install -y postgresql redis-server dovecot-imapd dovecot-pop3d \
  dovecot-lmtpd dovecot-managesieved dovecot-sieve dovecot-pgsql \
  postfix postfix-pgsql nginx python3 python3-venv python3-dev \
  build-essential libpq-dev git curl
# Node 20 (NodeSource)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
```

## 2. PostgreSQL — mail accounts + app schema

```bash
sudo -u postgres psql <<SQL
CREATE USER mailserver WITH PASSWORD 'CHANGE_ME_DB';
CREATE DATABASE maildb OWNER mailserver;
SQL
```

Minimal virtual-mailbox schema used by Postfix/Dovecot (extend as needed):

```sql
\c maildb
CREATE TABLE domain  (domain text PRIMARY KEY, active boolean DEFAULT true);
CREATE TABLE mailbox (
  username text PRIMARY KEY,          -- full address user@domain
  password text NOT NULL,             -- {SSHA512} hash (doveadm pw)
  domain   text REFERENCES domain(domain),
  maildir  text,                      -- e.g. user@domain/
  quota_bytes bigint DEFAULT 0,
  active   boolean DEFAULT true
);
CREATE TABLE alias   (address text PRIMARY KEY, goto text, active boolean DEFAULT true);
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mailserver;
```

Then apply the app migrations (creates webmail/compliance tables in the same DB):

```bash
cd /opt/maquita-webmail
for f in migrations/*.sql; do sudo -u postgres psql -d maildb -f "$f"; done
```

Create a domain + a mailbox to test with:

```bash
sudo -u postgres psql -d maildb -c \
 "INSERT INTO domain(domain) VALUES ('example.com');"
HASH=$(doveadm pw -s SSHA512 -p 'UserPass123')
sudo -u postgres psql -d maildb -c \
 "INSERT INTO mailbox(username,password,domain,maildir) \
  VALUES ('user@example.com','$HASH','example.com','example.com/user/');"
```

## 3. Dovecot — virtual users + master user

`/etc/dovecot/dovecot-sql.conf.ext`:
```
driver = pgsql
connect = host=127.0.0.1 dbname=maildb user=mailserver password=CHANGE_ME_DB
password_query = SELECT username AS user, password FROM mailbox \
  WHERE username = '%u' AND active = true
user_query     = SELECT maildir AS home FROM mailbox WHERE username='%u'
iterate_query  = SELECT username AS user FROM mailbox WHERE active = true
```

Mail location & vmail user:
```
mail_home = /var/vmail/%{user|domain}/%{user|username}
mail_location = maildir:~/Maildir
```
```bash
sudo groupadd -g 5000 vmail
sudo useradd  -u 5000 -g vmail -d /var/vmail -m -s /usr/sbin/nologin vmail
```

**Master user** (lets the backend open any mailbox). In a passwd-file
`/etc/dovecot/master-users`:
```
webmaster@*:{SSHA512}<hash from: doveadm pw -s SSHA512>
```
And in the `auth` config:
```
auth_master_user_separator = *
passdb { driver = passwd-file ; args = /etc/dovecot/master-users ; master = yes }
```
The plaintext you hash here is what goes into the backend `.env` as
`MASTER_PASSWORD`. Enable IMAP (143/993), LMTP, and ManageSieve (4190).

```bash
sudo systemctl restart dovecot
```

## 4. Postfix — SMTP + LMTP delivery

`/etc/postfix/main.cf` (key lines):
```
virtual_mailbox_domains = pgsql:/etc/postfix/pgsql/domains.cf
virtual_mailbox_maps    = pgsql:/etc/postfix/pgsql/mailbox.cf
virtual_alias_maps      = pgsql:/etc/postfix/pgsql/alias.cf
virtual_transport       = lmtp:unix:private/dovecot-lmtp
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
```
Enable the `submission` (587) service in `master.cf` with SASL via Dovecot.
Each `pgsql/*.cf` map is a small file (`hosts/user/password/dbname` + a
`query`), e.g. `domains.cf`:
```
query = SELECT 1 FROM domain WHERE domain='%s' AND active=true
```
```bash
sudo systemctl restart postfix
```

## 5. Backend (FastAPI)

```bash
sudo git clone https://github.com/wilsongabriel30/webmailMaquita.git /opt/maquita-webmail
cd /opt/maquita-webmail/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp ../.env.example .env      # then edit .env (see variable table in README)
```
Set in `.env`: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ADMIN_JWT_SECRET`,
`MASTER_PASSWORD` (the Dovecot master password from step 3), `IMAP_HOST=127.0.0.1`,
`SMTP_HOST=127.0.0.1`, `MAIL_DOMAIN`, `COOKIE_DOMAIN`, `CORS_ORIGINS`.

systemd unit `/etc/systemd/system/maquita-webmail.service`:
```ini
[Unit]
Description=Maquita Webmail backend
After=network.target postgresql.service redis-server.service

[Service]
User=www-data
WorkingDirectory=/opt/maquita-webmail/backend
EnvironmentFile=/opt/maquita-webmail/backend/.env
ExecStart=/opt/maquita-webmail/backend/venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 6 --loop uvloop
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now maquita-webmail
curl -s http://127.0.0.1:8000/api/health      # -> {"status":"ok",...}
```

## 6. Frontend (build + nginx)

```bash
cd /opt/maquita-webmail/frontend
npm ci && npm run build
sudo mkdir -p /var/www/webmail && sudo cp -r dist/* /var/www/webmail/
```

nginx site `/etc/nginx/sites-available/webmail` (TLS via certbot):
```nginx
server {
    listen 443 ssl;
    server_name mail.example.com;
    ssl_certificate     /etc/letsencrypt/live/mail.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mail.example.com/privkey.pem;

    root /var/www/webmail;
    location / { try_files $uri /index.html; }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    # optional: location /SOGo/ { proxy_pass http://127.0.0.1:20000; }
}
server { listen 80; server_name mail.example.com; return 301 https://$host$request_uri; }
```
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo ln -s /etc/nginx/sites-available/webmail /etc/nginx/sites-enabled/
sudo certbot --nginx -d mail.example.com
sudo nginx -t && sudo systemctl reload nginx
```

## 7. Optional components

- **Calendar/Contacts:** install `sogo`, point `SOGO_DAV_URL` at it, proxy `/SOGo/`.
- **AI assistant:** install Ollama, `ollama pull qwen2.5:7b`, set `OLLAMA_URL`.
  Leave `IA_API_KEY` blank unless you front Ollama with an auth gateway.
- **Spam filtering:** add rspamd and wire it into Postfix as a milter.

## 8. Verify

```bash
systemctl is-active postgresql dovecot postfix redis-server nginx maquita-webmail
curl -s http://127.0.0.1:8000/api/health
# log into https://mail.example.com with user@example.com / UserPass123
```

## Troubleshooting

| Symptom                               | Check |
|---------------------------------------|-------|
| Login OK but mailbox empty / IMAP err | `MASTER_PASSWORD` matches the Dovecot master passwd-file hash |
| Cannot send (535)                     | `submission` (587) up; user exists in `mailbox`; Postfix SASL via Dovecot |
| `/api/health` fails                   | backend `.env` (DATABASE_URL/REDIS_URL); `journalctl -u maquita-webmail` |
| 502 from nginx                        | backend listening on 127.0.0.1:8000 |

See also `docs/INSTALL.md`, `docs/DEPLOYMENT.md`, `docs/TROUBLESHOOTING.md`.
