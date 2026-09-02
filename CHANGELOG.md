# Registro de cambios

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
y este proyecto sigue el [Versionado Semántico](https://semver.org/spec/v2.0.0.html).

## [Sin publicar]

Nada aún.

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
