# Instalación desde cero — Maquita Webmail

Guía **canónica** y mínima. Para detalle por componente ver `docs/` y `deploy/`.
Filosofía: todo extra es **opt-in** y **fail-open** (si un componente externo no
está, el correo sigue funcionando; el login local es el respaldo "break-glass").

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
git clone https://github.com/wilsongabriel30/webmailMaquita.git /opt/maquita-webmail
cd /opt/maquita-webmail/backend
# crear backend/.env con (mínimo):
#   DATABASE_URL, SECRET_KEY, ADMIN_JWT_SECRET, MASTER_PASSWORD,
#   MAIL_DOMAIN, COOKIE_DOMAIN, OLLAMA_URL (IA)
```

## 3. Instalar
```bash
bash deploy/webmail/instalar.sh
```
Aplica el esquema (`migrations/*.sql`) **y los seeds** (`deploy/seeds/*.sql`:
DLP, SafeAttach, milters), crea el buzón demo y levanta los servicios.

## 4. Frontend + validar
```bash
cd frontend && npm install && npm run build   # nginx sirve desde dist/
curl -s https://TU-DOMINIO/api/health           # debe responder 200
```

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
