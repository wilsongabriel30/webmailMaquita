# Guía de administración del correo — `maquita-mailadm`

Manual de referencia para administradores que instalen el sistema de correo
Maquita. `maquita-mailadm` es la herramienta de consola (estilo `zmprov`/
`zmcontrol` de Zimbra) para gestionar cuentas, alias, reenvíos, autorespuestas,
cola y servicios — **sin tocar la base de datos a mano**.

Todas las acciones que modifican algo quedan registradas en
`/var/log/maquita-mailadm.log` (actor + fecha + acción + objetivo).

---

## Instalación
```bash
cp deploy/tools/maquita-mailadm /usr/local/sbin/maquita-mailadm
chmod 750 /usr/local/sbin/maquita-mailadm        # solo root
maquita-mailadm help
```
Requisitos: PostgreSQL local (`maildb`), `doveadm` + `sievec` (Dovecot),
`python3-bcrypt`. Ejecutar siempre como **root** (`sudo`).

---

## Referencia rápida (comando → equivalente Zimbra)

| maquita-mailadm | Zimbra | Qué hace |
|---|---|---|
| `mailbox create <email> [GB] [pass]` | `zmprov ca` | Crear buzón |
| `mailbox delete <email>` | `zmprov da` | Borrar buzón (conserva el maildir) |
| `mailbox passwd <email> [nueva]` | `zmprov sp` | Resetear contraseña |
| `mailbox quota <email> <GB>` | `zmprov ma zimbraMailQuota` | Cambiar cuota (0=ilimitado) |
| `mailbox enable\|disable <email>` | `zmprov ma zimbraAccountStatus` | Activar/desactivar |
| `mailbox info <email>` | `zmprov ga` | Ver estado |
| `mailbox list [dominio]` | `zmprov gaa` | Listar buzones |
| `alias create <alias> <destino>` | `zmprov aaa` | Crear alias |
| `alias delete <alias>` | `zmprov raa` | Borrar alias |
| `alias list [dominio]` | — | Listar alias/reenvíos |
| `forward set <buzon> <destino> [keep]` | `zmprov ma zimbraPrefMailForwardingAddress` | Reenviar (keep=copia local) |
| `forward off <buzon>` | — | Quitar reenvío |
| `forward list` | — | Buzones con reenvío |
| `autoresponder set <email> <asunto> <msg> [dias] [desde] [hasta]` | `zmprov ma zimbraPrefOutOfOffice*` | Autorespuesta (Sieve) |
| `autoresponder off\|show <email>` / `list` | — | Gestionar autorespuesta |
| `admin passwd <user> [nueva]` | — | Resetear admin del panel |
| `admin unlock <user>` | — | Desbloquear admin |
| `admin list` | — | Listar admins |
| `queue list\|flush\|delete-all` | `zmcontrol` / `postqueue` | Cola de correo |
| `fail2ban status` / `unban <ip>` | — | Ver baneos / desbanear |
| `domain list` | `zmprov gad` | Listar dominios |
| `service status\|restart\|reload <svc>` | `zmcontrol` | Control de servicios |

---

## Recetas (casos comunes)

**Un usuario olvidó su contraseña**
```bash
maquita-mailadm mailbox passwd juan@example.org      # la pide oculta
```

**Alta de un empleado nuevo (buzón 10 GB)**
```bash
maquita-mailadm mailbox create juan@example.org 10
```

**Un empleado dejó la organización** (no se borra de inmediato: se desactiva y se reenvía a su jefe)
```bash
maquita-mailadm mailbox disable  juan@example.org
maquita-mailadm forward set      juan@example.org jefe@example.org
# cuando ya no haga falta:
maquita-mailadm mailbox delete   juan@example.org
```

**Empleado de vacaciones**
```bash
maquita-mailadm autoresponder set juan@example.org "Fuera de oficina" \
  "Estoy de vacaciones. Para urgencias, recepcion@example.org." 1 2026-07-01 2026-07-15
#   los dos últimos (desde hasta, AAAA-MM-DD) son OPCIONALES: solo responde
#   dentro de ese rango. Sin ellos, responde mientras esté activo. Al volver:
maquita-mailadm autoresponder off juan@example.org
```

**Dirección de área que reparte a varias personas**
```bash
maquita-mailadm alias create ventas@example.org juan@example.org
# para varios destinos, repetir o editar el goto (separado por comas)
```

**Un usuario legítimo quedó baneado (mucho intento de login)**
```bash
maquita-mailadm fail2ban status            # ver qué IP está baneada
maquita-mailadm fail2ban unban 190.x.x.x
```

**El admin del panel no puede entrar / cuenta bloqueada**
```bash
maquita-mailadm admin unlock admin
maquita-mailadm admin passwd admin         # si además olvidó la contraseña
```

**Los correos no salen / se acumulan**
```bash
maquita-mailadm queue list                 # ver la cola
maquita-mailadm queue flush                # forzar reintento
maquita-mailadm service status             # ver si postfix/dovecot están arriba
```

---

## Seguridad y buenas prácticas
- **Solo root.** El texto plano de las contraseñas nunca toca el SQL: se hashea
  con `doveadm pw` (buzones, SHA512-CRYPT) o `bcrypt` (admins) antes.
- Si se omite la contraseña, se pide de forma **oculta** (no queda en el history).
- `mailbox delete` **no borra el maildir físico** (`/var/vmail/<dom>/<local>/`):
  eliminar a mano si se desea, para evitar pérdida accidental.
- `autoresponder set` **compila el Sieve con `sievec` antes de activarlo**: si el
  Sieve es inválido, no se activa nada (no rompe la entrega del buzón).
- Revisar la auditoría: `tail /var/log/maquita-mailadm.log`.
- Los buzones no tienen bloqueo de cuenta (se protegen por fail2ban/IP); el
  lockout (5 intentos → 15 min) aplica solo a los admins del panel.

---

## Esquema de datos (referencia)
| Objeto | Tabla(s) | Hash | Notas |
|---|---|---|---|
| Buzón | `mailbox` + `alias` (self) | SHA512-CRYPT | `quota` en bytes, `maildir`=`dom/local/` |
| Alias/reenvío | `alias` (PK `address`, `goto` admite comas) | — | `address≠goto` = reenvío |
| Autorespuesta | `mail_autoresponders` + Sieve `vacation.sieve` | — | symlink `.dovecot.sieve` |
| Admin panel | `admin_users` | bcrypt | `failed_attempts`, `locked_until` |
