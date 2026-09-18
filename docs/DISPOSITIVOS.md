# Teléfonos institucionales (gestión de dispositivos) — fases 1 a 3

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
