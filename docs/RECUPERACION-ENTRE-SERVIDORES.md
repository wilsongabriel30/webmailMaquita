# Recuperación de correo entre servidores

«Recuperar mensaje» retira un correo enviado por error del buzón del destinatario. Dentro de un mismo servidor
funciona para todos sus dominios. Desde esta versión funciona también **entre servidores distintos que usan esta
suite**: no hay que registrarse en ningún sitio ni intercambiar claves.

## Qué ve la persona

- Abre el correo en «Enviados» → «Recuperar mensaje». Si el destinatario está en otro servidor compatible, la
  comprobación dice «Otro servidor compatible: se intentará retirar de su buzón…».
- Al confirmar: «Recuperado del servidor del destinatario» o, si ya pasó el plazo de ese servidor, «Fuera de plazo».
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
   - el correo sigue dentro del plazo de recuperación **de B** (`RECALL_MAX_MINUTOS`, 60 por defecto).
4. B retira el correo, refresca la bandeja del destinatario y lo anota en su auditoría; A anota la suya.

Cualquier fallo responde `{"estado":"no_recuperado"}`, sin detalles, para no revelar qué buzones o correos existen.

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
| `RECALL_FEDERADO_HOSTS_INTERNOS` | vacío | Nombres MX de servidores hermanos que se alcanzan por la red privada (separados por coma). |
| `RECALL_FEDERADO_AUTHSERV` | vacío | Nombre con que este servidor firma `Authentication-Results`, si no coincide con el de la URL pública. |

## Requisitos

- El host del registro MX de cada dominio debe servir `https://<MX>/api/` con certificado válido (en una instalación
  normal es el mismo host del webmail). Un dominio alojado cuyo MX tiene otro nombre necesita ese nombre en nginx y
  en el certificado.
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
