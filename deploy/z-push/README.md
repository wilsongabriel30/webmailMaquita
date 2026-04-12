# Z-Push — ActiveSync para Maquita Webmail

Sincronización de **correo, calendario y contactos** con dispositivos móviles (Android, iOS, Outlook) mediante el protocolo Microsoft ActiveSync.

## ¿Qué es Z-Push?

Z-Push es una implementación open-source del protocolo ActiveSync de Microsoft. Permite que los dispositivos móviles sincronicen:

- **Correo** (vía IMAP/SMTP)
- **Calendario** (vía CalDAV → Radicale)
- **Contactos** (vía CardDAV → Radicale)

## Arquitectura

```
Dispositivo móvil (Android/iOS/Outlook)
        │
        │ ActiveSync (HTTPS puerto 443)
        ▼
    Nginx (proxy reverso)
        │
        │ FastCGI (socket Unix)
        ▼
  PHP-FPM 8.x (pool zpush)
        │
        ▼
    Z-Push (PHP)
     ├── BackendIMAP ──→ Dovecot (IMAP 143)
     ├── BackendCalDAV ──→ Radicale (CalDAV 5232)
     └── BackendCardDAV ──→ Radicale (CardDAV 5232)
```

## Requisitos Previos

Antes de instalar Z-Push necesitas tener funcionando:

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| Dovecot | 143 | IMAP (correo) |
| Postfix | 465/587 | SMTP (envío) |
| Radicale | 5232 | CalDAV/CardDAV (calendario y contactos) |
| Nginx | 443 | Proxy reverso con SSL |
| PHP-FPM | 8.1+ | Procesador PHP |
| PostgreSQL | 5432 | Base de datos (para autenticación Dovecot) |

## Instalación Paso a Paso

### 1. Instalar PHP y extensiones necesarias

```bash
# Debian 12/13 o Ubuntu 22.04+
apt update
apt install -y \
    php-fpm \
    php-imap \
    php-curl \
    php-xml \
    php-mbstring \
    php-intl \
    php-soap \
    php-xsl \
    libawl-php

# Verificar versión de PHP instalada
php -v
# Anotar la versión (ej: 8.2, 8.3, 8.4) para los pasos siguientes
```

### 2. Descargar Z-Push

```bash
# Clonar desde GitHub
cd /opt
git clone --depth 1 https://github.com/Z-Hub/Z-Push.git z-push

# Permisos
chown -R www-data:www-data /opt/z-push

# Crear directorios de estado y logs
mkdir -p /var/lib/z-push /var/log/z-push
chown -R www-data:www-data /var/lib/z-push /var/log/z-push
```

### 3. Configurar Z-Push

Copiar los archivos de configuración de este directorio:

```bash
# Configuración principal
cp configs/config.php /opt/z-push/src/config.php

# Backend IMAP
cp configs/backend-imap.php /opt/z-push/src/backend/imap/config.php

# Backend CalDAV
cp configs/backend-caldav.php /opt/z-push/src/backend/caldav/config.php

# Backend CardDAV
cp configs/backend-carddav.php /opt/z-push/src/backend/carddav/config.php

# Backend Combined (une IMAP + CalDAV + CardDAV)
cp configs/backend-combined.php /opt/z-push/src/backend/combined/config.php

# Autodiscover
cp configs/autodiscover.php /opt/z-push/src/autodiscover/config.php
```

**Editar cada archivo** y cambiar:
- `mail.example.org` → `mail.tudominio.com`
- `maquita.org` → `tudominio.com`
- Puertos IMAP/SMTP si son diferentes

### 4. Configurar PHP-FPM

```bash
# Detectar versión de PHP
PHP_VERSION=$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')

# Copiar pool de Z-Push
cp php-fpm/zpush.conf /etc/php/${PHP_VERSION}/fpm/pool.d/zpush.conf

# Editar si tu versión de PHP es diferente
# Ajustar el socket si es necesario

# Reiniciar PHP-FPM
systemctl restart php${PHP_VERSION}-fpm
```

### 5. Configurar Nginx

Agregar estas secciones a tu configuración de Nginx del servidor de correo:

```bash
# Copiar snippet de Nginx
# (Integrar el contenido de nginx/activesync.conf en tu server block HTTPS)
```

Dentro del bloque `server { ... }` de tu dominio HTTPS, agregar:

```nginx
# Microsoft ActiveSync (Z-Push)
location /Microsoft-Server-ActiveSync {
    # Cambiar 8.4 por tu versión de PHP
    fastcgi_pass unix:/run/php/php8.4-zpush.sock;
    fastcgi_index index.php;
    fastcgi_param SCRIPT_FILENAME /opt/z-push/src/index.php;
    include fastcgi_params;

    # Push/long polling necesita timeouts largos
    fastcgi_read_timeout 3600;
    fastcgi_send_timeout 3600;
    fastcgi_connect_timeout 60;
    fastcgi_buffering off;

    # Adjuntos grandes
    client_max_body_size 50m;

    access_log /var/log/nginx/activesync-access.log;
    error_log /var/log/nginx/activesync-error.log;
}

# Autodiscover para Outlook (autodiscovery automática)
location ~* /[Aa]utodiscover/[Aa]utodiscover.xml {
    # Cambiar 8.4 por tu versión de PHP
    fastcgi_pass unix:/run/php/php8.4-zpush.sock;
    fastcgi_index index.php;
    fastcgi_param SCRIPT_FILENAME /opt/z-push/src/autodiscover/autodiscover.php;
    include fastcgi_params;
    fastcgi_read_timeout 60;
    fastcgi_buffering off;
}
```

```bash
# Verificar y recargar
nginx -t && systemctl reload nginx
```

### 6. Configurar DNS para Autodiscover

Para que Outlook y los móviles encuentren automáticamente tu servidor:

| Tipo | Nombre | Valor |
|------|--------|-------|
| **CNAME** | `autodiscover.tudominio.com` | `mail.tudominio.com` |
| **SRV** | `_autodiscover._tcp.tudominio.com` | `0 443 mail.tudominio.com` |

### 7. Verificar la instalación

```bash
# Verificar que PHP-FPM escucha
ls -la /run/php/php*-zpush.sock

# Probar ActiveSync (debe dar 401 Unauthorized, NO 502/404)
curl -k -s -o /dev/null -w "%{http_code}" \
    https://mail.tudominio.com/Microsoft-Server-ActiveSync
# Debe devolver: 401

# Probar con credenciales (debe dar 200)
curl -k -s -o /dev/null -w "%{http_code}" \
    --user "usuario@tudominio.com:password" \
    https://mail.tudominio.com/Microsoft-Server-ActiveSync

# Ver logs
tail -f /var/log/z-push/z-push.log
```

---

## Configurar Dispositivos Móviles

### Android (Gmail / Outlook / Samsung Email)

1. Abrir la app de correo
2. Agregar cuenta → **Exchange / ActiveSync**
3. Correo: `usuario@tudominio.com`
4. Contraseña: tu contraseña del correo
5. Servidor: `mail.tudominio.com`
6. Puerto: `443`
7. Tipo de seguridad: **SSL/TLS**
8. Seleccionar qué sincronizar: Correo, Calendario, Contactos

### iOS (iPhone / iPad)

1. Ajustes → Correo → Cuentas → Agregar cuenta
2. Seleccionar **Microsoft Exchange**
3. Correo: `usuario@tudominio.com`
4. Contraseña: tu contraseña
5. Si pide servidor: `mail.tudominio.com`
6. Activar: Correo, Calendarios, Contactos

### Outlook (Windows / Mac)

1. Archivo → Agregar cuenta
2. Ingresar `usuario@tudominio.com`
3. Seleccionar **Exchange ActiveSync** si pregunta
4. Servidor: `mail.tudominio.com`
5. Outlook debería autoconfigurar vía Autodiscover

---

## Administración de Z-Push

### Comandos útiles

```bash
# Ver dispositivos conectados
php /opt/z-push/src/z-push-admin.php -a list

# Ver detalle de un usuario
php /opt/z-push/src/z-push-admin.php -a list -u usuario@tudominio.com

# Forzar resincronización de un dispositivo
php /opt/z-push/src/z-push-admin.php -a resync -u usuario@tudominio.com -d DEVICE_ID

# Borrar estado de sincronización (resetear dispositivo)
php /opt/z-push/src/z-push-admin.php -a remove -u usuario@tudominio.com -d DEVICE_ID

# Limpiar estados huérfanos
php /opt/z-push/src/z-push-admin.php -a fixstates

# Ver versión
php /opt/z-push/src/z-push-admin.php -v
```

### Logs

```bash
# Log principal
tail -f /var/log/z-push/z-push.log

# Log de errores
tail -f /var/log/z-push/z-push-error.log

# Log de Autodiscover
tail -f /var/log/z-push/autodiscover.log

# Log de PHP
tail -f /var/log/z-push/php-error.log
```

---

## Instalación alternativa con Docker

Si prefieres usar Docker en lugar de instalación nativa:

### Dockerfile

```bash
cd /opt/maquita-webmail/deploy/z-push
docker build -t zpush .
```

### Ejecutar contenedor

```bash
docker run -d \
    --name zpush \
    --restart unless-stopped \
    -p 127.0.0.1:9000:9000 \
    -v /opt/z-push/src/config.php:/opt/z-push/src/config.php:ro \
    -v /opt/z-push/src/backend/imap/config.php:/opt/z-push/src/backend/imap/config.php:ro \
    -v /opt/z-push/src/backend/caldav/config.php:/opt/z-push/src/backend/caldav/config.php:ro \
    -v /opt/z-push/src/backend/carddav/config.php:/opt/z-push/src/backend/carddav/config.php:ro \
    -v /opt/z-push/src/backend/combined/config.php:/opt/z-push/src/backend/combined/config.php:ro \
    -v /opt/z-push/src/autodiscover/config.php:/opt/z-push/src/autodiscover/config.php:ro \
    -v /var/lib/z-push:/var/lib/z-push \
    -v /var/log/z-push:/var/log/z-push \
    zpush
```

Con Docker, cambiar el bloque de Nginx para usar TCP en vez de socket:

```nginx
location /Microsoft-Server-ActiveSync {
    # Docker: usar TCP en vez de socket Unix
    fastcgi_pass 127.0.0.1:9000;
    fastcgi_index index.php;
    fastcgi_param SCRIPT_FILENAME /opt/z-push/src/index.php;
    include fastcgi_params;
    fastcgi_read_timeout 3600;
    fastcgi_send_timeout 3600;
    fastcgi_buffering off;
    client_max_body_size 50m;
}
```

---

## Solución de Problemas

| Problema | Solución |
|----------|----------|
| Error 502 Bad Gateway | PHP-FPM no está corriendo: `systemctl restart php8.x-fpm` |
| Error 401 constantemente | Credenciales incorrectas. Probar con `doveadm auth test usuario@dominio password` |
| Calendario no sincroniza | Verificar Radicale: `curl http://127.0.0.1:5232` debe responder |
| Error "Failed opening XMLDocument.php" | Instalar `libawl-php`: `apt install libawl-php` |
| Outlook no autodescubre | Verificar DNS: `nslookup autodiscover.tudominio.com` |
| Correo llega al móvil pero no se envía | Verificar config SMTP en `backend/imap/config.php` (puerto 465 con ssl://) |
| Sincronización lenta | Aumentar `pm.max_children` en pool PHP-FPM |
| Dispositivo no se conecta | Ver log: `tail -f /var/log/z-push/z-push.log` |

---

## Estructura de Archivos

```
/opt/z-push/
├── src/
│   ├── index.php                    ← Punto de entrada ActiveSync
│   ├── config.php                   ← Configuración principal
│   ├── z-push-admin.php             ← Herramienta de administración
│   ├── autodiscover/
│   │   ├── autodiscover.php         ← Autodiscover para Outlook
│   │   └── config.php               ← Config autodiscover
│   └── backend/
│       ├── imap/config.php          ← Config IMAP
│       ├── caldav/config.php        ← Config CalDAV
│       ├── carddav/config.php       ← Config CardDAV
│       └── combined/config.php      ← Config combinada
├── /var/lib/z-push/                 ← Estado de sincronización
└── /var/log/z-push/                 ← Logs
```

---

*Z-Push es software libre bajo licencia AGPLv3 — https://github.com/Z-Hub/Z-Push*
