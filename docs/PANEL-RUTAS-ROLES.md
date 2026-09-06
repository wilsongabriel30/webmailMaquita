# Panel de administración — endpoint → rol exigido → dónde se exige

Generado el 2026-09-06 a partir de `admin-panel/backend/app` (decoradores de ruta y `Depends`).
Mecanismos: `require_superadmin` / `require_role(...)` / `require_operador` son explícitos;
`get_current_admin` aplica el **rol efectivo por petición** (A-18): `viewer` solo puede GET/HEAD/OPTIONS
y nunca correo ajeno, cualquier rol desconocido se trata como viewer. Lo marcado **SIN PROTECCIÓN
EXPLÍCITA** no lleva ninguna dependencia de autenticación en la ruta: hay que revisarlo uno a uno
(login, salud y marca pública son legítimos; el resto no).

| Método | Ruta | Dependencia | Mecanismo | Fichero |
|---|---|---|---|---|
| POST | `/api/admin-recovery/register` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/admin_recovery/router.py` |
| POST | `/api/admin-recovery/request` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/admin_recovery/router.py` |
| POST | `/api/admin-recovery/reset` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/admin_recovery/router.py` |
| GET | `/api/admin-recovery/status` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/admin_recovery/router.py` |
| POST | `/api/admin-recovery/verify` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/admin_recovery/router.py` |
| GET | `/api/admin/outbound/activity` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/outbound/router.py` |
| GET | `/api/admin/outbound/limits` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/outbound/router.py` |
| PUT | `/api/admin/outbound/limits` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/outbound/router.py` |
| POST | `/api/admin/outbound/lock` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/outbound/router.py` |
| GET | `/api/admin/outbound/status/{email}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/outbound/router.py` |
| POST | `/api/admin/outbound/unlock` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/outbound/router.py` |
| GET | `/api/advanced-audit/export` | `require_role` | require_role(…) — rol explícito | `app/advanced_audit/router.py` |
| GET | `/api/advanced-audit/facets` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/advanced_audit/router.py` |
| GET | `/api/advanced-audit/retention` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/advanced_audit/router.py` |
| PUT | `/api/advanced-audit/retention` | `require_role` | require_role(…) — rol explícito | `app/advanced_audit/router.py` |
| POST | `/api/advanced-audit/retention/purge` | `require_role` | require_role(…) — rol explícito | `app/advanced_audit/router.py` |
| GET | `/api/advanced-audit/search` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/advanced_audit/router.py` |
| GET | `/api/advanced-audit/summary` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/advanced_audit/router.py` |
| GET | `/api/agents/list` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/agents/router.py` |
| POST | `/api/agents/run` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/agents/router.py` |
| GET | `/api/ai-config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/ai_config/router.py` |
| PUT | `/api/ai-config` | `require_role` | require_role(…) — rol explícito | `app/ai_config/router.py` |
| POST | `/api/ai-config/test` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/ai_config/router.py` |
| GET | `/api/air/incidents` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/air/router.py` |
| POST | `/api/air/investigate` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/air/router.py` |
| POST | `/api/air/lock` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/air/router.py` |
| GET | `/api/aliases` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/aliases/router.py` |
| POST | `/api/aliases` | `require_role` | require_role(…) — rol explícito | `app/aliases/router.py` |
| DELETE | `/api/aliases/{address:path}` | `require_role` | require_role(…) — rol explícito | `app/aliases/router.py` |
| PUT | `/api/aliases/{address:path}` | `require_role` | require_role(…) — rol explícito | `app/aliases/router.py` |
| GET | `/api/antispam-avanzado` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/antispam_avanzado/router.py` |
| PUT | `/api/antispam-avanzado` | `require_role` | require_role(…) — rol explícito | `app/antispam_avanzado/router.py` |
| POST | `/api/antispam-avanzado/depurar` | `require_role` | require_role(…) — rol explícito | `app/antispam_avanzado/router.py` |
| GET | `/api/audit` | `get_current_admin` (línea 15; el extractor no lo vio) | rol efectivo — falso positivo del extractor | `app/audit/router.py` |
| GET | `/api/auth/admins` | `require_superadmin` | superadmin | `app/auth/router.py` |
| POST | `/api/auth/admins` | `require_superadmin` | superadmin | `app/auth/router.py` |
| DELETE | `/api/auth/admins/{user_id}` | `require_superadmin` | superadmin | `app/auth/router.py` |
| PUT | `/api/auth/admins/{user_id}` | `require_superadmin` | superadmin | `app/auth/router.py` |
| POST | `/api/auth/change-password` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| POST | `/api/auth/login` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/auth/router.py` |
| POST | `/api/auth/logout` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| POST | `/api/auth/logout-all` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| GET | `/api/auth/me` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| GET | `/api/auth/sessions` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| POST | `/api/auth/totp/disable` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| POST | `/api/auth/totp/setup` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| GET | `/api/auth/totp/status` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| POST | `/api/auth/totp/verify` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| POST | `/api/auth/verify-password` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/auth/router.py` |
| GET | `/api/autoresponder` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/autoresponder/router.py` |
| POST | `/api/autoresponder` | `require_role` | require_role(…) — rol explícito | `app/autoresponder/router.py` |
| DELETE | `/api/autoresponder/{username:path}` | `require_role` | require_role(…) — rol explícito | `app/autoresponder/router.py` |
| GET | `/api/autoresponder/{username:path}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/autoresponder/router.py` |
| GET | `/api/branding` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/branding/router.py` |
| PUT | `/api/branding` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/branding/router.py` |
| DELETE | `/api/branding/file/{file_type}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/branding/router.py` |
| GET | `/api/branding/file/{file_type}/{filename}` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/branding/router.py` |
| POST | `/api/branding/upload/{file_type}` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/branding/router.py` |
| GET | `/api/comm-compliance/flags` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/comm_compliance/router.py` |
| POST | `/api/comm-compliance/flags/{fid}/status` | `require_role` | require_role(…) — rol explícito | `app/comm_compliance/router.py` |
| GET | `/api/comm-compliance/policies` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/comm_compliance/router.py` |
| POST | `/api/comm-compliance/policies` | `require_role` | require_role(…) — rol explícito | `app/comm_compliance/router.py` |
| DELETE | `/api/comm-compliance/policies/{pid}` | `require_role` | require_role(…) — rol explícito | `app/comm_compliance/router.py` |
| PUT | `/api/comm-compliance/policies/{pid}` | `require_role` | require_role(…) — rol explícito | `app/comm_compliance/router.py` |
| POST | `/api/conditional-access/delete` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/conditional_access/router.py` |
| GET | `/api/conditional-access/policies` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/conditional_access/router.py` |
| POST | `/api/conditional-access/policies` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/conditional_access/router.py` |
| POST | `/api/conditional-access/toggle` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/conditional_access/router.py` |
| GET | `/api/connections` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/connections/router.py` |
| POST | `/api/copiloto/ask` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/copiloto/router.py` |
| GET | `/api/dashboard` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/dashboard/router.py` |
| GET | `/api/dashboard/mail-volume` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/dashboard/router.py` |
| GET | `/api/dashboard/storage` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/dashboard/router.py` |
| GET | `/api/dlp-config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/dlp_config/router.py` |
| PUT | `/api/dlp-config` | `require_role` | require_role(…) — rol explícito | `app/dlp_config/router.py` |
| GET | `/api/dlp-config/violations` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/dlp_config/router.py` |
| GET | `/api/dnscheck` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/dnscheck/router.py` |
| GET | `/api/dnscheck/{domain}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/dnscheck/router.py` |
| GET | `/api/domains` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/domains/router.py` |
| POST | `/api/domains` | `require_role` | require_role(…) — rol explícito | `app/domains/router.py` |
| DELETE | `/api/domains/{domain}` | `require_role` | require_role(…) — rol explícito | `app/domains/router.py` |
| GET | `/api/domains/{domain}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/domains/router.py` |
| PUT | `/api/domains/{domain}` | `require_role` | require_role(…) — rol explícito | `app/domains/router.py` |
| GET | `/api/ediscovery-premium/cases` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/ediscovery_premium/router.py` |
| POST | `/api/ediscovery-premium/cases` | `require_role` | require_role(…) — rol explícito | `app/ediscovery_premium/router.py` |
| GET | `/api/ediscovery-premium/cases/{cid}/custodians` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/ediscovery_premium/router.py` |
| POST | `/api/ediscovery-premium/cases/{cid}/custodians` | `require_role` | require_role(…) — rol explícito | `app/ediscovery_premium/router.py` |
| DELETE | `/api/ediscovery-premium/custodians/{cust_id}` | `require_role` | require_role(…) — rol explícito | `app/ediscovery_premium/router.py` |
| POST | `/api/ediscovery-premium/custodians/{cust_id}/notify` | `require_role` | require_role(…) — rol explícito | `app/ediscovery_premium/router.py` |
| GET | `/api/ediscovery/export/{mailbox}` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/ediscovery/router.py` |
| GET | `/api/ediscovery/mailboxes` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/ediscovery/router.py` |
| GET | `/api/ediscovery/search` | `get_current_admin` (dentro de la firma; el extractor no lo vio) | rol efectivo — **H-01 6ª revisión: falso positivo** | `app/ediscovery/router.py` |
| GET | `/api/forwarding` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/forwarding/router.py` |
| POST | `/api/forwarding` | `require_role` | require_role(…) — rol explícito | `app/forwarding/router.py` |
| DELETE | `/api/forwarding/{address:path}` | `require_role` | require_role(…) — rol explícito | `app/forwarding/router.py` |
| GET | `/api/forwarding/{username:path}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/forwarding/router.py` |
| GET | `/api/geo-access/countries` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/geo_access/router.py` |
| POST | `/api/geo-access/toggle` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/geo_access/router.py` |
| GET | `/api/groups` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/groups/router.py` |
| POST | `/api/groups` | `require_role` | require_role(…) — rol explícito | `app/groups/router.py` |
| GET | `/api/groups/audit` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/groups/router.py` |
| GET | `/api/groups/by-member` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/groups/router.py` |
| DELETE | `/api/groups/{group_id}` | `require_role` | require_role(…) — rol explícito | `app/groups/router.py` |
| GET | `/api/groups/{group_id}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/groups/router.py` |
| PUT | `/api/groups/{group_id}` | `require_role` | require_role(…) — rol explícito | `app/groups/router.py` |
| POST | `/api/groups/{group_id}/members` | `require_role` | require_role(…) — rol explícito | `app/groups/router.py` |
| DELETE | `/api/groups/{group_id}/members/{member_id}` | `require_role` | require_role(…) — rol explícito | `app/groups/router.py` |
| PUT | `/api/groups/{group_id}/members/{member_id}` | `require_role` | require_role(…) — rol explícito | `app/groups/router.py` |
| GET | `/api/health` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/health/router.py` |
| GET | `/api/health-check` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/main.py` |
| GET | `/api/health/connections` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/health/router.py` |
| GET | `/api/health/fail2ban` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/health/router.py` |
| GET | `/api/insider-risk/users` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/insider_risk/router.py` |
| GET | `/api/insider-risk/users/{email}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/insider_risk/router.py` |
| GET | `/api/mailboxes` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/mailboxes/router.py` |
| POST | `/api/mailboxes` | `require_role` | require_role(…) — rol explícito | `app/mailboxes/router.py` |
| GET | `/api/mailboxes/quota/all` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/mailboxes/router.py` |
| GET | `/api/mailboxes/search/autocomplete` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/mailboxes/router.py` |
| DELETE | `/api/mailboxes/{username:path}` | `require_role` | require_role(…) — rol explícito | `app/mailboxes/router.py` |
| PUT | `/api/mailboxes/{username:path}` | `require_role` | require_role(…) — rol explícito | `app/mailboxes/router.py` |
| POST | `/api/mailboxes/{username:path}/cambiar-titular` | `require_role` | require_role(…) — rol explícito | `app/mailboxes/router.py` |
| GET | `/api/mailboxes/{username:path}/detail` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/mailboxes/router.py` |
| POST | `/api/mailboxes/{username:path}/impersonate` | `require_role` | require_role(…) — rol explícito | `app/mailboxes/router.py` |
| POST | `/api/mailboxes/{username:path}/toggle-active` | `require_role` | require_role(…) — rol explícito | `app/mailboxes/router.py` |
| POST | `/api/mailviewer/delete` | `require_operador,require_role` | require_role(…) — rol explícito | `app/mailviewer/router.py` |
| GET | `/api/mailviewer/folders/{username:path}` | `get_current_admin,require_operador` | operador+ | `app/mailviewer/router.py` |
| GET | `/api/mailviewer/message/{username:path}` | `require_operador` | operador+ | `app/mailviewer/router.py` |
| GET | `/api/mailviewer/messages/{username:path}` | `require_operador` | operador+ | `app/mailviewer/router.py` |
| POST | `/api/mailviewer/move` | `require_operador,require_role` | require_role(…) — rol explícito | `app/mailviewer/router.py` |
| GET | `/api/mailviewer/quota/{username:path}` | `get_current_admin,require_operador` | operador+ | `app/mailviewer/router.py` |
| GET | `/api/mailviewer/search/{username:path}` | `require_operador` | operador+ | `app/mailviewer/router.py` |
| GET | `/api/nextcloud/check/{email}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/nextcloud/router.py` |
| GET | `/api/nextcloud/groups` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/nextcloud/router.py` |
| GET | `/api/nextcloud/status` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/nextcloud/router.py` |
| GET | `/api/nextcloud/users` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/nextcloud/router.py` |
| POST | `/api/nextcloud/users` | `require_role` | require_role(…) — rol explícito | `app/nextcloud/router.py` |
| GET | `/api/nextcloud/users/{userid}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/nextcloud/router.py` |
| GET | `/api/office-config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/office_config/router.py` |
| PUT | `/api/office-config` | `require_role` | require_role(…) — rol explícito | `app/office_config/router.py` |
| POST | `/api/office-config/test` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/office_config/router.py` |
| GET | `/api/outbound-anomaly/config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/outbound_anomaly/router.py` |
| PUT | `/api/outbound-anomaly/config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/outbound_anomaly/router.py` |
| GET | `/api/outbound-anomaly/events` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/outbound_anomaly/router.py` |
| GET | `/api/phish/campaigns` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/phish_campaigns/router.py` |
| POST | `/api/phish/campaigns` | `require_role` | require_role(…) — rol explícito | `app/phish_campaigns/router.py` |
| DELETE | `/api/phish/campaigns/{cid}` | `require_role` | require_role(…) — rol explícito | `app/phish_campaigns/router.py` |
| GET | `/api/phish/campaigns/{cid}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/phish_campaigns/router.py` |
| POST | `/api/phish/campaigns/{cid}/send` | `require_role` | require_role(…) — rol explícito | `app/phish_campaigns/router.py` |
| GET | `/api/phish/recipients` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/phish_campaigns/router.py` |
| GET | `/api/phish/templates` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/phish_campaigns/router.py` |
| GET | `/api/quarantine/errors` | `get_current_admin,require_operador` | operador+ | `app/quarantine/router.py` |
| GET | `/api/quarantine/history` | `require_operador` | operador+ | `app/quarantine/router.py` |
| GET | `/api/quarantine/junk/{username:path}` | `get_current_admin,require_operador` | operador+ | `app/quarantine/router.py` |
| POST | `/api/quarantine/mark-spam` | `require_operador,require_role` | require_role(…) — rol explícito | `app/quarantine/router.py` |
| POST | `/api/quarantine/release` | `require_operador,require_role` | require_role(…) — rol explícito | `app/quarantine/router.py` |
| GET | `/api/quarantine/stats` | `get_current_admin,require_operador` | operador+ | `app/quarantine/router.py` |
| GET | `/api/queue` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/queue/router.py` |
| POST | `/api/queue/action` | `require_role` | require_role(…) — rol explícito | `app/queue/router.py` |
| POST | `/api/rag/ask` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/rag/router.py` |
| GET | `/api/rag/domains` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/rag/router.py` |
| POST | `/api/rag/domains` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/rag/router.py` |
| POST | `/api/rag/domains/toggle` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/rag/router.py` |
| POST | `/api/rag/ingest` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/rag/router.py` |
| POST | `/api/recovery/restore` | `require_operador,require_role` | require_role(…) — rol explícito | `app/recovery/router.py` |
| POST | `/api/recovery/restore-bulk` | `require_operador,require_role` | require_role(…) — rol explícito | `app/recovery/router.py` |
| GET | `/api/recovery/search/{username:path}` | `get_current_admin,require_operador` | operador+ | `app/recovery/router.py` |
| GET | `/api/recovery/trash/{username:path}` | `get_current_admin,require_operador` | operador+ | `app/recovery/router.py` |
| GET | `/api/resend/cuentas` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/resend/router.py` |
| POST | `/api/resend/enviar` | `require_role` | require_role(…) — rol explícito | `app/resend/router.py` |
| GET | `/api/resend/rebotes/{cuenta}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/resend/router.py` |
| POST | `/api/retention/delete` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/retention/router.py` |
| GET | `/api/retention/policies` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/retention/router.py` |
| POST | `/api/retention/policies` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/retention/router.py` |
| POST | `/api/retention/toggle` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/retention/router.py` |
| GET | `/api/risky-logins` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/risky_login/router.py` |
| GET | `/api/risky-logins/config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/risky_login/router.py` |
| PUT | `/api/risky-logins/config` | `require_role` | require_role(…) — rol explícito | `app/risky_login/router.py` |
| GET | `/api/risky-logins/recent` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/risky_login/router.py` |
| POST | `/api/risky-logins/{rid}/status` | `require_role` | require_role(…) — rol explícito | `app/risky_login/router.py` |
| POST | `/api/safeattach/analyze` | `require_role` | require_role(…) — rol explícito | `app/safeattach/router.py` |
| GET | `/api/safeattach/cola-cuarentena` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/safeattach/router.py` |
| GET | `/api/safeattach/config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/safeattach/router.py` |
| PUT | `/api/safeattach/config` | `require_role` | require_role(…) — rol explícito | `app/safeattach/router.py` |
| GET | `/api/safeattach/engine-status` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/safeattach/router.py` |
| POST | `/api/safeattach/release/{action_id}` | `require_role` | require_role(…) — rol explícito | `app/safeattach/router.py` |
| GET | `/api/safeattach/results` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/safeattach/router.py` |
| POST | `/api/safeattach/scan` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/safeattach/router.py` |
| GET | `/api/safeattach/stats` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/safeattach/router.py` |
| GET | `/api/safelinks-config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/safelinks_config/router.py` |
| PUT | `/api/safelinks-config` | `require_role` | require_role(…) — rol explícito | `app/safelinks_config/router.py` |
| GET | `/api/safelinks-config/clicks` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/safelinks_config/router.py` |
| GET | `/api/secure-config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/secure_config/router.py` |
| PUT | `/api/secure-config` | `require_role` | require_role(…) — rol explícito | `app/secure_config/router.py` |
| GET | `/api/secure-config/messages` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/secure_config/router.py` |
| POST | `/api/secure-config/messages/{token}/revoke` | `require_role` | require_role(…) — rol explícito | `app/secure_config/router.py` |
| GET | `/api/security-policies` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/security_policies/router.py` |
| POST | `/api/security-policies` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/security_policies/router.py` |
| GET | `/api/services` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/services/router.py` |
| POST | `/api/services/fail2ban/ban` | `require_role` | require_role(…) — rol explícito | `app/services/router.py` |
| POST | `/api/services/fail2ban/ban-all` | `require_role` | require_role(…) — rol explícito | `app/services/router.py` |
| GET | `/api/services/fail2ban/jail-config/{jail_name}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/services/router.py` |
| PUT | `/api/services/fail2ban/jail-config/{jail_name}` | `require_role` | require_role(…) — rol explícito | `app/services/router.py` |
| GET | `/api/services/fail2ban/jails` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/services/router.py` |
| GET | `/api/services/fail2ban/search/{ip}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/services/router.py` |
| POST | `/api/services/fail2ban/unban` | `require_role` | require_role(…) — rol explícito | `app/services/router.py` |
| POST | `/api/services/fail2ban/unban-all` | `require_role` | require_role(…) — rol explícito | `app/services/router.py` |
| GET | `/api/services/{service_key}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/services/router.py` |
| GET | `/api/services/{service_key}/config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/services/router.py` |
| PUT | `/api/services/{service_key}/config` | `require_role` | require_role(…) — rol explícito | `app/services/router.py` |
| GET | `/api/services/{service_key}/logs` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/services/router.py` |
| POST | `/api/services/{service_key}/{action}` | `require_role` | require_role(…) — rol explícito | `app/services/router.py` |
| GET | `/api/shared/delegates` | `require_role` | require_role(…) — rol explícito | `app/shared/router.py` |
| POST | `/api/shared/mailbox/{username:path}/grant` | `require_role` | require_role(…) — rol explícito | `app/shared/router.py` |
| GET | `/api/shared/mailbox/{username:path}/permissions` | `require_role` | require_role(…) — rol explícito | `app/shared/router.py` |
| POST | `/api/shared/mailbox/{username:path}/revoke` | `require_role` | require_role(…) — rol explícito | `app/shared/router.py` |
| GET | `/api/signatures/preview/{sig_id}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/signatures/router.py` |
| GET | `/api/signatures/templates` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/signatures/router.py` |
| POST | `/api/signatures/templates` | `require_role` | require_role(…) — rol explícito | `app/signatures/router.py` |
| DELETE | `/api/signatures/templates/{sig_id}` | `require_role` | require_role(…) — rol explícito | `app/signatures/router.py` |
| PUT | `/api/signatures/templates/{sig_id}` | `require_role` | require_role(…) — rol explícito | `app/signatures/router.py` |
| GET | `/api/signatures/users` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/signatures/router.py` |
| POST | `/api/signatures/users` | `require_role` | require_role(…) — rol explícito | `app/signatures/router.py` |
| POST | `/api/signatures/users/bulk` | `require_role` | require_role(…) — rol explícito | `app/signatures/router.py` |
| GET | `/api/sso/status` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/sso/router.py` |
| POST | `/api/sso/sync` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/sso/router.py` |
| GET | `/api/threats/actions` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/threats/router.py` |
| POST | `/api/threats/block-sender` | `require_role` | require_role(…) — rol explícito | `app/threats/router.py` |
| GET | `/api/threats/blocked-senders` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/threats/router.py` |
| GET | `/api/threats/config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/threats/router.py` |
| PUT | `/api/threats/config` | `require_role` | require_role(…) — rol explícito | `app/threats/router.py` |
| POST | `/api/threats/disable-mailbox` | `require_role` | require_role(…) — rol explícito | `app/threats/router.py` |
| POST | `/api/threats/enable-mailbox` | `require_role` | require_role(…) — rol explícito | `app/threats/router.py` |
| GET | `/api/threats/feed` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/threats/router.py` |
| GET | `/api/threats/summary` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/threats/router.py` |
| GET | `/api/threats/top-senders` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/threats/router.py` |
| GET | `/api/tracking` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/tracking/router.py` |
| GET | `/api/tracking/search/{email}` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/tracking/router.py` |
| GET | `/api/voice-config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/voice_config/router.py` |
| PUT | `/api/voice-config` | `require_role` | require_role(…) — rol explícito | `app/voice_config/router.py` |
| POST | `/api/voice-config/test` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/voice_config/router.py` |
| GET | `/api/zap/actions` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/zap/router.py` |
| DELETE | `/api/zap/actions/simulados` | `require_role` | require_role(…) — rol explícito | `app/zap/router.py` |
| GET | `/api/zap/config` | `get_current_admin` | rol efectivo (viewer: solo GET) | `app/zap/router.py` |
| PUT | `/api/zap/config` | `require_role` | require_role(…) — rol explícito | `app/zap/router.py` |
| POST | `/api/zap/release/{action_id}` | `require_role` | require_role(…) — rol explícito | `app/zap/router.py` |
| POST | `/api/zap/scan` | `-` | **SIN PROTECCIÓN EXPLÍCITA** | `app/zap/router.py` |

Total: 246 rutas · sin protección explícita: **18** · solo rol efectivo: 131 · rol explícito: 97.
