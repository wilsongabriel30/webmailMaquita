# Teléfonos institucionales (gestión de dispositivos) — fases 1 a 4

Gestión propia de los celulares de la organización: inventario y asignación, estado que reporta
cada equipo, mensajes urgentes con acuse de lectura y eventos de seguridad. Las fases siguientes
(ubicación y modo perdido, respaldos, control de aplicaciones) se apoyan en estas mismas tablas.

| Pieza | Dónde | Qué hace |
|---|---|---|
| API de los teléfonos | `backend/app/dispositivos/` (`/api/dispositivos/*` del webmail) | Enrolamiento con código, latidos, entrega de comandos y mensajes, acuses, eventos |
| Administración | `admin-panel/backend/app/dispositivos/` y `admin-panel/frontend/src/pages/Dispositivos.tsx` | Equipos, ficha de inventario y depreciación, códigos de enrolamiento, mensajes urgentes |
| Datos | `migrations/2026-09-18-01-dispositivos.sql` (tablas `disp_*`) | — |

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
`migrations/2026-09-18-02-dispositivos-fase2.sql`.

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
`2026-09-18-03-dispositivos-fase3.sql`, unidades systemd con `ReadWritePaths=-/mnt/almacen/.respaldo-movil`.

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
`backend/app/dispositivos/apps.py`; migración `2026-09-18-04-dispositivos-fase4.sql`.

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

# Cambios del 22/09/2026 — código asignado por Tecnología (AE-04) y portal de telemetría (AE-03)

## Código de enrolamiento asignado a una persona (v5)
- **Solo Tecnología crea códigos**, desde el panel (Teléfonos institucionales → Códigos de
  enrolamiento). Al crearlo puede **asignarlo a un buzón** (`custodio_email`, con buscador): esa persona
  queda como custodia al enrolar, y la tabla del panel muestra a quién está asignado, si ya se usó y
  desde qué equipo. Una persona tiene un solo código vigente: asignarle otro anula el anterior.
- `POST` y `DELETE /api/settings/mi-equipo` **se retiraron** (405): el correo web ya no genera ni
  anula códigos. Configuración → «Mi teléfono» es de solo lectura.
- **`GET /api/settings/mi-equipo`** (cookie del correo) responde ahora
  `{tiene_codigo_activo, prefijo, caduca_en, codigo, equipos}`. `codigo` es el código en claro
  (`xxxx-xxxx-xxxx`) cuando hay uno asignado y vigente para esa persona; si no, `null`. La app 1.2.8
  ofrece «Activar» con él. Cada entrega del código en claro queda en `admin_audit`
  (`dispositivo_codigo_ver_custodio`, sin `admin_id`).
- **Cómo se guarda (compromiso documentado):** el código asignado se guarda **cifrado** (Fernet) en
  `disp_codigos.codigo_cifrado` con la llave `DISP_CODIGO_CLAVE` del `.env` del backend y del panel
  (nunca en la base), solo mientras está vigente: se borra al agotarse los usos (en el propio
  enrolamiento), al anularse (panel) y al caducar (trabajo de alertas). Se descifra únicamente para el
  custodio autenticado (su sesión ya pasó el segundo factor si lo tiene) y para administradores del
  panel (`GET /api/dispositivos/codigos/{id}/ver`, auditado como `dispositivo_codigo_ver`). Se pierde el
  «solo se muestra una vez» a cambio de que la persona no dependa de Tecnología para volver a verlo;
  sigue con usos limitados, caducidad y anulable. Los códigos sin persona siguen siendo «una vez» y en la
  base solo queda su SHA-256. Sin la variable configurada, el panel avisa y no guarda nada en claro.
- Migración: `migrations/2026-09-22-01-dispositivos-codigo-asignado.sql`.

## Latido: campo nuevo opcional para la app
`POST /api/dispositivos/latido` acepta además **`admin_activo`** (booleano: si la app sigue siendo
administradora del dispositivo). Se guarda en `disp_equipos.admin_activo` y en el JSON del latido. La
1.2.8 no lo manda; mientras tanto el portal lo deduce (control completo = sí; limitado = «—» o «NO» si
hay un evento `admin_desactivado` sin revisar). **Pedido a la app:** mandarlo en cada latido.

## Portal de telemetría (panel, `/dispositivos` → «Telemetría» y «Alertas»)
Telemetría **del equipo**, no de la persona: nada de contenido, apps de uso ni navegación; la ubicación
no aparece (sigue bajo la regla de la fase 2). Todo GET lo puede ver el rol `viewer` (dirección).

| Ruta del panel | Qué devuelve |
|---|---|
| `GET /api/dispositivos/telemetria/flota` | `{publicada:{versionName,versionCode,fecha}, totales:{equipos,reportando_hoy,rojo,con_alertas}, equipos:[…]}`; cada equipo trae `semaforo` (verde < 1 h, amarillo < 24 h, rojo), `almacenamiento_pct`, `version_atrasada`, `admin_activo`, `play_protect`, `eventos_rojos_7d`, `eventos_sin_revisar`, `urgentes_sin_acuse`, `alertas_abiertas`, `alertas[]` |
| `GET /api/dispositivos/telemetria/flota.csv` | La misma tabla en CSV (`;`, UTF-8 con BOM). Queda en `admin_audit` (`dispositivo_telemetria_csv`) |
| `GET /api/dispositivos/telemetria/equipos/{id}?rango=24h\|7d\|30d` | `serie` (24h/7d: cada latido con `t, bateria, cargando, almacenamiento_libre, almacenamiento_total, red`; 30d: filas de `disp_resumen_diario`), `eventos`, `mensajes` (con `leido_en` y custodio), `comandos`, `versiones` (por las que pasó, con desde/hasta), `alertas` (30 días) |
| `GET /api/dispositivos/alertas?abiertas=true\|false` | Alertas abiertas (o últimos 30 días) con datos del equipo, `config` (umbrales) y `estado` |
| `PUT /api/dispositivos/alertas/config` (admin) | Umbrales: `sin_reportar_horas, bateria_pct, bateria_horas, almacenamiento_pct, version_atrasada_dias, acuse_horas, correo_ti, resumen_diario_para, resumen_hora, activo` |
| `GET /api/dispositivos/codigos` | Ahora con `custodio_email`, `recuperable` y `usado_por[]` |
| `GET /api/dispositivos/codigos/{id}/ver` (admin) | Código en claro de uno asignado y vigente (auditado) |

La **versión publicada** se lee del disco (`descargas-app/maquita-mail.json`); una app se marca
atrasada si su `versionName` es menor.

## Alertas automáticas (`maquita-disp-alertas.timer`, cada 15 min)
Trabajo del backend del correo (`python -m app.dispositivos.alertas_tarea`). Evalúa las reglas de
`alertas_reglas.py` con los umbrales de `disp_config.alertas`, abre una fila en **`disp_alertas`**
(`equipo_id, tipo, detalle, desde, hasta, avisada_en`; índice único por equipo y tipo mientras
`hasta IS NULL`) por cada condición nueva, cierra (`hasta`) las que dejaron de cumplirse y envía **un
solo correo** a `correo_ti` con las nuevas; si el envío falla, `avisada_en` queda NULL y se reintenta.
Resumen diario opcional a `resumen_diario_para` a la hora `resumen_hora` (una vez por día,
`disp_config.alertas_estado`). Tipos: `sin_reportar`, `bateria_baja`, `almacenamiento_bajo`,
`version_atrasada`, `admin_desactivado`, `desinstalacion_intento`, `sim_cambiada` (estos tres se
cierran al marcar el evento «revisado»), `play_protect_apagado`, `mensaje_sin_acuse`.

## Retención
- `disp_latidos`: `retencion_latidos_dias` de la política (30). Los borra el trabajo de alertas (y,
  ocasionalmente, el propio latido).
- **`disp_resumen_diario`** (nuevo): una fila por equipo y día (latidos, batería mín/máx/prom,
  almacenamiento libre mín/prom y total, versión de app y Android, latidos por wifi/móvil), recalculada
  para hoy y ayer en cada corrida; se conserva **400 días** (12 meses de tendencia). Es lo que alimenta
  la gráfica de 30 días y el historial de versiones más allá de los 30 días de latidos.
- `disp_alertas`: no se borra (es historial); el panel muestra 30 días.
- Migración: `migrations/2026-09-22-02-dispositivos-telemetria.sql`.

## Runbook
`docs/RUNBOOK-TELEFONOS-TELEMETRIA.md` (copia en `02-MODULOS/GESTION-DISPOSITIVOS-MOVILES/RUNBOOK-TELEMETRIA-TELEFONOS.md`).

## Anclas de red por sede (etapa 1 de la triangulación propia, 22/09/2026)
La ubicación de un celular es aproximada; para afinarla con nuestros propios puntos fijos:
- **Etapa 1 (hecha, solo servidor):** tabla `disp_anclas_red` (`tipo` red/bssid, `valor` CIDR o BSSID,
  `sede`, `nombre`, `lat`, `lon`, `radio_m`, `activa`). En cada latido, si la IP del teléfono cae en
  una red ancla (`app/dispositivos/anclas.py`), se anota `disp_equipos.ancla_sede/ancla_en` (siempre,
  es dato de red como la IP; la flota lo muestra en la columna «Red») y, **solo si la ubicación está
  autorizada o el equipo está perdido**, se guarda una posición con `origen = 'ancla'`, `fuente = 'red'`
  y `precision_m = radio_m`, como mucho una cada 15 min por equipo y sede. Sembradas: Maquita central
  (193.16.0.0/24 y 179.49.24.160/28, coordenadas del GPS del NTP, 60-80 m) y las subredes internas de
  los MikroTik de las demás sedes con coordenadas provisionales del centro de cada ciudad y radio 3 km,
  a afinar desde el panel (Telemetría → «Anclas de red por sede»). También las IP públicas fijas de cada
  sede (`/32`, leídas en el MikroTik de Quito el 22/09): así se ancla un teléfono en el wifi de la sede
  aunque no pase por la VPN. Si un proveedor cambia la IP, actualizarla en el panel.
- Panel: `GET/POST /api/dispositivos/anclas`, `DELETE /api/dispositivos/anclas/{id}` (alta y baja solo
  admin, auditadas `dispositivo_ancla_*`). En la ficha, la posición por ancla se muestra en azul:
  «En la sede: conectado a la red de Maquita».
- **Etapa 2 (pedido a la app):** que el latido traiga `wifi: {bssid, rssi}` del punto de acceso al que
  está conectado y que la respuesta a «localizar» traiga `wifis_vistas: [{bssid, rssi}]` (hasta 20).
  Con anclas de tipo `bssid` (MAC de cada punto de acceso de Maquita con sus coordenadas) el servidor
  calculará la posición por intensidad (centroide ponderado) dentro de las sedes, 5-15 m.

## «Teléfono extraviado» en el correo web (22/09/2026)
Configuración → «Mi teléfono». Para la persona, sin datos técnicos: última ubicación conocida (la más
precisa de los últimos 15 min respecto a la más reciente; margen en palabras; enlaces a Google Maps y
OpenStreetMap), «Ubicar ahora» y «Hacer sonar».
| Ruta (cookie del correo, solo custodio) | Respuesta |
|---|---|
| `GET /api/settings/mi-equipo/ubicacion` | `{equipos:[{id, nombre, estado, ultimo_contacto, ubicacion_permitida, posicion:{lat, lon, precision_m, cuando, margen, minutos}|null, buscando}]}` |
| `POST /api/settings/mi-equipo/{id}/localizar` | Encola `localizar` (con push ntfy, `push_ntfy.py`); 404 si el teléfono no es suyo; 429 si lo pidió hace < 1 min |
| `POST /api/settings/mi-equipo/{id}/sonar` | Encola `alarma` |
Auditoría: `dispositivo_custodio_localizar` / `dispositivo_custodio_alarma` (sin `admin_id`). El backend
del correo necesita `NTFY_URL_INTERNO` y `NTFY_TOKEN` en su `.env` (los mismos del panel).

## Wifi conectado (pedido de dirección, 22/09/2026)
El latido acepta además **`wifi_ssid`** (nombre de la red, ≤ 64) y **`wifi_bssid`** (MAC del punto de
acceso, `aa:bb:cc:dd:ee:ff`); Android exige el permiso de ubicación para leerlos. Se guardan en
`disp_equipos.wifi_ssid/wifi_bssid/wifi_en` (solo cuando `red` es wifi; con datos móviles se limpian).
Uso: Configuración → «Teléfono extraviado» muestra «Está conectado al wifi “X”» (si es el de su casa,
ahí lo dejó); la flota del panel lo muestra bajo la columna «Red». El `bssid` es la base de la etapa 2
(anclas por punto de acceso). Migración `2026-09-22-04-dispositivos-wifi-ssid.sql`.
**Pedido a la app:** mandar ambos en cada latido cuando esté en wifi.

## Lotes GNSS crudos (etapa 3, 22/09/2026)
`POST /api/dispositivos/gnss` (token del equipo): `{inicio, fin, segundos, formato: "gnsslogger-txt",
modelo?, android?, capacidades?, fix?: {lat, lon, precision}, datos_gz: base64(gzip(texto))}` ≤ 8 MB →
`{id, bytes}`. Se guarda en `DISP_GNSS_DIR` (por omisión `/var/lib/maquita-webmail/gnss/<equipo>/`) y en
`disp_gnss_lotes`; el procesamiento (RINEX + RTKLIB contra la estación REGME más cercana, datos gratuitos
del Geoportal del IGM con hasta 5 días hábiles de retraso, o REGME-IP por NTRIP en tiempo real) es fuera
de línea y escribe `resultado`. Comando del panel **`gnss_crudo`** con `segundos` (10-900, 60 por
omisión). Prompt para la app: `WEBMAIL-CALENDARIO/app-movil/PROMPT-APP-WIFI-ANCLAS-Y-GNSS-CRUDO.md`.

## IMEI (varios por equipo) — 22/09/2026
Doble SIM y eSIM dan 2, 3 o 4 IMEI. Sirven para que la operadora bloquee el equipo si lo roban o lo
pierden, así que se muestran **al administrador** (ficha del panel, recuadro «IMEI para la operadora»
con Copiar) y **a la persona** (correo web → «Mi teléfono», con Copiar y «Registrar / Agregar o corregir»).
- `disp_equipos.imeis` (JSONB, lista ≤ 4; `imei` sigue siendo el principal). Migración `2026-09-22-06`.
- App: `POST /enrolar` y `POST /latido` aceptan **`imeis: [..]`** (14-17 dígitos cada uno; se unen a los
  existentes, lo que reporta el teléfono va primero). **Solo se pueden leer con control completo (Device
  Owner) desde Android 10**; en modo limitado la app no puede y debe pedir a la persona que los escriba
  (o mostrar la instrucción *#06#).
- Persona: `PUT /api/settings/mi-equipo/{id}/imeis` `{imeis: "…, …" | [..]}` (custodio; auditado
  `dispositivo_custodio_imeis`). Los que reportó el teléfono no se pierden.
- Panel: `PUT /api/dispositivos/equipos/{id}` acepta `imeis` (texto con comas o lista).

## QR de aprovisionamiento desde el panel (22/09/2026)
Códigos de enrolamiento → botón **«Ver QR»** en los códigos de control completo (y «Ver QR para
enrolar» al crearlo). `POST /api/dispositivos/codigos/qr` `{codigo?}` o `{codigo_id?}` → `{svg, con_codigo,
version, json}` (admin; auditado `dispositivo_codigo_qr`). El QR lleva el componente
`org.maquita.mail/org.maquita.mail.equipo.AdministradorEquipo`, la URL del APK publicado, su huella
SHA-256 (base64url, calculada del archivo en `descargas-app/`, así siempre es de la versión vigente),
`es_EC`, `America/Guayaquil` y, cuando el código está en claro (recién creado o asignado y vigente),
`PROVISIONING_ADMIN_EXTRAS_BUNDLE = {"codigo_enrolamiento": "xxxx-xxxx-xxxx"}` para que la app se
registre sola. Procedimiento para no técnicos en la propia ventana y en
`QR-APROVISIONAMIENTO/COMO-ENROLAR-CON-CONTROL-COMPLETO.md`. Requiere `segno` en el venv del panel.
**Pedido a la app:** al completar el aprovisionamiento (`PROFILE_PROVISIONING_COMPLETE` /
`ACTION_ADMIN_POLICY_COMPLIANCE`) leer `codigo_enrolamiento` de los extras y enrolar sin teclear.
