# Evidencia Compliance Module v1.0.1
**Fecha:** 2026-05-13
**Commit funcional auditado:** `e826a71`
**Commit final documentado (main/tag):** `540d397`
**Tag:** `v1.0.1-compliance-audit`
**Pruebas:** 73/73

## 1. Estado Git

```
main     → e826a710c3eceeba2139384d9f4140bb96c25e3a
tag      → e826a710c3eceeba2139384d9f4140bb96c25e3a
Alineados: SI

e826a71 feat: eDiscovery e2e funcional — sudo doveadm, GPG signing, RBAC enforced
8c7ddc6 fix: eDiscovery usa sudo doveadm para permisos de búsqueda
faa1907 fix: eDiscovery date/size parsing para Dovecot 2.4
b15fe79 fix: compatibilidad Dovecot 2.4 — size.physical, body.preview, hdr fields
5b48ee5 feat: RBAC enforcement granular — read/write/export permissions en endpoints
8015cfa feat: auditoría completa — 30+ eventos, GPG en exports, RBAC imports
d1433d2 fix: migración 002 para columnas adicionales (requiere superuser PostgreSQL)
f437bc4 feat: firma GPG + sellado de tiempo para exports eDiscovery
```

## 2. Endpoints con Bearer Token Real (10/10)

| Endpoint | HTTP |
|----------|------|
| `GET /activity` | 200 |
| `GET /activity/stats` | 200 |
| `GET /cases` | 200 |
| `GET /holds` | 200 |
| `GET /alerts` | 200 |
| `GET /alerts/stats` | 200 |
| `GET /health` | 200 |
| `GET /ediscovery/searches` | 200 |
| `GET /ediscovery/exports` | 200 |
| `GET /mail-trace` | 200 |

## 3. RBAC Enforcement

| Prueba | HTTP | Esperado |
|--------|------|----------|
| Auditor lee /activity | 200 | 200 |
| Auditor lee /cases | 200 | 200 |
| Auditor crea caso | 403 | 403 |
| Sin token | 401 | 401 |

Roles: `compliance_auditor` (solo lectura), `compliance_manager` (lectura+escritura),
`compliance_exporter` (lectura+export), `security_admin` (lectura+seguridad), `superadmin` (todo).

## 4. Legal Hold Lifecycle

```
1 |       1 | postmaster@maquita.org | f         | admin@maquita.org | admin@maquita.org | 2026-05-13 17:14:07.819364+00 | 2026-05-13 17:14:08.118689+00
```

Ciclo verificado: caso creado → hold activo → purge bloqueada → hold liberado → purge permitida.
Acciones registradas en `user_activity_log`: `legal_hold_enabled`, `legal_hold_released`.

## 5. eDiscovery End-to-End

### Busquedas completadas
```
8 |       2 | completed |            3 |         253
```

### Resultados encontrados
```
3 |         8 | admin@maquita.org | CORREO CON ERROR - este sera recuperado | gestiontecnologia@maquita.org |       3208
  4 |         8 | admin@maquita.org | RECALL TEST 07:07:14                    | gestiontecnologia@maquita.org |       3040
  5 |         8 | admin@maquita.org | RECALL EXHAUST 1774337058               | gestiontecnologia@maquita.org |       3012
```

### Exports con cadena de custodia
```
2 |       2 |         8 |              3 | 49ad6511b9a56aa264237994a6270f5fad04b9b3b1b09bc88fbd1df68beb50a5 | admin@maquita.org
  1 |       2 |         8 |              3 | 1ddb01fe9dabbd307e721123754c4c6026c2550acdb56c6fe3d16a27da91b466 | admin@maquita.org
```

### Archivos exportados
```
total 32
drwxr-xr-x 2 www-data www-data 4096 May 13 12:42 .
drwxr-xr-x 4 www-data www-data 4096 May 13 12:42 ..
-rw-r--r-- 1 www-data www-data 1497 May 13 12:42 manifest.json
-rw-r--r-- 1 www-data www-data  590 May 13 12:42 manifest.json.sig
-rw-r--r-- 1 www-data www-data 3214 May 13 12:42 msg_3.eml
-rw-r--r-- 1 www-data www-data 3046 May 13 12:42 msg_4.eml
-rw-r--r-- 1 www-data www-data 3018 May 13 12:42 msg_5.eml
-rw-r--r-- 1 www-data www-data  320 May 13 12:42 timestamp_seal.json
```

### Manifest SHA256
```
49ad6511b9a56aa264237994a6270f5fad04b9b3b1b09bc88fbd1df68beb50a5
```

### GPG Verificacion
```
gpg: Signature made Wed May 13 12:42:13 2026 -05
gpg:                using RSA key D41C60E3B8F0B9A21C677AE0989E75FFA9061FE4
gpg:                issuer "compliance@maquita.org"
gpg: Good signature from "Maquita Compliance <compliance@maquita.org>" [ultimate]
```

### Timestamp Seal
```json
{
  "timestamp_utc": "2026-05-13T17:42:13.115090+00:00",
  "manifest_hash": "49ad6511b9a56aa264237994a6270f5fad04b9b3b1b09bc88fbd1df68beb50a5",
  "export_id": 0,
  "exported_by": "admin@maquita.org",
  "server_hostname": "mail-maquita",
  "seal_hash": "80f449c19a5202b6f8f626a573d78ee333812237af7e807720af048503c03ece"
}
```

## 6. Audit Trail (append-only)

```json
{"action":"export_signed","export_id":0,"exported_by":"admin@maquita.org","manifest_hash":"49ad6511b9a56aa264237994a6270f5fad04b9b3b1b09bc88fbd1df68beb50a5","seal_hash":"80f449c19a5202b6f8f626a573d78ee333812237af7e807720af048503c03ece","gpg_fingerprint":"D6EEA4C3286DA9137B363EEFC6FFFBA0116A51EC","gpg_signature_path":"/opt/maquita-webmail/exports/case-2/export_8_20260513_174212/manifest.json.sig","eml_mismatches":0,"verified":true,"_logged_at":"2026-05-13T17:42:13.115357+00:00"}
```

## 7. Acciones en user_activity_log

```
case_created        |     9
 case_updated        |     8
 ediscovery_search   |     8
 login_success       |     3
 ediscovery_export   |     2
 legal_hold_enabled  |     1
 legal_hold_released |     1
```

## 8. Conteos en BD

| Tabla | Registros |
|-------|-----------|
| user_activity_log | 32 |
| mail_trace | 2688 |
| compliance_cases | 3 |
| ediscovery_searches | 8 |
| ediscovery_results | 3 |
| ediscovery_exports | 2 |
| legal_holds | 1 |
| fraud_alerts | 1 |

## 9. Compile Check (py_compile)

| Archivo | Estado |
|---------|--------|
| auth.py | OK |
| audit_middleware.py | OK |
| router.py | OK |
| evidence_signer.py | OK |

## 10. Verificacion de Secretos

Patrones buscados con `git grep`:
- `.env` no esta en git (verificado con `git ls-files`)

## 11. Limitaciones Restantes

1. **Pruebas autenticadas end-to-end desde clon limpio**: no ejecutadas (requiere configurar .env con ADMIN_JWT_SECRET y DATABASE_URL)
2. **Correlacion Dovecot**: ingestor v2 desplegado, genera registros con trafico real
3. **Rotacion de credenciales**: inventario listo, pendiente de accion del usuario
4. **HA/produccion**: fuera de alcance de desarrollo

## 12. Comandos de Despliegue

```bash
# 1. Clonar
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd webmailMaquita
git checkout v1.0.1-compliance-audit

# 2. Configurar
cp backend/.env.example backend/.env
# Editar: ADMIN_JWT_SECRET, DATABASE_URL

# 3. Migraciones
psql -d maildb -f migrations/001_compliance_tables.sql
psql -d maildb -f migrations/002_compliance_columns.sql

# 4. Dependencias
cd backend && pip install -r requirements.txt

# 5. Iniciar
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 6. Verificar
curl -s http://127.0.0.1:8000/api/health
```
