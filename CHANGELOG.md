# Changelog — Fundacion Maquita Webmail

## v0.2-beta (2026-05-12)

Segunda version beta con auditorias de seguridad, optimizaciones de rendimiento y nuevas funcionalidades.

### Nuevas funcionalidades
- **Invitaciones de calendario ICS** estilo Outlook (Aceptar/Tentativo/Rechazar con RSVP)
- **eDiscovery** — busqueda forense en buzones desde panel admin
- **Modulo branding** — personalizacion visual del webmail
- **SafeEmailViewer** — visualizacion segura de correos con sanitizacion XSS
- **Pool de conexiones IMAP** — reutilizacion de conexiones para mejor rendimiento
- **Filtro anti-spam Python** — clasificacion por keywords configurable sin rechazar correos
- **Boton agregar contacto** desde correos recibidos
- **Script zimbra-sync.sh** para migracion desde Zimbra

### Seguridad
- Auditoria externa: 15 hallazgos, 14 corregidos (86/100 comparable a Gmail 87/100)
- Rate limiting post-autenticacion
- Login timing reducido de 7s a 2s
- POP3 deshabilitado, VRFY/ETRN deshabilitados
- BIMI configurado
- MTA-STS enforce activo
- Password complexity enforced
- Proteccion anti-compromiso de cuentas
- Blindaje anti-spam MIME con validacion al arranque y 32 tests permanentes
- Sanitizacion HTML con nh3 (backend) y DOMPurify (frontend)
- Fix CRLF injection en headers
- ClamAV cambiado de reject a add_header (no perder correos con virus, marcar)

### Rendimiento
- FTS Xapian optimizado: 4 threads, 256MB memoria, idioma espanol
- Cache Redis para UIDs de carpeta Sent (fix timeout 502)
- Invalidacion de cache tras leer/mover/borrar correos
- Gzip habilitado en nginx
- Service Worker bumped v21 a v22

### Correcciones
- Fix carpeta Sent con 502/timeout (>25s) — resuelto con cache Redis
- Fix contadores de no leidos desincronizados
- Fix auto-guardado de borradores no preservaba subject
- Fix busqueda de contactos retornaba 0 resultados (ahora busca en org_contacts)
- Fix TypeError charAt en calendario al abrir evento con asistentes
- Fix TypeError charAt en mensajes sin campo From
- Fix calendario no cargaba eventos al refrescar pagina
- Fix errores consola 404 por cache viejo del Service Worker

### Infraestructura
- DNSBL: removido zen.spamhaus.org (falsos positivos desde datacenter sin suscripcion)
- Postfix configurado para nunca rechazar correos (todo pasa al filtro interno)
- Rspamd: deshabilitadas listas que requieren suscripcion paga (SURBL, URIBL, Spamhaus)
- Whitelist de dominios grandes (Gmail, Outlook, Yahoo) en Rspamd
- 84 tablas en PostgreSQL (antes 77)

### Estadisticas
- 89 archivos cambiados, +3,226 / -674 lineas
- 48,000+ emails en produccion
- 13 buzones activos

---

## v0.1-beta (2026-04-12)

Primera version publica. Beta endurecida tras dos rondas de auditoria tecnica.

### Funciona y esta verificado

- **Correo**: lectura, redaccion, responder, reenviar, adjuntos, busqueda, etiquetas, carpetas
- **Composicion**: editor TipTap con tablas, imagenes, firmas HTML, plantillas, dictado por voz
- **Calendario**: vistas mes/semana/dia/agenda, eventos, invitaciones (CalDAV via Radicale)
- **Contactos**: CRUD, categorias, favoritos, listas, importar/exportar vCard/CSV (CardDAV)
- **Tareas**: tableros kanban, recordatorios, recurrencia, emails marcados como tareas
- **Admin**: dashboard, dominios, buzones, aliases, auditoria
- **Seguridad**: JWT + HttpOnly cookies, 2FA/TOTP, passwords cifrados en Redis (Fernet), rate limiting
- **Despliegue**: instalador automatizado, Nginx, systemd, GitHub Actions CI
- **ActiveSync**: Z-Push configurado para Android/iOS/Outlook
- **PWA**: Service Worker, manifest, funcionamiento offline parcial
- **Build**: `npm ci` + `npm run build` pasan limpio (0 errores TS, 0 warnings Pydantic)
- **Tests**: 14 passed, 1 skipped, 0 warnings
- **Healthcheck**: `/api/health` verifica API + Redis + PostgreSQL

### Limitaciones conocidas

- Sin tests E2E de UI (no hay Playwright/Cypress)
- Sin tests de IMAP/SMTP real
- Sin pruebas de carga
- Chunks frontend >500KB (optimizable con code splitting)
