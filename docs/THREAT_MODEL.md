# Threat Model

This document describes the threat model for Maquita Webmail, covering key threats, mitigations, and residual risks.

## Trust Boundaries

```
                            INTERNET
                               |
              +----------------+----------------+
              |          NGINX (TLS)            |
              |         (trust boundary)        |
              +------+------------------+-------+
                     |                  |
              +------+------+   +------+------+
              |  Frontend   |   |   Backend   |
              |  (static)   |   |  (FastAPI)  |
              +-------------+   +------+------+
                                       |
                     +---------+-------+---------+
                     |         |                 |
              +------+--+  +--+------+  +-------+------+
              |PostgreSQL|  |  Redis  |  | Mail Stack   |
              |  (data)  |  |(session)|  | Postfix      |
              +----------+  +---------+  | Dovecot      |
                                         | Rspamd       |
                                         | ClamAV       |
                                         +------+-------+
                                                |
                                         +------+-------+
                                         | Mail Storage |
                                         | /var/vmail   |
                                         +--------------+
```

**Trust boundaries:**

1. **Internet to Nginx** -- untrusted network traffic enters the system
2. **Nginx to Backend** -- reverse proxy validates TLS, forwards to application
3. **Backend to Database/Redis** -- application accesses data stores on localhost
4. **Backend to Mail Stack** -- application issues commands to Dovecot/Postfix via sockets
5. **Mail Stack to Storage** -- Dovecot reads/writes maildir on filesystem

## Data Flow: Compliance Operations

```
  Admin/Officer                    Backend                      Dovecot
       |                             |                            |
       |-- POST /api/compliance/ --> |                            |
       |   (JWT + RBAC check)        |                            |
       |                             |-- doveadm search --------> |
       |                             |<-- message list ---------- |
       |                             |-- doveadm fetch ---------> |
       |                             |<-- message content ------- |
       |                             |                            |
       |                             |-- INSERT audit_log ------> PostgreSQL
       |                             |-- GPG sign export -------> |
       |                             |                            |
       |<-- export package --------- |                            |
       |   (signed, checksummed)     |                            |
```

## Threat Catalog

### T1: Unauthorized Mailbox Access

**Description:** An attacker gains access to another user's mailbox through session hijacking, credential theft, or authentication bypass.

**Mitigations:**
- Session tokens stored in Redis with configurable TTL
- TOTP-based two-factor authentication
- Rate limiting on authentication endpoints
- Session invalidation on password change
- `HttpOnly`, `Secure`, `SameSite=Strict` cookie attributes
- Failed login attempt logging and alerting

**Residual risk:** Medium. A compromised TOTP device combined with a phished password could still grant access. Mitigated by session monitoring and anomaly detection (planned).

---

### T2: Email Impersonation / Spoofing

**Description:** An attacker sends email appearing to originate from the organization's domain.

**Mitigations:**
- SPF record with `-all` policy
- DKIM signing via Rspamd for all outbound mail
- DMARC policy set to `reject`
- MTA-STS enforcing TLS for inbound connections
- DANE/TLSA records for transport security

**Residual risk:** Low. Properly configured SPF/DKIM/DMARC prevents domain spoofing. Display-name spoofing remains possible but is a client-side issue.

---

### T3: Unauthorized eDiscovery Export

**Description:** A user with partial access exports mailbox data they are not authorized to access, exfiltrating sensitive communications.

**Mitigations:**
- RBAC enforcement: only `compliance_officer` and `compliance_admin` roles can initiate exports
- All export operations recorded in the audit trail with actor, scope, timestamp, and IP
- GPG-signed export packages with SHA-256 checksums for integrity verification
- Export directory permissions restricted to the application service user
- Rate limiting on export endpoints

**Residual risk:** Medium. A compromised compliance officer account could export data within their authorized scope. Mitigated by audit trail review and separation of duties.

---

### T4: Evidence Tampering

**Description:** An attacker modifies or deletes compliance evidence (audit logs, exported data, legal hold records) to cover tracks or undermine legal proceedings.

**Mitigations:**
- Audit log entries are append-only (no UPDATE/DELETE grants on `audit_log` table)
- GPG signatures on all export packages
- SHA-256 checksums for exported files
- Legal hold records are immutable once activated (soft-delete only, with audit entry)
- Database backups with integrity verification

**Residual risk:** Medium. A database administrator with direct PostgreSQL access could theoretically modify records. Mitigated by backup comparison and external log forwarding (planned via Wazuh).

---

### T5: Email Deletion Under Legal Hold

**Description:** A user or automated process deletes emails that are subject to a legal hold, destroying potentially relevant evidence.

**Mitigations:**
- Legal hold flag prevents message deletion at the Dovecot level
- Backend enforces hold status check before any delete operation
- Held messages are excluded from automated retention/purge policies
- Audit trail records all deletion attempts (including blocked ones)

**Residual risk:** Low. Direct filesystem access to `/var/vmail` could bypass application controls. Mitigated by filesystem permissions and integrity monitoring (planned).

---

### T6: Secret Leakage

**Description:** Secrets (JWT keys, database passwords, API keys) are exposed through logs, error messages, source code, or environment dumps.

**Mitigations:**
- Fail-fast validation on startup: refuses to run with default or weak `ADMIN_JWT_SECRET`
- Secret values sanitized from all log output and error responses
- `.env` file permissions restricted to `600` (owner read/write only)
- `gitleaks` runs in CI to prevent secrets from entering the repository
- Secrets never passed as command-line arguments (visible in `/proc`)

**Residual risk:** Low. Memory dumps or core files could theoretically contain secrets. Mitigated by disabling core dumps in production (`MemoryDenyWriteExecute` in systemd).

---

### T7: Log Manipulation

**Description:** An attacker with system access modifies or deletes application or system logs to hide malicious activity.

**Mitigations:**
- Application logs forwarded to syslog (configurable)
- Systemd journal captures stdout/stderr with tamper-evident storage
- Audit trail stored in PostgreSQL (separate from file-based logs)
- Log rotation preserves historical data with configurable retention

**Residual risk:** High. A root-level attacker can modify any local log. Mitigated by forwarding logs to an external, append-only system (Wazuh/OpenSearch integration planned in v1.3).

---

### T8: Admin Role Abuse

**Description:** An administrator uses elevated privileges to access mailboxes, modify compliance data, or grant unauthorized access without oversight.

**Mitigations:**
- All admin actions recorded in audit trail (no silent operations)
- RBAC separates admin roles: `mail_admin`, `compliance_officer`, `compliance_admin`, `system_admin`
- Compliance operations require specific compliance roles (mail admins cannot access eDiscovery)
- Admin session activity visible in the admin panel

**Residual risk:** Medium. A `system_admin` with database access could bypass RBAC. Mitigated by audit trail review and planned separation of database credentials per role.

---

### T9: Doveadm Privilege Escalation

**Description:** The `doveadm` command-line tool runs with elevated privileges and can access any mailbox. Compromise of the doveadm socket or credentials grants full mailbox access.

**Mitigations:**
- Doveadm socket permissions restricted to the application service user
- Doveadm HTTP API protected with a strong password
- Backend validates authorization before issuing doveadm commands
- All doveadm operations logged in the audit trail
- Systemd hardening prevents the backend from escalating privileges (`NoNewPrivileges=yes`)

**Residual risk:** Medium. The application service user inherently has broad mailbox access via doveadm. Mitigated by audit logging and systemd sandboxing. A dedicated doveadm proxy with per-operation authorization is under consideration.

---

### T10: System Resource Exhaustion

**Description:** An attacker overwhelms the system through large attachments, rapid API calls, mail bombing, or search queries that consume excessive CPU/memory.

**Mitigations:**
- `MAX_UPLOAD_SIZE_MB` limits attachment size (default: 25 MB)
- API rate limiting per user per minute
- Postfix `message_size_limit` and `smtpd_recipient_limit`
- Rspamd rate limiting and greylisting for inbound mail
- Database connection pool limits (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`)
- Systemd resource controls (`MemoryMax`, `CPUQuota`) available

**Residual risk:** Low. Distributed attacks could still cause degradation. Mitigated by upstream firewall rules and monitoring alerts.

---

## Summary Matrix

| ID  | Threat                        | Severity | Likelihood | Residual Risk |
|-----|-------------------------------|----------|------------|---------------|
| T1  | Unauthorized mailbox access   | High     | Medium     | Medium        |
| T2  | Email impersonation           | High     | Low        | Low           |
| T3  | Unauthorized export           | High     | Low        | Medium        |
| T4  | Evidence tampering            | Critical | Low        | Medium        |
| T5  | Deletion under legal hold     | Critical | Low        | Low           |
| T6  | Secret leakage                | High     | Low        | Low           |
| T7  | Log manipulation              | Medium   | Medium     | High          |
| T8  | Admin role abuse              | High     | Low        | Medium        |
| T9  | Doveadm privilege escalation  | High     | Low        | Medium        |
| T10 | System resource exhaustion    | Medium   | Medium     | Low           |

## Review Schedule

This threat model should be reviewed:

- Before every major release (vX.0.0)
- After any security incident
- When new features introduce new trust boundaries or data flows
- At minimum, annually
