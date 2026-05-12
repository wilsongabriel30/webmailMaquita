# Fundación Maquita Webmail

Sistema de correo electrónico completo con interfaz web tipo Microsoft Outlook. Software libre para la inteligencia colectiva.

![Fundación Maquita Webmail](https://img.shields.io/badge/Fundación%20Maquita-Webmail-0078d4?style=for-the-badge)
![License](https://img.shields.io/badge/Licencia-MIT-green?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12+-blue?style=flat-square)
![React](https://img.shields.io/badge/React-19-61dafb?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-336791?style=flat-square)
![Dovecot](https://img.shields.io/badge/Dovecot-2.4-blue?style=flat-square)

## Descripcion

Webmail completo desarrollado por la Fundacion Maquita (Ecuador). Interfaz moderna tipo Outlook con correo, calendario, contactos, tareas, panel de administracion y seguridad avanzada. Diseñado para organizaciones que necesitan un sistema de correo propio, seguro y de alto rendimiento.

**En produccion** con 48,000+ emails, 13 buzones, 380+ peticiones/hora.

---

## Caracteristicas

### Correo Electronico
- Bandeja de entrada con vista previa (derecha, inferior, oculta, popout)
- Composicion avanzada con editor TipTap (tablas, imagenes, firmas HTML)
- Hilos de conversacion
- Busqueda avanzada full-text (FTS Xapian) con filtros (fecha, remitente, adjuntos, carpeta)
- Etiquetas personalizadas con colores
- Reglas de correo (filtros Sieve)
- Posponer correos (Snooze)
- Prioridades inteligentes
- Descarga masiva de adjuntos (.zip)
- Dictado por voz (Whisper)
- Asistente IA para redaccion
- Atajos de teclado completos
- Paleta de comandos (Ctrl+K)
- Sanitizacion XSS en visualizacion de correos (SafeEmailViewer)

### Calendario
- Vistas: mes, semana, dia, agenda
- Integracion CalDAV con Radicale
- Crear/editar/eliminar eventos
- Invitaciones ICS estilo Outlook (Aceptar/Tentativo/Rechazar con RSVP)
- Compartir calendarios
- Panel "Mi dia" en correo con agenda por horas

### Contactos
- CRUD completo con formulario detallado
- Categorias, favoritos, listas de distribucion
- Sincronizacion CardDAV
- Deteccion de duplicados
- Importar/exportar vCard y CSV
- Gravatar, campos personalizados
- Historial de interacciones
- Directorio global (GAL)
- Agregar remitentes a contactos desde correo recibido

### Tareas
- Tableros Kanban con listas y tarjetas
- Recordatorios con presets (Hoy, Manana, Proximo lunes)
- Recurrencia (diaria, semanal, mensual, anual)
- Emails marcados como tareas
- Ordenar por fecha, importancia, alfabetico

### Panel de Administracion
- Dashboard con estadisticas en tiempo real
- Gestion de dominios y buzones
- Aliases de correo
- Cola de correos (Postfix queue)
- Auditoria de acciones
- eDiscovery (busqueda forense en buzones)
- Impersonar usuarios
- Branding personalizable

### Seguridad
- Autenticacion JWT + cookies HttpOnly/Secure/SameSite
- 2FA/TOTP
- Certificados S/MIME
- Cifrado de emails en disco (mail_crypt secp521r1)
- Compresion de emails (gzip)
- Rate limiting por endpoint
- Cabeceras de seguridad (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)
- Rspamd antispam con analisis de reputacion
- ClamAV antivirus
- Filtro anti-spam Python personalizable por keywords
- Proteccion anti-compromiso de cuentas
- Blindaje anti-spam MIME con validacion al arranque
- Passwords cifrados en Redis con Fernet
- SPF, DKIM, DMARC (reject), MTA-STS (enforce), DANE

### Rendimiento
- FTS Xapian para busquedas full-text indexadas
- Cache Redis para UIDs, sesiones, estadisticas
- Pool de conexiones IMAP
- Compresion gzip en nginx y en emails almacenados
- Service Worker para cache de assets
- Lazy expunge para borrado rapido

### Extras
- PWA instalable (Progressive Web App)
- Service Worker para funcionamiento offline
- ActiveSync para moviles (Z-Push)
- Autoconfiguracion para Outlook y Thunderbird
- WebSocket para notificaciones en tiempo real
- Modo responsive

---

## Stack Tecnologico

| Componente | Tecnologia | Version |
|------------|-----------|---------|
| **Frontend** | React + TypeScript + Vite | React 19, Vite 6 |
| **Backend** | FastAPI + Uvicorn | FastAPI 0.115 |
| **Base de datos** | PostgreSQL | 17+ |
| **Cache** | Redis | 7+ |
| **SMTP** | Postfix | 3.7+ |
| **IMAP** | Dovecot | 2.4+ |
| **Antispam** | Rspamd | 3.8+ |
| **Antivirus** | ClamAV | 1.0+ |
| **Proxy** | Nginx | 1.22+ |
| **CalDAV/CardDAV** | Radicale | 3.0+ |
| **SSL** | Let's Encrypt / Certbot | - |
| **Busqueda** | FTS Xapian | Integrado en Dovecot |
| **Runtime** | Python 3.12+ / Node.js 18+ | - |
| **SO** | Debian 12+ o Ubuntu 22.04+ | - |

---

## Requisitos del Servidor

### Hardware minimo

| Recurso | Minimo | Recomendado |
|---------|--------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Disco | 20 GB | 50+ GB (segun buzones) |

### Registros DNS necesarios

Antes de instalar, configura estos registros en tu proveedor de dominio:

| Tipo | Nombre | Valor |
|------|--------|-------|
| **A** | `mail.tudominio.com` | `IP_DE_TU_SERVIDOR` |
| **MX** | `tudominio.com` | `mail.tudominio.com` (prioridad 10) |
| **TXT** | `tudominio.com` | `v=spf1 ip4:IP_SERVIDOR mx -all` |
| **TXT** | `_dmarc.tudominio.com` | `v=DMARC1; p=reject; rua=mailto:postmaster@tudominio.com` |
| **TXT** | `mail._domainkey.tudominio.com` | *(se genera en paso 7)* |
| **TXT** | `_mta-sts.tudominio.com` | `v=STSv1; id=YYYYMMDD` |
| **CNAME** | `autoconfig.tudominio.com` | `mail.tudominio.com` |
| **CNAME** | `autodiscover.tudominio.com` | `mail.tudominio.com` |
| **SRV** | `_imaps._tcp.tudominio.com` | `0 1 993 mail.tudominio.com` |
| **SRV** | `_submission._tcp.tudominio.com` | `0 1 587 mail.tudominio.com` |

---

## Instalacion Paso a Paso

### 1. Preparar el servidor

```bash
# Actualizar sistema
apt update && apt upgrade -y

# Instalar paquetes base
apt install -y curl wget git sudo ufw software-properties-common \
  build-essential python3 python3-venv python3-pip nodejs npm
```

### 2. Configurar hostname

```bash
hostnamectl set-hostname mail.tudominio.com
echo "IP_DE_TU_SERVIDOR mail.tudominio.com" >> /etc/hosts
```

### 3. Instalar PostgreSQL

```bash
apt install -y postgresql postgresql-contrib

sudo -u postgres psql << 'SQL'
CREATE USER mailserver WITH PASSWORD 'TU_PASSWORD_SEGURA';
CREATE DATABASE maildb OWNER mailserver;
GRANT ALL PRIVILEGES ON DATABASE maildb TO mailserver;
\c maildb
GRANT ALL ON SCHEMA public TO mailserver;
SQL
```

### 4. Instalar Redis

```bash
apt install -y redis-server

# Configurar contraseña
sed -i 's/# requirepass foobared/requirepass TU_REDIS_PASSWORD/' /etc/redis/redis.conf
systemctl restart redis-server
```

### 5. Instalar Postfix

```bash
apt install -y postfix postfix-pgsql

# Seleccionar "Internet Site" cuando pregunte
# Hostname: mail.tudominio.com
```

Configurar `/etc/postfix/main.cf`:
```ini
myhostname = mail.tudominio.com
mydomain = tudominio.com
myorigin = $mydomain
mydestination = localhost
mynetworks = 127.0.0.0/8

# Buzones virtuales via PostgreSQL
virtual_mailbox_domains = pgsql:/etc/postfix/pgsql-virtual-domains.cf
virtual_mailbox_maps = pgsql:/etc/postfix/pgsql-virtual-mailboxes.cf
virtual_alias_maps = pgsql:/etc/postfix/pgsql-virtual-aliases.cf

# Entregar via Dovecot LMTP
virtual_transport = lmtp:unix:private/dovecot-lmtp

# TLS
smtpd_tls_cert_file = /etc/letsencrypt/live/mail.tudominio.com/fullchain.pem
smtpd_tls_key_file = /etc/letsencrypt/live/mail.tudominio.com/privkey.pem
smtpd_tls_security_level = may
smtpd_tls_protocols = >=TLSv1.2
smtp_tls_security_level = dane

# Limites
message_size_limit = 26214400
mailbox_size_limit = 0

# Autenticacion SASL via Dovecot
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
smtpd_sasl_auth_enable = yes

# Restricciones (permisivas - el filtro Python clasifica internamente)
smtpd_recipient_restrictions = permit_sasl_authenticated, permit_mynetworks, reject_unauth_destination
smtpd_client_restrictions = permit_mynetworks, permit

# Rspamd como milter
smtpd_milters = inet:localhost:11332
non_smtpd_milters = inet:localhost:11332
milter_protocol = 6
milter_default_action = accept
```

Crear archivos de consulta PostgreSQL:

`/etc/postfix/pgsql-virtual-domains.cf`:
```ini
hosts = localhost
user = mailserver
password = TU_PASSWORD_SEGURA
dbname = maildb
query = SELECT domain FROM domain WHERE domain='%s' AND active='1'
```

`/etc/postfix/pgsql-virtual-mailboxes.cf`:
```ini
hosts = localhost
user = mailserver
password = TU_PASSWORD_SEGURA
dbname = maildb
query = SELECT maildir FROM mailbox WHERE username='%s' AND active='1'
```

`/etc/postfix/pgsql-virtual-aliases.cf`:
```ini
hosts = localhost
user = mailserver
password = TU_PASSWORD_SEGURA
dbname = maildb
query = SELECT goto FROM alias WHERE address='%s' AND active='1'
```

### 6. Instalar Dovecot

```bash
apt install -y dovecot-core dovecot-imapd dovecot-lmtpd dovecot-pgsql \
  dovecot-sieve dovecot-managesieved dovecot-fts-xapian
```

Crear usuario vmail:
```bash
groupadd -g 150 vmail
useradd -u 150 -g vmail -d /var/vmail -s /usr/sbin/nologin -m vmail
```

Configurar `/etc/dovecot/conf.d/10-mail.conf`:
```ini
mail_location = maildir:/var/vmail/%d/%n/Maildir
mail_home = /var/vmail/%d/%n
mail_uid = vmail
mail_gid = vmail
first_valid_uid = 150

# Plugins: FTS, cifrado, compresion, quota
mail_plugins = quota acl fts fts_xapian lazy_expunge mail_crypt mail_compress

# Compresion de emails almacenados
mail_compress_write_method = gz
```

Configurar `/etc/dovecot/conf.d/10-auth.conf`:
```ini
disable_plaintext_auth = yes
auth_mechanisms = plain login
!include auth-sql.conf.ext
```

Crear `/etc/dovecot/dovecot-sql.conf.ext`:
```ini
driver = pgsql
connect = host=localhost dbname=maildb user=mailserver password=TU_PASSWORD_SEGURA
default_pass_scheme = BLF-CRYPT
password_query = SELECT username AS user, password, \
  '/var/vmail/%d/%n/Maildir' AS userdb_home, \
  150 AS userdb_uid, 150 AS userdb_gid \
  FROM mailbox WHERE username = '%u' AND active = '1'
user_query = SELECT '/var/vmail/%d/%n/Maildir' AS home, \
  150 AS uid, 150 AS gid \
  FROM mailbox WHERE username = '%u'
```

Configurar FTS Xapian `/etc/dovecot/conf.d/90-fts.conf`:
```ini
fts_autoindex = yes
fts_autoindex_max_recent_msgs = 999
fts_search_add_missing = yes

language "en" {
  default = yes
}

language "es" {
}

fts xapian {
  verbose = 0
  maxthreads = 4
  lowmemory = 256
  partial = 2
}

service indexer-worker {
  vsz_limit = 2G
  process_limit = 4
}
```

Configurar cifrado en reposo `/etc/dovecot/conf.d/10-mail.conf` (agregar):
```ini
# Cifrado de emails en disco
plugin {
  mail_crypt_curve = secp521r1
}
```

```bash
systemctl restart dovecot postfix
```

### 7. Instalar Rspamd (antispam) y ClamAV (antivirus)

```bash
apt install -y rspamd clamav clamav-daemon

# Generar clave DKIM
mkdir -p /var/lib/rspamd/dkim
rspamadm dkim_keygen -b 2048 -s mail -d tudominio.com \
  -k /var/lib/rspamd/dkim/tudominio.com.mail.key \
  > /var/lib/rspamd/dkim/tudominio.com.mail.txt
chown -R _rspamd:_rspamd /var/lib/rspamd/dkim

# Mostrar registro DKIM para agregar en DNS
cat /var/lib/rspamd/dkim/tudominio.com.mail.txt
```

Configurar DKIM en `/etc/rspamd/local.d/dkim_signing.conf`:
```ini
enabled = true;
sign_authenticated = true;
sign_local = true;
use_domain = "header";
selector = "mail";
path = "/var/lib/rspamd/dkim/$domain.mail.key";
allow_username_mismatch = true;
```

Configurar acciones en `/etc/rspamd/local.d/actions.conf`:
```ini
# NUNCA rechazar correos - solo marcar para que sieve clasifique
reject = null;
greylist = 4;
add_header = 6;
rewrite_subject = 12;
```

Configurar ClamAV en `/etc/rspamd/local.d/antivirus.conf`:
```ini
clamav {
  action = "add_header";
  type = "clamav";
  servers = "/var/run/clamav/clamd.ctl";
  scan_mime_parts = true;
  symbol = "CLAM_VIRUS";
}
```

```bash
systemctl restart rspamd clamav-daemon
```

### 8. Configurar Sieve (clasificacion automatica de spam)

Crear `/var/vmail/sieve/before.sieve`:
```sieve
require ["fileinto", "mailbox"];

# Rspamd marca como spam
if header :is "X-Spam-Flag" "YES" {
    fileinto :create "Junk";
    stop;
}

if header :contains "X-Spam-Status" "Yes" {
    fileinto :create "Junk";
    stop;
}

# Filtro Python personalizado
if header :is "X-Maquita-Spam" "YES" {
    fileinto :create "Junk";
    stop;
}
```

```bash
sievec /var/vmail/sieve/before.sieve
chown -R vmail:vmail /var/vmail/sieve
```

### 9. Instalar filtro anti-spam Python (opcional pero recomendado)

El filtro analiza cada correo entrante buscando palabras clave configurables y los clasifica sin rechazar nada.

```bash
mkdir -p /opt/maquita-mail-filter /etc/maquita-mail

# Copiar el script (esta en el repo)
cp /opt/maquita-webmail/scripts/spam-filter-service.py /opt/maquita-mail-filter/
chmod +x /opt/maquita-mail-filter/spam-filter-service.py
```

Crear `/etc/maquita-mail/spam-keywords.txt`:
```
# Formato: palabra_o_frase | peso
# Score >= 3 = SPAM (va a Junk)
# Se lee en cada correo, no requiere reiniciar

# Phishing
your account has been suspended|3
verify your account immediately|3
su cuenta ha sido suspendida|3

# Premios / Estafas
you have won|3
has ganado|3
claim your prize|3

# Financiero
nigerian prince|5
herencia millonaria|3
earn money from home|3
```

Crear `/etc/maquita-mail/whitelist-senders.txt`:
```
# Dominios que NUNCA van a spam
gmail.com
outlook.com
hotmail.com
yahoo.com
tudominio.com
```

Agregar en `/etc/postfix/master.cf`:
```
# Filtro anti-spam Python
maquita-filter unix - n n - 10 pipe
  flags=Rq user=vmail argv=/opt/maquita-mail-filter/spam-filter-service.py -f ${sender} -- ${recipient}

# Reinyeccion sin filtro (evitar loop)
10025 inet n - n - 10 smtpd
  -o content_filter=
  -o receive_override_options=no_unknown_recipient_checks,no_header_body_checks
  -o smtpd_recipient_restrictions=permit_mynetworks,reject
  -o mynetworks=127.0.0.0/8
```

En `/etc/postfix/main.cf` agregar:
```ini
content_filter = maquita-filter:
```

```bash
touch /var/log/maquita-spam-filter.log
chown vmail:vmail /var/log/maquita-spam-filter.log
systemctl restart postfix
```

### 10. Instalar Radicale (CalDAV/CardDAV)

```bash
pip3 install radicale
mkdir -p /var/lib/radicale/collections /etc/radicale
useradd -r -s /usr/sbin/nologin radicale
chown -R radicale:radicale /var/lib/radicale
```

Crear `/etc/radicale/config`:
```ini
[server]
hosts = 127.0.0.1:5232

[auth]
type = none

[storage]
filesystem_folder = /var/lib/radicale/collections

[logging]
level = warning
```

Crear `/etc/systemd/system/radicale.service`:
```ini
[Unit]
Description=Radicale CalDAV/CardDAV Server
After=network.target

[Service]
Type=simple
User=radicale
ExecStart=/usr/local/bin/radicale
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now radicale
```

### 11. Certificado SSL

```bash
apt install -y certbot python3-certbot-nginx
certbot certonly --nginx -d mail.tudominio.com
```

### 12. Instalar Fundacion Maquita Webmail

```bash
cd /opt
git clone https://github.com/wilsongabriel30/webmailMaquita.git maquita-webmail
cd maquita-webmail

# === Backend ===
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
nano .env  # Editar con tus datos

# === Frontend ===
cd ../frontend
npm install
npm run build

# Crear estructura de despliegue
mkdir -p /opt/maquita-webmail/www
ln -sf /opt/maquita-webmail/frontend/dist /opt/maquita-webmail/www/webmail
```

### 13. Configurar variables de entorno

Editar `/opt/maquita-webmail/backend/.env` (copiar de `.env.example`):
```ini
# Base de datos
DATABASE_URL=postgresql://mailserver:TU_PASSWORD@localhost:5432/maildb

# Redis
REDIS_URL=redis://:TU_REDIS_PASSWORD@localhost:6379/0

# JWT (generar con: python3 -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=GENERA_CON_SECRETS_TOKEN_HEX

# Servidor de correo
IMAP_HOST=127.0.0.1
IMAP_PORT=143
SMTP_HOST=127.0.0.1
SMTP_PORT=587
SIEVE_HOST=127.0.0.1
SIEVE_PORT=4190

# Tu dominio
MAIL_DOMAIN=tudominio.com
COOKIE_DOMAIN=mail.tudominio.com
CORS_ORIGINS=https://mail.tudominio.com

# Administracion
MASTER_PASSWORD=GENERA_PASSWORD_SEGURA
ADMIN_JWT_SECRET=GENERA_OTRO_SECRET
```

### 14. Crear servicio systemd

Crear `/etc/systemd/system/maquita-webmail.service`:
```ini
[Unit]
Description=Fundacion Maquita Webmail API
After=network.target postgresql.service redis-server.service dovecot.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/maquita-webmail/backend
Environment=PATH=/opt/maquita-webmail/backend/venv/bin:/usr/local/bin:/usr/bin
EnvironmentFile=/opt/maquita-webmail/backend/.env
ExecStart=/opt/maquita-webmail/backend/venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 4 --loop uvloop
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now maquita-webmail
```

### 15. Configurar Nginx

Crear `/etc/nginx/sites-available/mail.tudominio.com`:
```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;

server {
    listen 80;
    server_name mail.tudominio.com;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name mail.tudominio.com;

    ssl_certificate /etc/letsencrypt/live/mail.tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mail.tudominio.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    # Webmail SPA
    location /webmail/ {
        root /opt/maquita-webmail/www;
        location = /webmail/sw.js {
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Service-Worker-Allowed "/webmail/";
        }
        location ~* /webmail/assets/ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
        try_files $uri $uri/ /webmail/index.html;
    }

    # API
    location = /api/auth/login {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://127.0.0.1:8000;
        include proxy_params;
    }

    location /api/ {
        limit_req zone=api burst=80 nodelay;
        proxy_pass http://127.0.0.1:8000;
        include proxy_params;
        client_max_body_size 25M;
        proxy_read_timeout 120s;
    }

    # WebSocket
    location /api/ws {
        proxy_pass http://127.0.0.1:8000/api/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }

    # CalDAV/CardDAV
    location /.well-known/caldav { return 301 /dav/; }
    location /.well-known/carddav { return 301 /dav/; }
    location /dav/ {
        proxy_pass http://127.0.0.1:5232/;
        client_max_body_size 50M;
    }

    # Rspamd UI (solo admin)
    location /rspamd/ {
        auth_basic "Rspamd Admin";
        auth_basic_user_file /etc/nginx/.htpasswd_rspamd;
        proxy_pass http://127.0.0.1:11334/;
    }

    location / { return 301 /webmail; }
}
```

```bash
ln -sf /etc/nginx/sites-available/mail.tudominio.com /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 16. Crear primer buzon

```bash
# Generar password cifrado
doveadm pw -s BLF-CRYPT -p TuPasswordSegura

# Crear dominio y buzon
sudo -u postgres psql -d maildb << 'SQL'
INSERT INTO domain (domain, description, transport, active)
VALUES ('tudominio.com', 'Dominio principal', 'virtual', 1);

INSERT INTO mailbox (username, password, name, maildir, domain, active)
VALUES (
  'usuario@tudominio.com',
  '$2y$05$...HASH_GENERADO...',
  'Nombre del Usuario',
  'tudominio.com/usuario/Maildir/',
  'tudominio.com',
  1
);

INSERT INTO alias (address, goto, domain, active)
VALUES ('usuario@tudominio.com', 'usuario@tudominio.com', 'tudominio.com', 1);
SQL
```

### 17. Verificar instalacion

```bash
# Servicios
systemctl status maquita-webmail postfix dovecot postgresql redis-server nginx rspamd radicale

# Puertos
ss -tlnp | grep -E '25|143|443|587|993|5232|8000'

# API
curl -s http://127.0.0.1:8000/docs | head -5

# Test envio
echo "Prueba de instalacion" | mail -s "Test" usuario@tudominio.com

# Test DKIM
dig +short TXT mail._domainkey.tudominio.com
```

Abrir en el navegador: `https://mail.tudominio.com/webmail/`

---

## Estructura del Proyecto

```
maquita-webmail/
├── backend/
│   ├── app/
│   │   ├── main.py              # Punto de entrada FastAPI
│   │   ├── config.py            # Configuracion central
│   │   ├── admin/               # Panel de administracion + eDiscovery
│   │   ├── ai/                  # Asistente IA (Ollama)
│   │   ├── auth/                # Autenticacion JWT + TOTP
│   │   ├── branding/            # Personalizacion visual
│   │   ├── calendar/            # Calendario (CalDAV/Radicale)
│   │   ├── contacts/            # Contactos (CardDAV)
│   │   ├── core/                # DB, Redis, sesion, sanitizacion
│   │   ├── gal/                 # Directorio global (GAL)
│   │   ├── identities/          # Identidades de correo
│   │   ├── mail/                # Correo (IMAP/SMTP)
│   │   │   ├── clients/         # IMAP client + pool conexiones
│   │   │   ├── parsers/         # MIME parser + HTML sanitizer
│   │   │   ├── routers/         # Endpoints REST
│   │   │   └── services/        # Logica de negocio
│   │   ├── meetings/            # Reuniones
│   │   ├── nextcloud/           # Integracion Nextcloud
│   │   ├── presence/            # Estado en linea
│   │   ├── rooms/               # Salas de reunion
│   │   ├── security/            # Seguridad avanzada
│   │   ├── settings/            # Preferencias de usuario
│   │   ├── sieve/               # Reglas de correo
│   │   ├── smime/               # Certificados S/MIME
│   │   ├── sso/                 # Single Sign-On
│   │   ├── tasks/               # Tareas (Kanban)
│   │   ├── webhooks/            # Webhooks
│   │   └── websocket/           # Notificaciones tiempo real
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Router principal
│   │   ├── components/
│   │   │   ├── admin/           # Admin + eDiscovery
│   │   │   ├── auth/            # Login
│   │   │   ├── calendar/        # Calendario
│   │   │   ├── common/          # Componentes compartidos
│   │   │   ├── compose/         # Editor TipTap
│   │   │   ├── contacts/        # Contactos
│   │   │   ├── layout/          # NavRail, Topbar, Sidebar
│   │   │   ├── mail/            # MailView, MessageList, SafeEmailViewer
│   │   │   ├── settings/        # Configuracion + 2FA
│   │   │   └── tasks/           # Kanban
│   │   ├── hooks/               # Custom hooks (shortcuts, presence, websocket)
│   │   ├── lib/                 # Utilidades (sanitize, syncQueue)
│   │   ├── store/               # Zustand (estado global)
│   │   └── types/               # Tipos TypeScript
│   ├── public/
│   │   ├── sw.js                # Service Worker
│   │   └── manifest.json        # PWA manifest
│   └── package.json
│
├── deploy/                      # Scripts de despliegue
├── docs/                        # Documentacion adicional
├── deploy-webmail.sh            # Script de deploy seguro
├── zimbra-sync.sh               # Script migracion desde Zimbra
├── .gitignore
├── CHANGELOG.md
├── LICENSE                      # MIT
└── README.md
```

---

## Base de Datos

El sistema usa **84 tablas** en PostgreSQL, organizadas por modulo:

| Modulo | Tablas principales |
|--------|-------------------|
| **Correo** | `mailbox`, `domain`, `alias`, `user_labels`, `message_labels`, `snoozed_emails`, `scheduled_emails`, `mail_log` |
| **Calendario** | `calendars`, `events`, `event_invitations`, `calendar_shares`, `meeting_rooms`, `room_bookings` |
| **Contactos** | `user_contacts`, `org_contacts`, `contact_categories`, `contact_lists`, `contact_relationships`, `contact_reminders` |
| **Tareas** | `task_boards`, `task_lists`, `task_cards`, `task_labels`, `task_activity`, `task_steps` |
| **Admin** | `admin_users`, `admin_sessions`, `admin_audit`, `branding_settings` |
| **Seguridad** | `user_totp`, `smime_certificates`, `api_keys`, `sso_config`, `spam_analysis`, `attachment_scans` |
| **Otros** | `user_preferences`, `user_signatures`, `email_templates`, `webhooks`, `retention_policies` |

Las tablas se crean automaticamente al iniciar el backend por primera vez.

---

## Puertos Utilizados

| Puerto | Servicio | Acceso |
|--------|----------|--------|
| 25 | Postfix SMTP | Publico |
| 80 | Nginx HTTP (redirect) | Publico |
| 143 | Dovecot IMAP | Local |
| 443 | Nginx HTTPS | Publico |
| 587 | Postfix Submission | Publico |
| 993 | Dovecot IMAPS | Publico |
| 4190 | Sieve (ManageSieve) | Local |
| 5232 | Radicale CalDAV | Local |
| 5432 | PostgreSQL | Local |
| 6379 | Redis | Local |
| 8000 | Webmail API (FastAPI) | Local |
| 10025 | Postfix reinyeccion (filtro) | Local |
| 11332 | Rspamd milter | Local |
| 11334 | Rspamd Web UI | Local |

---

## Comandos Utiles

```bash
# Reiniciar webmail
systemctl restart maquita-webmail

# Ver logs del webmail
journalctl -u maquita-webmail -f

# Ver log del filtro anti-spam
tail -f /var/log/maquita-spam-filter.log

# Deploy seguro (frontend)
bash /opt/maquita-webmail/deploy-webmail.sh

# Verificar correo de un usuario
doveadm mailbox list -u usuario@tudominio.com

# Buscar en emails (FTS)
doveadm search -u usuario@tudominio.com mailbox INBOX text "busqueda"

# Generar password para nuevo buzon
doveadm pw -s BLF-CRYPT

# Backup de base de datos
pg_dump -U mailserver maildb > backup_$(date +%Y%m%d).sql

# Actualizar desde GitHub
cd /opt/maquita-webmail
git pull origin main
bash deploy-webmail.sh
```

---

## Migracion desde Zimbra

El proyecto incluye un script para migrar buzones desde Zimbra:

```bash
# Migrar un buzon
bash zimbra-sync.sh usuario@tudominio.com IP_ZIMBRA
```

El script usa `imapsync` para copiar todos los correos preservando carpetas, fechas y flags.

---

## Solucion de Problemas

| Problema | Solucion |
|----------|----------|
| No carga la interfaz | `systemctl status maquita-webmail` — verificar backend activo |
| Error 502 Bad Gateway | Backend no responde: `curl http://127.0.0.1:8000/docs` |
| No llegan correos | Verificar: `tail -f /var/log/mail.log` y registros MX en DNS |
| Correos van a spam en Gmail | Verificar DKIM: `dig +short TXT mail._domainkey.tudominio.com` |
| No se puede enviar | Verificar Dovecot SASL y puerto 587 |
| Busqueda lenta | Reindexar FTS: `doveadm fts rescan -u usuario@tudominio.com` |
| Cache vieja del navegador | Ctrl+Shift+R o borrar Service Worker en DevTools |
| Error de certificado | Renovar: `certbot renew` |
| Calendario no funciona | Verificar Radicale: `systemctl status radicale` |
| Correos legitimos en Junk | Agregar dominio a `/etc/maquita-mail/whitelist-senders.txt` |

---

## Contribuir

1. Fork del repositorio
2. Crear rama: `git checkout -b mi-mejora`
3. Hacer cambios y commit
4. Push: `git push origin mi-mejora`
5. Crear Pull Request

---

## Licencia

Este proyecto es **software libre** bajo la licencia **MIT**. Usalo, modificalo y compartelo libremente.

---

## Creditos

- **Fundacion Maquita** — Comercializadora asociativa sin fines de lucro, Ecuador
- **Wilson Gabriel Arguello Robalino** — Desarrollo y arquitectura

*"Tecnologia al servicio de todos, no solo de quienes pueden pagarla."*
