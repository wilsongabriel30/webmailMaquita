# Fundación Maquita Webmail

Sistema de correo electrónico completo con interfaz web tipo Microsoft Outlook. Software libre para la inteligencia colectiva.

![Fundación Maquita Webmail](https://img.shields.io/badge/Fundación%20Maquita-Webmail-0078d4?style=for-the-badge)
![License](https://img.shields.io/badge/Licencia-MIT-green?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)
![React](https://img.shields.io/badge/React-19-61dafb?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square)

## Características

### Correo Electrónico
- Bandeja de entrada con vista previa (derecha, inferior, oculta, popout)
- Composición avanzada con editor TipTap (tablas, imágenes, firmas HTML)
- Hilos de conversación
- Búsqueda avanzada con filtros (fecha, remitente, adjuntos, carpeta)
- Etiquetas personalizadas con colores
- Reglas de correo (filtros Sieve)
- Posponer correos (Snooze)
- Prioridades inteligentes
- Descarga masiva de adjuntos (.zip)
- Dictado por voz (Whisper)
- Asistente IA para redacción
- Atajos de teclado completos
- Paleta de comandos (Ctrl+K)

### Calendario
- Vistas: mes, semana, día, agenda
- Integración CalDAV con Radicale
- Crear/editar/eliminar eventos
- Invitaciones y compartir calendarios
- Panel "Mi día" en correo con agenda por horas

### Contactos
- CRUD completo con formulario detallado
- Categorías, favoritos, listas de distribución
- Sincronización CardDAV
- Detección de duplicados
- Importar/exportar vCard y CSV
- Gravatar, campos personalizados
- Historial de interacciones
- Directorio global (GAL)

### Tareas
- Tableros Kanban con listas y tarjetas
- Recordatorios con presets (Hoy, Mañana, Próximo lunes)
- Recurrencia (diaria, semanal, mensual, anual)
- Emails marcados como tareas
- Ordenar por fecha, importancia, alfabético

### Panel de Administración
- Dashboard con estadísticas
- Gestión de dominios y buzones
- Aliases de correo
- Auditoría de acciones
- Impersonar usuarios

### Seguridad
- Autenticación JWT + cookies HttpOnly
- 2FA/TOTP
- Certificados S/MIME
- Rate limiting por endpoint
- Cabeceras de seguridad (HSTS, CSP, X-Frame-Options)
- Rspamd antispam

### Extras
- PWA instalable (Progressive Web App)
- Service Worker para funcionamiento offline
- ActiveSync para móviles (Z-Push)
- Autoconfiguración para Outlook y Thunderbird
- WebSocket para notificaciones en tiempo real
- Modo responsive

---

## Requisitos del Servidor

### Hardware mínimo
| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Disco | 20 GB | 50+ GB (según buzones) |

### Sistema Operativo
- **Debian 12 (Bookworm)** o **Debian 13 (Trixie)** — recomendado
- Ubuntu 22.04+ también funciona

### Software necesario

| Componente | Versión mínima | Descripción |
|------------|---------------|-------------|
| **Postfix** | 3.5+ | Servidor SMTP |
| **Dovecot** | 2.3+ | Servidor IMAP/LMTP |
| **PostgreSQL** | 14+ | Base de datos |
| **Redis** | 6+ | Cache y sesiones |
| **Nginx** | 1.18+ | Proxy reverso |
| **Python** | 3.11+ | Backend API |
| **Node.js** | 18+ | Compilar frontend |
| **Radicale** | 3.0+ | CalDAV/CardDAV |
| **Certbot** | 1.0+ | Certificados SSL |
| **Rspamd** | 3.0+ | Antispam |

### Opcionales
| Componente | Descripción |
|------------|-------------|
| Z-Push | ActiveSync para móviles |
| OnlyOffice | Vista previa de documentos Office |
| Ollama/Whisper | IA asistente y transcripción de voz |

---

## Instalación Paso a Paso

### 1. Preparar el servidor

```bash
# Actualizar sistema
apt update && apt upgrade -y

# Instalar paquetes base
apt install -y curl wget git sudo ufw software-properties-common
```

### 2. Configurar hostname y DNS

```bash
# Configurar hostname
hostnamectl set-hostname mail.tudominio.com
echo "IP_DE_TU_SERVIDOR mail.tudominio.com" >> /etc/hosts
```

**Registros DNS necesarios** (en tu proveedor de dominio):

| Tipo | Nombre | Valor |
|------|--------|-------|
| **A** | `mail.tudominio.com` | `IP_DE_TU_SERVIDOR` |
| **MX** | `tudominio.com` | `mail.tudominio.com` (prioridad 10) |
| **TXT** | `tudominio.com` | `v=spf1 mx a ip4:IP_SERVIDOR ~all` |
| **TXT** | `_dmarc.tudominio.com` | `v=DMARC1; p=quarantine; rua=mailto:postmaster@tudominio.com` |
| **CNAME** | `autoconfig.tudominio.com` | `mail.tudominio.com` |
| **CNAME** | `autodiscover.tudominio.com` | `mail.tudominio.com` |
| **SRV** | `_imaps._tcp.tudominio.com` | `0 1 993 mail.tudominio.com` |
| **SRV** | `_submission._tcp.tudominio.com` | `0 1 587 mail.tudominio.com` |

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

# Configurar como "Internet Site"
# Hostname: mail.tudominio.com
```

Crear `/etc/postfix/main.cf`:
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
smtpd_tls_cert_file = /etc/ssl/tu-certificado/fullchain.pem
smtpd_tls_key_file = /etc/ssl/tu-certificado/privkey.pem
smtpd_tls_security_level = may
smtp_tls_security_level = may

# Límites
message_size_limit = 26214400
mailbox_size_limit = 0

# Autenticación SASL via Dovecot
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
smtpd_sasl_auth_enable = yes
smtpd_recipient_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_unauth_destination
```

Crear `/etc/postfix/pgsql-virtual-domains.cf`:
```ini
hosts = localhost
user = mailserver
password = TU_PASSWORD_SEGURA
dbname = maildb
query = SELECT domain FROM domain WHERE domain='%s' AND active='1'
```

Crear `/etc/postfix/pgsql-virtual-mailboxes.cf`:
```ini
hosts = localhost
user = mailserver
password = TU_PASSWORD_SEGURA
dbname = maildb
query = SELECT maildir FROM mailbox WHERE username='%s' AND active='1'
```

Crear `/etc/postfix/pgsql-virtual-aliases.cf`:
```ini
hosts = localhost
user = mailserver
password = TU_PASSWORD_SEGURA
dbname = maildb
query = SELECT goto FROM alias WHERE address='%s' AND active='1'
```

### 6. Instalar Dovecot

```bash
apt install -y dovecot-core dovecot-imapd dovecot-lmtpd dovecot-pgsql dovecot-sieve dovecot-managesieved
```

Configurar `/etc/dovecot/conf.d/10-mail.conf`:
```ini
mail_location = maildir:/var/vmail/%d/%n/Maildir
mail_uid = vmail
mail_gid = vmail
first_valid_uid = 150
```

Crear usuario vmail:
```bash
groupadd -g 150 vmail
useradd -u 150 -g vmail -d /var/vmail -s /usr/sbin/nologin -m vmail
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
password_query = SELECT username AS user, password, '/var/vmail/%d/%n/Maildir' AS userdb_home, 150 AS userdb_uid, 150 AS userdb_gid FROM mailbox WHERE username = '%u' AND active = '1'
user_query = SELECT '/var/vmail/%d/%n/Maildir' AS home, 150 AS uid, 150 AS gid FROM mailbox WHERE username = '%u'
```

```bash
systemctl restart dovecot postfix
```

### 7. Instalar Rspamd (antispam)

```bash
apt install -y rspamd
# Rspamd funciona automáticamente con Postfix via milter
```

### 8. Instalar Radicale (CalDAV/CardDAV)

```bash
pip3 install radicale

mkdir -p /var/lib/radicale/collections /etc/radicale
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

Crear servicio systemd `/etc/systemd/system/radicale.service`:
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
useradd -r -s /usr/sbin/nologin radicale
chown -R radicale:radicale /var/lib/radicale
systemctl enable --now radicale
```

### 9. Certificado SSL

```bash
apt install -y certbot python3-certbot-nginx

# Opción A: Let's Encrypt
certbot certonly --nginx -d mail.tudominio.com

# Opción B: Wildcard (requiere DNS challenge)
certbot certonly --manual --preferred-challenges dns -d "*.tudominio.com" -d "tudominio.com"
```

### 10. Instalar Fundación Maquita Webmail

```bash
# Clonar repositorio
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
nano .env  # Editar con tus datos (ver sección Configuración)

# Crear tablas de la base de datos
# Las tablas se crean automáticamente al iniciar la API por primera vez

# === Frontend ===
cd ../frontend
npm install
```

Editar `frontend/vite.config.ts` — cambiar `base` a tu ruta:
```typescript
export default defineConfig({
  base: '/webmail/',
  // ... resto de configuración
})
```

Editar `frontend/src/api/client.ts` — verificar que la URL base sea `/api`:
```typescript
const API_BASE = '/api';
```

```bash
# Compilar frontend
npx vite build

# Crear estructura de despliegue
mkdir -p /opt/maquita-webmail/www
ln -sf /opt/maquita-webmail/frontend/dist /opt/maquita-webmail/www/webmail
```

### 11. Configurar variables de entorno

Crear `/opt/maquita-webmail/backend/.env`:
```ini
# Base de datos
DATABASE_URL=postgresql://mailserver:TU_PASSWORD_DB@localhost:5432/maildb

# Redis
REDIS_URL=redis://:TU_REDIS_PASSWORD@localhost:6379/0

# Clave secreta para JWT (generar una única)
SECRET_KEY=GENERA_CON_python3 -c "import secrets; print(secrets.token_hex(32))"

# Servidor de correo (local)
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

# Contraseña maestra para administración
MASTER_PASSWORD=GENERA_UNA_PASSWORD_SEGURA
ADMIN_JWT_SECRET=GENERA_OTRO_SECRET_AQUI

# Opcional: IA (si tienes servidor con Ollama)
# IA_API_KEY=tu-clave
# OLLAMA_URL=http://ip-servidor-ia:8000
```

### 12. Crear servicio systemd

Crear `/etc/systemd/system/maquita-webmail.service`:
```ini
[Unit]
Description=Fundación Maquita Webmail API
After=network.target postgresql.service redis-server.service dovecot.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/maquita-webmail/backend
Environment=PATH=/opt/maquita-webmail/backend/venv/bin:/usr/local/bin:/usr/bin
EnvironmentFile=/opt/maquita-webmail/backend/.env
ExecStart=/opt/maquita-webmail/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4 --loop uvloop
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

### 13. Configurar Nginx

Crear `/etc/nginx/sites-available/mail.tudominio.com`:
```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=compose:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;

# Redirect HTTP -> HTTPS
server {
    listen 80;
    server_name mail.tudominio.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl http2;
    server_name mail.tudominio.com;

    ssl_certificate /etc/letsencrypt/live/mail.tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mail.tudominio.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Cabeceras de seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Block robots
    location = /robots.txt {
        return 200 "User-agent: *\nDisallow: /\n";
    }

    # === Webmail SPA ===
    location = /webmail {
        return 301 /webmail/;
    }

    location /webmail/ {
        root /opt/maquita-webmail/www;

        # Service Worker sin cache
        location = /webmail/sw.js {
            root /opt/maquita-webmail/www;
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Service-Worker-Allowed "/webmail/";
        }

        # Assets con hash: cache largo
        location ~* /webmail/assets/ {
            root /opt/maquita-webmail/www;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # SPA fallback
        try_files $uri $uri/ /webmail/index.html;
    }

    # === API Backend ===
    location = /api/auth/login {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        limit_req zone=api burst=80 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 25M;
        proxy_read_timeout 120s;
    }

    # === WebSocket ===
    location /api/ws {
        proxy_pass http://127.0.0.1:8000/api/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }

    # === CalDAV/CardDAV (Radicale) ===
    location /.well-known/caldav { return 301 /dav/; }
    location /.well-known/carddav { return 301 /dav/; }

    location /dav/ {
        proxy_pass http://127.0.0.1:5232/;
        proxy_set_header X-Remote-User $remote_user;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        client_max_body_size 50M;
    }

    # Raíz -> Webmail
    location / {
        return 301 /webmail;
    }
}
```

```bash
ln -sf /etc/nginx/sites-available/mail.tudominio.com /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 14. Crear primer buzón

Usa PostfixAdmin o directamente en la base de datos:

```bash
# Instalar PostfixAdmin (opcional, recomendado)
apt install -y postfixadmin

# O crear buzón manualmente:
sudo -u postgres psql -d maildb << 'SQL'
INSERT INTO domain (domain, description, transport, active)
VALUES ('tudominio.com', 'Dominio principal', 'virtual', 1);

-- Generar password: doveadm pw -s BLF-CRYPT -p TuPassword123
INSERT INTO mailbox (username, password, name, maildir, domain, active)
VALUES (
  'usuario@tudominio.com',
  '$2y$05$...hash_generado...',
  'Nombre Usuario',
  'tudominio.com/usuario/Maildir/',
  'tudominio.com',
  1
);

INSERT INTO alias (address, goto, domain, active)
VALUES ('usuario@tudominio.com', 'usuario@tudominio.com', 'tudominio.com', 1);
SQL
```

### 15. Verificar instalación

```bash
# Verificar servicios
systemctl status maquita-webmail postfix dovecot postgresql redis-server nginx radicale

# Verificar puertos
ss -tlnp | grep -E '25|143|443|587|993|5232|8000'

# Probar API
curl -s http://127.0.0.1:8000/docs | head -5

# Probar envío de correo
echo "Test" | mail -s "Prueba" usuario@tudominio.com
```

Abre en tu navegador: `https://mail.tudominio.com/webmail/`

---

## Estructura del Proyecto

```
maquita-webmail/
├── backend/
│   ├── app/
│   │   ├── main.py              # Punto de entrada FastAPI
│   │   ├── admin/               # Panel de administración
│   │   ├── ai/                  # Asistente IA
│   │   ├── auth/                # Autenticación JWT + TOTP
│   │   ├── calendar/            # Calendario (Radicale)
│   │   ├── contacts/            # Contactos (CardDAV)
│   │   ├── core/                # Config, DB, Redis, sesión
│   │   ├── gal/                 # Directorio global
│   │   ├── identities/          # Identidades de correo
│   │   ├── import_export/       # Importar/exportar correos
│   │   ├── mail/                # Correo (IMAP/SMTP)
│   │   │   ├── clients/         # Clientes IMAP y SMTP
│   │   │   ├── routers/         # Endpoints REST
│   │   │   ├── schemas/         # Modelos Pydantic
│   │   │   └── services/        # Lógica de negocio
│   │   ├── meetings/            # Reuniones
│   │   ├── rooms/               # Salas de reunión
│   │   ├── security/            # Seguridad avanzada
│   │   ├── settings/            # Preferencias de usuario
│   │   ├── sieve/               # Reglas de correo
│   │   ├── smime/               # Certificados S/MIME
│   │   ├── sso/                 # Single Sign-On
│   │   ├── tasks/               # Tareas (Kanban)
│   │   ├── webhooks/            # Webhooks
│   │   └── websocket/           # Notificaciones en tiempo real
│   ├── migrations/              # Scripts de migración SQL
│   ├── requirements.txt
│   └── .env                     # Variables de entorno (no en git)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Router principal
│   │   ├── components/
│   │   │   ├── admin/           # Panel de administración
│   │   │   ├── auth/            # Login
│   │   │   ├── calendar/        # Calendario
│   │   │   ├── common/          # Componentes compartidos
│   │   │   ├── compose/         # Composición (TipTap)
│   │   │   ├── contacts/        # Contactos
│   │   │   ├── layout/          # NavRail, Topbar, Sidebar
│   │   │   ├── mail/            # Correo (MailView, MessageList, etc)
│   │   │   ├── settings/        # Configuración
│   │   │   └── tasks/           # Tareas
│   │   ├── hooks/               # Custom hooks
│   │   ├── store/               # Zustand (estado global)
│   │   └── types/               # Tipos TypeScript
│   ├── public/
│   │   ├── sw.js                # Service Worker
│   │   └── manifest.json        # PWA manifest
│   ├── package.json
│   └── vite.config.ts
│
├── deploy/                      # Scripts de despliegue
├── .gitignore
└── README.md
```

---

## Base de Datos

El sistema usa **77 tablas** en PostgreSQL, organizadas por módulo:

| Módulo | Tablas principales |
|--------|-------------------|
| **Correo** | `mailbox`, `domain`, `alias`, `user_labels`, `message_labels`, `snoozed_emails`, `scheduled_emails` |
| **Calendario** | `calendars`, `events`, `event_invitations`, `calendar_shares`, `calendar_event_attachments` |
| **Contactos** | `user_contacts`, `contact_categories`, `contact_lists`, `contact_relationships`, `contact_reminders` |
| **Tareas** | `task_boards`, `task_lists`, `task_cards`, `task_labels`, `task_activity`, `task_board_members` |
| **Admin** | `admin_users`, `admin_sessions`, `admin_audit` |
| **Seguridad** | `user_totp`, `smime_certificates`, `api_keys`, `sso_config` |
| **Otros** | `user_preferences`, `user_signatures`, `email_templates`, `webhooks`, `retention_policies` |

Las tablas se crean automáticamente al iniciar el backend por primera vez.

---

## Puertos Utilizados

| Puerto | Servicio | Acceso |
|--------|----------|--------|
| 25 | Postfix SMTP | Público |
| 80 | Nginx HTTP (redirect) | Público |
| 143 | Dovecot IMAP | Local* |
| 443 | Nginx HTTPS | Público |
| 587 | Postfix Submission | Público |
| 993 | Dovecot IMAPS | Público |
| 4190 | Sieve (ManageSieve) | Local |
| 5232 | Radicale CalDAV | Local |
| 5432 | PostgreSQL | Local |
| 6379 | Redis | Local |
| 8000 | Fundación Maquita API | Local |

*Local = solo accesible desde 127.0.0.1, protegido por Nginx

---

## Comandos Útiles

```bash
# Reiniciar webmail
systemctl restart maquita-webmail

# Ver logs
journalctl -u maquita-webmail -f

# Recompilar frontend después de cambios
cd /opt/maquita-webmail/frontend
npx vite build
cp /var/www/mail/sw.js /opt/maquita-webmail/frontend/dist/sw.js

# Verificar correo
doveadm mailbox list -u usuario@tudominio.com

# Generar contraseña para nuevo buzón
doveadm pw -s BLF-CRYPT

# Backup de base de datos
pg_dump -U mailserver maildb > backup_$(date +%Y%m%d).sql

# Actualizar desde GitHub
cd /opt/maquita-webmail
git pull origin main
cd frontend && npm install && npx vite build
systemctl restart maquita-webmail
```

---

## Solución de Problemas

| Problema | Solución |
|----------|----------|
| No carga la interfaz | `systemctl status maquita-webmail` — verificar que el backend esté activo |
| Error 502 Bad Gateway | El backend no responde: `curl http://127.0.0.1:8000/docs` |
| No llegan correos | Verificar Postfix: `journalctl -u postfix -f` y registros MX en DNS |
| No se puede enviar | Verificar Dovecot SASL y puerto 587: `telnet localhost 587` |
| Cache vieja del navegador | Ctrl+Shift+R o borrar Service Worker en DevTools > Application |
| Error de certificado | Renovar: `certbot renew` |
| Calendario no funciona | Verificar Radicale: `systemctl status radicale` |

---

## Contribuir

1. Fork del repositorio
2. Crear rama: `git checkout -b mi-mejora`
3. Hacer cambios y commit: `git commit -m "Descripción del cambio"`
4. Push: `git push origin mi-mejora`
5. Crear Pull Request

---

## Licencia

Este proyecto es **software libre** bajo la licencia MIT. Úsalo, modifícalo y compártelo libremente.

Desarrollado con amor por la inteligencia colectiva.

---

## Créditos

- **Fundación Maquita** — Comercializadora asociativa sin fines de lucro, Ecuador
- **Wilson Gabriel** — Desarrollo y arquitectura
- **IA AI** — Asistente de desarrollo

*"Tecnología al servicio de todos, no solo de quienes pueden pagarla."*
