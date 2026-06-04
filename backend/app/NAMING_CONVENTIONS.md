# Convenciones de nomenclatura — Maquita Webmail Backend

## Identificación de usuario
La clave primaria de un usuario es su correo electrónico (mailbox.username).
`get_current_user()` devuelve un `str` con el email completo (ej: `usuario@maquita.org`).

Diferentes tablas usan diferentes nombres para este campo (legado):
- `mailbox.username` → email del usuario (fuente de verdad)
- `user_labels.owner` → email del usuario
- `message_labels.owner` → email del usuario
- `email_templates.owner` → email del usuario
- `snoozed_emails.owner` → email del usuario
- `scheduled_emails.username` → email del usuario
- `priority_cache.owner` → email del usuario
- `spam_analysis.owner` → email del usuario
- `user_totp.username` → email del usuario

## Convención para código nuevo
- En nuevas columnas de base de datos: usar `user_email`
- En variables Python de endpoints: `username` (consistente con get_current_user)
- En variables internas donde el contexto sea ambiguo: usar `user_email`
- Nunca usar solo `user` para un string de email (confuso con objetos User)

## Variables de sesión en Redis
- `imap_pass:{email}` → contraseña en caché para IMAP/SMTP
- `imap_master:{email}` → indica sesión master ("admin")
- `refresh:{hash}` → refresh token

## Configuración
Toda la configuración sensible está en `/opt/maquita-webmail/backend/.env`
y se carga mediante `pydantic_settings` en `app/config.py`.
