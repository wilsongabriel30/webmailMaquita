# A free alternative to cPanel

**English | [Español](ALTERNATIVA-CPANEL.md)**

Maquita turns a Debian server into a **complete hosting server**: email, websites, databases, DNS,
certificates and backups, with a **panel for whoever runs the server** and a **portal for each client**. It is
free software (AGPL-3.0), with no per-account or per-domain licences, and it runs on your own servers.

Built for organisations, cooperatives, local governments and small providers who want to stop paying for
foreign panels and clouds without losing features.

---

## Two panels, as in cPanel/WHM

| | General panel (port 8443) | Client portal (port 8444) |
|---|---|---|
| **For** | The server administrator (like WHM) | Each organisation or client (like cPanel) |
| **Scope** | The whole server | Only their domains, within their quotas |
| **Security** | Double authentication and second factor | Second factor; unprivileged: every action goes through a broker that re-checks the session and the domain |

## Features

✅ available · ⏳ coming (version shown)

### Files

| Feature | Status |
|---|---|
| Web file manager (upload, download, move, copy, zip, unzip, permissions, 30-day trash) | ✅ |
| FTP/SFTP accounts: one per site plus extra accounts jailed in a subfolder | ✅ |
| Disk usage per site, databases and backups, with per-domain quotas | ✅ |
| Password-protected directories | ✅ |
| Backups: clients create, download and restore their site and databases | ✅ |
| Git deployment | ✅ custom apps · ⏳ PHP sites (v1.11) |

### Domains and DNS

| Feature | Status |
|---|---|
| Domains, subdomains and domain aliases | ✅ (aliases from the portal: ⏳ v1.11) |
| 301/302 redirects for a path or a whole domain | ✅ |
| DNS zone editor (own DNS server), with mail records protected | ✅ |
| Dynamic DNS | ⏳ v1.11 |

### Email

| Feature | Status |
|---|---|
| Accounts, Outlook-like webmail, forwarders and autoresponders | ✅ |
| Filters (Sieve) and learning spam filter (Rspamd) | ✅ |
| SPF, DKIM, DMARC and MTA-STS | ✅ |
| Mailing lists and distribution groups | ✅ |
| Phones over ActiveSync 16.1 (mail, calendar, contacts, drafts and organisation address book) | ✅ |
| Import accounts from a CSV file | ✅ general panel and portal ([guide, in Spanish](IMPORTAR-CSV-Y-ENRUTAMIENTO.md)) |
| Email routing (backup MX, relay to another server) | ✅ general panel ([guide, in Spanish](IMPORTAR-CSV-Y-ENRUTAMIENTO.md)) |

### Databases

| Feature | Status |
|---|---|
| MariaDB and PostgreSQL, with a wizard | ✅ |
| phpMyAdmin and Adminer with one-click sign-in | ✅ |
| Database users with custom privileges | ✅ ([guide, in Spanish](BASES-WAF-CLAVES.md)) |
| Remote database access (by IP, with TLS) | ✅ ([guide, in Spanish](BASES-WAF-CLAVES.md)) |

### Security

| Feature | Status |
|---|---|
| Automatic Let's Encrypt certificates and renewal | ✅ |
| IP blocking for the server (firewall, fail2ban, countries) and per site | ✅ |
| Hotlink protection | ✅ |
| Brute-force protection and two-factor authentication | ✅ |
| Web application firewall (OWASP rules) | ✅ full OWASP CRS per site: mode, paranoia level, rule exclusions and blocked requests ([guide, in Spanish](BASES-WAF-CLAVES.md)) |
| SSH keys and API tokens | ✅ ([guide, in Spanish](BASES-WAF-CLAVES.md)) |

### Software

| Feature | Status |
|---|---|
| PHP version per site and its settings | ✅ |
| App catalogue (WordPress, Joomla, Drupal, Moodle and more) | ✅ |
| WordPress: install, one-click login, update core, plugins, themes and language | ✅ |
| Scheduled tasks (cron) | ✅ |
| Custom error pages (403, 404, 500, 502, 503) | ✅ |
| gzip/brotli compression and caching, tuned for rural and satellite links | ✅ |
| Node.js and Python apps | ✅ general panel · ⏳ portal (v1.11) |
| Migration from another host (package and .sql dump) | ✅ |
| Visual page builder | Later phase: free alternative (GrapesJS); Sitejet is proprietary and out of scope |

### Metrics and monitoring

| Feature | Status |
|---|---|
| Visitor and bandwidth statistics (GoAccess, no browser tracking) | ✅ |
| Site and PHP error/access log viewer | ✅ |
| Site-down email alerts (checked every 5 minutes, with certificate days left) | ✅ |
| CPU and memory per site | ⏳ v1.11 |
| Server information in the portal | ⏳ v1.11 |

## What cPanel does not include

- **Outlook-like webmail** with Microsoft 365 E5-level security: DLP, eDiscovery, legal hold, anti-impersonation.
- **Chat, calendar, tasks and Drive** (Almacén) on the same server.
- **Own DNS server** and automatic certificates for every mail and site name.
- **Signed updates**: each server only installs releases signed by the project, from the panel or automatically every night.
- **Sites for slow links**: compression and caching on by default for rural DSL and satellite.
- **No per-account cost**: the price does not grow with each domain, mailbox or site.

## Installation

On a clean Debian 13 (or Debian 12 / Ubuntu 22.04+), as root:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd webmailMaquita
sudo bash deploy/webmail/instalar.sh                     # mail, webmail and general panel
sudo bash deploy/webmail/instalar-app.sh sitios          # websites, databases and apps
sudo bash deploy/webmail/instalar-app.sh dns             # own DNS server
sudo bash deploy/webmail/instalar-app.sh portal-dominio  # client portal (port 8444)
sudo bash deploy/webmail/instalar-app.sh actualizar      # signed updates
```

Other optional sections: `activesync`, `cortafuegos` (firewall), `identidad`, `respaldos` (backups), `chat`,
`bi`, `pdf`, `onlyoffice`. The full guide is in [INSTALL-NATIVE.md](INSTALL-NATIVE.md); the interface and
documentation are in Spanish.

**Indicative requirements:** 4 cores, 8 GB RAM and 80 GB disk for a medium-sized organisation with its
sites; a public IP with port 25 open to receive email.

## Releases and roadmap

Release notes are in [Releases](https://github.com/wilsongabriel30/webmailMaquita/releases) and
[CHANGELOG.md](../CHANGELOG.md); what comes next is in [ROADMAP.md](../ROADMAP.md).
