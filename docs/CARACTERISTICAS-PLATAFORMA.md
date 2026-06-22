# Plataforma de Correo Institucional — Autohospedada y Soberana

> Correo electrónico empresarial completo, **autohospedado**, con seguridad y cumplimiento de nivel corporativo — sobre software libre líder de la industria + desarrollo propio. **A costo cero de licencias.**

Desarrollada por el Equipo de Tecnología de **Fundación Maquita Cushunchic MCCH** y publicada como software libre, para que cualquier organización pueda operar su propio correo con control total de sus datos.

---

## ¿Por qué autohospedar el correo?

Las suites de correo empresarial equivalentes tienen un costo de licencias del orden de **$25 a $60 por usuario al mes**, con los datos alojados en la nube de un proveedor externo y dependencia permanente de ese proveedor.

Esta plataforma ofrece **capacidades equivalentes**, pero:

- **$0 en licencias** — el costo no crece con cada usuario nuevo.
- **Datos en tus propios servidores** — soberanía total, sin transferir información a terceros.
- **Sin dependencia de proveedor** (sin *lock-in*) ni alzas de precio.
- **Ahorro aproximado: $30,000 a $70,000 al año** para una organización de ~100 cuentas, frente a una suite comercial equivalente.

---

## ✨ Capacidades

### 📬 Correo y colaboración
- Webmail propio: bandeja, **calendario, contactos, tareas**.
- **Chat y presencia** en tiempo real.
- **Videollamadas / reuniones**.
- **Almacenamiento en la nube** propio + envío de adjuntos grandes.
- **Edición de documentos** en el navegador.
- Firma **S/MIME** y **mensajes cifrados** (cifrado de extremo).

### 🛡️ Seguridad
- Anti-spam, anti-malware y **anti-phishing** avanzado.
- **Adjuntos seguros**: análisis multi-motor (antivirus, macros, YARA, tipo real) + **detonación en sandbox aislado**.
- **Enlaces seguros**: verificación y bloqueo de URLs maliciosas.
- **DLP — Prevención de fuga de datos**: detecta y bloquea el envío de información sensible (documentos de identidad, tarjetas, datos personales) y registra cada intento.
- **Purga automática (zero-hour)** de correos maliciosos ya entregados.
- **Simulación de phishing** para concientización del personal.
- **Investigación y respuesta a incidentes** asistida por IA local, con contención de cuentas comprometidas.

### 📋 Cumplimiento
- **eDiscovery**: búsqueda forense en buzones con trazabilidad.
- **Retención** y **retención legal (holds)**.
- **Auditoría avanzada** y registro completo de acciones.
- **Cumplimiento de comunicaciones** y **riesgo interno (insider risk)**.
- Exportación de evidencia con cabeceras completas.

### 🔑 Identidad y acceso
- **SSO / OIDC** + federación de usuarios **LDAP**.
- **MFA** (autenticación de doble factor).
- **Acceso condicional**: políticas por riesgo, país o viaje imposible → bloquear, exigir 2FA o alertar.
- Detección de **inicios de sesión de riesgo** con auto-bloqueo.

### 🧠 Inteligencia Artificial (local y privada)
- **Agentes autónomos**: vigilan la seguridad, auditan la postura y resumen incidentes.
- **Copiloto de seguridad**: preguntas en lenguaje natural respondidas con datos reales del sistema.
- **"Pregúntale a tu correo"**: búsqueda semántica sobre la bandeja con IA.
- **IA enchufable**: compatible con proveedores de IA locales o en la nube — configurable, sin cambiar código. La IA es **opcional** y *fail-open* (si no está, el correo sigue funcionando).

---

## 🧱 Arquitectura

Construida sobre **software libre líder de la industria** + desarrollo propio:

| Capa | Tecnología |
|---|---|
| Correo (MTA / IMAP / anti-spam / AV) | Postfix · Dovecot · Rspamd · ClamAV |
| Datos / caché | PostgreSQL · Redis |
| Web / proxy | nginx |
| Backend | FastAPI (Python) |
| Frontend | React + TypeScript |
| IA local (opcional) | Servidor de modelos compatible |
| Identidad (opcional) | OpenLDAP · OIDC |

- **Panel de administración** con decenas de secciones operativas.
- **Webmail** moderno tipo SPA.
- Todo **opt-in y fail-open**: cada componente avanzado se activa cuando se necesita; si un servicio externo no está, el correo sigue funcionando.

---

## 🚀 Instalación

Ver **[`INSTALL-DESDE-CERO.md`](INSTALL-DESDE-CERO.md)**:

- **Evaluar**: una VM Debian desechable + `instalar.sh` (genera secretos y una cuenta demo automáticamente).
- **Producción**: servidor Debian + dominio + DNS (MX/SPF/DKIM/DMARC) + TLS.

---

## 📜 Licencia y filosofía

Software libre, autohospedado y **soberano**: tus datos son tuyos y viven en tu infraestructura. Pensado para fundaciones, organizaciones sociales y cualquier institución que quiera correo de nivel empresarial **sin pagar licencias por usuario ni entregar sus datos a un tercero**.
