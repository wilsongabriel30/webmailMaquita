# Instalar el servicio de chat en su propia máquina

Guía completa, paso a paso y en orden de ejecución. Cada paso trae su comprobación y, donde
importa, el caso negativo: lo que **no** debe funcionar. Si un paso no da lo que dice aquí, no
sigas al siguiente.

El chat corre aparte del correo a propósito: así un fallo en el chat no alcanza a los buzones.
No tiene lista de usuarios propia ni contraseñas: reconoce a cada persona por el **correo** que
figura en la tabla `usuarios` de la plataforma.

## 0. Antes de empezar

Necesitas:

- Una máquina con Python 3.11 o superior, `git` y `curl`.
- PostgreSQL accesible: la base del chat y la base de usuarios de la plataforma.
- Redis accesible. **No es opcional**: sin Redis no hay uso único de los vales de entrada y la
  puerta se cierra a propósito (fallo cerrado).
- Un nombre para el chat (por ejemplo `mensajeria.tudominio.org`) con su certificado, si vas a
  publicarlo en su propio origen.

## 1. Traer el código

```
git clone <repositorio> /opt/maquita-webmail
cd /opt/maquita-webmail && git checkout "$(git tag --sort=-v:refname | head -1)"   # la última etiqueta
```

Si solo quieres el chat, basta con una copia dispersa de `chat-service/`.

**Comprobación**: `ls /opt/maquita-webmail/chat-service/app_chat.py` existe.

## 2. Base de datos: crear las tablas

El chat usa las tablas `chat_*` (conversaciones, participantes, mensajes, estados) y **lee** la
tabla `usuarios`. Si vienes de una instalación con el chat dentro de la plataforma, no hay que
migrar nada: son las mismas tablas.

En una instalación nueva **hay que crear la base y las tablas**, y esto es más importante de lo
que parece: sin ellas el servicio arranca igual y responde a `/healthz`, pero cualquier petición
real devuelve «Error interno del servidor». Le pasó a un equipo durante semanas.

```
# 1) La base, si no existe (como usuario postgres)
sudo -u postgres createuser --pwprompt chat
sudo -u postgres createdb -O chat chat_maquita

# 2) Las tablas del chat
cd chat-service
venv/bin/python3 migrar_chat.py        # idempotente: se puede repetir sin miedo

# 3) Las personas: el chat no tiene lista propia, la copia del directorio del correo
DATABASE_URL=... USERS_DB_URL=... venv/bin/python3 sincronizar_usuarios.py
```

`sincronizar_usuarios.py` mira qué hay al otro lado: si la fuente tiene `usuarios`, la usa; si
apuntas a la base del **correo**, usa su tabla `mailbox` (el buzón es el correo y su nombre, el
nombre). Sin este paso el chat no reconoce a nadie, aunque todo lo demás esté bien.

Después, comprobar:

```
psql "$DATABASE_URL" -c "\dt chat_*"
psql "$USERS_DB_URL" -c "SELECT count(*) FROM usuarios WHERE active = true"
```

**Comprobación**: la primera lista las tablas del chat; la segunda devuelve un número mayor que
cero. Si devuelve cero, el chat no reconocerá a nadie.

**El propio servicio lo delata**: `/healthz` responde **503** con `"base": "sin_tablas"` mientras
falten, y 200 solo cuando la base está utilizable. Si vigiláis el servicio, vigilad ese 200.

## 3. Instalar el servicio

```
bash /opt/maquita-webmail/chat-service/deploy/instalar.sh
```

La primera vez crea `.env` a partir del ejemplo y **se detiene** para que lo rellenes. Genera
cada secreto por separado:

```
openssl rand -hex 32      # una vez por cada secreto, nunca el mismo valor dos veces
```

Los tres secretos del chat son distintos a propósito: comprometer uno no da los otros.

**Ojo con el modo integrado.** Lo de arriba vale para el chat en su propia máquina. Cuando el
chat va dentro de la plataforma del correo, la sesión funciona porque `CHAT_JWT_SECRET` es
**la misma** clave con la que el correo firma (`SECRET_KEY`), y `CHAT_SSO_SECRET` puede no
existir, porque nadie usa la puerta de entrada: la cookie del correo llega sola. Resumen:

| | Integrado (mismo origen) | Separado (origen propio) |
|---|---|---|
| `CHAT_JWT_SECRET` | la `SECRET_KEY` del correo | la `SECRET_KEY` del correo |
| `CHAT_SSO_SECRET` | opcional (no se usa la puerta) | **obligatorio** |
| `CHAT_SESSION_KEY` | propio del chat | propio del chat |

Si rotáis la `SECRET_KEY` del correo, **hay que actualizar y reiniciar el chat**: nos ha pasado
dos veces que un servicio se quedaba con la clave anterior en memoria y rechazaba a todo el mundo.

| Variable | Para qué |
|---|---|
| `CHAT_JWT_SECRET` | reconocer la sesión que emite la plataforma |
| `CHAT_SSO_SECRET` | la puerta de entrada (`/sso/entrar`), vale de un solo uso |
| `CHAT_SESSION_KEY` | la cookie propia del chat (`chat_session`) |
| `NOTIF_SECRET` | avisos entre servicios y revocación de sesiones |

Vuelve a ejecutar el instalador cuando el `.env` esté completo.

**Comprobación**:

```
systemctl is-active maquita-chat                                   # active
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8790/healthz   # 200
```

**Negativo**: `curl http://<ip-de-la-maquina>:8790/healthz` desde otra máquina **no** debe
responder. El servicio se publica por nginx, no directamente.

Desde esta versión el chat escucha **solo en loopback** salvo que se le diga otra cosa. Si tu
proxy vive en OTRA máquina (nuestro caso), indícale la interfaz y **acota con el cortafuegos**,
que el servicio por sí solo no lo hace:

```
# .env del chat
CHAT_BIND=10.0.0.10          # la interfaz por la que lo alcanza el proxy

# y en el cortafuegos, solo desde el proxy
nft add rule inet filter input tcp dport 8790 ip saddr 10.0.0.5 accept
```

## 4. Publicarlo en nginx

Dos formas, y se pueden usar a la vez:

- **En su propio origen** (`deploy/nginx-chat-origen-propio.conf`): para el cliente de escritorio
  y para abrirlo suelto. Ajusta `frame-ancestors` con los sitios que pueden enmarcarlo.
- **Dentro de otra aplicación** (`deploy/nginx-chat-consumidor.conf`): pega esos bloques en el
  vhost del correo o de la plataforma. Incluyen la puerta `/chat/entrar`, sin la cual las páginas
  de esa aplicación no consiguen sesión y el chat sale vacío.

```
nginx -t && systemctl reload nginx
```

**Comprobación**: `https://<chat>/sso/entrar` responde **401** (sin vale, correcto).
**Negativo**: `https://<chat>/api/chat/conversations` sin sesión responde 401, nunca 200.

## 5. Que la plataforma abra sesión en el chat

Quien quiera mostrar el chat emite un **vale** firmado con `CHAT_SSO_SECRET` y manda a la
persona a `/chat/entrar?t=<vale>&r=<a dónde volver>`. El vale lleva:

| Campo | Valor |
|---|---|
| `sub` | correo de la persona (el de la tabla `usuarios`) |
| `iss` | quién emite: `correo` o `raices` |
| `sid` | identificador de la sesión de quien emite (obligatorio si `iss` no es `correo`) |
| `aud` | `chat-sso` |
| `jti` | identificador único del vale |
| `exp` | 60 segundos |

El chat lo canjea por su sesión propia. Un vale caducado, repetido, de un emisor no declarado o
sin `sid` se rechaza.

**Comprobación**: al abrir la página de la aplicación, aparece la cookie `chat_session` y
`/api/chat/unread/count` responde 200.
**Negativo**: repite el mismo vale y debe dar 401.

## 5b. Cablear el correo con el chat (imprescindible)

Para que el correo emita el vale y muestre el chat, en el `.env` del **correo** hacen falta:

| Variable | Valor |
|---|---|
| `CHAT_SSO_SECRET` | el mismo del chat |
| `NOTIF_SECRET` | el mismo del chat |

Y en la configuración del chat del panel (`chat_settings`), `embed_url` apuntando al origen del
chat (`https://mensajeria.<dominio>/chat/?embed=1`) si vive aparte. Reinicia el correo después.

**Confianza TLS entre los dos.** El chat revalida cada sesión contra el correo
(`CORREO_URL_API` + `/api/auth/sesion-servicio`) y **falla cerrado**: si no puede comprobar,
cierra la sesión. Con un certificado autofirmado, esa llamada falla por TLS y **todas las
sesiones del chat mueren a los 300 segundos** con `SESION_NO_REVALIDABLE`. Dos salidas:

- certificado de confianza en el correo (lo normal en producción), o
- en evaluación, `CORREO_URL_API=http://127.0.0.1:8000` si comparten máquina.

## 6. Cerrar sesiones cuando la persona sale

Cuando alguien cierra sesión en la plataforma (o se cambia de identidad), avisad al chat:

```
POST /api/chat/sesion/revocar
Cabecera: X-Notif-Secret: <NOTIF_SECRET>
Cuerpo:   {"user": "<correo>", "sid": "<sid>"}          # una sesión concreta
Cuerpo:   {"user": "<correo>", "sid": "*"}              # todas las suyas
```

**Qué significa «todas»**: se cierra lo que esa persona tenga abierto EN ESE MOMENTO. Puede
volver a entrar en el acto; no queda bloqueada. (Hasta la 1.7.15 la marca duraba 24 horas y
tumbaba también las sesiones nuevas.)

**Comprobación**: responde 200 y esa sesión pasa a 401 en la siguiente petición, también con
`"*"`. (Hasta la 1.7.14, `"*"` sin el campo `av` respondía 200 y no revocaba nada: se anotaba la
generación 0 y ninguna sesión es anterior a 0. Corregido; si mandas `av` numérico, sigue
revocando solo lo anterior a esa generación.)
**Negativo**: sin la cabecera correcta responde 403.

## 7. Avisos: que se enteren sin mirar la pantalla

El chat emite por Socket.IO:

- `msg` y `new_message` a la sala de la conversación (quien la tiene abierta).
- **`notificacion` a la sala personal de cada participante** (contrato T-47): llega a cualquier
  ventana de esa persona, esté en la sección que esté, y es el mismo evento que usa la
  aplicación de escritorio. Trae `titulo`, `texto`, `url` lista para abrir, `conversacion_id`,
  `avatar` y, si la persona tiene «no molestar», `silencioso: true` (el aviso llega, pero el
  cliente no debe sonar). Es lo que hace que suene el aviso fuera del chat.

Quien tenga la conversación silenciada no recibe el evento: eso se resuelve en el servidor y el
cliente no tiene que filtrarlo. Silenciar se guarda en `chat_participants.is_muted`; hoy se
cambia desde la interfaz del chat y **no hay endpoint REST propio**, así que para una prueba se
pone por SQL:

```
UPDATE chat_participants SET is_muted = TRUE
 WHERE conversation_id = <conv> AND user_id = <persona>;
```

**`silencioso` no viene siempre**: solo llega, y con valor `true`, cuando esa persona tiene
puesto «no molestar» (nunca en menciones, llamadas ni reuniones, que se consideran urgentes).
La regla para el cliente es: **si llega `silencioso: true`, contador sin sonido; si no viene,
sonar**.

Si el chat vive en **otro origen**, el vhost del correo necesita además los bloques
«consumidor» (`deploy/nginx-chat-consumidor.conf`) o la burbuja del correo no lo encontrará: hasta
la 1.7.14 comprobaba la disponibilidad contra su propio origen, recibía 404 y se escondía con el
chat perfectamente vivo. Desde esa versión, si el correo ya conoce el origen del chat, la burbuja
no sondea nada.

Para engancharlo desde vuestra interfaz:

```
socket.on('notificacion', function (d) { /* sonido, contador, aviso del sistema */ });
```

Dos detalles que cuestan una tarde si no se saben: el cliente de Socket.IO **no** se sirve en
`/socket.io/socket.io.js` (ahí está el servidor, devuelve 400), hay que servir el fichero del
cliente; y los navegadores no dejan sonar a una página que no ha recibido un clic, así que hay
que «preparar» el audio en el primer clic de la persona.

## 8. Lo que conviene comprobar el primer día

| Prueba | Qué debe pasar |
|---|---|
| Escribir a alguien con quien no hay conversación previa | el mensaje se guarda a la primera |
| Escribir estando la otra persona en otra sección | suena el aviso y sube el contador |
| Silenciar la conversación y escribir | no suena para quien la silenció |
| Pedir una conversación ajena (`join_conversation`) | `No autorizado` |
| Parar Redis y entrar por la puerta | se rechaza (fallo cerrado) |

## 9. Cosas nuestras que quizá no necesites

- **Túnel a Redis**: si el chat y la plataforma comparten cola de Socket.IO en máquinas
  distintas, nosotros lo resolvemos con un túnel SSH dedicado (`faro-redis-tunnel`). Con Redis
  accesible en red no hace falta.
- **Nómina**: la lista de personas puede salir de una tabla de nómina. Si no la configuras, el
  buscador funciona igual y sale de `usuarios`.
- **Llamadas y GIF**: LiveKit, Jitsi y la biblioteca de GIF son opcionales; sin sus variables
  esas funciones no aparecen.

## Ejecutar el candado del contrato de notificaciones

`humo_notificaciones.py` comprueba que un mensaje llega a TODAS las ventanas de la persona
(navegador y aplicación a la vez). Para correrlo hacen falta dos cosas:

- la dependencia `websocket-client` (ya viene en `requirements.txt` desde la 1.7.16);
- que el origen desde el que conectas esté en `CHAT_CORS_ORIGENES`.

```
HUMO_BASE=https://chat.ejemplo.org \
HUMO_DESTINO=quien.recibe@ejemplo.org \
HUMO_REMITENTE=quien.escribe@ejemplo.org \
HUMO_CONVERSACION=12 \
venv/bin/python3 humo_notificaciones.py
```
