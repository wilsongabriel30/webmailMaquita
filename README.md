# Maquita Webmail

[![CI](https://img.shields.io/github/actions/workflow/status/fundacion-maquita/maquita-webmail/ci.yml?branch=main&label=CI)](https://github.com/fundacion-maquita/maquita-webmail/actions)
[![Security Scan](https://img.shields.io/github/actions/workflow/status/fundacion-maquita/maquita-webmail/security.yml?branch=main&label=security%20scan)](https://github.com/fundacion-maquita/maquita-webmail/actions)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/fundacion-maquita/maquita-webmail/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/fundacion-maquita/maquita-webmail)](https://github.com/fundacion-maquita/maquita-webmail/releases)

**Open-source mail compliance and eDiscovery layer with a full-featured webmail client for Postfix/Dovecot-based mail platforms.**

Built and maintained by [Fundacion Maquita](https://maquita.org), a non-profit organization in Ecuador.

---

## What Is This

Maquita Webmail is two things in one repository:

1. **A webmail client** -- a modern, Outlook-style interface for reading, composing, and managing email on top of an existing Postfix + Dovecot mail stack.

2. **A compliance and eDiscovery layer** -- forensic search, legal holds, audit trails, fraud detection, and cryptographically signed exports, designed for organizations that need to meet regulatory or internal governance requirements for email.

It does not replace your MTA or IMAP server. It sits alongside them, connecting to Postfix, Dovecot, Rspamd, and PostgreSQL to provide a unified interface for end users and compliance officers.

## What Problem It Solves

Small and mid-size organizations running self-hosted Postfix/Dovecot have few options for:

- A usable webmail interface that goes beyond Roundcube
- eDiscovery and legal hold without purchasing enterprise software
- Unified audit trails that correlate events across Postfix, Rspamd, Dovecot, and user actions
- Mail compliance tooling that works with open-source mail infrastructure

Maquita Webmail addresses all four.

## Who It Is For

- Organizations already running (or willing to run) Postfix + Dovecot
- IT teams that need compliance and audit capabilities without vendor lock-in
- Non-profits, universities, and government agencies with self-hosted mail
- Teams that want a modern webmail UI on top of standard mail protocols

## What This Is NOT

- **Not a hosted email service.** You must operate your own mail infrastructure or be willing to set one up.
- **Not a drop-in replacement for Microsoft 365 or Google Workspace.** It does not include spreadsheets, video conferencing, or a full office suite. It is a webmail and compliance tool.
- **Not battle-tested at massive scale.** It is in production at Fundacion Maquita with 13 mailboxes and 48,000+ emails. It has not been tested with thousands of concurrent users.
- **Not a mail server.** It requires Postfix and Dovecot to be installed and configured separately (Docker Compose handles this for you in the default deployment).
- **Not feature-frozen.** The project is actively evolving. APIs and database schemas may change between releases.

## Current Status

**Production, early-stage open source.** Maquita Webmail has been running in production at Fundacion Maquita since 2024. The codebase is being prepared for broader community adoption. Expect rough edges, ongoing refactoring, and breaking changes until a 1.0 release.

- 380 tracked files
- 150+ API endpoints
- 77 PostgreSQL tables
- 39 auditable event types

## Architecture

```
                          +-------------------+
                          |     Nginx         |
                          | (TLS termination) |
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
           |  compliance data |     |  Sieve               |
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

           +------------------+     +----------------------+
           |    Radicale      |     |  Ollama (optional)   |
           |  CalDAV/CardDAV  |     |  smart replies, AI   |
           |  calendar/contacts|    |  autocomplete,       |
           +------------------+     |  Whisper dictation   |
                                    +----------------------+
```

## Key Features

### Webmail
- Outlook-style UI with folders, threads, and labels
- Rich text editor (TipTap) with inline images and attachments
- Full-text search powered by Dovecot Xapian
- Server-side Sieve rule management
- Calendar (CalDAV via Radicale)
- Contacts (CardDAV via Radicale)
- Kanban-style task boards
- Two-factor authentication (TOTP)
- Mail encryption at rest (Dovecot mail_crypt)

### Compliance and eDiscovery
- **Forensic search**: query across all mailboxes by date range, sender, recipient, keywords, attachments
- **Legal holds**: freeze mailboxes to prevent deletion during investigations
- **Export with integrity**: GPG-signed exports with RFC 3161 timestamp sealing
- **Audit trail**: 39 event types covering login, send, delete, admin actions, and more
- **Fraud detection**: pattern-based alerting on suspicious mail activity
- **Mail trace correlation**: unified view linking Postfix queue IDs to Rspamd scores to Dovecot delivery to user actions
- **RBAC**: 5 roles (superadmin, admin, compliance officer, auditor, user)

### Mail Security
- SPF, DKIM, DMARC validation and reporting
- MTA-STS and DANE/TLSA support
- Rspamd integration for spam scoring and filtering

### Optional AI Features
- Smart reply suggestions (Ollama, local inference)
- Compose autocomplete
- Voice dictation via Whisper
- All AI processing runs locally -- no data leaves your infrastructure

## Quick Start (Docker)

Prerequisites: Docker 24+, Docker Compose v2, GNU Make.

```bash
git clone https://github.com/fundacion-maquita/maquita-webmail.git
cd maquita-webmail
cp .env.example .env
docker compose up -d
make migrate
make seed-demo
make test
```

The webmail UI will be available at `https://localhost` (self-signed certificate by default). Demo credentials are printed by `make seed-demo`.

## Local Development Installation

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database and mail server settings
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### External Services

The backend expects running instances of PostgreSQL 17, Redis 7, Dovecot 2.4, and Postfix. For local development, `docker compose up postgres redis dovecot postfix` will start only the infrastructure services.

## Environment Variables

Copy `.env.example` to `.env` and review the following key variables:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://maquita:changeme@localhost:5432/maquita` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `IMAP_HOST` | Dovecot IMAP server | `localhost` |
| `SMTP_HOST` | Postfix SMTP server | `localhost` |
| `SECRET_KEY` | JWT signing key | (none, required) |
| `MAIL_DOMAIN` | Primary mail domain | `example.org` |
| `OLLAMA_URL` | Ollama API endpoint (optional) | `http://localhost:11434` |
| `RADICALE_URL` | Radicale CalDAV/CardDAV URL | `http://localhost:5232` |

See `.env.example` for the full list.

## Running Tests

```bash
# All tests
make test

# Backend only
make test-backend

# Frontend only
make test-frontend

# With coverage
make test-coverage
```

## Running Migrations

```bash
# Apply all pending migrations
make migrate

# Create a new migration
make migration-create name="description_of_change"

# Roll back the last migration
make migrate-rollback
```

## Generating Demo Data

```bash
# Seed the database with sample mailboxes, emails, and compliance data
make seed-demo

# Reset demo data (WARNING: deletes all data and re-seeds)
make seed-demo-reset
```

## Security and Compliance

- All authentication endpoints are rate-limited
- TOTP-based two-factor authentication
- RBAC with five distinct roles
- Audit log captures 39 event types with IP address, user agent, and timestamp
- eDiscovery exports are GPG-signed with optional RFC 3161 timestamping
- Mail at rest is encrypted via Dovecot mail_crypt plugin
- TLS enforced for all external connections (MTA-STS, DANE)
- Dependencies are scanned with `pip-audit` and `npm audit` in CI

To report a security vulnerability, please email security@maquita.org. Do not open a public issue.

## Documentation

Detailed documentation is available in the `docs/` directory:

- `docs/architecture.md` -- system design and component interaction
- `docs/deployment.md` -- production deployment guide
- `docs/compliance.md` -- eDiscovery and legal hold usage
- `docs/api.md` -- API reference
- `docs/contributing.md` -- development workflow and coding standards
- `docs/security.md` -- security model and threat mitigations

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features and milestones.

## Contributing

Contributions are welcome. Please read `docs/contributing.md` before submitting a pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Write tests for your changes
4. Ensure `make test` and `make lint` pass
5. Submit a pull request with a clear description of the change

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgments

Built by the technology team at [Fundacion Maquita](https://maquita.org), Quito, Ecuador.
