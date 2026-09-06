# Actualizar Maquita Mail

Guía para pasar de una versión publicada a la siguiente **sin reinstalar**. Para una
instalación nueva, `docs/INSTALL-DESDE-CERO.md`.

Regla general: `git fetch && git checkout vX.Y.Z`, aplicar las migraciones nuevas
(`migrations/*.sql`, idempotentes, en orden), revisar las variables nuevas del `.env` de cada
servicio, reiniciar lo que cambió y correr `deploy/tools/validar-despliegue.sh`.

---

## De 1.6.1 a 1.7.0 — ciclo de vida de sesión (sid / auth_version)

**Lo que cambia para la gente: un corte único.** Al reiniciar el correo con 1.7.0, **todas las
sesiones abiertas dejan de valer** (webmail, app, chat): los tokens anteriores no llevan `sid`
ni `av` y el sistema ya no los acepta. Cada persona vuelve a iniciar sesión **una vez**. Hazlo
fuera de horario y avísalo antes.

### 1. Variables nuevas

**Correo (`backend/.env`)** — ninguna obligatoria.

| Variable | Qué es | Valor si falta |
|---|---|---|
| `CHAT_INTERNAL_URL` | URL del chat a la que el correo empuja las revocaciones (F-03). | El origen de `embed_url` de la configuración del chat; si es relativa (mismo origen), no se empuja nada. |
| `NOTIF_SECRET` | Ya existía: secreto compartido con el chat. Ahora también autentica `GET /api/auth/sesion-servicio` y el empuje de revocaciones. **Mismo valor en el correo y en el chat.** | — |

**Chat (`chat-service/.env`)**

| Variable | Qué es | Valor si falta |
|---|---|---|
| `NOTIF_SECRET` | **Ahora obligatorio** (≥ 16 caracteres). Sin él el chat no arranca. Mismo valor que en el correo. | arranque abortado |
| `CHAT_SESION_CENTRAL` | `1` = el chat comprueba la sesión central del correo en cada petición y conexión. `0` = pasivo (solo durante la actualización, ver orden). | `1` |
| `CORREO_URL_API` | URL del correo para revalidar sesiones. | `CORREO_URL_CALENDARIO` |
| `CHAT_REVALIDAR_SESION_SEG` | Cada cuánto revalida una sesión del chat contra el correo. | `300` |

### 2. Migración de base de datos

```bash
sudo -u postgres psql -d maildb -v ON_ERROR_STOP=1 -f migrations/2026-09-06-sesiones-sid-av.sql
```
Idempotente. Crea `auth_estado`, añade `sid`, `session_kind`, `absolute_expires_at` y
`auth_version` a `refresh_tokens`, concede permisos a `mailserver` y marca revocados los
refresh anteriores al modelo (ya no se podrían renovar).

### 3. Orden de despliegue (importa)

1. **Chat primero, en modo pasivo**: `CHAT_SESION_CENTRAL=0` y `NOTIF_SECRET` en su `.env`;
   `git checkout v1.7.0` en VM del chat; reiniciar `maquita-chat`. Desde aquí el chat ya acepta
   el empuje de revocaciones (`POST /api/chat/sesion/revocar`) aunque todavía no exija `sid`.
2. **Correo**: migración (paso 2), `git checkout v1.7.0`, `bash deploy-webmail.sh` (construye,
   publica y reinicia el backend). **Este es el corte**: todo el mundo vuelve a entrar.
3. **Activar la comprobación en el chat**: `CHAT_SESION_CENTRAL=1` (o quitar la variable) y
   reiniciar `maquita-chat`. Quien tuviera el chat abierto con una sesión anterior verá la
   pantalla de «vuelve a iniciar sesión en el correo».

Para revertir: orden inverso (chat pasivo → correo a la versión anterior → chat a la versión
anterior). La migración no hace falta deshacerla: las columnas nuevas no estorban a 1.6.x.

### 4. Comprobar

```bash
bash deploy/tools/validar-despliegue.sh          # 0 fallos
curl -s -o /dev/null -w '%{http_code}\n' https://<correo>/api/auth/verify   # 401 sin sesión
```
Y a mano: entrar en dos navegadores, cambiar la contraseña en uno → el otro cae (webmail y
chat); «Cerrar todas las sesiones» en Ajustes hace lo mismo; el panel de administración sigue
pudiendo impersonar, y esa sesión muere a la hora aunque se use.

### 5. Qué reportar si algo falla

Mismo formato que en `docs/INSTALL-DESDE-CERO.md` («Si algo falla: qué reportar»), indicando
además desde qué versión se actualizó y en qué paso del orden de arriba ocurrió.
