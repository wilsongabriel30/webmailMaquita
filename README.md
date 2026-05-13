# Fundacion Maquita Webmail

<div align="center">

**Sistema de correo electronico completo con interfaz web tipo Microsoft Outlook.**
**Software libre para la inteligencia colectiva.**

Desarrollado por la **Fundacion Maquita** — Comercializadora asociativa sin fines de lucro, Ecuador.

![Fundacion Maquita Webmail](https://img.shields.io/badge/Fundaci%C3%B3n%20Maquita-Webmail-0078d4?style=for-the-badge)
![License](https://img.shields.io/badge/Licencia-MIT-green?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12+-blue?style=flat-square)
![React](https://img.shields.io/badge/React-19-61dafb?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-336791?style=flat-square)
![Dovecot](https://img.shields.io/badge/Dovecot-2.4-blue?style=flat-square)

</div>

---

## Por que Maquita Webmail?

Porque las organizaciones sin fines de lucro, cooperativas, escuelas, gobiernos locales y pequenas empresas merecen un sistema de correo profesional **sin depender de Google, Microsoft ni pagar licencias**.

Este es un webmail **completo, funcional y en produccion** — no un prototipo. Incluye todo lo que necesitas para operar tu propio servidor de correo con interfaz moderna.

**En produccion** en Fundacion Maquita con 48,000+ emails, 13 buzones, 380+ peticiones/hora.

---

## Caracteristicas principales

### Correo electronico
- Interfaz tipo Outlook con vista previa configurable
- Editor avanzado (TipTap) con tablas, imagenes, firmas HTML
- Hilos de conversacion y busqueda full-text (FTS Xapian)
- Etiquetas, reglas de correo (Sieve), posponer correos
- Descarga masiva de adjuntos, atajos de teclado, paleta de comandos (Ctrl+K)

### Calendario
- Vistas mes, semana, dia, agenda
- CalDAV con Radicale
- Invitaciones ICS estilo Outlook (Aceptar/Tentativo/Rechazar)

### Contactos
- CardDAV, importar/exportar vCard y CSV
- Categorias, favoritos, directorio global (GAL)
- Deteccion de duplicados, historial de interacciones

### Tareas
- Tableros Kanban con listas y tarjetas
- Recordatorios, recurrencia, emails como tareas

### Panel de administracion
- Dashboard con estadisticas en tiempo real
- Gestion de dominios, buzones y aliases
- Anti-spam con listas negras/grises gestionables
- eDiscovery (busqueda forense), auditoria, impersonacion
- Branding personalizable

### Seguridad
- JWT + 2FA/TOTP + rate limiting
- Cifrado en disco (mail_crypt), S/MIME
- SPF, DKIM, DMARC (reject), MTA-STS, DANE
- Sistema anti-spam interno con heuristicas avanzadas
- ClamAV antivirus

### Inteligencia Artificial (opcional)
- Respuestas inteligentes contextualizadas
- Autocompletado al redactar
- Dictado por voz (Whisper)
- Ejecutado localmente con Ollama (sin enviar datos a terceros)
- Soporte multi-GPU con failover automatico

### Extras
- PWA instalable (Progressive Web App)
- Migracion desde Zimbra incluida
- Compresion de emails (ahorra ~60% disco)
- Service Worker para cache de assets

---

## Stack tecnologico

| Componente | Tecnologia |
|------------|-----------|
| Frontend | React 19 + TypeScript + Vite 6 |
| Backend | FastAPI 0.115 + Uvicorn |
| Base de datos | PostgreSQL 17+ |
| Cache | Redis 7+ |
| SMTP | Postfix 3.7+ |
| IMAP | Dovecot 2.4+ |
| Antispam | Rspamd 3.8+ (reglas internas) |
| Antivirus | ClamAV 1.0+ |
| Proxy/TLS | Nginx 1.22+ + Let's Encrypt |
| CalDAV/CardDAV | Radicale 3.0+ |
| Busqueda | FTS Xapian |
| IA | Ollama + FastAPI Gateway |

---

## Inicio rapido

```bash
# Clonar
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd webmailMaquita

# Ver la guia de instalacion completa
cat docs/INSTALL.md
```

> **Guia completa paso a paso:** La instalacion esta documentada para personas con poca experiencia tecnica. Cada paso tiene explicaciones claras y comandos que puedes copiar y pegar.

---

## Documentacion

| Documento | Descripcion |
|-----------|-------------|
| [Instalacion](docs/INSTALL.md) | Guia paso a paso desde cero (17 pasos) |
| [Arquitectura](docs/ARCHITECTURE.md) | Estructura del proyecto, modulos, flujo de correos |
| [Seguridad](docs/SECURITY.md) | Medidas de hardening, anti-spam, cifrado |
| [Inteligencia Artificial](docs/AI.md) | Configurar IA local con Ollama |
| [Solucionar problemas](docs/TROUBLESHOOTING.md) | Errores comunes y comandos de diagnostico |
| [Changelog](CHANGELOG.md) | Historial de cambios |

---

## Estructura del proyecto

```
maquita-webmail/
├── backend/           # API FastAPI (auth, mail, admin, calendar, contacts, tasks, AI)
├── frontend/          # React + TypeScript (interfaz tipo Outlook)
├── scripts/           # Filtro anti-spam, mapas rspamd, configuracion
├── docs/              # Documentacion completa
├── deploy-webmail.sh  # Script de deploy seguro
├── zimbra-sync.sh     # Migracion desde Zimbra
└── CHANGELOG.md
```

> Ver [ARCHITECTURE.md](docs/ARCHITECTURE.md) para detalles de cada modulo.

---

## Screenshots

> *Proximamente: capturas de pantalla de la interfaz en produccion.*

<!-- 
Agregar screenshots de:
- Bandeja de entrada
- Composicion de correo
- Panel de administracion
- Calendario
- Tareas (Kanban)
- Vista movil
- Panel anti-spam
-->

---

## Contribuir

1. Fork del repositorio
2. Crear rama: `git checkout -b mi-mejora`
3. Hacer cambios y commit
4. Push: `git push origin mi-mejora`
5. Crear Pull Request

---

## Licencia

**MIT** — Software libre. Usalo, modificalo y compartelo libremente.

Al usar este software, por favor menciona a la Fundacion Maquita como creadores originales.

---

## Uso etico y atribucion

Este software fue creado por la **Fundacion Maquita**, una organizacion sin fines de lucro dedicada a la comercializacion asociativa en Ecuador. Lo compartimos con el mundo porque creemos que la tecnologia debe estar al servicio de todos.

**Al usar este software te pedimos:**

- Dar credito a la Fundacion Maquita como creadores originales
- No utilizar este software para actividades ilegales, spam masivo, phishing o cualquier actividad que perjudique a otros
- Si detectas un uso indebido de esta herramienta, reportalo creando un issue en este repositorio

> *Si eres una organizacion sin fines de lucro, cooperativa, escuela o gobierno local y necesitas ayuda con la instalacion, no dudes en contactarnos.*

---

<div align="center">

**Fundacion Maquita** — Ecuador

*"Tecnologia al servicio de todos, no solo de quienes pueden pagarla."*

</div>
