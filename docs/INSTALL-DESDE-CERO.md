# Instalación desde cero — Maquita Webmail

**Guía canónica.** Versión de referencia: **`v1.6.0-rc5`** (2026-09-05). Es la única guía que se
mantiene; `INSTALL-NATIVE.md` es el detalle manual por componente para quien no use el
instalador, e `INSTALL.md` queda sustituida y se conserva solo por referencia.

Filosofía: todo lo extra es **opt-in** (apagado por defecto). Los *motores de análisis* (ClamAV,
YARA, IA) son **fail-open**: si fallan, el correo se entrega igual y queda registrado, porque
cortar la entrega de toda la organización es peor. Los *controles de acceso* (permisos de
unidades compartidas, certificados, callbacks del editor, vales de sesión) son **fail-closed**:
si no pueden comprobar, deniegan. No confundir los dos.

## Antes de empezar: ¿Evaluar o Producción?

| | **Evaluar / probar** | **Producción real** |
|---|---|---|
| Objetivo | Ver cómo funciona | Servir correo de verdad |
| Infra | Una **VM Debian 13 desechable** (nube por horas o VirtualBox) | Servidor Debian 13 estable |
| Dominio / DNS | No hace falta (`DOMAIN=example.test`) | Dominio propio + **MX/SPF/DKIM/DMARC** (ver `CONFIGURAR-DNS.md`) |
| IP / PTR | No importa | IP fija con **PTR** (reverso), si no el correo cae en spam |
| TLS | Opcional (autofirmado) | **Obligatorio** (certbot, paso 4) |
| Cómo | `DOMAIN=example.test bash deploy/webmail/instalar.sh` → imprime URL + credenciales demo. Con `DOMAIN` dado no pide confirmación (vale sin TTY); `ASSUME_YES=1` la salta también en modo interactivo | Pasos 1→5 completos |

> **No hay modo "sin servidor"**: un servidor de correo necesita PostgreSQL + Dovecot + Postfix corriendo. Lo más liviano para evaluar es una VM Debian desechable; el instalador hace el resto (auto-genera secretos y una cuenta demo).

## 1. Prerequisitos del sistema (Debian 13 recomendado)
```bash
apt update && apt install -y \
  postgresql redis-server \
  dovecot-core dovecot-imapd dovecot-lmtpd dovecot-managesieved dovecot-sieve \
  postfix rspamd clamav clamav-daemon nginx \
  python3 python3-venv python3-pip nodejs npm \
  yara file ldap-utils
```
- **yara, file (libmagic)** → motores de Safe Attachments (estáticos, siempre activos).
- **ldap-utils** → solo si se usa SSO/LDAP (opt-in).
- `oletools`/`olefile` ya están en `backend/requirements.txt` (los instala el venv).

## 2. Clonar y configurar
```bash
git clone --branch v1.6.0-rc5 https://github.com/wilsongabriel30/webmailMaquita.git /opt/maquita-webmail
cd /opt/maquita-webmail
bash deploy/hooks/instalar.sh        # Guardián pre-commit: bloquea secretos, datos personales y volcados
# → rellena .git/guardian-patrones-locales (una expresión por línea): contraseñas del equipo,
#   términos que no deban publicarse. Vive fuera del repositorio a propósito.
cd backend
# crear backend/.env con (mínimo):
#   DATABASE_URL, SECRET_KEY, ADMIN_JWT_SECRET, MASTER_PASSWORD,
#   MAIL_DOMAIN, COOKIE_DOMAIN                 (OLLAMA_URL solo si vas a usar IA)
```
El instalador (paso 3) genera los secretos que falten. **Nunca** copies un `.env` de otra
instalación: los secretos firman sesiones y cifran claves privadas.

Chat (opcional): `chat-service/.env` a partir de `chat-service/.env.example`. Las fuentes
externas de GIF (GIPHY, Wikimedia) están **desactivadas** salvo que pongas `GIPHY_API_KEY` o
`GIFS_EXTERNOS_COMMONS=1`: con ellas, lo que la gente escribe en el buscador sale a ese tercero.

## 3. Instalar
```bash
bash deploy/webmail/instalar.sh
```
Aplica el esquema (`migrations/*.sql`) **y los seeds** (`deploy/seeds/*.sql`:
DLP, SafeAttach, milters), crea el buzón demo y levanta los servicios.

## 4. TLS / HTTPS (solo producción)
El webmail debe ir por HTTPS. Con el dominio ya apuntando a tu IP:
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d TU-DOMINIO -d mail.TU-DOMINIO
# certbot instala el timer systemd de renovación automática
```
Para evaluar en una VM desechable puedes omitir esto (Dovecot/nginx usan certificado autofirmado).

## 5. Validar
```bash
bash deploy/tools/validar-despliegue.sh          # chequeos; la IA sale como WARN, no falla
curl -sk https://TU-DOMINIO/api/health           # debe responder 200
git -C /opt/maquita-webmail status --porcelain   # debe estar VACÍO: un despliegue no ensucia el árbol
python3 deploy/tools/barrido-datos-personales.py --arbol /opt/maquita-webmail   # 0 hallazgos
```
Y a mano, con una sesión real: entrar, enviar un correo interno, cambiar la contraseña, abrir
Ajustes → Contraseña y comprobar que el botón explica por qué está deshabilitado.

## 6. Pon tu marca
El nombre y el logo **no viven en el código**. Desde el panel de administración (Branding) o en
la tabla `branding_settings`: `org_name` (la organización) y `app_name` (el producto; por
defecto «Maquita Mail»). Iconos de la PWA y detalles en `PON-TU-MARCA.md`. **No renombres** los
identificadores de almacenamiento del navegador (`maquita-mail-offline`, `maquita-cache`,
`MaquitaAlmacen`): dejarían sin datos a quien ya los tenga.

**Después de cambiar la marca** hay que reiniciar el backend (guarda `app_name`/`org_name` en
memoria al arrancar: hasta entonces los correos salen con la marca anterior) y reconstruir el
frontend (inyecta el nombre en `sw.js` y `manifest.json`):
```bash
systemctl restart maquita-webmail && bash deploy-webmail.sh --solo-frontend
```
El buzón `demo@ejemplo.local` es de un dominio de prueba que no recibe correo de fuera; los
buzones reales de tu dominio se crean en el panel.

## Si algo falla: qué reportar
Para que podamos corregirlo en el repositorio sin adivinar, envía **todo esto**:
1. Etiqueta instalada (`git -C /opt/maquita-webmail describe --tags`) y sistema (`cat /etc/os-release | head -2`).
2. **Paso exacto** de esta guía donde falló y el **comando literal** que ejecutaste.
3. La **salida completa** del comando (no un resumen), y `journalctl -u <servicio> --since "-10 min"` del servicio implicado.
4. La salida completa de `bash deploy/tools/validar-despliegue.sh`.
5. Si es de interfaz: navegador, captura, y los errores de la consola del navegador (F12).
6. Si lo arreglaste por tu cuenta: el cambio exacto, para integrarlo.
Sin valores de secretos ni datos de personas reales en el informe.
> El **frontend lo compila `instalar.sh`** (paso 3). Para recompilarlo tras cambios usa `bash deploy-webmail.sh` (build + deploy seguro a `www/webmail`). **No** corras `npm build` suelto: el deploy retiene los assets viejos para no romper pestañas abiertas.

---

## Features opt-in (todas con **default OFF**)

### 🔒 Detonación de Safe Attachments (sandbox dinámico)
> **REQUIERE:** Docker + imagen construida. **Default: OFF** (solo motores estáticos: ClamAV+oletools+YARA+archive+MIME).
```bash
cd deploy/safeattach && docker build -t maquita-safeattach-sandbox .
# backend/.env:  SAFEATTACH_DETONATE=1
```

### 🔑 SSO / OIDC (Keycloak + federación LDAP)
> **REQUIERE:** Keycloak + OpenLDAP federado (ver `deploy/sso/README.md`). **Default: OFF** (login local).
```bash
# backend/.env:  KC_OIDC_ENABLED=true  KC_CLIENT_SECRET=...
# LDAP desde maildb:  bash deploy/sso/sync-ldap-from-maildb.sh
```
El login local sigue como **break-glass**.

### 🛡️ AIR — contención automática de cuentas
> **REQUIERE:** decisión humana previa. **Default: OFF** (solo detecta y recomienda).
```sql
UPDATE threat_config SET auto_disable_on_compromise=true WHERE id=1;  -- habilitar
```

### 🧠 IA local (Qwen) — agentes, Copiloto Maquita, redacción
> **REQUIERE:** gateway Ollama/Qwen alcanzable. **Default: degradación elegante** (si no está, esas funciones se desactivan solas; el correo no se afecta).
```
# backend/.env:  OLLAMA_URL=http://<host>:<puerto>     (modelo en tabla ai_config)
```

---

## Notas de robustez (lecciones de producción)
- `COOKIE_DOMAIN` puede llevar punto inicial (`.dominio`) para cookies de subdominios;
  las URLs públicas (OnlyOffice, mensaje seguro) ya quitan ese punto automáticamente.
- Todos los motores de seguridad son **fail-open**: si ClamAV/YARA/IA fallan, el correo se entrega igual (se registra, no se bloquea salvo configuración explícita).

---

## Conectar una IA (opcional)

La app **arranca sin IA** (fail-open: las funciones de IA se degradan solas; el correo y el login nunca se afectan). Para activarla, **3 pasos**:

1. En `backend/.env`, descomenta **UN** preset y ajusta `IA_MODEL` / `IA_API_KEY`.
2. `bash deploy/webmail/probar-ia.sh` → debe imprimir **"IA OK"** (o el error con su causa y solución).
3. `systemctl restart maquita-webmail`.

Cambiar de proveedor (OpenAI → Ollama → Anthropic → gateway propio) = **2–4 líneas del `.env`, cero código**.

| Preset | IA_PROVIDER | IA_BASE_URL | Notas |
|---|---|---|---|
| **[A] Ollama local (INFINITO)** | `ollama` | `http://192.168.2.4:11434` | Recomendado local · `IA_MODEL=infinito-qwen36-lora:latest` |
| [B] OpenAI | `openai` | `https://api.openai.com` | requiere `IA_API_KEY` |
| [C] Anthropic | `anthropic` | `https://api.anthropic.com` | requiere `IA_API_KEY` |
| [D] OpenAI-compatible | `openai` | `http://tu-endpoint:puerto` | vLLM, LM Studio, OpenRouter, LocalAI… |

Config central (todas las features de IA la leen): `IA_PROVIDER`, `IA_BASE_URL`, `IA_MODEL`, `IA_API_KEY`, `IA_TIMEOUT`, `IA_EMBED_MODEL` (este último, para RAG/grounding futuro). El `probar-ia.sh` está integrado en `validar-despliegue.sh` como **WARN** (no bloquea el despliegue si la IA no está).
