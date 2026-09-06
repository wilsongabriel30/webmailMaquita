# Registro de cambios

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
y este proyecto sigue el [Versionado Semántico](https://semver.org/spec/v2.0.0.html).

## [Sin publicar]

### Seguridad

- **[L-04] El atajo CSS `font` sale de la lista de propiedades permitidas en `style`** (las sueltas
  `font-family`, `font-size`, `font-weight`, `font-style`, `font-variant` siguen). La etiqueta
  `<font>` con `color/size/face` se mantiene: es inerte y la usan muchos correos antiguos.
- **[H-04] Comparaciones con la contraseña maestra en tiempo constante** (`hmac.compare_digest`) en
  la sesión IMAP impersonada y en el SASL de SMTP.
- **[H-03 / F-09] Códigos de respaldo de 2FA: 128 bits, hash con sal, un solo uso atómico.** Un
  código por fila en `user_totp_backup_codes` (migración `2026-09-06-codigos-respaldo.sql`);
  los anteriores (32 bits, en claro, consumo no atómico) dejan de valer y cada persona con
  2FA genera unos nuevos desde Ajustes (`POST /api/auth/totp/backup-codes`, exige TOTP vigente).

### Corregido

- **El instalador genera `ALMACEN_CLAVE_SESION`** en `almacen/.env` (obligatoria desde 1.7.0 por
  R-01; sin ella el almacén no arranca al primer reinicio). Reportado por Andes al actualizar
  1.7.0 → 1.7.2. `UPGRADING.md` la documenta como variable nueva de 1.7.0.

## [1.7.2] - 2026-09-06

Correcciones de la sexta revisión (panel) y del lote P2 de la tercera revisión (almacén).
Sin corte de sesiones. Pasos del almacén (dependencia `argon2-cffi`, reinicio, `Referrer-Policy`
por mapa en nginx) en `UPGRADING.md`, sección «De 1.7.1 a la siguiente».

### Seguridad

- **[F-11] Una unidad compartida no puede quedarse sin manager.** Degradar o quitar al último manager
  (incluido uno mismo) responde 409 dentro de una transacción con las membresías bloqueadas; el
  override del master en la gestión de miembros queda explícito.
- **[F-07] Las capacidades de OnlyOffice nacidas de un enlace público mueren con el enlace.** Llevan el id
  y la versión del share y se revalidan en cada descarga y callback (existe, no venció, misma versión,
  y para guardar sigue permitiendo editar); la de descarga pública dura 30 minutos, no 7 días.
- **[F-08] Clave de los enlaces compartidos: nunca en la URL, Argon2id y límite de intentos.** La clave
  viaja en la cabecera `X-Clave-Enlace` (o el cuerpo), se guarda con Argon2id con sal (los hashes
  SHA-256 anteriores se migran al primer acierto), hay límite de 10 fallos cada 10 minutos por enlace
  e IP, y la página del enlace y las respuestas públicas llevan `Referrer-Policy: no-referrer` y
  `Cache-Control: no-store`. Nueva dependencia del almacén: `argon2-cffi`.
- **[L-03 panel] `DB_PASS` entra en la validación de arranque** (fail-fast si falta).
- **[L-02 panel] La auditoría de SafeAttach y SSO ya no falla en silencio**: si no se puede registrar,
  ERROR con marca `AUDITORIA_NO_REGISTRADA` (misma regla que el milter).
- **[M-03/L-01 panel] Último rastro de `bash -c` y `create_subprocess_shell`** (estado SSO, sincronización
  LDAP, lectura de rebotes): listas de argumentos y lectura de ficheros en Python, sin shell.
- **[M-02 panel] `fail2ban/unban` y `unban-all` validan `jail` e `ip`** (lista cerrada de caracteres y
  `ipaddress`) antes de pasarlos a `fail2ban-client`.
- **[M-01 panel] Matriz `admin` / `superadmin` aplicada.** Retención, acceso condicional, límites y
  bloqueo de envío, geo-bloqueo, sincronización LDAP, ingestión y dominios del RAG y políticas de
  seguridad exigen `superadmin` (`require_superadmin` en la ruta). Antes bastaba `admin`. `DECISIONES.md` D-6.
- **[H-02 panel] `GET /api/branding` (público, lo usa la pantalla de entrada) devuelve solo nombre, lema,
  contacto, colores y ficheros de marca**; el resto de claves de `branding_settings` ya no sale. Mismo
  recorte en el `/api/branding` del correo.

### Corregido

- **[F-06] La tabla `cuotas_reservas` también se crea desde `app_webmail`** (la aplicación que corre en
  producción) y bajo `pg_advisory_xact_lock`, para que el DDL concurrente de varios workers no
  provoque deadlocks en el arranque del almacén.
- Documentación: `docs/PANEL-RUTAS-ROLES.md` (246 rutas → rol), `DECISIONES.md` D-6 (matriz
  admin/superadmin), ejemplo de nginx del almacén con `Referrer-Policy` por mapa.

## [1.7.1] - 2026-09-06

Lote tras la pasada fría sobre 1.7.0 y el informe de actualización de Correo Andes. Sin corte de sesiones.

### Seguridad

- **[F-02] SAML: aserción validada de verdad.** Toda lectura (Status, Assertion, NameID) sale del XML
  que devolvió el verificador de firma, nunca del árbol original (XML Signature Wrapping); se exige
  exactamente una Assertion; `InResponseTo` se consume de un solo uso (GETDEL); se validan `Destination`,
  `Recipient`, `AudienceRestriction`, `NotBefore`/`NotOnOrAfter` con tolerancia de reloj y el `ID` de la
  Assertion es de un solo uso (SET NX). `signxml` y `lxml` fijados (R-11). Pruebas negativas con un IdP
  de laboratorio para cada condición, incluido el wrapping. SAML sigue inactivo hasta probarlo con el IdP
  real. Cierra A-10.
- **[R-03] Importación de contactos y correos con límite en la aplicación y sin cargar el archivo en
  memoria.** `import_contacts_max_mb` (10) e `import_emails_max_mb` (200); el upload va a disco en
  trozos y MBOX se analiza desde el archivo. nginx (`client_max_body_size`) queda como segunda capa.
- **[F-06] La cuota del Drive se aplica al admitir archivos.** Antes solo se calculaba y se mostraba: se
  podía superar subiendo varios archivos. Ahora, antes de escribir, se reserva atómicamente el tamaño
  declarado (bloqueo de la fila de uso), hay un umbral global de espacio libre (`ALMACEN_MINIMO_LIBRE_BYTES`,
  5 GB) y, sin `Content-Length` fiable, se contabiliza durante el streaming y se aborta al superar la cuota
  (413) o el espacio (507). Pruebas en `almacen/tests/test_cuota_admision.py`.
- **[F-05] Webhooks sin SSRF por DNS.** La validación resolvía el nombre una vez y la entrega volvía a
  resolverlo (rebinding hacia 127.0.0.1 o la red interna). Ahora se resuelven TODAS las A/AAAA con
  `getaddrinfo`, se rechaza si cualquiera es privada/loopback/enlace local, y la entrega conecta a la
  IP validada con `Host` y SNI del nombre, sin seguir redirecciones; en producción solo `https://`.
  Política de egreso del sistema para el proceso en `deploy/webmail/nftables/egreso-backend.nft`.

## [1.7.0] - 2026-09-06

Cierra la P0 y la P1 de la tercera, cuarta y quinta revisión externa (ASVS). **Corte único al
desplegar**: todo el mundo vuelve a iniciar sesión una vez. Cómo actualizar desde 1.6.1: `UPGRADING.md`.

### Añadido

- **«Cerrar todas las sesiones»** en Ajustes → Contraseña (L-01, versión mínima): cierra webmail, app
  y chat en todos los dispositivos. El listado por dispositivo queda para después.

### Seguridad

- **[M-07 chat] Ningún registro lleva el contenido de los mensajes.** Los `print()` con el payload
  completo (mensajes, eventos de llamada, `join`) pasan a `logger.debug` con id, remitente, sala y
  tamaño. Prueba de regresión que falla si vuelve a aparecer un campo de contenido en un registro.
  Amplía F-10.
- **[M-06 chat] `MAX_CONTENT_LENGTH` de 16 GB a 100 MB**, configurable con `CHAT_MAX_CONTENT_MB`.
- **[M-05 chat] Fuera el secreto de Keycloak escrito en el código.** `KEYCLOAK_CLIENT_SECRET` sin valor
  por defecto; `KEYCLOAK_ENABLED` pasa a `false` salvo que se pida, y habilitarlo sin secreto aborta el
  arranque. **El valor anterior está publicado: hay que rotarlo en Keycloak.**
- **[M-04 chat] Solo los invitados entran a una conferencia.** `conference_invite` guarda la lista de
  invitados (y exige que quien invita sea participante de la conversación, si la hay);
  `conference_join` la comprueba. Conecta con A-5 (grabaciones).
- **[M-05] El atributo `style` de los correos pasa por una lista blanca de CSS.** `background-image:
  url(...)` y similares (balizas de lectura, fuga de IP), `expression()`, `@import`, `behavior` y
  `position: fixed` se descartan declaración a declaración; el resto del estilo se conserva para no
  romper los correos HTML. Pruebas en `backend/tests/test_sanitize_style.py`.
- **[H-01] Sin contraseña «bootstrap» conocida.** Desaparece la constante del código. Cada buzón nuevo
  (o reset del admin) recibe una contraseña aleatoria de un solo uso y queda con
  `must_change_password` en `auth_estado`; mientras esté activa, el servidor solo permite cambiar la
  contraseña o cerrar sesión (403 en lo demás). El instalador genera la clave inicial del buzón demo.
  Absorbe R-02. Migración `2026-09-06-cambio-obligatorio.sql`.
- **[H-02] Llave de cifrado de credenciales dedicada y versionada.** Antes se derivaba de `SECRET_KEY`.
  Ahora `CREDENTIAL_ENCRYPTION_KEY` (obligatoria, Fernet) cifra la credencial IMAP cacheada, las cuentas
  de Nextcloud y **el secreto TOTP, que estaba en claro** (L-03); `CREDENTIAL_ENCRYPTION_KEY_ANTERIOR`
  permite rotar. `deploy/tools/recifrar-credenciales.py` migra lo guardado; un secreto TOTP sin cifrar
  ya no valida (fallo cerrado). Entra con el corte de sesiones de 1.7.0 (`UPGRADING.md`).
- **[R-01] El almacén ya no arranca con una clave de sesión por defecto.** `ALMACEN_CLAVE_SESION`
  es obligatoria (≥ 16 caracteres, sin valor de ejemplo), como los secretos del backend. La unidad
  de systemd documenta cuándo hace falta un segundo `--bind` en la IP de red y que ese puerto va
  limitado por cortafuegos a la VM que lo usa.
- **[R-04] SafeAttach falla cerrado si un motor obligatorio no responde.** Con ClamAV caído el
  adjunto salía `clean` (confirmado con EICAR). Ahora un motor obligatorio (`clamav`; más por
  `SAFEATTACH_MOTORES_OBLIGATORIOS`) que lanza error, no está o agota el tiempo deja el adjunto
  como `suspicious`, lo anota en `errors` y el milter lo manda a cuarentena mirando también
  `errors`, no solo `result`. Pruebas en `backend/tests/test_safeattach_fallo_cerrado.py`.
- **[M-01] Login en dos pasos sin fuga.** La respuesta `requires_2fa` confirmaba que la contraseña era
  válida. Ahora, para una cuenta con 2FA, el primer paso devuelve siempre la misma forma (un vale
  opaco de un solo uso, 60 s) acierte o no la contraseña; el segundo paso `POST /api/auth/login/2fa`
  canjea vale + código y responde igual ante vale inválido o código incorrecto. La decisión de fondo
  (el 2FA no cubre IMAP/SMTP directo) queda en `DECISIONES.md` D-5.

- **[H-01/M-01 chat] Todo evento con `conversation_id` o `message_id` exige ser participante.**
  `send_message` (legado, aún lo usa el cliente), `edit_message`, `delete_message`, `mark_read`,
  `mark_read_batch`, `delivered`, `add_reaction`, `remove_reaction`, `typing_start` y
  `get_messages` no lo comprobaban (solo `send`, `join_conversation` y `sync_chat`). En
  reacciones, borrado y entrega la sala de emisión sale del mensaje en la base, no del payload.
  Hallazgo de la quinta revisión externa.
- **[F-03] El chat obedece a la revocación central.** El vale de entrada lleva `sid` y `av`
  del correo; el correo empuja cada revocación a `POST /api/chat/sesion/revocar` (secreto de
  servicios, límite de peticiones) y el chat anota la generación en su Redis, desconecta los
  Socket.IO afectados y rechaza la sesión en el `before_request` y al conectar. Cada sesión
  revalida contra el correo (`GET /api/auth/sesion-servicio`) como máximo cada 5 minutos, con
  fallo cerrado. Riesgo residual y marca `REVOCACION_CHAT_FALLIDA` en `DECISIONES.md` D-4.
  Nuevas variables del chat: `CHAT_SESION_CENTRAL` (0 = pasivo durante la actualización),
  `CORREO_URL_API` (opcional; si falta usa `CORREO_URL_CALENDARIO`), y del correo:
  `CHAT_INTERNAL_URL` (opcional; si falta, el origen de `embed_url`). Pruebas en
  `chat-service/tests/test_revocacion.py`, con su propio job de CI.

- **[F-01] Ciclo de vida de sesión con `sid` y `auth_version`.** La sesión ya no «vive» en una
  clave por usuario: cada navegador tiene su `sid`, la credencial IMAP se cifra por sesión y el
  access JWT lleva `sid`, `av`, `kind` y `abs_exp`. Cerrar sesión cierra solo la propia; «cerrar
  todas» (nuevo `POST /api/auth/logout-all`), cambiar la contraseña, el reset o la clave puesta
  por el admin, desactivar o eliminar el buzón y la contención AIR suben la generación y revocan
  todos los refresh: un re-login no revive nada, y el WebSocket cierra con 4401 lo revocado.
  **Corte único al desplegar**: todo el mundo vuelve a iniciar sesión una vez. Diseño en
  `docs/DISENO-SESIONES.md`; migración `migrations/2026-09-06-sesiones-sid-av.sql`.
- **[F-04] La impersonación muere a la hora, se renueve lo que se renueve.** El refresh conserva
  `session_kind` y `absolute_expires_at` y nunca emite más allá de ese límite; sin prórroga por
  actividad. Comparte código con F-01 (mismo `refresh`); sus pruebas están en
  `backend/tests/test_lifecycle_sesion.py`.

## [1.6.1] - 2026-09-06

Correcciones tras la instalación desde cero de Correo Andes y la segunda revisión ASVS externa
(cinco hallazgos reales; uno ya cubierto, uno rebajado).

### Seguridad

- **[R-1] La credencial IMAP cacheada que no descifra ya no se usa en claro.** Cuatro sitios
  aceptaban el valor de `imap_pass:*` tal cual si el descifrado fallaba (correo programado,
  `get_user_password`, sondeo del websocket) y las invitaciones de reuniones ni siquiera
  descifraban. Ahora se registra ERROR con marca `CREDENCIAL_NO_DESCIFRA`, se invalida la sesión
  y el usuario vuelve a entrar; el correo programado vuelve a `pending`. Nuevo
  `deploy/tools/purgar-imap-pass-legacy.py` (purga de una vez, con conteo antes y después).
- **[R-2] El límite de peticiones falla cerrado sin Redis.** Antes un fallo de Redis dejaba pasar
  todo. Ahora se limita con un contador en memoria por proceso a la cuarta parte del límite
  normal y se registra ERROR con marca `RATE_LIMIT_SIN_REDIS`.
- **[R-3]** El origen se compara con el dominio de la cookie por host exacto o sufijo con punto,
  no por subcadena.
- **[R-4]** `/api/health/detailed` solo para administradores y sin banners ni mensajes internos.
- **[R-5]** El registro de seguridad recibe método, ruta y mensaje acotado; el traceback completo
  va al registro técnico sin datos de la petición.
- Documentado en código que `X-Real-IP` solo es fiable detrás del proxy del proyecto.

### Corregido

Los siete hallazgos de la instalación desde cero hecha por Correo Andes sobre `v1.6.0-rc5`:

- **Instalador desatendido de verdad.** Con `DOMAIN` por variable o sin terminal ya no se queda
  esperando un «¿Correcto?» que nadie va a contestar; y si se detiene antes del primer paso, el
  mensaje dice que no se instaló nada, en vez de mandar a buscar un error que no existe.
- **El panel nacía en bucle de reinicio.** Su `.env` recibía `JWT_SECRET` pero no
  `ADMIN_JWT_SECRET` (el secreto compartido con el correo) ni los valores prestados que necesitan
  los subprocesos que lanza. Ahora se escriben los dos y los `WEBMAIL_*` imprescindibles.
- **Instalador y validador se contradecían**: el validador exigía fail2ban, el puerto 465 y el
  milter activo, y el instalador no montaba ninguno de los tres. Ahora instala fail2ban con una
  configuración versionada (backend systemd, obligatorio en Debian 13), añade `smtps` (465) a
  Postfix y arranca el milter. Una instalación limpia termina con 0 fallos sin retoques.
- **El despliegue no ensucia el árbol**: `frontend/.env.production` va en `.gitignore`, y los
  iconos propios de la PWA se dejan en `branding/local/` (no versionado), que el despliegue copia
  sobre `dist/`.
- **La marca llega a todo**: el título de la pestaña sale de `app_name` (antes componía
  `org_name + " Mail"` y al cambiar de cuenta volvía al nombre por defecto escrito en código), y el
  despliegue inyecta `name`/`short_name`/`description` en `manifest.json`, que es con lo que el
  celular instala la app. Las guías dicen que tras cambiar la marca hay que reiniciar el backend y
  reconstruir el frontend.
- El resumen final del instalador daba un usuario demo que no existía (`demo@<tu-dominio>`); el
  buzón es `demo@ejemplo.local`, de un dominio de prueba que no recibe correo de fuera, y así lo
  dice ahora. `deploy-webmail.sh` toma la URL final de la configuración, no de un dominio escrito
  en el código. `PON-TU-MARCA.md` explica cómo instalar Pillow en Debian 13 (PEP 668).

## [1.6.0] - 2026-09-06

Cierra la remediación de seguridad de la auditoría del 2026-09-03: fusiona
`remediacion-seguridad-2026-09` en `main` con el CI en verde **sin bypasses**, tras la validación
externa sobre la rama y la instalación desde cero hecha por el equipo de Correo Andes en su propio
centro de datos (sus 7 hallazgos entran como correcciones sobre `main`). Incluye lo publicado en
las candidatas rc4 y rc5.

### Seguridad

- **TLS de nginx con el perfil intermedio de Mozilla.** La configuración versionada del webmail
  traía `HIGH:!aNULL:!MD5` (admitía CBC y suites sin secreto hacia adelante) y la plantilla de
  autoconfig no fijaba cifrados; el panel usaba una tercera lista. Ahora las tres comparten la misma
  lista (solo AEAD con PFS, TLS 1.2/1.3, orden a elección del cliente). Verificado con testssl.sh.
  Era el único de los ocho hallazgos de la auditoría original que faltaba por tocar.
- **`transcribe.py` deja de desactivar la verificación TLS** al hablar con el servidor de dictado.
- **Dependencias del almacén al día**: las aplicaciones BI y editor de PDF fijaban Flask, PyJWT,
  cryptography, Pillow y requests con avisos abiertos (20 High). Subidas a las versiones que los
  corrigen; el conjunto resuelve sin conflictos.
- Los MD5 de ETags de CardDAV, clave de documento de OnlyOffice e id de hilo por asunto se marcan
  como no criptográficos (`usedforsecurity=False`): son identificadores, no protegen nada.

### Cambiado

- **El CI vuelve a decir la verdad.** Al quitar las escapatorias afloró deuda vieja: `black` nunca
  había pasado (208 de 285 ficheros; ahora todo `app/` está formateado y las versiones de black e
  isort van fijadas), `isort` marcaba 151 ficheros, y los 9 ficheros del frontend que tocó la rama
  arrastraban 54 errores de eslint (`any`, bloques vacíos, código muerto, `@ts-nocheck`). Bandit
  bloquea por High; los 64 Medium (casi todos B608 de baja confianza sobre listas blancas) se
  muestran como informe con triage agendado. `trivy-action` sube a una versión sin el aviso crítico
  de cadena de suministro.

### Documentación

- `DECISIONES.md` D-3: `pickle.loads` en el canal interno del editor de PDF, registrado como deuda
  con fecha; se migra a JSON al tocar ese módulo.

### Documentación

- **Una sola guía de instalación.** `INSTALL-DESDE-CERO.md` es la canónica, al día con esta semana:
  el Guardián pre-commit como paso obligatorio, el `.env` del chat con las fuentes externas
  desactivadas por defecto, la marca desde `branding_settings`, la distinción entre lo que falla
  abierto (motores de análisis) y lo que falla cerrado (controles de acceso), y una sección de
  **qué reportar cuando algo falla**, pensada para las réplicas. `INSTALL-NATIVE.md` queda como
  detalle manual por componente e `INSTALL.md` como sustituida.
- El instalador instala el Guardián (paso 7c). El validador (`validar-despliegue.sh`) comprueba
  además los guardianes, el árbol limpio, la ausencia de datos personales y la marca; y **la
  comprobación de IA por fin se ejecuta**: estaba después del `exit` y nunca corría.


### Cambiado

- **[T4] Las fuentes externas de GIF del chat pasan a ser opt-in.** Si no había clave propia
  de GIPHY, el módulo usaba una clave «pública de pruebas» escrita en el código: cada búsqueda de
  la gente salía a un tercero sin que nadie lo hubiera decidido, y quedaba una clave de API literal
  en un repositorio público. Ahora sin `GIPHY_API_KEY` no se consulta a GIPHY, Wikimedia Commons
  exige `GIFS_EXTERNOS_COMMONS=1`, y sin fuentes el endpoint responde que la búsqueda externa está
  desactivada en vez de una lista vacía engañosa. La biblioteca de GIF propia no cambia. Con esto
  el inventario T4 (sin dependencias externas de runtime) queda completo: socket.io ya se servía
  en local y gravatar ya se resolvía en casa.

### Corregido

- **La burbuja de chat sondeaba sin parar con 404 en instalaciones sin chat.** La autodetección
  consultaba `/api/chat/conversations` cada 60 s y en cada cambio de foco, y un 404 —ruta
  inexistente, que no se arregla solo— nunca la detenía: consola llena de errores y una petición
  inútil por minuto y por persona. Además, si la configuración del chat fallaba, se asumía que el
  chat sí estaba habilitado. Ahora tres 404 seguidos detienen el sondeo hasta recargar, y ante
  error de configuración el chat se da por deshabilitado. Detectado por el equipo de Correo Andes.

### Documentación

- `PON-TU-MARCA.md`: se aclara que `manifest.json` no se toca, que la caché del service worker se
  renueva sola en cada despliegue, y de dónde salen `app_name` y `org_name`.


## [1.6.0-rc3] - 2026-09-05

Candidata para la verificación externa. Incluye la remediación de seguridad de la auditoría del
2026-09-03 y los hallazgos reportados por el equipo de Correo Andes.

### Corregido

- **El botón «Cambiar contraseña» quedaba gris sin explicar por qué.** La barra de fuerza contaba
  cuántas reglas se cumplían, sin mirar cuáles: una contraseña de 9 caracteres con mayúscula,
  minúscula, número y símbolo sumaba 4 de 5 y se anunciaba como **«Fuerte» en verde**, mientras el
  botón seguía deshabilitado porque el mínimo de 10 caracteres no se cumplía. La pantalla decía una
  cosa y el botón hacía otra, sin salida posible.

  Ahora la barra no muestra ninguna etiqueta positiva mientras falte un requisito obligatorio:
  dice «Faltan requisitos» en naranja. Y bajo el botón aparece el motivo concreto —qué regla falta,
  que hay que repetir la contraseña, que la confirmación no coincide o que falta la actual—.
  Reproducido con el caso real reportado (`860829Al@`) y con otras cinco contraseñas. Detectado por
  el equipo de Correo Andes.


- **No se podía cambiar la contraseña desde el webmail.** En Ajustes → Contraseña, el campo
  «Confirmar» marcaba «Las contraseñas no coinciden» aunque se escribiera lo mismo en los dos
  campos, y el botón quedaba deshabilitado sin salida. La comparación era correcta: los valores
  de verdad diferían. Dos causas, y ninguna se veía:
  - el gestor de contraseñas del navegador rellenaba «Confirmar» con otro valor, porque los dos
    campos declaraban `autoComplete="new-password"`;
  - un espacio invisible al principio o al final, típico del teclado del móvil o de pegar desde
    otra aplicación.

  «Confirmar» pasa a `autoComplete="off"`, gana el mismo botón de mostrar/ocultar que ya tenía
  «Nueva» —sin él no había forma de ver la diferencia— y, cuando lo único que separa a las dos
  contraseñas son espacios, el mensaje lo dice en lugar del genérico. **Los espacios no se
  recortan solos a propósito:** una contraseña puede llevarlos a posta y cambiarla por detrás
  sería peor. Detectado por el equipo de Correo Andes.

### Seguridad

- **La reverificación por IMAP del cambio de contraseña ahora va cifrada.** `verify_imap` abría
  `IMAP4` sin cifrar y enviaba la contraseña recién puesta tal cual. En esta instalación no se
  notaba, porque el IMAP es `127.0.0.1` y Dovecot admite acceso en claro desde localhost, pero en
  un despliegue con el IMAP en otra máquina la contraseña viajaría por la red sin cifrar; y si ese
  servidor exigiera TLS, el paso fallaría y el cambio se reportaría como no aplicado aunque sí se
  hubiera guardado. Ahora se usa STARTTLS siempre que el servidor lo ofrezca, y si el servidor es
  remoto y no lo ofrece **no se envía la contraseña**. Aviso del equipo de Correo Andes.

### Cambiado

- **La marca visible deja de estar escrita a mano en el código.** Los textos de marca vivían
  repartidos en literales (`"Maquita Mail"`, `"Maquita"`, `"Maquita Webmail"`), lo que obligaba a
  reparchear en cada versión a quien usa el proyecto como base. Ahora salen de `branding_settings`,
  a través de `app/branding/service.py`, y se pueden cambiar sin tocar código. Sugerido por el
  equipo de Correo Andes.

  Se distinguen **dos** valores, porque no son lo mismo:
  - `org_name` — la organización (aquí, «Fundación Maquita Cushunchic MCCH»). Su valor por defecto
    es neutro a propósito: una réplica no debe mostrar la marca de otra organización, porque un
    aviso de seguridad a nombre ajeno parece phishing.
  - `app_name` — el producto de correo (aquí, «Maquita Mail»). Es lo que ve quien usa el sistema.
    Valor por defecto: `Maquita Mail`.

  Puntos parametrizados: emisor del segundo factor (`auth/totp.py`), cabeceras `X-Mailer` y
  `Organization` del correo saliente (`mail/clients/smtp_client.py`), pie de los recordatorios
  automáticos (`reminders_scheduler.py`), identificador de producto iCal, texto de invitación y pie
  de las invitaciones de calendario (`calendar/service.py`), y el título de los avisos del navegador
  y el prefijo del nombre de caché en `frontend/public/sw.js`, que el despliegue inyecta.

  **Cuatro textos cambian de contenido**, porque los literales anteriores eran inconsistentes entre
  sí y ahora se unifican:

  | Texto | Antes | Ahora |
  |---|---|---|
  | Cabecera `X-Mailer` | `Maquita Webmail/1.0` | `Maquita Mail/1.0` |
  | Cabecera `Organization` | `Maquita` | nombre completo de la organización |
  | Identificador iCal | `-//Maquita Webmail//Calendar//ES` | `-//Maquita Mail//Calendar//ES` |
  | Pie de invitación | `… · Fundación Maquita` | `… ·` nombre completo de la organización |

  El resto (emisor del segundo factor, pie de recordatorios, texto de invitación y título de los
  avisos) queda **exactamente igual** en la instalación de Maquita.

  Para los puntos que no tienen la base de datos a mano —el cliente SMTP, sobre todo— hay una caché
  de proceso que se rellena al arrancar. Si no se ha rellenado, se usan los valores por defecto: un
  correo nunca deja de salir por consultar la marca.

  **No se han renombrado los identificadores internos de almacenamiento**: las bases del navegador
  `maquita-mail-offline` y `maquita-cache`, y el global `MaquitaAlmacen`, siguen igual. Renombrarlos
  dejaría sin datos a quien ya los tenga guardados. Queda advertido en el propio `sw.js`.


### Seguridad (remediación de la auditoría 2026-09-03 — rama `remediacion-seguridad-2026-09`)

Entorno en pre-producción sin usuarios reales; el lanzamiento ocurre tras el pentest externo y su
re-test. Cada hallazgo lleva su código del informe y un commit propio, con prueba antes/después.

- **[C-7] Unidades compartidas del Almacén sin control de membresía:** `ruta_fisica()` exige ser
  miembro en toda ruta `/unidades/<id>/…` y rol de escritura en las operaciones que escriben; falla
  cerrado si la base de datos no responde. Compartir por enlace exige rol de escritura. Sin permiso
  responde 403 en todos los endpoints. Aplicado también al espejo `drive-maquita/`.
- **[C-6] Cuentas externas del Drive podían tomar el buzón interno:** la sesión externa lleva
  `aud`/ámbito propios que el backend del correo rechaza; `change-password` verifica siempre contra
  IMAP; `crear_e_invitar` rechaza buzones y dominios internos.
- **[C-9] Chat: borrado global de cualquier conversación:** `clear` exige ser participante activo.
- **[C-4] y [C-5] Ejecución de comandos como root desde el panel admin:** análisis de adjuntos y
  autorespondedor sin `bash -c` ni heredoc; argumentos como lista, nombres y buzones validados, script
  Sieve escapado.
- **[C-3] Integraciones de IA y transcripción publicadas sin sesión:** plantilla nginx con
  `auth_request` al backend (`deploy/hardening/nginx/integraciones-sesion.conf`); claves fuera del
  archivo de configuración.
- **[A-16] fail2ban y logrotate del webmail** alineados con el log de seguridad real
  (`deploy/hardening/fail2ban/*`, `deploy/hardening/logrotate/webmail`).
- **[B1] Secretos obligatorios validados al arranque** en backend, panel, chat y almacén (aborta
  nombrando la variable, sin imprimir valores).
- **[B2] Milter sin errores silenciosos** y cola de evidencia diferida con reconciliación por cron.

En el servidor, además (sin código): rotación de `SECRET_KEY`, `ADMIN_JWT_SECRET` y `CHAT_JWT_SECRET`
con invalidación de sesiones; `/dav/` restringido a LAN/VPN (temporal); log de cookies de nginx
eliminado; permisos de logs 640. Detalle en `REMEDIACION-2026-09.md` (servidor).

## [1.5.0] - 2026-09-03

### Añadido

- **UI de S/MIME (Ajustes del webmail):** nueva sección «Certificados S/MIME» donde cada usuario
  sube su `.p12/.pfx` (firmar/descifrar) o el `.pem/.crt` público de un contacto (cifrarle),
  lista y elimina sus certificados. El backend `/api/smime/*` ya existía; solo faltaba pantalla.
- **UI de AIR — respuesta a incidentes (admin):** nueva página «Incidentes (AIR)» que investiga
  señales de riesgo por ventana de tiempo, muestra los incidentes (severidad, motivos, resumen de
  IA) y permite **contener** (bloquear) una cuenta comprometida. Backend `/api/air/*` ya existía.

## [1.4.0] - 2026-09-03

### Corregido

- **BLOQUEANTE de instalación limpia — claves VAPID (#18):** `py-vapid` 1.9.1 pasa la **clase**
  de la curva a `ec.generate_private_key`, y `cryptography` >=42 exige la **instancia** →
  `TypeError` en `generate_keys()`; con `set -e`, el instalador **abortaba** dejando la
  instalación a medias. Ahora las claves se generan con `cryptography` directo
  (`ec.SECP256R1()` + X962/PKCS8), sin depender de `py_vapid` (la firma de envíos sí lo usa,
  vía `from_file`). `validar-despliegue.sh` ahora verifica que `/api/push/vapid-public-key`
  devuelva `enabled:true` con clave no vacía, para que un fallo del paso VAPID no pase en silencio.

### Añadido

- **Aviso de «remitente externo»:** banner discreto (informativo, **no de alarma**) en el correo
  abierto cuando el remitente es de fuera de la organización. Si es una contraparte frecuente, el
  usuario lo **marca como conocido**: se agrega a sus contactos (`user_contacts`) y el aviso deja
  de salir para esa dirección. Backend: `GET /api/mail/remitente-estado`,
  `POST /api/mail/remitente-conocido`.

## [1.3.0] - 2026-09-03

### Corregido

- **Botón «Descargar APK» falso (#16):** ofrecía `/webmail/downloads/MaquitaMail.apk`, que no
  existe en el repo, y `try_files` servía el `index.html` renombrado (el usuario instalaba "algo"
  que no es nada). Se retira el botón (queda «Instalar aplicación» = PWA real).

### Añadido

- **Notificaciones Web Push del correo (#17):** avisos nativos del navegador al llegar
  correo, incluso con la PWA/pestaña cerrada. Módulo backend `app/push` (VAPID, `/api/push`),
  disparo desde el vigilante IMAP IDLE, Service Worker (`push`/`notificationclick`) y suscripción
  del frontend al iniciar sesión. El instalador genera claves VAPID únicas por instalación; la
  clave privada VAPID queda fuera del repo.
- **Certificado con dominio pelado + autoconfig (#15):** `deploy/webmail/tls/emitir-certificado.sh`
  emite el cert con el apex y los subdominios de cliente que realmente apuntan al servidor
  (resolver público por el split-horizon), fija el linaje con `--cert-name` y publica el XML de
  autoconfiguración (Thunderbird/Evolution); evita el «certificado equivocado» cuando el cliente
  autoconfigura probando el dominio pelado. Plantillas de autoconfig + guía
  `docs/CERTIFICADO-Y-AUTOCONFIG.md`. El instalador recomienda el helper en vez del certbot que
  solo cubría `mail.`.
- **Chequeo TLS/SNI del correo en `validar-despliegue.sh` (#14, #15):** por cada nombre
  (dominio pelado + mail./imap./smtp.) prueba `openssl s_client -servername -verify_hostname` en
  465 y avisa si el cert no valida (config automática móvil); y busca en `mail.log` los errores
  fantasma de un mapa SNI mal construido (`malformed BASE64`/`lookup problem`) recordando que
  `vmail_sni` se reconstruye con `postmap -F` + **restart** postfix (reload NO basta).

- **QA «perilla -> UI» del Drive:** `almacen/deploy/verificar_perillas.py` valida que las
  funciones de configuracion (p. ej. `drive_name`) REALMENTE lean `config_kv` y no devuelvan
  siempre el default por un fallo silencioso (caza el #13). Setea un valor de prueba, comprueba
  que la funcion lo refleja y restaura. El instalador lo ejecuta en el paso del Almacen.
- **QA de assets del Drive:** `almacen/deploy/verificar_assets.py` comprueba que los assets
  estáticos referenciados por las plantillas/CSS del Drive existan de verdad (caza la familia
  #1/#6/#10). El instalador lo ejecuta en el paso del Almacén y **aborta** si falta alguno.

## [1.2.2] - 2026-09-02

### Corregido

- **Drive (#13):** la perilla del nombre del Drive no funcionaba. drive_name() usaba consultar()
  sin importarlo, el NameError lo tragaba un except silencioso y siempre devolvia el default.
  Se agrega el import y el except ahora LOGUEA la excepcion (no mas fallos escondidos).
  Verificado con la perilla seteada.

## [1.2.1] - 2026-09-02

### Cambiado

- **Branding del Drive para adoptantes (#3, #12):** la UI del Drive ya no fija «Maquita». El
  nombre visible sale de `config_kv.drive_name` (una sola perilla; default «Nube Maquita») en
  título, bienvenida, menú, avisos y hints; el **favicon y color** del Drive se toman de
  `/api/branding` (misma fuente del panel de Personalización). Nueva guía `docs/PON-TU-MARCA.md`
  (qué cubre el panel hoy y los ajustes manuales con comandos: nombre del Drive, color primario
  por SQL, íconos PWA desde el logo). Pendientes «ideales» documentados (campo de color en el
  panel; generación server-side de íconos PWA).

## [1.2.0] - 2026-09-02

### Añadido

- **Cuentas Drive externas (colaboradores/aliados):** acceso al Drive para personas con un
  correo que NO es buzón del servidor (pasantes, aliados), **sin tocar** el flujo de empleados
  (nómina). Incluye: directorio híbrido (nómina + tabla `usuarios_externos`, ids en rango
  reservado para no colisionar), **login propio** (`/acceso-externo`) que emite el mismo JWT que
  el webmail y lleva al Drive, **invitación por correo** con enlace de un solo uso + activación
  con política de contraseña, **panel de administración** (crear/listar/activar/desactivar/
  reinvitar/cuota/eliminar, solo master), **cuota real** por la tabla `cuotas`, y acceso a las
  **Aplicaciones** (BI/PDF). Preparado para **Keycloak** (columna `proveedor`, `emitir_sesion`
  reutilizable por un callback OIDC). Enlace «¿Colaborador externo?» en el login del correo.

## [1.1.7] - 2026-09-02

### Corregido

- **Drive (#11):** el botón «Instalar app de escritorio» abría `nextcloud.com/install` — enlace a
  un producto ajeno y callejón sin salida (el Almacén no habla WebDAV). Ahora muestra
  «Próximamente: la aplicación de escritorio del Drive está en preparación». Cuando se publique el
  cliente propio, irá con la URL del servidor parametrizable (mismo espíritu que `drive_url`).

## [1.1.6] - 2026-09-02

### Corregido

- **Drive — menú de usuario abierto/sin estilo (#10):** el explorador extiende un `base.html`
  mínimo que no cargaba Bootstrap, así que el dropdown del usuario (arriba a la derecha) nacía
  expandido y en crudo en toda réplica. Se empaqueta **Bootstrap 5.3.2 local** y `base.html`
  carga su CSS (antes de `extra_css`) y `bootstrap.bundle.min.js`. Los 4 iconos Font Awesome del
  menú se migran a **material-icons** (ya empaquetado).

## [1.1.5] - 2026-09-02

### Corregido

- **OnlyOffice (#9):** si el Document Server se proxeaba bajo un prefijo `/onlyoffice/`, tapaba
  el diagnóstico `/onlyoffice/estado` del Drive (la UI no sabía si la ofimática estaba
  configurada). Salvaguarda `location = /onlyoffice/estado` (match exacto → Almacén) en ambos
  snippets nginx + la guía recomienda `/office/` para el DS. El endpoint ya usaba el prefijo a
  prueba de futuro `/api/almacen/onlyoffice/estado`.

## [1.1.4] - 2026-09-02

### Cambiado

- **OnlyOffice (ofimática):** el README lo prometía dentro del instalador de un solo script,
  pero `instalar.sh` no montaba el Document Server ni avisaba (el adoptante abría un `.docx` y
  no pasaba nada). Ahora: README honesto (la ofimática se monta aparte), guía dedicada
  **`docs/ONLYOFFICE-DOCUMENT-SERVER.md`** (docker + JWT + rutas nginx + healthcheck),
  **`instalar-app.sh onlyoffice`** (levanta el DS y cablea la config con el patrón de BI/PDF), y
  el Drive avisa **«Ofimática no configurada»** (consulta `/onlyoffice/estado`) en vez de fallar
  en silencio.

## [1.1.3] - 2026-09-02

### Corregido

- **Cookies multi-dominio (SSO):** un `domain=cookie_domain` fijo rompía instancias que sirven
  varios dominios padre — el navegador rechazaba la cookie cuando el `Domain` no correspondía al
  host, dejando sin acceso a los usuarios del otro dominio. Ahora el `Domain` se deriva del host
  de la petición contra `COOKIE_PARENT_DOMAINS` (nuevo `app/auth/cookies.py`), en los 12
  `set_cookie`/`delete_cookie` de auth y OIDC. Sin la variable → host-only (retro-compatible).
  Habilita SSO webmail↔drive por subdominios en cada dominio, sin que uno pise al otro.

## [1.1.2] - 2026-09-02

Segundo lote de portabilidad reportado por el equipo externo (Drive frente a usuarios reales).

### Corregido

- **Drive — dominio propio quemado (crítico):** el botón «Archivos» abría un dominio fijo, así
  que en una réplica los usuarios aterrizaban en el login de otra organización. Ahora la URL
  del Drive sale de `branding_settings.drive_url` con **default mismo host** (`/archivos-almacen/`).
- **Drive — nginx del Almacén incompleto (grave):** no proxeaba `/almacen-static/` (CSS), `/drive`
  ni `/webmail-inicio` → Drive deforme/404 en réplicas. Se completa el snippet y se agrega la
  plantilla `nginx-almacen-dominio-dedicado.conf` (patrón recomendado: dominio dedicado).
- **Compartir:** clasificaba interno/externo con `dominio.includes('maquita')` → en réplicas todos
  salían «Externos». Ahora usa el dominio real (`USUARIO_DOMINIO` / `DOMINIOS_INTERNOS`).
- **`cookie_domain`:** estaba sobrecargado (cookie y construcción de URLs). Las URLs públicas usan
  ahora `public_base_url`; `cookie_domain` queda solo para la cookie, habilitando SSO entre
  subdominios (p. ej. `.suorg.tld`).
- **Explorador del Drive:** cargaba Google Fonts y sweetalert2 desde CDN; ahora van empaquetados
  en local (`/almacen-static/vendor`), acorde a la filosofía offline.

## [1.1.1] - 2026-09-02

Correcciones de portabilidad reportadas por un equipo externo que corre una réplica del repo.

### Corregido

- **Editor de PDF autónomo**: daba `500 TemplateNotFound: base.html` en instalación limpia.
  Se publica la interfaz completa (`interfaces/web/static/` con los estáticos del editor +
  Bootstrap) y un `base.html` autónomo; el instalador valida el render (no solo el arranque).
- El instalador ahora copia `maquita-mailadm` a `/usr/local/sbin` (el README lo documentaba).
- Aviso temprano si la CPU no expone x86-64-v2 (`sse4_2`): NumPy 2.x (Tableros/BI) no arranca
  en Proxmox con CPU `kvm64`; se indica `qm set <vmid> --cpu host`.
- Editor de PDF: puerto documentado 8790 → 8792 (coincide con el servicio y nginx);
  `AUTH_DATABASE_URI` marcado como OPCIONAL.
- Service worker: el `sed` de despliegue actualiza la versión de caché de cualquier marca,
  para que una réplica no pierda la autoactualización de la PWA.

### Cambiado

- Las pantallas de seguridad (2FA, verificación de enlace, simulacro de phishing, retención
  legal) y el prompt de IA usan el nombre de la organización desde el branding
  (`branding_settings.org_name`, `ORG_NAME`, `AI_ORG_CONTEXT`) con fallback neutro, para que
  una réplica no muestre la marca de otra organización.

### Añadido

- `instalar-app.sh <bi|pdf>`: agrega una Aplicación del Drive a un despliegue ya montado
  (idempotente; reutiliza los pasos 16-17 y la configuración existente).

## [1.1.0] - 2026-09-02

Tag: `v1.1.0`. Incorpora el **Drive Maquita (Almacén)** y sus **Aplicaciones**, el
instalador ampliado que las despliega, y correcciones de seguridad del webmail.

### Añadido

- **Almacén (Drive Maquita)**: gestor de archivos propio estilo Drive, integrado al
  webmail (unidades, compartir por enlace/carpeta, papelera, versiones, búsqueda,
  auditoría, OnlyOffice y formularios `.forma`). Sustituye a Nextcloud.
- **Aplicaciones del Drive Maquita**:
  - **Tableros/BI**: lee `.xlsx`/`.csv` del Drive y genera KPIs y gráficos (Chart.js).
  - **Editor de PDF**: app instalable (editar, OCR, firmar) integrada con el token del Drive.
- **Instalador completo ampliado** (`deploy/webmail/instalar.sh`): despliega también el
  Almacén y las Aplicaciones (pasos 15–17); validado en Debian 13 limpio.
- **`actualizar-apps.sh`**: actualiza las Aplicaciones del Drive (git pull + dependencias + reinicio).
- **Adjuntos grandes al Almacén**: los adjuntos superiores a 25 MB se suben al Drive propio
  y generan un enlace público, en lugar de un servicio externo.
- **Documentación de la suite** (`docs/SUITE-MAQUITA.md`) y sección «Cómo se compara» en el README.

### Cambiado

- README con métricas reales del proyecto y alcance público acotado (correo + Drive Maquita
  + Aplicaciones; el ERP/Raíces no forma parte del repositorio).
- Snippets de nginx de las Aplicaciones movidos al subdirectorio `maquita-apps/`.

### Corregido

- **Cambio de contraseña**: la política del frontend se alinea con la del backend
  (≥10 caracteres + carácter especial) y los mensajes de error son específicos
  (se evita un 422 genérico del esquema).
- Portabilidad del Editor de PDF (rutas por variables de entorno, creación de tablas al arranque).
- Instalador: arranque de PostgreSQL, Postfix y nginx en entornos sin auto-arranque de servicios.

### Seguridad

- Los adjuntos grandes dejan de depender de un servicio de archivos externo (soberanía de datos).

## [1.0.1] - 2026-05-13

Tag: `v1.0.1-compliance-audit`

### Añadido

- **Módulo de compliance** con flujo completo de eDiscovery (búsqueda, preservación, recolección, exportación)
- **Retenciones legales** con preservación inmutable de mensajes y gestión de custodios
- **Trazabilidad de auditoría** que registra todas las acciones de usuarios y administradores con actor, marca de tiempo, IP y contexto
- **Motor de detección de fraude** con puntuación basada en reglas y umbrales configurables
- **Firma GPG** para exportaciones de eDiscovery y paquetes de evidencia de compliance
- **Aplicación granular de RBAC** para operaciones de compliance (viewer, analyst, officer, admin)
- **Correlación de trazas de correo** que vincula mensajes a través de los logs de Postfix, Dovecot y Rspamd por message-id

### Cambiado

- Actualizada la integración con Dovecot para compatibilidad con la versión 2.4 (cambios en protocolo doveadm, rutas de socket)
- RBAC refactorizado a verificaciones de permisos granulares por endpoint
- Mensajes de error mejorados para los endpoints de la API de compliance

### Corregido

- El análisis de fechas en la búsqueda de correos ahora maneja correctamente RFC 2822, ISO 8601 y marcas de tiempo en formato epoch
- Análisis de tamaño para cuota de buzón y filtros de búsqueda (unidades KB/MB/GB)
- Errores de permisos de doveadm al ejecutar como usuario de servicio sin root
- Condición de carrera en la activación concurrente de retenciones legales para el mismo custodio

### Seguridad

- Validación de fallo rápido para `ADMIN_JWT_SECRET` al inicio (rechaza el arranque con valores débiles o predeterminados)
- Valores de secretos sanitizados en respuestas de error y en la salida de logs
- Añadido `hardening.conf` como drop-in de systemd con `NoNewPrivileges`, `ProtectSystem=strict`, `MemoryDenyWriteExecute`
- Permisos del socket doveadm restringidos únicamente al usuario de servicio de la aplicación

## [1.0.0] - 2026-04-12

### Añadido

- Interfaz de webmail completa: bandeja de entrada, redacción, respuesta, reenvío, borradores
- Vista de conversaciones encadenadas con agrupación de mensajes
- Gestión de etiquetas y carpetas con arrastrar y soltar
- Búsqueda de correo de texto completo con filtros (fecha, remitente, has:attachment)
- Módulo de calendario con soporte CalDAV mediante Radicale 3.0
- Gestión de contactos con importación/exportación de vCard
- Módulo de tareas con fechas de vencimiento y niveles de prioridad
- Panel de administración para gestión de usuarios, dominios y alias
- Integración antispam con Rspamd (visualización de puntuación de spam, aprendizaje ham/spam)
- Análisis antivirus con ClamAV en correo entrante y saliente
- Autenticación de dos factores (TOTP) con inscripción mediante código QR
- Plugin `mail_crypt` de Dovecot para cifrado en reposo
- Configuración de proxy inverso Nginx con cabeceras de seguridad
- Pipeline de CI/CD: linting, pruebas, compilación, despliegue
- Entorno de desarrollo con Docker Compose
- Sistema de migraciones de base de datos (`migrations/*.sql`)
- Documentación de API mediante OpenAPI/Swagger

## [0.9.0] - 2026-03-23

### Añadido

- Versión inicial de Maquita Webmail
- Herramientas de migración de buzones de Zimbra a Dovecot
- Interfaz de webmail básica (leer, redactar, eliminar)
- Integración IMAP con Dovecot
- Envío SMTP mediante Postfix
- Gestión de usuarios y dominios respaldada por PostgreSQL
- Autenticación basada en sesiones
- Interfaz de administración básica

[Sin publicar]: https://github.com/wilsongabriel30/webmailMaquita/compare/v1.0.1-compliance-audit...HEAD
[1.0.1]: https://github.com/wilsongabriel30/webmailMaquita/compare/v1.0.0...v1.0.1-compliance-audit
[1.0.0]: https://github.com/wilsongabriel30/webmailMaquita/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/wilsongabriel30/webmailMaquita/releases/tag/v0.9.0
