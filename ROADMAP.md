# Hoja de ruta

Este documento describe la hoja de ruta de desarrollo de Maquita Webmail. Las etiquetas de estado indican el avance:

- **DONE** -- Completado y publicado
- **IN PROGRESS** -- En desarrollo activo
- **PLANNED** -- Aprobado y programado para desarrollo
- **PROPOSED** -- En consideración, aún sin compromiso

---

## v1.0.x -- Cumplimiento normativo y núcleo eDiscovery `DONE`

La versión base con capacidades completas de cumplimiento normativo.

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

## v1.1 -- Indexación de texto completo escalable `PLANNED`

Búsqueda de alto rendimiento en buzones grandes y datos de cumplimiento.

- Integrar Apache Solr o Manticore Search para indexación de texto completo
- Indexar cuerpos de correo, encabezados y texto de adjuntos
- Soporte para sintaxis de consulta compleja (operadores booleanos, rangos de fechas, búsqueda por campo)
- Actualizaciones de índice en tiempo real vía gancho LMTP
- Resaltado de resultados de búsqueda y puntuación de relevancia
- Búsqueda con conciencia de cumplimiento: respeta retenciones legales y políticas de retención

## v1.2 -- Extracción avanzada de adjuntos `PLANNED`

Extracción profunda de contenido de formatos de documento habituales.

- Extracción de texto en PDF (con OCR de respaldo vía Tesseract)
- Análisis de contenido DOCX/XLSX/PPTX
- Inspección de archivos comprimidos (ZIP, TAR, 7z) con extracción anidada
- Extracción de metadatos de imagen (EXIF)
- Indexación de contenido para integración con búsqueda de texto completo
- Análisis de malware en el contenido extraído
- Validación de tipo de archivo más allá del sniffing de MIME

## v1.3 -- Integración con Wazuh y OpenSearch `PROPOSED`

Monitoreo de seguridad y análisis centralizado de registros.

- Despliegue y configuración del agente Wazuh
- OpenSearch como backend de registros para eventos de correo, autenticación y cumplimiento
- Reglas de alerta predefinidas para actividad sospechosa de correo
- Integración con la auditoría de cumplimiento
- Paneles de control para visión general del estado de seguridad
- Monitoreo de integridad de archivos para almacenamiento de correo y configuración

## v1.4 -- Paneles SIEM `PROPOSED`

Paneles de control operativos y de seguridad para administradores.

- Paneles Grafana para métricas de flujo de correo
- Visualización de eventos de autenticación (éxito, fallo, geográfico)
- Panel de actividad del módulo de cumplimiento
- Gestión de alertas y flujos de escalamiento
- Detección de anomalías en patrones de acceso a buzones
- Generación de informes (PDF/CSV) para auditorías de cumplimiento

## v1.5 -- Multi-tenant y multi-dominio `PROPOSED`

Soporte para alojar múltiples organizaciones en una sola instancia.

- Aislamiento a nivel de dominio para buzones, configuraciones y datos de cumplimiento
- Roles de administrador por tenant y políticas RBAC
- Marca y configuración específicas por tenant
- Cuotas de recursos por tenant (almacenamiento, usuarios, límites de tasa)
- Infraestructura compartida con garantías de aislamiento de datos
- API de aprovisionamiento de tenants e interfaz de administración
- Operaciones de cumplimiento entre tenants (para organizaciones matrices)

## v2.0 -- Arquitectura de producción estable `PROPOSED`

La primera versión de soporte a largo plazo con madurez arquitectónica.

- Escalado horizontal: backend sin estado detrás de balanceador de carga
- Réplicas de lectura de base de datos y agrupación de conexiones (PgBouncer)
- Redis Sentinel o Cluster para caché de alta disponibilidad
- Procesamiento asíncrono basado en colas (Celery o equivalente)
- Estrategia de despliegue sin tiempo de inactividad (blue-green o rolling)
- Versionado completo de API (v1 estable, v2 en vista previa)
- Benchmarks de rendimiento y objetivos de SLA
- Compromiso de soporte a largo plazo (parches de seguridad por 2+ años)
- Especificación OpenAPI completa con generación de SDK
- Sistema de complementos/extensiones para reglas de cumplimiento personalizadas

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
| 7 | Git | Parcial: aplicaciones propias desde git | v1.11: también en sitios PHP |
| 8 | Dominios | Ya (asistente «Nuevo dominio») | — |
| 9 | Subdominios | Ya — panel y portal | — |
| 10 | Alias de dominios | Ya en el panel general | v1.11: desde el portal |
| 11 | Redireccionamientos | Ya: 301/302 por dirección y de dominio completo — panel y portal | — |
| 12 | Editor de zona DNS | Ya — portal con NS, SOA y correo en solo lectura | — |
| 13 | DNS dinámico | No | v1.11 |
| 14-17 | Cuentas, webmail, reenvíos, respuestas automáticas | Ya | — |
| 18-19 | Filtros y antispam | Ya (Sieve y Rspamd con aprendizaje) | — |
| 20 | SPF, DKIM, DMARC | Ya, más MTA-STS | — |
| 21 | Listas de correo | Ya (grupos de distribución) | — |
| 22 | Importar cuentas desde archivo | No | v1.11 (CSV, desde el portal) |
| 23 | Enrutamiento de correo | No | v1.11 (MX de respaldo y reenvío a otro servidor) |
| 24-26, 28 | MariaDB, PostgreSQL, phpMyAdmin/Adminer, asistente | Ya — panel y portal | — |
| 27 | Usuarios de base con permisos | Parcial: un usuario por base | v1.11 |
| 29 | Acceso remoto a bases | No | v1.11 (por IP y con TLS) |
| 30-31 | Certificados y renovación automática | Ya (Let's Encrypt) — panel y portal | — |
| 32 | Bloqueo de IP | Ya: servidor (cortafuegos, fail2ban, países) y por sitio | — |
| 33 | Cortafuegos de aplicaciones web | Parcial: reglas para WordPress y fail2ban | v1.11 (Coraza/ModSecurity con reglas OWASP) |
| 34 | Protección contra hotlinking | Ya — panel y portal | — |
| 35-36 | Abuso de contraseñas y segundo factor | Ya | — |
| 37 | Claves SSH | No | v1.11 (SFTP con clave) |
| 38 | Fichas de API | No | v1.11 |
| 39-40 | Versiones y ajustes de PHP | Ya — portal con las versiones ya instaladas | — |
| 41 | Catálogo de aplicaciones | Ya (WordPress, Joomla, Drupal y más) — panel y portal | — |
| 42 | Tareas cron | Ya — panel y portal | — |
| 43 | Páginas de error propias | Ya (403, 404, 500, 502, 503) — panel y portal | — |
| 44 | Manejadores de Apache | No aplica: nginx con PHP-FPM | — |
| 45 | Optimización (compresión, caché) | Ya: gzip/brotli de serie, caché del navegador y de página, pensado para conexiones rurales y satelitales | — |
| 46 | Node.js y Python | Ya en el panel general (aplicaciones propias) | v1.11: portal con límites |
| 47-49, 51 | WordPress: instalar, entrar, actualizar, varios sitios | Ya — panel y portal | — |
| 50 | Editor visual de páginas | No: Sitejet es de pago y cerrado, no entra | Fase posterior, solo si hace falta: primero la alternativa libre GrapesJS (BSD); si no alcanza, desarrollo propio y gratuito |
| 52 | Migración desde otro hosting | Ya (paquete y respaldo .sql) — panel y portal | — |
| 53-54 | Estadísticas de visitas y tráfico | Ya: GoAccess, sin rastreo en el navegador — panel y portal | — |
| 55-56 | CPU y memoria por sitio | No (cada sitio ya tiene su propio PHP) | v1.11 |
| 57 | Errores del sitio | Ya: visor de errores y accesos del sitio y de PHP — panel y portal | — |
| 58 | Monitoreo de disponibilidad | Ya: por sitio cada 5 minutos, con aviso al cliente | — |
| 59 | Información del servidor | Parcial: en el panel general | v1.11: en el portal |

**v1.9.0 — El cliente administra su sitio** `DONE` (2026-10-21): pestaña «Mi sitio web» del portal de dominio
(sitios y subdominios, aplicaciones, HTTPS, FTP, cron, bases, PHP, archivos, migración, zona DNS, cuotas
por dominio, baja que confirma el administrador general).

**v1.10.0 — Hospedaje completo** `DONE` (2026-10-21): administrador de archivos, redirecciones, privacidad
de directorios, páginas de error, hotlinking, bloqueo de IP por sitio, cuentas FTP adicionales, copias que el
cliente descarga y restaura, estadísticas (GoAccess), visor de errores, disponibilidad por sitio y
optimización por sitio, en el panel general y en el portal. Además: ActiveSync 16.1 (borradores del teléfono
en el servidor) y libreta de la organización en los teléfonos.

**v1.11 — Para desarrolladores** `PLANNED`: git en sitios PHP, claves SSH, fichas de API, acceso remoto
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
