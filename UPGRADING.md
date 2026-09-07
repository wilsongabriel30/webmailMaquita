# Actualizar Maquita Mail

Guía para pasar de una versión publicada a la siguiente **sin reinstalar**. Para una
instalación nueva, `docs/INSTALL-DESDE-CERO.md`.

Regla general: `git fetch --tags --force && git checkout vX.Y.Z` (el `--force` hace falta en clones
anteriores a la reconstrucción del historial de 2026-09-05), aplicar las migraciones nuevas
(`migrations/*.sql`, idempotentes, en orden), revisar las variables nuevas del `.env` de cada
servicio, reiniciar lo que cambió y correr `deploy/tools/validar-despliegue.sh`.

---

## De 1.7.7 a 1.7.8 — Z-Push vuelve (ActiveSync para Outlook)

Sin migraciones ni corte. `git fetch --tags --force && git checkout v1.7.8 && bash deploy-webmail.sh`
(el backend trae el autodiscover con ActiveSync).

1. `bash deploy/z-push/instalar.sh <dominio>`: construye la imagen (base actual + upgrade), escribe
   `/opt/z-push-docker/*.php`, arranca el contenedor `zpush` en `127.0.0.1:9000` y deja el snippet.
   Si ya tenías Z-Push nativo (pool PHP-FPM `zpush.conf`, `/opt/z-push`), retíralos: todo va en el
   contenedor.
2. nginx: en el `server{}` HTTPS del correo, `include snippets/maquita-apps/activesync.conf;` y en
   el `location` del autodiscover admite `.xml` **y** `.json` (ver `deploy/webmail/nginx/webmail.conf`).
   `nginx -t && systemctl reload nginx`.
3. Radicale debe escuchar también en la IP del puente de Docker: `hosts = 127.0.0.1:5232,
   172.17.0.1:5232` y **reinicio** (comprobar con `ss -ltn | grep 5232`). Cortafuegos: antes de los
   `drop` por país en la cadena `input`, `iifname "docker0" tcp dport { 465, 993, 5232 } accept`
   (persistir en `/etc/nftables.conf`). Colecciones: `deploy/tools/radicale-asegurar-colecciones.py
   --todos` (el instalador instala el cron horario). Si había Z-Push nativo, retira su `location`
   (`php8.4-zpush.sock`), el pool y `/opt/z-push`; el `include` del snippet va en el `server{}` del correo.
4. Comprobar (todo en `OPERACION.md`, «Z-Push / ActiveSync»): `OPTIONS /Microsoft-Server-ActiveSync`
   → 401; autodiscover `mobilesync` → `<Type>MobileSync</Type>`; JSON v2 → `"Protocol":"ActiveSync"`;
   y la **prueba real con una cuenta en los dos Outlook** (correo, calendario en los dos sentidos,
   contactos, tarea).

---

## De 1.7.6 a 1.7.7 — segundo factor obligatorio para cuentas privilegiadas

Sin migraciones ni corte. `git fetch --tags --force && git checkout v1.7.7 && bash deploy-webmail.sh`.

- Desde esta versión los buzones `admin@` y `postmaster@` (de cualquier dominio) **no pueden usar
  el webmail sin TOTP**: al entrar, la pantalla les pide activarlo (con sus códigos de respaldo)
  y hasta entonces todo lo demás responde 403 `must_setup_2fa`. Avisa a quien use esos buzones.
- Para cambiar la lista: `TOTP_OBLIGATORIO=admin,postmaster,soporte@tu-dominio` en `backend/.env`
  (partes locales o direcciones completas, separadas por comas; vacía = nadie) y reinicia el
  backend. `DECISIONES.md` D-10.
- Comprobar: entrar con `admin@tu-dominio` debe llevar a la pantalla «Activa la verificación en
  dos pasos»; una cuenta normal entra como siempre.

---

## De 1.7.5 a 1.7.6 — Z-Push retirado e imágenes

Sin migraciones ni corte. Solo afecta a quien tuviera Z-Push (ActiveSync) instalado.

1. `git fetch --tags --force && git checkout v1.7.6`.
2. Si tenías Z-Push (contenedor `zpush`, pool PHP-FPM `zpush.conf`, `/opt/z-push*`): comprueba antes
   que nadie lo usa (`grep -c Microsoft-Server-ActiveSync /var/log/nginx/access.log*` y
   `ls /var/lib/z-push/users`). Luego, con respaldo: `docker stop zpush && docker rm zpush &&
   docker rmi zpush:latest`, retira el pool `zpush.conf` y recarga `php8.4-fpm`, y en nginx haz que
   `/autodiscover/autodiscover.xml` vaya al backend (bloque «Autodiscover Outlook» de
   `deploy/webmail/nginx/webmail.conf`). Comprobar: un `POST` a
   `https://autodiscover.TU-DOMINIO/autodiscover/autodiscover.xml` responde 200 con `IMAP` y `SMTP`.
   Los teléfonos siguen por IMAP + CalDAV/CardDAV con autoconfiguración.
3. Si despliegas el chat en contenedor: reconstruye con `docker build --pull` (la imagen ya no trae
   pip). Nada que hacer si el chat corre en venv.

---

## De 1.7.4 a 1.7.5 — sudoers, IA y milter

Sin migraciones ni corte de sesiones. Cambia cómo el correo y el panel obtienen privilegios.

1. `git fetch --tags --force && git checkout v1.7.5`.
2. **sudoers** (antes de reiniciar nada):
   ```bash
   install -m755 deploy/sudoers/maquita-sudo /usr/local/sbin/maquita-sudo
   install -m440 deploy/sudoers/maquita-webmail /etc/sudoers.d/maquita-webmail
   install -m440 deploy/sudoers/maquita-admin  /etc/sudoers.d/maquita-admin
   rm -f /etc/sudoers.d/webmail-doveadm
   visudo -c
   ```
   Si tu sudoers del panel tenía unidades o parámetros propios fuera de la lista del envoltorio,
   añádelos en `UNIDADES` / `POSTCONF_PARAMS` de `maquita-sudo` (y en el repo, por favor).
   Comprobar como `www-data`:
   `sudo -u www-data sudo -n /usr/local/sbin/maquita-sudo doveadm search -u <buzón> mailbox Sent header message-id x`
   debe devolver 0 o 1 (no «password is required»), y con `-o mail_location=/etc` debe rechazarse.
3. `bash deploy-webmail.sh` (backend), `systemctl restart maquita-admin maquita-milter`.
4. Comprobar: `grep MAQUITA_SUDO /var/log/auth.log` muestra `ok` al usar el panel (fail2ban, cola);
   Smart Reply responde (si devuelve 502, revisa que `IA_API_KEY` en `backend/.env` y en la tabla
   `ai_config` sea la que espera tu pasarela de IA); `X-Maquita-Scan: failed` solo aparece si el
   análisis del milter falla, y entonces `vigilar-milter.sh` avisa a partir de 3 por hora.

---

## De 1.7.3 a 1.7.4 — correo, chat y nginx

Sin migraciones ni corte de sesiones.

1. `git fetch --tags --force && git checkout v1.7.4` y `bash deploy-webmail.sh` (reinicia el backend).
2. nginx: añade la zona `csp` y el `location = /api/csp-report` de `deploy/webmail/nginx/webmail.conf`
   (cuerpo de 16 KB, 30 informes/minuto por IP) y recarga. Sin esto el backend igual filtra y
   deduplica; la zona solo evita que el ruido llegue al backend.
3. Chat: `git checkout v1.7.4` en su máquina y `systemctl restart maquita-chat`. Después, una vez:
   `cd chat-service && venv/bin/python purgar_tokens_reuniones.py` (con `DATABASE_URL` en el entorno)
   para quitar de `reuniones_programadas` los JWT de Meet que se guardaban.
4. Comprobar: `POST /api/csp-report` con un informe NEL responde 200 y no deja línea en
   `security.log`; `SELECT count(token_moderador) FROM reuniones_programadas` devuelve 0;
   `deploy/tools/validar-despliegue.sh` no marca fallo por `SSL_accept error` de escáneres.

---

## De 1.7.2 a 1.7.3 — correo, almacén y chat

Sin corte de sesiones. Migración nueva, reinicio del backend del correo, del almacén y del chat.

1. Migración `migrations/2026-09-06-codigos-respaldo.sql` (idempotente) **antes** de reiniciar:
   crea `user_totp_backup_codes` y **vacía los códigos de respaldo antiguos** de 2FA (32 bits,
   en claro). El backend también crea la tabla si falta, pero no vacía nada.
2. `git checkout <etiqueta>` y `bash deploy-webmail.sh` (construye el frontend y reinicia el backend).
3. **Avisar a quien tenga 2FA activo**: sus códigos de respaldo anteriores ya no valen; debe
   generar unos nuevos en Ajustes → Autenticación de dos factores → «Generar códigos de
   respaldo nuevos» (pide un código TOTP vigente). El estado muestra «0 códigos de respaldo».
4. Comprobar: `GET /api/auth/sesiones` con sesión devuelve la lista de sesiones abiertas;
   `GET /api/auth/totp/status` de una cuenta con 2FA devuelve `backup_codes_remaining`.
5. Almacén: `systemctl restart maquita-almacen` (nombres sin marcas de HTML, explorador escapado,
   DDL de arranque serializado: ya no debe haber `DeadlockDetected` al arrancar).
6. Chat (VM propia, sin git): copiar `chat-service/app/` completo salvo `.env`, `venv/` y las
   subidas, y reiniciar `maquita-chat`. Cambia la presencia (solo entre quienes comparten
   conversación), la señalización de llamadas, la conversación directa por socket, el limitador y
   la validación del emoji de las reacciones. Comprobar en el registro que no aparezcan
   `LLAMADA_RECHAZADA` ni `DIRECTO_RECHAZADO` para usos legítimos, ni `RATE_LIMIT_SIN_REDIS`.

---

## De 1.7.1 a 1.7.2 — almacén y panel

Sin corte de sesiones. Cambia el servicio del almacén, el panel y un detalle de nginx.
Si vienes de **1.7.0** (saltándote 1.7.1) instala también `backend/requirements.txt`
(`signxml`, `lxml`) y reinicia el backend del correo.

0. **Antes de reiniciar el almacén**, comprueba que `almacen/.env` tiene `ALMACEN_CLAVE_SESION`
   con un valor real (≥ 16 caracteres). Es obligatoria desde 1.7.0 y las instalaciones
   anteriores no la traían; sin ella el almacén no arranca (ver «Variables nuevas» de 1.7.0).

1. Dependencia nueva del almacén (Argon2id para la clave de los enlaces compartidos):
   `almacen/venv/bin/pip install -r almacen/requirements.txt` (trae `argon2-cffi`).
2. Reiniciar `maquita-almacen`. Al arrancar crea la columna `compartidos.version` y la tabla
   `compartidos_intentos`; los hashes SHA-256 de claves anteriores siguen valiendo y se
   migran a Argon2id en el primer acierto.
3. nginx: la clave de un enlace ya no viaja en la URL y las páginas públicas responden
   `Referrer-Policy: no-referrer`. Si tu `server{}` añade su propia `Referrer-Policy`, la del
   servicio queda anulada: define el valor por `map` como muestra
   `almacen/deploy/nginx-almacen.conf` y recarga nginx.
4. Comprobar: `curl -sD - -o /dev/null https://TU_HOST/almacen-s/<token>` debe traer
   `referrer-policy: no-referrer` y `cache-control: no-store` (y no otra `Referrer-Policy`).

---

## De 1.6.1 a 1.7.0 — ciclo de vida de sesión (sid / auth_version)

**Lo que cambia para la gente: un corte único.** Al reiniciar el correo con 1.7.0, **todas las
sesiones abiertas dejan de valer** (webmail, app, chat): los tokens anteriores no llevan `sid`
ni `av` y el sistema ya no los acepta. Cada persona vuelve a iniciar sesión **una vez**. Hazlo
fuera de horario y avísalo antes.

### 1. Variables nuevas

**Correo (`backend/.env`)**

| Variable | Qué es | Valor si falta |
|---|---|---|
| `CREDENTIAL_ENCRYPTION_KEY` | **Obligatoria (H-02).** Llave Fernet dedicada que cifra la credencial IMAP cacheada, las cuentas de Nextcloud y el secreto TOTP. Genérala: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Cópiala también al panel como `WEBMAIL_CREDENTIAL_ENCRYPTION_KEY`. | arranque abortado |
| `CREDENTIAL_ENCRYPTION_KEY_ANTERIOR` | Solo al rotar la anterior. | — |
| `CHAT_INTERNAL_URL` | URL del chat a la que el correo empuja las revocaciones (F-03). | El origen de `embed_url` de la configuración del chat; si es relativa (mismo origen), no se empuja nada. |
| `NOTIF_SECRET` | Ya existía: secreto compartido con el chat. Ahora también autentica `GET /api/auth/sesion-servicio` y el empuje de revocaciones. **Mismo valor en el correo y en el chat.** | — |

**Almacén (`almacen/.env`)**

| Variable | Qué es | Valor si falta |
|---|---|---|
| `ALMACEN_CLAVE_SESION` | **Obligatoria desde 1.7.0 (R-01).** Clave propia de la sesión Flask del almacén; no es la del SSO (`WEBMAIL_SECRET_KEY`). Genérala: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. En 1.6.x tenía un valor por defecto y el instalador anterior a 1.7.2 no la escribía, así que **el fallo queda latente hasta el primer reinicio del almacén**. | arranque del almacén abortado (`RuntimeError: Falta ALMACEN_CLAVE_SESION`) |

**Chat (`chat-service/.env`)**

| Variable | Qué es | Valor si falta |
|---|---|---|
| `NOTIF_SECRET` | **Ahora obligatorio** (≥ 16 caracteres). Sin él el chat no arranca. Mismo valor que en el correo. | arranque abortado |
| `CHAT_SESION_CENTRAL` | `1` = el chat comprueba la sesión central del correo en cada petición y conexión. `0` = pasivo (solo durante la actualización, ver orden). | `1` |
| `CORREO_URL_API` | URL del correo para revalidar sesiones. | `CORREO_URL_CALENDARIO` |
| `CHAT_REVALIDAR_SESION_SEG` | Cada cuánto revalida una sesión del chat contra el correo. | `300` |

### 2. Migración de base de datos

**Las dos** migraciones de 1.7.0, en orden alfabético (todas son idempotentes):
```bash
for f in migrations/2026-09-06-*.sql; do sudo -u postgres psql -d maildb -v ON_ERROR_STOP=1 -f "$f"; done
```
Sin `2026-09-06-cambio-obligatorio.sql` el login responde 503 (falta la columna
`must_change_password`): fue el fallo que encontró Correo Andes al actualizar su VM de pruebas.
Idempotente. Crea `auth_estado`, añade `sid`, `session_kind`, `absolute_expires_at` y
`auth_version` a `refresh_tokens`, concede permisos a `mailserver` y marca revocados los
refresh anteriores al modelo (ya no se podrían renovar).

### 2b. Recifrar lo guardado con la llave nueva

Tras definir `CREDENTIAL_ENCRYPTION_KEY` y **antes** de reiniciar el correo:
```bash
cd backend && venv/bin/python ../deploy/tools/recifrar-credenciales.py          # cuenta
cd backend && venv/bin/python ../deploy/tools/recifrar-credenciales.py --aplicar # aplica
```
Recifra los secretos TOTP (antes en claro) y las cuentas de Nextcloud. Las credenciales IMAP
cacheadas no se migran: caen con el corte de sesiones.

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
