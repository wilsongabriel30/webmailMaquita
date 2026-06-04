# Referencia de Configuración

Toda la configuración se gestiona mediante variables de entorno. El backend las lee desde `backend/.env` (o del entorno del sistema).

## Variables de Entorno

### Variables Obligatorias

| Variable            | Descripción                                      | Ejemplo                                              |
|---------------------|--------------------------------------------------|------------------------------------------------------|
| `DATABASE_URL`      | Cadena de conexión a PostgreSQL                  | `postgresql://maquita:pass@localhost:5432/maquita_webmail` |
| `REDIS_URL`         | Cadena de conexión a Redis                       | `redis://localhost:6379/0`                            |
| `SECRET_KEY`        | Secreto de la aplicación para firma de sesiones  | (hexadecimal aleatorio de 64 caracteres)              |
| `ADMIN_JWT_SECRET`  | Clave de firma JWT para tokens de administrador  | (hexadecimal aleatorio de 64 caracteres)              |
| `CORS_ORIGINS`      | Orígenes CORS permitidos (separados por coma)    | `https://mail.example.com`                           |
| `MAIL_DOMAIN`       | Dominio de correo principal                      | `example.com`                                        |
| `MAIL_HOSTNAME`     | FQDN del servidor de correo                      | `mail.example.com`                                   |

### Variables Opcionales

| Variable                  | Valor por defecto | Descripción                                             |
|---------------------------|-------------------|---------------------------------------------------------|
| `APP_ENV`                 | `production`      | Entorno: `development`, `staging`, `production`         |
| `DEBUG`                   | `false`           | Activar modo debug (nunca en producción)                |
| `LOG_LEVEL`               | `INFO`            | Nivel de registro: `DEBUG`, `INFO`, `WARNING`, `ERROR`  |
| `LOG_FORMAT`              | `json`            | Formato de registro: `json` o `text`                    |
| `LOG_FILE`                | (ninguno)         | Ruta al archivo de registro (usa stdout si no se define)|
| `WORKERS`                 | `4`               | Número de workers de uvicorn                            |
| `BIND_HOST`               | `127.0.0.1`       | Dirección de escucha del backend                        |
| `BIND_PORT`               | `8000`            | Puerto de escucha del backend                           |
| `SESSION_TTL_SECONDS`     | `86400`           | Duración de la sesión en segundos (24h)                 |
| `MAX_UPLOAD_SIZE_MB`      | `25`              | Tamaño máximo de adjunto en MB                          |
| `RATE_LIMIT_PER_MINUTE`   | `60`              | Límite de peticiones por usuario por minuto             |

## Generación de Secretos

Use un método criptográficamente seguro:

```bash
# Python
python3 -c "import secrets; print(secrets.token_hex(32))"

# OpenSSL
openssl rand -hex 32

# /dev/urandom
head -c 32 /dev/urandom | xxd -p -c 64
```

Genere valores distintos para `SECRET_KEY` y `ADMIN_JWT_SECRET`. Nunca reutilice secretos entre entornos.

## Configuración de Base de Datos

| Variable                | Valor por defecto | Descripción                                    |
|-------------------------|-------------------|------------------------------------------------|
| `DATABASE_URL`          | --                | Cadena de conexión completa a PostgreSQL        |
| `DB_POOL_SIZE`          | `10`              | Tamaño del pool de conexiones                  |
| `DB_MAX_OVERFLOW`       | `20`              | Conexiones máximas de desbordamiento           |
| `DB_POOL_TIMEOUT`       | `30`              | Tiempo de espera del pool en segundos          |
| `DB_ECHO`               | `false`           | Mostrar consultas SQL (solo para debug)        |

### Formato de cadena de conexión

```
postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

En producción, use siempre `sslmode=require` o `sslmode=verify-full`.

## Configuración del Servidor de Correo

| Variable                  | Valor por defecto           | Descripción                                    |
|---------------------------|-----------------------------|------------------------------------------------|
| `MAIL_DOMAIN`             | --                          | Dominio de correo principal                    |
| `MAIL_HOSTNAME`           | --                          | FQDN del servidor para HELO/EHLO              |
| `IMAP_HOST`               | `localhost`                 | Host IMAP de Dovecot                           |
| `IMAP_PORT`               | `993`                       | Puerto IMAP de Dovecot                         |
| `SMTP_HOST`               | `localhost`                 | Host SMTP de Postfix                           |
| `SMTP_PORT`               | `587`                       | Puerto de envío de Postfix                     |
| `LMTP_SOCKET`             | `/var/run/dovecot/lmtp`     | Ruta del socket LMTP de Dovecot               |
| `DOVEADM_SOCKET`          | `/var/run/dovecot/doveadm`  | Ruta del socket de Doveadm                    |
| `DOVEADM_PASSWORD`        | (ninguno)                   | Contraseña de la API HTTP de Doveadm          |
| `RSPAMD_URL`              | `http://localhost:11334`    | URL de la interfaz web de Rspamd              |
| `RSPAMD_PASSWORD`         | (ninguno)                   | Contraseña del controlador de Rspamd          |

## Configuración de Redis

| Variable                 | Valor por defecto | Descripción                            |
|--------------------------|-------------------|----------------------------------------|
| `REDIS_URL`              | --                | Cadena de conexión completa a Redis    |
| `REDIS_PREFIX`           | `maquita:`        | Prefijo de clave para el espacio de nombres |
| `REDIS_SOCKET_TIMEOUT`   | `5`               | Tiempo de espera del socket (segundos)|
| `REDIS_RETRY_ON_TIMEOUT` | `true`            | Reintentar al agotar el tiempo de espera |

### Formato de cadena de conexión

```
redis://[:PASSWORD@]HOST:PORT/DB
```

Para TLS:

```
rediss://[:PASSWORD@]HOST:PORT/DB
```

## Configuración de CORS y Dominio

| Variable                 | Valor por defecto | Descripción                                         |
|--------------------------|-------------------|-----------------------------------------------------|
| `CORS_ORIGINS`           | --                | Orígenes permitidos (separados por coma)            |
| `CORS_ALLOW_CREDENTIALS` | `true`            | Permitir credenciales en peticiones CORS            |
| `CORS_MAX_AGE`           | `600`             | Duración de caché del preflight (segundos)          |
| `TRUSTED_PROXIES`        | (ninguno)         | IPs de proxies confiables para X-Forwarded-For      |
| `BASE_URL`               | (ninguno)         | URL pública de la aplicación                        |

## Configuración del Módulo de Cumplimiento

| Variable                        | Valor por defecto | Descripción                                           |
|---------------------------------|-------------------|-------------------------------------------------------|
| `COMPLIANCE_ENABLED`            | `true`            | Activar módulo de cumplimiento/eDiscovery             |
| `COMPLIANCE_RETENTION_DAYS`     | `2555`            | Período de retención por defecto (7 años)             |
| `COMPLIANCE_LEGAL_HOLD_NOTIFY`  | `true`            | Notificar a administradores al activar retención legal|
| `COMPLIANCE_AUDIT_LOG_LEVEL`    | `detailed`        | Detalle del registro de auditoría: `minimal`, `standard`, `detailed` |
| `COMPLIANCE_EXPORT_PATH`        | `/var/lib/maquita/exports` | Directorio de exportaciones de eDiscovery   |
| `COMPLIANCE_GPG_KEY_ID`         | (ninguno)         | ID de clave GPG para firmar exportaciones             |
| `COMPLIANCE_GPG_PASSPHRASE`     | (ninguno)         | Contraseña de la clave GPG                            |
| `FRAUD_DETECTION_ENABLED`       | `true`            | Activar reglas de detección de fraude                 |
| `FRAUD_DETECTION_THRESHOLD`     | `0.7`             | Umbral de puntuación para marcar (0.0-1.0)            |

## Configuración del Módulo de IA (Opcional)

| Variable               | Valor por defecto | Descripción                                         |
|------------------------|-------------------|-----------------------------------------------------|
| `AI_ENABLED`           | `false`           | Activar funcionalidades potenciadas por IA          |
| `AI_PROVIDER`          | (ninguno)         | Proveedor de IA: `ollama`, `custom`                 |
| `AI_API_KEY`           | (ninguno)         | Clave API del proveedor de IA                       |
| `AI_MODEL`             | (ninguno)         | Identificador del modelo (ej. `gpt-4o`, `llama3`)   |
| `AI_BASE_URL`          | (ninguno)         | Endpoint personalizado (para Ollama o proxies)      |
| `AI_MAX_TOKENS`        | `1024`            | Tokens máximos por petición de IA                   |
| `AI_TIMEOUT_SECONDS`   | `30`              | Tiempo de espera de la petición                     |

El módulo de IA es completamente opcional y puede usarse para redacción asistida, resumen de correos y clasificación.

## Configuración de Registro

| Variable        | Valor por defecto | Descripción                                            |
|-----------------|-------------------|--------------------------------------------------------|
| `LOG_LEVEL`     | `INFO`            | Nivel mínimo de registro                               |
| `LOG_FORMAT`    | `json`            | Formato de salida: `json` (estructurado) o `text`      |
| `LOG_FILE`      | (ninguno)         | Ruta al archivo; omitir para registrar en stdout       |
| `LOG_ROTATE_MB` | `100`             | Rotar el archivo de registro al alcanzar este tamaño (MB) |
| `LOG_RETAIN`    | `30`              | Número de archivos de registro rotados a conservar     |
| `SYSLOG_ENABLED`| `false`           | Reenviar registros a syslog                            |
| `SYSLOG_HOST`   | `localhost`       | Host de destino para syslog                            |
| `SYSLOG_PORT`   | `514`             | Puerto de destino para syslog                          |

### Recomendación para producción

```env
LOG_LEVEL=INFO
LOG_FORMAT=json
SYSLOG_ENABLED=true
```

Los registros JSON estructurados se integran fácilmente con Loki, Elasticsearch o cualquier herramienta de agregación de registros.

## Archivo `.env` de Ejemplo

```env
# Núcleo
APP_ENV=production
DEBUG=false
SECRET_KEY=<generar-con-openssl-rand-hex-32>
ADMIN_JWT_SECRET=<generar-con-openssl-rand-hex-32>

# Base de datos
DATABASE_URL=postgresql://maquita:STRONG_PASSWORD@localhost:5432/maquita_webmail?sslmode=require
DB_POOL_SIZE=10

# Redis
REDIS_URL=redis://localhost:6379/0

# Correo
MAIL_DOMAIN=example.com
MAIL_HOSTNAME=mail.example.com
IMAP_HOST=localhost
SMTP_HOST=localhost

# Web
CORS_ORIGINS=https://mail.example.com
BASE_URL=https://mail.example.com

# Cumplimiento
COMPLIANCE_ENABLED=true
COMPLIANCE_GPG_KEY_ID=your-key-id-here

# Registro
LOG_LEVEL=INFO
LOG_FORMAT=json
```
