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
