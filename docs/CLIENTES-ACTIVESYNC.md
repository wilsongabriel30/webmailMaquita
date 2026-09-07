# Guía por cliente: correo, calendario, contactos y tareas por ActiveSync

Para el personal. Todos los clientes usan la **misma cuenta** (correo completo + una **contraseña de
aplicación** creada en Configuración → Seguridad, ver `CONTRASENAS-APLICACION.md`; la contraseña
principal solo sirve para el webmail y la app) y el **mismo servidor** `mail.maquita.org`; el calendario y los contactos son los mismos
que en el webmail (`https://mail.maquita.org/webmail/`), en cualquier orden que se editen.

> Las capturas de cada pantalla se toman en la prueba real de cada versión (`OPERACION.md`,
> «Z-Push / ActiveSync», «Prueba real») y se guardan en `docs/capturas/activesync/`. Donde diga
> _[captura: …]_ va la imagen de esa pantalla. Si un cliente muestra algo distinto a lo descrito,
> se ajusta el servidor (autodiscover o Z-Push), no se le pide nada raro al usuario.

## Nuevo Outlook (Windows y Mac)
1. Configuración (engranaje) → **Cuentas** → **Agregar cuenta**.
2. Escribe tu correo completo (`nombre@maquita.org`) → **Continuar**. _[captura: agregar cuenta]_
3. El nuevo Outlook consulta el autodiscover del servidor y ofrece la cuenta directamente
   (Exchange/ActiveSync). Escribe la contraseña del buzón → **Continuar**. _[captura: contraseña]_
4. En un minuto aparecen Correo, Calendario, Contactos y Tareas. _[captura: cuenta añadida]_
5. **No hay configuración manual**: si el asistente pide «servidor IMAP» o dice que no encuentra
   la configuración, avisa a tecnología (el autodiscover no está devolviendo ActiveSync).

## Outlook clásico (Office 365 de escritorio)
1. **Archivo → Agregar cuenta** → escribe tu correo → despliega **Opciones avanzadas** → marca
   **Configurar mi cuenta manualmente** → **Conectar**. _[captura: opciones avanzadas]_
2. Elige **Exchange ActiveSync** (icono de teléfono; en algunas versiones «Exchange»).
   _[captura: tipo de cuenta]_
3. Servidor `mail.maquita.org`, usuario = tu correo completo, contraseña del buzón, «Usar SSL»
   marcado → **Siguiente** / **Conectar**. _[captura: datos del servidor]_
4. Espera el primer ciclo (uno o dos minutos): Correo, Calendario, Contactos y Tareas.
5. Si Outlook sugiere IMAP/POP: cancela y repite desde el paso 1 eligiendo ActiveSync; como
   cuenta IMAP **no** tendrás calendario ni contactos.

## iPhone / iPad
1. Ajustes → **Correo** (o «Apps → Mail») → **Cuentas** → **Añadir cuenta** → **Microsoft
   Exchange**. _[captura: tipo de cuenta]_
2. Correo completo y una descripción («Maquita») → **Siguiente** → **Configurar manualmente**
   (si iOS ofrece «Iniciar sesión», elige configurar manualmente) → contraseña → **Siguiente**.
3. Si iOS no rellena el servidor solo, escribe `mail.maquita.org`; dominio vacío; usuario = correo
   completo. _[captura: servidor]_
4. Activa Correo, Contactos, Calendarios y Recordatorios (tareas) → **Guardar**.
   _[captura: qué sincronizar]_

## Android (Gmail o el correo del fabricante)
1. Gmail → foto/menú → **Añadir otra cuenta** → **Exchange y Office 365** (en Samsung: «Exchange»).
   _[captura: tipo de cuenta]_
2. Correo completo → **Configurar manualmente** (si aparece) → contraseña.
3. Servidor `mail.maquita.org`, puerto 443, seguridad **SSL/TLS**, dominio vacío, usuario = correo
   completo → **Siguiente**. Acepta la política de seguridad si la pide (no impone PIN).
   _[captura: servidor]_
4. Marca Correo, Contactos, Calendario y Tareas → **Listo**.

## Qué comprobar tras configurar (la prueba real, la misma cuenta en los cuatro)
| Prueba | Cómo |
|---|---|
| Correo | Recibir un correo en el cliente; enviar uno desde el cliente y verlo en «Enviados» del webmail. |
| Calendario webmail → cliente | Crear un evento en el webmail; aparece en el cliente en menos de 5 minutos. |
| Calendario cliente → webmail | Crear un evento en el cliente; aparece en el webmail. |
| Contactos | Crear un contacto en el cliente; aparece en Contactos del webmail (y al revés). |
| Tareas | Crear una tarea en el cliente; aparece en las tareas (CalDAV) del webmail. |

## Si no sincroniza
Reinicia el cliente; comprueba que el usuario es el correo completo; y avisa a tecnología con el
cliente, la versión y la hora: en el servidor se ve la sesión con `z-push-top` y el motivo en
`/var/log/z-push/` (`OPERACION.md`, «Cuando no sincroniza»).
