# Maquita Webmail

[![CI](https://img.shields.io/github/actions/workflow/status/wilsongabriel30/webmailMaquita/ci.yml?branch=main&label=CI)](https://github.com/wilsongabriel30/webmailMaquita/actions)
[![Security Scan](https://img.shields.io/github/actions/workflow/status/wilsongabriel30/webmailMaquita/security-scan.yml?branch=main&label=security%20scan)](https://github.com/wilsongabriel30/webmailMaquita/actions)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/wilsongabriel30/webmailMaquita/actions)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/wilsongabriel30/webmailMaquita)](https://github.com/wilsongabriel30/webmailMaquita/releases)

**[English](README.en.md) | 🌐 Español**

**Cliente de correo web (webmail) completo, con capa de cumplimiento legal y eDiscovery, para plataformas de correo basadas en Postfix/Dovecot.**

Desarrollado y mantenido por [Fundación Maquita](https://maquita.org), organización sin fines de lucro de Ecuador.

---

## Qué es esto

Maquita Webmail son dos cosas en un mismo repositorio:

1. **Un cliente webmail** — una interfaz web moderna para leer, redactar y gestionar correo sobre una plataforma de correo Postfix + Dovecot existente.

2. **Una capa de cumplimiento y eDiscovery** — búsqueda forense, retenciones legales (legal holds), pistas de auditoría, detección de fraude y exportaciones firmadas criptográficamente, pensada para organizaciones que deben cumplir requisitos regulatorios o de gobierno interno sobre el correo.

No reemplaza tu MTA ni tu servidor IMAP. Funciona **junto a ellos**, conectándose a Postfix, Dovecot, Rspamd y PostgreSQL para ofrecer una interfaz unificada a usuarios y oficiales de cumplimiento.

## Filosofía: nativo, robusto, reproducible

Todo el sistema corre **de forma nativa, directo sobre el sistema operativo** (Debian 13 o similar): webmail, Postfix, Dovecot, PostgreSQL, Redis y SOGo. **No depende de Docker.** Está pensado para ser **reproducible e instalable por cualquiera** en su propio servidor Debian — incluso por estudiantes — con un solo script.

> **Docker se usa únicamente para Z-Push** (ActiveSync: sincronización de correo, calendario y contactos con teléfonos móviles). Es un componente **opcional** y aislado — ver [`deploy/z-push/`](deploy/z-push/). El correo y el webmail **nunca** se ejecutan en contenedores.

## Qué problema resuelve

Las organizaciones pequeñas y medianas que operan Postfix/Dovecot por su cuenta tienen pocas opciones para:

- Una interfaz webmail usable que vaya más allá de Roundcube
- eDiscovery y retención legal sin comprar software empresarial
- Pistas de auditoría unificadas que correlacionan eventos de Postfix, Rspamd, Dovecot y acciones de usuario
- Herramientas de cumplimiento de correo que funcionen con infraestructura de código abierto

Maquita Webmail resuelve las cuatro.

## Para quién es

- Organizaciones que ya operan (o están dispuestas a operar) Postfix + Dovecot
- Equipos de TI que necesitan capacidades de cumplimiento y auditoría sin dependencia de un proveedor
- ONG, universidades y entidades públicas con correo autoalojado
- Equipos que quieren una interfaz webmail moderna sobre protocolos de correo estándar

## Qué NO es

- **No es un servicio de correo alojado.** Debes operar tu propia infraestructura de correo o estar dispuesto a montarla.
- **No es un reemplazo directo de Microsoft 365 o Google Workspace.** No incluye hojas de cálculo, videoconferencia ni una suite ofimática completa. Es una herramienta de webmail y cumplimiento.
- **No está probado a escala masiva.** Está en producción en Fundación Maquita con más de 200 buzones y más de 100 000 correos. No se ha probado con miles de usuarios concurrentes.
- **No es un servidor de correo.** Requiere Postfix y Dovecot instalados y configurados (el instalador nativo los deja listos).
- **No está congelado en funciones.** El proyecto evoluciona activamente. Las APIs y los esquemas de base de datos pueden cambiar entre versiones.

## Estado actual

**Producción, código abierto en etapa temprana.** Maquita Webmail está en producción en Fundación Maquita desde 2024. El código se está preparando para una adopción comunitaria más amplia. Espera detalles ásperos, refactorización continua y cambios incompatibles hasta una versión 1.0.

- 380 archivos versionados
- Más de 150 endpoints de API
- 77 tablas en PostgreSQL
- 39 tipos de evento auditables

## Capturas de pantalla

<table>
<tr>
<td><b>Calendario — vista mensual</b></td>
<td><b>Editor de eventos</b></td>
</tr>
<tr>
<td><img src="docs/screenshots/calendar-month.png" width="450" alt="Vista mensual del calendario con eventos"></td>
<td><img src="docs/screenshots/calendar-event-editor.png" width="450" alt="Editor de eventos con invitados, recordatorios y texto enriquecido"></td>
</tr>
<tr>
<td><b>Correo de invitación a evento</b></td>
<td></td>
</tr>
<tr>
<td><img src="docs/screenshots/calendar-invitation.png" width="450" alt="Calendario con correo de invitación recibido por el invitado"></td>
<td></td>
</tr>
</table>

## Arquitectura

```
                          +-------------------+
                          |     Nginx         |
                          | (terminación TLS) |
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
           |  77 tablas       |     |  IMAP / mail_crypt   |   |  caché/cola    |
           |  auditoría       |     |  Xapian FTS          |   +----------------+
           |  cumplimiento    |     |  Sieve               |
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

  Componentes opcionales:
  - SOGo: calendario y contactos (CalDAV/CardDAV)         -> nativo
  - Ollama: respuestas/redacción asistidas por IA local   -> nativo
  - Z-Push: ActiveSync (sincronización con móviles)        -> Docker (deploy/z-push)
```

## Características principales

### Webmail
- Interfaz moderna con carpetas, conversaciones y etiquetas
- Editor de texto enriquecido (TipTap) con imágenes en línea y adjuntos
- Búsqueda de texto completo con Dovecot Xapian
- Gestión de reglas Sieve del lado del servidor
- Calendario (CalDAV vía SOGo)
- Contactos (CardDAV vía SOGo)
- Tableros de tareas estilo Kanban
- Autenticación de dos factores (TOTP)
- Cifrado del correo en reposo (Dovecot mail_crypt)

### Cumplimiento y eDiscovery
- **Búsqueda forense**: consulta sobre todos los buzones por rango de fechas, remitente, destinatario, palabras clave y adjuntos
- **Retenciones legales**: congela buzones para impedir el borrado durante investigaciones
- **Exportación con integridad**: exportaciones firmadas con GPG y sellado de tiempo RFC 3161
- **Pista de auditoría**: 39 tipos de evento (inicio de sesión, envío, borrado, acciones de administración y más)
- **Detección de fraude**: alertas basadas en patrones de actividad sospechosa
- **Correlación de trazas de correo**: vista unificada que enlaza IDs de cola de Postfix con puntajes de Rspamd, entrega de Dovecot y acciones de usuario
- **RBAC**: 5 roles (superadmin, administrador, oficial de cumplimiento, auditor, usuario)

### Seguridad del correo
- Validación y reportes de SPF, DKIM, DMARC
- Soporte de MTA-STS y DANE/TLSA
- Integración con Rspamd para puntaje y filtrado de spam

### Funciones de IA (opcionales)
- Sugerencias de respuesta inteligente (Ollama, inferencia local)
- Autocompletado al redactar
- Dictado por voz vía Whisper
- Todo el procesamiento de IA se ejecuta localmente — ningún dato sale de tu infraestructura

---

## Instalación (nativa — recomendada)

Pensada para que **cualquiera** la reproduzca en un Debian 13 limpio (o similar).

### Opción A — Instalador automático (lo más fácil)

```bash
# En un Debian recién instalado, git puede no venir incluido:
sudo apt update && sudo apt install -y git
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd webmailMaquita
sudo bash deploy/webmail/instalar.sh
```

El instalador (como root, en Debian 12/13 o Ubuntu 22.04+):

1. Instala los paquetes base (PostgreSQL, Redis, Postfix, Dovecot, nginx, rspamd, Python, Node 20).
2. Crea la base de datos, el usuario `vmail` y los secretos.
3. Compila el frontend y configura el backend (systemd + uvicorn).
4. Deja los servicios arrancados e imprime las **credenciales generadas**.

**Primer ingreso (sin necesidad de DNS todavía):** el instalador crea un buzón de
prueba y un administrador del panel, ambos con una **clave genérica conocida** para
que entres de inmediato:

| Acceso | URL | Usuario | Clave |
|---|---|---|---|
| Webmail | `https://tudominio/webmail/` | `demo@ejemplo.local` | `Cambiar2026` |
| Panel avanzado | `https://tudominio:8443` | `admin` | `Cambiar2026` |

> ⚠️ **`Cambiar2026` es genérica y pública (está en este README). CÁMBIALA apenas
> entres**, en ambos accesos. El buzón demo usa un dominio falso (`ejemplo.local`)
> a propósito, para que pruebes el login aunque todavía no tengas el DNS configurado.

**Ojo: el panel `:8443` pide la clave DOS veces** (es a propósito — doble capa de
seguridad). Con el instalador, ambas son `Cambiar2026`:

1. Primero un **popup del navegador** (autenticación básica de nginx) → usuario
   `admin`, clave `Cambiar2026`.
2. Después la **pantalla de login del panel** → usuario `admin`, clave `Cambiar2026`.

Para cambiarlas: la del **panel** se cambia desde dentro del propio panel; la del
**navegador** se regenera en el servidor con
`htpasswd /etc/nginx/.htpasswd_admin admin` (o `openssl passwd -apr1`).

Al terminar te indica los pasos finales (DNS, certificado SSL con `certbot`, crear el primer buzón) y **genera tu clave DKIM**. La guía detallada de instalación está en **[docs/INSTALL-NATIVE.md](docs/INSTALL-NATIVE.md)**.

> **¿Nunca configuraste un DNS?** La parte de DNS (registros A, MX, SPF, DKIM,
> DMARC y PTR) es imprescindible para enviar/recibir sin caer en spam. Está
> explicada **paso a paso para principiantes** en
> **[docs/CONFIGURAR-DNS.md](docs/CONFIGURAR-DNS.md)** — incluye los casos de
> panel web, proveedor de VPS y servidor DNS propio (BIND/PowerDNS).

### Opción B — Paso a paso manual

Si prefieres entender cada componente o adaptarlo, sigue la guía completa:
**[docs/INSTALL-NATIVE.md](docs/INSTALL-NATIVE.md)** (PostgreSQL, Dovecot con usuarios virtuales + usuario maestro, Postfix, backend, frontend, nginx + TLS).

### Stack de referencia (probado en producción)

| Componente | Versión | Rol |
|---|---|---|
| Debian | 12 / 13 | Sistema operativo base |
| PostgreSQL | 17 | Cuentas de correo + datos de la app |
| Dovecot | 2.4 | IMAP/POP3, ManageSieve, usuario maestro |
| Postfix | 3.10 | MTA SMTP, entrega LMTP a Dovecot |
| Redis | 7 / 8 | Sesiones y cachés |
| Python | 3.12+ | Backend (FastAPI / uvicorn) |
| Node | 20 | Compilación del frontend (Vite) |
| nginx | 1.24+ | Proxy inverso con TLS |

## Panel de administración

El webmail incluye un **panel de administración integrado** (no requiere instalar
nada aparte). El instalador deja el buzón `demo@tudominio` como **administrador**;
inicia sesión con él y tendrás acceso a funciones avanzadas:

- Gestión de **dominios, buzones y alias** (crear, editar, activar/desactivar, desbloquear)
- **Auditoría** (39 tipos de evento) y **eDiscovery / retención legal**
- **Colas de correo** y trazas (Postfix ↔ Rspamd ↔ Dovecot ↔ acciones de usuario)
- **Anti-spam** (listas negras/grises de dominios), **disclaimers** por dominio
- **Seguridad**: desbloqueo de cuentas, reenvíos aprobados, RBAC (5 roles)

**Hacer administrador a otro usuario** (el usuario debe tener buzón en `mailbox`):

```sql
INSERT INTO admin(username, superadmin, active)
VALUES ('correo@tudominio.com', true, true)
ON CONFLICT (username) DO UPDATE SET superadmin = true, active = true;
```

El acceso al panel se concede consultando la tabla `admin`; el inicio de sesión
se hace con el buzón normal (no hay una contraseña de admin aparte).

### Panel avanzado (puerto 8443)

Además del panel integrado, el instalador monta un **panel de administración
avanzado** e independiente en `https://tudominio:8443` (carpeta `admin-panel/`)
con funciones de nivel empresarial:

- **Autoresponder** (respuestas automáticas / vacaciones)
- **Firmas corporativas masivas** por dominio
- **Buzones compartidos** y delegación
- **Interfaz de Rspamd** (cuarentena, entrenamiento de spam)
- **Firewall** y verificación de DNS
- Cola de correo, recuperación y branding

Está protegido con doble credencial (auth básica de nginx + login propio del
panel); el instalador genera ambas y las muestra al terminar.

## Sincronización con móviles (Z-Push / ActiveSync) — opcional

El **único** componente que usa Docker. Permite sincronizar correo, calendario y
contactos con teléfonos (Android/iOS) vía Exchange ActiveSync. Es opcional:

```bash
cd deploy/z-push
cat README.md      # instrucciones de configuración
bash instalar.sh
```

## Nube de archivos y ofimática en línea (Nextcloud + OnlyOffice) — opcional

Opcionalmente puedes integrar **Nextcloud** (almacenamiento en la nube, archivos,
compartir, adjuntos grandes) y, dentro de él, **OnlyOffice** (editar documentos
Word/Excel/PowerPoint en el navegador). El webmail ya trae la integración vía las
variables `NC_*` y `ONLYOFFICE_*` del `.env`.

> Es una **recomendación opcional**; la guía de configuración paso a paso se
> añadirá más adelante. Resumen en [`docs/INSTALL-NATIVE.md`](docs/INSTALL-NATIVE.md)
> (sección "Componentes opcionales").

## Actualizar a una nueva versión

Cuando publiquemos mejoras, actualiza así (en el servidor, en `/opt/maquita-webmail`):

```bash
git pull
# Reconstruye los frontends desde el código fuente (NO edites la carpeta dist a mano)
cd frontend            && npm ci && npx vite build && cd ..
cd admin-panel/frontend && npm ci && npx vite build && cd ../..
# Reinstala dependencias del backend si cambiaron y reinicia los servicios
cd backend && ./venv/bin/pip install -r requirements.txt && cd ..
cd admin-panel/backend && ./venv/bin/pip install -r requirements.txt && cd ../..
# Aplica el esquema por si hay tablas nuevas (idempotente)
for f in migrations/*.sql; do sudo -u postgres psql -d maildb -f "$f"; done
systemctl restart maquita-webmail maquita-admin
```

> ⚠️ **Nunca edites los archivos ya compilados de `dist/` directamente.** El build
> usa **SRI (Subresource Integrity)**: el `index.html` lleva un hash de cada `.js`.
> Si modificas el `.js` compilado, el hash deja de cuadrar y el navegador muestra
> **pantalla en blanco** con `Failed to find a valid digest in the integrity
> attribute`. Cambia siempre el **código fuente** (`src/`) y **reconstruye** con
> `vite build` — así el hash se recalcula solo.

## Variables de entorno

Copia `.env.example` a `.env` y revísalo. Las variables coinciden 1:1 con
`backend/app/config.py`. Las principales:

| Variable | Descripción | Por defecto |
|---|---|---|
| `DATABASE_URL` | Cadena de conexión a PostgreSQL | `postgresql://mailserver:CHANGE_ME@postgres:5432/maildb` |
| `REDIS_URL` | Cadena de conexión a Redis | `redis://redis:6379/0` |
| `SECRET_KEY` | Clave de firma JWT (obligatoria) | (ninguna) |
| `ADMIN_JWT_SECRET` | Clave JWT de administración (obligatoria) | (ninguna) |
| `MASTER_PASSWORD` | Contraseña del usuario maestro de Dovecot | (ninguna) |
| `IMAP_HOST` / `SMTP_HOST` | Dovecot / Postfix | `127.0.0.1` |
| `MAIL_DOMAIN` | Dominio de correo principal | `example.com` |
| `OLLAMA_URL` | Endpoint de Ollama (IA, opcional) | `http://127.0.0.1:11434` |

Lista completa en `.env.example`.

## Ejecutar pruebas

```bash
make test        # pruebas del backend (pytest)
make lint        # ruff + eslint
```

## Migraciones

```bash
make migrate     # aplica todas las migraciones SQL contra DATABASE_URL
```

## Datos de demostración

```bash
# Con el entorno virtual del backend activo:
make seed-demo   # carga buzones, correos y datos de cumplimiento de ejemplo
```

## Seguridad y cumplimiento

- Todos los endpoints de autenticación tienen límite de tasa (rate limit)
- Autenticación de dos factores basada en TOTP
- RBAC con cinco roles distintos
- El registro de auditoría captura 39 tipos de evento con IP, agente de usuario y marca de tiempo
- Las exportaciones de eDiscovery se firman con GPG y sellado de tiempo RFC 3161 opcional
- El correo en reposo se cifra con el plugin mail_crypt de Dovecot
- TLS obligatorio en todas las conexiones externas (MTA-STS, DANE)
- Las dependencias se escanean con `pip-audit` y `npm audit` en CI
- **Respaldos cifrados** (GPG/AES-256) con script de respaldo diario y **prueba de restauración** verificable — ver [`docs/BACKUP-RESTAURACION.md`](docs/BACKUP-RESTAURACION.md)

Para reportar una vulnerabilidad de seguridad escribe a security@maquita.org. No abras un issue público. Consulta nuestra [política de seguridad](SECURITY.md) para el modelo de amenazas y las mitigaciones.

## Documentación

Documentación detallada en el directorio `docs/`:

- `docs/INSTALL-NATIVE.md` — guía de instalación nativa (recomendada)
- `docs/CONFIGURAR-DNS.md` — DNS/dominio paso a paso (A, MX, SPF, DKIM, DMARC, PTR) para principiantes
- `docs/ENTREGABILIDAD.md` — cómo llegar a 10/10 y no caer en spam (MTA-STS, TLS-RPT, DANE, BIMI, listas negras)
- `docs/BACKUP-RESTAURACION.md` — respaldos cifrados, respaldo diario automático y **prueba de restauración**
- `docs/ARCHITECTURE.md` — diseño del sistema e interacción de componentes
- `docs/DEPLOYMENT.md` — guía de despliegue en producción
- `docs/COMPLIANCE.md` — uso de eDiscovery y retención legal
- `docs/CONFIGURATION.md` — variables de entorno y configuración
- `CONTRIBUTING.md` — flujo de desarrollo y estándares de código
- [`SECURITY.md`](SECURITY.md) — modelo de seguridad y mitigaciones

## Hoja de ruta

Ver [ROADMAP.md](ROADMAP.md) para funciones y hitos planificados.

## Contribuir

Las contribuciones son bienvenidas. Lee `CONTRIBUTING.md` antes de enviar un pull request.

1. Haz un fork del repositorio
2. Crea una rama de función (`git checkout -b feature/tu-funcion`)
3. Escribe pruebas para tus cambios
4. Asegúrate de que `make test` y `make lint` pasen
5. Envía un pull request con una descripción clara del cambio

## Licencia

Este proyecto está licenciado bajo la [Licencia Pública General Affero de GNU v3.0](LICENSE) (AGPL-3.0-or-later).

## Créditos

Desarrollado por el equipo de tecnología de [Fundación Maquita](https://maquita.org), Quito, Ecuador.

## Características
Ver **[docs/CARACTERISTICAS-PLATAFORMA.md](docs/CARACTERISTICAS-PLATAFORMA.md)** — qué ofrece la plataforma (correo, seguridad, cumplimiento e IA), a costo cero de licencias.
