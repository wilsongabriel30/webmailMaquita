# Guía de instalación nativa (producción)

Esta guía instala Maquita Webmail de forma **nativa** (sin Docker) en un único
servidor Debian, junto a una plataforma de correo real Postfix + Dovecot.
Reproduce el despliegue de producción de referencia.

> El correo y el webmail corren **nativos, directo sobre el sistema operativo**.
> Docker se usa únicamente para Z-Push (ActiveSync) — ver `deploy/z-push/`.
> Esta guía es la vía recomendada y soportada para producción.

## Stack de referencia (probado)

| Componente  | Versión        | Rol                                    |
|-------------|----------------|----------------------------------------|
| Debian      | 12 / 13        | Sistema operativo base                 |
| PostgreSQL  | 17             | Cuentas de correo + datos de la app    |
| Dovecot     | 2.4            | IMAP/POP3, ManageSieve, usuario maestro|
| Postfix     | 3.10           | MTA SMTP, entrega LMTP a Dovecot       |
| Redis       | 7 / 8          | Sesiones y cachés                      |
| Python      | 3.12+          | Backend (FastAPI / uvicorn)            |
| Node        | 20             | Compilación del frontend (Vite)        |
| nginx       | 1.24+          | Proxy inverso con TLS                  |
| SOGo        | 5 (opcional)   | CalDAV/CardDAV (calendario y contactos)|
| Ollama      | (opcional)     | Asistente de IA local                  |

## Forma más fácil: instalador automático

```bash
git clone https://github.com/wilsongabriel30/webmailMaquita.git /opt/maquita-webmail
cd /opt/maquita-webmail
sudo bash deploy/webmail/instalar.sh
```

El instalador deja el sistema arrancado e imprime las credenciales generadas.
Si prefieres entender o adaptar cada componente, sigue los pasos manuales de
abajo.

## Arquitectura

```
            Internet :443 (TLS, nginx)
                       |
   /            -> frontend (estático, /var/www/webmail)
   /api/        -> backend  127.0.0.1:8000  (uvicorn, systemd)
   /SOGo/       -> SOGo      127.0.0.1:20000 (opcional)
                       |
   backend --IMAP/Sieve--> Dovecot 143/4190  (login con usuario maestro)
   backend --SMTP-------->  Postfix 587       (auth por usuario)
   backend --SQL-------->   PostgreSQL :5432
   backend --caché----->    Redis :6379
   Postfix --LMTP------->    Dovecot (entrega)
```

El backend nunca almacena las contraseñas de los buzones: lee cualquier buzón a
través del **usuario maestro de Dovecot** (`MASTER_PASSWORD`) y envía a través de
la sumisión (submission) de Postfix usando las credenciales propias del usuario.

---

## 1. Paquetes del sistema

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

## 2. PostgreSQL — cuentas de correo + esquema de la app

```bash
sudo -u postgres psql <<SQL
CREATE USER mailserver WITH PASSWORD 'CAMBIAME_DB';
CREATE DATABASE maildb OWNER mailserver;
SQL
```

Esquema mínimo de buzones virtuales que usan Postfix/Dovecot (amplíalo según necesites):

```sql
\c maildb
CREATE TABLE domain  (domain text PRIMARY KEY, active boolean DEFAULT true);
CREATE TABLE mailbox (
  username text PRIMARY KEY,          -- dirección completa usuario@dominio
  password text NOT NULL,             -- hash {SSHA512} (doveadm pw)
  domain   text REFERENCES domain(domain),
  maildir  text,                      -- ej. usuario@dominio/
  quota_bytes bigint DEFAULT 0,
  active   boolean DEFAULT true
);
CREATE TABLE alias   (address text PRIMARY KEY, goto text, active boolean DEFAULT true);
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mailserver;
```

Luego aplica las migraciones de la app (crea las tablas de webmail/cumplimiento en la misma BD):

```bash
cd /opt/maquita-webmail
for f in migrations/*.sql; do sudo -u postgres psql -d maildb -f "$f"; done
```

Crea un dominio + un buzón de prueba:

```bash
sudo -u postgres psql -d maildb -c \
 "INSERT INTO domain(domain) VALUES ('example.com');"
HASH=$(doveadm pw -s SSHA512 -p 'ClaveUsuario123')
sudo -u postgres psql -d maildb -c \
 "INSERT INTO mailbox(username,password,domain,maildir,local_part) \
  VALUES ('user@example.com','$HASH','example.com','example.com/user/','user');"
```

Marca ese buzón como **administrador** del panel (gestión de dominios, buzones,
auditoría, eDiscovery, colas, anti-spam, etc.):

```bash
sudo -u postgres psql -d maildb -c \
 "INSERT INTO admin(username,superadmin,active) VALUES ('user@example.com',true,true) \
  ON CONFLICT (username) DO UPDATE SET superadmin=true, active=true;"
```

## 3. Dovecot — usuarios virtuales + usuario maestro

`/etc/dovecot/dovecot-sql.conf.ext`:
```
driver = pgsql
connect = host=127.0.0.1 dbname=maildb user=mailserver password=CAMBIAME_DB
password_query = SELECT username AS user, password FROM mailbox \
  WHERE username = '%u' AND active = true
user_query     = SELECT maildir AS home FROM mailbox WHERE username='%u'
iterate_query  = SELECT username AS user FROM mailbox WHERE active = true
```

Ubicación del correo y usuario vmail:
```
mail_home = /var/vmail/%{user|domain}/%{user|username}
mail_location = maildir:~/Maildir
```
```bash
sudo groupadd -g 5000 vmail
sudo useradd  -u 5000 -g vmail -d /var/vmail -m -s /usr/sbin/nologin vmail
```

**Usuario maestro** (permite al backend abrir cualquier buzón). En un passwd-file
`/etc/dovecot/master-users`:
```
webmaster@*:{SSHA512}<hash de: doveadm pw -s SSHA512>
```
Y en la configuración `auth`:
```
auth_master_user_separator = *
passdb { driver = passwd-file ; args = /etc/dovecot/master-users ; master = yes }
```
La clave en texto plano que aquí cifras es la que va en el `.env` del backend como
`MASTER_PASSWORD`. Habilita IMAP (143/993), LMTP y ManageSieve (4190).

```bash
sudo systemctl restart dovecot
```

## 4. Postfix — SMTP + entrega LMTP

`/etc/postfix/main.cf` (líneas clave):
```
virtual_mailbox_domains = pgsql:/etc/postfix/pgsql/domains.cf
virtual_mailbox_maps    = pgsql:/etc/postfix/pgsql/mailbox.cf
virtual_alias_maps      = pgsql:/etc/postfix/pgsql/alias.cf
virtual_transport       = lmtp:unix:private/dovecot-lmtp
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
```
Habilita el servicio `submission` (587) en `master.cf` con SASL vía Dovecot.
Cada mapa `pgsql/*.cf` es un archivo pequeño (`hosts/user/password/dbname` + una
`query`), por ejemplo `domains.cf`:
```
query = SELECT 1 FROM domain WHERE domain='%s' AND active=true
```
```bash
sudo systemctl restart postfix
```

## 5. Backend (FastAPI)

```bash
cd /opt/maquita-webmail/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp ../.env.example .env      # luego edita .env (ver la tabla de variables del README)
```
Define en `.env`: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ADMIN_JWT_SECRET`,
`MASTER_PASSWORD` (la clave del usuario maestro de Dovecot del paso 3),
`IMAP_HOST=127.0.0.1`, `SMTP_HOST=127.0.0.1`, `MAIL_DOMAIN`, `COOKIE_DOMAIN`,
`CORS_ORIGINS`.

Unidad systemd `/etc/systemd/system/maquita-webmail.service`:
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

## 6. Frontend (compilar + nginx)

```bash
cd /opt/maquita-webmail/frontend
npm ci && npm run build
sudo mkdir -p /var/www/webmail && sudo cp -r dist/* /var/www/webmail/
```

Sitio nginx `/etc/nginx/sites-available/webmail` (TLS con certbot):
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
    # opcional: location /SOGo/ { proxy_pass http://127.0.0.1:20000; }
}
server { listen 80; server_name mail.example.com; return 301 https://$host$request_uri; }
```
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo ln -s /etc/nginx/sites-available/webmail /etc/nginx/sites-enabled/
sudo certbot --nginx -d mail.example.com
sudo nginx -t && sudo systemctl reload nginx
```

## 7. Componentes opcionales

- **Calendario/Contactos:** instala `sogo`, apunta `SOGO_DAV_URL` a él y haz proxy de `/SOGo/`.
- **Asistente de IA:** instala Ollama, `ollama pull qwen2.5:7b`, define `OLLAMA_URL`.
  Deja `IA_API_KEY` en blanco salvo que pongas un gateway de autenticación delante de Ollama.
- **Filtrado de spam:** agrega rspamd e intégralo en Postfix como milter.
- **Sincronización con móviles (ActiveSync):** ver `deploy/z-push/` (único componente en Docker).
- **Nube de archivos + ofimática en línea (Nextcloud + OnlyOffice) — sugerido:**
  Para almacenamiento en la nube (archivos, adjuntos grandes, compartir) puedes
  instalar **[Nextcloud](https://nextcloud.com)**, y dentro de él
  **[OnlyOffice](https://www.onlyoffice.com)** para editar documentos de oficina
  (Word/Excel/PowerPoint) en línea desde el navegador. El webmail ya trae la
  integración (variables `NC_BASE_URL`, `NC_ADMIN_USER`, `NC_ADMIN_PASS`,
  `NC_PUBLIC_URL`, `ONLYOFFICE_URL`, `ONLYOFFICE_SECRET`,
  `ONLYOFFICE_DOWNLOAD_SECRET` en `.env`).

  > Es **opcional** y aún no documentamos la configuración paso a paso (lo
  > añadiremos cuando lo tengamos afinado). Por ahora queda como recomendación:
  > Nextcloud para la nube y OnlyOffice (instalado como app/conector dentro de
  > Nextcloud) para la ofimática en línea.

## 8. Verificar

```bash
systemctl is-active postgresql dovecot postfix redis-server nginx maquita-webmail
curl -s http://127.0.0.1:8000/api/health
# inicia sesión en https://mail.example.com con user@example.com / ClaveUsuario123
```

## Resolución de problemas

| Síntoma                                | Revisa |
|----------------------------------------|--------|
| Login OK pero buzón vacío / error IMAP | que `MASTER_PASSWORD` coincida con el hash del passwd-file maestro de Dovecot |
| No se puede enviar (535)               | `submission` (587) activo; el usuario existe en `mailbox`; SASL de Postfix vía Dovecot |
| `/api/health` falla                    | `.env` del backend (DATABASE_URL/REDIS_URL); `journalctl -u maquita-webmail` |
| 502 desde nginx                        | que el backend escuche en 127.0.0.1:8000 |

Ver también `docs/INSTALL.md`, `docs/DEPLOYMENT.md`, `docs/TROUBLESHOOTING.md`.
