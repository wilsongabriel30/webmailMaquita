# Registro de cambios

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
y este proyecto sigue el [Versionado Semántico](https://semver.org/spec/v2.0.0.html).

## [Sin publicar]

Pendiente: #3 del reporte externo — parametrizar la marca de la UI del Drive (~40 strings)
con `branding_settings` (queda como tarea aparte por su tamaño).

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
