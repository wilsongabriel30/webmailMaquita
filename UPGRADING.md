# Actualizar Maquita Mail

Guía para pasar de una versión publicada a la siguiente **sin reinstalar**. Para una
instalación nueva, `docs/INSTALL-DESDE-CERO.md`.

Regla general: `git fetch --tags --force && git checkout vX.Y.Z` (el `--force` hace falta en clones
anteriores a la reconstrucción del historial de 2026-09-05), aplicar las migraciones nuevas
(`migrations/*.sql`, idempotentes, en orden), revisar las variables nuevas del `.env` de cada
servicio, reiniciar lo que cambió y correr `deploy/tools/validar-despliegue.sh`.

---

## De 1.7.14 a 1.7.15 — lo que enseño una instalacion desde cero

Recoge los trece hallazgos de una instalacion limpia hecha por el equipo que replica el sistema.
**Hay un paso que puede dejaros el chat sin proxy si no lo hacen antes**: leedlo entero.

### 1. ANTES de actualizar: donde escucha el chat

Desde esta version el chat escucha **solo en loopback** por omision. Estaba en 0.0.0.0 y la guia
prometia lo contrario; en una instalacion limpia era el unico puerto expuesto.

Si vuestro proxy vive en la MISMA maquina, no hay que hacer nada. Si vive en OTRA (nuestro caso),
antes de reiniciar el chat:

```
echo 'CHAT_BIND=0.0.0.0' >> chat-service/.env     # o la interfaz concreta
```

Y acotad el puerto en el cortafuegos, que el servicio no lo hace:

```
nft add rule inet filter input tcp dport 8790 ip saddr <ip-del-proxy> accept
```

### 2. Traer el codigo, reconstruir el correo y reiniciar

```
git fetch --tags && git checkout v1.7.15
cd frontend && npm run build && cd ..     # cambia la burbuja del chat
systemctl restart maquita-chat
systemctl restart maquita-webmail
```

Comprobacion: `ss -lntp | grep 8790` debe mostrar la interfaz que esperais, y el chat seguir
respondiendo a traves de vuestro proxy.

### 3. Comprobar que revocar «todas» revoca de verdad

```
curl -s -X POST https://<chat>/api/chat/sesion/revocar \
  -H "X-Notif-Secret: $NOTIF_SECRET" -H 'Content-Type: application/json' \
  -d '{"user":"persona@ejemplo.org","sid":"*"}'
```

Responde 200 y **la siguiente peticion de esa persona debe dar 401**. Antes respondia 200 y la
sesion seguia viva: sin `av` se anotaba la generacion 0 y ninguna sesion es anterior a 0.

**Negativo 1**: con `sid` concreto solo cae esa sesion, las demas siguen.
**Negativo 2**: con el secreto equivocado, 403.

### 4. Si el chat vive en otro origen

La burbuja del correo ya no sondea su propio origen (daba 404 y se escondia con el chat vivo).
Comprobad en la consola del navegador que al cargar el correo **no** aparecen 404 de
`/api/chat/conversations`.

### 5. Instalaciones nuevas

- `chat-service/deploy/instalar.sh` **rechaza los valores de ejemplo** y comprueba que las dos
  bases responden, que las tablas del chat existen y cuanta gente hay en el directorio.
- `sincronizar_usuarios.py` funciona apuntando a la base del **correo**: detecta el esquema y usa
  `usuarios` o `mailbox`.
- `docs/CHAT-INSTALACION.md` incluye ahora crear la base, poblar el directorio, el cableado del
  correo con el chat (`CHAT_SSO_SECRET`, `NOTIF_SECRET`, `embed_url`) y **la confianza TLS entre
  ambos**: con certificado autofirmado, la revalidacion falla y todas las sesiones mueren a los
  300 segundos; la alternativa es `CORREO_URL_API=http://127.0.0.1:8000` cuando comparten maquina.
- `docs/INSTALL-DESDE-CERO.md`: aviso del preseed de Postfix, comprobacion del paso 5 con el
  nombre del dominio (con `localhost` responde 301) y que en sistemas sin rsyslog no existe
  `/var/log/mail.log`.

## De 1.7.13 a 1.7.14 — dos cosas que se veian desde fuera y no debian

Actualizacion corta y de seguridad. **Conviene mirarla aunque no actualiceis hoy**: el primer
punto se ve en cualquier instalacion con la IA configurada.

### 1. Traer el codigo y reiniciar el correo

```
git fetch --tags && git checkout v1.7.14
systemctl restart maquita-webmail
```

### 2. Comprobar que el estado de la IA ya no cuenta de mas

**Antes de actualizar**, para ver si os afecta:

```
curl -s https://<vuestro-correo>/api/ai/health
```

Si eso devuelve `detail` con vuestros servidores de IA, sus direcciones y sus modelos, lo estais
publicando en internet sin pedir sesion. Despues de actualizar debe devolver solo:

```
{"status":"ok"}
```

Con sesion sale ademas el proveedor y el modelo; el detalle completo, solo para administradores.

### 3. Cabeceras en los nombres de autoconfiguracion

`autodiscover.<dominio>` y `autoconfig.<dominio>` deben mandar `Strict-Transport-Security`: por
ahi viaja la direccion de correo de quien configura su cliente.

```
curl -s -D- -o /dev/null https://autodiscover.<dominio>/ | grep -i strict-transport
curl -s -D- -o /dev/null https://autoconfig.<dominio>/ | grep -i strict-transport
```

Si no aparece, mirad **que bloque atiende ese nombre**: si teneis un vhost con el nombre exacto,
gana sobre el comodin y las cabeceras hay que ponerlas ahi (a nosotros nos paso).

Comprobad despues que el autodescubrimiento sigue respondiendo:

```
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: text/xml' \
  --data @peticion.xml https://autodiscover.<dominio>/autodiscover/autodiscover.xml
```

### Casos negativos

1. `https://<correo>/openapi.json`, `/docs` y `/redoc` no deben servir la documentacion de la API.
2. Un listado de directorio (`/static/`, `/uploads/`) debe dar 403, nunca la lista de ficheros.
3. `https://<correo>/webmail/assets/<fichero>.js.map` debe dar 404: los mapas de codigo fuente no
   se publican.

### Como revisar vuestra propia superficie

En `OPERACION.md` («Superficie expuesta: como revisarla») queda el metodo: leer la tabla de rutas
del servicio y probar cada GET sin sesion. Adivinar direcciones no sirve, porque nginx devuelve la
aplicacion para todo lo que no existe y parece que esta abierto.

## De 1.7.12 a 1.7.13 — el chat sin nomina, avisos honestos y menos ruido

Actualizacion corta: no hay nada que configurar. Recoge los seis avisos del equipo que replica
la instalacion y dos hallazgos de nuestras pruebas con navegador.

### 1. Traer el codigo, reconstruir el correo y reiniciar el chat

```
git fetch --tags && git checkout v1.7.13
cd frontend && npm run build && cd ..        # cambia el boton del chat
systemctl restart maquita-chat
```

### 2. Comprobar que `/healthz` ahora dice la verdad

```
curl -s http://127.0.0.1:8790/healthz
```

Debe traer `"base": "ok"` y responder 200. Si faltan las tablas del chat responde **503** con
`"base": "sin_tablas"` y te dice que ejecutes `migrar_chat.py`; si no llega a la base, 503 con
`"base": "sin_conexion"`. **Si vigilais el servicio, vigilad ese 200**: antes un proceso vivo con
la base a medias daba verde igual.

### 3. Comprobaciones, con sus casos negativos

**Positivo (sin nomina)**: en un esquema sin `trabajadores` ni `usuarios.trabajador_id`, abrir una
conversacion y listar sus mensajes debe funcionar. Antes devolvia 500 por una foto de respaldo.

**Positivo (motivo real)**: con la base parada, intentar empezar una conversacion nueva debe
rechazar (sigue siendo fallo cerrado) pero diciendo que **no se pudo comprobar**, con
`reintentable: true`, en vez de acusar de un bloqueo que no existe.

**Negativo 1**: con un bloqueo de verdad entre dos personas, el mensaje sigue siendo «No puedes
chatear con esta persona» y `reintentable` no aparece.

**Negativo 2**: en una instalacion sin chat (o con la bandera en 0), cargar el correo no debe
disparar ninguna peticion a `/api/chat/*`. Se mira en la consola del navegador.

**Negativo 3**: con una cuenta que no esta en el directorio del chat, el sondeo debe pararse tras
tres vueltas, no seguir cada minuto.

### 4. El candado T-47 ya se puede correr fuera de nuestra casa

```
HUMO_BASE=https://chat.ejemplo.org \
HUMO_DESTINO=quien.recibe@ejemplo.org \
HUMO_REMITENTE=quien.escribe@ejemplo.org \
HUMO_CONVERSACION=12 \
python3 chat-service/humo_notificaciones.py
```

Si falta algo, lo explica en una linea. La direccion se toma de `CHAT_URL_PUBLICA` si no se indica.

## De 1.7.11 a 1.7.12 — un solo canal de aviso y el candado del contrato al día

Actualización corta: no hay nada que configurar. Corrige un error nuestro de la versión anterior.

### 1. Traer el código y reiniciar el chat

```
git fetch --tags && git checkout v1.7.12
systemctl restart maquita-chat
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8790/healthz    # 200
```

### 2. Si engancharon `aviso_chat`, cámbienlo por `notificacion`

En 1.7.11 anunciamos el evento `aviso_chat` creyendo que el servidor solo avisaba dentro de la
conversación abierta. **No era así**: ya emitía `notificacion` a la sala personal de cada
destinatario en los dos caminos de envío, y con más información (título, texto, enlace absoluto,
avatar, `es_grupo` y `silencioso` cuando la persona tiene «no molestar»). El fallo estaba en
nuestro cliente web, que escuchaba `notification`, en inglés, que no existe.

`aviso_chat` se retira en esta versión. Si lo engancharon en estas horas:

```
socket.on('notificacion', function (d) { ... });   // en vez de 'aviso_chat'
```

Y conviene respetar la marca de «no molestar»: si llega `silencioso: true`, mostrar el contador
pero no sonar.

### 3. Comprobación del contrato de la aplicación de escritorio (T-47)

El candado que lo protege fabricaba su vale sin `sid` ni `av`, que la regla de sesión exige desde
F-03, así que daba rojo sin haber nada roto. Ya está al día:

```
humo-notificaciones            # o: python3 chat-service/humo_notificaciones.py <conversacion>
```

Debe terminar en «TODO OK - 0 fallas», con las dos conexiones simultáneas (navegador y
aplicación) recibiendo el aviso.

### Dos cosas para quien mantenga clientes propios

- **El vale de sesión tiene que llevar `sid` y `av`.** Sin ellos el socket se rechaza en el
  handshake con `sesion central no valida`. El vale que emite el correo al iniciar sesión ya los
  trae: basta con usar el vigente y no uno guardado.
- **Un vale firmado con una clave anterior a una rotación se rechaza** con firma inválida. Ante
  ese motivo concreto, el cliente debe forzar entrada nueva en vez de reintentar: reintentando
  deja miles de rechazos al día en el registro y no se recupera solo.

## De 1.7.10 a 1.7.11 — el chat avisa de verdad y deja de perder el primer mensaje

Cuatro pasos, en este orden. Los tres primeros se pueden hacer con gente conectada; el cuarto
corta el chat unos segundos.

### 1. Panel: quitar `NoNewPrivileges` de su confinamiento

Si el panel corre con usuario propio (fase 2 de A-15) y su unidad lleva `NoNewPrivileges=yes`,
**ninguna** operación privilegiada funciona: crear un buzón, cambiar cuotas, reiniciar servicios
o mirar la cola devuelven «Error interno del servidor».

```
systemctl show maquita-admin -p User -p NoNewPrivileges
```

Si responde `User=maquita-admin` y `NoNewPrivileges=yes`, edita el confinamiento
(`deploy/hardening/systemd/maquita-admin-confinamiento.conf` ya viene corregido en esta versión),
recarga y reinicia:

```
systemctl daemon-reload && systemctl restart maquita-admin
```

Comprobación (debe devolver un hash `{SHA512-CRYPT}$6$…`):

```
sudo -u maquita-admin sudo -n /usr/local/sbin/maquita-sudo doveadm pw -s SHA512-CRYPT -p prueba
```

Si dice `the "no new privileges" flag is set`, el ajuste sigue puesto en algún otro fragmento
de la unidad.

### 2. Traer el código y reconstruir el panel

```
git fetch --tags && git checkout v1.7.11
cd admin-panel/frontend && npx vite build && cd ../..
```

### 3. Servicio de chat: nada que configurar, pero conviene saber qué cambia

- La lista de personas (`/api/chat/trabajadores/activos`) devolvía **cero** si en tu nómina el
  estado está escrito distinto de `ACTIVO`, y además devolvía el id de NÓMINA como si fuera el
  de la cuenta del chat. Si esa lista se usaba en alguna pantalla vuestra, revisad que ahora
  llega el id de la cuenta (campo `id`) y el de nómina aparte (`trabajador_id`).
- El aviso de mensaje nuevo se emite ahora también a la sala personal `user_<id>` con el evento
  `aviso_chat`. Es un evento NUEVO: si vuestro cliente no lo escucha, no cambia nada; si queréis
  el aviso fuera de la conversación abierta, engancharlo es una línea.

### 3b. Si el chat corre en su propia máquina (o queréis moverlo)

Esta versión publica lo que faltaba para instalarlo sin adivinar: unidad de systemd,
configuración de ejemplo con todas las variables explicadas, las dos formas de publicarlo en
nginx y un instalador guiado.

```
bash chat-service/deploy/instalar.sh
```

La guía completa, con comprobaciones y casos negativos, está en `docs/CHAT-INSTALACION.md`.
Dos cosas que conviene mirar aunque ya lo tengáis montado: la puerta `/chat/entrar` debe estar
publicada en el vhost de la aplicación que muestra el chat (sin ella, sus páginas no consiguen
sesión y el chat sale vacío), y el cliente de Socket.IO no se sirve en `/socket.io/socket.io.js`.

### 4. Reiniciar el chat (unos segundos de corte)

```
systemctl restart maquita-chat
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8790/healthz    # 200
```

### Comprobaciones, con sus casos negativos

**Positivo, el que estaba roto**: con dos cuentas que NO tengan conversación previa, escribid la
primera del tirón (crear conversación y enviar seguido, que es lo que hace la interfaz). El
mensaje debe guardarse. Antes se rechazaba con «No tienes acceso a esta conversacion» y se perdía.

```
journalctl -u maquita-chat | grep "participacion confirmada en base"
```

**Negativo 1**: pedid `join_conversation` de una conversación en la que la cuenta no participa.
Debe seguir respondiendo `No autorizado`; la comprobación se reforzó, no se relajó.

**Negativo 2**: con la conversación silenciada por el destinatario, enviad un mensaje. No debe
salir `aviso_chat` para esa persona.

```
journalctl -u maquita-chat | grep aviso_chat
```

**Negativo 3**: parad la base un instante y enviad a una conversación nueva. Debe rechazarse
(fallo cerrado), nunca dejar pasar por no poder comprobar.

Pruebas automáticas nuevas del bloque: 34 (`chat-service/tests/test_directorio_nomina.py`,
`test_aviso_personal.py`, `test_participacion.py`).

## De 1.7.9 a 1.7.10

Tres cambios, ninguno obligatorio para el correo en sí.

1. **Panel, alta de buzón**: la dirección se compone con el nombre de la cuenta más un dominio
   elegido de la lista del servidor. No hace falta nada: basta con reconstruir el panel.

   ```
   cd /opt/maquita-webmail/admin-panel/frontend && npx vite build
   ```

2. **Outlook nuevo**: si el acceso a 443/143/993/465/587 está limitado por país, el Outlook nuevo
   no funciona, porque sincroniza desde la nube de Microsoft. Instala la excepción:

   ```
   install -m 750 deploy/tools/ms-outlook-rangos.sh /usr/local/sbin/ms-outlook-rangos.sh
   /usr/local/sbin/ms-outlook-rangos.sh
   nft insert rule inet filter input tcp dport '{ 143, 443, 465, 587, 993 }' \
       ip saddr @nube_microsoft counter accept
   nft list ruleset > /etc/nftables.conf
   printf '#!/bin/sh\n/usr/local/sbin/ms-outlook-rangos.sh\n' > /etc/cron.weekly/ms-outlook-rangos
   chmod 755 /etc/cron.weekly/ms-outlook-rangos
   ```

   Comprobación: `nft list set inet filter nube_microsoft | grep -c /` debe pasar de 8, y el contador
   de la regla sube al añadir una cuenta desde el Outlook nuevo.

3. **Puerta del chat (N-24)**: el servicio admite ahora vales de emisores declarados. Si otro sistema
   propio (por ejemplo Raíces) va a entrar al chat, dale `CHAT_SSO_SECRET` (el secreto DEDICADO, nunca
   el del correo) y que emita el vale con `iss` igual a `raices` y su propio `sid`. Opcional:
   `CHAT_SESION_EXTERNA_MAX_SEG` (12 h por omisión) para el tope absoluto de esas sesiones.

   Reinicia el servicio de chat (`systemctl restart maquita-chat`) y comprueba:

   ```
   journalctl -u maquita-chat | grep "sso/entrar"    # vales rechazados y su motivo
   ```

   Negativos que deben fallar: un vale con `iss` de un emisor no declarado, uno sin `sid` y uno
   reutilizado devuelven 401.

### Además, en esta versión: Nextcloud retirado del todo (N-20)

Nextcloud retirado del todo (N-20): ya no hay «Guardar en Nube» en el webmail, ni sección de Nextcloud en el
panel, ni rutas `/api/nextcloud/*`. Nada que hacer al actualizar salvo limpieza opcional:
`NC_BASE_URL`, `NC_ADMIN_USER`, `NC_ADMIN_PASS` y `NC_PUBLIC_URL` sobran en `backend/.env` y en el `.env` del
panel; la tabla `nextcloud_accounts` de `maildb` puede borrarse (`DROP TABLE nextcloud_accounts`) y las columnas
`nc_*` de `office_config` quedan vacías.

## De 1.7.8 a 1.7.9 — correcciones de Andes, Drive desde el panel, Radicale con acceso por cabecera

Si vienes de 1.7.7, haz primero «De 1.7.7 a 1.7.8» (ya corregida: incluye Radicale con
`http_x_remote_user`, la migración de prefijos y el vhost de Z-Push). Desde 1.7.8:
`git fetch --tags --force && git checkout v1.7.9 && bash deploy-webmail.sh`, `systemctl restart
maquita-almacen maquita-admin`, y después:

Drive desde el panel (vincular buzones y cuota): un secreto nuevo, el mismo en dos ficheros.
1. `S=$(openssl rand -hex 24); echo "ALMACEN_SECRETO_PANEL=$S" >> almacen/.env; printf
   ALMACEN_URL=http://127.0.0.1:8788
ALMACEN_SECRETO_PANEL=%s
 "$S" >> admin-panel/backend/.env`.
2. `systemctl restart maquita-almacen maquita-admin` y reconstruir el frontend del panel
   (`cd admin-panel/frontend && npx vite build`). Sin el secreto, el alta de buzón sigue funcionando y
   el formulario lo dice.
3. La cuota por defecto del Drive en instalaciones nuevas es 5 GB (`ALMACEN_CUOTA_DEFECTO` o Configuración
   del Almacén); las existentes conservan la suya.
4. Si usas Z-Push y vienes de 1.7.8 con Radicale en `auth type = none`: aplica el paso 5 de «De 1.7.7 a
   1.7.8» (config de referencia, migración de prefijos, vhost `radicale-zpush`) y el paso 4 (snippet
   `tls-intermedio.conf`). Comprueba el caso negativo del paso 6: la principal por el puente con la
   política activa → 401.
5. Egreso del backend (`deploy/webmail/nftables/egreso-backend.nft`): si lo instalas, ajusta
   `ALLOWLIST_INTERNA` y mira `journalctl -k | grep EGRESO_BACKEND_DENEGADO` unos días antes de dar la
   lista por buena.

## De 1.7.7 a 1.7.8 — Z-Push vuelve, contraseñas de aplicación, firmas, autodiscover por dominio

En orden de ejecución (cada paso usa ficheros que llegan con el paso anterior). Corte: **ninguno para
los usuarios del webmail** salvo el `systemctl restart dovecot` del paso 2 (unos segundos de IMAP/SMTP)
y el reinicio de Radicale del paso 5. Migración: una (`2026-09-07-contrasenas-aplicacion.sql`).

0. **Código y backend**: `git fetch --tags --force && git checkout v1.7.8 && bash deploy-webmail.sh`.
   El backend trae el autodiscover con ActiveSync, las contraseñas de aplicación y las firmas.
   Reinicia también el panel: `systemctl restart maquita-admin`.

1. **Vigilancia horaria de integraciones** (la instala el instalador, no la actualización):
   `install -m644 deploy/hardening/cron-vigilar-integraciones /etc/cron.d/maquita-integraciones` y
   `install -m644 deploy/hardening/cron-radicale-colecciones /etc/cron.d/maquita-radicale`. Prueba a mano:
   `backend/venv/bin/python deploy/hardening/vigilar-integraciones.py`: cada sonda en `OK` o, si esa
   integración no existe en tu instalación (sin IA, sin OnlyOffice…), en `NO_CONFIGURADA`, que también es válido.

2. **Contraseñas de aplicación (D-5)**:
   - `sudo -u postgres psql -d maildb -c "CREATE EXTENSION IF NOT EXISTS pgcrypto"` y la migración como
     `mailserver`: `psql "$(grep -m1 '^DATABASE_URL=' backend/.env | cut -d= -f2-)" -f
     migrations/2026-09-07-contrasenas-aplicacion.sql`.
   - Dovecot: las dos `passdb` de `deploy/webmail/configs/dovecot.conf` (la principal con la condición
     de IP y política; `contrasenas_aplicacion` con la función) y **`systemctl restart dovecot`**, no
     `doveadm reload`: con el reload, Dovecot 2.4 se queda en un estado intermedio que **acepta cualquier
     login** (usuario inexistente, contraseña inventada) hasta el reinicio (informe de Andes, 07/09).
   - Comprobar SIEMPRE con un caso positivo y uno negativo. Para el positivo hace falta una contraseña de
     aplicación: crea una de prueba en `Configuración → Seguridad` de tu propia cuenta y revócala después.
     `doveadm auth test -x rip=1.2.3.4 usuario clave-de-aplicacion` → `auth succeeded`;
     `doveadm auth test -x rip=1.2.3.4 usuario clave-mala` → `auth failed`;
     `doveadm auth test -x rip=1.2.3.4 noexiste@dominio x` → `auth failed`.
     Si el negativo no rechaza, no sigas: reinicia Dovecot y repite.
   - Avisar al personal (guía `docs/CONTRASENAS-APLICACION.md`), dar tiempo a crear las suyas y después
     `maquita-mailadm auth apppass-policy on`: la principal deja de valer fuera del webmail.

3. **Firmas (normalización automática)**:
   - `install -d -o www-data -g maquita-admin -m 2775 /var/lib/maquita-webmail/firmas`. Sin usuario
     `maquita-admin` (panel como root): `-g www-data`; el panel escribe igual (comprobado).
   - Migrar las firmas existentes: `cd backend && venv/bin/python ../deploy/tools/firmas-normalizar.py`
     (cuenta) y después `--aplicar`. Sin dependencias nuevas.

4. **Autodiscover para todos los dominios (N-16)**:
   - `install -m644 deploy/webmail/nginx/tls-intermedio.conf /etc/nginx/snippets/tls-intermedio.conf`
     (el vhost lo incluye; hasta ahora solo existía en nuestros servidores).
   - `sed "s/tudominio.com/<dominio canónico>/g" deploy/webmail/nginx/autodiscover-dominios.conf >
     /etc/nginx/sites-available/autodiscover-dominios`; **sin certificado de Let's Encrypt** (VM de
     evaluación) cambia sus dos rutas `/etc/letsencrypt/live/mail.<dominio>/…` por
     `/etc/ssl/certs/ssl-cert-snakeoil.pem` y `/etc/ssl/private/ssl-cert-snakeoil.key`, como hace el
     instalador; enlazar en `sites-enabled`, `nginx -t`, recargar.
   - Por cada dominio de correo que ya apunte aquí: `DOMINIOS_EXTRA="..." bash
     deploy/webmail/tls/emitir-certificado.sh <canónico>` (tras esperar el TTL del DNS).
   - `backend/venv/bin/python deploy/tools/comprobar-autodiscover.py` (desde cualquier directorio): estado
     dominio por dominio.

5. **Z-Push (ActiveSync) y Radicale**:
   - Radicale: `/etc/radicale/config` como `deploy/webmail/configs/radicale.config` (`hosts =
     127.0.0.1:5232` **solo**, `auth type = http_x_remote_user`; **nunca `none`**, que deja el calendario
     de todos abierto a cualquier proceso local) y `systemctl restart radicale`. Todo `/var/lib/radicale`
     debe ser del usuario con el que corre el servicio (`systemctl show radicale -p User`); con otro
     dueño responde 500.
   - Las colecciones pasan a llamarse por el correo completo (el mismo árbol que usa Z-Push):
     `cd backend && venv/bin/python ../deploy/tools/radicale-migrar-prefijo.py` (cuenta) y `--aplicar`.
   - `bash deploy/z-push/instalar.sh <dominio>`: construye la imagen, escribe `/opt/z-push-docker/*.php`,
     arranca el contenedor `zpush` en `127.0.0.1:9000`, instala el snippet de nginx, el vhost
     `radicale-zpush` en la IP del puente (`auth_request` al backend) y crea las colecciones base
     (`radicale-asegurar-colecciones.py --todos`, con el venv del backend). Si ya tenías Z-Push nativo
     (pool PHP-FPM, `/opt/z-push`, `location` con `php8.4-zpush.sock`), retíralos.
   - nginx: si el `server{}` HTTPS del correo ya tiene `include /etc/nginx/snippets/maquita-apps/*.conf;`
     (lo escribe el instalador para el Drive), **no añadas nada**: el snippet entra por el glob y un
     `include` explícito duplica la `location`. Solo si no está el glob: `include
     snippets/maquita-apps/activesync.conf;`. El `location` del autodiscover debe admitir `.xml` **y**
     `.json`: `sed -i 's#\[Aa\]utodiscover\\.xml\$#[Aa]utodiscover\\.(xml|json)#' /etc/nginx/sites-available/<tu vhost>`
     (queda como en `deploy/webmail/nginx/webmail.conf`). `nginx -t && systemctl reload nginx`.
   - Cortafuegos: antes de los `drop` por país en la cadena `input`, `iifname "docker0" tcp dport
     { 465, 993, 5232 } accept` (persistir en `/etc/nftables.conf`).

6. **Comprobar** (todo en `OPERACION.md`, «Z-Push / ActiveSync»): `OPTIONS /Microsoft-Server-ActiveSync`
   → 401; autodiscover `mobilesync` → `<Type>MobileSync</Type>`; JSON v2 → `"Protocol":"ActiveSync"`;
   `curl -X PROPFIND http://<ip del puente>:5232/` → 401, con `-u correo:clave-de-aplicacion` → 207 y, con la
   política de contraseñas de aplicación activa, con `-u correo:contraseña-principal` → **401** (si da 207,
   el puente está aceptando la principal: revisa el backend);
   y la **prueba real con una cuenta en los dos Outlook, iPhone y Android** con una contraseña de
   aplicación (correo, calendario en los dos sentidos, contactos, tarea).

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
4. Comprobar: `grep MAQUITA_SUDO /var/log/auth.log` (o, sin rsyslog, como en Debian 13 por defecto:
   `journalctl -t maquita-sudo`) muestra `ok` al usar el panel (fail2ban, cola);
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
   `security.log`; `SELECT count(token_moderador) FROM reuniones_programadas` devuelve 0 (si la tabla
   no existe, nunca se programó una reunión: el guion dice «nada que purgar» y no hay nada que comprobar);
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
