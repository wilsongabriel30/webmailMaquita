# Maquita Webmail

[![CI](https://img.shields.io/github/actions/workflow/status/wilsongabriel30/webmailMaquita/ci.yml?branch=main&label=CI)](https://github.com/wilsongabriel30/webmailMaquita/actions)
[![Security Scan](https://img.shields.io/github/actions/workflow/status/wilsongabriel30/webmailMaquita/security-scan.yml?branch=main&label=security%20scan)](https://github.com/wilsongabriel30/webmailMaquita/actions)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/wilsongabriel30/webmailMaquita/actions)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/wilsongabriel30/webmailMaquita)](https://github.com/wilsongabriel30/webmailMaquita/releases)

**🌐 English | [Español](README.md)**

**A full-featured webmail client with a legal compliance and eDiscovery layer, for Postfix/Dovecot-based mail platforms.**

Built and maintained by [Fundación Maquita](https://maquita.org), a non-profit organization in Ecuador.

---

## What is this

Maquita Webmail is two things in a single repository:

1. **A webmail client** — a modern, Outlook-style interface to read, compose and manage email on top of an existing Postfix + Dovecot mail platform.

2. **A compliance and eDiscovery layer** — forensic search, legal holds, audit trails, fraud detection and cryptographically signed exports, designed for organizations that must meet regulatory or internal governance requirements for email.

It does not replace your MTA or IMAP server. It runs **alongside them**, connecting to Postfix, Dovecot, Rspamd and PostgreSQL to offer a unified interface for users and compliance officers.

> **The platform.** The webmail ships with a **self-hosted Drive (Almacén) and its apps** —documents, forms and more— plus everyday collaboration (chat, calendar, tasks), all on your own servers. See **[The Maquita suite](docs/SUITE-MAQUITA.md)** — what each part is, what it does and what it is for. *(In Spanish.)*

## Philosophy: native, robust, reproducible

The whole system runs **natively, directly on the operating system** (Debian 13 or similar): webmail, Postfix, Dovecot, PostgreSQL, Redis and SOGo. **It does not rely on Docker.** It is designed to be **reproducible and installable by anyone** on their own Debian server — even by students — with a single script.

> **Docker is used only for Z-Push** (ActiveSync: syncing mail, calendar and contacts with mobile phones). It is an **optional**, isolated component — see [`deploy/z-push/`](deploy/z-push/). Mail and webmail are **never** run in containers.

## What problem it solves

Small and mid-sized organizations running Postfix/Dovecot on their own have few options for:

- A usable webmail interface that goes beyond Roundcube
- eDiscovery and legal hold without buying enterprise software
- Unified audit trails that correlate events across Postfix, Rspamd, Dovecot and user actions
- Mail-compliance tooling that works with open-source infrastructure

Maquita Webmail solves all four.

## Who it is for

- Organizations already running (or willing to run) Postfix + Dovecot
- IT teams that need compliance and audit capabilities without vendor lock-in
- NGOs, universities and public agencies with self-hosted email
- Teams that want a modern webmail interface over standard mail protocols

## What it is NOT

- **It is not a hosted email service.** You must run your own mail infrastructure or be willing to set it up.
- **It is not a device-management or telephony platform.** This repository covers email, **Drive**, **online office (OnlyOffice)**, **dashboards/BI** and **PDF editing** —all installable with a single script—; what it does not include is endpoint/mobile management (EDR/MDM) or telephony. There, the big enterprise suites are still broader.
- **It is not battle-tested at massive scale.** It runs in production at Fundación Maquita with nearly 300 mailboxes and 100,000+ emails. It has not been tested with thousands of concurrent users.
- **It is not a mail server.** It requires Postfix and Dovecot to be installed and configured (the native installer sets them up for you).
- **It is not feature-frozen.** The project evolves actively. APIs and database schemas may change between versions.

## Current status

**Production, early-stage open source.** Maquita Webmail has been in production at Fundación Maquita since 2024. The code is being prepared for broader community adoption. Expect rough edges, ongoing refactoring and breaking changes until a 1.0 release.

- 1000+ tracked files
- 850+ API endpoints
- 170+ PostgreSQL tables
- 39 auditable event types
- Nearly 300 mailboxes and 100,000+ emails in production

## How it compares

On **free software and your own servers**, this repository delivers the **email security and compliance** capabilities that commercial suites reserve for their **top plan** (equivalent to Microsoft 365 **E5**): Safe Attachments/Links, ZAP, DLP, anti-impersonation, eDiscovery with custodians and legal hold, insider risk, communication compliance, MFA and conditional access.

**Where it goes beyond that plan:**

- **Full data sovereignty** — data never leaves your servers; the AI assistant runs locally.
- **No per-user license** — cost does not grow with each mailbox.
- **Open source, installable with a single script** by anyone.
- **DLP with national ID and tax ID** — local data types, not generic ones.
- **Suite in the same repo** — email + Drive + online office (OnlyOffice) + dashboards/BI + PDF editor, integrated.

**Where the big suites are still ahead (honestly):** endpoint/device management (EDR/MDM), telephony, tens-of-thousands-of-users scale, and the depth of their detection engines trained on global telemetry.

## Screenshots

<table>
<tr>
<td><b>Calendar — month view</b></td>
<td><b>Event editor</b></td>
</tr>
<tr>
<td><img src="docs/screenshots/calendar-month.png" width="450" alt="Calendar month view with events"></td>
<td><img src="docs/screenshots/calendar-event-editor.png" width="450" alt="Event editor with attendees, reminders and rich text"></td>
</tr>
<tr>
<td><b>Event invitation email</b></td>
<td></td>
</tr>
<tr>
<td><img src="docs/screenshots/calendar-invitation.png" width="450" alt="Calendar with invitation email received by an attendee"></td>
<td></td>
</tr>
</table>

## Architecture

```
                          +-------------------+
                          |     Nginx         |
                          |  (TLS termination)|
                          +--------+----------+
                                   |
                    +--------------+--------------+
                    |                             |
           +-------v--------+          +---------v---------+
           |  React 19 SPA  |          |   FastAPI 0.115   |
           |  TypeScript    |          |   Python 3.12+    |
           |  Vite          |          |   150+ endpoints  |
           +----------------+          +----+----+----+----+
                                            |    |    |
                    +-----------------------+    |    +------------------+
                    |                            |                      |
           +--------v---------+     +-----------v----------+   +-------v--------+
           |  PostgreSQL 17   |     |      Dovecot 2.4     |   |    Redis 7     |
           |  77 tables       |     |  IMAP / mail_crypt   |   |  cache/queue   |
           |  audit trail     |     |  Xapian FTS          |   +----------------+
           |  compliance      |     |  Sieve               |
           +------------------+     +----------+-----------+
                                               |
                                    +----------v-----------+
                                    |      Postfix         |
                                    |  SPF/DKIM/DMARC      |
                                    |  MTA-STS / DANE      |
                                    +----------+-----------+
                                               |
                                    +----------v-----------+
                                    |      Rspamd          |
                                    |  anti-spam / scoring |
                                    +----------------------+

  Optional components:
  - SOGo: calendar and contacts (CalDAV/CardDAV)        -> native
  - Ollama: local AI-assisted replies/composition        -> native
  - Z-Push: ActiveSync (mobile sync)                      -> Docker (deploy/z-push)
```

## Key features

### Webmail
- Outlook-style interface with folders, threads and labels
- Rich-text editor (TipTap) with inline images and attachments
- Full-text search with Dovecot Xapian
- Server-side Sieve rule management
- Calendar (CalDAV via SOGo)
- Contacts (CardDAV via SOGo)
- Kanban-style task boards
- Two-factor authentication (TOTP), with optional enforcement by date
- Automatic app updates (service worker): users get improvements without a manual reload
- Outbox with send retry
- Encryption of mail at rest (Dovecot mail_crypt)

### Compliance and eDiscovery
- **Forensic search**: query across all mailboxes by date range, sender, recipient, keywords and attachments
- **Legal holds**: freeze mailboxes to prevent deletion during investigations
- **Tamper-evident export**: GPG-signed exports with RFC 3161 timestamping
- **Audit trail**: 39 event types (login, send, delete, admin actions and more)
- **Fraud detection**: pattern-based alerts on suspicious activity
- **Mail trace correlation**: unified view linking Postfix queue IDs to Rspamd scores, Dovecot delivery and user actions
- **RBAC**: 5 roles (superadmin, admin, compliance officer, auditor, user)

### Mail security
- SPF, DKIM, DMARC validation and reporting
- MTA-STS and DANE/TLSA support
- Rspamd integration for spam scoring and filtering
- **Targeted anti-impersonation**: blocks external mail spoofing institutional brands or internal roles (accounting, HR, IT, management) in the display name; managed from the panel
- **Outbound DLP** (national ID, tax ID, IBAN, card): scans outgoing mail and attachments, reinforced via milter so it also applies to Outlook and mobile
- **Sensitivity labels** (Public/Internal/Confidential/Restricted): mark the message and block external delivery for the two highest
- **Audited administrative mailbox access**: support opens a mailbox on request, logging who, what, when and from which IP
- Compromised-account protection: automatic bulk-send detection with containment and alerting

### AI features (optional)
- Smart reply suggestions (Ollama, local inference)
- Compose autocomplete
- Voice dictation via Whisper
- All AI processing runs locally — no data leaves your infrastructure

---

## Installation (native — recommended)

Designed so **anyone** can reproduce it on a clean Debian 13 (or similar).

### Option A — Automated installer (easiest)

```bash
# On a freshly installed Debian, git may not be present:
sudo apt update && sudo apt install -y git
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd webmailMaquita
sudo bash deploy/webmail/instalar.sh
```

The installer (as root, on Debian 12/13 or Ubuntu 22.04+):

1. Installs the base packages (PostgreSQL, Redis, Postfix, Dovecot, nginx, rspamd, Python, Node 20).
2. Creates the database, the `vmail` user and the secrets.
3. Builds the frontend and configures the backend (systemd + uvicorn).
4. Starts the services and prints the **generated credentials**.

**First login (no DNS needed yet):** the installer creates a test mailbox and a panel
administrator, both with a **known generic password** so you can get in right away:

| Access | URL | User | Password |
|---|---|---|---|
| Webmail | `https://yourdomain/webmail/` | `demo@ejemplo.local` | `Cambiar2026` |
| Advanced panel | `https://yourdomain:8443` | `admin` | `Cambiar2026` |

> ⚠️ **`Cambiar2026` is generic and public (it's in this README). CHANGE IT as soon as
> you log in**, on both. The demo mailbox uses a fake domain (`ejemplo.local`) on
> purpose, so you can test the login even before DNS is configured.

**Note: the `:8443` panel asks for the password TWICE** (by design — two security
layers). With the installer, both are `Cambiar2026`:

1. First a **browser popup** (nginx basic auth) → user `admin`, password `Cambiar2026`.
2. Then the **panel login screen** → user `admin`, password `Cambiar2026`.

To change them: the **panel** password is changed from within the panel itself; the
**browser** one is regenerated on the server with
`htpasswd /etc/nginx/.htpasswd_admin admin` (or `openssl passwd -apr1`).

When it finishes, it shows the final steps (DNS, SSL certificate with `certbot`,
creating the first mailbox) and **generates your DKIM key**. The detailed install
guide is in **[docs/INSTALL-NATIVE.md](docs/INSTALL-NATIVE.md)** (in Spanish).

> **Never configured DNS before?** The DNS part (A, MX, SPF, DKIM, DMARC and PTR
> records) is essential to send/receive without landing in spam. It is explained
> **step by step for beginners** in **[docs/CONFIGURAR-DNS.md](docs/CONFIGURAR-DNS.md)**
> (in Spanish) — covering web panel, VPS provider and your own DNS server (BIND/PowerDNS).

### Option B — Manual, step by step

If you prefer to understand or adapt each component, follow the full guide:
**[docs/INSTALL-NATIVE.md](docs/INSTALL-NATIVE.md)** (PostgreSQL, Dovecot with virtual
users + master user, Postfix, backend, frontend, nginx + TLS).

### Reference stack (production-tested)

| Component | Version | Role |
|---|---|---|
| Debian | 12 / 13 | Base OS |
| PostgreSQL | 17 | Mail accounts + app data |
| Dovecot | 2.4 | IMAP/POP3, ManageSieve, master user |
| Postfix | 3.10 | SMTP MTA, LMTP delivery to Dovecot |
| Redis | 7 / 8 | Sessions and caches |
| Python | 3.12+ | Backend (FastAPI / uvicorn) |
| Node | 20 | Frontend build (Vite) |
| nginx | 1.24+ | TLS reverse proxy |

## Administration panel

The webmail includes a **built-in administration panel** (nothing extra to install).
The installer marks the `demo@yourdomain` mailbox as an **administrator**; log in with
it to access advanced functions:

- Manage **domains, mailboxes and aliases** (create, edit, enable/disable, unlock)
- **Auditing** (39 event types) and **eDiscovery / legal hold**
- **Mail queues** and traces (Postfix ↔ Rspamd ↔ Dovecot ↔ user actions)
- **Anti-spam** (domain block/grey lists), per-domain **disclaimers**
- **Security**: account unlocking, approved forwards, RBAC (5 roles)

**Make another user an administrator** (the user must have a mailbox in `mailbox`):

```sql
INSERT INTO admin(username, superadmin, active)
VALUES ('user@yourdomain.com', true, true)
ON CONFLICT (username) DO UPDATE SET superadmin = true, active = true;
```

Panel access is granted by checking the `admin` table; you log in with the normal
mailbox (there is no separate admin password).

### Advanced panel (port 8443)

In addition to the built-in panel, the installer sets up a separate **advanced
administration panel** at `https://yourdomain:8443` (the `admin-panel/` folder) with
enterprise-grade functions:

- **Autoresponder** (out-of-office / vacation)
- **Bulk corporate signatures** per domain
- **Shared mailboxes** and delegation
- **Rspamd UI** (quarantine, spam training)
- **Firewall** and DNS checks
- Mail queue, recovery and branding

It is protected with two credentials (nginx basic auth + the panel's own login); the
installer generates both and shows them when it finishes.

## Mobile sync (Z-Push / ActiveSync) — optional

The **only** component that uses Docker. It lets you sync mail, calendar and contacts
with phones (Android/iOS) via Exchange ActiveSync. It is optional:

```bash
cd deploy/z-push
cat README.md      # configuration instructions
bash instalar.sh
```

## Cloud files and online office (Almacén / Maquita Drive) — built in

The system ships **Almacén** ("Maquita Drive"), a self-hosted Drive (no Nextcloud
required) with folders, link sharing, trash, versions, content search, auditing and
built-in **forms** (Google Forms style). It bundles **OnlyOffice** to edit
Word/Excel/PowerPoint documents in the browser. See the `almacen/` folder and its
own README/docs.

> The former Nextcloud integration is discontinued.

## Upgrading to a new version

When we publish improvements, update like this (on the server, in `/opt/maquita-webmail`):

```bash
git pull
# Rebuild the frontends from source (do NOT edit the dist folder by hand)
cd frontend            && npm ci && npx vite build && cd ..
cd admin-panel/frontend && npm ci && npx vite build && cd ../..
# Reinstall backend deps if they changed and restart the services
cd backend && ./venv/bin/pip install -r requirements.txt && cd ..
cd admin-panel/backend && ./venv/bin/pip install -r requirements.txt && cd ../..
# Apply the schema in case there are new tables (idempotent)
for f in migrations/*.sql; do sudo -u postgres psql -d maildb -f "$f"; done
systemctl restart maquita-webmail maquita-admin
```

> ⚠️ **Never edit the compiled files in `dist/` directly.** The build uses
> **SRI (Subresource Integrity)**: `index.html` carries a hash of each `.js`. If you
> modify a compiled `.js`, the hash no longer matches and the browser shows a
> **blank page** with `Failed to find a valid digest in the integrity attribute`.
> Always change the **source** (`src/`) and **rebuild** with `vite build` — the hash
> is recomputed automatically.

## Environment variables

Copy `.env.example` to `.env` and review it. The variables map 1:1 to
`backend/app/config.py`. The main ones:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://mailserver:CHANGE_ME@postgres:5432/maildb` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `SECRET_KEY` | JWT signing key (required) | (none) |
| `ADMIN_JWT_SECRET` | Admin JWT key (required) | (none) |
| `MASTER_PASSWORD` | Dovecot master user password | (none) |
| `IMAP_HOST` / `SMTP_HOST` | Dovecot / Postfix | `127.0.0.1` |
| `MAIL_DOMAIN` | Primary mail domain | `example.com` |
| `OLLAMA_URL` | Ollama endpoint (AI, optional) | `http://127.0.0.1:11434` |

Full list in `.env.example`.

## Running tests

```bash
make test        # backend tests (pytest)
make lint        # ruff + eslint
```

## Migrations

```bash
make migrate     # apply all SQL migrations against DATABASE_URL
```

## Demo data

```bash
# With the backend virtualenv active:
make seed-demo   # loads sample mailboxes, emails and compliance data
```

## Security and compliance

- All authentication endpoints are rate-limited
- TOTP-based two-factor authentication
- RBAC with five distinct roles
- The audit log captures 39 event types with IP, user agent and timestamp
- eDiscovery exports are GPG-signed with optional RFC 3161 timestamping
- Mail at rest is encrypted with the Dovecot mail_crypt plugin
- TLS enforced on all external connections (MTA-STS, DANE)
- Dependencies are scanned with `pip-audit` and `npm audit` in CI

To report a security vulnerability, email security@maquita.org. Do not open a public issue.

## Documentation

Detailed documentation in the `docs/` directory (currently in Spanish):

- [`docs/SUITE-MAQUITA.md`](docs/SUITE-MAQUITA.md) — **the full Maquita suite**: what each component is (mail, collaboration, management, data and AI) and what it is for *(in Spanish)*
- `docs/INSTALL-NATIVE.md` — native install guide (recommended)
- `docs/CONFIGURAR-DNS.md` — DNS/domain step by step (A, MX, SPF, DKIM, DMARC, PTR) for beginners
- `docs/ENTREGABILIDAD.md` — how to reach 10/10 deliverability and avoid spam (MTA-STS, TLS-RPT, DANE, BIMI, blocklists)
- `docs/ARCHITECTURE.md` — system design and component interaction
- `docs/DEPLOYMENT.md` — production deployment guide
- `docs/COMPLIANCE.md` — eDiscovery and legal hold usage
- `docs/CONFIGURATION.md` — environment variables and configuration
- `CONTRIBUTING.md` — development workflow and coding standards
- `SECURITY.md` — security model and mitigations

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features and milestones.

## Contributing

Contributions are welcome. Read `CONTRIBUTING.md` before opening a pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Write tests for your changes
4. Make sure `make test` and `make lint` pass
5. Open a pull request with a clear description of the change

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0-or-later).

## Credits

Built by the technology team at [Fundación Maquita](https://maquita.org), Quito, Ecuador.
