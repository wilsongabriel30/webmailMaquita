# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [1.0.1] - 2026-05-13

Tag: `compliance-audit`

### Added

- **Compliance module** with full eDiscovery workflow (search, preserve, collect, export)
- **Legal holds** with immutable message preservation and custodian management
- **Audit trail** capturing all user and admin actions with actor, timestamp, IP, and context
- **Fraud detection** engine with rule-based scoring and configurable thresholds
- **GPG signing** for eDiscovery exports and compliance evidence packages
- **RBAC granular enforcement** for compliance operations (viewer, analyst, officer, admin)
- **Mail trace correlation** linking messages across Postfix, Dovecot, and Rspamd logs by message-id

### Changed

- Updated Dovecot integration for 2.4 compatibility (doveadm protocol changes, socket paths)
- RBAC enforcement refactored to granular per-endpoint permission checks
- Improved error messages for compliance API endpoints

### Fixed

- Date parsing in mail search now handles RFC 2822, ISO 8601, and epoch timestamps correctly
- Size parsing for mailbox quota and search filters (KB/MB/GB units)
- Doveadm permission errors when running as non-root service user
- Race condition in concurrent legal hold activation for the same custodian

### Security

- Fail-fast validation for `ADMIN_JWT_SECRET` on startup (refuses to start with weak or default values)
- Sanitized secret values from error responses and log output
- Added `hardening.conf` systemd drop-in with `NoNewPrivileges`, `ProtectSystem=strict`, `MemoryDenyWriteExecute`
- Restricted doveadm socket permissions to application service user only

## [1.0.0] - 2026-04-12

### Added

- Full webmail interface: inbox, compose, reply, forward, drafts
- Threaded conversation view with message grouping
- Label/folder management with drag-and-drop
- Full-text email search with filters (date, sender, has:attachment)
- Calendar module with CalDAV support via Radicale 3.0
- Contacts management with vCard import/export
- Tasks module with due dates and priority levels
- Admin panel for user, domain, and alias management
- Anti-spam integration with Rspamd (spam score display, learn ham/spam)
- Antivirus scanning with ClamAV on inbound and outbound mail
- Two-factor authentication (TOTP) with QR code enrollment
- Dovecot `mail_crypt` plugin for encryption at rest
- Nginx reverse proxy configuration with security headers
- CI/CD pipeline: lint, test, build, deploy
- Docker Compose development environment
- Database migration system (`migrations/*.sql`)
- API documentation via OpenAPI/Swagger

## [0.9.0] - 2026-03-23

### Added

- Initial release of Maquita Webmail
- Zimbra-to-Dovecot mailbox migration tooling
- Basic webmail interface (read, compose, delete)
- IMAP integration with Dovecot
- SMTP submission via Postfix
- PostgreSQL-backed user and domain management
- Session-based authentication
- Basic admin interface

[Unreleased]: https://github.com/maquita/maquita-webmail/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/maquita/maquita-webmail/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/maquita/maquita-webmail/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/maquita/maquita-webmail/releases/tag/v0.9.0
