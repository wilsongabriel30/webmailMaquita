# Proteccion de salida (anti cuenta comprometida)

Leccion del incidente Zimbra: una cuenta robada puede mandar spam masivo y quemar la
reputacion de la IP. Capas:

1. **Limite por usuario** (rspamd `ratelimit` bucket `per_user_out`, selector `user`):
   solo afecta correo saliente AUTENTICADO; al exceder -> DEFER. Config:
   `deploy/webmail/configs/rspamd-ratelimit.conf` -> `/etc/rspamd/local.d/ratelimit.conf`.
   Whitelist de bulk legitimo: `/etc/rspamd/maps.d/ratelimit_whitelist.map` (lectura en caliente).
2. **Contencion** `maquita-contener lock|unlock|status <email>`: desactiva la cuenta,
   borra su sesion en Redis (revoca cred SMTP cacheada) y vacia su cola.
3. **Panel** (:8443 -> "Proteccion de salida"): ver/ajustar limite y whitelist, ver volumen
   por remitente, y boton Contener. El backend llama al helper privilegiado.

## Privilegios
El backend corre como `www-data`. El unico acceso privilegiado es el helper
`/usr/local/sbin/maquita-outbound` (sudoers `deploy/webmail/configs/sudoers-maquita-outbound`,
NOPASSWD solo para ese binario), que valida estrictamente sus argumentos. No se da sudo
amplio ni escritura directa a `/etc/rspamd`.

## Endpoints
`/api/admin/outbound/limits` (GET/PUT), `/api/admin/outbound/activity` (GET),
`/api/admin/outbound/lock` y `/unlock` (POST). Todos `require_admin`.

---

## 4. Detección automática de envío masivo (cuenta comprometida)

Un detector corre por cron cada 2 minutos (`maquita-anomalia-salida.py`) y analiza el log
de correo: cuenta los destinatarios por cuenta autenticada dentro de una ventana. Si una
cuenta supera el umbral (el correo institucional envía pocos al día; un envío masivo en
minutos es señal de cuenta robada):

- **Notifica** al administrador y al usuario (aviso: cambiar contraseña + activar 2FA).
- **Contiene** la cuenta (`maquita-contener lock`) antes de que la IP caiga en listas negras.
- Registra el evento en `outbound_anomaly_events` y en `fraud_alerts` (dashboard de amenazas).
- Respeta *legal holds* y no re-bloquea si ya hay un evento reciente.

Administrable desde el panel (**Protección de salida**): activar/desactivar, umbral,
ventana, acción (bloquear o solo alertar) y correo de aviso, más la tabla de detecciones.

Config en la tabla `outbound_anomaly_config` (por defecto: 30 destinatarios / 10 min / lock).

**Mensaje en el login:** si una cuenta fue contenida, al intentar entrar al webmail el
usuario ve el motivo e instrucciones (cambiar clave, activar 2FA) en vez del genérico.

### Comandos de consola relacionados
```
maquita-contener lock|unlock|status <email>   # contener / recuperar una cuenta de USUARIO
```
El detector (`/usr/local/sbin/maquita-anomalia-salida.py`) y el helper del panel
(`/usr/local/sbin/maquita-outbound`) se instalan en el servidor; leen su configuración de
la base de datos y del `.env` del backend (no llevan credenciales embebidas en el repo).

---

## Prueba real de filtros de salida y ajustes para Raíces Nómina (2026-09-03)

Desde la sesión de Nómina de Raíces se probó en real el filtrado de salida enviando **72
correos** desde la VM 101 (193.16.0.153) con una cuenta de sistema. **Los cuatro mecanismos
frenaron el envío** (ratelimit, contención/detector de anomalías, DLP y el límite de eventos
por IP de Postfix): la prueba fue un éxito. A raíz de eso se ajustó la VM 130 para que el
correo legítimo de Raíces (rol de pago con la cédula del propio trabajador + aviso de
depósito) SÍ salga, sin abrir la mano a otros remitentes. Respaldos `.bak.20260903*`.

### Los 7 cambios aplicados

1. **Buzón de sistema `noreply@maquita.org`** ("Raíces Nómina (no responder)", cuota 1 GB,
   `active=t`, hash SHA512-CRYPT vía `doveadm pw`, con alias a sí mismo). Autentica por 587
   STARTTLS; el `From` debe ser la misma cuenta por `reject_sender_login_mismatch`. Clave en
   `CREDENCIALES-CAJA-FUERTE.md` y en BD `nomina` (`nomina_correo_config`). Buzón en BD `maildb`
   (tabla `mailbox`), NO en `mailserver` ni `postfixadmin`.

2. **Panel admin "Protección de salida" — dos fallas de origen corregidas:**
   - (a) La casilla "Cuentas exentas" escribía por error en
     `/etc/rspamd/local.d/maps/whitelist_senders.map` (whitelist de remitentes **ENTRANTES**,
     −10 puntos → riesgo de suplantación). Ahora escribe en el mapa correcto,
     `/etc/rspamd/maps.d/ratelimit_whitelist.map` (el que usan el ratelimit, `settings.conf` y
     el detector de anomalías).
   - (b) `www-data` no tenía sudo sobre el helper y "Guardar y aplicar" fallaba. Se creó
     `/etc/sudoers.d/maquita-outbound` (`www-data ALL=(root) NOPASSWD: /usr/local/sbin/maquita-outbound`);
     el helper quedó `root:root 755`. Se agregó la subacción `set-dlp-exempt` →
     `/etc/maquita-mail/dlp-exempt-senders.txt` y `get-limits` ahora devuelve `whitelist` y
     `dlp_exempt`. Backend: `backend/app/admin/outbound_service.py` y `.../router.py` aceptan
     `dlp_exempt` (rutas separadas). Frontend: `admin-panel/frontend/src/pages/OutboundProtection.tsx`
     con la segunda casilla; `npm run build` hecho (`dist.bak.20260903`). `maquita-webmail` reiniciado.

3. **rspamd `local.d/ratelimit.conf`:** `whitelisted_user = "/etc/rspamd/maps.d/ratelimit_whitelist.map"`
   para eximir de todos los buckets. Recargado.

4. **Detector de anomalías** `/usr/local/sbin/maquita-anomalia-salida.py`: lee la misma lista de
   exentos (`ratelimit_whitelist.map`) y salta esas cuentas. Corre por cron cada 2 min
   (`/etc/cron.d/maquita-anomalia`); no es un servicio persistente.

5. **Milter DLP** `/opt/maquita-webmail/milter/dlp_outbound.py`: función `_exempt_senders()` que
   lee `/etc/maquita-mail/dlp-exempt-senders.txt` en cada mensaje; si el remitente está ahí,
   agrega la cabecera `X-DLP-Exempt` y **no inspecciona**. Motivo: el rol de pago lleva la
   cédula del propio destinatario y el DLP lo rechazaba con 554. `maquita-milter` reiniciado.

6. **Postfix `main.cf`:** `smtpd_client_event_limit_exceptions = $mynetworks, 193.16.0.153/32`
   (el límite de 50 mensajes/hora por IP frenaba a Raíces). Recargado.

7. **Listas de exentos:** ambas contienen SOLO `noreply@maquita.org`. La whitelist de
   remitentes ENTRANTES (`whitelist_senders.map`) quedó **vacía** de cuentas nuestras (correcto).

### Rutas de los dos mapas y la lista de exentos
- Exentos de **ratelimit + settings + detector**: `/etc/rspamd/maps.d/ratelimit_whitelist.map`
- Exentos de **DLP de salida**: `/etc/maquita-mail/dlp-exempt-senders.txt`
- Whitelist de remitentes **ENTRANTES** (NO poner cuentas propias): `/etc/rspamd/local.d/maps/whitelist_senders.map`

### Recomendación operativa (importante)
**Mantener las listas de exentos al mínimo.** Hoy solo `noreply@maquita.org` (cuenta de sistema
que solo usa Raíces). Si una persona debe escribir a todo el personal, agregarla **solo ese
rato** y **quitarla después**. Nunca dejar cuentas de usuarios humanos exentas del DLP ni del
ratelimit de forma permanente.

### Nota de diseño — exención DLP por remitente
La exención DLP es **por remitente** (salta la inspección completa para `noreply@`). El milter SÍ
conoce los destinatarios (`st["rcpts"]`) y evalúa "externo", pero **no** conoce el
`email_personal`/`email_other` de cada trabajador (eso vive en la BD `nomina`, VM 132; el milter
solo tiene el pool de `maildb`), así que hoy no puede acotar la exención a "solo cuando el
destinatario es el correo personal del propio trabajador". Es aceptable como está por los
controles que la rodean (buzón de sistema, `reject_sender_login_mismatch`, uso exclusivo de
Raíces, lista mínima), pero el endurecimiento natural sería que Raíces/el milter validen que el
destinatario sea el correo registrado del trabajador antes de eximir. Ver la sesión del día.
