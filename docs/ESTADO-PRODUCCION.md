# Estado de Producción — Fundación Maquita Webmail

**Fecha:** 2026-04-12
**Versión:** 1.0-beta

## Resumen

Sistema de correo electrónico con interfaz tipo Outlook. Backend FastAPI + Frontend React/TypeScript.

## Hallazgos de Auditoría y Correcciones

### Puntos Muy Alta — RESUELTOS

| # | Hallazgo | Estado | Corrección aplicada |
|---|----------|--------|-------------------|
| 1 | Frontend no instala limpio (npm ci falla) | ✅ Resuelto | `@tailwindcss/vite` y `tailwindcss` actualizados a 4.2.2, compatible con Vite 8 |
| 2 | Hardcodes de dominio en backend | ✅ Resuelto | 7 archivos parametrizados via `settings.cookie_domain` / `settings.mail_domain` |
| 3 | Password IMAP en texto plano en Redis | ✅ Resuelto | Cifrado Fernet (clave derivada de SECRET_KEY via SHA-256) |
| 4 | No hay tests automáticos | ✅ Resuelto | 15 smoke tests (pytest): auth, endpoints, seguridad, health |
| 5 | No hay healthcheck | ✅ Resuelto | `GET /api/health` verifica API + Redis + PostgreSQL |
| 6 | No hay CI/CD | ✅ Resuelto | GitHub Actions: lint Python, smoke tests, build frontend |

### Puntos Alta — Estado

| Hallazgo | Estado | Notas |
|----------|--------|-------|
| Config duplicada (app.config vs app.core.config) | ✅ Resuelto | Consolidado en `app.config`, proxy en `core/config.py` |
| Logging hardcodeado | ✅ Resuelto | `security_log_path` configurable via `.env` |
| Archivos de despliegue | ✅ Resuelto | Nginx, systemd, installer script, Z-Push completo |
| Módulos "stub" | ✅ Verificado | 20 módulos, 18 completos, 2 con TODOs menores (security, ai) |

### Puntos Pendientes (Mejora Continua)

| Hallazgo | Prioridad | Plan |
|----------|-----------|------|
| Tests end-to-end (con IMAP/SMTP real) | Alta | Requiere entorno de staging con Dovecot de prueba |
| TLS en Redis | Media | Cambiar `redis://` por `rediss://` + certificado |
| Pydantic v2 deprecation warnings (2) | Baja | Migrar `class Config` → `ConfigDict`, `min_items` → `min_length` |
| Code splitting frontend | Baja | Configurar dynamic imports para chunks >500KB |

## Resultados de Tests

```
14 passed, 1 skipped, 2 warnings in 0.17s

tests/test_auth.py::test_login_missing_fields ............... PASSED
tests/test_auth.py::test_login_invalid_credentials .......... SKIPPED (requiere Redis)
tests/test_auth.py::test_protected_endpoint_no_auth ......... PASSED
tests/test_auth.py::test_refresh_no_token ................... PASSED
tests/test_auth.py::test_logout_no_auth ..................... PASSED
tests/test_endpoints.py::test_protected_[GET-/api/mail/folders] PASSED
tests/test_endpoints.py::test_protected_[GET-/api/mail/messages/INBOX] PASSED
tests/test_endpoints.py::test_protected_[GET-/api/contacts/] PASSED
tests/test_endpoints.py::test_protected_[GET-/api/calendar/calendars] PASSED
tests/test_endpoints.py::test_protected_[GET-/api/tasks/boards] PASSED
tests/test_endpoints.py::test_protected_[GET-/api/identities/] PASSED
tests/test_health.py::test_api_docs ......................... PASSED
tests/test_health.py::test_openapi_schema ................... PASSED
tests/test_security.py::test_cors_headers ................... PASSED
tests/test_security.py::test_no_server_header_leak .......... PASSED
```

## Healthcheck

```json
{
    "status": "healthy",
    "checks": {
        "api": "ok",
        "redis": "ok",
        "database": "ok"
    }
}
```

## Métricas del Proyecto

| Métrica | Valor |
|---------|-------|
| Archivos Python (backend) | ~146 |
| Archivos TS/TSX (frontend) | ~107 |
| Módulos backend | 20 (todos montados en main.py) |
| Endpoints API | 150+ |
| Tablas PostgreSQL | 77 |
| Tests automáticos | 15 |
| Build frontend | npm ci + vite build (limpio, 0 vulnerabilidades) |

## Arquitectura de Seguridad

| Capa | Implementación |
|------|---------------|
| Autenticación | JWT + cookies HttpOnly + refresh tokens |
| 2FA | TOTP (Google Authenticator compatible) |
| Sesiones | Redis con TTL, passwords cifrados con Fernet |
| CORS | Parametrizado via .env, validado por origen |
| Rate limiting | Nginx: login=5/min, compose=10/min, API=30/s |
| Cabeceras | HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| Antispam | Rspamd integrado con Postfix |
| Certificados | SSL/TLS obligatorio (Let's Encrypt o wildcard) |

## Archivos de Despliegue Incluidos

```
deploy/
├── webmail/
│   ├── instalar.sh          ← Instalador automatizado completo
│   ├── nginx/webmail.conf   ← Config Nginx (rate limit, SSL, SPA, API, WebSocket, CalDAV)
│   └── systemd/maquita-webmail.service
├── z-push/
│   ├── README.md            ← Guía ActiveSync completa
│   ├── Dockerfile           ← Opción Docker
│   ├── instalar.sh          ← Instalador Z-Push
│   ├── configs/             ← 6 archivos de configuración
│   ├── nginx/               ← Snippet ActiveSync
│   └── php-fpm/             ← Pool PHP-FPM dedicado
```
