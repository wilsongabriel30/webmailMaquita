# Changelog — Fundación Maquita Webmail

## v0.1-beta (2026-04-12)

Primera versión pública. Beta endurecida tras dos rondas de auditoría técnica.

### Funciona y está verificado

- **Correo**: lectura, redacción, responder, reenviar, adjuntos, búsqueda, etiquetas, carpetas
- **Composición**: editor TipTap con tablas, imágenes, firmas HTML, plantillas, dictado por voz
- **Calendario**: vistas mes/semana/día/agenda, eventos, invitaciones (CalDAV vía Radicale)
- **Contactos**: CRUD, categorías, favoritos, listas, importar/exportar vCard/CSV (CardDAV)
- **Tareas**: tableros kanban, recordatorios, recurrencia, emails marcados como tareas
- **Admin**: dashboard, dominios, buzones, aliases, auditoría
- **Seguridad**: JWT + HttpOnly cookies, 2FA/TOTP, passwords cifrados en Redis (Fernet), rate limiting
- **Despliegue**: instalador automatizado, Nginx, systemd, GitHub Actions CI
- **ActiveSync**: Z-Push configurado para Android/iOS/Outlook
- **PWA**: Service Worker, manifest, funcionamiento offline parcial
- **Build**: `npm ci` + `npm run build` pasan limpio (0 errores TS, 0 warnings Pydantic)
- **Tests**: 14 passed, 1 skipped, 0 warnings
- **Healthcheck**: `/api/health` verifica API + Redis + PostgreSQL

### Limitaciones conocidas (honesto)

- **No probado en otro servidor** — solo verificado en el entorno de desarrollo/producción original
- **Sin tests E2E de UI** — no hay Playwright/Cypress; los smoke tests son solo de API
- **Sin tests de IMAP/SMTP real** — los tests no conectan a Dovecot/Postfix
- **Sin pruebas de carga** — no sabemos cuántos usuarios simultáneos aguanta
- **Sin pruebas de reconexión WebSocket** — comportamiento bajo cortes de red no verificado
- **Chunks frontend >500KB** — funciona pero podría optimizarse con code splitting
- **El test `test_login_invalid_credentials` se salta** — requiere Redis activo en entorno de test
- **Módulos `security` y `ai` tienen TODOs menores** — funcionales pero incompletos

### Requisitos

- Debian 12/13 o Ubuntu 22.04+
- Postfix + Dovecot + PostgreSQL 14+ + Redis 6+ + Nginx + Radicale 3+
- Python 3.11+ / Node.js 18+
- Certificado SSL (Let's Encrypt o wildcard)

### Cómo verificar

```bash
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd webmailMaquita

# Frontend
cd frontend && npm ci && npm run build

# Backend
cd ../backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt pytest pytest-asyncio httpx
python -m pytest tests/ -v
```
