# Módulo de Compliance / eDiscovery

## Arquitectura

```
┌─────────────────────────┐     ┌──────────────────────────┐
│  Admin Panel (:8443)    │     │  Webmail (:443)          │
│  /opt/maquita-admin/    │     │  /opt/maquita-webmail/   │
│  Bearer JWT Auth        │     │  Cookie JWT Auth         │
└──────────┬──────────────┘     └──────────┬───────────────┘
           │                               │
           │  nginx proxy                  │ direct
           │  /api/compliance/ → :8000     │
           ▼                               ▼
┌──────────────────────────────────────────────────────────┐
│  Backend Webmail (FastAPI :8000)                         │
│  /opt/maquita-webmail/backend/app/                      │
│                                                          │
│  ├── compliance/                                         │
│  │   ├── router.py          21 endpoints REST            │
│  │   ├── auth.py            Autenticación dual (cookie+bearer) │
│  │   ├── activity_logger.py Registro de actividad        │
│  │   ├── audit_middleware.py Intercepción automática      │
│  │   └── fraud_detector.py  Alertas cada 5 min           │
│  │                                                        │
│  └── log_ingestor/                                        │
│      └── mail_log_ingestor.py  tail mail.log → PostgreSQL │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  PostgreSQL (maildb)                                     │
│  8 tablas: user_activity_log, mail_trace,                │
│  compliance_cases, ediscovery_searches,                  │
│  ediscovery_results, ediscovery_exports,                 │
│  legal_holds, fraud_alerts                               │
└──────────────────────────────────────────────────────────┘
```

## Endpoints API (`/api/compliance/`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | /activity | Registro de actividad de usuarios |
| GET | /activity/stats | Estadísticas de actividad |
| GET | /activity/export | Exportar actividad (CSV) |
| GET/POST | /cases | Listar/crear casos |
| PUT | /cases/{id} | Actualizar caso |
| POST | /ediscovery/search | Ejecutar búsqueda forense |
| GET | /ediscovery/searches | Listar búsquedas |
| GET | /ediscovery/results/{id} | Resultados de búsqueda |
| POST | /ediscovery/export | Exportar con hash SHA-256 |
| GET | /ediscovery/exports | Listar exportaciones |
| GET/POST | /holds | Retenciones legales (legal holds) |
| DELETE | /holds/{id} | Desactivar retención |
| GET | /alerts | Alertas de fraude |
| PUT | /alerts/{id}/ack | Reconocer alerta |
| GET | /mail-trace | Rastreo de mensajes |
| GET | /mail-trace/stats | Estadísticas de correo |

## Servicios en Segundo Plano

### Ingestor de Registros (Log Ingestor)
- Ejecuta `tail -f /var/log/mail.log`
- Parsea líneas de Postfix, Dovecot y Rspamd
- Inserta los datos en la tabla `mail_trace`
- Se inicia automáticamente con el backend

### Detector de Fraude (Fraud Detector)
- Se ejecuta cada 5 minutos
- Detecta: envío masivo, destrucción de evidencia, reenvíos externos, inicio de sesión inusual
- Genera alertas automáticas en la tabla `fraud_alerts`

## Dependencias de Configuración

### Dovecot
- `conf.d/95-mail-log.conf` — habilita el registro de acciones de buzón
- `conf.d/90-quota.conf` — complementos: `notify mail_log`

### Nginx (panel admin :8443)
- Proxy `/api/compliance/` → backend webmail (:8000)

## Migración SQL
- `migrations/001_compliance_tables.sql` — DDL completo de las 8 tablas
