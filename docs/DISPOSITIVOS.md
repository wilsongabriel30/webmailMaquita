# Teléfonos institucionales (gestión de dispositivos) — fases 1 a 4

Gestión propia de los celulares de la organización: inventario y asignación, estado que reporta
cada equipo, mensajes urgentes con acuse de lectura y eventos de seguridad. Las fases siguientes
(ubicación y modo perdido, respaldos, control de aplicaciones) se apoyan en estas mismas tablas.

| Pieza | Dónde | Qué hace |
|---|---|---|
| API de los teléfonos | `backend/app/dispositivos/` (`/api/dispositivos/*` del webmail) | Enrolamiento con código, latidos, entrega de comandos y mensajes, acuses, eventos |
| Administración | `admin-panel/backend/app/dispositivos/` y `admin-panel/frontend/src/pages/Dispositivos.tsx` | Equipos, ficha de inventario y depreciación, códigos de enrolamiento, mensajes urgentes |
| Datos | `migrations/2026-09-18-dispositivos.sql` (tablas `disp_*`) | — |

## Seguridad
- **Código de enrolamiento** = contraseña de instalación. Lo crea un administrador del panel, se
  muestra una sola vez, caduca y tiene usos limitados; en la base solo queda su SHA-256. Sin código
  vigente la app no activa la gestión. El **modo** (control completo o limitado) lo fija el código,
  no el teléfono.
- **Token del equipo**: 48 bytes aleatorios, se entrega una vez al enrolar y se guarda solo su
  SHA-256. Es independiente de la sesión de correo. «Quitar de la gestión» lo invalida.
- Cada equipo solo ve sus propios comandos y mensajes (todas las consultas filtran por el equipo
  dueño del token). Límites de ritmo en Redis para enrolar, latidos y eventos.
- El panel exige rol `admin`/`superadmin` para escribir y audita cada acción en `admin_audit`.
- Privacidad: no se guarda contenido del teléfono. La ubicación sigue la regla de la fase 2 (más abajo).

## Contrato de la API (v1) — `Authorization: Bearer <token_equipo>` salvo `enrolar`
| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `POST /api/dispositivos/enrolar` | `{codigo, id_instalacion, modo?, fabricante?, modelo?, serie?, imei?, android?, version_app?}`. Si llega con la cookie de sesión del correo, esa persona queda como custodia. | `{id_equipo, token_equipo, modo, politica, push}` · 403 si el código no vale · 429 tras 10 intentos por hora e IP |
| `POST /api/dispositivos/latido` | `{bateria?, cargando?, almacenamiento_libre?, almacenamiento_total?, red?, version_app?, android?, play_protect?, ubicacion?}` | `{comandos:[{id,tipo,parametros}], mensajes:[{id,titulo,texto,nivel,requiere_acuse,creado_en}], politica_version, latido_minutos}`. Un mensaje se repite en cada latido hasta que llega su acuse. |
| `POST /api/dispositivos/mensajes/{id}/acuse` | `{leido_en?}` | `{ok}` |
| `POST /api/dispositivos/comandos/{id}/resultado` | `{estado: "hecho"\|"fallido", detalle?}` | `{ok}` |
| `POST /api/dispositivos/evento` | `{tipo, detalle?}` con tipo en `arranque`, `admin_desactivado`, `desinstalacion_intento`, `permiso_revocado`, `sim_cambiada`, `otro` | `{ok}` |
| `GET /api/dispositivos/yo` | — | Nombre del equipo, custodio, contacto de Tecnología y aviso de privacidad |
| `GET /api/dispositivos/politica` | — | `{version, latido_minutos, contacto_ti, telefono_ti, aviso_privacidad}` |

401 = token desconocido o equipo retirado de la gestión desde el panel (al retirarlo, su token se
destruye): la app debe apagar el módulo, avisar a la persona y pedir un código nuevo para volver a
enrolarse. 403 = equipo dado de baja del inventario.

## Instalar y desinstalar con contraseña
- Instalar: el código de enrolamiento cumple esa función.
- Desinstalar: en equipos enrolados de fábrica (control completo) la app bloquea su propia
  desinstalación y solo Tecnología la libera. En modo limitado Android no permite exigir una
  contraseña para desinstalar: la app se registra como administradora del dispositivo (hay que
  desactivarla antes de poder desinstalar), avisa a la persona y envía el evento
  `admin_desactivado` / `desinstalacion_intento`, que el panel resalta para revisión.

# Fase 2 — ubicación y modo perdido

## Regla de privacidad
Una posición **solo se guarda** si el custodio firmó la política de uso (`ubicacion_autorizada`, que el
panel activa por equipo indicando la fecha de firma) **o** si el equipo está declarado perdido. En
cualquier otro caso el servidor la descarta sin dejar rastro (tampoco queda en el JSON del latido).
El panel pide un motivo para cada consulta de ubicación y para cada comando, y lo registra en
`admin_audit` (`dispositivo_ver_ubicacion`, `dispositivo_perdido`, `dispositivo_comando_*`…).
Retención: ubicaciones 90 días, latidos 30 días (`disp_config.politica`).

## Cambios en el contrato para la app (v2)
`POST /latido` ahora responde además:

| Campo | Significado |
|---|---|
| `ubicacion_activa` | `true` si el servidor guardará posiciones de este equipo. Si es `false`, la app **no debe tomar la ubicación** (ahorra batería y respeta la política). También viene en `GET /yo`. |
| `ubicacion_minutos` | Cada cuánto incluir `ubicacion` en el latido cuando está activa. |
| `modo_perdido` | `null`, o `{mensaje, telefono, baliza_id}` mientras el equipo esté declarado perdido: reportar cada `latido_minutos` (baja a 5), con ubicación precisa, y emitir la baliza Bluetooth. |
| `balizas_buscadas` | Identificadores (16 hex) de otros equipos perdidos. Si la app oye uno por Bluetooth, lo reporta. |

`ubicacion` (en el latido y en los lotes): `{lat, lon, precision?, hora?, fuente?}` con `fuente` en `gps`, `red`, `fusion` y `hora` ISO-8601 (si falta o es absurda se usa la del servidor).

| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `POST /api/dispositivos/ubicacion` | `{origen: "comando"\|"perdido"\|"periodica", puntos: [ubicacion…]}` (1–100; sirve para responder a `localizar` y para vaciar la cola acumulada sin red) | `{guardadas, ubicacion_activa}` |
| `POST /api/dispositivos/avistamientos` | `{vistos: [{baliza_id, rssi?, ubicacion}]}` (1–50). `ubicacion` es la **del teléfono que oye**, no la del perdido | `{registrados}` (las balizas que no correspondan a un equipo perdido se ignoran) |

### Comandos que entrega el latido
| `tipo` | `parametros` | Qué hace la app | Requisito |
|---|---|---|---|
| `localizar` | — | Una posición de alta precisión ahora → `POST /ubicacion` con `origen:"comando"` y luego el resultado | Cualquier modo (en limitado, si la persona concedió la ubicación) |
| `alarma` | — | Sonar a volumen máximo 2 minutos aunque esté en silencio; se detiene al tocar la pantalla | Cualquier modo |
| `bloquear` | `{mensaje, telefono}` | `lockNow()` y mensaje en la pantalla de bloqueo con el teléfono de contacto | Solo control completo |
| `desbloquear` | — | Quitar el mensaje de la pantalla de bloqueo y apagar la baliza: fin del modo perdido | — |
| `borrar` | — | `wipeData()` (restablecer de fábrica). Enviar el resultado **antes** de ejecutarlo | Solo control completo; el panel exige superadministrador, equipo perdido y frase de confirmación |

Siempre responder con `POST /comandos/{id}/resultado` (`hecho` o `fallido` con `detalle`).

### Baliza Bluetooth (búsqueda con ayuda de los demás teléfonos)
El equipo perdido anuncia por Bluetooth de baja energía un servicio con UUID fijo
`6d617175-6974-612d-6d61-696c2d6d646d` y, como datos del servicio, los 8 bytes de `baliza_id`.
Los demás teléfonos, mientras `balizas_buscadas` no esté vacío, hacen un escaneo breve en cada latido
filtrando por ese UUID; si coincide un identificador, envían `avistamientos` con su propia posición y
el `rssi`. El identificador cambia cada vez que un equipo se declara perdido y se borra al recuperarlo.

## Panel
Ficha del equipo → bloque **Pérdida o robo** (declarar perdido / recuperado, localizar, hacer sonar,
bloquear, borrado remoto, estado de cada comando) y bloque **Ubicación** (activar con fecha de firma,
consultar con motivo, mapa de OpenStreetMap sin librerías, historial con origen de cada punto).
Backend del panel: `admin-panel/backend/app/dispositivos/perdido.py`. Migración:
`migrations/2026-09-18-dispositivos-fase2.sql`.

# Fase 3 — respaldos

## Cómo funciona
Respaldo **incremental por contenido**: el teléfono envía un manifiesto (ruta, tamaño, SHA-256) y el
servidor responde qué contenidos le faltan; lo que no cambió no se vuelve a enviar. Cada contenido se
guarda una vez por equipo, **cifrado en reposo** (AES-256-GCM por tramas de 1 MiB; el texto claro no
toca el disco) en `DISP_RESPALDO_DIR` (`/mnt/almacen/.respaldo-movil/<equipo>/objetos/…`). La clave
(`DISP_RESPALDO_CLAVE`, en `backend/.env`) no está en la base de datos ni en el almacén: **sin ella
los respaldos son ilegibles; hay que custodiarla fuera del servidor**. Una *instantánea* es la lista
ruta → contenido de un momento; se conservan las 7 últimas completas y las 2 últimas de cierre, y los
contenidos que ya nadie referencia se borran del disco. Cuota por equipo (64 GB por defecto).

El panel **no ve contenido ni nombres de archivo**: solo fechas, tamaños y totales por categoría.
Restaurar en otro teléfono exige una autorización temporal creada en el panel (con motivo, auditada,
72 horas por defecto); al usarla queda un evento `restauracion` en el equipo de origen.

## Contrato para la app (v3) — prefijo `/api/dispositivos/respaldos`
El latido trae `respaldo`: `{activo, hora, solo_wifi, solo_cargando, categorias[], instantaneas}` y puede
traer el comando `respaldar {tipo: "manual"|"cierre"}` (responder con el resultado al terminar).

| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `POST ""` | `{tipo: "programado"\|"manual"\|"cierre", version_app?}` | `{id, trozo_bytes (8 MiB sugerido), trama_bytes (1 MiB), trozo_maximo_bytes (32 MiB), cuota_bytes, usado_bytes}` · 403 respaldo desactivado · 503 almacén no disponible (reintentar más tarde) |
| `POST /{id}/manifiesto` | `{archivos: [{ruta, categoria, tamano, sha256, mtime?}]}` (hasta 2000 por llamada; se puede llamar varias veces). `ruta` relativa, sin `..`. Categorías: `fotos, videos, documentos, descargas, contactos, llamadas, sms, whatsapp, apps, ajustes, otros` | `{faltan: [{sha256, tamano, recibido}]}` · 413 supera la cuota |
| `PUT /objetos/{sha256}?offset=N&total=T` | Cuerpo binario crudo. `offset` = lo ya recibido; cada trozo múltiplo de 1 MiB salvo el último | `{recibido, completo}` · **409 con `recibido`** = desfase: continuar desde ese valor · 422 = al completar, el contenido no coincide con su SHA-256 (se descarta: volver a subir desde 0) |
| `POST /{id}/cerrar` | `{errores?: [texto…]}` (p. ej. «SMS: permiso no concedido») | `{estado: "completo"\|"incompleto", faltantes, resumen}` |
| `GET ""` | — | Instantáneas completas propias y de los equipos autorizados (`propio: false`) |
| `GET /{id}/manifiesto?despues_de=<ruta>&limite=2000` | — | `{equipo_origen, archivos[], hay_mas}` (paginar con la última `ruta`) |
| `GET /objetos/{sha256}?equipo_origen=<id>&desde=<múltiplo de 1 MiB>` | — | Contenido en claro (flujo binario con `Content-Length`); `desde` permite reanudar |

Archivos de 0 bytes: van en el manifiesto y no se suben. Un mismo contenido no admite dos subidas a la
vez (409). Tras un corte, volver a enviar el manifiesto: `recibido` dice por dónde seguir.

### Qué respalda la app y cómo lo nombra (convención de `ruta`)
`DCIM/…`, `Pictures/…`, `Movies/…`, `Documents/…`, `Download/…` tal cual están en el almacenamiento
compartido; `WhatsApp/Databases/…`, `WhatsApp/Backups/…`, `WhatsApp/Media/…` (y `WhatsAppBusiness/…`)
desde `Android/media/com.whatsapp/WhatsApp/`; datos que no son archivos, exportados a
`_datos/contactos.vcf`, `_datos/llamadas.json`, `_datos/sms.json`, `_datos/apps.json`, `_datos/ajustes.json`.

## Panel
Ficha del equipo → **Respaldos**: último completo, respaldo de cierre, ocupación y cuota, «Respaldar
ahora», «Pedir respaldo de cierre», activar/desactivar, tabla de instantáneas con totales por categoría y
autorización de restauración desde otro equipo. Backend: `admin-panel/backend/app/dispositivos/respaldos.py`.
Servidor: `backend/app/dispositivos/{respaldos,objetos,respaldos_mantenimiento}.py`, migración
`2026-09-18-dispositivos-fase3.sql`, unidades systemd con `ReadWritePaths=-/mnt/almacen/.respaldo-movil`.

# Fase 4 — aplicaciones, reasignación y destino del respaldo

## Aplicaciones (`POST /api/dispositivos/apps`)
El teléfono envía su lista de apps `{apps: [{paquete, nombre?, version?, instalador?, firma_sha256?, permisos[], sistema}]}`
(hasta 1000). El servidor la cruza con las reglas y responde `{avisos: [{paquete, veredicto, accion, texto}]}`.
- **Veredicto**: `ok`, `sospechosa`, `bloqueada`. **Acción**: `ninguna`, `avisar`, `desinstalar` (esta última
  solo en equipos con control completo; en modo limitado se degrada a `avisar`).
- Reglas base (semilla): Google Play y Galaxy Store como instaladores de confianza; accesibilidad,
  administrador de dispositivo y superposición como permisos de riesgo (avisar). Señales automáticas:
  instalada fuera de una tienda conocida u origen desconocido.
- La app muestra `texto` a la persona con un botón que abre la desinstalación. Con control completo,
  Tecnología puede además enviar el comando `desinstalar` o `bloquear_app` con `{paquete}` (llega por el
  latido). El teléfono debe reenviar su inventario tras instalar o desinstalar algo, y al menos cada
  `apps.reinventariar_horas` (24). Play Protect debe estar activo (`play_protect` en el latido).

## Reasignación con historial de custodia
La reasignación la hace Tecnología en el panel (ficha del equipo → «Custodia y reasignación»): cierra el
tramo del custodio anterior, abre el del nuevo y, opcionalmente, encola el respaldo de cierre. La app no
necesita nada: en su próximo `GET /yo` verá el nuevo custodio. Sirve para la cadena jefe → subordinado →
técnico sin apagar el equipo.

## Destino del respaldo y usuario del teléfono
En la ficha del equipo, bloque «Respaldos», se fija la **carpeta en el almacén** donde va el respaldo de ese
teléfono (letras, números, punto, guion y guion bajo; por defecto el número del equipo). Solo se puede
cambiar **antes del primer respaldo**. El **usuario del teléfono** es el custodio (correo), que se asigna
en la reasignación o en la ficha. `PUT /api/dispositivos/equipos/{id}/respaldo-config` acepta
`{respaldo_activo, cuota_respaldo_gb, carpeta_respaldo}`.

## Panel
- **Reglas de apps** (`GET/POST/DELETE /api/dispositivos/apps-reglas`): lista de bloqueo por paquete o
  firma, instaladores de confianza y permisos de riesgo. Las reglas base del sistema no se borran.
- Ficha del equipo: bloque **Aplicaciones** (con las de riesgo primero y desinstalación en control
  completo), **Custodia y reasignación** (historial y reasignar) y la carpeta de respaldo en **Respaldos**.
Backend: `admin-panel/backend/app/dispositivos/{apps_panel,custodia}.py`; servidor:
`backend/app/dispositivos/apps.py`; migración `2026-09-18-dispositivos-fase4.sql`.

# Mejora transversal — avisos push nativos (ntfy autoalojado, sin Google)

Para que los **mensajes urgentes y los comandos lleguen al instante** sin esperar el latido (hasta 15
min), el servidor publica un aviso en un servidor **ntfy autoalojado**. No interviene Google ni ningún
servicio externo. El aviso solo dice «sync» (sin contenido): el teléfono despierta y hace su latido
normal, que trae los mensajes o comandos por el canal seguro de siempre.

## Infraestructura (VM 130)
- `ntfy` 2.11 (binario de GitHub) como servicio `ntfy`, escucha en `127.0.0.1:2586`, config
  `/etc/ntfy/server.yml` (`auth-default-access: read-only`, `auth-file` con el usuario `backend`).
- nginx sirve ntfy en el **puerto 2587** con el certificado y los nombres de mail.maquita.org
  (`/etc/nginx/sites-available/ntfy-push.conf`). Cortafuegos: 2587 abierto solo para Ecuador (nft) y
  NAT en el MikroTik pendiente si se quiere desde fuera de la LAN (ver más abajo).
- Usuario `backend` con permiso de **escritura** sobre `disp_*`; su token está en
  `admin-panel/backend/.env` (`NTFY_TOKEN`, `NTFY_URL_INTERNO=http://127.0.0.1:2586`) y hay copia en
  `/root/ntfy-backend-token.txt`. Los teléfonos **leen** su tema sin token: el tema es un secreto de
  128 bits (`disp_` + 32 hex) y nadie más lo conoce. El aviso no lleva datos, así que aunque se
  filtrara un tema, solo provocaría un latido de más.

## Contrato para la app
- Al enrolar y en `GET /yo`, la respuesta trae `push: {servidor, tema, protocolo: "ntfy"}` (o `null`).
- La app se suscribe con **UnifiedPush** (distribuidor ntfy autoalojado, `servidor`) al `tema`, o
  directamente por el flujo de ntfy (`GET <servidor>/<tema>/json`, SSE/WebSocket). Al recibir cualquier
  aviso, dispara un latido inmediato; con eso trae mensajes y comandos al momento.
- El push es **best-effort y complementario**: si ntfy o la red fallan, el latido periódico entrega
  igual lo pendiente. La app nunca debe depender solo del push.

## Cuándo publica el servidor
- Un **mensaje** nuevo a los equipos destinatarios (`disp_mensajes` → aviso a cada tema).
- Un **comando** nuevo (localizar, alarma, bloquear, borrar, desbloquear, respaldar, desinstalar,
  bloquear_app): el aviso sale al encolarlo (`_encolar`).

## Pendiente operativo
- Para que el push llegue con datos móviles (fuera de la Wi-Fi), falta el **NAT del puerto 2587** en el
  MikroTik (`179.49.24.165:2587 → 193.16.0.21:2587`), como el resto de puertos del correo. Dentro de la
  LAN ya funciona. Alternativa más limpia a futuro: subdominio `push.maquita.org` en el 443 (ntfy exige
  un host propio, no admite sub-ruta), con su registro DNS y el nombre añadido al certificado.

# Mejora transversal — cuenta del sistema de Android con sincronización

Para que el correo Maquita aparezca en **Ajustes → Cuentas → Agregar cuenta** de Android y desde ahí se
sincronicen contactos, calendario, correo y fotos con el servidor, casi todo es trabajo de la app
(`AccountManager` + `SyncAdapter`). El servidor aporta dos cosas, ya en producción:

## 1. Descubrimiento de cuenta por dominio (`GET /api/cuenta/descubrir?correo=<correo>`)
Público. Dado un correo, resuelve su portal (mail.maquita.org o el de la empresa: maquitaturismo.com,
invertiagro.com…) y devuelve en una sola llamada todo lo que necesita la cuenta del sistema:
`{encontrado, correo, usuario, dominio, organizacion, servidor, imap{host,puerto,seguridad},
smtp{host,puerto,seguridad,alternativo}, caldav{url,descubrimiento,auth}, carddav{...}, api{base,ws},
push{servidor,protocolo}, auth{tipo,nota}}`. El usuario es siempre el correo completo.

## 2. CalDAV/CardDAV accesible desde fuera con las credenciales del correo
Antes (contención del 03/09/2026) `/dav/` solo se abría en la red interna. Desde el 18/09/2026 autentica
cada petición por Basic contra las credenciales reales del correo (`auth_request → /api/auth/dav`, que
acepta la contraseña de aplicación o la principal mientras no sea obligatoria) y solo entonces pasa
`X-Remote-User` a Radicale (`rights owner_only`: cada quien ve lo suyo). Probado: sin clave 401, clave
mala 401, clave correcta 207, un usuario mirando la colección de otro 403. Vale para los tres portales
(el bloque está en `snippets/webmail-portal-comun.conf`, incluido por todos). `.well-known/caldav` y
`.well-known/carddav` redirigen a `/dav/`.

## Contrato para la app (cuenta del sistema)
- **Tipo de cuenta** `org.maquita.correo` con `AbstractAccountAuthenticator`: la pantalla de alta pide el
  correo, llama a `/api/cuenta/descubrir`, y guarda usuario + contraseña (o contraseña de aplicación).
- **SyncAdapter de contactos** (`ContactsContract`, CardDAV a `carddav.url`, Basic con las credenciales).
- **SyncAdapter de calendario** (`CalendarContract`, CalDAV a `caldav.url`).
- **Correo**: el canal propio (`api.base`, `api.ws`) o IMAP/SMTP; interruptor de sincronización.
- **Fotos**: respaldo de la fase 3 (no es sincronización bidireccional).
- Cada interruptor con `ContentResolver.setSyncAutomatically`, para que aparezcan en la pantalla nativa
  de la cuenta igual que en una cuenta de Google.

Backend: `backend/app/cuenta/router.py`. DAV externo: `snippets/webmail-portal-comun.conf`
(backup `.bak.20260918-dav`).
