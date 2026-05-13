# Estado de Producción — Fundación Maquita Webmail

**Fecha de última verificación:** 2026-04-12
**Verificado contra:** commit en rama main (no ZIP independiente)
**Clasificación:** Preproducción — beta endurecida

---

## Verificaciones Reales Ejecutadas

### Frontend
```
$ npm ci          → ✅ 0 errores, 0 vulnerabilidades
$ npm run build   → ✅ tsc -b (0 errores) + vite build (676ms)
```

### Backend
```
$ python -m pytest tests/ -v
  14 passed, 1 skipped, 0 warnings (0.17s)

$ curl http://127.0.0.1:8000/api/health
  {"status":"healthy","checks":{"api":"ok","redis":"ok","database":"ok"}}
```

### CI/CD
Pipeline GitHub Actions (`.github/workflows/ci.yml`):
- `backend-lint`: compila todos los .py con py_compile
- `backend-tests`: smoke tests con PostgreSQL 16 + Redis 7
- `frontend-build`: npm ci + npm run build (tsc -b + vite build)

---

## Hallazgos de Auditoría y Estado de Corrección

### Severidad Alta — RESUELTOS

| Hallazgo | Corrección | Verificación |
|----------|-----------|-------------|
| `npm ci` fallaba (Vite 8 / Tailwind) | Actualizado a @tailwindcss/vite 4.2.2 | `npm ci` pasa limpio |
| `npm run build` fallaba (errores TS) | Corregidos imports no usados, tipo `list_type`, variable `isFlagged` | `tsc -b && vite build` exit 0 |
| Hardcodes de dominio en backend | 7 archivos parametrizados via settings | `grep` confirma 0 IPs/dominios hardcoded |
| IPs internas en código (red interna) | Parametrizadas via settings.ollama_url, settings.onlyoffice_url | `git grep` de IPs internas devuelve 0 resultados |
| Password IMAP en texto plano en Redis | Cifrado Fernet (clave derivada de SECRET_KEY) | Login funciona, passwords cifradas en Redis |
| Arranque crash si /var/log/webmail/ no existe | Auto-crea directorio + fallback a StreamHandler | Probado: app arranca sin el directorio |
| No había tests | 15 smoke tests (auth, endpoints, security, health) | 14 passed, 1 skipped, 0 warnings |
| No había CI/CD | GitHub Actions con 3 jobs | Workflow en `.github/workflows/ci.yml` |
| Documentación optimista vs realidad | Este documento regenerado con evidencia real | Verificable reproduciendo los comandos |

### Severidad Media — RESUELTOS

| Hallazgo | Corrección |
|----------|-----------|
| Config duplicada (app.config vs core.config) | Consolidado: `app.config` canónico, `core.config` es proxy |
| Logging se inicializaba demasiado pronto | Movido a bloque seguro con try/except + fallback |
| Defaults atados a maquita.org | Cambiados a `example.com` (genéricos) |
| Pydantic deprecation warnings (2) | Migrados: `class Config` → `ConfigDict`, `min_items` → `min_length` |
| security_log_path hardcodeado | Configurable via `.env` (`SECURITY_LOG_PATH`) |

### Pendientes — Mejora Continua

| Hallazgo | Prioridad | Notas |
|----------|-----------|-------|
| Tests E2E frontend (Playwright/Cypress) | Alta | No hay pruebas de navegación UI real |
| Tests IMAP/SMTP reales | Alta | Requiere entorno staging con Dovecot/Postfix de prueba |
| Tests de flujo completo (login → inbox → send) | Alta | Requiere credenciales de prueba y servicios reales |
| Code splitting frontend (chunks >500KB) | Baja | Warning de Vite, no bloquea funcionalidad |
| Prueba de instalación limpia en servidor nuevo | Media | El script `instalar.sh` existe pero no ha sido validado end-to-end |

---

## Métricas del Proyecto

| Métrica | Valor |
|---------|-------|
| Archivos Python (backend) | ~146 |
| Archivos TS/TSX (frontend) | ~107 |
| Módulos backend montados | 20 de 20 |
| Endpoints API | 150+ |
| Tablas PostgreSQL | 77 |
| Smoke tests | 15 (14 passed, 1 skipped) |
| Build frontend | `npm run build` (tsc -b + vite) exit 0 |
| Pydantic warnings | 0 |
| TypeScript errors | 0 |
| Secrets en código | 0 |
| IPs internas en código | 0 |

## Seguridad

| Capa | Implementación |
|------|---------------|
| Autenticación | JWT + cookies HttpOnly + refresh tokens |
| 2FA | TOTP (Google Authenticator) |
| Sesiones | Redis, passwords cifrados con Fernet, TTL 30min |
| CORS | Parametrizado via `.env` |
| Rate limiting | Nginx: login=5/min, compose=10/min, API=30/s |
| Cabeceras | HSTS, X-Frame-Options, X-Content-Type-Options |
| Antispam | Rspamd integrado |
| Healthcheck | `/api/health` verifica API + Redis + PostgreSQL |
| Config | Defaults genéricos (example.com), valores reales en `.env` |
| Logging | Ruta configurable, fallback a stdout si falta directorio |

## Archivos de Despliegue

```
deploy/
├── webmail/
│   ├── instalar.sh                    ← Instalador automatizado
│   ├── nginx/webmail.conf             ← Nginx con rate limit, SSL, SPA
│   └── systemd/maquita-webmail.service
├── z-push/
│   ├── README.md                      ← Guía ActiveSync
│   ├── Dockerfile
│   ├── instalar.sh
│   ├── configs/                       ← 6 archivos de configuración
│   ├── nginx/activesync.conf
│   └── php-fpm/zpush.conf
```

## Cómo Reproducir Esta Verificación

```bash
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd webmailMaquita

# Frontend
cd frontend
npm ci
npm run build   # debe salir exit 0

# Backend
cd ../backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx
SECURITY_LOG_PATH=/tmp/test-security.log python -m pytest tests/ -v
# Resultado esperado: 14 passed, 1 skipped, 0 warnings
```

---

*Documento generado manualmente con verificación real contra el código del repositorio.*
*No es autogenerado por CI — los resultados aquí reflejan ejecución local en el servidor de producción.*