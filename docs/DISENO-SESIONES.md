# Diseño — ciclo de vida de sesión con `sid` y `auth_version` (F-01, F-03, F-04)

**Fecha:** 2026-09-06 · **Estado:** propuesta para aprobación, sin código todavía · **Cubre:** F-01, F-03, F-04 (y prepara F-02).

## 1. Qué está roto hoy (una frase por cara)

- **REST/WebSocket (F-01):** la sesión «vive» mientras exista `imap_pass:{user}` en Redis: **una clave por usuario**, no por sesión. Cambiar la contraseña la *reescribe* (`password.py:243`), el reset del admin la borra pero un login legítimo la recrea y **resucita** cualquier access token robado aún no vencido (15 min) y cualquier refresh no revocado (7 días). El WebSocket solo comprueba la firma del JWT.
- **Chat (F-03):** el vale de un solo uso crea una `chat_session` propia (Flask, cookie firmada) que después **no vuelve a mirar al correo**; Socket.IO confía en `session['usuario_id']`. El chat tiene **su propio Redis** (VM 136, `127.0.0.1:6390`): no puede leer el estado del correo directamente.
- **Impersonación (F-04):** se emite con refresh de 1 h, pero `/api/auth/refresh` es genérico: rota y emite **7 días** más. El límite de una hora no es un límite.

## 2. Vocabulario (el mínimo que todos los servicios comprueban)

| Término | Qué es | Dónde vive |
|---|---|---|
| `sid` | Identificador de **sesión** (dispositivo/navegador). 128 bits aleatorios, urlsafe. | Claim del access JWT; fila del refresh; claves Redis. |
| `av` (`auth_version`) | **Generación de autenticación** del usuario. Entero que sube en cada evento de revocación global. | Tabla `auth_estado` (PostgreSQL) + caché `av:{user}` en Redis (write-through). Claim del access JWT y columna del refresh. |
| `kind` | Tipo de sesión: `normal` · `impersonation` · `oidc` · `saml`. | Claim del access; columna `session_kind` del refresh; metadatos de sesión. |
| `abs_exp` | **Vencimiento absoluto** de la sesión: ninguna renovación lo supera. `normal`: `now + refresh_days`; `impersonation`: `now + 1 h`. | Claim del access; columna `absolute_expires_at` del refresh. |

Regla única, aplicada en todas las fronteras: **una petición vale si (a) el token está firmado y no vencido, (b) existe su sesión `sid`, (c) su `av` es el actual del usuario, (d) no ha pasado `abs_exp`.**

## 3. Almacenamiento

**PostgreSQL** (migración `deploy/webmail/migrations/2026-09-06-sesiones.sql`, idempotente):

```sql
CREATE TABLE IF NOT EXISTS auth_estado (
  username     varchar(255) PRIMARY KEY,
  auth_version integer NOT NULL DEFAULT 1,
  updated_at   timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE refresh_tokens
  ADD COLUMN IF NOT EXISTS sid                 varchar(32),
  ADD COLUMN IF NOT EXISTS session_kind        varchar(16) NOT NULL DEFAULT 'normal',
  ADD COLUMN IF NOT EXISTS absolute_expires_at timestamptz,
  ADD COLUMN IF NOT EXISTS auth_version        integer NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS refresh_tokens_user_activos ON refresh_tokens (username) WHERE NOT is_revoked;
```
No se toca `mailbox` (esquema de Postfix/Dovecot): la generación vive en su propia tabla; un usuario sin fila tiene `av = 1`.

**Redis** (mismo cifrado Fernet de hoy):

| Clave | Contenido | TTL |
|---|---|---|
| `sess:{user}:{sid}` | hash: `kind`, `abs_exp`, `av`, `ua`, `ip`, `creada` | `min(access_ttl con keep-alive, abs_exp)` |
| `imap_pass:{user}:{sid}` | contraseña IMAP cifrada (**por sesión**, ya no por usuario) | igual que `sess` |
| `imap_master:{user}:{sid}` | marca de impersonación | `abs_exp` (1 h, sin prórroga) |
| `sids:{user}` | set de `sid` vivos (para «cerrar todas» y para el WebSocket) | sin TTL; se poda al revocar |
| `av:{user}` | caché de `auth_version` | 24 h; **write-through** en cada subida |

`get_user_password(request, user)` pasa a leer `imap_pass:{user}:{sid}` con el `sid` de la petición (`request.state.sid`, puesto por la dependencia). Los 30 usos actuales de `imap_pass:{user}` se migran por esa función; el `grep` de R-1 ya inventarió que no hay otros patrones.

## 4. Emisión y comprobación

**Login / OIDC / SAML / impersonación** generan `sid`, leen `av`, fijan `kind` y `abs_exp`, escriben `sess`, `imap_pass`, `sids`, y la fila de refresh con `sid`, `session_kind`, `absolute_expires_at`, `auth_version`. El access JWT lleva `sub, sid, av, kind, abs_exp, type, exp`.

**`get_current_user` (dependencia central, REST):**
1. decodifica; **exige** `sid` y `av` (un token sin ellos → 401: es un token anterior al despliegue);
2. `av == av_actual(user)` (caché Redis; si no está, lee `auth_estado` y la rellena; si Redis y BD fallan → **401, fallo cerrado**);
3. `EXISTS sess:{user}:{sid}` (si no → 401 «sesión cerrada»);
4. `now < abs_exp`; keep-alive de TTL **solo** si `kind == normal` (impersonación no se prorroga, como hoy);
5. deja `request.state.sid` para el resto de la petición.

**`/api/auth/refresh`:** hash válido, no revocado, `expires_at > now`, **`absolute_expires_at > now`**, `auth_version == av_actual`; rota el refresh conservando `sid`, `session_kind`, `absolute_expires_at`; `expires_at_nuevo = min(now + refresh_ttl, absolute_expires_at)`; el access nuevo lleva los mismos `sid/kind/abs_exp`; el TTL de `imap_pass` también queda acotado por `abs_exp`. Una impersonación **muere a la hora**, se renueve lo que se renueve.

**WebSocket del backend (`/api/ws`):** en el handshake aplica los mismos 4 puntos; guarda `(user, sid)` por conexión; se suscribe (ya existe el suscriptor Redis) al canal `revocacion` y cierra con código 4401 las conexiones cuyo `sid` o `user` (si es global) fue revocado. El sondeo IMAP de cada conexión usa `imap_pass:{user}:{sid}`.

## 5. Eventos de revocación (una sola función, `revocar(user, alcance, motivo)`)

| Evento | Alcance | Efecto |
|---|---|---|
| Logout normal | `sid` | borra `sess/imap_pass/imap_master` de ese `sid`, lo quita de `sids`, revoca **su** refresh. Otras sesiones siguen. |
| «Cerrar todas las sesiones» (nuevo, Ajustes) | global | **sube `av`** (`UPDATE auth_estado … auth_version+1 RETURNING`, write-through a Redis), revoca todos los refresh no revocados, borra todos los `sid` de `sids:{user}`. |
| Cambio de contraseña por el usuario | global + **reemisión** | igual que «cerrar todas» y, en la misma respuesta, emite una sesión nueva (`sid` nuevo, `av` nuevo) al llamante: el usuario no se cae; todo lo demás sí. |
| Reset/cambio de clave por admin | global | como «cerrar todas». |
| Desactivar cuenta (admin) / bloqueo AIR / `account_blocked` | global | como «cerrar todas»; además `get_current_user` comprueba `active` a través de la generación: desactivar sube `av`, así que ningún token viejo pasa aunque el admin reactive después (reactivar **no** baja `av`). |
| Vencimiento `abs_exp` | `sid` | expira solo por TTL; el refresh lo rechaza por `absolute_expires_at`. |

Cada revocación **publica** en Redis `revocacion` `{user, sid|"*", av, motivo}` (para los WebSocket del backend) y **empuja** al chat (sección 6). Re-login **no revive nada**: un token viejo trae `av` viejo.

## 6. Chat (F-03): misma regla, sin fusionar servicios ni consultar PostgreSQL por mensaje

El chat no comparte Redis con el correo (VM 136, Redis propio en `127.0.0.1:6390`). Tres piezas:

1. **El vale de un solo uso lleva `sid` y `av`** (además de `sub`, `jti`, `aud`, `exp` de hoy). Al canjearlo, la `chat_session` guarda `sid`, `av` y `validado_hasta`.
2. **Empuje de revocación correo → chat:** `revocar()` llama a `POST /api/chat/sesion/revocar` con el secreto ya existente `X-Notif-Secret` (mismo patrón que `/api/chat/notificaciones`), cuerpo `{user, sid|"*", av}`. El chat guarda `av:{user}` en **su** Redis y, si `sid="*"`, marca al usuario; en ambos casos **desconecta los Socket.IO** de ese usuario/sesión (`usuarios_conectados` ya mapea usuario → sids de Socket.IO). Reintentos con cola si el chat no responde (como la cola de cuarentena del milter).
3. **Comprobación en el chat:** `before_request` y `connect` de Socket.IO comparan `session['av']` con `av:{user}` de su Redis (O(1), sin BD). Además, como red de seguridad ante un empuje perdido, cada sesión **revalida contra el correo** (`GET /api/auth/sesion/{sid}`, con el mismo secreto de servicio) cuando `validado_hasta` (5 min) caduca; si el correo no responde, **fallo cerrado**: 401 en el chat (el chat ya depende del correo para calendario y tareas). Los enlaces de notificación con `?token=` (T-44) pasan por la misma dependencia al sembrar la sesión.

## 7. Prueba de cierre obligatoria (CI, `backend/tests/test_lifecycle_sesion.py` + `chat-service/tests/test_revocacion.py`)

Matriz **{logout, logout-all, password-change, admin-reset, disable} × {REST, WebSocket, refresh, chat REST, chat Socket.IO}** = 25 celdas; cada celda espera **401** o **cierre de conexión**. Más las de coherencia: logout de A no toca B; re-login no revive un access viejo; refresh de impersonación a los 30 min conserva `absolute_expires_at`; refresh pasado el límite → 401; sesión normal no hereda `kind=impersonation`. Se corren con PostgreSQL y Redis reales del CI (ya los levanta `ci.yml`), Dovecot sustituido por un doble que acepta la clave de prueba; el chat con su cliente de pruebas de Flask/Flask-SocketIO y un correo simulado para `/api/auth/sesion/{sid}`. **Sin la matriz en verde, P0 no se cierra.**

## 8. Despliegue y compatibilidad

- Un solo corte: al desplegar, **todos los tokens anteriores dejan de valer** (no traen `sid/av`) → todo el mundo vuelve a iniciar sesión una vez. Se anuncia y se hace fuera de horario.
- Migración SQL idempotente antes del reinicio; `auth_estado` se rellena perezosamente (usuario sin fila = `av 1`).
- Chat: se despliega **antes** el endpoint de revocación (acepta el empuje aunque aún no lo use) y después el correo; por último se activa la comprobación de `av` en el chat. Orden inverso al revertir.
- Panel de administración: sus llamadas de impersonación ya pasan por `/api/auth/impersonate`; solo cambia que el refresh ya no prorroga.
- Orden de commits: F-01 backend (jwt, dependencies, router, password, admin, websocket, migración, pruebas) → F-04 (refresh acotado; va dentro de F-01 en cuanto a datos, commit aparte) → F-03 chat (vale, endpoint, guard, Socket.IO, pruebas) → matriz completa en CI.

## 9. Fuera de este diseño pero encadenado

- **F-02 SAML** (P0, aparte): SAML está **inactivo hoy** (`sso_config` vacía; `/api/sso/saml/login` → «SSO no está configurado o inactivo»). El ACS nuevo emitirá sesiones `kind=saml` con este mismo modelo. `signxml==4.4.0` y `lxml==6.1.0` (las instaladas) se fijan en `requirements.txt` con ese commit (R-11).
- El registro interno decía A-10 «abierto (latente)» en `REAUDITORIA-2026-09-04.md`; no consta como cerrado en los documentos versionados. Si en algún resumen se dio por cerrado, se corrige a **abierto** (queda anotado en `ESTADO-REMEDIACION`).

## 10. Implementación (2026-09-06)

F-01/F-04 en `backend/app/auth/sesiones.py`, `jwt.py`, `dependencies.py`, `router.py`; F-03 en
`chat-service/app/interfaces/api/sesion_central.py`, `backend/app/chatcfg/revocacion.py` y
`backend/app/auth/sesion_servicio.py`. Variables y orden de despliegue en `UPGRADING.md`
(`CHAT_SESION_CENTRAL`, `CHAT_INTERNAL_URL`, `CORREO_URL_API`). Matriz: `backend/tests/
test_lifecycle_sesion.py` y `chat-service/tests/test_revocacion.py`.
