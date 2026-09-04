# Registro de cambios

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
y este proyecto sigue el [Versionado Semántico](https://semver.org/spec/v2.0.0.html).

## [Sin publicar]

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
