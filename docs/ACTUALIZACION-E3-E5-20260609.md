# Actualización: features E3 + E5 (DLP, Cifrado, Safe Links, Phishing Sim, Amenazas, Compliance)

**Para:** el equipo que mantiene otra instalación del webmail.
**Objetivo:** traer todas las funciones nuevas **sin romper tu personalización**.
**Fecha:** 2026-06-09.

---

## ⚠️ ANTES DE EMPEZAR — no rompas lo tuyo
- **NUNCA sobrescribas tu `.env`.** Solo vas a *agregar* una línea nueva (ver paso 3).
- **Genera TU PROPIA clave** `SECURE_MSG_KEY` (NO copies la de otra instalación; es la clave maestra del correo cifrado).
- La migración SQL **solo agrega tablas nuevas y datos semilla**; no toca tus tablas ni tus datos.
- Si modificaste `compose.py`, `messages.py`, `main.py`, etc., hacé `git pull` y **resolvé conflictos** (no sobrescribas a ciegas).
- Tu **branding, tu admin, tu nginx y tus secretos** quedan intactos.

---

## 1) Traer el código
```bash
cd /opt/maquita-webmail
git stash            # si tenés cambios locales sin commitear
git pull origin main
git stash pop        # y resolvé conflictos si los hay
```

## 2) Migración de base de datos
Crea las tablas nuevas + datos semilla. Como `mailserver`:
```bash
PGPASSWORD='TU_PASS' psql -h localhost -U mailserver -d maildb \
  -f migrations/2026-06-e3-e5-features.sql
```
> El bloque `ALTER TABLE ediscovery_exports ...` al final requiere **superusuario**
> (la tabla es de `postgres`). Si da "must be owner", corré solo ese bloque como
> postgres: `sudo -u postgres psql -d maildb -c "ALTER TABLE ediscovery_exports ADD COLUMN ...; GRANT ... TO mailserver;"`

## 3) Variable de entorno NUEVA (correo cifrado)
Generá TU propia clave (32 bytes) y agregала al `.env` del **backend webmail**:
```bash
KEY=$(python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())")
echo "SECURE_MSG_KEY=$KEY" >> /opt/maquita-webmail/backend/.env
```
(El campo `secure_msg_key` ya está en `config.py`, viene en el pull.)

## 4) nginx — una sola ruta nueva (portal de correo cifrado)
Agregá al server block del vhost del webmail (junto a `location /api/`):
```nginx
location /secure/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
Luego: `nginx -t && systemctl reload nginx`.
> Las demás rutas nuevas (`/api/safelink`, `/api/phishtest`, `/api/hold-ack`,
> `/api/secure`) ya caen bajo tu `location /api/` existente — **no requieren cambios**.

## 5) Reconstruir y desplegar frontends
**Webmail** (usa el script oficial, que incluye la GUARDIA anti-bundle-roto):
```bash
bash /opt/maquita-webmail/deploy-webmail.sh
```
**Panel admin:**
```bash
cd /opt/maquita-webmail/admin-panel/frontend && npm run build
# (nginx sirve el dist directamente; no hay copia manual)
```

## 6) Reiniciar backends
```bash
systemctl restart maquita-webmail maquita-admin
```

## 7) Verificar
```bash
systemctl is-active maquita-webmail maquita-admin
curl -sk -o /dev/null -w '%{http_code}\n' https://TU_DOMINIO/webmail/   # 200
```
En `:8443` deben aparecer las secciones nuevas: **Protección** (Panel de amenazas,
Protección de datos DLP, Correo cifrado, Protección de enlaces, Simulación de phishing)
y **Compliance** (Cumplimiento de comunicaciones, Riesgo interno, Custodios y retención legal).

---

## Dependencias del entorno (revisar que existan en tu server)
- **rspamd** con `/etc/rspamd/local.d/maps/blacklist_domains.map` y `multimap.conf`
  (lo usa "Bloquear remitente" del Panel de amenazas, con `systemctl reload rspamd`).
  Si no lo tenés, el bloqueo igual queda registrado en BD pero no lo aplica rspamd.
- **Postfix relay local** en `127.0.0.1:25` sin auth (lo usan los avisos: OME OTP,
  phishing, retención legal). Enviando con `start_tls=False`.
- **Python**: `cryptography` (AES-GCM del cifrado). Ya suele estar.
- **GPG** + `gpg` CLI para la firma de exports de eDiscovery (opcional).
- **Guardia de deploy**: `frontend/scripts/check-bundle.mjs` (necesita `acorn`,
  `eslint-scope`, `globals` en node_modules del webmail; ya están como deps).

## La GUARDIA anti-bundle-roto (importante)
`deploy-webmail.sh` ahora corre `scripts/check-bundle.mjs` que **aborta el deploy
si el bundle tiene referencias indefinidas** (`X is not defined`). Si tu build falla
ahí, NO se publica nada roto. Es intencional. Para el panel admin podés correrla
manual: `node frontend/scripts/check-bundle.mjs admin-panel/frontend/dist/assets`.

## Resumen de lo que entra
- **E3:** DLP (fuga de datos), Correo cifrado (OME/portal con OTP).
- **E5-A:** Safe Links, Simulación de phishing, Panel de amenazas + respuesta automática.
- **E5-B:** Communication Compliance, Insider Risk, eDiscovery Premium (custodios + retención legal).
- **Arreglos:** ingestor `mail_trace` (parser ISO8601 + columnas), `report_spam` (SQL roto),
  firma GPG de exports (tabla/columnas).

Cada feature es administrable desde `:8443`. Toda la doc detallada está en
`/home/Documentacion/webmail/*.md` (en la instalación de Maquita) y en los commits.
