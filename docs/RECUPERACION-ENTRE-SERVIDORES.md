# Recuperación de correo entre servidores

«Recuperar mensaje» retira un correo enviado por error del buzón del destinatario. Dentro de un mismo servidor
funciona para todos sus dominios. Desde esta versión funciona también **entre servidores distintos que usan esta
suite**: no hay que registrarse en ningún sitio ni intercambiar claves.

## Qué ve la persona

- Abre el correo en «Enviados» → «Recuperar mensaje». Si el destinatario está en otro servidor compatible, la
  comprobación dice «Otro servidor compatible: se intentará retirar de su buzón…».
- Al confirmar: «Recuperado del servidor del destinatario» o, si ya pasó el plazo de ese servidor, «Fuera de plazo».
- Si el destinatario **ya lo había leído** y su servidor no retira correos leídos (es lo normal entre
  organizaciones distintas), el correo se queda en su buzón y recibe el aviso de «enviado por error».
- Si el otro servidor no es compatible, no responde o rechaza la petición, el destinatario recibe en la misma
  conversación el aviso de «enviado por error» (como cualquier externo).

## Cómo se ponen de acuerdo los servidores

Remitente en el servidor **A**, destinatario en el servidor **B**. El servidor de un dominio es el de su registro MX
y se le habla por HTTPS con certificado válido.

1. A pregunta a B: `GET https://<MX de B>/api/federacion/v1/recuperacion` → `{"version":1,"activo":true}`.
2. A guarda una solicitud con un testigo de un solo uso (2 minutos) y la envía:
   `POST …/recuperacion/solicitar` `{token, message_id, remitente, destinatario}`.
3. B comprueba, en este orden:
   - el destinatario es un buzón suyo y el correo está en ese buzón;
   - **B mismo** autenticó ese correo al recibirlo (DKIM o DMARC del dominio del `From`), según su propia cabecera
     `Authentication-Results` (la más alta; las que traiga el correo no cuentan);
   - el servidor del dominio del `From` (su MX) confirma la solicitud:
     `POST https://<MX del remitente>/api/federacion/v1/recuperacion/confirmar` → `{"confirmado":true}`;
   - el correo sigue dentro del plazo de recuperación **de B** (`RECALL_MAX_MINUTOS`, 60 por defecto);
   - si el destinatario ya lo leyó, **la política de B** permite retirarlo (ver «Correos ya leídos»).
4. B retira el correo, refresca la bandeja del destinatario y lo anota en su auditoría; A anota la suya.

Cualquier fallo responde `{"estado":"no_recuperado"}`, sin detalles, para no revelar qué buzones o correos existen.

## Correos ya leídos: decide el servidor del destinatario

Entre organizaciones distintas, hacer desaparecer un correo que la persona ya leyó es decisión del servidor
que lo recibió, no del que lo pide:

- **Por defecto no se retira.** B responde `{"estado":"leido_no_retirado","leido":true}`, el correo se queda en el
  buzón y A envía al destinatario el aviso de «enviado por error», igual que a un servidor no compatible. Un
  servidor A con una versión anterior no conoce ese estado y hace lo mismo: envía el aviso.
- **Opción de cada instalación:** `RECALL_FEDERADO_RETIRAR_LEIDOS=true` lo permite para cualquier servidor;
  `RECALL_FEDERADO_DOMINIOS_CONFIANZA=socio.org,filial.org` lo permite solo cuando el correo viene de esos dominios
  (el dominio del `From`, que B ya autenticó y cuyo servidor confirmó la solicitud).
- La comprobación previa («¿se puede recuperar?») no revela si el correo fue leído: eso solo se sabe al ejecutar
  una solicitud confirmada.
- Dentro de una misma instalación (todos sus dominios) no cambia nada: se retira aunque se haya leído, dentro del plazo.

## Auditoría en el servidor del destinatario

Toda solicitud confirmada que llega de otro servidor queda en `audit_log` de B (acción `message_recall`), se retire
o no y aunque al destinatario no se le muestre nada: quién lo pidió (`admin_user` = remitente), cuándo, qué
Message-ID (`target`), desde qué IP y, en `details`, el destinatario, el resultado, si estaba leído, las carpetas,
`pedido_por_otro_servidor: true`, `dominio_solicitante` y `retirado`.

## Por qué es seguro

- Solo se retira un correo que el servidor del destinatario recibió y autenticó como del dominio que lo pide: nadie
  puede retirar correos de terceros.
- La petición solo vale si la confirma el servidor del dominio remitente, y ese servidor solo emite solicitudes para
  una persona con sesión iniciada que tiene ese correo en sus «Enviados».
- Cada servidor aplica su propio plazo y decide sobre sus propios buzones; ninguno da acceso al otro.
- Las llamadas salen solo hacia direcciones públicas (no sirven para alcanzar la red interna), sin redirecciones, con
  límite de peticiones por IP.

## Configuración (`backend/.env`)

| Variable | Por defecto | Para qué |
|---|---|---|
| `RECALL_ENTRE_SERVIDORES` | `true` | `false` apaga la función en los dos sentidos (los puntos de entrada responden 404). |
| `RECALL_MAX_MINUTOS` | `60` | Plazo de recuperación de este servidor. |
| `RECALL_FEDERADO_RETIRAR_LEIDOS` | `false` | `true`: se retiran también los correos ya leídos cuando lo pide otro servidor. |
| `RECALL_FEDERADO_DOMINIOS_CONFIANZA` | vacío | Dominios (separados por coma) a los que sí se les permite retirar correos ya leídos. |
| `RECALL_FEDERADO_HOSTS_INTERNOS` | vacío | Nombres MX de servidores hermanos que se alcanzan por la red privada (separados por coma). |
| `RECALL_FEDERADO_AUTHSERV` | vacío | Nombres (separados por coma) con que este servidor firma `Authentication-Results`. Vacío: el de la URL pública, el de la máquina y el `myhostname` de Postfix, que es el que usa rspamd. Si se indica, valen solo esos. |

## Requisitos

- El host del registro MX de cada dominio debe servir `https://<MX>/api/` con certificado válido (en una instalación
  normal es el mismo host del webmail). Un dominio alojado cuyo MX tiene otro nombre necesita ese nombre en nginx y
  en el certificado.
  - **MX con nombre distinto al del correo web** (p. ej. correo web en `webmail.ejemplo.org`, MX en
    `mail.ejemplo.org`): las llamadas no siguen redirecciones, así que un MX que responde 301 hacia el correo web
    deja la federación sin funcionar y sin ningún error visible. Con un certificado que cubra los nombres del MX:
    `sudo bash deploy/tools/federacion-mx-nginx.sh mail.ejemplo.org mail2.ejemplo.org`
    (añade un `server` que solo atiende `/api/federacion/` en esos nombres; plantilla
    `deploy/webmail/nginx/federacion-mx.conf`). Se intentan los dos primeros MX por prioridad: conviene que ambos
    respondan. `deploy/tools/validar-despliegue.sh` avisa si el MX de un dominio alojado redirige o no responde.
- rspamd debe añadir la cabecera `Authentication-Results` a lo que entra: lo deja así el ajuste
  `deploy/ajustes/80-rspamd-cabecera-de-autenticacion.sh`, que el actualizador aplica solo.
- El correo debe salir firmado con DKIM (la instalación lo deja así) para que el otro servidor lo autentique.
- Salida HTTPS (443) desde el backend hacia los otros servidores.

## Reacciones entre servidores

Las reacciones a un correo (👍 ❤️ 🎉 😂 😮 😢) usan el mismo esquema: cuando alguien reacciona, su servidor
avisa a los servidores de la suite de las demás personas del correo (`POST /api/federacion/v1/reacciones/avisar`).
El servidor que recibe el aviso solo lo acepta si:

- alguno de los destinatarios indicados es un buzón suyo y tiene ese correo;
- quien reacciona figura en el De/Para/CC de la copia guardada allí;
- el servidor del dominio de esa persona confirma el aviso (`…/reacciones/confirmar`).

No se envía ningún correo. A los servidores que no usan la suite (Gmail, Outlook…) no se les envía nada.
`REACCIONES_ENTRE_SERVIDORES=false` lo apaga en los dos sentidos.
