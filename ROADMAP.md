# Hoja de ruta

Maquita Webmail se usa en producción en la Fundación Maquita (Ecuador) desde **2024**: empezó como webmail
propio y fue creciendo con el panel, el Drive y el hospedaje. El historial de cambios publicado arranca en
**marzo de 2026**. Este documento recoge lo hecho, en qué versión llegó, y lo que viene.

Estados: **DONE** (publicado) · **IN PROGRESS** (en desarrollo) · **PLANNED** (programado) · **PROPOSED** (en consideración).

---

## Historia del proyecto

| Fecha | Versión | Hito |
|---|---|---|
| 2024 | — | Webmail propio sobre Postfix y Dovecot en producción en la Fundación Maquita |
| 2026-03-23 | 0.9.0 | Primera versión pública del código |
| 2026-04-12 | 1.0.0 | Cumplimiento normativo y eDiscovery: retención legal, auditoría, exportaciones firmadas |
| 2026-05-13 | — | Preparación como proyecto abierto: licencia, guías de contribución y seguridad, hoja de ruta |
| 2026-09-02 | 1.1.0 | Drive (Almacén) y sus aplicaciones |
| 2026-09-03 a 09-06 | 1.3.0 a 1.7.0 | Correcciones de auditorías de seguridad externas (ASVS) |
| 2026-09-06 | — | Repositorio público en GitHub, con todo el historial de cambios desde marzo de 2026 |
| 2026-10-20 | 1.8.0 | Panel de hospedaje: sitios web, DNS propio, cortafuegos, actualizaciones firmadas, respaldos |
| 2026-10-21 | 1.9.0 | Portal del cliente: cada organización administra sus sitios |
| 2026-10-21 | 1.10.0 | Hospedaje completo (alternativa libre a cPanel), ActiveSync 16.1 |
| 2026-10-21 | 1.11.0 | Para desarrolladores y organizaciones grandes: búsqueda en adjuntos, tableros de seguridad y Wazuh, gran escala, OIDC, git, API y DNS dinámico |
| 2026-10-22 | 1.11.1 | Correcciones pedidas por Andes: Editor de PDF y Tableros sin 401, nombres de marca, «Nuevo → Documento», nginx por defecto |
| 2026-10-22 | 1.11.2 | Hospedaje para otras organizaciones: proxy de confianza, certificado por dominio, repositorios privados, entrada por dominio, informe del actualizador |
| 2026-10-22 | 1.11.3 | `maquita-sudo` en módulos (sin cambios de comportamiento) |
| 2026-10-22 | 1.11.4 | Drive: «Mover a…» dentro de las unidades, aviso de unidad compartida y vista dividida |
| 2026-10-23 | 1.11.5 | Drive: «Eliminar definitivamente» en la papelera (ruta que faltaba en el Almacén) |
| 2026-10-26 | 1.11.6 | Favicon con el logo de la organización en el panel, el webmail y el Drive (adiós al rayo de Vite) |
| 2026-10-29 | 1.11.7 | Grupo «Párrafo» e importancia en el redactor, aviso de invitaciones no entregadas, contadores y Cuadrícula en Tareas, sitios en .rar y .7z |
| 2026-10-30 | 1.11.8 | Tareas al estilo Microsoft To Do: listas propias y compartidas, grupos, detalle con pasos, repetición y adjuntos, asignar con plazo e indicaciones, recordatorios, Sugerencias y configuración |

El detalle de cada versión está en [CHANGELOG.md](CHANGELOG.md) y en
[Releases](https://github.com/wilsongabriel30/webmailMaquita/releases).

---

## Líneas de trabajo planteadas en mayo de 2026

Al abrir el proyecto (2026-05-13) se trazaron estas líneas. Se numeraron como v1.1 a v2.0, pero las versiones
siguieron otro orden; por eso hoy se nombran por tema y cada una indica su estado real.

### Cumplimiento normativo y núcleo eDiscovery `DONE` (v1.0.0, 2026-04-12)

- Webmail completo: bandeja de entrada, redacción, hilos, etiquetas, búsqueda
- Calendario (CalDAV vía Radicale), contactos, tareas
- Panel de administración con RBAC
- Antispam (Rspamd), antivirus (ClamAV)
- Autenticación de dos factores (TOTP)
- Cifrado en reposo con Dovecot mail_crypt
- **Módulo eDiscovery**: búsqueda, preservación, recopilación, exportación
- **Retenciones legales**: preservación inmutable con auditoría
- **Auditoría de cumplimiento**: todas las acciones registradas con actor, marca de tiempo y contexto
- **Detección de fraude**: análisis de correo basado en reglas con puntuación
- **Firma GPG**: integridad criptográfica para exportaciones y evidencia
- **Aplicación de RBAC**: acceso granular basado en roles para operaciones de cumplimiento
- **Correlación de trazas de correo**: seguimiento de mensajes de extremo a extremo en MTA/MDA/MUA
- Pipeline CI/CD con gitleaks y generación de SBOM

### Varias organizaciones y dominios `DONE` en gran parte (v1.8.0 a v1.10.0)

Pensada como «multi-tenant». Ya hecho: varios dominios por servidor, administradores por dominio con su
propio portal, cuotas por dominio (sitios, disco, bases), marca propia por organización y aislamiento de
cada sitio. Pendiente: API de aprovisionamiento.

### Indexación de texto completo escalable `DONE` (v1.11.0, 2026-10-21)

Búsqueda de alto rendimiento en buzones grandes y datos de cumplimiento. Se hizo con el índice nativo de
Dovecot 2.4 (**fts-flatcurve**, Xapian) en lugar de Solr o Manticore: medido en un buzón de 120.871 correos,
0,05–0,3 s por carpeta, sin otro servicio que mantener. Detalle en
[docs/BUSQUEDA-TEXTO-COMPLETO.md](docs/BUSQUEDA-TEXTO-COMPLETO.md).

- Índice de cuerpos, encabezados y texto de adjuntos; español e inglés, sin distinguir tildes ni mayúsculas
- Actualización en tiempo real al entregar el correo (`fts_autoindex` en LMTP); papelera y no deseado fuera
- Indexación inicial en segundo plano con prioridad mínima y pasada nocturna de lo que falte
- Webmail (operadores `de:`, `asunto:`, `entre:`…) y eDiscovery sobre el mismo índice
- Respeta las retenciones legales: el índice no modifica ni borra mensajes
- Panel: estado del índice y «Reindexar buzón»
- Pendiente: resaltado de resultados y orden por relevancia

### Extracción avanzada de adjuntos `DONE` (v1.11.0, 2026-10-21)

Decodificador propio para el índice (`deploy/dovecot/fts/`), sin privilegios y con límites de tamaño,
tiempo y memoria.

- Texto de PDF (OCR opcional con Tesseract para los escaneados)
- DOCX/XLSX/PPTX (también con macros, sin ejecutarlas), ODT/ODS/ODP, Office 97-2003, RTF y HTML
- Comprimidos ZIP, TAR, gzip, bzip2, xz y 7z con extracción anidada y defensa contra bombas de descompresión
- Metadatos de imagen (EXIF)
- Validación del tipo por el contenido, no solo por el MIME declarado
- Pendiente: análisis de malware del contenido extraído (hoy ClamAV analiza el adjunto al llegar)

### Monitoreo de seguridad: Wazuh y OpenSearch `DONE` (v1.11.0, 2026-10-21)

Opcional y con el manager **fuera** del servidor de correo (`docs/WAZUH.md`): `instalar-app.sh wazuh` instala
el agente oficial con versión fija y lo registra contra el manager que indique el administrador; el manager
todo en uno (con el indexador OpenSearch y su tablero) se monta en otra máquina.

- Despliegue y configuración del agente Wazuh (`deploy/wazuh/instalar.sh`, idempotente, clave del repositorio verificada)
- OpenSearch como backend de registros: el indexador de Wazuh en el manager externo; el servidor envía un registro JSON propio (alertas, auditoría del panel y cumplimiento), Postfix, Dovecot, nginx y autenticación
- Reglas de alerta predefinidas (`deploy/wazuh/manager/`, 100800-100899): `maquita-sudo`, inicios de sesión del panel, anomalías, cumplimiento y vigilantes
- Integración con la auditoría de cumplimiento: eDiscovery, custodios, retenciones y lectura de buzones llegan como eventos propios
- Paneles: los del propio panel (Seguridad → Tableros) y, si se quiere un SIEM central, los de Wazuh
- Integridad de archivos de la configuración (Postfix, Dovecot, nginx, Rspamd, `/etc/maquita-mail`, sudoers), los ayudantes y el código. El buzón (`/var/vmail`) no: cambia con cada mensaje; lo cubren los respaldos y la retención legal

### Paneles de seguridad (SIEM) `DONE` (v1.11.0, 2026-10-21)

En el **propio panel general** (Seguridad → Tableros), sin Grafana: un recolector cada 5 minutos agrega los
registros de Postfix, Dovecot y ActiveSync, la auditoría y Rspamd en tablas propias de PostgreSQL
(retención configurable, 400 días por omisión) y las pantallas solo leen esos totales.

- Flujo de correo: entregados, enviados, rechazados, spam y cola por hora o por día
- Eventos de autenticación: correctos y fallidos por servicio y por país (GeoIP local), IP y cuentas más atacadas
- Actividad del módulo de cumplimiento (eDiscovery, retenciones legales, políticas, auditoría)
- Gestión de alertas y escalamiento: avisos por correo con los vigilantes, reconocer y cerrar, reaviso de las altas sin reconocer
- Anomalías en el acceso a buzones con reglas explicables: país nuevo, fallos seguidos de acceso, hora inusual, muchas cuentas desde una IP
- Informes CSV y PDF (HTML imprimible) para auditorías de cumplimiento

### Arquitectura para gran escala `DONE` en gran parte (v1.11.0, 2026-10-21)

Para organizaciones de 300 a 5000 buzones, sin cambiar la instalación de una sola máquina. Guía:
[docs/GRAN-ESCALA.md](docs/GRAN-ESCALA.md); soporte: [docs/SOPORTE-Y-VERSIONES.md](docs/SOPORTE-Y-VERSIONES.md).

- **Hecho.** Escalado horizontal: backend sin estado detrás de balanceador. Inventario del estado en memoria;
  las tareas de fondo ya no se repiten por worker (bloqueo distribuido en Redis, líder por máquina para
  el lector de `mail.log`); progreso del asistente en Redis
- **Hecho.** Agrupación de conexiones con PgBouncer (modo transaction, `PGBOUNCER=true`) y bloqueos de DDL
  compatibles. Réplica de lectura: el pool existe (`DATABASE_URL_LECTURA`); **pendiente** pasar
  consultas a ella
- **Hecho.** Redis Sentinel en el webmail (`redis+sentinel://` o `REDIS_SENTINELS`). Redis Cluster: no
  (no hace falta a esta escala). Panel, Drive y chat: a través de HAProxy
- **Hecho.** Despliegue sin corte (rolling): `deploy/escala/actualizar-sin-corte.sh` con `/api/salud` y
  `/api/listo` en webmail, panel y Drive
- **Hecho.** API v1 estable (`/api/v1/...`, alias de las rutas actuales). v2 en vista previa: **pendiente**
  (todavía no hay cambios que la necesiten)
- **Hecho.** Benchmark (`deploy/escala/prueba-carga-webmail.py`) y objetivos p50/p95 y de disponibilidad.
  **Pendiente** medirlos en un clúster real
- **Hecho.** Soporte largo: canal `estable-X.Y`, 24 meses de parches de seguridad por serie LTS, parches
  firmados desde ramas `estable/X.Y`
- **Hecho.** Especificación OpenAPI exportada (`scripts/exportar-openapi.py` → `docs/api/`), con copia `/api/v1`
  para generar clientes. **Pendiente** publicar SDK generados
- **Pendiente.** Procesamiento asíncrono basado en colas: **pendiente** (las tareas pesadas siguen en el proceso web)
- **Pendiente.** Archivos locales (firmas, adjuntos de calendario, marca) en almacenamiento de objetos: **pendiente**
  (hoy, almacenamiento compartido entre réplicas)
- **Pendiente.** Sistema de complementos/extensiones para reglas de cumplimiento personalizadas: **no empezado**

---

## Hospedaje completo: lo que ofrece un panel comercial y dónde estamos

Comparación con las 59 funciones de un panel de hospedaje comercial (tipo cPanel), hecha el
2026-10-21. «Ya» = publicado (panel general o webmail); «Portal» = el cliente lo hace solo desde el
portal de su dominio. Todo con software libre; donde el panel comercial usa un producto cerrado,
se indica la alternativa libre.

| # | Función | Estado (v1.10.0) | Pendiente |
|---|---|---|---|
| 1 | Administrador de archivos | Ya: web completo (subir, bajar, mover, copiar, comprimir, permisos, papelera) — panel y portal | — |
| 2 | Cuentas FTP | Ya: FTP seguro y SFTP, una por sitio y cuentas adicionales por subcarpeta — panel y portal | — |
| 3 | Uso de disco | Ya: sitio, bases y copias, con cuotas por dominio — panel y portal | — |
| 4 | Privacidad de directorios | Ya: usuario y contraseña por carpeta — panel y portal | — |
| 5-6 | Copias de seguridad y asistente | Ya: restic del servidor y copias del sitio que el cliente crea, descarga y restaura | — |
| 7 | Git | Ya: aplicaciones propias y sitios PHP (clave de despliegue, gancho, registro y vuelta atrás) — panel y portal | — |
| 8 | Dominios | Ya (asistente «Nuevo dominio») | — |
| 9 | Subdominios | Ya — panel y portal | — |
| 10 | Alias de dominios | Ya — panel y portal | — |
| 11 | Redireccionamientos | Ya: 301/302 por dirección y de dominio completo — panel y portal | — |
| 12 | Editor de zona DNS | Ya — portal con NS, SOA y correo en solo lectura | — |
| 13 | DNS dinámico | Ya: fichas por nombre y /nic/update (dyndns2) — portal | — |
| 14-17 | Cuentas, webmail, reenvíos, respuestas automáticas | Ya | — |
| 18-19 | Filtros y antispam | Ya (Sieve y Rspamd con aprendizaje) | — |
| 20 | SPF, DKIM, DMARC | Ya, más MTA-STS | — |
| 21 | Listas de correo | Ya (grupos de distribución) | — |
| 22 | Importar cuentas desde archivo | Ya (v1.11): CSV con vista previa — panel y portal | — |
| 23 | Enrutamiento de correo | Ya (v1.11): MX de respaldo y reenvío a otro servidor — panel general | — |
| 24-26, 28 | MariaDB, PostgreSQL, phpMyAdmin/Adminer, asistente | Ya — panel y portal | — |
| 27 | Usuarios de base con permisos | Ya: usuarios adicionales con perfiles o lista fina — panel y portal ([guía](docs/BASES-WAF-CLAVES.md)) | — |
| 29 | Acceso remoto a bases | Ya: por IP o red, solo TLS, puerto abierto solo para esas IP (ajuste 72) — panel y portal | — |
| 30-31 | Certificados y renovación automática | Ya (Let's Encrypt) — panel y portal | — |
| 32 | Bloqueo de IP | Ya: servidor (cortafuegos, fail2ban, países) y por sitio | — |
| 33 | Cortafuegos de aplicaciones web | Ya: ModSecurity con OWASP CRS completo por sitio (modo, paranoia, exclusiones, bloqueos) y fail2ban — panel y portal | — |
| 34 | Protección contra hotlinking | Ya — panel y portal | — |
| 35-36 | Abuso de contraseñas y segundo factor | Ya | — |
| 37 | Claves SSH | Ya: SFTP con clave ed25519, ECDSA o RSA ≥ 3072, por cuenta — panel y portal | — |
| 38 | Fichas de API | Ya: con alcance, caducidad, hash y auditoría — panel y portal | — |
| 39-40 | Versiones y ajustes de PHP | Ya — portal con las versiones ya instaladas | — |
| 41 | Catálogo de aplicaciones | Ya (WordPress, Joomla, Drupal y más) — panel y portal | — |
| 42 | Tareas cron | Ya — panel y portal | — |
| 43 | Páginas de error propias | Ya (403, 404, 500, 502, 503) — panel y portal | — |
| 44 | Manejadores de Apache | No aplica: nginx con PHP-FPM | — |
| 45 | Optimización (compresión, caché) | Ya: gzip/brotli de serie, caché del navegador y de página, pensado para conexiones rurales y satelitales | — |
| 46 | Node.js y Python | Ya: aplicaciones propias con límites de memoria y CPU — panel y portal | — |
| 47-49, 51 | WordPress: instalar, entrar, actualizar, varios sitios | Ya — panel y portal | — |
| 50 | Editor visual de páginas | No: Sitejet es de pago y cerrado, no entra | Fase posterior, solo si hace falta: primero la alternativa libre GrapesJS (BSD); si no alcanza, desarrollo propio y gratuito |
| 52 | Migración desde otro hosting | Ya (paquete y respaldo .sql) — panel y portal | — |
| 53-54 | Estadísticas de visitas y tráfico | Ya: GoAccess, sin rastreo en el navegador — panel y portal | — |
| 55-56 | CPU y memoria por sitio | Ya: pool de PHP-FPM y unidad de la aplicación, cada 5 minutos, gráfico de 24 h — panel y portal | — |
| 57 | Errores del sitio | Ya: visor de errores y accesos del sitio y de PHP — panel y portal | — |
| 58 | Monitoreo de disponibilidad | Ya: por sitio cada 5 minutos, con aviso al cliente | — |
| 59 | Información del servidor | Ya — panel y portal | — |

**v1.9.0 — El cliente administra su sitio** `DONE` (2026-10-21): pestaña «Mi sitio web» del portal de dominio
(sitios y subdominios, aplicaciones, HTTPS, FTP, cron, bases, PHP, archivos, migración, zona DNS, cuotas
por dominio, baja que confirma el administrador general).

**v1.10.0 — Hospedaje completo** `DONE` (2026-10-21): administrador de archivos, redirecciones, privacidad
de directorios, páginas de error, hotlinking, bloqueo de IP por sitio, cuentas FTP adicionales, copias que el
cliente descarga y restaura, estadísticas (GoAccess), visor de errores, disponibilidad por sitio y
optimización por sitio, en el panel general y en el portal. Además: ActiveSync 16.1 (borradores del teléfono
en el servidor) y libreta de la organización en los teléfonos.

**v1.11.0 — Para desarrolladores** `DONE` (2026-10-21): git en sitios PHP, claves SSH, fichas de API, acceso remoto
a bases, usuarios de base con permisos, CPU y memoria por sitio, cortafuegos de aplicaciones (OWASP),
DNS dinámico, enrutamiento de correo, Node.js y Python desde el portal. Pasan también de la v1.10:
importación de cuentas por CSV, alias de dominio e información del servidor en el portal.

**v1.12 — Asistente propio del cliente para su sitio** `PROPOSED`: desde el portal, «Asistente para mi
sitio» abre una terminal web donde el cliente usa su propio asistente de programación (con su propia cuenta:
el costo es suyo) para crear, editar y publicar su sitio.
- Corre como el usuario del sitio, sin root ni sudo, encerrado: solo ve la carpeta de su sitio; nada del
  sistema, del correo ni de otros sitios.
- Red de salida solo hacia el proveedor del asistente y los repositorios de paquetes; topes de CPU, memoria
  y tiempo.
- Lo que el sitio necesita del servidor (HTTPS, bases, PHP) lo pide con una ficha de API limitada a su
  dominio (v1.11), por el mismo intermediario y con el mismo alcance que el portal (v1.9).
- Copia del sitio antes de cada sesión para volver atrás (v1.10) y auditoría de todo lo que hace.

**Criterio**: lo que es de pago o cerrado no entra. Se usa una alternativa libre si hace lo mismo con la
misma calidad; si no existe o se queda corta, se desarrolla aquí y se entrega gratis.

---

## Contribuir a la hoja de ruta

Las sugerencias de la comunidad son bienvenidas. Para proponer una funcionalidad:

1. Abre un issue en GitHub con la etiqueta `roadmap`
2. Describe el caso de uso y el comportamiento esperado
3. Los mantenedores revisarán y asignarán un hito si la propuesta es aceptada

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para las pautas de contribución.
