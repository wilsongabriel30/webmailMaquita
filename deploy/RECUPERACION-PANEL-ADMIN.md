# Recuperación de acceso al PANEL ADMIN por correo alternativo

Si un administrador pierde el acceso al panel (olvida su contraseña o queda bloqueado por
intentos fallidos), puede recuperarlo con un **correo alternativo** (Gmail, Hotmail, etc.)
que él mismo registra y verifica. Es exclusivo del panel administrativo.

## Cómo funciona

1. **Registrar el correo** — El administrador, ya con sesión, va a **Configuración →
   "Correo de recuperación del panel"**, ingresa su correo externo y recibe un **código OTP
   de 6 dígitos** (vence en 15 minutos). Al ingresarlo, el correo queda verificado y activo.

2. **Recuperar el acceso** — En la pantalla de login hay un enlace
   **"Perdí el acceso — Recuperar con correo alternativo"**:
   - Ingresa su usuario → se envía un **token** (un solo uso, vence en 30 minutos) al correo
     alternativo registrado.
   - Pega el token y define una nueva contraseña. Se limpian los intentos fallidos y el
     bloqueo, y la cuenta queda lista para iniciar sesión.

3. **Límite** — Máximo **5 recuperaciones por año**. Superado, ya no se envía token; se
   desbloquea por consola (ver abajo).

## Seguridad
- Las respuestas de solicitud/recuperación son siempre genéricas: no revelan si un usuario
  existe ni si tiene recuperación configurada (sin enumeración).
- Token de un solo uso; el OTP y el token se guardan solo como hash (SHA-256).
- El reset invalida la contraseña anterior.

## Comando de consola: `maquita-admin-recovery`

Se instala en `/usr/local/sbin/maquita-admin-recovery` (en el servidor). Uso:

```
maquita-admin-recovery status <admin>          # ver correo de recuperación y usos del año
maquita-admin-recovery reset-counter <admin>   # poner los usos del año a 0 (tras superar el límite de 5)
maquita-admin-recovery unlock <admin>          # limpiar el bloqueo de login (intentos/tiempo) y reactivar
maquita-admin-recovery clear <admin>           # eliminar el correo de recuperación (des-registrar)
```

Ejemplo — un administrador agotó sus 5 recuperaciones del año y necesita otra:
```
maquita-admin-recovery reset-counter admin
```

## Componentes
- Tabla `admin_recovery` (correo, verificado, hashes de OTP/token, usos por año).
- Backend admin: `app/admin_recovery/router.py` (endpoints /status, /register, /verify,
  /request, /reset). Contraseñas con bcrypt.
- Frontend: `components/AdminRecoveryCard.tsx` (registro) y flujo de recuperación en
  `pages/Login.tsx`.
- Consola: `/usr/local/sbin/maquita-admin-recovery` (lee credenciales del entorno del
  servidor; no lleva secretos en el repo).
