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
cd /opt/maquita-webmail && git checkout v1.7.11
```

Si solo quieres el chat, basta con una copia dispersa de `chat-service/`.

**Comprobación**: `ls /opt/maquita-webmail/chat-service/app_chat.py` existe.

## 2. Base de datos

El chat usa las tablas `chat_*` (conversaciones, participantes, mensajes, estados) y **lee** la
tabla `usuarios`. Si vienes de una instalación con el chat dentro de la plataforma, no hay que
migrar nada: son las mismas tablas.

```
psql "$DATABASE_URL" -c "\dt chat_*"
psql "$USERS_DB_URL" -c "SELECT count(*) FROM usuarios WHERE active = true"
```

**Comprobación**: la primera lista las tablas del chat; la segunda devuelve un número mayor que
cero. Si devuelve cero, el chat no reconocerá a nadie.

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

## 6. Cerrar sesiones cuando la persona sale

Cuando alguien cierra sesión en la plataforma (o se cambia de identidad), avisad al chat:

```
POST /api/chat/sesion/revocar
Cabecera: X-Notif-Secret: <NOTIF_SECRET>
Cuerpo:   {"user": "<correo>", "sid": "<sid o *>"}
```

**Comprobación**: responde 200 y esa sesión pasa a 401 en la siguiente petición.
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
cliente no tiene que filtrarlo.

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
