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

## Contribuir a la hoja de ruta

Las sugerencias de la comunidad son bienvenidas. Para proponer una funcionalidad:

1. Abre un issue en GitHub con la etiqueta `roadmap`
2. Describe el caso de uso y el comportamiento esperado
3. Los mantenedores revisarán y asignarán un hito si la propuesta es aceptada

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para las pautas de contribución.
