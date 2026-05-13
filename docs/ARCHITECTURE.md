# Arquitectura — Fundacion Maquita Webmail

> **Proyecto de la Fundacion Maquita** — Comercializadora asociativa sin fines de lucro, Ecuador.

---

## Vision general

Sistema modular de correo electronico con interfaz web. Cada componente tiene una responsabilidad clara y se comunica via APIs internas o protocolos estandar.

```
                    ┌─────────────────────────────────┐
                    │           INTERNET               │
                    └──────────┬──────────────────────┘
                               │
                    ┌──────────▼──────────────────────┐
                    │         NGINX (443/80)           │
                    │   Reverse proxy + TLS + Headers  │
                    └──┬───────────────┬──────────────┘
                       │               │
            ┌──────────▼───┐    ┌──────▼──────────────┐
            │  Frontend    │    │  Backend API (:8000) │
            │  React/TS    │    │  FastAPI/Python      │
            │  (static)    │    │                      │
            └──────────────┘    └──┬──┬──┬──┬─────────┘
                                   │  │  │  │
                    ┌──────────────┘  │  │  └──────────────┐
                    │                 │  │                  │
             ┌──────▼─────┐   ┌──────▼──▼───┐    ┌────────▼───────┐
             │ PostgreSQL  │   │   Dovecot   │    │    Redis       │
             │ (datos)     │   │   (IMAP)    │    │    (cache)     │
             └─────────────┘   └──────┬──────┘    └────────────────┘
                                      │
                               ┌──────▼──────┐
                               │   Postfix   │
                               │   (SMTP)    │
                               └──┬───────┬──┘
                                  │       │
                           ┌──────▼──┐  ┌─▼──────────┐
                           │ Rspamd  │  │ Filtro     │
                           │ (score) │  │ Python     │
                           └─────────┘  └────────────┘
```

## Modulos del backend

El backend esta organizado en modulos independientes, cada uno con su propio router, servicios y modelos:

| Modulo | Directorio | Responsabilidad |
|--------|-----------|-----------------|
| **Auth** | `app/auth/` | Login JWT, refresh tokens, 2FA/TOTP |
| **Mail** | `app/mail/` | IMAP client, MIME parser, SMTP compose, threads |
| **Admin** | `app/admin/` | Dashboard, gestion de dominios/buzones, eDiscovery, auditoria, anti-spam |
| **Calendar** | `app/calendar/` | CalDAV con Radicale, eventos, invitaciones ICS |
| **Contacts** | `app/contacts/` | CardDAV, CRUD, importar/exportar vCard/CSV |
| **Tasks** | `app/tasks/` | Kanban boards, listas, tarjetas, recurrencia |
| **AI** | `app/ai/` | Proxy a gateway IA, respuestas inteligentes, autocompletado |
| **Settings** | `app/settings/` | Preferencias de usuario, firmas, identidades |
| **Sieve** | `app/sieve/` | Reglas de correo (ManageSieve) |
| **Security** | `app/security/` | S/MIME, anti-compromiso, blindaje MIME |
| **SSO** | `app/sso/` | Single Sign-On |
| **Core** | `app/core/` | DB, Redis, sesion, sanitizacion, utilidades compartidas |

### Principios de diseno

1. **Cada modulo es un router FastAPI** — se monta en `main.py` con prefix `/api/`
2. **Sin dependencias circulares** — los modulos solo importan de `core/`
3. **Servicios separados de routers** — logica de negocio en `services/`, endpoints en `routers/`
4. **Validacion en fronteras** — Pydantic schemas para input/output de API

## Modulos del frontend

| Modulo | Directorio | Responsabilidad |
|--------|-----------|-----------------|
| **Mail** | `components/mail/` | MailView, MessageList, SafeEmailViewer, threads |
| **Compose** | `components/compose/` | Editor TipTap, adjuntos, firma HTML |
| **Admin** | `components/admin/` | Dashboard, buzones, dominios, anti-spam, eDiscovery |
| **Calendar** | `components/calendar/` | Vistas mes/semana/dia, eventos, invitaciones |
| **Contacts** | `components/contacts/` | CRUD, categorias, importar/exportar |
| **Tasks** | `components/tasks/` | Kanban, listas, tarjetas |
| **Auth** | `components/auth/` | Login, 2FA |
| **Settings** | `components/settings/` | Preferencias, firmas, reglas de correo |
| **Layout** | `components/layout/` | NavRail, Topbar, Sidebar |

### Estado global

- **Zustand** para estado global (store/)
- **React Query** para cache de datos del servidor
- **Custom hooks** para shortcuts, presencia, websocket

## Estructura de la base de datos

**84 tablas** en PostgreSQL, organizadas por modulo:

| Modulo | Tablas principales |
|--------|-------------------|
| **Correo** | `mailbox`, `domain`, `alias`, `user_labels`, `message_labels`, `snoozed_emails`, `scheduled_emails` |
| **Calendario** | `calendars`, `events`, `event_invitations`, `calendar_shares`, `meeting_rooms` |
| **Contactos** | `user_contacts`, `org_contacts`, `contact_categories`, `contact_lists` |
| **Tareas** | `task_boards`, `task_lists`, `task_cards`, `task_labels`, `task_activity` |
| **Admin** | `admin_users`, `admin_sessions`, `admin_audit`, `branding_settings` |
| **Seguridad** | `user_totp`, `smime_certificates`, `api_keys`, `sso_config`, `spam_analysis` |
| **Otros** | `user_preferences`, `user_signatures`, `email_templates`, `webhooks` |

Las tablas se crean automaticamente al iniciar el backend por primera vez (SQLAlchemy).

## Puertos utilizados

| Puerto | Servicio | Acceso |
|--------|----------|--------|
| 25 | Postfix SMTP | Publico |
| 80 | Nginx HTTP (redirect a HTTPS) | Publico |
| 143 | Dovecot IMAP | Local |
| 443 | Nginx HTTPS | Publico |
| 587 | Postfix Submission | Publico |
| 993 | Dovecot IMAPS | Publico |
| 4190 | ManageSieve | Local |
| 5232 | Radicale CalDAV/CardDAV | Local |
| 5432 | PostgreSQL | Local |
| 6379 | Redis | Local |
| 8000 | Webmail API (FastAPI) | Local |
| 10025 | Postfix reinyeccion (filtro) | Local |
| 11332 | Rspamd milter | Local |
| 11334 | Rspamd Web UI | Local |

## Stack tecnologico

| Componente | Tecnologia | Version |
|------------|-----------|---------|
| Frontend | React + TypeScript + Vite | React 19, Vite 6 |
| Backend | FastAPI + Uvicorn | FastAPI 0.115 |
| Base de datos | PostgreSQL | 17+ |
| Cache | Redis | 7+ |
| SMTP | Postfix | 3.7+ |
| IMAP | Dovecot | 2.4+ |
| Antispam | Rspamd | 3.8+ |
| Antivirus | ClamAV | 1.0+ |
| Proxy | Nginx | 1.22+ |
| CalDAV/CardDAV | Radicale | 3.0+ |
| SSL | Let's Encrypt / Certbot | - |
| Busqueda | FTS Xapian | Integrado en Dovecot |
| IA (opcional) | Ollama + FastAPI Gateway | Ollama 0.6+ |
| SO | Debian 12+ o Ubuntu 22.04+ | - |

## Flujo de un correo entrante

```
1. Llega por SMTP (puerto 25)
2. Postfix lo recibe
3. Rspamd lo analiza (scoring interno, DKIM, SPF)
4. Filtro Python lo analiza (keywords, heuristicas, blacklists)
5. Se agrega header X-Maquita-Spam: YES/NO
6. Postfix lo entrega a Dovecot via LMTP
7. Sieve global revisa el header → Inbox o Junk
8. Dovecot lo guarda cifrado y comprimido en /var/vmail/
9. El usuario lo ve en el webmail
```

## Flujo de un correo saliente

```
1. Usuario compone en el webmail
2. Frontend envia al backend (POST /api/compose/send)
3. Backend se conecta a Postfix via SMTP (puerto 587)
4. Postfix firma con DKIM
5. Postfix envia al servidor destino
```

---

*Fundacion Maquita — Tecnologia al servicio de todos, no solo de quienes pueden pagarla.*
