# Firmar PDF desde el correo, confirmaciones de lectura y avisos por carpeta

Tres funciones añadidas en noviembre de 2026. Las tres funcionan sin configuración extra salvo la firma, que necesita el
sistema de gestión donde las personas guardan su certificado.

## 1. Firmar un PDF adjunto sin descargarlo

Desde el visor de adjuntos, botón **Firmar**. La persona elige su certificado (guardado en el sistema de gestión o un
`.p12` que sube en el momento), escribe la contraseña y **dibuja con el ratón o el dedo el rectángulo** donde irá el sello
sobre la página que elija (navegación de páginas, un toque coloca un sello de tamaño normal). También puede firmar sin
sello visible.

- **Firmar y responder**: crea la respuesta al mismo correo con `nombre_firmado.pdf` adjunto y un texto automático editable.
- **Firmar y añadir otra**: deja la firma puesta y vuelve al formulario para la siguiente (otra persona, u otra hoja con la
  misma firma). Las firmas son incrementales: cada una conserva las anteriores y todas siguen siendo válidas.
- **Solo firmar**: descarga, responde o reenvía con el PDF firmado.

Rutas del backend (`/api/mail/firma-pdf/*`): `certificados`, `consentimiento`, `pagina` (GET adjunto / POST archivo:
PNG de la página con cabeceras `X-Pagina`, `X-Paginas`, `X-Ancho-Pt`, `X-Alto-Pt`) y `firmar` (multipart; con
`posicion=manual` recibe `pagina, x, y, ancho, alto` en puntos PDF, origen abajo-izquierda; acepta `archivo` con una
versión ya firmada). La firma criptográfica la hace el servicio externo configurado con:

```
RAICES_FIRMA_URL=https://gestion.example.org
RAICES_FIRMA_TOKEN=<token compartido servicio a servicio>
```

Dependencias: `pypdfium2` y `pillow` (render de páginas). El servicio externo debe exponer
`/api/pdf/firma-servicio/{certificados,consentimiento,firmar}` y aceptar `posicion=manual`.

## 2. Confirmaciones de lectura y de entrega

- Al abrir un correo que pide confirmación de lectura (`Disposition-Notification-To`), aparece un aviso con
  **Enviar / No enviar** y accesos «enviar siempre · no enviar nunca». Preferencia en Configuración
  (`acuse_lectura`: `preguntar` | `siempre` | `nunca`; columna nueva en `user_preferences`). Con «siempre» se envía solo
  únicamente si el destinatario del acuse coincide con el remitente (RFC 8098 §2.1).
- El acuse es un `multipart/report` MDN estándar (`message/disposition-notification` + cabeceras originales) y el correo
  queda marcado con la palabra clave IMAP `$MDNSent` para no enviarlo dos veces. No se piden acuses de listas,
  correos automáticos ni `Precedence: bulk`.
- Al redactar, la opción **Confirmación de entrega** usa DSN SMTP (`NOTIFY=SUCCESS,FAILURE`, `RET=HDRS`); el servidor de
  correo debe anunciar `DSN`.

Rutas: `POST /api/mail/acuse-lectura {folder, uid, enviar}`; el detalle del mensaje trae `acuse_lectura: {to, mismo_remitente} | null`.

Migración: `ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS acuse_lectura varchar(12) NOT NULL DEFAULT 'preguntar';`

## 3. Avisos de correo nuevo en cualquier carpeta

El sondeo de correo nuevo (cada 45 s por WebSocket) revisaba solo INBOX, así que los correos que una regla archivaba en
otra carpeta no pintaban el contador ni avisaban. Ahora revisa todas las carpetas seleccionables, menos Enviados,
Borradores, Papelera y Correo no deseado, y publica el mismo evento `new_mail` con `folder`, `unseen`, `delta`, `uid`,
`de` y `asunto`. El cliente pinta el contador de esa carpeta, muestra «En «Carpeta»: …», suena y lanza la notificación del
navegador. El estado anterior por carpeta vive en Redis (`sondeo:carpetas:<usuario>`, 24 h), así que un cambio de
worker no avisa en falso; la primera vez que se ve una carpeta solo se memoriza.
