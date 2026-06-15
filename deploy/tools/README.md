# maquita-mailadm — CLI de administración del correo

Herramienta de consola inspirada en `zmprov`/`zmcontrol` de Zimbra, adaptada a
nuestro stack (Postfix/Dovecot/PostgreSQL). Gestiona cuentas y servicios sin
tocar la base de datos a mano. Todas las acciones quedan en
`/var/log/maquita-mailadm.log` (actor + timestamp + acción + target).

## Instalación
```bash
cp maquita-mailadm /usr/local/sbin/maquita-mailadm
chmod 750 /usr/local/sbin/maquita-mailadm   # solo root
```
Requisitos: PostgreSQL local (`maildb`), `doveadm`, `python3-bcrypt`.

## Comandos (y su equivalente en Zimbra)
### Buzones — `zmprov`
```
mailbox create  <email> [quota_GB] [password]   # createAccount (ca)
mailbox delete  <email>                         # deleteAccount (da) — pide confirmación
mailbox passwd  <email> [nueva]                 # setAccountPassword (sp)
mailbox quota   <email> <GB>                    # modifyAccount zimbraMailQuota (0=ilimitado)
mailbox enable|disable <email>                  # activar/desactivar
mailbox info    <email>                         # getAccount (ga)
mailbox list    [dominio]                       # getAllAccounts (gaa)
```
### Alias y reenvío — `zmprov` / forwarding
```
alias create <alias> <destino>        # crear alias (correo a <alias> -> <destino>)
alias delete <alias>                  # borrar alias (protege buzones reales)
alias list   [dominio]                # listar alias y reenvíos
forward set  <buzon> <destino> [keep] # reenviar buzón; 'keep' conserva copia local
forward off  <buzon>                  # desactivar reenvío (entrega local)
forward list                          # buzones con reenvío activo
```
### Autorespuesta / vacaciones — Sieve vacation
```
autoresponder set  <email> <asunto> <mensaje> [dias] [desde] [hasta]  # activar (Sieve)
#   fechas AAAA-MM-DD opcionales: solo responde dentro del rango
autoresponder off  <email>                             # desactivar
autoresponder show <email> | list                      # consultar
```
### Cola / Seguridad / Dominios
```
queue list | flush | delete-all        # gestión de la cola (postqueue/postsuper)
fail2ban status | unban <ip>           # ver baneos / desbanear IP
domain list                            # listar dominios
```
> Guía completa con recetas de uso: ver GUIA-COMANDOS.md

### Panel admin (https://mail.example.org:8443)
```
admin passwd <usuario> [nueva]   # resetear contraseña (desbloquea de paso)
admin unlock <usuario>           # desbloquear (tras 5 intentos fallidos -> 15 min)
admin list                       # listar admins y estado
```
### Servicios — `zmcontrol`
```
service status                   # estado de todos los servicios del correo
service restart <servicio>       # reiniciar (whitelist del stack)
service reload  <servicio>       # recargar
```
Servicios permitidos: postfix, dovecot, rspamd, redis-server, nginx,
clamav-daemon, maquita-webmail, maquita-admin, fail2ban, postgresql@17-main.

## Notas de seguridad
- Solo root. Contraseña oculta si se omite (no queda en el history); el texto
  plano nunca toca el SQL (se hashea con `doveadm`/`bcrypt` antes).
- `mailbox delete` pide confirmación y **NO borra el maildir físico**
  (`/var/vmail/<dominio>/<local>/`) — eliminar a mano si se desea, para evitar
  pérdida accidental de datos.
- `mailbox create` exige que el dominio exista (`domain`) y crea el self-alias.
  El maildir lo crea Dovecot al primer correo.
- `service restart/reload` solo opera sobre la whitelist.
- Los buzones no tienen lockout de cuenta (se protegen por fail2ban/IP).

## Esquema (referencia)
| Cuenta | Tabla | Hash | Lockout |
|---|---|---|---|
| Buzón | `mailbox` (`password`, `quota` bytes, `active`, `maildir`) + `alias` | SHA512-CRYPT | no (fail2ban) |
| Admin panel | `admin_users` (`password_hash`, `failed_attempts`, `locked_until`) | bcrypt | sí (5/15min) |
