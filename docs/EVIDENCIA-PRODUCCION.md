# Evidencia de Produccion — Fundacion Maquita Webmail

**Sistema en produccion real desde marzo 2026.**

## Datos del Entorno

| Metrica | Valor |
|---------|-------|
| **Buzones activos** | 4+ |
| **Correos almacenados** | ~48,600+ archivos Maildir |
| **Contactos** | 10,005 registros |
| **Tokens de sesion (refresh)** | 226 emitidos |
| **Destinatarios enviados** | 170 registros |
| **Calendarios creados** | 5 |
| **Requests API** | ~380/hora (uso activo) |

## Infraestructura en Produccion

| Servicio | Estado |
|----------|--------|
| Postfix (SMTP) | Activo, puertos 25/587 |
| Dovecot (IMAP) | Activo, puertos 143/993 |
| PostgreSQL 17 | Activo, 77+ tablas, datos reales |
| Redis 8 | Activo, sesiones cifradas |
| Nginx | Activo, SSL, rate limiting |
| Radicale (CalDAV) | Activo |
| Rspamd (antispam) | Activo, reglas internas |
| Maquita Webmail API | Activo, 4 workers uvicorn |

## Modulos con Datos Reales

- **Contactos**: 10,005 contactos almacenados
- **Auditoria admin**: 64+ acciones registradas
- **Etiquetas**: 10 etiquetas personalizadas
- **Analisis de spam**: reglas internas activas
- **Calendarios**: 5 calendarios creados
- **Salas de reunion**: 3 configuradas
- **Preferencias de usuario**: multiples usuarios configurados

## Verificacion

Para verificar tu propia instalacion:

```bash
# Healthcheck
curl -s http://localhost:8000/api/auth/health
# Debe responder: {"status":"healthy",...}

# Servicios activos
systemctl status postfix dovecot rspamd nginx maquita-webmail
```

---

*Fundacion Maquita — Tecnologia al servicio de todos, no solo de quienes pueden pagarla.*
