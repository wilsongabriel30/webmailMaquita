# Evidencia de Producción — Módulo Compliance/eDiscovery
**Generado:** 2026-05-13 11:22:05
**Servidor:** VM 130 (mail-maquita) — mail.example.org
**Tag:** v1.0-compliance

---

## 1. Conteo de Registros en Base de Datos (maildb)

| Tabla | Registros | Descripción |
|-------|-----------|-------------|
| user_activity_log | 2 | Acciones de usuario auditadas |
| mail_trace | 2124 | Mensajes rastreados (Postfix/Dovecot/Rspamd) |
| compliance_cases | 0 | Casos de investigación |
| ediscovery_searches | 0 | Búsquedas forenses ejecutadas |
| ediscovery_results | 0 | Resultados de búsqueda |
| ediscovery_exports | 0 | Exportaciones con hash SHA-256 |
| legal_holds | 0 | Retenciones legales |
| fraud_alerts | 1 | Alertas de fraude generadas |

## 2. Estado de Servicios

### maquita-webmail.service (backend compliance)
```
● maquita-webmail.service - Maquita Webmail API
     Loaded: loaded (/etc/systemd/system/maquita-webmail.service; enabled; preset: enabled)
    Drop-In: /etc/systemd/system/maquita-webmail.service.d
             └─hardening.conf
     Active: active (running) since Wed 2026-05-13 10:58:06 -05; 23min ago
 Invocation: e56a94d109f640a89441f59274e69008
   Main PID: 1777367 (uvicorn)
      Tasks: 30 (limit: 100)
     Memory: 329.7M (max: 2G, available: 1.6G, peak: 332.1M)
        CPU: 30.650s
     CGroup: /system.slice/maquita-webmail.service
             ├─1777367 /opt/maquita-webmail/backend/venv/bin/python3 /opt/maquita-webmail/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4 --loop uvloop
```

### maquita-admin.service (panel admin)
```
● maquita-admin.service - Maquita Mail Admin Panel
     Loaded: loaded (/etc/systemd/system/maquita-admin.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-04-27 12:25:23 -05; 2 weeks 1 day ago
 Invocation: 355addd13a2943cebdaba4c7d75b8601
   Main PID: 1182 (uvicorn)
      Tasks: 12 (limit: 14329)
     Memory: 132.9M (peak: 152.9M, swap: 25.4M, swap peak: 27.7M)
        CPU: 2h 19min 3.569s
     CGroup: /system.slice/maquita-admin.service
             ├─1182 /opt/maquita-admin/backend/venv/bin/python3 /opt/maquita-admin/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 2
             ├─1188 /opt/maquita-admin/backend/venv/bin/python3 -c "from multiprocessing.resource_tracker import main;main(6)"
             ├─1189 /opt/maquita-admin/backend/venv/bin/python3 -c "from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=7, pipe_handle=9)" --multiprocessing-fork
```

### dovecot.service (mail_log plugin activo)
```
● dovecot.service - Dovecot IMAP/POP3 email server
     Loaded: loaded (/usr/lib/systemd/system/dovecot.service; enabled; preset: enabled)
     Active: active (running) since Wed 2026-05-13 10:39:07 -05; 42min ago
 Invocation: ce6f251d2f4e46d3bbe085b14a95608e
       Docs: man:dovecot(1)
             https://doc.dovecot.org/
   Main PID: 1774559 (dovecot)
     Status: "v2.4.1-4 (7d8c0e5759) running"
```

### postfix.service
```
● postfix.service - Postfix Mail Transport Agent (main/default instance)
     Loaded: loaded (/usr/lib/systemd/system/postfix.service; enabled; preset: enabled)
     Active: active (running) since Tue 2026-05-12 17:55:18 -05; 17h ago
 Invocation: 221a8dd1f5e842c6ad717dbab5afbee5
       Docs: man:postfix(1)
   Main PID: 1682629 (master)
      Tasks: 6 (limit: 14329)
     Memory: 10.7M (peak: 52.6M)
```

## 3. API Endpoints — Test de Conectividad

| Endpoint | HTTP Code | Estado |
|----------|-----------|--------|
| GET /api/compliance/activity | 401 | OK |
| GET /api/compliance/mail-trace | 401 | OK |
| GET /api/compliance/alerts | 401 | OK |
| GET /api/compliance/cases | 401 | OK |
| GET https://mail.example.org:8443/compliance | 200 | OK — Panel accesible |

> Nota: HTTP 401 es correcto — indica que el endpoint existe y requiere autenticación.

## 4. Muestra de Datos — mail_trace (últimos 5)
```

```

## 5. Muestra de Datos — fraud_alerts
```
id |  alert_type   | severity |        username        |          created_at           
----+---------------+----------+------------------------+-------------------------------
  1 | unusual_login | high     | postmaster@maquita.org | 2026-05-13 15:56:49.583414+00
(1 row)
```

## 6. Muestra de Datos — user_activity_log
```
id |        username        |    action     | category | risk_level |          created_at           
----+------------------------+---------------+----------+------------+-------------------------------
  2 | postmaster@maquita.org | login_success | auth     | low        | 2026-05-13 15:54:26.289467+00
  1 | postmaster@maquita.org | login_success | auth     | low        | 2026-05-13 15:54:15.865114+00
(2 rows)
```

## 7. Logs de Servicios Background (journalctl)
```
May 13 11:18:47 mail-maquita uvicorn[1777370]: INFO:     127.0.0.1:47606 - "GET /api/compliance/alerts?per_page=3 HTTP/1.1" 401 Unauthorized
May 13 11:21:10 mail-maquita uvicorn[1777370]: 2026-05-13 11:21:10 [INFO] rid=6a770e3a | action=http_request | module=core | ms=3.8 | status=401 | method=GET | path=/api/compliance/activity
May 13 11:21:10 mail-maquita uvicorn[1777370]: INFO:     127.0.0.1:56128 - "GET /api/compliance/activity HTTP/1.1" 401 Unauthorized
May 13 11:21:10 mail-maquita uvicorn[1777373]: 2026-05-13 11:21:10 [INFO] rid=f850ab38 | action=http_request | module=core | ms=7.1 | status=401 | method=GET | path=/api/compliance/mail-trace
May 13 11:21:10 mail-maquita uvicorn[1777373]: INFO:     127.0.0.1:56130 - "GET /api/compliance/mail-trace HTTP/1.1" 401 Unauthorized
May 13 11:21:10 mail-maquita uvicorn[1777372]: 2026-05-13 11:21:10 [INFO] rid=d92adc62 | action=http_request | module=core | ms=7.4 | status=401 | method=GET | path=/api/compliance/alerts
May 13 11:21:10 mail-maquita uvicorn[1777372]: INFO:     127.0.0.1:56140 - "GET /api/compliance/alerts HTTP/1.1" 401 Unauthorized
May 13 11:22:06 mail-maquita uvicorn[1777373]: 2026-05-13 11:22:06 [INFO] rid=7209840a | action=http_request | module=core | ms=4.1 | status=401 | method=GET | path=/api/compliance/activity
May 13 11:22:06 mail-maquita uvicorn[1777373]: INFO:     127.0.0.1:52588 - "GET /api/compliance/activity HTTP/1.1" 401 Unauthorized
May 13 11:22:06 mail-maquita uvicorn[1777373]: 2026-05-13 11:22:06 [INFO] rid=3ed17324 | action=http_request | module=core | ms=3.5 | status=401 | method=GET | path=/api/compliance/mail-trace
May 13 11:22:06 mail-maquita uvicorn[1777373]: INFO:     127.0.0.1:52594 - "GET /api/compliance/mail-trace HTTP/1.1" 401 Unauthorized
May 13 11:22:06 mail-maquita uvicorn[1777371]: 2026-05-13 11:22:06 [INFO] rid=ced8e31e | action=http_request | module=core | ms=8.6 | status=401 | method=GET | path=/api/compliance/alerts
May 13 11:22:06 mail-maquita uvicorn[1777371]: INFO:     127.0.0.1:52600 - "GET /api/compliance/alerts HTTP/1.1" 401 Unauthorized
May 13 11:22:06 mail-maquita uvicorn[1777372]: 2026-05-13 11:22:06 [INFO] rid=6377ed81 | action=http_request | module=core | ms=2.1 | status=401 | method=GET | path=/api/compliance/cases
May 13 11:22:06 mail-maquita uvicorn[1777372]: INFO:     127.0.0.1:52616 - "GET /api/compliance/cases HTTP/1.1" 401 Unauthorized
```

## 8. Configuración Dovecot Compliance
```
# Mail Log Plugin — Compliance/Auditoría
# Registra acciones críticas de buzón
# Activado 2026-05-13

mail_log_events = delete undelete expunge copy mailbox_delete mailbox_rename flag_change save append
mail_log_fields = uid box msgid from subject size vsize flags
```

## 9. Plugins Dovecot Activos
```
mail_plugins = quota acl fts fts_xapian lazy_expunge mail_crypt mail_compress notify mail_log
```

## 10. Nginx Proxy Compliance (admin:8443 → webmail:8000)
```
location /api/compliance/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host mail.example.org;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
```

---

## Trazabilidad Git

| Repositorio | Tag | Commit |
|-------------|-----|--------|
| webmailMaquita | v1.0-compliance | b011a4c feat: compliance audit-ready — migraciones SQL, configs, evidencia |
| adminMaquita | v1.0-compliance | d693f39 feat: centro de compliance + personalización (branding) |

### Archivos versionados (compliance)
```
- migrations/001_compliance_tables.sql — DDL completo 8 tablas
    - config/dovecot/95-mail-log.conf — logging de acciones de buzón
    - config/nginx/compliance-proxy.conf — proxy admin→webmail para compliance API
    - docs/COMPLIANCE.md — documentación técnica del módulo
    - docs/EVIDENCIA-PRODUCCION-20260513.md — evidencia de producción con conteos
    - backend/app/log_ingestor/__init__.py — init module
    - frontend: actualización rutas para compliance panel
    
    Co-Authored-By: IA Opus 4.6 <noreply@IA.com>

 config/dovecot/90-quota-compliance-note.conf  |    3 +
 config/dovecot/95-mail-log.conf               |    6 +
 config/nginx/compliance-proxy.conf            |   12 +
 docs/COMPLIANCE.md                            |   84 ++
 docs/EVIDENCIA-PRODUCCION-20260513.md         |  117 +++
 frontend/src/App.tsx                          |    2 +
 frontend/src/components/admin/AdminLayout.tsx |    1 +
 migrations/001_compliance_tables.sql          | 1230 +++++++++++++++++++++++++
 8 files changed, 1455 insertions(+)
```
