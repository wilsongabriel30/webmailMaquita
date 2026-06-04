# Guía de Instalación Completa

Guía paso a paso para instalar Maquita Webmail desde cero. Escrita para personas con poca experiencia técnica.

> **Tiempo estimado:** 2-4 horas (primera vez) | 30-60 minutos (con experiencia)

---

## Antes de Empezar

### Qué se va a construir

Este sistema de correo tiene muchas piezas que trabajan juntas, como un equipo:

```
Internet
   |
   v
[Postfix] -----> Recibe y envía correos (como el cartero)
   |
   v
[Rspamd] ------> Analiza spam y virus (como el guardia de seguridad)
   |
   v
[Filtro Python] -> Clasifica con las reglas definidas (filtro personalizado)
   |
   v
[Dovecot] ------> Guarda los correos y permite leerlos (como el archivo/bodega)
   |
   v
[Webmail API] --> La aplicación web que conecta todo (FastAPI/Python)
   |
   v
[Frontend] -----> Lo que se ve en el navegador (React/TypeScript)
   |
   v
[Nginx] --------> Sirve la página web con HTTPS (como la puerta de entrada)
```

**Otros servicios de apoyo:**
- **PostgreSQL**: base de datos donde se guardan usuarios, contactos, tareas, calendario, configuración
- **Redis**: caché rápida para sesiones y datos temporales (hace todo más rápido)
- **Radicale**: servidor de calendario y contactos (CalDAV/CardDAV)
- **ClamAV**: antivirus que escanea adjuntos
- **Certbot**: genera certificados SSL gratuitos (el candado en el navegador)

### Requisitos previos

1. **Un servidor** con acceso root (puede ser):
   - VPS en la nube (DigitalOcean, Hetzner, OVH, AWS, etc.) — desde $10/mes
   - Servidor físico en la oficina
   - Máquina virtual en Proxmox, VMware, VirtualBox, etc.
   - Requisitos mínimos: 2+ cores, 4+ GB RAM, 20+ GB disco, Debian 12+ o Ubuntu 22.04+

2. **Un dominio** (ej: tudominio.com)

3. **IP pública fija**

4. **Acceso al panel DNS** del dominio

5. **Puerto 25 abierto** — algunos proveedores de nube bloquean el puerto 25 por defecto. Solicite que lo abran.

### Registros DNS necesarios

Configure estos registros en el panel de su proveedor de dominio **ANTES** de empezar:

| Tipo | Nombre | Valor | Para qué sirve |
|------|--------|-------|----------------|
| **A** | `mail.tudominio.com` | `IP_DE_TU_SERVIDOR` | Apuntar el subdominio al servidor |
| **MX** | `tudominio.com` | `mail.tudominio.com` (prioridad 10) | Dónde recibir correos |
| **TXT** | `tudominio.com` | `v=spf1 ip4:IP_SERVIDOR mx -all` | Autorizar la IP para enviar |
| **TXT** | `_dmarc.tudominio.com` | `v=DMARC1; p=reject; rua=mailto:postmaster@tudominio.com` | Anti-suplantación |
| **TXT** | `mail._domainkey.tudominio.com` | *(se genera en el paso 7)* | Firma digital DKIM |
| **CNAME** | `autoconfig.tudominio.com` | `mail.tudominio.com` | Auto-configuración Thunderbird |
| **CNAME** | `autodiscover.tudominio.com` | `mail.tudominio.com` | Auto-configuración Outlook |

> **¿Dónde se configura esto?** En el panel web del proveedor de dominio (Namecheap, GoDaddy, Cloudflare, NIC.ec, etc.). Busque la sección "DNS" o "Zona DNS".

---

## Paso 1: Preparar el servidor

```bash
# Actualizar lista de paquetes
apt update && apt upgrade -y

# Instalar herramientas necesarias
apt install -y curl wget gnupg2 software-properties-common \
  apt-transport-https ca-certificates lsb-release \
  git build-essential python3 python3-pip python3-venv \
  nodejs npm ufw

# Configurar firewall
ufw allow ssh
ufw allow 25/tcp    # SMTP
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 587/tcp   # Submission
ufw allow 993/tcp   # IMAPS
ufw enable
```

## Paso 2: Hostname

```bash
hostnamectl set-hostname mail.tudominio.com
echo "IP_SERVIDOR mail.tudominio.com" >> /etc/hosts
hostname -f  # Verificar: debe mostrar mail.tudominio.com
```

## Paso 3: PostgreSQL

```bash
apt install -y postgresql postgresql-contrib

sudo -u postgres psql << SQL
CREATE DATABASE maildb;
CREATE USER mailserver WITH ENCRYPTED PASSWORD 'TU_PASSWORD_SEGURA';
GRANT ALL PRIVILEGES ON DATABASE maildb TO mailserver;
\q
SQL

# Verificar conexión:
psql -U mailserver -d maildb -h 127.0.0.1
# Debe conectar sin errores y mostrar "maildb=>"
```

## Paso 4: Redis

```bash
apt install -y redis-server

# Establecer contraseña
sed -i "s/# requirepass .*/requirepass TU_REDIS_PASSWORD/" /etc/redis/redis.conf
systemctl restart redis

# Verificar
redis-cli -a TU_REDIS_PASSWORD ping
# Debe responder: PONG
```

## Paso 5: Postfix (servidor SMTP)

```bash
apt install -y postfix postfix-pgsql

# Cuando pregunte el tipo, elegir: "Internet Site"
# Cuando pregunte hostname: mail.tudominio.com
```

Edite `/etc/postfix/main.cf`:

```bash
# Hacer backup primero
cp /etc/postfix/main.cf /etc/postfix/main.cf.bak

# Editar con nano o vim
nano /etc/postfix/main.cf
```

Contenido principal (ver repositorio para configuración completa con comentarios):

```ini
# === IDENTIFICACIÓN ===
myhostname = mail.tudominio.com
mydomain = tudominio.com
myorigin = $mydomain

# === BUZONES VIRTUALES ===
virtual_mailbox_domains = pgsql:/etc/postfix/pgsql-domains.cf
virtual_mailbox_maps = pgsql:/etc/postfix/pgsql-mailbox.cf
virtual_alias_maps = pgsql:/etc/postfix/pgsql-aliases.cf

# === ENTREGA ===
virtual_transport = lmtp:unix:private/dovecot-lmtp

# === SEGURIDAD TLS ===
smtpd_tls_cert_file = /etc/letsencrypt/live/mail.tudominio.com/fullchain.pem
smtpd_tls_key_file = /etc/letsencrypt/live/mail.tudominio.com/privkey.pem
smtpd_use_tls = yes

# === LÍMITES ===
message_size_limit = 26214400

# === ANTISPAM ===
milter_default_action = accept
smtpd_milters = inet:localhost:11332
```

Verificar:
```bash
postfix check
# No debe mostrar errores
```

## Paso 6: Dovecot (servidor IMAP)

```bash
apt install -y dovecot-core dovecot-imapd dovecot-lmtpd \
  dovecot-pgsql dovecot-sieve dovecot-managesieved \
  dovecot-fts dovecot-fts-xapian

# Crear usuario vmail
groupadd -g 5000 vmail
useradd -g vmail -u 5000 -d /var/vmail -m vmail
mkdir -p /var/vmail && chown -R vmail:vmail /var/vmail
```

Complementos importantes a habilitar en Dovecot:
- `quota` — límites de espacio por usuario
- `fts` + `fts_xapian` — búsqueda rápida dentro de correos
- `mail_crypt` — cifrado de correos en disco
- `mail_compress` — comprimir correos (~60% de ahorro)
- `lazy_expunge` — borrado rápido

```bash
# Reiniciar
systemctl restart postfix dovecot

# Verificar que ambos estén activos
systemctl status postfix dovecot
```

## Paso 7: Rspamd + ClamAV + DKIM

```bash
# Instalar
apt install -y rspamd clamav clamav-daemon
freshclam  # Actualizar base de virus (toma 1-2 minutos)

# Generar clave DKIM
mkdir -p /var/lib/rspamd/dkim
rspamadm dkim_keygen -d tudominio.com -s mail \
  -k /var/lib/rspamd/dkim/mail.tudominio.com.key

# IMPORTANTE: el comando muestra un registro DNS TXT
# Debe agregarlo en el panel DNS
```

Configuración anti-spam (nunca rechazar, solo marcar):
```
# /etc/rspamd/local.d/actions.conf
reject = null;            # Nunca rechazar
add_header = 6;           # Agregar encabezado si score >= 6
greylist = null;          # No usar greylisting
```

```bash
# Verificar configuración
rspamadm configtest

# Reiniciar
systemctl restart rspamd clamav-daemon
```

## Paso 8: Sieve (reglas globales)

```bash
mkdir -p /var/vmail/sieve-global

cat > /var/vmail/sieve-global/default.sieve << 'EOF'
require ["fileinto", "mailbox"];

# Si Rspamd lo marcó como spam
if header :contains "X-Spam" "Yes" {
    fileinto :create "Junk";
    stop;
}

# Si el filtro Python lo marcó como spam
if header :is "X-Maquita-Spam" "YES" {
    fileinto :create "Junk";
    stop;
}
EOF

sievec /var/vmail/sieve-global/default.sieve
chown -R vmail:vmail /var/vmail/sieve-global
```

## Paso 9: Filtro anti-spam Python

```bash
mkdir -p /opt/maquita-mail-filter /etc/maquita-mail

# Copiar archivos del repositorio
cp scripts/spam-filter-service.py /opt/maquita-mail-filter/
cp scripts/maquita-mail-config/* /etc/maquita-mail/
chown -R vmail:vmail /etc/maquita-mail

# Crear log
touch /var/log/maquita-spam-filter.log
chown vmail:vmail /var/log/maquita-spam-filter.log

# Agregar a /etc/postfix/master.cf:
# maquita-filter unix - n n - 10 pipe
#   flags=Rq user=vmail argv=/usr/bin/python3
#   /opt/maquita-mail-filter/spam-filter-service.py
#   -f ${sender} -- ${recipient}

# Agregar a /etc/postfix/main.cf:
# content_filter = maquita-filter:

# Puerto de reinyección en /etc/postfix/master.cf:
# 127.0.0.1:10025 inet n - n - 10 smtpd
#   -o content_filter=
#   -o receive_override_options=no_unknown_recipient_checks

# Reiniciar Postfix
systemctl restart postfix
```

## Paso 10: Radicale (calendario y contactos)

```bash
apt install -y radicale
# Configurar para escuchar en localhost:5232
systemctl enable --now radicale

# Verificar
curl -s http://localhost:5232
```

## Paso 11: Certificado SSL (Let's Encrypt)

```bash
apt install -y certbot

# Obtener certificado (el dominio debe apuntar a este servidor)
certbot certonly --standalone -d mail.tudominio.com

# Si Nginx ya está corriendo:
# certbot certonly --nginx -d mail.tudominio.com

# Verificar renovación automática
certbot renew --dry-run
```

## Paso 12: Instalar el webmail

```bash
cd /opt
git clone https://github.com/wilsongabriel30/webmailMaquita.git maquita-webmail
cd maquita-webmail

# Backend — crear entorno virtual Python
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# Frontend — compilar interfaz
cd frontend
npm install    # Toma 1-3 minutos
npm run build  # Genera archivos en dist/
cd ..

# Desplegar frontend
mkdir -p /opt/maquita-webmail/www/webmail
cp -r frontend/dist/* /opt/maquita-webmail/www/webmail/
```

## Paso 13: Configurar variables de entorno

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Variables principales:
```ini
# Base de datos (la contraseña del paso 3)
DATABASE_URL=postgresql://mailserver:TU_PASSWORD@localhost:5432/maildb

# Redis (la contraseña del paso 4)
REDIS_PASSWORD=TU_REDIS_PASSWORD

# JWT (generar con: python3 -c "import secrets; print(secrets.token_hex(32))")
JWT_SECRET=CLAVE_ALEATORIA_AQUI

# Servidor de correo
IMAP_HOST=localhost
SMTP_HOST=localhost
MAIL_DOMAIN=tudominio.com

# Admin
ADMIN_PASSWORD=tu_password_admin
ADMIN_SECRET=OTRA_CLAVE_ALEATORIA

# IA local (opcional, ver docs/AI.md)
# OLLAMA_URL=http://ip-servidor-ia:8000
# IA_API_KEY=tu-clave-api
```

## Paso 14: Servicio systemd

```bash
cat > /etc/systemd/system/maquita-webmail.service << 'EOF'
[Unit]
Description=Maquita Webmail
After=network.target postgresql.service redis-server.service dovecot.service

[Service]
Type=simple
WorkingDirectory=/opt/maquita-webmail/backend
ExecStart=/opt/maquita-webmail/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5
User=www-data

[Install]
WantedBy=multi-user.target
EOF

chown -R www-data:www-data /opt/maquita-webmail
systemctl daemon-reload
systemctl enable --now maquita-webmail

# Verificar
sleep 5
systemctl status maquita-webmail
curl -s http://localhost:8000/api/health
```

## Paso 15: Nginx

Configure el virtual host con SSL, proxy al backend, rate limiting y encabezados de seguridad. Ejemplo disponible en el repositorio.

```bash
# Crear configuración
nano /etc/nginx/sites-available/maquita-webmail

# Habilitar
ln -s /etc/nginx/sites-available/maquita-webmail /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Verificar y recargar
nginx -t
systemctl reload nginx
```

## Paso 16: Crear primer buzón de correo

```bash
# Generar contraseña cifrada
doveadm pw -s BLF-CRYPT
# Ingrese la contraseña y copie el hash (empieza con $2y$05$...)

# Insertar en base de datos
sudo -u postgres psql -d maildb << SQL
INSERT INTO domain (domain, active) VALUES ('tudominio.com', true);
INSERT INTO mailbox (username, password, name, maildir, domain, active, quota)
VALUES ('admin@tudominio.com', '\$2y\$05\$...HASH...', 'Administrador',
        'tudominio.com/admin/Maildir/', 'tudominio.com', true, 5368709120);
INSERT INTO alias (address, goto, domain, active)
VALUES ('admin@tudominio.com', 'admin@tudominio.com', 'tudominio.com', true);
SQL
```

## Paso 17: Verificación final

```bash
# 1. Verificar que todos los servicios estén activos
systemctl status postfix dovecot rspamd clamav-daemon \
  redis-server postgresql nginx radicale maquita-webmail

# 2. Verificar puertos en escucha
ss -tlnp | grep -E "25|80|143|443|587|993|5232|8000"

# 3. Verificar que la API responde
curl -s http://localhost:8000/api/health

# 4. Abrir en navegador: https://mail.tudominio.com/webmail/

# 5. Verificar registros DNS (propagación)
dig +short MX tudominio.com
dig +short A mail.tudominio.com
dig +short TXT tudominio.com
```

---

## Siguientes pasos

- [Configurar IA local](AI.md) — Asistente de correo con IA local (opcional)
- [Seguridad](SECURITY.md) — Medidas de endurecimiento implementadas
- [Arquitectura](ARCHITECTURE.md) — Entender la estructura del proyecto
- [Solucionar problemas](TROUBLESHOOTING.md) — Errores comunes y soluciones
