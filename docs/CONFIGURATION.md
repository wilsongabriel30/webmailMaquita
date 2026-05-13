# Configuration Reference

All configuration is managed through environment variables. The backend reads from `backend/.env` (or system environment).

## Environment Variables

### Required Variables

| Variable            | Description                              | Example                                              |
|---------------------|------------------------------------------|------------------------------------------------------|
| `DATABASE_URL`      | PostgreSQL connection string             | `postgresql://maquita:pass@localhost:5432/maquita_webmail` |
| `REDIS_URL`         | Redis connection string                  | `redis://localhost:6379/0`                            |
| `SECRET_KEY`        | Application secret for session signing   | (64-char random hex)                                  |
| `ADMIN_JWT_SECRET`  | JWT signing key for admin tokens         | (64-char random hex)                                  |
| `CORS_ORIGINS`      | Allowed CORS origins (comma-separated)   | `https://mail.example.com`                           |
| `MAIL_DOMAIN`       | Primary mail domain                      | `example.com`                                        |
| `MAIL_HOSTNAME`     | Mail server FQDN                         | `mail.example.com`                                   |

### Optional Variables

| Variable                  | Default          | Description                                    |
|---------------------------|------------------|------------------------------------------------|
| `APP_ENV`                 | `production`     | Environment: `development`, `staging`, `production` |
| `DEBUG`                   | `false`          | Enable debug mode (never in production)        |
| `LOG_LEVEL`               | `INFO`           | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT`              | `json`           | Log format: `json` or `text`                   |
| `LOG_FILE`                | (none)           | Path to log file (logs to stdout if unset)     |
| `WORKERS`                 | `4`              | Number of uvicorn workers                      |
| `BIND_HOST`               | `127.0.0.1`      | Backend bind address                           |
| `BIND_PORT`               | `8000`           | Backend bind port                              |
| `SESSION_TTL_SECONDS`     | `86400`          | Session lifetime in seconds (24h)              |
| `MAX_UPLOAD_SIZE_MB`      | `25`             | Maximum attachment size in MB                  |
| `RATE_LIMIT_PER_MINUTE`   | `60`             | API rate limit per user per minute             |

## Generating Secrets

Use a cryptographically secure method:

```bash
# Python
python3 -c "import secrets; print(secrets.token_hex(32))"

# OpenSSL
openssl rand -hex 32

# /dev/urandom
head -c 32 /dev/urandom | xxd -p -c 64
```

Generate separate values for `SECRET_KEY` and `ADMIN_JWT_SECRET`. Never reuse secrets across environments.

## Database Configuration

| Variable                | Default | Description                           |
|-------------------------|---------|---------------------------------------|
| `DATABASE_URL`          | --      | Full PostgreSQL connection string     |
| `DB_POOL_SIZE`          | `10`    | Connection pool size                  |
| `DB_MAX_OVERFLOW`       | `20`    | Max overflow connections              |
| `DB_POOL_TIMEOUT`       | `30`    | Pool checkout timeout (seconds)      |
| `DB_ECHO`               | `false` | Echo SQL queries (debug only)        |

### Connection string format

```
postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
```

For production, always use `sslmode=require` or `sslmode=verify-full`.

## Mail Server Configuration

| Variable                  | Default                 | Description                              |
|---------------------------|-------------------------|------------------------------------------|
| `MAIL_DOMAIN`             | --                      | Primary mail domain                      |
| `MAIL_HOSTNAME`           | --                      | Server FQDN for HELO/EHLO               |
| `IMAP_HOST`               | `localhost`             | Dovecot IMAP host                        |
| `IMAP_PORT`               | `993`                   | Dovecot IMAP port                        |
| `SMTP_HOST`               | `localhost`             | Postfix SMTP host                        |
| `SMTP_PORT`               | `587`                   | Postfix submission port                  |
| `LMTP_SOCKET`             | `/var/run/dovecot/lmtp` | Dovecot LMTP socket path                |
| `DOVEADM_SOCKET`          | `/var/run/dovecot/doveadm` | Doveadm socket path                  |
| `DOVEADM_PASSWORD`        | (none)                  | Doveadm HTTP API password               |
| `RSPAMD_URL`              | `http://localhost:11334`| Rspamd web interface URL                |
| `RSPAMD_PASSWORD`         | (none)                  | Rspamd controller password              |

## Redis Configuration

| Variable                | Default                  | Description                         |
|-------------------------|--------------------------|-------------------------------------|
| `REDIS_URL`             | --                       | Full Redis connection string        |
| `REDIS_PREFIX`          | `maquita:`               | Key prefix for namespacing          |
| `REDIS_SOCKET_TIMEOUT`  | `5`                     | Socket timeout (seconds)            |
| `REDIS_RETRY_ON_TIMEOUT` | `true`                 | Retry on timeout                    |

### Connection string format

```
redis://[:PASSWORD@]HOST:PORT/DB
```

For TLS:

```
rediss://[:PASSWORD@]HOST:PORT/DB
```

## CORS and Domain Settings

| Variable              | Default | Description                                    |
|-----------------------|---------|------------------------------------------------|
| `CORS_ORIGINS`        | --      | Allowed origins (comma-separated)              |
| `CORS_ALLOW_CREDENTIALS` | `true` | Allow credentials in CORS requests          |
| `CORS_MAX_AGE`        | `600`   | Preflight cache duration (seconds)             |
| `TRUSTED_PROXIES`     | (none)  | Trusted proxy IPs for X-Forwarded-For          |
| `BASE_URL`            | (none)  | Public URL of the application                  |

## Compliance Module Settings

| Variable                        | Default   | Description                                 |
|---------------------------------|-----------|---------------------------------------------|
| `COMPLIANCE_ENABLED`            | `true`    | Enable compliance/eDiscovery module         |
| `COMPLIANCE_RETENTION_DAYS`     | `2555`    | Default retention period (7 years)          |
| `COMPLIANCE_LEGAL_HOLD_NOTIFY`  | `true`    | Notify admins on legal hold activation      |
| `COMPLIANCE_AUDIT_LOG_LEVEL`    | `detailed`| Audit log detail: `minimal`, `standard`, `detailed` |
| `COMPLIANCE_EXPORT_PATH`       | `/var/lib/maquita/exports` | eDiscovery export directory    |
| `COMPLIANCE_GPG_KEY_ID`        | (none)    | GPG key ID for signing exports              |
| `COMPLIANCE_GPG_PASSPHRASE`    | (none)    | GPG key passphrase                          |
| `FRAUD_DETECTION_ENABLED`      | `true`    | Enable fraud detection rules                |
| `FRAUD_DETECTION_THRESHOLD`    | `0.7`     | Score threshold for flagging (0.0-1.0)      |

## AI Module Settings (Optional)

| Variable               | Default  | Description                                   |
|------------------------|----------|-----------------------------------------------|
| `AI_ENABLED`           | `false`  | Enable AI-powered features                    |
| `AI_PROVIDER`          | (none)   | AI provider: `openai`, `IA`, `ollama`  |
| `AI_API_KEY`           | (none)   | API key for the AI provider                   |
| `AI_MODEL`             | (none)   | Model identifier (e.g., `gpt-4o`, `IA-sonnet-4-20250514`) |
| `AI_BASE_URL`          | (none)   | Custom API endpoint (for Ollama or proxies)   |
| `AI_MAX_TOKENS`        | `1024`   | Max tokens per AI request                     |
| `AI_TIMEOUT_SECONDS`   | `30`     | Request timeout                               |

The AI module is fully optional and can be used for smart compose, email summarization, and classification.

## Logging Configuration

| Variable        | Default  | Description                                       |
|-----------------|----------|---------------------------------------------------|
| `LOG_LEVEL`     | `INFO`   | Minimum log level                                 |
| `LOG_FORMAT`    | `json`   | Output format: `json` (structured) or `text`      |
| `LOG_FILE`      | (none)   | File path; omit to log to stdout                  |
| `LOG_ROTATE_MB` | `100`    | Rotate log file at this size (MB)                 |
| `LOG_RETAIN`    | `30`     | Number of rotated log files to keep               |
| `SYSLOG_ENABLED`| `false`  | Forward logs to syslog                            |
| `SYSLOG_HOST`   | `localhost` | Syslog destination host                        |
| `SYSLOG_PORT`   | `514`    | Syslog destination port                           |

### Production recommendation

```env
LOG_LEVEL=INFO
LOG_FORMAT=json
SYSLOG_ENABLED=true
```

Structured JSON logs integrate well with Loki, Elasticsearch, or any log aggregation tool.

## Example `.env` File

```env
# Core
APP_ENV=production
DEBUG=false
SECRET_KEY=<generate-with-openssl-rand-hex-32>
ADMIN_JWT_SECRET=<generate-with-openssl-rand-hex-32>

# Database
DATABASE_URL=postgresql://maquita:STRONG_PASSWORD@localhost:5432/maquita_webmail?sslmode=require
DB_POOL_SIZE=10

# Redis
REDIS_URL=redis://localhost:6379/0

# Mail
MAIL_DOMAIN=example.com
MAIL_HOSTNAME=mail.example.com
IMAP_HOST=localhost
SMTP_HOST=localhost

# Web
CORS_ORIGINS=https://mail.example.com
BASE_URL=https://mail.example.com

# Compliance
COMPLIANCE_ENABLED=true
COMPLIANCE_GPG_KEY_ID=your-key-id-here

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```
