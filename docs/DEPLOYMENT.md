# Guía de Despliegue en Producción

Esta guía cubre el despliegue de Maquita Webmail en un servidor de producción con la pila de correo completa.

## Requisitos del Sistema

| Recurso  | Mínimo                              | Recomendado          |
|----------|-------------------------------------|----------------------|
| SO       | Debian 12+ / Ubuntu 24.04+          | Debian 12            |
| CPU      | 2 núcleos                           | 4 núcleos            |
| RAM      | 4 GB                                | 8 GB                 |
| Disco    | 40 GB SSD                           | 100 GB+ SSD          |
| Red      | IPv4 pública, registro PTR configurado | IPv4 + IPv6       |

Se requiere un nombre de dominio válido con control total de DNS.

## Instalar Paquetes del Sistema

```bash
apt update && apt upgrade -y

# Pila de correo
apt install -y postfix postfix-pgsql dovecot-core dovecot-imapd dovecot-lmtpd \
  dovecot-pgsql rspamd clamav clamav-daemon

# Web y base de datos
apt install -y nginx postgresql-17 postgresql-client-17 redis-server

# Entorno de ejecución
apt install -y python3.12 python3.12-venv python3-pip nodejs npm certbot \
  python3-certbot-nginx

# Utilidades
apt install -y git curl jq fail2ban ufw
```

## Configuración de Servicios

### PostgreSQL

```bash
sudo -u postgres createuser maquita
sudo -u postgres createdb -O maquita maquita_webmail
sudo -u postgres psql -c "ALTER USER maquita PASSWORD 'STRONG_PASSWORD_HERE';"
```

Aplique las migraciones:

```bash
for f in $(ls migrations/*.sql | sort); do
  sudo -u postgres psql -d maquita_webmail -f "$f"
done
```

Para ajuste de rendimiento, consulte la [documentación de PostgreSQL](https://www.postgresql.org/docs/17/runtime-config.html). Parámetros clave: `shared_buffers`, `work_mem`, `effective_cache_size`.

### Redis

Edite `/etc/redis/redis.conf`:

```
bind 127.0.0.1 ::1
maxmemory 256mb
maxmemory-policy allkeys-lru
```

```bash
systemctl enable --now redis-server
```

### Postfix

Configure como MTA de cara a internet. Archivos clave:

- `/etc/postfix/main.cf` -- configuración principal
- `/etc/postfix/master.cf` -- definiciones de servicios
- `/etc/postfix/pgsql-*.cf` -- mapas de consulta a PostgreSQL

Parámetros esenciales de `main.cf`:

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

Consulte la [documentación de Postfix](http://www.postfix.org/documentation.html).

### Dovecot

Configure IMAP y LMTP. Archivos clave:

- `/etc/dovecot/dovecot.conf`
- `/etc/dovecot/conf.d/10-auth.conf`
- `/etc/dovecot/conf.d/10-mail.conf`
- `/etc/dovecot/conf.d/10-ssl.conf`

Parámetros esenciales:

```
protocols = imap lmtp
mail_location = maildir:/var/vmail/%d/%n/Maildir
ssl_cert = </etc/letsencrypt/live/mail.example.com/fullchain.pem
ssl_key = </etc/letsencrypt/live/mail.example.com/privkey.pem
```

Consulte la [documentación de Dovecot](https://doc.dovecot.org/).

### Rspamd

Rspamd gestiona el filtrado de spam, la firma DKIM y la lista gris.

```bash
systemctl enable --now rspamd
```

Configure la firma DKIM en `/etc/rspamd/local.d/dkim_signing.conf`. Consulte la [documentación de Rspamd](https://rspamd.com/doc/).

### ClamAV

```bash
freshclam                          # actualizar definiciones de virus
systemctl enable --now clamav-daemon clamav-freshclam
```

### Radicale (CalDAV)

```bash
pip3 install radicale==3.0
```

Configure en `/etc/radicale/config`. Consulte la [documentación de Radicale](https://radicale.org/v3.html).

## Desplegar el Backend

### Crear usuario del sistema

```bash
useradd -r -s /usr/sbin/nologin -m -d /opt/maquita-webmail maquita
```

### Instalar la aplicación

```bash
cd /opt/maquita-webmail
git clone https://github.com/wilsongabriel30/webmailMaquita.git app
cd app/backend

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configurar el entorno

```bash
cp .env.example .env
# Edite .env con los valores de producción -- vea CONFIGURATION.md
chmod 600 .env
chown maquita:maquita .env
```

### Servicio systemd

Cree `/etc/systemd/system/maquita-webmail.service`:

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

# Endurecimiento de seguridad
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

## Desplegar el Frontend

```bash
cd /opt/maquita-webmail/app/frontend
npm ci --production=false
npm run build
```

Copie el resultado del build a nginx:

```bash
rm -rf /opt/maquita-webmail/www/webmail
cp -r dist /opt/maquita-webmail/www/webmail
chown -R www-data:www-data /opt/maquita-webmail/www/webmail
```

O use el script de despliegue:

```bash
bash /opt/maquita-webmail/deploy-webmail.sh
```

### Configuración de nginx

Cree `/etc/nginx/sites-available/maquita-webmail`:

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

    # API del backend
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

## SSL/TLS con Let's Encrypt

```bash
certbot certonly --nginx -d mail.example.com
```

Configure la renovación automática:

```bash
systemctl enable --now certbot.timer
```

## Registros DNS

Configure estos registros DNS para su dominio:

| Tipo  | Nombre                        | Valor                                              |
|-------|-------------------------------|----------------------------------------------------|
| A     | mail.example.com              | `<server-ip>`                                      |
| MX    | example.com                   | `10 mail.example.com`                              |
| TXT   | example.com                   | `v=spf1 mx a:mail.example.com -all`                |
| TXT   | mail._domainkey.example.com   | `v=DKIM1; k=rsa; p=<public-key>`                   |
| TXT   | _dmarc.example.com            | `v=DMARC1; p=reject; rua=mailto:dmarc@example.com` |
| TXT   | _mta-sts.example.com          | `v=STSv1; id=<timestamp>`                          |
| TLSA  | _25._tcp.mail.example.com     | Registro DANE (3 1 1 <hash>)                       |
| PTR   | `<server-ip>`                 | mail.example.com (configure con el proveedor de hosting) |

### Política MTA-STS

Publique en `https://mta-sts.example.com/.well-known/mta-sts.txt`:

```
version: STSv1
mode: enforce
mx: mail.example.com
max_age: 604800
```

## Endurecimiento con systemd

La unidad de servicio anterior incluye directivas de endurecimiento. Verifique la puntuación de seguridad:

```bash
systemd-analyze security maquita-webmail
```

Apunte a una puntuación de 5.0 o menor (buena). Opciones adicionales de endurecimiento:

```ini
CapabilityBoundingSet=
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
```

## Monitoreo

Pila de monitoreo recomendada:

- **Prometheus + Grafana** -- métricas y paneles de control
- **Loki** -- agregación centralizada de registros
- **/api/health** endpoint -- verificación de salud por HTTP
- **Uptime Kuma** o **Blackbox Exporter** -- monitoreo externo de disponibilidad

Métricas clave a monitorear:

- Tamaño de la cola de correo (`postqueue -p | tail -1`)
- Conexiones de Dovecot
- Tiempo de respuesta del backend (p95, p99)
- Uso de disco en el almacenamiento de correo
- Vigencia de las definiciones de ClamAV
- Vencimiento de certificados

## Estrategia de Respaldo

### Base de datos

```bash
# Respaldo lógico diario
pg_dump -U maquita maquita_webmail | gzip > /backup/db/maquita_$(date +%Y%m%d).sql.gz

# Retener 30 días
find /backup/db/ -name "*.sql.gz" -mtime +30 -delete
```

### Almacenamiento de correo

```bash
# Respaldo incremental con rsync
rsync -a --delete /var/vmail/ /backup/vmail/
```

### Archivos de configuración

```bash
# Respaldo con control de versiones
tar czf /backup/conf/etc_$(date +%Y%m%d).tar.gz \
  /etc/postfix /etc/dovecot /etc/rspamd /etc/nginx /etc/radicale
```

### Verificación de respaldos

- Pruebe la restauración mensualmente en un servidor de pruebas
- Verifique la integridad de la base de datos: `pg_restore --list backup.sql.gz`
- Monitoree los códigos de salida de los trabajos de respaldo
- Almacene los respaldos fuera del sitio (compatible con S3, datacenter separado)
