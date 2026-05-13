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

### Inteligencia Artificial (opcional)
- Smart Reply: genera 3 respuestas contextualizadas para cada correo
- Smart Compose: autocompletado inteligente al redactar
- Resumenes automaticos de hilos de correo
- Sugerencias de asunto basadas en el contenido
- Requiere servidor con GPU y Ollama (LLM local, sin dependencia de servicios externos)
- Soporte multi-GPU con failover automatico
- Compatible con cualquier modelo de Ollama (Llama, Gemma, Qwen, Mistral, etc.)

### Cuarentena Anti-Spam (Admin)
- Vista de todos los correos en Junk de todos los usuarios
- Aprobar correos (mover a Inbox), confirmar spam o eliminar
- Seleccion masiva con acciones en lote
- Log del filtro en tiempo real (veredictos, scores, razones)
- Editor de palabras clave con pesos (sin reiniciar servicios)
- Editor de whitelist de remitentes confiables

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
| **IA (opcional)** | Ollama + FastAPI Gateway | Ollama 0.6+, cualquier modelo |


---

## Antes de Empezar

### Que vas a construir

Este sistema de correo tiene muchas piezas que trabajan juntas, como un equipo:

```
Internet
   |
   v
[Postfix] -----> Recibe y envia correos (como el cartero)
   |
   v
[Rspamd] ------> Analiza spam y virus (como el guardia de seguridad)
   |
   v
[Filtro Python] -> Clasifica con tus reglas (tu filtro personalizado)
   |
   v
[Dovecot] ------> Guarda los correos y permite leerlos (como el archivo/bodega)
   |
   v
[Webmail API] --> La aplicacion web que conecta todo (FastAPI/Python)
   |
   v
[Frontend] -----> Lo que ves en el navegador (React/TypeScript)
   |
   v
[Nginx] --------> Sirve la pagina web con HTTPS (como la puerta de entrada)
```

**Otros servicios de apoyo:**
- **PostgreSQL**: base de datos donde se guardan usuarios, contactos, tareas, calendario, configuracion
- **Redis**: cache rapida para sesiones y datos temporales (hace todo mas rapido)
- **Radicale**: servidor de calendario y contactos (CalDAV/CardDAV)
- **ClamAV**: antivirus que escanea adjuntos
- **Certbot**: genera certificados SSL gratuitos (el candadito verde en el navegador)

### Que necesitas antes de empezar

1. **Un servidor** con acceso root (puede ser):
   - VPS en la nube (DigitalOcean, Hetzner, OVH, AWS, etc.) — desde $10/mes
   - Servidor fisico en tu oficina
   - Maquina virtual en Proxmox, VMware, VirtualBox, etc.
   - Requisitos: 2+ cores, 4+ GB RAM, 20+ GB disco, Debian 12+ o Ubuntu 22.04+

2. **Un dominio** (ej: `tudominio.com`) — puedes comprar uno en Namecheap, GoDaddy, NIC.ec, etc.

3. **IP publica fija** — tu proveedor de internet o hosting debe darte una

4. **Acceso al panel DNS** de tu dominio — para configurar registros MX, SPF, DKIM, etc.

5. **Puerto 25 abierto** — algunos proveedores de nube (AWS, Azure) bloquean el puerto 25 por defecto. Debes solicitar que lo abran. Sin esto NO puedes recibir correos.


6. **Registros DNS** — configura estos registros en el panel de tu proveedor de dominio ANTES de empezar:

| Tipo | Nombre | Valor | Para que sirve |
|------|--------|-------|----------------|
| **A** | `mail.tudominio.com` | `IP_DE_TU_SERVIDOR` | Apuntar el subdominio al servidor |
| **MX** | `tudominio.com` | `mail.tudominio.com` (prioridad 10) | Decirle al mundo donde recibir correos |
| **TXT** | `tudominio.com` | `v=spf1 ip4:IP_SERVIDOR mx -all` | Autorizar tu IP para enviar correos |
| **TXT** | `_dmarc.tudominio.com` | `v=DMARC1; p=reject; rua=mailto:postmaster@tudominio.com` | Politica anti-suplantacion |
| **TXT** | `mail._domainkey.tudominio.com` | *(se genera en paso 7)* | Firma digital de correos (DKIM) |
| **CNAME** | `autoconfig.tudominio.com` | `mail.tudominio.com` | Auto-configuracion para Thunderbird |
| **CNAME** | `autodiscover.tudominio.com` | `mail.tudominio.com` | Auto-configuracion para Outlook |
| **SRV** | `_imaps._tcp.tudominio.com` | `0 1 993 mail.tudominio.com` | Auto-configuracion IMAP |
| **SRV** | `_submission._tcp.tudominio.com` | `0 1 587 mail.tudominio.com` | Auto-configuracion SMTP |

   > **Donde configuro esto?** En el panel web de tu proveedor de dominio (Namecheap, GoDaddy, Cloudflare, NIC.ec, etc.). Busca la seccion "DNS" o "Zona DNS". Los registros MX, SPF y A son los mas importantes — sin ellos el correo no funciona.


### Tiempo estimado de instalacion
- Primera vez: 2-4 horas (leyendo y entendiendo cada paso)
- Con experiencia: 30-60 minutos

---

## Instalacion Paso a Paso

> **IMPORTANTE:** En todos los pasos donde veas `tudominio.com`, reemplazalo por tu dominio real (ej: `maquita.org`). Donde veas `IP_DE_TU_SERVIDOR`, pon la IP publica de tu servidor.

### 1. Preparar el servidor

Conectate a tu servidor por SSH (desde tu computadora):
```bash
ssh root@IP_DE_TU_SERVIDOR
```

Actualiza el sistema e instala lo basico:
```bash
# Actualizar lista de paquetes y actualizarlos
apt update && apt upgrade -y

# Instalar herramientas necesarias
apt install -y curl wget git sudo ufw software-properties-common \
  build-essential python3 python3-venv python3-pip nodejs npm
```

**Que instalamos y por que:**
| Paquete | Para que sirve |
|---------|---------------|
| `curl`, `wget` | Descargar archivos de internet |
| `git` | Clonar el codigo del webmail desde GitHub |
| `sudo` | Ejecutar comandos como administrador |
| `ufw` | Firewall (cortafuegos) para proteger el servidor |
| `python3`, `python3-venv`, `python3-pip` | Python y su gestor de paquetes (el backend esta hecho en Python) |
| `nodejs`, `npm` | Node.js y su gestor de paquetes (el frontend esta hecho en React/TypeScript) |
| `build-essential` | Compiladores necesarios para instalar algunas librerias |

Configurar firewall basico:
```bash
# Permitir SSH (para no perder acceso)
ufw allow 22/tcp

# Permitir correo
ufw allow 25/tcp    # SMTP - recibir correos
ufw allow 587/tcp   # Submission - enviar correos
ufw allow 993/tcp   # IMAPS - leer correos desde apps (Outlook, etc)

# Permitir web
ufw allow 80/tcp    # HTTP (redirige a HTTPS)
ufw allow 443/tcp   # HTTPS - la pagina del webmail

# Activar firewall
ufw enable
# Responder "y" cuando pregunte
```

**Verificar:** `ufw status` debe mostrar los puertos abiertos.

### 2. Configurar hostname

El hostname es el "nombre" de tu servidor. Los servidores de correo del mundo lo verifican para asegurarse de que eres legitimo.

```bash
# Establecer el nombre del servidor
hostnamectl set-hostname mail.tudominio.com

# Agregar a /etc/hosts (para que el servidor se reconozca a si mismo)
echo "IP_DE_TU_SERVIDOR mail.tudominio.com" >> /etc/hosts
```

**Verificar:**
```bash
hostname -f
# Debe mostrar: mail.tudominio.com
```

### 3. Instalar PostgreSQL (base de datos)

PostgreSQL es la base de datos donde se guardan los usuarios, contactos, eventos del calendario, tareas, configuraciones, etc. Es como un Excel gigante pero mucho mas rapido y seguro.

```bash
# Instalar PostgreSQL
apt install -y postgresql postgresql-contrib

# Crear la base de datos y el usuario
# (Reemplaza TU_PASSWORD_SEGURA por una contraseña real)
sudo -u postgres psql << 'SQL'
CREATE USER mailserver WITH PASSWORD 'TU_PASSWORD_SEGURA';
CREATE DATABASE maildb OWNER mailserver;
GRANT ALL PRIVILEGES ON DATABASE maildb TO mailserver;
\c maildb
GRANT ALL ON SCHEMA public TO mailserver;
SQL
```

**IMPORTANTE:** Anota la password que elegiste. La necesitaras en el paso 13.

**Verificar:**
```bash
# Debe conectar sin errores y mostrar "maildb=>"
sudo -u postgres psql -d maildb -c "SELECT version();"
```

### 4. Instalar Redis (cache)

Redis es una base de datos ultra-rapida que guarda datos temporales en memoria RAM. El webmail la usa para:
- Sesiones de usuario (que no te pida login cada 5 minutos)
- Cache de carpetas (que no tarde al abrir la bandeja)
- Passwords cifrados temporales

```bash
# Instalar Redis
apt install -y redis-server

# Poner una contraseña (reemplaza TU_REDIS_PASSWORD por una real)
sed -i 's/# requirepass foobared/requirepass TU_REDIS_PASSWORD/' /etc/redis/redis.conf

# Reiniciar para aplicar
systemctl restart redis-server
```

**IMPORTANTE:** Anota esta password tambien. La necesitaras en el paso 13.

**Verificar:**
```bash
redis-cli -a TU_REDIS_PASSWORD ping
# Debe responder: PONG
```

### 5. Instalar Postfix (servidor SMTP)

Postfix es el programa que **recibe y envia correos**. Es como el cartero: recibe cartas del mundo y las entrega al buzon correcto.

```bash
# Instalar Postfix
apt install -y postfix postfix-pgsql

# Cuando pregunte el tipo de configuracion, elegir: "Internet Site"
# Cuando pregunte el hostname: mail.tudominio.com
```

Ahora hay que configurarlo. Abre el archivo principal de configuracion:
```bash
# Hacer backup del original (por si algo sale mal)
cp /etc/postfix/main.cf /etc/postfix/main.cf.original

# Editar (puedes usar nano, vim, o el editor que prefieras)
nano /etc/postfix/main.cf
```

Reemplaza TODO el contenido por esto (cambia `tudominio.com` por tu dominio real):
```ini
# === IDENTIFICACION DEL SERVIDOR ===
# Estos le dicen al mundo quien eres
myhostname = mail.tudominio.com
mydomain = tudominio.com
myorigin = $mydomain
mydestination = localhost
mynetworks = 127.0.0.0/8

# === BUZONES VIRTUALES ===
# Postfix busca los usuarios en PostgreSQL (no en /etc/passwd)
virtual_mailbox_domains = pgsql:/etc/postfix/pgsql-virtual-domains.cf
virtual_mailbox_maps = pgsql:/etc/postfix/pgsql-virtual-mailboxes.cf
virtual_alias_maps = pgsql:/etc/postfix/pgsql-virtual-aliases.cf

# === ENTREGA DE CORREOS ===
# Postfix le pasa los correos a Dovecot para que los guarde
virtual_transport = lmtp:unix:private/dovecot-lmtp

# === SEGURIDAD TLS (cifrado) ===
# Para que nadie lea los correos en transito
smtpd_tls_cert_file = /etc/letsencrypt/live/mail.tudominio.com/fullchain.pem
smtpd_tls_key_file = /etc/letsencrypt/live/mail.tudominio.com/privkey.pem
smtpd_tls_security_level = may
smtpd_tls_protocols = >=TLSv1.2
smtp_tls_security_level = dane

# === LIMITES ===
# Tamano maximo de correo: 25 MB
message_size_limit = 26214400
# Sin limite de buzon (el admin controla esto)
mailbox_size_limit = 0

# === AUTENTICACION ===
# Los usuarios se autentican via Dovecot (no directamente en Postfix)
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
smtpd_sasl_auth_enable = yes

# === RESTRICCIONES ===
# Quienes pueden enviar correos a traves de este servidor
# - Usuarios autenticados (empleados con cuenta)
# - Servidores de la red local
# - Rechazar todo lo demas que no sea para nuestro dominio
smtpd_recipient_restrictions = permit_sasl_authenticated, permit_mynetworks, reject_unauth_destination
smtpd_client_restrictions = permit_mynetworks, permit

# === ANTISPAM ===
# Rspamd analiza cada correo y agrega headers de spam
smtpd_milters = inet:localhost:11332
non_smtpd_milters = inet:localhost:11332
milter_protocol = 6
milter_default_action = accept
```

Ahora crea los archivos que Postfix usa para consultar PostgreSQL. Estos le dicen a Postfix "que dominios aceptas" y "que usuarios existen":

**Archivo 1** — `/etc/postfix/pgsql-virtual-domains.cf`:
```ini
# Consulta: ¿Este dominio es nuestro?
hosts = localhost
user = mailserver
password = TU_PASSWORD_SEGURA
dbname = maildb
query = SELECT domain FROM domain WHERE domain='%s' AND active='1'
```

**Archivo 2** — `/etc/postfix/pgsql-virtual-mailboxes.cf`:
```ini
# Consulta: ¿Este buzon existe?
hosts = localhost
user = mailserver
password = TU_PASSWORD_SEGURA
dbname = maildb
query = SELECT maildir FROM mailbox WHERE username='%s' AND active='1'
```

**Archivo 3** — `/etc/postfix/pgsql-virtual-aliases.cf`:
```ini
# Consulta: ¿Este alias a donde redirige?
hosts = localhost
user = mailserver
password = TU_PASSWORD_SEGURA
dbname = maildb
query = SELECT goto FROM alias WHERE address='%s' AND active='1'
```

Proteger estos archivos (tienen passwords):
```bash
chmod 640 /etc/postfix/pgsql-*.cf
chgrp postfix /etc/postfix/pgsql-*.cf
```

**Verificar:**
```bash
postfix check
# No debe mostrar errores
# Si sale algo con "TLS" no te preocupes, el certificado se genera en el paso 11
```

### 6. Instalar Dovecot (servidor IMAP)

Dovecot es el programa que **guarda los correos y permite leerlos**. Cuando abres el webmail o Outlook, estas hablando con Dovecot.

```bash
# Instalar Dovecot y sus modulos
apt install -y dovecot-core dovecot-imapd dovecot-lmtpd dovecot-pgsql \
  dovecot-sieve dovecot-managesieved dovecot-fts-xapian
```

**Que instalamos:**
| Modulo | Para que |
|--------|---------|
| `dovecot-core` | El servidor base |
| `dovecot-imapd` | Protocolo IMAP (leer correos) |
| `dovecot-lmtpd` | Recibir correos de Postfix |
| `dovecot-pgsql` | Buscar usuarios en PostgreSQL |
| `dovecot-sieve` | Reglas automaticas (ej: mover spam a Junk) |
| `dovecot-managesieved` | Gestionar reglas desde el webmail |
| `dovecot-fts-xapian` | Busqueda full-text (buscar dentro del contenido de los correos) |

Crear el usuario que posee todos los correos en disco:
```bash
# Crear usuario "vmail" que sera dueno de todos los archivos de correo
groupadd -g 150 vmail
useradd -u 150 -g vmail -d /var/vmail -s /usr/sbin/nologin -m vmail

# Crear directorio para correos
mkdir -p /var/vmail
chown -R vmail:vmail /var/vmail
```

Configurar donde se guardan los correos — `/etc/dovecot/conf.d/10-mail.conf`:
```ini
# Cada usuario tiene su carpeta: /var/vmail/dominio/usuario/Maildir/
mail_location = maildir:/var/vmail/%d/%n/Maildir
mail_home = /var/vmail/%d/%n
mail_uid = vmail
mail_gid = vmail
first_valid_uid = 150

# Plugins que mejoran rendimiento y seguridad
# quota: limites de espacio por usuario
# fts + fts_xapian: busqueda rapida dentro de correos
# mail_crypt: cifrado de correos en disco
# mail_compress: comprimir correos para ahorrar espacio
# lazy_expunge: borrado rapido (mueve a papelera interna primero)
mail_plugins = quota acl fts fts_xapian lazy_expunge mail_crypt mail_compress

# Comprimir correos almacenados (ahorra ~60% de disco)
mail_compress_write_method = gz

# Cifrado de emails en disco (si alguien roba el disco, no puede leerlos)
plugin {
  mail_crypt_curve = secp521r1
}
```

Configurar autenticacion — `/etc/dovecot/conf.d/10-auth.conf`:
```ini
# No permitir passwords en texto plano sin TLS
disable_plaintext_auth = yes
auth_mechanisms = plain login

# Buscar usuarios en PostgreSQL (no en /etc/passwd)
!include auth-sql.conf.ext
```

Crear consulta SQL — `/etc/dovecot/dovecot-sql.conf.ext`:
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

Configurar busqueda full-text (para poder buscar dentro del contenido de los correos) — `/etc/dovecot/conf.d/90-fts.conf`:
```ini
# Indexar automaticamente todos los correos nuevos
fts_autoindex = yes
fts_autoindex_max_recent_msgs = 999
fts_search_add_missing = yes

# Soporte para espanol e ingles
language "en" {
  default = yes
}

language "es" {
}

# Motor de busqueda Xapian (rapido y ligero)
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

```bash
# Reiniciar ambos servicios
systemctl restart dovecot postfix
```

**Verificar:**
```bash
# Ambos deben estar "active (running)"
systemctl status dovecot
systemctl status postfix
```

### 7. Instalar Rspamd (antispam) y ClamAV (antivirus)

Rspamd analiza cada correo entrante y le asigna un puntaje de spam. ClamAV escanea los adjuntos buscando virus.

```bash
# Instalar ambos
apt install -y rspamd clamav clamav-daemon

# Actualizar base de datos de virus (toma 1-2 minutos)
freshclam
```

**Generar clave DKIM** — DKIM es una firma digital que demuestra que el correo realmente salio de tu servidor (como un sello oficial). Sin DKIM, Gmail y Outlook pueden enviar tus correos a spam.

```bash
# Crear directorio para las claves
mkdir -p /var/lib/rspamd/dkim

# Generar la clave (reemplaza tudominio.com)
rspamadm dkim_keygen -b 2048 -s mail -d tudominio.com \
  -k /var/lib/rspamd/dkim/tudominio.com.mail.key \
  > /var/lib/rspamd/dkim/tudominio.com.mail.txt

# Dar permisos correctos
chown -R _rspamd:_rspamd /var/lib/rspamd/dkim

# IMPORTANTE: Mostrar el registro DNS que debes agregar
echo "=== COPIA ESTO A TU DNS ==="
cat /var/lib/rspamd/dkim/tudominio.com.mail.txt
echo "==========================="
```

**ACCION REQUERIDA:** Copia el contenido que se muestra y agregalo como registro TXT en tu DNS con el nombre `mail._domainkey.tudominio.com`. Sin esto, tus correos llegaran a spam de otros servidores.

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

Configurar acciones de spam en `/etc/rspamd/local.d/actions.conf`:
```ini
# IMPORTANTE: Nunca rechazar correos
# Solo marcarlos para que el filtro interno decida
reject = null;
greylist = 4;
add_header = 6;
rewrite_subject = 12;
```

Configurar ClamAV en `/etc/rspamd/local.d/antivirus.conf`:
```ini
# Si encuentra virus, NO rechazar — solo agregar header
# Asi el admin puede revisar en cuarentena
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

**Verificar:**
```bash
systemctl status rspamd clamav-daemon
# Ambos deben estar activos
```

### 8. Configurar Sieve (clasificacion automatica de spam)

Sieve es un lenguaje de reglas que dice "si un correo tiene esta marca, muevelo a esta carpeta". Es como un asistente que clasifica tu correo automaticamente.

```bash
# Crear directorio para reglas globales
mkdir -p /var/vmail/sieve
```

Crear `/var/vmail/sieve/before.sieve`:
```sieve
require ["fileinto", "mailbox"];

# Si Rspamd lo marco como spam → mover a carpeta Junk
if header :is "X-Spam-Flag" "YES" {
    fileinto :create "Junk";
    stop;
}

if header :contains "X-Spam-Status" "Yes" {
    fileinto :create "Junk";
    stop;
}

# Si el filtro Python personalizado lo marco como spam → mover a Junk
if header :is "X-Maquita-Spam" "YES" {
    fileinto :create "Junk";
    stop;
}
```

```bash
# Compilar las reglas (genera el archivo .svbin)
sievec /var/vmail/sieve/before.sieve

# Dar permisos al usuario de correo
chown -R vmail:vmail /var/vmail/sieve
```

### 9. Instalar filtro anti-spam Python (opcional pero recomendado)

Este es un filtro personalizado que TU controlas. Puedes agregar palabras clave para detectar spam especifico de tu organizacion. A diferencia de Rspamd (que usa reglas genericas), este filtro es tuyo.

**Como funciona:**
1. Postfix recibe un correo
2. Se lo pasa al script Python
3. El script busca palabras clave en el asunto y cuerpo
4. Si encuentra suficientes coincidencias → marca como SPAM
5. El correo se entrega (NUNCA se rechaza)
6. Sieve lo mueve a Junk si esta marcado

```bash
# Crear directorios
mkdir -p /opt/maquita-mail-filter /etc/maquita-mail

# Copiar el script del filtro (viene con el webmail)
cp /opt/maquita-webmail/scripts/spam-filter-service.py /opt/maquita-mail-filter/
chmod +x /opt/maquita-mail-filter/spam-filter-service.py
```

Crear tu lista de palabras clave — `/etc/maquita-mail/spam-keywords.txt`:
```
# ============================================
# PALABRAS CLAVE DEL FILTRO ANTI-SPAM
# ============================================
# Formato: palabra_o_frase | peso
# Si la suma de pesos >= 3, el correo va a Junk
# Se lee en cada correo nuevo — no necesitas reiniciar nada
# Las lineas que empiezan con # son comentarios
# ============================================

# --- Phishing (suplantacion de identidad) ---
your account has been suspended|3
verify your account immediately|3
su cuenta ha sido suspendida|3
verifique su identidad ahora|3
hemos detectado actividad sospechosa|2

# --- Premios y estafas ---
you have won|3
has ganado|3
claim your prize|3
reclama tu premio|3
felicidades has sido seleccionado|3

# --- Estafas financieras ---
nigerian prince|5
herencia millonaria|3
earn money from home|3
gana dinero desde casa|3
inversion sin riesgo|2
bitcoin gratis|3

# --- Farmacia spam ---
viagra|3
cialis|3
pharmacy online|2

# --- Urgencia falsa ---
act now|1
limited time offer|1
oferta por tiempo limitado|1
urgente abrir inmediatamente|2

# --- Puedes agregar las tuyas aqui ---
# ejemplo: palabra sospechosa|2
```

Crear tu lista de remitentes de confianza — `/etc/maquita-mail/whitelist-senders.txt`:
```
# ============================================
# WHITELIST — Remitentes que NUNCA van a spam
# ============================================
# Un dominio o email por linea
# Si el remitente coincide, siempre va a Inbox
# ============================================

# Proveedores grandes de correo
gmail.com
outlook.com
hotmail.com
yahoo.com
live.com
icloud.com

# Tu propio dominio
tudominio.com

# Gobierno y educacion (ajusta a tu pais)
# gov.ec
# edu.ec
# gob.mx
```

Configurar Postfix para usar el filtro — agregar al final de `/etc/postfix/master.cf`:
```
# === FILTRO ANTI-SPAM PYTHON ===
# Postfix le pasa cada correo al script Python para analisis
maquita-filter unix - n n - 10 pipe
  flags=Rq user=vmail argv=/opt/maquita-mail-filter/spam-filter-service.py -f ${sender} -- ${recipient}

# Puerto de reinyeccion (el script devuelve el correo por aqui)
# Sin content_filter para evitar loop infinito
10025 inet n - n - 10 smtpd
  -o content_filter=
  -o receive_override_options=no_unknown_recipient_checks,no_header_body_checks
  -o smtpd_recipient_restrictions=permit_mynetworks,reject
  -o mynetworks=127.0.0.0/8
```

Activar el filtro — agregar en `/etc/postfix/main.cf`:
```ini
# Activar filtro Python (cada correo pasa por el script)
content_filter = maquita-filter:
```

```bash
# Crear archivo de log y dar permisos
touch /var/log/maquita-spam-filter.log
chown vmail:vmail /var/log/maquita-spam-filter.log

# Reiniciar Postfix para activar
systemctl restart postfix
```

**Verificar:**
```bash
# Enviar un correo de prueba (debe aparecer en el log)
echo "Correo de prueba" | mail -s "Test filtro" usuario@tudominio.com

# Ver el log (Ctrl+C para salir)
tail -f /var/log/maquita-spam-filter.log
# Debe mostrar algo como: HAM | score=0/3 | from=... | subject=Test filtro
```

### 10. Instalar Radicale (CalDAV/CardDAV)

Radicale es un servidor de calendario y contactos. Permite que el webmail tenga un calendario funcional y sincronice contactos con telefonos y Outlook.

```bash
# Instalar Radicale
pip3 install radicale

# Crear usuario y directorios
useradd -r -s /usr/sbin/nologin radicale
mkdir -p /var/lib/radicale/collections /etc/radicale
chown -R radicale:radicale /var/lib/radicale
```

Crear configuracion — `/etc/radicale/config`:
```ini
[server]
# Solo escuchar en localhost (Nginx lo expone al mundo)
hosts = 127.0.0.1:5232

[auth]
# Sin autenticacion propia (el webmail maneja la autenticacion)
type = none

[storage]
filesystem_folder = /var/lib/radicale/collections

[logging]
level = warning
```

Crear servicio systemd — `/etc/systemd/system/radicale.service`:
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
# Iniciar y habilitar para que arranque automaticamente
systemctl daemon-reload
systemctl enable --now radicale
```

**Verificar:**
```bash
systemctl status radicale
# Debe estar activo

curl -s http://127.0.0.1:5232/.web/
# Debe responder HTML (la interfaz web de Radicale)
```

### 11. Certificado SSL (HTTPS)

El certificado SSL es lo que pone el **candadito verde** en el navegador. Sin esto, los navegadores marcan tu sitio como "No seguro" y las contraseñas viajan sin cifrar.

**Let's Encrypt** te da certificados **gratuitos** que se renuevan automaticamente cada 90 dias.

**REQUISITO:** Antes de este paso, tu dominio (`mail.tudominio.com`) debe apuntar a la IP de tu servidor. Puedes verificar con: `dig +short mail.tudominio.com` — debe mostrar tu IP.

```bash
# Instalar Certbot (el programa que obtiene certificados)
apt install -y certbot

# Obtener el certificado
# Certbot verificara que el dominio apunta a este servidor
certbot certonly --standalone -d mail.tudominio.com

# Si el puerto 80 esta ocupado por Nginx, usa este comando en su lugar:
# certbot certonly --nginx -d mail.tudominio.com
```

Certbot te pedira:
1. Tu email (para avisos de renovacion)
2. Aceptar terminos de servicio
3. Si quieres compartir tu email con EFF (opcional)

Los certificados se guardan en: `/etc/letsencrypt/live/mail.tudominio.com/`

Configurar renovacion automatica:
```bash
# Probar que la renovacion funciona
certbot renew --dry-run

# Certbot ya crea un timer automatico, verificar:
systemctl list-timers | grep certbot
```

**Ahora si puedes reiniciar Postfix** (que necesitaba el certificado):
```bash
systemctl restart postfix
```

### 12. Instalar Fundacion Maquita Webmail

Aqui es donde instalas la aplicacion web en si.

```bash
# Ir al directorio donde se instala
cd /opt

# Descargar el codigo desde GitHub
git clone https://github.com/wilsongabriel30/webmailMaquita.git maquita-webmail
cd maquita-webmail
```

**Instalar el Backend (la parte de Python que procesa todo):**
```bash
cd backend

# Crear un "entorno virtual" de Python
# (es como una carpeta aislada para que las librerias del webmail
#  no interfieran con las del sistema)
python3 -m venv venv

# Activar el entorno virtual
source venv/bin/activate

# Instalar todas las librerias necesarias
pip install -r requirements.txt
# Esto toma 1-2 minutos. Instala FastAPI, SQLAlchemy, Redis, etc.

# Volver al directorio principal
cd ..
```

**Instalar el Frontend (la interfaz que ves en el navegador):**
```bash
cd frontend

# Instalar librerias de JavaScript
npm install
# Esto toma 1-3 minutos. Instala React, TypeScript, Vite, etc.

# Compilar la interfaz (genera los archivos HTML/CSS/JS optimizados)
npm run build
# Debe terminar sin errores y mostrar los archivos generados en dist/

# Volver al directorio principal
cd ..
```

**Crear la estructura de despliegue:**
```bash
# Crear directorio donde Nginx buscara los archivos
mkdir -p /opt/maquita-webmail/www

# Enlazar la interfaz compilada
ln -sf /opt/maquita-webmail/frontend/dist /opt/maquita-webmail/www/webmail
```

**Verificar:**
```bash
# Debe existir y tener archivos
ls /opt/maquita-webmail/www/webmail/
# Debe mostrar: index.html, assets/, etc.
```

### 13. Configurar variables de entorno

El archivo `.env` contiene todas las contraseñas y configuraciones del webmail. **NUNCA lo subas a GitHub** (ya esta en `.gitignore`).

```bash
# Copiar el ejemplo
cp /opt/maquita-webmail/backend/.env.example /opt/maquita-webmail/backend/.env

# Editar con tus datos reales
nano /opt/maquita-webmail/backend/.env
```

Contenido del archivo (reemplaza TODOS los valores):
```ini
# === BASE DE DATOS ===
# La password que creaste en el paso 3
DATABASE_URL=postgresql://mailserver:TU_PASSWORD_SEGURA@localhost:5432/maildb

# === REDIS ===
# La password que creaste en el paso 4
REDIS_URL=redis://:TU_REDIS_PASSWORD@localhost:6379/0

# === JWT (tokens de sesion) ===
# Genera una clave aleatoria con este comando:
#   python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=PEGA_AQUI_LA_CLAVE_GENERADA

# === SERVIDOR DE CORREO ===
# Si todo esta en el mismo servidor, deja estos valores
IMAP_HOST=127.0.0.1
IMAP_PORT=143
SMTP_HOST=127.0.0.1
SMTP_PORT=587
SIEVE_HOST=127.0.0.1
SIEVE_PORT=4190

# === TU DOMINIO ===
MAIL_DOMAIN=tudominio.com
COOKIE_DOMAIN=mail.tudominio.com
CORS_ORIGINS=https://mail.tudominio.com

# === ADMINISTRACION ===
# Password para el panel de admin (elige una segura)
MASTER_PASSWORD=ELIGE_UNA_PASSWORD_SEGURA
# Otra clave aleatoria (genera con el mismo comando de arriba)
ADMIN_JWT_SECRET=PEGA_OTRA_CLAVE_GENERADA

# === INTELIGENCIA ARTIFICIAL (opcional) ===
# Si configuraste el servidor de IA (paso 18), descomenta estas lineas:
# IA_API_KEY=tu-clave-api
# OLLAMA_URL=http://ip-servidor-ia:8000
```

### 14. Crear servicio systemd

Systemd es el administrador de servicios de Linux. Le decimos que arranque el webmail automaticamente cuando el servidor se enciende.

Crear `/etc/systemd/system/maquita-webmail.service`:
```ini
[Unit]
Description=Fundacion Maquita Webmail API
# Esperar a que estos servicios esten listos antes de arrancar
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
# Dar permisos al usuario www-data
chown -R www-data:www-data /opt/maquita-webmail/backend

# Cargar y arrancar el servicio
systemctl daemon-reload
systemctl enable --now maquita-webmail

# Esperar 5 segundos a que arranque
sleep 5
```

**Verificar:**
```bash
systemctl status maquita-webmail
# Debe estar "active (running)"

curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
# Debe mostrar {"status": "ok", ...}
```

### 15. Configurar Nginx (proxy web)

Nginx es el **servidor web** que recibe las peticiones del navegador y las dirige al webmail. Tambien maneja HTTPS, compresion y cache.

```bash
apt install -y nginx
```

Crear `/etc/nginx/sites-available/mail.tudominio.com`:
```nginx
# === LIMITES DE VELOCIDAD ===
# Proteccion contra ataques de fuerza bruta
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;   # Max 5 intentos de login por minuto
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;     # Max 30 peticiones API por segundo

# === REDIRECCION HTTP → HTTPS ===
server {
    listen 80;
    server_name mail.tudominio.com;
    # Permitir verificacion de certificados Let's Encrypt
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    # Todo lo demas va a HTTPS
    location / { return 301 https://$host$request_uri; }
}

# === SERVIDOR PRINCIPAL (HTTPS) ===
server {
    listen 443 ssl http2;
    server_name mail.tudominio.com;

    # Certificados SSL (generados en paso 11)
    ssl_certificate /etc/letsencrypt/live/mail.tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mail.tudominio.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Cabeceras de seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Compresion (hace la pagina mas rapida)
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    # --- WEBMAIL (frontend) ---
    location /webmail/ {
        root /opt/maquita-webmail/www;
        # Service Worker sin cache (para actualizaciones)
        location = /webmail/sw.js {
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Service-Worker-Allowed "/webmail/";
        }
        # Assets con cache largo (tienen hash en el nombre, cambian al actualizar)
        location ~* /webmail/assets/ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
        # Si no encuentra el archivo, servir index.html (SPA routing)
        try_files $uri $uri/ /webmail/index.html;
    }

    # --- API: Login (con limite estricto contra fuerza bruta) ---
    location = /api/auth/login {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://127.0.0.1:8000;
        include proxy_params;
    }

    # --- API: Todo lo demas ---
    location /api/ {
        limit_req zone=api burst=80 nodelay;
        proxy_pass http://127.0.0.1:8000;
        include proxy_params;
        client_max_body_size 25M;     # Adjuntos hasta 25 MB
        proxy_read_timeout 120s;      # Timeout para operaciones lentas
    }

    # --- WebSocket (notificaciones en tiempo real) ---
    location /api/ws {
        proxy_pass http://127.0.0.1:8000/api/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;    # Mantener conexion 1 hora
    }

    # --- CalDAV/CardDAV (calendario y contactos) ---
    location /.well-known/caldav { return 301 /dav/; }
    location /.well-known/carddav { return 301 /dav/; }
    location /dav/ {
        proxy_pass http://127.0.0.1:5232/;
        client_max_body_size 50M;
    }

    # --- Rspamd UI (panel antispam, solo admin) ---
    location /rspamd/ {
        auth_basic "Rspamd Admin";
        auth_basic_user_file /etc/nginx/.htpasswd_rspamd;
        proxy_pass http://127.0.0.1:11334/;
    }

    # Redirigir la raiz al webmail
    location / { return 301 /webmail; }
}
```

Crear password para Rspamd UI:
```bash
# Instalar herramienta de passwords
apt install -y apache2-utils

# Crear usuario admin para Rspamd (reemplaza TU_PASSWORD)
htpasswd -c /etc/nginx/.htpasswd_rspamd admin
# Te pedira una password, escogela segura
```

Activar el sitio:
```bash
# Habilitar el sitio
ln -sf /etc/nginx/sites-available/mail.tudominio.com /etc/nginx/sites-enabled/

# Desactivar el sitio por defecto
rm -f /etc/nginx/sites-enabled/default

# Verificar que no hay errores de sintaxis
nginx -t
# Debe decir: "test is successful"

# Recargar Nginx
systemctl reload nginx
```

**Verificar:**
```bash
# Abrir en el navegador (debe mostrar la pagina de login):
# https://mail.tudominio.com/webmail/

# O probar desde terminal:
curl -s -o /dev/null -w "%{http_code}" https://mail.tudominio.com/webmail/
# Debe responder: 200
```

### 16. Crear primer buzon de correo

Ahora vamos a crear tu primera cuenta de correo. Este proceso crea un usuario en la base de datos.

```bash
# Paso 1: Generar password cifrada
# Reemplaza "TuPasswordSegura" por la password que quieras para el correo
doveadm pw -s BLF-CRYPT -p TuPasswordSegura
# Copia el resultado (empieza con $2y$05$...)
```

```bash
# Paso 2: Crear el dominio y el buzon en la base de datos
# IMPORTANTE: Reemplaza:
#   - tudominio.com por tu dominio real
#   - usuario por el nombre del buzon (ej: admin, info, wilson)
#   - $2y$05$...HASH... por el hash del paso anterior
#   - "Nombre del Usuario" por el nombre real

sudo -u postgres psql -d maildb << 'SQL'

-- Registrar tu dominio
INSERT INTO domain (domain, description, transport, active)
VALUES ('tudominio.com', 'Dominio principal', 'virtual', 1);

-- Crear el buzon de correo
INSERT INTO mailbox (username, password, name, maildir, domain, active)
VALUES (
  'usuario@tudominio.com',
  '$2y$05$...HASH_DEL_PASO_ANTERIOR...',
  'Nombre del Usuario',
  'tudominio.com/usuario/Maildir/',
  'tudominio.com',
  1
);

-- Crear alias (necesario para que Postfix acepte correos)
INSERT INTO alias (address, goto, domain, active)
VALUES ('usuario@tudominio.com', 'usuario@tudominio.com', 'tudominio.com', 1);

SQL
```

**NOTA:** Para crear mas buzones despues, podras hacerlo desde el panel de administracion del webmail (mas facil que por terminal).

### 17. Verificar instalacion completa

Llegaste al final. Vamos a verificar que todo funciona:

```bash
echo "=== VERIFICANDO SERVICIOS ==="

# 1. Todos los servicios deben estar activos
for svc in maquita-webmail postfix dovecot postgresql redis-server nginx rspamd radicale; do
  status=$(systemctl is-active $svc 2>/dev/null || echo "no instalado")
  echo "$svc: $status"
done

echo ""
echo "=== VERIFICANDO PUERTOS ==="
# 2. Puertos que deben estar escuchando
ss -tlnp | grep -E '25|143|443|587|993|5232|8000'

echo ""
echo "=== VERIFICANDO API ==="
# 3. La API debe responder
curl -s http://127.0.0.1:8000/api/health

echo ""
echo "=== VERIFICANDO DNS ==="
# 4. Registros DNS (reemplaza tudominio.com)
echo "MX:"
dig +short MX tudominio.com
echo "SPF:"
dig +short TXT tudominio.com | grep spf
echo "DKIM:"
dig +short TXT mail._domainkey.tudominio.com
echo "DMARC:"
dig +short TXT _dmarc.tudominio.com
```

Si todo esta verde, abre en tu navegador:

**https://mail.tudominio.com/webmail/**

Inicia sesion con el usuario y password que creaste en el paso 16.

**Enviar un correo de prueba:**
1. Desde el webmail, envia un correo a una cuenta de Gmail
2. Verifica que llego a Gmail (revisa spam si no lo ves)
3. Responde desde Gmail para verificar que recibes correos

**Si los correos van a spam de Gmail:**
- Verifica DKIM: `dig +short TXT mail._domainkey.tudominio.com` (debe tener valor)
- Verifica SPF: `dig +short TXT tudominio.com` (debe incluir tu IP)
- Verifica PTR: tu IP debe resolver a `mail.tudominio.com` (pide a tu proveedor de hosting)


### 18. Configurar Inteligencia Artificial (opcional)

El webmail incluye funciones de IA para ayudar a redactar correos: respuestas inteligentes, autocompletado, resumenes y sugerencias de asunto. Todo funciona con modelos locales (sin enviar datos a terceros).

**Requisitos:**
- Un servidor (puede ser el mismo del correo o uno separado) con GPU NVIDIA
- Minimo 8 GB de VRAM para modelos pequenos, 16+ GB para modelos grandes
- NVIDIA drivers + CUDA instalados

#### 18.1 Instalar NVIDIA drivers y CUDA

```bash
# Verificar que el sistema detecta la GPU
lspci | grep -i nvidia

# Instalar drivers NVIDIA (Debian/Ubuntu)
apt install -y nvidia-driver firmware-misc-nonfree
# O en Ubuntu:
# apt install -y nvidia-driver-535

# Reiniciar
reboot

# Verificar que funciona
nvidia-smi
# Debe mostrar tu GPU, memoria VRAM y version del driver
```

#### 18.2 Instalar Ollama

Ollama es el motor que ejecuta los modelos de IA localmente. Es gratuito y open source.

```bash
# Instalar Ollama (una sola linea)
curl -fsSL https://ollama.com/install.sh | sh

# Verificar que esta corriendo
systemctl status ollama
# Debe decir "active (running)"

# Si no esta corriendo:
systemctl enable --now ollama
```

#### 18.3 Descargar un modelo de lenguaje

Necesitas al menos un modelo. Recomendaciones segun tu VRAM:

| VRAM | Modelo recomendado | Comando | Calidad |
|------|-------------------|---------|---------|
| 8 GB | Gemma 2 9B | `ollama pull gemma2:9b` | Buena |
| 8 GB | Llama 3.1 8B | `ollama pull llama3.1:8b` | Buena |
| 8 GB | Qwen 2.5 7B | `ollama pull qwen2.5:7b` | Buena |
| 16 GB | Qwen 2.5 14B | `ollama pull qwen2.5:14b` | Muy buena |
| 24 GB | Gemma 4 26B | `ollama pull gemma4:26b` | Excelente |
| 24 GB | Llama 3.1 70B (Q4) | `ollama pull llama3.1:70b` | Excelente |

```bash
# Ejemplo: descargar Gemma 2 9B (funciona con 8GB VRAM)
ollama pull gemma2:9b

# Verificar que se descargo
ollama list
# Debe mostrar el modelo con su tamano

# Probar que funciona (chat rapido)
ollama run gemma2:9b "Hola, responde en una frase"
# Debe responder en 2-5 segundos
```

#### 18.4 Configurar Ollama para aceptar conexiones remotas

Por defecto Ollama solo escucha en localhost. Si el servidor de IA es diferente al servidor de correo, hay que abrirlo:

```bash
# Editar la configuracion de Ollama
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=*"
EOF

# Recargar y reiniciar
systemctl daemon-reload
systemctl restart ollama

# Verificar que escucha en todas las interfaces
ss -tlnp | grep 11434
# Debe mostrar 0.0.0.0:11434
```

**IMPORTANTE:** Si abres Ollama a la red, asegurate de que solo sea accesible desde tu red interna. Usa firewall:
```bash
# Solo permitir acceso desde la IP del servidor de correo
ufw allow from IP_SERVIDOR_CORREO to any port 11434
ufw deny 11434
```

#### 18.5 Crear el gateway de IA (API intermedia)

El webmail no se conecta directamente a Ollama. Necesita un gateway FastAPI que:
- Autentica las peticiones con API key
- Enruta a la GPU correcta
- Hace failover si una GPU falla
- Expone endpoints estandarizados

Crear `/opt/maquita-ia-gateway/gateway.py`:
```python
"""
Gateway IA para Maquita Webmail
Proxy autenticado entre el webmail y Ollama
"""
import logging
import httpx
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="Maquita IA Gateway")
logging.basicConfig(level=logging.INFO)

# --- CONFIGURACION ---
API_KEY = "tu-clave-api-segura"  # Cambiar por una clave segura
OLLAMA_URL = "http://localhost:11434"  # URL de Ollama
MODELO_DEFAULT = "gemma2:9b"  # Cambiar por tu modelo

# --- AUTENTICACION ---
def verificar_token(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Token de autenticacion requerido")
    return "webmail"

# --- SCHEMAS ---
class GenerateRequest(BaseModel):
    prompt: str
    system: str = ""
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 500
    preferir_gpu: str = "auto"
    usar_rag: bool = False

# --- ENDPOINTS ---
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/v1/ia/generate")
async def generate(req: GenerateRequest, user: str = Header(None, alias="X-API-Key")):
    verificar_token(user)
    modelo = req.model or MODELO_DEFAULT
    payload = {
        "model": modelo,
        "prompt": req.prompt,
        "system": req.system,
        "stream": False,
        "options": {"temperature": req.temperature, "num_predict": req.max_tokens},
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return {
            "respuesta": data.get("response", ""),
            "tokens_usados": data.get("eval_count", 0),
            "modelo": modelo,
            "gpu": "local",
            "gpu_url": OLLAMA_URL,
            "tiempo_ms": int(data.get("total_duration", 0) / 1_000_000),
            "rag_usado": False,
            "rag_documentos": 0,
            "authenticated_as": "webmail",
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error Ollama: {e}")

@app.get("/api/v1/ia/status")
async def status(user: str = Header(None, alias="X-API-Key")):
    verificar_token(user)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            modelos = [m["name"] for m in resp.json().get("models", [])]
        return {"gpus": {"local": {"url": OLLAMA_URL, "modelos": modelos, "status": "ok"}}, "gateway": "ok"}
    except Exception as e:
        return {"gpus": {"local": {"status": "offline", "error": str(e)}}, "gateway": "ok"}

@app.get("/api/v1/ia/models")
async def models(user: str = Header(None, alias="X-API-Key")):
    verificar_token(user)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            modelos = [m["name"] for m in resp.json().get("models", [])]
        return {"modelos": modelos}
    except:
        return {"modelos": []}

@app.get("/api/v1/email-assistant/health")
async def email_health(user: str = Header(None, alias="X-API-Key")):
    verificar_token(user)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            modelos = [m["name"] for m in resp.json().get("models", [])]
        return {"status": "ok", "model": MODELO_DEFAULT, "available_models": modelos, "ollama_url": OLLAMA_URL}
    except Exception as e:
        return {"status": "offline", "error": str(e)}
```

Instalar dependencias y ejecutar:
```bash
# Crear entorno virtual
cd /opt/maquita-ia-gateway
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn httpx

# Probar que funciona
uvicorn gateway:app --host 0.0.0.0 --port 8000

# En otra terminal, probar:
curl -s -H "X-API-Key: tu-clave-api-segura" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8000/api/v1/ia/generate \
  -d '{"prompt": "Hola, responde brevemente"}'
# Debe retornar JSON con "respuesta"
```

Crear servicio systemd para que arranque automaticamente:
```bash
cat > /etc/systemd/system/maquita-ia-gateway.service << 'EOF'
[Unit]
Description=Maquita IA Gateway
After=network.target ollama.service

[Service]
Type=simple
WorkingDirectory=/opt/maquita-ia-gateway
ExecStart=/opt/maquita-ia-gateway/venv/bin/uvicorn gateway:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now maquita-ia-gateway

# Verificar
systemctl status maquita-ia-gateway
curl -s http://localhost:8000/health
# Debe responder {"status": "ok"}
```

#### 18.6 Conectar el webmail al servidor de IA

En el archivo `.env` del webmail, agregar estas dos lineas:
```ini
# Si el gateway IA esta en el mismo servidor:
OLLAMA_URL=http://localhost:8000
IA_API_KEY=tu-clave-api-segura

# Si esta en otro servidor (reemplazar IP):
# OLLAMA_URL=http://192.168.1.100:8000
# IA_API_KEY=tu-clave-api-segura
```

Reiniciar el webmail:
```bash
systemctl restart maquita-webmail
```

Verificar la conexion desde el webmail:
```bash
curl -s http://localhost:8000/api/ai/health
# Debe responder {"status": "ok", "ia_server": "connected", ...}
```

#### 18.7 Verificar que funciona en el navegador

1. Ir a `https://mail.tudominio.com/webmail/`
2. Abrir un correo recibido
3. Buscar el boton de "Respuesta inteligente" o el icono de IA
4. Debe generar 3 opciones de respuesta contextualizadas
5. Al redactar un correo, el autocompletado debe sugerir texto

#### 18.8 Configuracion avanzada: multiples GPUs (opcional)

Si tienes dos o mas GPUs, puedes distribuir la carga. Para eso necesitas:

1. Ollama corriendo en cada servidor/GPU
2. Modificar el gateway para incluir ambas URLs
3. El sistema rutea automaticamente:
   - GPU principal: tareas pesadas (resumenes largos, razonamiento)
   - GPU secundaria: tareas rapidas (autocompletado, chat)
   - Failover automatico si una GPU falla

Ejemplo con dos GPUs:
```python
# En el gateway, agregar segunda GPU
GPU_LOCAL = "http://localhost:11434"      # GPU 1 (ej: P40)
GPU_REMOTA = "http://192.168.1.50:11434"  # GPU 2 (ej: RTX 3090)
```

#### 18.9 Solucionar problemas de IA

| Problema | Solucion |
|----------|----------|
| "El servicio de IA no respondio a tiempo" | El modelo es muy grande para tu GPU. Prueba uno mas pequeno |
| "Error al comunicarse con el servicio de IA" | Verificar que Ollama y el gateway estan corriendo: `systemctl status ollama maquita-ia-gateway` |
| Las respuestas son muy lentas (>30 seg) | Usa un modelo mas pequeno o una GPU con mas VRAM |
| Las respuestas son de baja calidad | Usa un modelo mas grande (14B o 26B) |
| "Token de autenticacion requerido" | Verificar que `IA_API_KEY` en `.env` coincide con `API_KEY` en el gateway |
| GPU no detectada por Ollama | Verificar drivers: `nvidia-smi`. Si no funciona: `apt install nvidia-driver` y reiniciar |
| Ollama usa CPU en vez de GPU | Verificar CUDA: `nvcc --version`. Reinstalar Ollama si es necesario |

**Modelos recomendados por idioma:**
- **Espanol**: Gemma 4, Qwen 2.5, Llama 3.1 (todos funcionan bien en espanol)
- **Solo ingles**: Phi-3, Mistral (menos recomendados para webmail en espanol)

**Recursos:**
- Ollama: https://ollama.com
- Lista de modelos: https://ollama.com/library
- Documentacion NVIDIA CUDA: https://developer.nvidia.com/cuda-downloads


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
