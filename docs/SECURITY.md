# Seguridad — Fundacion Maquita Webmail

> **Proyecto de la Fundacion Maquita** — Comercializadora asociativa sin fines de lucro, Ecuador.
> Si detectas un uso indebido de esta herramienta, reportalo a los mantenedores del proyecto.

Medidas de seguridad implementadas en el sistema. Este documento describe las practicas de hardening aplicadas. Se recomienda realizar auditorias periodicas en entornos de produccion.

---

## Autenticacion y sesiones

- **JWT + cookies HttpOnly/Secure/SameSite** — los tokens no son accesibles desde JavaScript
- **2FA/TOTP** — autenticacion de dos factores con apps como Google Authenticator
- **Rate limiting por endpoint** — proteccion contra fuerza bruta (configurable en Nginx)
- **Sesiones en Redis** con TTL automatico
- **Passwords cifrados** — BLF-CRYPT para buzones, Fernet para credenciales en cache

## Cifrado

- **TLS en transito** — todo el trafico usa HTTPS (Let's Encrypt / Certbot)
- **Cifrado de emails en disco** — mail_crypt con curva secp521r1 (Dovecot)
- **Compresion de emails** — gzip en almacenamiento (ahorra ~60% disco)
- **Certificados S/MIME** — firma y cifrado de correos individuales

## Proteccion de correo (autenticacion de dominio)

- **SPF** — solo IPs autorizadas pueden enviar correo desde tu dominio
- **DKIM** — cada correo lleva firma criptografica verificable
- **DMARC (reject)** — correos sin SPF/DKIM son rechazados por servidores receptores
- **MTA-STS (enforce)** — fuerza TLS en conexiones SMTP entrantes
- **DANE** — vincula certificados TLS al DNS (requiere DNSSEC)

## Sistema anti-spam interno

El sistema usa un enfoque de **reputacion interna** (similar a como un banco evalua transacciones):

- **Rspamd** con reglas propias de scoring (no depende de listas externas DNSBL)
- **Filtro Python** con 10 heuristicas avanzadas y scoring por capas
- **Listas negras/grises internas** gestionables desde el panel admin
- **ClamAV** para escaneo de virus en adjuntos
- **Principio fundamental: nunca rechazar correos** — solo clasificar (Inbox o Junk via Sieve)

### Capas de analisis

| Capa | Que analiza | Scoring |
|------|------------|---------|
| Blacklist IP | IPs conocidas de spam | +8 puntos |
| Blacklist dominio | Dominios spam/phishing | +10 puntos |
| Greylist dominio | Dominios sospechosos | +4 puntos |
| Keywords | Palabras tipicas de spam | +1 a +3 puntos |
| Heuristicas | Links, adjuntos, DKIM, Reply-To, etc. | +1 a +5 puntos |
| Whitelist | Remitentes confiables | Exento |

> **Threshold:** score >= 3 = clasificado como spam (va a Junk, nunca se pierde)

## Headers de seguridad (Nginx)

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Content-Security-Policy: default-src 'self'; ...
Referrer-Policy: strict-origin-when-cross-origin
```

## Sanitizacion

- **SafeEmailViewer** — sanitiza HTML de correos para prevenir XSS
- **Validacion MIME** al arranque del backend
- **Input validation** en todos los endpoints API

## Panel de administracion

- Acceso restringido a usuarios admin
- **Audit log** de todas las acciones administrativas
- **eDiscovery** para busqueda forense (solo admin)
- **Impersonacion** con registro en auditoria

## Recomendaciones para produccion

1. **Mantener actualizado** — `apt update && apt upgrade` regularmente
2. **Firewall estricto** — solo abrir puertos necesarios (25, 80, 443, 587, 993)
3. **Monitoreo de logs** — revisar `/var/log/mail.log` y journalctl periodicamente
4. **Backups automatizados** — `pg_dump` + tar de /var/vmail con cron
5. **Auditorias de seguridad** — pentesting periodico para sistemas en produccion
6. **Fail2Ban** — bloquear IPs con intentos fallidos de login
7. **Actualizaciones de ClamAV** — `freshclam` corre automaticamente via timer
8. **Certificados SSL** — Let's Encrypt renueva automaticamente

## Reportar vulnerabilidades

Si encuentras una vulnerabilidad de seguridad, contacta directamente al equipo de desarrollo de la Fundacion Maquita. **No publiques detalles en issues publicos.**

---

*Fundacion Maquita — Tecnologia al servicio de todos, no solo de quienes pueden pagarla.*
