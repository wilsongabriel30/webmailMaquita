# Security Policy — Fundacion Maquita Webmail

> **Version:** 1.0  
> **Last updated:** 2026-05-12  
> **Maintainer:** Equipo de Tecnologia, Fundacion Maquita  
> **Status:** Self-hosted, pre-audit

This document describes the security posture of the Fundacion Maquita Webmail system. It is written to be honest about what has been implemented, what has not, and what risks remain. We follow the spirit of projects like [Mail-in-a-Box](https://mailinabox.email/) in being transparent about our threat model rather than claiming to be "secure" or "bulletproof."

---

## Table of Contents

1. [Vulnerability Disclosure Policy](#vulnerability-disclosure-policy)
2. [Threat Model](#threat-model)
3. [Security Architecture](#security-architecture)
4. [Known Limitations](#known-limitations)
5. [Hardening Guide](#hardening-guide)
6. [Dependency Security](#dependency-security)

---

## 1. Vulnerability Disclosure Policy

### How to Report

If you discover a security vulnerability in Fundacion Maquita Webmail, please report it responsibly:

- **Email:** Contactar al equipo de desarrollo via GitHub Issues (para vulnerabilidades, usar mensajes privados)
- **Subject line:** `[SECURITY] Brief description of the issue`
- **Encrypt reports** with our PGP key if available (request via the same address)

**Do NOT** open a public issue, post on social media, or disclose the vulnerability before coordinated resolution.

### What to Include

- Description of the vulnerability and its potential impact
- Steps to reproduce, including versions, configurations, and payloads
- Any proof-of-concept code (non-destructive only)
- Your name and contact information (for credit, if desired)

### Response Commitments

| Stage | Target Time |
|---|---|
| Acknowledgment of report | 48 hours |
| Initial triage and severity assessment | 5 business days |
| Status update to reporter | 10 business days |
| Patch for critical/high severity | 15 business days |
| Patch for medium/low severity | 30 business days |
| Public disclosure (coordinated) | 90 days after report, or upon patch release |

### Responsible Disclosure Terms

- We will not pursue legal action against researchers who follow this policy.
- We ask that you do not access, modify, or delete data belonging to other users.
- We ask that you do not degrade the availability of the service during testing.
- We will credit reporters in release notes unless anonymity is requested.

### Scope

**In scope:**
- The webmail frontend application
- The backend API (FastAPI)
- Authentication and session management
- Email processing pipeline (Postfix, Dovecot, Rspamd, custom filters)
- The IA gateway proxy
- CalDAV (Radicale) integration

**Out of scope:**
- Third-party services and upstream software bugs (report those upstream)
- Social engineering attacks against Maquita staff
- Physical security of the hosting infrastructure
- Denial-of-service attacks that require significant bandwidth

---

## 2. Threat Model

### Design Philosophy

This system is a self-hosted webmail platform for an organization. Like Mail-in-a-Box, we operate under the assumption that running your own mail server is inherently more complex than using a managed service, and that transparency about risks is more valuable than false assurances.

### Trust Boundaries

The system defines the following trust boundaries, each representing a point where data crosses from one trust level to another:

```
Internet (untrusted)
    |
    | TLS 1.2+ termination
    v
[Nginx] ── rate limiting, security headers, WAF-like rules
    |
    | localhost:8000 (HTTP, no TLS)
    v
[FastAPI Backend] ── JWT validation, input sanitization, CORS
    |
    |── localhost:993 (IMAP, authenticated) ──> [Dovecot]
    |── localhost:587 (SMTP, SASL auth) ──> [Postfix]
    |── localhost:5432 (password auth) ──> [PostgreSQL]
    |── localhost:6379 (password + Fernet) ──> [Redis]
    |── configurable URL (API key) ──> [IA Gateway / Ollama]
    |── localhost:5232 ──> [Radicale CalDAV]
    |
[Postfix]
    |── milter protocol ──> [Rspamd]
    |── pipe transport (vmail user) ──> [Python spam filter]
    |── ClamAV scanning
```

### Threat Categories Addressed

#### Account Takeover (Brute Force, Credential Stuffing, Session Hijacking)

**Measures implemented:**
- Rate limiting at Nginx level (per-IP request throttling)
- Fail2Ban monitoring of authentication failures (backend and Dovecot)
- JWT tokens stored in HttpOnly, Secure, SameSite=Strict cookies
- Optional 2FA/TOTP for all accounts
- Password hashing with modern algorithms (bcrypt/argon2)
- Session data in Redis with Fernet-encrypted sensitive fields

**Residual risk:** JWT refresh token rotation is not yet implemented, meaning a stolen refresh token remains valid until expiration.

#### Email Spoofing and Phishing

**Measures implemented:**
- SPF records published and enforced
- DKIM signing of all outbound mail
- DMARC policy set to `reject`
- MTA-STS policy published and enforced
- DANE/TLSA records for opportunistic verification
- Rspamd scoring of inbound mail with custom rules

**Residual risk:** Inbound spoofing protection depends on sender domains having correct SPF/DKIM/DMARC. Many legitimate senders still lack these.

#### Cross-Site Scripting (XSS) via HTML Emails

**Measures implemented:**
- HTML email content is sanitized before rendering in the frontend
- React 19 escapes output by default; `dangerouslySetInnerHTML` usage is limited and wrapped with DOMPurify
- Content-Security-Policy headers restrict inline scripts and external resources
- Image proxying to prevent tracking pixels and external resource loading

**Residual risk:** HTML email sanitization is an ongoing arms race. Novel bypass techniques emerge regularly.

#### Server-Side Request Forgery (SSRF) via IA Gateway

**Measures implemented:**
- The IA gateway is a dedicated FastAPI proxy with a configurable, allowlisted target URL
- Requests to the IA gateway require API key authentication
- The gateway does not follow redirects
- Internal network addresses (RFC 1918, loopback, link-local) are blocked at the gateway level

**Residual risk:** If the Ollama instance is compromised or misconfigured, it could be used as a pivot point. The gateway URL is configurable by administrators.

#### Privilege Escalation

**Measures implemented:**
- Services run as dedicated unprivileged users: `vmail`, `www-data`, `_rspamd`, `clamav`, `redis`, `postgres`
- The Python spam filter runs as `vmail` via Postfix pipe transport, not as root
- Backend (Uvicorn) runs as `www-data` behind Nginx
- Systemd service files use `NoNewPrivileges=true` where applicable
- PostgreSQL connections use per-service credentials with minimal grants

**Residual risk:** AppArmor/SELinux profiles are not yet deployed. A vulnerability in any service could potentially escalate within that user's permissions.

#### Data Exfiltration

**Measures implemented:**
- Mail storage encrypted at rest with `mail_crypt` plugin (secp521r1 curve)
- S/MIME support for end-to-end encrypted mail
- TLS enforced on all connections (internal and external)
- Database credentials stored in environment variables or restricted config files
- Redis stores only session metadata; sensitive values are Fernet-encrypted

**Residual risk:** An attacker with `vmail` or `www-data` shell access could read decrypted mail in memory or access the encryption keys.

#### Spam and Outbound SMTP Abuse

**Measures implemented:**
- Rspamd with internal scoring rules and Bayes classifier
- Custom Python filter for organization-specific spam patterns
- ClamAV scanning of all inbound and outbound mail
- Outbound rate limiting per authenticated user
- DKIM/SPF/DMARC on outbound ensures mail integrity

**Residual risk:** A compromised user account can send spam until rate limits are hit or the account is suspended.

#### MIME Parsing Vulnerabilities

**Measures implemented:**
- Python `email` stdlib used for MIME parsing (well-tested, maintained upstream)
- Attachment size limits enforced at Postfix and backend levels
- ClamAV scans attachments for known malware signatures

**Residual risk:** The custom Python spam filter uses regex-based rules on untrusted MIME content, which is susceptible to catastrophic backtracking (ReDoS). See [Known Limitations](#known-limitations).

#### Prompt Injection via IA

**Measures implemented:**
- IA features are optional and disabled by default
- The IA gateway proxies to a local Ollama instance (no data sent to external APIs)
- User input sent to the LLM is clearly delimited from system prompts
- IA responses are treated as untrusted and sanitized before display

**Residual risk:** Prompt injection is an unsolved problem in the industry. Malicious email content processed by the IA could influence its output.

#### Denial of Service / Resource Exhaustion

**Measures implemented:**
- Nginx rate limiting (requests per second, concurrent connections)
- Postfix connection rate limits and message size limits
- Uvicorn worker limits and request timeouts
- PostgreSQL connection pooling
- Redis maxmemory configuration with eviction policy

**Residual risk:** Application-level DoS (e.g., expensive database queries triggered by crafted requests) has not been systematically tested.

### What Is NOT Covered

This threat model does **not** address:

- **Nation-state adversaries** with the ability to compromise hosting infrastructure or intercept traffic at the network level
- **Physical access** to the server hardware
- **Supply-chain attacks** on upstream package repositories (Debian, PyPI, npm)
- **Zero-day vulnerabilities** in core dependencies (Linux kernel, OpenSSL, Python runtime)
- **Insider threats** from users with legitimate administrative access
- **Side-channel attacks** (timing, power analysis, etc.)

### Accepted Risks

- Running a self-hosted mail server inherently increases attack surface compared to using a managed service. We accept this tradeoff for data sovereignty and organizational independence.
- The IA gateway introduces a novel attack surface (prompt injection). We accept this because the feature is optional and runs locally.
- Email is an inherently insecure protocol at the transport level. We mitigate but cannot eliminate risks from non-compliant remote mail servers.

---

## 3. Security Architecture

### Defense in Depth

The system implements multiple layers of defense. No single layer is relied upon exclusively.

```
Layer 1: Network Perimeter
├── Firewall (iptables/nftables): only ports 25, 443, 465, 587, 993 exposed
├── Fail2Ban: automatic IP banning on repeated failures
└── DDoS mitigation: connection rate limiting at firewall level

Layer 2: TLS and Transport
├── Nginx: TLS 1.2+ only, strong cipher suites, HSTS, OCSP stapling
├── Postfix: opportunistic TLS for SMTP, mandatory TLS for submission
├── Dovecot: TLS required for IMAP
└── MTA-STS + DANE: enforced encrypted transport to supporting servers

Layer 3: Application Gateway (Nginx)
├── Rate limiting (per-IP, per-endpoint)
├── Security headers: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
├── Request size limits
├── Static file serving (no backend for assets)
└── Proxy to backend on localhost only

Layer 4: Application (FastAPI Backend)
├── JWT authentication with HttpOnly cookies
├── TOTP-based 2FA (optional per user)
├── Input validation (Pydantic models)
├── CORS restricted to webmail origin
├── CSRF protection via SameSite cookies
└── Parameterized database queries (SQLAlchemy ORM)

Layer 5: Data Storage
├── PostgreSQL: password auth, minimal grants, localhost only
├── Redis: password auth, Fernet encryption for sensitive values, localhost only
├── Dovecot mail_crypt: per-user encryption (secp521r1)
├── S/MIME: optional end-to-end encryption
└── Filesystem permissions: strict ownership per service user

Layer 6: Email Pipeline
├── Rspamd: spam scoring, DKIM verification, ARC
├── ClamAV: malware scanning
├── Custom Python filter: organization-specific rules
├── SPF/DKIM/DMARC: outbound signing, inbound verification
└── Postfix restrictions: HELO checks, sender verification, relay controls
```

### Authentication Flow

```
User → [Nginx] → POST /api/auth/login
                      │
                      ├── Validate credentials against PostgreSQL
                      ├── Check 2FA/TOTP if enabled
                      ├── Generate JWT (access + refresh tokens)
                      ├── Store session metadata in Redis (Fernet-encrypted)
                      └── Set HttpOnly, Secure, SameSite=Strict cookies
                            │
                            └── Subsequent requests: JWT validated on every API call
```

### Network Segmentation

All backend services (PostgreSQL, Redis, Dovecot, Postfix, Rspamd, ClamAV, Radicale, Ollama) listen exclusively on `127.0.0.1` or Unix sockets. Only Nginx is exposed to the network.

---

## 4. Known Limitations

We believe in honesty over marketing. The following limitations are known and documented:

| Limitation | Risk Level | Mitigation Plan |
|---|---|---|
| No external security audit performed | High | Budget allocation planned; community review welcomed |
| No formal penetration testing | High | Internal testing performed; external pentest planned |
| AppArmor/SELinux profiles not implemented | Medium | Profiles in development; systemd sandboxing used as interim |
| JWT refresh token rotation not implemented | Medium | Refresh tokens have expiration; rotation planned for next release |
| No automated secret scanning in CI | Medium | Manual review process in place; tool integration planned |
| Python spam filter vulnerable to ReDoS | Medium | Regex patterns under review; timeout wrapper planned |
| No Web Application Firewall (WAF) | Low-Medium | Nginx rules provide basic protection; ModSecurity evaluation in progress |
| IA prompt injection not fully mitigated | Low | Feature is optional; output is sanitized; no autonomous actions |
| No SIEM or centralized log analysis | Low | Logs collected via journald; ELK/Loki stack under evaluation |

---

## 5. Hardening Guide

### 5.1 Fail2Ban Configuration

Install and configure Fail2Ban to automatically ban IPs that exhibit malicious behavior.

```bash
apt install fail2ban -y
```

#### Webmail Backend Jail

Create `/etc/fail2ban/jail.d/maquita-webmail.conf`:

```ini
[maquita-webmail]
enabled  = true
port     = https
filter   = maquita-webmail
logpath  = /var/log/maquita-webmail/access.log
maxretry = 5
findtime = 300
bantime  = 3600
action   = iptables-multiport[name=maquita-webmail, port="https"]
```

Create the filter at `/etc/fail2ban/filter.d/maquita-webmail.conf`:

```ini
[Definition]
failregex = ^<HOST> .* "POST /api/auth/login HTTP/.*" 401
            ^<HOST> .* "POST /api/auth/login HTTP/.*" 429
ignoreregex =
```

#### Dovecot Jail

```ini
[dovecot]
enabled  = true
port     = imaps
filter   = dovecot
logpath  = /var/log/mail.log
maxretry = 5
findtime = 300
bantime  = 3600
```

#### Postfix Jail

```ini
[postfix-sasl]
enabled  = true
port     = smtp,submissions,submission
filter   = postfix[mode=auth]
logpath  = /var/log/mail.log
maxretry = 3
findtime = 300
bantime  = 7200
```

#### Recidive Jail (repeat offenders)

```ini
[recidive]
enabled  = true
logpath  = /var/log/fail2ban.log
banaction = iptables-allports
bantime  = 604800
findtime = 86400
maxretry = 3
```

### 5.2 AppArmor Profiles (Planned)

Although full AppArmor profiles are not yet deployed, the following is the recommended structure for when they are implemented:

```
/etc/apparmor.d/
├── usr.sbin.dovecot
├── usr.sbin.postfix
├── usr.bin.rspamd
├── usr.bin.clamd
├── maquita-webmail-backend
└── maquita-webmail-ia-gateway
```

Example profile skeleton for the backend (`/etc/apparmor.d/maquita-webmail-backend`):

```apparmor
#include <tunables/global>

/opt/maquita-webmail/backend/venv/bin/uvicorn {
  #include <abstractions/base>
  #include <abstractions/nameservice>
  #include <abstractions/python>

  # Read application code
  /opt/maquita-webmail/backend/** r,

  # Write logs
  /var/log/maquita-webmail/** rw,

  # Network: localhost only for backend services
  network inet stream,
  network inet6 stream,

  # Deny direct access to mail storage
  deny /var/mail/** rwlx,

  # Deny write to system directories
  deny /etc/** w,
  deny /usr/** w,
}
```

### 5.3 Systemd Sandboxing

Apply the following directives to all Maquita Webmail systemd service files to reduce the blast radius of a compromise.

For the backend service (`/etc/systemd/system/maquita-webmail.service`):

```ini
[Service]
# User isolation
User=www-data
Group=www-data
DynamicUser=no

# Filesystem restrictions
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/log/maquita-webmail /opt/maquita-webmail/data
PrivateTmp=yes
NoNewPrivileges=yes

# Capability restrictions
CapabilityBoundingSet=
AmbientCapabilities=

# Network namespace (allow only necessary)
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
IPAddressAllow=127.0.0.0/8 ::1/128

# System call filtering
SystemCallFilter=@system-service
SystemCallArchitectures=native

# Misc hardening
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
MemoryDenyWriteExecute=yes
RemoveIPC=yes
PrivateDevices=yes
```

For the IA gateway service, add additionally:

```ini
# Restrict network to only Ollama endpoint
IPAddressAllow=127.0.0.0/8
IPAddressDeny=any
```

Verify sandboxing effectiveness:

```bash
systemd-analyze security maquita-webmail.service
```

Aim for a score of 4.0 or lower (on a 0-10 scale where lower is more secure).

### 5.4 Firewall Rules (nftables)

```nft
#!/usr/sbin/nft -f

flush ruleset

table inet filter {
    set fail2ban-blacklist {
        type ipv4_addr
        flags timeout
    }

    chain input {
        type filter hook input priority 0; policy drop;

        # Drop blacklisted IPs
        ip saddr @fail2ban-blacklist drop

        # Allow established connections
        ct state established,related accept

        # Allow loopback
        iif lo accept

        # Allow SSH (restricted to admin IPs)
        tcp dport 22 ip saddr { TU_RED_INTERNA/24 } accept

        # Allow mail services
        tcp dport { 25, 465, 587 } accept   # SMTP
        tcp dport 993 accept                  # IMAPS

        # Allow HTTPS (webmail)
        tcp dport 443 accept

        # Allow ICMP (ping)
        ip protocol icmp accept
        ip6 nexthdr icmpv6 accept

        # Log and drop everything else
        log prefix "[nftables-drop] " drop
    }

    chain forward {
        type filter hook forward priority 0; policy drop;
    }

    chain output {
        type filter hook output priority 0; policy accept;
    }
}
```

**Important:** Port 80 (HTTP) should only be open if needed for ACME/Let's Encrypt challenges. Otherwise, redirect to 443 at the Nginx level and keep it closed at the firewall.

### 5.5 Additional Hardening Recommendations

- **SSH:** Disable password authentication; use key-based auth only. Disable root login.
- **Automatic updates:** Enable `unattended-upgrades` for security patches.
- **Log rotation:** Ensure all service logs rotate properly to prevent disk exhaustion.
- **Monitoring:** Set up basic monitoring (e.g., `monit`, `node_exporter` + Prometheus) for service health and resource usage.
- **Backup encryption:** Encrypt backups before storing offsite. Test restoration regularly.
- **DNS CAA records:** Publish CAA records to restrict which CAs can issue certificates for your domain.

---

## 6. Dependency Security

### Frontend (React 19 + TypeScript)

```bash
# Audit npm dependencies for known vulnerabilities
npm audit

# Review outdated packages
npm outdated

# Use only pinned versions in package-lock.json
# Regenerate lockfile periodically:
rm -rf node_modules package-lock.json && npm install

# Check for licenses that may be problematic
npx license-checker --summary
```

### Backend (Python 3.12 + FastAPI)

```bash
# Audit Python dependencies
pip-audit

# Check for known vulnerabilities
safety check -r requirements.txt

# Review outdated packages
pip list --outdated

# Pin all dependencies with hashes for integrity verification
pip-compile --generate-hashes requirements.in -o requirements.txt

# Scan for common security issues in Python code
bandit -r /opt/maquita-webmail/backend/ -ll
```

### System Packages

```bash
# Check for available security updates
apt list --upgradable 2>/dev/null | grep -i security

# Review installed packages for CVEs
apt install debian-goodies
checkrestart

# Subscribe to Debian Security Advisories:
# https://www.debian.org/security/
```

### Container/Service Isolation Audit

```bash
# Verify service users and permissions
ps aux | grep -E '(dovecot|postfix|rspamd|clamav|uvicorn|redis|postgres)'

# Check for world-readable sensitive files
find /opt/maquita-webmail -type f -perm -004 -name "*.env" -o -name "*.key" -o -name "*.pem"

# Verify no services are listening on 0.0.0.0 that should be localhost
ss -tlnp | grep -v '127.0.0.1\|::1\|\[::1\]'
```

### Recommended Audit Schedule

| Task | Frequency |
|---|---|
| `npm audit` / `pip-audit` | Weekly (automated) |
| `apt list --upgradable` | Daily (automated via unattended-upgrades) |
| Review Fail2Ban logs | Weekly |
| Review authentication failure logs | Weekly |
| Full dependency version review | Monthly |
| Backup restoration test | Monthly |
| Firewall rule review | Quarterly |
| Systemd security score review | Quarterly |
| Rspamd rule effectiveness review | Quarterly |
| Full security posture review | Biannually |

---

## Changelog

| Date | Version | Description |
|---|---|---|
| 2026-05-12 | 1.0 | Initial security policy document |

---

*Fundacion Maquita — Tecnologia al servicio de todos, no solo de quienes pueden pagarla.*
