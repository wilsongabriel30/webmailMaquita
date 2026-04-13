# Evidencia de Producción — mail.example.org

**Sistema en producción real desde marzo 2026.**

## Datos del Entorno

| Métrica | Valor |
|---------|-------|
| **URL** | https://mail.example.org/webmail/ |
| **Dominio** | maquita.org |
| **Buzones activos** | 4 |
| **Correos almacenados** | ~48,600+ archivos Maildir |
| **Contactos** | 10,005 registros |
| **Tokens de sesión (refresh)** | 226 emitidos |
| **Destinatarios enviados** | 170 registros |
| **Calendarios creados** | 5 |
| **Certificado SSL** | Wildcard Sectigo (*.maquita.org) |
| **Requests API** | ~380/hora (uso activo) |

## Infraestructura en Producción

| Servicio | Estado |
|----------|--------|
| Postfix (SMTP) | Activo, puertos 25/587 |
| Dovecot (IMAP) | Activo, puertos 143/993 |
| PostgreSQL 17 | Activo, 77 tablas, datos reales |
| Redis 8 | Activo, sesiones cifradas |
| Nginx | Activo, SSL, rate limiting |
| Radicale (CalDAV) | Activo, puerto 5232 |
| Rspamd (antispam) | Activo |
| Maquita Webmail API | Activo, 4 workers uvicorn |

## Buzón Principal

El buzón `gestiontecnologia@maquita.org` tiene **48,453 archivos** en su Maildir, demostrando uso real continuo con volumen de correo institucional.

## Módulos con Datos Reales

- **Contactos**: 10,005 contactos almacenados
- **Auditoría admin**: 64 acciones registradas
- **Etiquetas**: 10 etiquetas personalizadas
- **Análisis de spam**: 7 análisis ejecutados
- **Firmas**: 7 cambios auditados
- **Calendarios**: 5 calendarios creados
- **Salas de reunión**: 3 configuradas
- **Preferencias de usuario**: 3 usuarios configurados

## Verificación en Vivo

```bash
# Healthcheck
$ curl -s https://mail.example.org/api/health
{"status":"healthy","checks":{"api":"ok","redis":"ok","database":"ok"}}

# SSL válido
$ echo | openssl s_client -connect mail.example.org:443 -servername mail.example.org
subject=CN=*.maquita.org
issuer=Sectigo Public Server Authentication CA DV R36
```

---

*Esto no es un entorno de prueba. Es el servidor de correo institucional de Fundación Maquita, en uso diario.*
