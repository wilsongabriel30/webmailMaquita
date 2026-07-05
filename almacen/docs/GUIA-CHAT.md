# Chat institucional: cómo funciona el botón flotante y cómo conectar el tuyo

> El correo y el explorador de archivos traen un **botón de chat flotante**
> (💬 abajo a la derecha). Este documento explica qué es, por qué quizás no
> lo ves, y cómo conectarle un chat a TU instalación.

## Qué incluye este proyecto (y qué no)

- ✅ **Incluido:** el botón flotante, el panel, y el patrón de integración
  (proxy bajo el mismo dominio + puente de identidad por cookie).
- ❌ **No incluido:** un servidor de chat. El botón **se autodetecta**: solo
  aparece si `/api/chat/conversations` responde en tu dominio. Si tu
  instalación no tiene chat, no verás el botón ni ningún error — todo lo
  demás (correo, archivos, Office) funciona completo sin él.

## El contrato: qué necesita el botón para aparecer

1. `GET /api/chat/conversations?limit=1` en TU dominio → responde 200 con la
   sesión del correo (la cookie `access_token`).
2. `GET /chat/` en tu dominio → una página web del chat (se abre en el panel;
   debe permitir iframes del mismo origen: `frame-ancestors 'self'`).
3. (Opcional) websockets del chat bajo tu dominio para tiempo real.

## Opción A — Ya tienes un sistema de chat en tu organización

Sigue el patrón de esta instalación:

1. **Proxy bajo el mismo dominio** (nginx del correo):
   ```nginx
   location ^~ /api/chat/ { proxy_pass https://TU-SERVIDOR-DE-CHAT; ... }
   location ^~ /chat/     { proxy_pass https://TU-SERVIDOR-DE-CHAT; ...
                            proxy_hide_header X-Frame-Options;
                            add_header Content-Security-Policy "frame-ancestors 'self';" always; }
   # + la ruta de websockets de tu chat, con Upgrade/Connection y timeouts largos
   ```
2. **Puente de identidad**: tu chat debe aceptar la sesión del correo. La
   cookie `access_token` es un JWT HS256 firmado con el `SECRET_KEY` del
   backend (payload: `sub` = correo del usuario, `type` = "access"). Un
   middleware en tu chat puede validarla y resolver el correo contra tu
   directorio de usuarios — exactamente lo que hace `auth_webmail.py` en el
   módulo del Almacén de este mismo repo (úsalo de referencia).
3. Nada más: el botón detecta `/api/chat` y aparece solo.

## Opción B — No tienes chat y quieres uno libre

Recomendación: **Matrix (servidor Synapse) + Element Web** — mensajería
libre y federada, con apps móviles, llamadas y cifrado, sin licencias:

```bash
# Servidor (Debian/Ubuntu, en una VM aparte o la misma):
apt install -y matrix-synapse-py3      # o vía docker: matrixdotorg/synapse
# Cliente web (una carpeta estática):
#   descargar element-web y servirlo en /chat/ de tu dominio
```

Para que la sesión sea única (sin segundo login) configura en Synapse un
proveedor JWT (`jwt_config`) con el mismo `SECRET_KEY` del correo — el
mismo principio del puente. Es un proyecto de una tarde, bien documentado
por la comunidad Matrix.

## Opción C — Sin chat

No hagas nada. El botón no aparece y el resto de la suite funciona igual.

## Cómo se ve cuando está conectado

- El botón 💬 aparece en todas las vistas del correo y en el explorador de
  archivos. Al pulsarlo se abre el panel con tu chat, con la misma sesión.
- Un mensaje enviado desde el correo suena en el chat de escritorio/móvil y
  viceversa: es EL MISMO chat, con varias puertas.
