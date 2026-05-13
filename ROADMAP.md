# Roadmap

This document outlines the development roadmap for Maquita Webmail. Status labels indicate progress:

- **DONE** -- Completed and released
- **IN PROGRESS** -- Actively being developed
- **PLANNED** -- Approved and scheduled for development
- **PROPOSED** -- Under consideration, not yet committed

---

## v1.0.x -- Compliance and eDiscovery Core `DONE`

The foundation release with full compliance capabilities.

- Full webmail: inbox, compose, threads, labels, search
- Calendar (CalDAV via Radicale), contacts, tasks
- Admin panel with RBAC
- Anti-spam (Rspamd), antivirus (ClamAV)
- Two-factor authentication (TOTP)
- Dovecot mail_crypt encryption at rest
- **eDiscovery module**: search, preserve, collect, export
- **Legal holds**: immutable preservation with audit trail
- **Compliance audit trail**: all actions logged with actor, timestamp, and context
- **Fraud detection**: rule-based email analysis with scoring
- **GPG signing**: cryptographic integrity for exports and evidence
- **RBAC enforcement**: granular role-based access for compliance operations
- **Mail trace correlation**: end-to-end message tracking across MTA/MDA/MUA
- CI/CD pipeline with gitleaks, SBOM generation

## v1.1 -- Scalable Full-Text Indexing `PLANNED`

High-performance search across large mailboxes and compliance data.

- Integrate Apache Solr or Manticore Search for full-text indexing
- Index email bodies, headers, and attachment text
- Support complex query syntax (boolean operators, date ranges, field-specific search)
- Real-time index updates via LMTP hook
- Search result highlighting and relevance scoring
- Compliance-aware search: respect legal holds and retention policies

## v1.2 -- Advanced Attachment Extraction `PLANNED`

Deep content extraction from common document formats.

- PDF text extraction (with OCR fallback via Tesseract)
- DOCX/XLSX/PPTX content parsing
- Archive inspection (ZIP, TAR, 7z) with nested extraction
- Image metadata extraction (EXIF)
- Content indexing for full-text search integration
- Malware scanning of extracted content
- File type validation beyond MIME sniffing

## v1.3 -- Wazuh and OpenSearch Integration `PROPOSED`

Security monitoring and centralized log analysis.

- Wazuh agent deployment and configuration
- OpenSearch as log backend for mail, auth, and compliance events
- Pre-built alert rules for suspicious mail activity
- Integration with compliance audit trail
- Dashboards for security posture overview
- File integrity monitoring for mail storage and configuration

## v1.4 -- SIEM Dashboards `PROPOSED`

Operational and security dashboards for administrators.

- Grafana dashboards for mail flow metrics
- Authentication event visualization (success, failure, geographic)
- Compliance module activity dashboard
- Alert management and escalation workflows
- Anomaly detection for mailbox access patterns
- Report generation (PDF/CSV) for compliance audits

## v1.5 -- Multi-Tenant and Multi-Domain `PROPOSED`

Support for hosting multiple organizations on a single instance.

- Domain-level isolation for mailboxes, settings, and compliance data
- Per-tenant admin roles and RBAC policies
- Tenant-specific branding and configuration
- Resource quotas per tenant (storage, users, rate limits)
- Shared infrastructure with data isolation guarantees
- Tenant provisioning API and admin UI
- Cross-tenant compliance operations (for parent organizations)

## v2.0 -- Stable Production Architecture `PROPOSED`

The first long-term support release with architectural maturity.

- Horizontal scaling: stateless backend behind load balancer
- Database read replicas and connection pooling (PgBouncer)
- Redis Sentinel or Cluster for HA caching
- Queue-based async processing (Celery or equivalent)
- Zero-downtime deployment strategy (blue-green or rolling)
- Comprehensive API versioning (v1 stable, v2 preview)
- Performance benchmarks and SLA targets
- Long-term support commitment (security patches for 2+ years)
- Complete OpenAPI specification with SDK generation
- Plugin/extension system for custom compliance rules

---

## Contributing to the Roadmap

Community input is welcome. To propose a feature:

1. Open a GitHub issue with the `roadmap` label
2. Describe the use case and expected behavior
3. The maintainers will review and assign a milestone if accepted

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
