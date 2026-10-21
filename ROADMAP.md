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

| # | Función | Hoy | Plan |
|---|---|---|---|
| 1 | Administrador de archivos | Parcial: ver y editar archivos de texto (Avanzado) y SFTP | v1.10: administrador web completo (subir, bajar, mover, comprimir) |
| 2 | Cuentas FTP | Ya: FTP seguro y SFTP, una cuenta por sitio | v1.9 Portal; v1.10 varias cuentas por sitio |
| 3 | Uso de disco | Ya en buzones | v1.9 Portal: sitio y bases, con cuotas por dominio |
| 4 | Privacidad de directorios | No | v1.10 (usuario y contraseña por carpeta) |
| 5-6 | Copias de seguridad y asistente | Ya (restic): el administrador general restaura sitios y buzones | v1.10 Portal: descargar y restaurar su sitio y sus bases |
| 7 | Git | Parcial: las aplicaciones propias se despliegan desde git | v1.11: despliegue desde git también en sitios PHP |
| 8 | Dominios | Ya (asistente «Nuevo dominio») | — |
| 9 | Subdominios | Ya | v1.9 Portal |
| 10 | Alias de dominios | Ya | v1.10 Portal |
| 11 | Redireccionamientos | No | v1.10 (301/302 por dirección y de dominio completo) |
| 12 | Editor de zona DNS | Ya | v1.9 Portal (NS, SOA y correo en solo lectura) |
| 13 | DNS dinámico | No | v1.11 |
| 14-17 | Cuentas, webmail, reenvíos, respuestas automáticas | Ya | — |
| 18-19 | Filtros y antispam | Ya (Sieve y Rspamd con aprendizaje) | — |
| 20 | SPF, DKIM, DMARC | Ya (zona y verificación en el portal) | — |
| 21 | Listas de correo | Ya (grupos de distribución) | — |
| 22 | Importar cuentas desde archivo | No | v1.10 Portal (CSV) |
| 23 | Enrutamiento de correo | No | v1.11 (MX de respaldo y reenvío a otro servidor) |
| 24-26, 28 | MariaDB, PostgreSQL, phpMyAdmin/Adminer, asistente | Ya | v1.9 Portal |
| 27 | Usuarios de base con permisos | Parcial: un usuario por base | v1.11 |
| 29 | Acceso remoto a bases | No | v1.11 (por IP y con TLS) |
| 30-31 | Certificados y renovación automática | Ya (Let's Encrypt) | v1.9 Portal |
| 32 | Bloqueo de IP | Ya en el servidor (cortafuegos, fail2ban, países) | v1.10 por sitio |
| 33 | Cortafuegos de aplicaciones web | Parcial: reglas para WordPress y fail2ban | v1.11 (Coraza/ModSecurity con reglas OWASP) |
| 34 | Protección contra hotlinking | No | v1.10 |
| 35-36 | Abuso de contraseñas y segundo factor | Ya | — |
| 37 | Claves SSH | No | v1.11 (SFTP con clave) |
| 38 | Fichas de API | No | v1.11 |
| 39-40 | Versiones y ajustes de PHP | Ya | v1.9 Portal (solo versiones ya instaladas) |
| 41 | Catálogo de aplicaciones | Ya (WordPress, Joomla, Drupal y más) | v1.9 Portal |
| 42 | Tareas cron | Ya | v1.9 Portal |
| 43 | Páginas de error propias | No | v1.10 |
| 44 | Manejadores de Apache | No aplica: nginx con PHP-FPM | — |
| 45 | Optimización (compresión, caché) | Parcial | v1.10 por sitio, pensando en conexiones rurales y satelitales |
| 46 | Node.js y Python | Ya (aplicaciones propias, administrador general) | v1.11 Portal con límites |
| 47-49, 51 | WordPress: instalar, entrar, actualizar, varios sitios | Ya | v1.9 Portal |
| 50 | Editor visual de páginas | Fuera del plan: Sitejet es de pago y cerrado | — (el editor de WordPress cubre esa necesidad) |
| 52 | Migración desde otro hosting | Ya (paquete y respaldo .sql) | v1.9 Portal |
| 53-54 | Estadísticas de visitas y tráfico | Parcial: Matomo en el catálogo | v1.10 (GoAccess, libre, sin rastreo en el navegador) |
| 55-56 | CPU y memoria por sitio | No (cada sitio ya tiene su propio PHP) | v1.11 |
| 57 | Errores del sitio | Parcial: registro por sitio, solo por SFTP | v1.10 visor en el portal |
| 58 | Monitoreo de disponibilidad | Ya del servidor (vigilantes) | v1.10 por sitio, con aviso al cliente |
| 59 | Información del servidor | Parcial | v1.10 Portal |

**v1.9 — El cliente administra su sitio** `IN PROGRESS`: pestaña «Mi sitio web» del portal de dominio
(sitios y subdominios, aplicaciones, HTTPS, FTP, cron, bases, PHP, archivos, migración, zona DNS, cuotas
por dominio, baja que confirma el administrador general).

**v1.10 — Hospedaje completo** `PLANNED`: administrador de archivos, redirecciones, privacidad de
directorios, páginas de error, hotlinking, bloqueo de IP por sitio, alias en el portal, copias que el
cliente descarga y restaura, estadísticas (GoAccess), visor de errores, disponibilidad por sitio,
importación de cuentas por CSV, optimización por sitio.

**v1.11 — Para desarrolladores** `PROPOSED`: git en sitios PHP, claves SSH, fichas de API, acceso remoto
a bases, usuarios de base con permisos, CPU y memoria por sitio, cortafuegos de aplicaciones (OWASP),
DNS dinámico, enrutamiento de correo, Node.js y Python desde el portal.

---

## Contribuir a la hoja de ruta

Las sugerencias de la comunidad son bienvenidas. Para proponer una funcionalidad:

1. Abre un issue en GitHub con la etiqueta `roadmap`
2. Describe el caso de uso y el comportamiento esperado
3. Los mantenedores revisarán y asignarán un hito si la propuesta es aceptada

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para las pautas de contribución.
