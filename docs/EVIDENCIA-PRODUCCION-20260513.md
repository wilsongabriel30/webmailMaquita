# Evidencia de Producción — Compliance Module
# Generado: 2026-05-13 11:21:02
# Servidor: VM 130 (mail-maquita) — mail.example.org

## Estado de Servicios

### maquita-webmail.service
```
● maquita-webmail.service - Maquita Webmail API
     Loaded: loaded (/etc/systemd/system/maquita-webmail.service; enabled; preset: enabled)
    Drop-In: /etc/systemd/system/maquita-webmail.service.d
             └─hardening.conf
     Active: active (running) since Wed 2026-05-13 10:58:06 -05; 22min ago
 Invocation: e56a94d109f640a89441f59274e69008
   Main PID: 1777367 (uvicorn)
      Tasks: 30 (limit: 100)
     Memory: 329.7M (max: 2G, available: 1.6G, peak: 332.1M)
        CPU: 29.845s
     CGroup: /system.slice/maquita-webmail.service
             ├─1777367 /opt/maquita-webmail/backend/venv/bin/python3 /opt/maquita-webmail/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4 --loop uvloop
```

### maquita-admin.service
```
● maquita-admin.service - Maquita Mail Admin Panel
     Loaded: loaded (/etc/systemd/system/maquita-admin.service; enabled; preset: enabled)
     Active: active (running) since Mon 2026-04-27 12:25:23 -05; 2 weeks 1 day ago
 Invocation: 355addd13a2943cebdaba4c7d75b8601
   Main PID: 1182 (uvicorn)
      Tasks: 12 (limit: 14329)
     Memory: 132.9M (peak: 152.9M, swap: 25.4M, swap peak: 27.7M)
        CPU: 2h 19min 3.168s
     CGroup: /system.slice/maquita-admin.service
             ├─1182 /opt/maquita-admin/backend/venv/bin/python3 /opt/maquita-admin/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 2
             ├─1188 /opt/maquita-admin/backend/venv/bin/python3 -c "from multiprocessing.resource_tracker import main;main(6)"
             ├─1189 /opt/maquita-admin/backend/venv/bin/python3 -c "from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=7, pipe_handle=9)" --multiprocessing-fork
```

## Conteo de Registros en Base de Datos

| Tabla | Registros |
|-------|----------|
| user_activity_log | N/A |
| mail_trace | N/A |
| compliance_cases | N/A |
| ediscovery_searches | N/A |
| ediscovery_results | N/A |
| ediscovery_exports | N/A |
| legal_holds | N/A |
| fraud_alerts | N/A |

### dovecot.service
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
      Tasks: 7 (limit: 14329)
     Memory: 12.2M (peak: 52.6M)
```

## API Endpoints

- GET /api/compliance/activity → HTTP 401
- GET /api/compliance/mail-trace → HTTP 401
- GET /api/compliance/alerts → HTTP 401
- GET https://mail.example.org:8443/compliance → HTTP 200

## Logs de Servicios Background
```
May 13 11:18:47 mail-maquita uvicorn[1777370]: 2026-05-13 11:18:47 [INFO] rid=c0fd97aa | action=http_request | module=core | ms=10.6 | status=401 | method=GET | path=/api/compliance/alerts
May 13 11:18:47 mail-maquita uvicorn[1777370]: INFO:     127.0.0.1:47606 - "GET /api/compliance/alerts?per_page=3 HTTP/1.1" 401 Unauthorized
May 13 11:21:10 mail-maquita uvicorn[1777370]: 2026-05-13 11:21:10 [INFO] rid=6a770e3a | action=http_request | module=core | ms=3.8 | status=401 | method=GET | path=/api/compliance/activity
May 13 11:21:10 mail-maquita uvicorn[1777370]: INFO:     127.0.0.1:56128 - "GET /api/compliance/activity HTTP/1.1" 401 Unauthorized
May 13 11:21:10 mail-maquita uvicorn[1777373]: 2026-05-13 11:21:10 [INFO] rid=f850ab38 | action=http_request | module=core | ms=7.1 | status=401 | method=GET | path=/api/compliance/mail-trace
May 13 11:21:10 mail-maquita uvicorn[1777373]: INFO:     127.0.0.1:56130 - "GET /api/compliance/mail-trace HTTP/1.1" 401 Unauthorized
May 13 11:21:10 mail-maquita uvicorn[1777372]: 2026-05-13 11:21:10 [INFO] rid=d92adc62 | action=http_request | module=core | ms=7.4 | status=401 | method=GET | path=/api/compliance/alerts
May 13 11:21:10 mail-maquita uvicorn[1777372]: INFO:     127.0.0.1:56140 - "GET /api/compliance/alerts HTTP/1.1" 401 Unauthorized
```

## Muestra mail_trace (últimos 5)
```
ERROR:  column "log_time" does not exist
LINE 1: SELECT id, queue_id, sender, recipient, status, log_time FRO...
                                                        ^
```

## Muestra fraud_alerts (últimos 5)
```
id |  alert_type   | severity |        username        |          created_at           
----+---------------+----------+------------------------+-------------------------------
  1 | unusual_login | high     | postmaster@maquita.org | 2026-05-13 15:56:49.583414+00
(1 row)
```

## Muestra user_activity_log (últimos 5)
```
id |        username        |    action     | category | risk_level |          created_at           
----+------------------------+---------------+----------+------------+-------------------------------
  2 | postmaster@maquita.org | login_success | auth     | low        | 2026-05-13 15:54:26.289467+00
  1 | postmaster@maquita.org | login_success | auth     | low        | 2026-05-13 15:54:15.865114+00
(2 rows)
```
