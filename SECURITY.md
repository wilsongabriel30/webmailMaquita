# Security Policy

> **Version:** 2.0
> **Last updated:** 2026-05-13
> **Maintainer:** Fundacion Maquita — Technology Team

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please report vulnerabilities via email:

- **Email:** security@maquita.org
- **Subject line:** `[SECURITY] Brief description`
- **PGP encryption:** Request our public key via the same email address

### What to Include

- Description of the vulnerability and potential impact
- Steps to reproduce (versions, configurations, payloads)
- Proof-of-concept code (non-destructive only)
- Your name and contact information (for credit, if desired)

### Response Timeline

| Stage | Target Time |
|-------|-------------|
| Acknowledgment of report | 48 hours |
| Initial triage and severity assessment | 5 business days |
| Status update to reporter | 10 business days |
| Patch for critical/high severity | 15 business days |
| Patch for medium/low severity | 30 business days |
| Coordinated public disclosure | 90 days after report, or upon patch release |

### Responsible Disclosure Terms

- We will not pursue legal action against researchers who follow this policy.
- Do not access, modify, or delete data belonging to other users.
- Do not degrade the availability of the service during testing.
- We will credit reporters in release notes unless anonymity is requested.

## Scope

### In Scope

- The webmail frontend application
- The backend API (FastAPI)
- Authentication and session management (JWT, 2FA/TOTP)
- Compliance module (eDiscovery, legal holds, audit trail)
- Email processing pipeline (Postfix, Dovecot, Rspamd integration)
- CalDAV/CardDAV integration (Radicale)
- Docker images and deployment configurations
- CI/CD workflows

### Out of Scope

- Third-party software bugs (report those upstream)
- Social engineering attacks
- Physical security of hosting infrastructure
- Denial-of-service attacks requiring significant bandwidth
- Issues in dependencies (report to the dependency maintainer)

## What NOT to Report via Public Issues

- Authentication bypasses or credential exposure
- Injection vulnerabilities (SQL, command, template)
- Privilege escalation paths
- Data exposure or exfiltration vectors
- Cryptographic weaknesses
- Any issue that could be exploited before a patch is available

These must go through the private reporting channel above.

## Security Architecture Overview

- **Authentication:** JWT tokens in HttpOnly/Secure/SameSite=Strict cookies + optional 2FA/TOTP
- **Authorization:** Role-based access control (RBAC) with 5 compliance roles
- **Encryption at rest:** Dovecot mail_crypt plugin (secp521r1)
- **Encryption in transit:** TLS 1.2+ on all connections
- **Email security:** SPF, DKIM, DMARC (reject), MTA-STS, DANE
- **Session storage:** Redis with Fernet-encrypted sensitive fields
- **Anti-spam:** Rspamd with custom scoring rules + ClamAV
- **Audit:** 39 audited events, append-only audit log
- **Evidence integrity:** GPG detached signatures + timestamp sealing
- **Systemd hardening:** ProtectSystem=strict, PrivateTmp, MemoryMax, TasksMax

## GitHub Security Features

We recommend enabling the following on your fork/deployment:

- **Secret scanning:** Detects committed credentials across full history
- **Dependabot:** Automated dependency update PRs
- **Code scanning:** CodeQL or similar SAST tool
- **Security advisories:** For coordinated vulnerability disclosure

## Known Limitations

See [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for a complete threat model including residual risks and system boundaries.

Key limitations:
- JWT refresh token rotation is not yet implemented
- AppArmor/SELinux profiles are not yet deployed
- The compliance module requires `sudo doveadm` access for eDiscovery operations
- HTML email sanitization relies on DOMPurify (ongoing arms race with bypass techniques)

---

*This policy follows guidelines from GitHub security policy documentation and OpenSSF Best Practices.*
