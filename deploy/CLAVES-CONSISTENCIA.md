# Consistencia de contraseñas (fuente única) — que el desync no vuelva

## Fuente ÚNICA de autenticación
Dovecot autentica SOLO contra la tabla `mailbox` (passdb SQL):
`SELECT username, password FROM mailbox WHERE username=... AND active=true` (scheme SHA512-CRYPT).
No hay segunda passdb por usuario (`auth-master` es solo para impersonación del webmail).

## Las dos rutas de cambio escriben en esa MISMA fuente + invalidan la sesión
- Usuario (webmail) `auth/password.py change_password`: UPDATE mailbox + actualiza el caché Redis
  `imap_pass` + reverifica IMAP.
- Admin (panel) `admin/mailboxes_service.update_mailbox`: UPDATE mailbox; el router AHORA invalida
  `imap_pass`/`imap_master` del usuario en Redis (antes no, y la sesión activa quedaba con la clave
  vieja cacheada = el desync detectado en el tenant en producción). Con PR de auth también reverifica IMAP.

`imap_pass` NO es una fuente de auth: es el caché de sesión del webmail para hablarle a IMAP. Si no se
invalida tras un cambio de clave del admin, la sesión activa sigue usando la clave vieja → "no puede entrar".

## Auditoría de claves (seguridad de migración)
Panel → "Cuentas sin clave válida" (`GET /api/admin/password-audit`): lista buzones con clave vacía,
en texto plano, o formato roto. Hoy: 488 cuentas, todas válidas.

## Reseteo (individual o masivo)
- Panel: botón "Resetear clave temporal" por cuenta → clave fuerte mostrada una vez, verifica IMAP,
  invalida la sesión. Comunicarla al usuario; la cambia desde el webmail.
- Masivo (CLI): por cada cuenta marcada,
  `maquita-mailadm mailbox passwd <email> '<clave>'` y comunicar. El importador debe correr el audit al
  final y NO dejar buzones sin clave válida en silencio.
