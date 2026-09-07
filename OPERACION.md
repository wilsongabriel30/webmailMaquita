# OPERACIÓN — Maquita Mail

Cómo se vigila la plataforma y qué hacer cuando algo avisa. Documento vivo.

---

## Canal de alertas

**Destino:** `gestiontecnologia@maquita.org` y `gestiontecnologia@maquita.com.ec`
**Vía:** correo local con `sendmail`, sin depender de servicios externos.

### Por qué el correo y no otra cosa

No hay sistema de alertas montado. El correo local funciona siempre que Postfix
esté vivo, y Postfix es justo lo que queremos vigilar desde dentro. Tiene un
límite conocido: **si Postfix cae del todo, esta vía no avisa**. Para eso hace
falta vigilancia desde fuera del servidor, que hoy no existe y conviene añadir.

Lo que sí está cubierto es el caso frecuente: los servicios que rodean al correo
fallan mientras Postfix sigue entregando.

---

## Vigilancia del milter DLP

**Qué:** `/usr/local/sbin/vigilar-milter.sh`
**Cuándo:** cada 3 minutos, `vigilar-milter.timer`
**Instalado:** 2026-09-04 (hallazgo A-15, decisión D-1)

### El punto ciego que cierra

Postfix tiene `milter_default_action = accept`: si el milter no responde, **el
correo se entrega igual, sin inspeccionar**. Bueno para la disponibilidad, malo
para enterarse. Antes de esto, la protección contra fugas de datos podía estar
caída durante horas sin que nadie lo notara.

### Qué comprueba

1. Que el servicio `maquita-milter` esté activo.
2. Que el puerto 11335 acepte conexiones. **Activo no es lo mismo que
   respondiendo**: un proceso colgado sigue apareciendo como activo.
3. Que Postfix siga apuntando al milter y que `milter_default_action` no haya
   cambiado sin que nadie lo decidiera.
4. Que la cola de evidencia diferida (hallazgo B2) no acumule marcadores. Cuando
   la base no está disponible, el milter deja un marcador y un cron los reinserta
   cada 7 minutos. Ese cron **solo avisa si la base sigue caída**; si el marcador
   se queda por otro motivo, hasta hoy no lo miraba nadie. Umbral: 5 marcadores.

### Cómo avisa

Un correo cuando aparece la incidencia y otro cuando se recupera. **No repite**
mientras el problema sigue: una caída de una hora serían veinte correos y el
aviso dejaría de leerse. El estado se guarda en
`/var/lib/maquita-admin/estado-vigilancia-milter`.

El correo de recuperación dice **desde cuándo y hasta cuándo** estuvo sin
inspección, para poder revisar el tráfico de esa franja.

### Probado el 2026-09-04

Se detuvo el milter de verdad. Se recibió la alerta en las dos direcciones, la
segunda pasada no generó correo nuevo, y al arrancarlo llegó el aviso de
recuperación. Cuatro correos entregados, dos por dirección.

### Si llega una alerta

```
systemctl status maquita-milter
journalctl -u maquita-milter -n 50
systemctl restart maquita-milter
```

Si el aviso es por marcadores acumulados, el problema está en la base:

```
ls -la /var/lib/maquita-admin/cola-cuarentena/
journalctl -t reconciliar-cuarentena -n 30
```

### Falso positivo conocido

Ninguno hasta la fecha. Si se reinicia el milter a mano, la comprobación puede
coincidir con la ventana de arranque y avisar; el aviso de recuperación llega
tres minutos después.

---

## Vigilancia de las integraciones con clave compartida (cada hora)

**Lección de N-15 (07/09/2026):** la clave del webmail hacia la pasarela de IA dejó de coincidir
tras una rotación y Smart Reply devolvió 502 en silencio durante cuatro días. Ningún servicio
estaba caído. **«Activo» no es «sano».**

`deploy/hardening/vigilar-integraciones.py` (cron `/etc/cron.d/maquita-integraciones`, minuto 23
de cada hora, con el venv del almacén) hace sondas **sin efectos secundarios** y avisa por el
canal de alertas cuando algo pasa a fallar y cuando se recupera:

| Sonda | Qué prueba | `desajuste` | `servicio` |
|---|---|---|---|
| `ia` | La misma llamada que hace el backend (`_call_llm` con su venv, su `.env` y el override del panel) con un prompt mínimo | 401/403 | 5xx, tiempo agotado |
| `chat` | `POST /api/chat/sesion/revocar` con `X-Notif-Secret` y cuerpo vacío (400 «Falta user» = clave aceptada, no toca a nadie) y `GET /api/auth/sesion-servicio` del correo con el mismo secreto | 403 en cualquiera de los dos sentidos | otro código o sin respuesta |
| `onlyoffice` | `CommandService.ashx` del Document Server con un JWT firmado con el secreto del almacén (`config_kv` manda sobre el `.env`) | `error 6` | otro error, sin respuesta |
| `secretos` | Copias de `SECRET_KEY`, `ADMIN_JWT_SECRET` y `CREDENTIAL_ENCRYPTION_KEY` en backend, almacén, panel y apps del Drive | copias distintas (se muestra un hash corto, nunca el valor) | — |

A mano: `almacen/venv/bin/python deploy/hardening/vigilar-integraciones.py --probar` imprime el
estado sin enviar correo y sale con 1 si algo falla. Al rotar cualquier secreto compartido,
correr esto **antes de dar la rotación por terminada**.

## Lo que NO está vigilado todavía

Escrito para que no se olvide:

- **Postfix, Dovecot y la base de datos.** Si caen, esta vía no avisa porque
  depende de ellos. Necesita vigilancia externa al servidor.
- **El filtro en tubería** (`maquita-filter`, hallazgo N-15). Es el único
  componente que **sí puede detener la entrega**, y no tiene ninguna vigilancia.
  Debería avisar si la cola de Postfix crece o si el filtro tarda de más.
- **La cola de Postfix.** Hoy nadie avisa si se acumulan mensajes.
- **Certificados.** El comodín vence en marzo de 2027 y requiere renovación
  manual anual. El de `mta-sts.maquita.com.ec` vencía en pocos días al momento
  de escribir esto: conviene comprobarlo.
- **Espacio en disco.** El correo ocupa 2,1 TB de 5 TB (44 %).

---

## Umbrales de capacidad conocidos

| Componente | Medida | Techo |
|---|---|---|
| Filtro en tubería | 2,16 s de media, 8,70 s de máximo, 10 procesos | 278 mensajes/minuto en el caso medio; **69 en el peor caso** |
| Pico real observado | 47 mensajes/minuto (2026-09-03) | el 68 % del techo del peor caso |

El filtro en tubería es el cuello de botella del sistema. Subir el número de
procesos en `master.cf` es barato porque cada uno pasa la mayor parte del tiempo
esperando al descompresor y al antivirus, no consumiendo procesador.

## Segundo factor (2FA) del panel de administración

Desde 2026-09-04 la impersonación de buzones exige que quien la use sea **superadministrador** y
haya **iniciado sesión con segundo factor**. El vale que emite el panel dura 5 minutos, nombra un
solo buzón y no se puede reutilizar.

### Activar el 2FA de la propia cuenta
1. Entrar al panel desde la red interna o la VPN (fuera de ahí nginx no deja pasar).
2. Arriba a la derecha, el icono de la persona («Mi cuenta»).
3. En «Verificación en dos pasos», escribir la contraseña actual y pulsar **Activar 2FA**.
4. Escanear el código QR con la aplicación de autenticación (o copiar la clave que aparece debajo).
5. Escribir el código de 6 dígitos y pulsar **Verificar y activar**.
6. **Cerrar sesión y volver a entrar con el código.** La marca de segundo factor se pone al iniciar
   sesión: sin este paso la sesión abierta sigue sin ella y la impersonación responderá 403.

### Si alguien pierde su segundo factor
No hay códigos de respaldo. La cuenta no puede entrar sola: otra persona con acceso tiene que
desactivarle el 2FA.

- **Camino normal (preferido):** otro superadministrador entra al panel, va a «Administradores»,
  edita esa cuenta y le cambia la contraseña. Eso cierra sus sesiones. El 2FA se desactiva desde la
  base (abajo), porque la pantalla de desactivar solo actúa sobre la propia cuenta.
- **Camino de rescate (como root en la VM 130):**

  ```bash
  maquita-admin-2fa estado              # quien tiene 2FA y cuantas sesiones abiertas
  maquita-admin-2fa rescatar <cuenta>   # quita el 2FA y cierra sus sesiones (pide confirmacion)
  ```

  La persona vuelve a entrar solo con contraseña y **debe activar el 2FA de nuevo el mismo día**.
  Queda registrado en `admin_audit` como `totp_rescate`. La herramienta vive en el repositorio
  (`deploy/tools/maquita-admin-2fa`) y lee la contraseña de la base del `.env` del panel.

- **Ojo con la recuperación por correo alternativo** (`/api/admin-recovery`): solo restablece la
  **contraseña**, no toca el segundo factor. Si se perdió el teléfono, ese camino NO alcanza para
  entrar; hay que usar el rescate de arriba.

### Reglas de continuidad
- Debe haber **al menos dos** cuentas de superadministrador con 2FA activo, de personas distintas.
  Con una sola, la impersonación (y con ella el soporte a los buzones) depende de un solo teléfono.
- El secreto del 2FA se genera en el panel y vive en la aplicación del teléfono de cada persona.
  No se comparte, no se guarda en documentos ni se envía por correo o chat.
- Al dar de baja a una persona: desactivar su cuenta en «Administradores» (eso revoca sus sesiones
  al instante) y borrar su secreto con la sentencia de arriba.

## Contraseñas de aplicación (D-5)

Desde 1.7.8 cada cliente externo (Outlook, Thunderbird, celular, ActiveSync) entra con una contraseña
de aplicación propia (`Configuración → Seguridad`), generada por el webmail (16 símbolos, ~79 bits),
guardada como bcrypt en `contrasenas_aplicacion` y verificada por Dovecot en cada login con
`verificar_contrasena_aplicacion(user, password, remote_ip)` (segunda `passdb`, pgcrypto; la función compara
sin guiones ni espacios y responde `nopassword`, por eso la clave se acepta tecleada de las dos formas). Se
revocan desde Ajustes, con `maquita-mailadm mailbox apppass <email> revoke`, y todas al cambiar la
contraseña principal. No valen desde el propio servidor (webmail y app siguen con la principal + 2FA).

- **Política** `auth_politica.contrasenas_aplicacion_obligatorias`: con `true`, la contraseña
  principal solo se acepta desde 127.0.0.1/::1 (webmail, app, envío del backend); Z-Push (docker0)
  y cualquier cliente externo necesitan una de aplicación. `maquita-mailadm auth apppass-policy on|off`
  (aplica en el siguiente login, sin reinicio). En producción está en **on** desde el 07/09/2026.
- Diagnóstico: `doveadm auth test -x rip=<ip-del-cliente> usuario contraseña` (con `rip` externa
  prueba la ruta real; sin `rip`, la de aplicación no vale a propósito). Último uso e IP en la tabla.
- Requisitos: `CREATE EXTENSION pgcrypto` en `maildb` (superusuario; lo hace el instalador) y la
  migración `2026-09-07-contrasenas-aplicacion.sql`. Guía de usuario: `docs/CONTRASENAS-APLICACION.md`.

## Firmas: normalización automática

Desde 1.7.8 toda firma pasa por `backend/app/mail/firmas.py` al guardarse (webmail → Firmas,
Identidades, plantillas del panel) y al enviarse (bloque `email-signature`): imágenes remotas o
incrustadas descargadas (5 s, 2 MB, `image/*`, sin redes internas) y guardadas al tamaño declarado
(máximo 600 px) en `/var/lib/maquita-webmail/firmas/<hash>.png`; tabla exterior de ancho fijo con
`role="presentation"`; `margin` de celdas a `padding`; `mailto:` revisado. En el correo que sale las
imágenes viajan incrustadas (`cid:`), nunca como enlace. Motivo: hallazgo de usuario del 07/09/2026
(firmas de Zimbra con logos de 1.200 px y `width="201"`, gigantes en Outlook y en el celular).

- Lo que falla se quita y se avisa (fallo cerrado): la respuesta de guardar trae `avisos` y el
  webmail los muestra. Nunca queda una URL externa ni un `data:` en una firma guardada.
- Migración de una vez, con conteo y sin tocar nada hasta `--aplicar`:
  `cd /opt/maquita-webmail/backend && venv/bin/python ../deploy/tools/firmas-normalizar.py [--aplicar]`.
  Las firmas con una imagen no recuperable se dejan como están (código de salida 1; `--forzar`).
- El panel no importa el código del correo: llama a `venv/bin/python -m app.mail.firmas_cli` del
  correo con la firma por la entrada estándar. Directorio con grupo `maquita-admin` y `2775`.
- Guía de usuario: `docs/GUIA-FIRMAS.md`. Pruebas: `backend/tests/test_firmas.py`.

## Z-Push / ActiveSync: Outlook clásico y nuevo Outlook

Z-Push (`deploy/z-push/`, contenedor `zpush`) sirve correo, calendario, contactos y tareas por
ActiveSync desde Dovecot y Radicale: **un solo origen de datos**. Lo usan la dirección y las
gerencias desde Outlook de escritorio (D-9). Prueba real obligatoria con **los dos Outlook** y la
misma cuenta antes de etiquetar cualquier cambio que toque Z-Push, el autodiscover o Radicale.

### Prerequisito: autodiscover con ActiveSync
El nuevo Outlook **no permite configurar ActiveSync a mano**: depende por completo del
autodiscover. El backend responde `https://autodiscover.<dominio>/autodiscover/autodiscover.xml`
(esquema `mobilesync`) y `.../autodiscover.json?Protocol=ActiveSync` (v2). Comprobar:

```bash
curl -s -X POST -H 'Content-Type: text/xml' https://autodiscover.maquita.org/autodiscover/autodiscover.xml \
  -d '<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/mobilesync/requestschema/2006"><Request><EMailAddress>usuario@maquita.org</EMailAddress><AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/mobilesync/responseschema/2006</AcceptableResponseSchema></Request></Autodiscover>'
# → <Type>MobileSync</Type> <Url>https://mail.maquita.org/Microsoft-Server-ActiveSync</Url>
curl -s 'https://autodiscover.maquita.org/autodiscover/autodiscover.json/v1.0/usuario@maquita.org?Protocol=ActiveSync'
# → {"Protocol":"ActiveSync","Url":"https://mail.maquita.org/Microsoft-Server-ActiveSync"}
curl -s -o /dev/null -w '%{http_code}\n' -X OPTIONS https://mail.maquita.org/Microsoft-Server-ActiveSync   # 401
```
DNS: `autodiscover.<cada dominio>` → este servidor, y el certificado debe cubrirlo. Ojo: hoy
`autodiscover.maquita.com.ec` apunta a otro servidor (190.110.197.118): las cuentas `@maquita.com.ec`
no podrán configurarse en el nuevo Outlook hasta corregir DNS, `server_name` y SAN (pendiente).
Z-Push 2.7.6 anuncia ActiveSync 12.0, 12.1 y 14.0 (suficiente para Outlook, iOS y Android).

Prueba de carga de referencia (07/09/2026, 50 dispositivos a la vez con FolderSync real, cuenta
`prueba.carga@maquita.org`): 0 fallos, p50 3,5 s, p95 4,2 s, 112 MB de memoria en el contenedor.
`deploy/z-push/prueba-carga.py --usuario ... --dispositivos 50` (contraseña por `CLAVE=`).

### Outlook clásico (Office 365 de escritorio)
1. Archivo → Agregar cuenta → escribir el correo → **Opciones avanzadas → «Configurar mi cuenta
   manualmente»** → Conectar.
2. Elegir **Exchange (o «Exchange ActiveSync»)**. Servidor: `mail.maquita.org`; usuario: el
   **correo completo**; contraseña: la del buzón. Si Outlook pregunta por dominio\usuario, dejar
   el dominio vacío y poner el correo completo como usuario.
3. Tras conectar: carpetas de correo, Calendario, Contactos y Tareas aparecen bajo la cuenta.
   El primer ciclo puede tardar unos minutos; después Ping mantiene la conexión.
4. También puede añadirse como cuenta **IMAP** (autodiscover IMAP/SMTP), pero entonces **no** hay
   calendario ni contactos: para dirección, siempre ActiveSync.
   _[captura pendiente: pantalla «Configuración avanzada» con Exchange elegido]_

### Nuevo Outlook
1. Configuración → Cuentas → Agregar cuenta → escribir el correo → Continuar.
2. El nuevo Outlook consulta el autodiscover y ofrece la cuenta como **Exchange/ActiveSync** sin
   más pasos: contraseña del buzón y listo. **No hay pantalla manual**: si no aparece la opción o
   pide servidores IMAP, el autodiscover no está devolviendo ActiveSync (ver prerequisito).
3. Calendario, contactos y tareas se sincronizan igual que en el clásico.
   _[captura pendiente: pantalla de «Agregar cuenta» con la detección automática]_

### Diferencia entre los dos
| | Outlook clásico | Nuevo Outlook |
|---|---|---|
| Configuración manual de ActiveSync | Sí (Opciones avanzadas) | **No**, solo autodiscover |
| Depende del autodiscover | Solo si no se configura a mano | Siempre (XML `mobilesync` y JSON v2) |
| Cuenta IMAP como alternativa | Sí (sin calendario ni contactos) | Sí (sin calendario ni contactos) |

### Prueba real (la misma cuenta en los dos)
Correo (recibir y enviar); evento creado en el webmail visto en Outlook y viceversa; contacto
creado en Outlook visto en el webmail; tarea creada en Outlook visible en el CalDAV del webmail.
Registrar el resultado en `REGISTRO-HALLAZGOS.md` (documentación) antes de etiquetar.

### Cuando no sincroniza
1. `docker ps | grep zpush` (Up), `docker logs --tail 50 zpush`, `/var/log/z-push/z-push-error.log`.
2. `docker exec zpush z-push-top` (sesiones en vivo) y `docker exec zpush z-push-admin -a list -u
   correo@dominio` (dispositivos de la cuenta y su estado).
3. `/var/log/nginx/activesync-error.log`: 502/504 = el contenedor no responde o el `fastcgi_pass`
   no apunta a `127.0.0.1:9000`.
4. Credenciales: `docker exec zpush php -r 'var_dump(imap_open("{host.docker.internal:993/imap/ssl/novalidate-cert}INBOX","correo","clave"));'`
   distingue «clave mal» de «no llega a Dovecot».
5. Calendario/contactos vacíos con correo bien: Radicale no escucha en la IP del puente
   (`hosts = 127.0.0.1:5232, 172.17.0.1:5232` en `/etc/radicale/config`) o la ruta `/%u/` no
   coincide con las colecciones del usuario (`ls /var/lib/radicale/collections/collection-root/`).
6. Resincronizar un dispositivo: `docker exec zpush z-push-admin -a resync -u correo -d <deviceid>`;
   como último recurso, quitar la cuenta del cliente y volver a añadirla.
7. Tras cambiar un `.php` de `/opt/z-push-docker/`: `docker restart zpush`.

## Imágenes de contenedor (chat-service y las que se añadan)

- **Una vez al mes** se reconstruyen todas las imágenes con la etiqueta actual de su base oficial
  (`docker build --pull --no-cache`) y se despliegan si se usan. El `apt-get upgrade` del build
  cierra lo que la base aún no trae.
- El CI (`security-scan.yml`, job «Trivy Imágenes») construye cada imagen y la escanea con Trivy:
  **bloquea solo por avisos altos o críticos con corrección disponible**. Lo que la distribución
  no arregla (p. ej. `CVE-2023-45853`, zlib/minizip) se acepta con motivo en `DECISIONES.md` y se
  revisa cuando haya corrección.
- No se migra a Alpine ni a versiones «rc» para «limpiar» un informe: se cambia la base solo
  cuando la actual deje de recibir soporte.
- Imágenes en producción: `zpush` (Z-Push, `deploy/z-push/`). Se reconstruye con `bash deploy/z-push/instalar.sh`.

## Snyk (conectado al repositorio el 07/09/2026)

- Snyk se usa **para mirar, no para actuar**: sin PRs automáticos ni «fix» automáticos. Cada cambio
  de versión que sugiera pasa por el flujo normal (rama → PR → CI en verde → despliegue → etiqueta),
  con la verificación de que aplica de verdad al intérprete y a la imagen reales.
- `.snyk` en la raíz fija `language-settings.python: "3.13"`, que es el intérprete real de todos los
  satélites; sin él la organización asumía 3.7 e inflaba avisos falsos.
- Lo que Snyk marque sin corrección disponible se trata como Trivy: aceptado con motivo en
  `DECISIONES.md`, no se «arregla» cambiando de base ni a versiones «rc».
