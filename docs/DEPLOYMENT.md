# Production Deployment Guide

This guide covers deploying Maquita Webmail on a production server with full mail stack.

## System Requirements

| Resource | Minimum       | Recommended         |
|----------|---------------|---------------------|
| OS       | Debian 12+ / Ubuntu 24.04+ | Debian 12     |
| CPU      | 2 cores       | 4 cores             |
| RAM      | 4 GB          | 8 GB                |
| Disk     | 40 GB SSD     | 100 GB+ SSD         |
| Network  | Public IPv4, PTR record set | IPv4 + IPv6  |

A valid domain name with full DNS control is required.

## Install System Packages

```bash
apt update && apt upgrade -y

# Mail stack
apt install -y postfix postfix-pgsql dovecot-core dovecot-imapd dovecot-lmtpd \
  dovecot-pgsql rspamd clamav clamav-daemon

# Web and database
apt install -y nginx postgresql-17 postgresql-client-17 redis-server

# Runtime
apt install -y python3.12 python3.12-venv python3-pip nodejs npm certbot \
  python3-certbot-nginx

# Utilities
apt install -y git curl jq fail2ban ufw
```

## Service Configuration

### PostgreSQL

```bash
sudo -u postgres createuser maquita
sudo -u postgres createdb -O maquita maquita_webmail
sudo -u postgres psql -c "ALTER USER maquita PASSWORD 'STRONG_PASSWORD_HERE';"
```

Apply migrations:

```bash
for f in $(ls migrations/*.sql | sort); do
  sudo -u postgres psql -d maquita_webmail -f "$f"
done
```

For tuning, see the [PostgreSQL documentation](https://www.postgresql.org/docs/17/runtime-config.html). Key settings: `shared_buffers`, `work_mem`, `effective_cache_size`.

### Redis

Edit `/etc/redis/redis.conf`:

```
bind 127.0.0.1 ::1
maxmemory 256mb
maxmemory-policy allkeys-lru
```

```bash
systemctl enable --now redis-server
```

### Postfix

Configure as an internet-facing MTA. Key files:

- `/etc/postfix/main.cf` -- main configuration
- `/etc/postfix/master.cf` -- service definitions
- `/etc/postfix/pgsql-*.cf` -- PostgreSQL lookup maps

Essential `main.cf` settings:

```
myhostname = mail.example.com
mydomain = example.com
mydestination = $myhostname, localhost
virtual_mailbox_domains = pgsql:/etc/postfix/pgsql-domains.cf
virtual_mailbox_maps = pgsql:/etc/postfix/pgsql-mailboxes.cf
virtual_alias_maps = pgsql:/etc/postfix/pgsql-aliases.cf
virtual_transport = lmtp:unix:private/dovecot-lmtp
smtpd_tls_cert_file = /etc/letsencrypt/live/mail.example.com/fullchain.pem
smtpd_tls_key_file = /etc/letsencrypt/live/mail.example.com/privkey.pem
smtpd_tls_security_level = may
milter_default_action = accept
smtpd_milters = inet:localhost:11332
non_smtpd_milters = inet:localhost:11332
```

See [Postfix documentation](http://www.postfix.org/documentation.html).

### Dovecot

Configure IMAP and LMTP. Key files:

- `/etc/dovecot/dovecot.conf`
- `/etc/dovecot/conf.d/10-auth.conf`
- `/etc/dovecot/conf.d/10-mail.conf`
- `/etc/dovecot/conf.d/10-ssl.conf`

Essential settings:

```
protocols = imap lmtp
mail_location = maildir:/var/vmail/%d/%n/Maildir
ssl_cert = </etc/letsencrypt/live/mail.example.com/fullchain.pem
ssl_key = </etc/letsencrypt/live/mail.example.com/privkey.pem
```

See [Dovecot documentation](https://doc.dovecot.org/).

### Rspamd

Rspamd handles spam filtering, DKIM signing, and greylisting.

```bash
systemctl enable --now rspamd
```

Configure DKIM signing in `/etc/rspamd/local.d/dkim_signing.conf`. See [Rspamd documentation](https://rspamd.com/doc/).

### ClamAV

```bash
freshclam                          # update virus definitions
systemctl enable --now clamav-daemon clamav-freshclam
```

### Radicale (CalDAV)

```bash
pip3 install radicale==3.0
```

Configure in `/etc/radicale/config`. See [Radicale documentation](https://radicale.org/v3.html).

## Deploy Backend

### Create system user

```bash
useradd -r -s /usr/sbin/nologin -m -d /opt/maquita-webmail maquita
```

### Install application

```bash
cd /opt/maquita-webmail
git clone https://github.com/wilsongabriel30/webmailMaquita.git app
cd app/backend

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure environment

```bash
cp .env.example .env
# Edit .env with production values -- see CONFIGURATION.md
chmod 600 .env
chown maquita:maquita .env
```

### Systemd service

Create `/etc/systemd/system/maquita-webmail.service`:

```ini
[Unit]
Description=Maquita Webmail Backend
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=exec
User=maquita
Group=maquita
WorkingDirectory=/opt/maquita-webmail/app/backend
ExecStart=/opt/maquita-webmail/app/backend/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 4
EnvironmentFile=/opt/maquita-webmail/app/backend/.env
Restart=always
RestartSec=5

# Hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/maquita-webmail/app/backend
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
SystemCallArchitectures=native
MemoryDenyWriteExecute=yes

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now maquita-webmail
```

## Deploy Frontend

```bash
cd /opt/maquita-webmail/app/frontend
npm ci --production=false
npm run build
```

Copy build output to nginx:

```bash
rm -rf /opt/maquita-webmail/www/webmail
cp -r dist /opt/maquita-webmail/www/webmail
chown -R www-data:www-data /opt/maquita-webmail/www/webmail
```

Or use the deploy script:

```bash
bash /opt/maquita-webmail/deploy-webmail.sh
```

### Nginx configuration

Create `/etc/nginx/sites-available/maquita-webmail`:

```nginx
server {
    listen 443 ssl http2;
    server_name mail.example.com;

    ssl_certificate     /etc/letsencrypt/live/mail.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mail.example.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    root /opt/maquita-webmail/www/webmail;
    index index.html;

    # Frontend (SPA)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name mail.example.com;
    return 301 https://$server_name$request_uri;
}
```

```bash
ln -s /etc/nginx/sites-available/maquita-webmail /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

## SSL/TLS with Let's Encrypt

```bash
certbot certonly --nginx -d mail.example.com
```

Set up automatic renewal:

```bash
systemctl enable --now certbot.timer
```

## DNS Records

Configure these DNS records for your domain:

| Type  | Name                      | Value                                              |
|-------|---------------------------|----------------------------------------------------|
| A     | mail.example.com          | `<server-ip>`                                      |
| MX    | example.com               | `10 mail.example.com`                              |
| TXT   | example.com               | `v=spf1 mx a:mail.example.com -all`                |
| TXT   | mail._domainkey.example.com | `v=DKIM1; k=rsa; p=<public-key>`                 |
| TXT   | _dmarc.example.com        | `v=DMARC1; p=reject; rua=mailto:dmarc@example.com` |
| TXT   | _mta-sts.example.com      | `v=STSv1; id=<timestamp>`                          |
| TLSA  | _25._tcp.mail.example.com | DANE record (3 1 1 <hash>)                         |
| PTR   | `<server-ip>`             | mail.example.com (set via hosting provider)         |

### MTA-STS Policy

Host at `https://mta-sts.example.com/.well-known/mta-sts.txt`:

```
version: STSv1
mode: enforce
mx: mail.example.com
max_age: 604800
```

## Systemd Hardening

The service unit above includes hardening directives. Verify the security score:

```bash
systemd-analyze security maquita-webmail
```

Target a score of 5.0 or lower (good). Additional hardening options:

```ini
CapabilityBoundingSet=
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
```

## Monitoring

Recommended monitoring stack:

- **Prometheus + Grafana** -- metrics and dashboards
- **Loki** -- centralized log aggregation
- **/api/health** endpoint -- HTTP health check
- **Uptime Kuma** or **Blackbox Exporter** -- external uptime monitoring

Key metrics to monitor:

- Mail queue size (`postqueue -p | tail -1`)
- Dovecot connections
- Backend response time (p95, p99)
- Disk usage on mail storage
- ClamAV definition freshness
- Certificate expiry

## Backup Strategy

### Database

```bash
# Daily logical backup
pg_dump -U maquita maquita_webmail | gzip > /backup/db/maquita_$(date +%Y%m%d).sql.gz

# Retain 30 days
find /backup/db/ -name "*.sql.gz" -mtime +30 -delete
```

### Mail storage

```bash
# Incremental with rsync
rsync -a --delete /var/vmail/ /backup/vmail/
```

### Configuration files

```bash
# Version-controlled backup
tar czf /backup/conf/etc_$(date +%Y%m%d).tar.gz \
  /etc/postfix /etc/dovecot /etc/rspamd /etc/nginx /etc/radicale
```

### Backup verification

- Test restore monthly on a staging server
- Verify database integrity: `pg_restore --list backup.sql.gz`
- Monitor backup job exit codes
- Store backups off-site (S3-compatible, separate datacenter)
