# DECISIONES — Maquita Mail

Decisiones de arquitectura y seguridad tomadas **a conciencia**, con su motivo y su
fecha de revisión. Lo que está aquí no es una configuración heredada que nadie
recuerda haber elegido: es una postura, y se puede discutir.

Formato: qué se decidió, por qué, qué se acepta a cambio, y cuándo hay que
volver a mirarlo.

---

## D-1. El milter DLP falla ABIERTO: si no responde, el correo pasa sin inspección

**Fecha:** 2026-09-04 · **Estado:** vigente en preproducción · **Revisar antes de:** salida a usuarios

### Qué está configurado

En Postfix:

```
milter_default_action = accept
smtpd_milters = inet:localhost:11332, inet:localhost:11335
```

`11332` es rspamd. `11335` es `maquita-milter`, la inspección de fugas de datos.

Con `accept`, si un milter no responde, Postfix **entrega el correo igualmente**,
sin inspeccionar. La alternativa sería `tempfail`, que retiene el mensaje en cola
hasta que el milter vuelva.

### Por qué se mantiene así hoy

Prioriza que el correo circule sobre que se inspeccione. En preproducción es lo
correcto: un fallo del milter no debe detener el trabajo del equipo, y el coste
de un mensaje sin inspeccionar es bajo mientras no haya tráfico sensible real.

Esta decisión se registró tras confinar el milter (A-15, fase 1), al comprobar
que un reinicio del servicio **no corta la entrega**. Eso rebajó el riesgo de la
intervención, y conviene que quede escrito por qué.

### Qué se acepta a cambio

Que la protección contra fugas de datos se pueda saltar **en silencio**. Hoy, si
el milter muere, nadie se entera: el correo sigue saliendo y el registro de
Postfix no grita. Un atacante con acceso al servidor podría parar el milter y
exfiltrar por correo sin dejar una alerta.

### Qué falta antes de salir a usuarios

1. **Decidir a conciencia si sigue siendo `accept`.** Con datos sensibles reales,
   puede compensar que el correo espere en cola a que el milter vuelva. No es
   obvio: `tempfail` mal calibrado convierte una caída del milter en una parada
   de correo. La decisión es del responsable, no técnica.
2. **Alerta obligatoria, se quede como se quede.** Si Postfix empieza a aceptar
   sin inspección, tiene que notarse en minutos, no en la siguiente auditoría.
   Mínimo: vigilar que `maquita-milter` esté activo y que el puerto 11335
   responda, y avisar si deja de hacerlo. Si se pasa a `tempfail`, hace falta
   además vigilar el tamaño de la cola.
3. Anotar el resultado aquí, sustituyendo esta sección.

### Relación con otros hallazgos

- B2 (errores silenciosos del milter) ya dejó anotado que la elección
  `tempfail`/`accept` se reevalúa en la puerta de lanzamiento. Esto lo concreta.
- A-15 fase 1: el milter quedó confinado el 2026-09-04. Su superficie es mínima
  y medida, pero sigue corriendo como root.

---

## D-2. El panel administrativo no comparte el archivo de configuración del correo

**Fecha:** 2026-09-04 · **Estado:** decidido, pendiente de ejecutar con la fase 2 de A-15

Se copian a su propia configuración solo los valores que necesita, en vez de darle
lectura del archivo del correo. Si el panel pudiera leerlo entero, quien lo
comprometa se lleva el secreto de sesión del webmail, el de administración y las
credenciales de la base, y el confinamiento pierde sentido.

Se acepta a cambio el riesgo de que los valores duplicados se desalineen al rotar
un secreto. Mitigación obligatoria: validación al arranque que **aborte** si un
valor compartido no coincide, nombrando la variable y nunca el valor. Detalle en
`docs/auditoria/PLAN-PANEL-FASE2-SIN-ROOT.md`.

Precedente que lo justifica: el 2026-09-03 se rotaron secretos y el chat quedó 17
horas rechazando sesiones sin que nadie lo notara.

## D-3. `pickle` en el canal interno del editor de PDF del almacén

**Fecha:** 2026-09-06 · **Estado:** deuda aceptada con fecha; se migra a JSON al tocar el módulo

`almacen/aplicaciones/pdf_editor/infraestructura/externos/worker_pdf.py:117` y
`pool_pdf.py:265` deserializan con `pickle.loads` lo que llega por el canal entre
el proceso del almacén y sus trabajadores de PDF. Hoy ese canal es interno (tuberías
entre procesos del mismo servicio, mismo usuario, sin exposición de red), así que
no hay vía de ataque desde fuera.

Se anota igualmente porque es el patrón que se convierte en ejecución remota de
código el día que ese canal se exponga (cola compartida, red, otro usuario): con
`pickle`, quien controle los bytes controla el proceso. La regla es que ningún
dato que cruce una frontera de confianza se deserialice con `pickle`.

Compromiso: **la próxima intervención en `pdf_editor` sustituye `pickle` por JSON**
(las tareas son nombre + argumentos serializables; el contenido binario viaja por
ficheros, no por el canal). Hasta entonces, el módulo no se conecta a ninguna cola
ni socket. Hallazgo de la validación externa del 2026-09-06.

## D-4. El chat depende del empuje del correo entre una revocación y la siguiente revalidación

**Fecha:** 2026-09-06 · **Estado:** riesgo residual aceptado (F-03, tercera revisión ASVS)

El chat tiene su propia cookie y su propio Redis; no ve el estado de sesión del correo. La
revocación llega por dos vías: el correo la **empuja** en el acto a
`POST /api/chat/sesion/revocar` (secreto compartido `X-Notif-Secret`, con límite de
peticiones), y cada sesión del chat **revalida** contra el correo como máximo cada 5 minutos
(`CHAT_REVALIDAR_SESION_SEG`), con fallo cerrado si el correo no responde.

Riesgo que se acepta: si el empuje falla (chat caído, red), una sesión revocada puede seguir
viva en el chat **hasta 5 minutos**. A cambio, el chat no consulta a PostgreSQL por mensaje.
El fallo del empuje **nunca es silencioso**: el correo reintenta tres veces y, si no llega,
registra ERROR con la marca `REVOCACION_CHAT_FALLIDA` (monitoreo). `X-Notif-Secret` entra en
el inventario de secretos a rotar: comprometido permite cerrar sesiones ajenas.

## D-5. El segundo factor no cubre IMAP/SMTP directo

**Fecha:** 2026-09-06 · **Estado:** **DECIDIDO (2026-09-06): contraseñas de aplicación.** Pendiente de implementar antes de salir a usuarios.

El 2FA (TOTP) protege el webmail y la app. IMAP y SMTP directos (Thunderbird, Outlook, un
celular configurado a mano) autentican solo con la contraseña, así que **quien tenga la
contraseña entra por ahí aunque el 2FA esté activo**. M-01 cerró la fuga de la respuesta de
login (ya no confirma la contraseña de una cuenta con 2FA), pero no cambia este hecho.

Decisión de la dirección (2026-09-06): **contraseñas de aplicación** — una por cliente (Thunderbird, Outlook,
celular), generada por el webmail, revocable desde Ajustes; la contraseña principal deja de valer en
IMAP/SMTP directo. Se implementa como tarea propia (Dovecot: passdb adicional o tabla de claves de
aplicación) antes de salir a usuarios.

Las dos mitigaciones que se valoraron: **contraseñas de aplicación** (una por cliente,
revocables, la contraseña principal deja de valer en IMAP/SMTP) o **exigir 2FA también ahí**
(no es viable con los clientes actuales). Hasta decidirlo, se documenta al usuario que el 2FA
no protege los clientes de escritorio. Hallazgo de la cuarta revisión externa (M-01).

## D-6. Qué puede escribir `admin` y qué exige `superadmin` en el panel

**Fecha:** 2026-09-06 · **Estado:** decidido y aplicado (sexta revisión externa, M-01)

Regla: `admin` opera el día a día (buzones, alias, cuarentena, cortafuegos, marca, integraciones,
investigación AIR, pruebas de configuración). **`superadmin`** es el único que puede cambiar lo que
altera la retención de datos, el perímetro o la salida de correo de toda la organización:

| Exige `superadmin` | Motivo |
|---|---|
| Retención (`/api/retention/*` crear, activar, borrar) | destruye o conserva datos de todos |
| Acceso condicional (`/api/conditional-access/*`) | perímetro de acceso de todos |
| Límites y bloqueo de envío (`/api/admin/outbound/*`, `/api/outbound-anomaly/config`) | reputación del dominio |
| Geo-bloqueo (`/api/geo-access/toggle`) | perímetro |
| Sincronización LDAP (`/api/sso/sync`) | identidad de todas las cuentas |
| Ingestión RAG y dominios del RAG (`/api/rag/ingest`, `/api/rag/domains*`) | qué correo lee la IA |
| Políticas de seguridad (`POST /api/security-policies`) | contraseñas y bloqueo de todos |

Se aplica con `Depends(require_superadmin)` en la ruta (no con la política genérica de rol efectivo).
Cualquier ruta nueva de estas familias hereda la regla; `docs/PANEL-RUTAS-ROLES.md` es la tabla viva.

## D-7. El JWT de Meet Maquita (Jitsi) viaja en la URL

**Decisión (06/09/2026):** se acepta que el token de acceso a una sala de Meet vaya en `?jwt=`
de la URL, porque Jitsi Meet no admite otra vía (ni cabecera ni cookie) para el cliente web y
la app. Lo que se controla es **qué vale y cuánto dura**: siempre atado a UNA sala (nunca `*`),
moderador solo para quien creó la reunión, vida de 60 minutos (5–120; Jitsi solo lo comprueba
al entrar, y quien se reconecta pide otro a `/api/chat/reuniones/<id>/acceso`), y **nunca se
guarda** en la base ni en enlaces de calendario (esos llevan `/acceso?redirigir=1`, que exige
sesión). Antes: `room='*'`, 8–72 horas, y el token de moderador persistido en cada fila de
`reuniones_programadas`.

**Residual:** el token queda en el historial del navegador y en los registros del servidor de
Meet durante su vida (≤ 2 h) y solo sirve para esa sala. Revisar si Jitsi añade autenticación
por cabecera para el iframe API.

## D-8. Las funciones de IA sobre correo entrante procesan contenido hostil por definición

**Decisión (07/09/2026, séptima revisión):** Smart Reply y el resumen de hilos trabajan sobre
correo que cualquiera puede haber enviado, así que su entrada se trata SIEMPRE como hostil:
el correo va entre delimitadores explícitos (`<<<CORREO_ENTRANTE>>>` … `<<<FIN_CORREO_ENTRANTE>>>`,
retirados del contenido si los trae), la instrucción de sistema declara que lo delimitado son
datos que no se obedecen, y la salida se valida antes de llegar al usuario: Smart Reply y
asuntos solo aceptan un JSON array de tres cadenas (si no, respuestas de reserva; nunca texto
libre del modelo), el resumen solo prosa acotada sin delimitadores. Toda función nueva de IA que
lea correo recibido pasa por `app/ai/contenido_hostil.py`.

**Residual:** un modelo puede seguir obedeciendo una instrucción inyectada dentro del formato
válido (por ejemplo, tres respuestas que digan lo que pide el atacante). Se mitiga con la regla
de sistema y con que la persona siempre ve y edita la sugerencia antes de enviar; no se
automatiza ningún envío a partir de la salida de la IA.

## D-9. Z-Push (ActiveSync) se retira; las imágenes de contenedor se reconstruyen cada mes

**Decisión (07/09/2026, informe de Snyk sobre `deploy/z-push/Dockerfile`):** Z-Push se retira del
repositorio y de producción. Evidencia: cero peticiones a `/Microsoft-Server-ActiveSync` en dos
semanas de registros de nginx (el endpoint ni siquiera estaba enrutado), cero dispositivos en
`/var/lib/z-push/users`, y el único uso residual (autodiscover de Outlook) lo sirve ya el backend.
IMAP + CalDAV/CardDAV con autoconfiguración cubren los teléfonos. Quitarlo elimina una imagen
PHP de 595 MB con vulnerabilidades altas (libssh2 ×6, util-linux ×3) y un pool PHP-FPM en el host.

**Imágenes que quedan** (`chat-service/Dockerfile`, solo para el CI y despliegues en contenedor):
se construyen con la etiqueta actual de la base oficial y `apt-get upgrade` en el build; no se
migra a Alpine ni a versiones «rc». Regla en `OPERACION.md`: reconstruir todas las imágenes con
base actualizada **una vez al mes** y escanearlas (Trivy) en cada cambio de Dockerfile, bloqueando
**solo** por avisos con corrección disponible.

**Aceptado con motivo:** `CVE-2023-45853` (zlib/minizip) en imágenes basadas en Debian: sin
corrección en Debian, y minizip no se usa en estos contenedores. El CI lo ignora por
`--ignore-unfixed`; se revisa si Debian publica arreglo.
