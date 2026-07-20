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
