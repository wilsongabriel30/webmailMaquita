# Guía de MFA / 2FA (TOTP) del correo

El webmail soporta segundo factor TOTP (Google Authenticator, Aegis, etc.) con
códigos de respaldo. El login ya lo aplica: si un usuario tiene 2FA activo, tras
la contraseña se le pide el código (`requires_2fa`).

## Activar 2FA (usuario)
1. Webmail → Ajustes → Seguridad → Activar verificación en dos pasos.
2. Escanear el QR con la app, confirmar un código → guarda secreto y backup codes.
   (Endpoints: `POST /api/auth/totp/setup` → `POST /api/auth/totp/verify`.)
3. Guardar los códigos de respaldo en lugar seguro.

## Ver cobertura (administración / cumplimiento)
```
maquita-mailadm mfa status        # buzones con 2FA vs total
maquita-mailadm mfa list          # quién tiene 2FA
```

## Forzar 2FA a administradores / oficiales de cumplimiento
**Recomendado** para cuentas con acceso a eDiscovery, compliance y panel admin.
Diseño de enforcement (opt-in, OFF por defecto para no bloquear despliegues):

1. Definir la lista en `backend/.env`:  `MFA_REQUIRED_USERS=alguien@dominio,otro@dominio`
2. En el login (`backend/app/auth/router.py`), tras validar la contraseña:
   si `username in MFA_REQUIRED_USERS` y `not is_totp_enabled(...)`,
   responder `{"must_setup_2fa": true, "username": ...}` (sin emitir token).
3. El frontend debe enrutar `must_setup_2fa` a la pantalla de alta de TOTP.
> No activar en producción hasta validar el paso 3 en el frontend, o se bloquea
> el login de esos usuarios. Por eso aquí se entrega la guía + visibilidad y el
> diseño; la activación se valida en staging.
