# OnlyOffice Document Server — ofimática en línea del Drive

> La edición de `.docx/.xlsx/.pptx` dentro del Drive la provee **OnlyOffice Document Server**,
> un componente **aparte** (contenedor Docker). El instalador principal (`instalar.sh`) **no**
> lo monta. Esta guía lo deja andando. Atajo: `sudo bash deploy/webmail/instalar-app.sh onlyoffice`.

## Qué necesitas
- Docker instalado.
- Un secreto JWT **compartido** entre el Document Server y la app (webmail + Almacén).
- La ruta nginx `/office/` (ya viene en `almacen/deploy/nginx-almacen.conf`).

## 1) Levantar el Document Server (Docker)
```bash
SECRET=$(openssl rand -hex 32)
docker run -d --restart unless-stopped --name onlyoffice-ds \
  -p 127.0.0.1:8080:80 \
  -e JWT_ENABLED=true -e JWT_SECRET="$SECRET" \
  onlyoffice/documentserver
# Espera ~1-2 min al primer arranque; healthcheck:
curl -s http://127.0.0.1:8080/healthcheck   # -> true
```

## 2) nginx: servir el DS bajo /office/ del mismo dominio
El bloque ya está en `almacen/deploy/nginx-almacen.conf` (evita problemas de iframe/CORS
sirviendo el DS bajo `/office/` con `X-Forwarded-Host $host/office`). Asegúrate de incluir el
snippet en tu `server{}` y recarga nginx. **Patrón recomendado**: dominio dedicado del Drive
(`drive.suorg.tld`), donde `/office/` también aplica.

> **Ojo con el prefijo del DS (#9):** sirve el Document Server bajo `/office/`, **no** bajo
> `/onlyoffice/`. La app expone rutas `/onlyoffice/*` (bajo `/api/almacen/`); si el DS toma
> el prefijo `/onlyoffice/`, se traga el diagnóstico `/onlyoffice/estado`. Los snippets ya
> incluyen un `location = /onlyoffice/estado` (match exacto → Almacén) como salvaguarda.

## 3) Configurar la app (MISMO secreto JWT en todo)
En `backend/.env` (webmail):
```
ONLYOFFICE_URL=https://TU-DOMINIO/office
ONLYOFFICE_SECRET=EL_MISMO_SECRET
```
En `almacen/.env` (Drive):
```
ALMACEN_ONLYOFFICE_URL_PUBLICA=https://TU-DOMINIO/office
ALMACEN_ONLYOFFICE_URL_INTERNA=http://127.0.0.1:8080
ALMACEN_ONLYOFFICE_SECRET=EL_MISMO_SECRET
```
Reinicia: `systemctl restart maquita-webmail maquita-almacen`.

## 4) Verificar
- `curl -s http://127.0.0.1:8080/healthcheck` → `true`.
- Sin `ALMACEN_ONLYOFFICE_SECRET`, `GET /api/almacen/onlyoffice/config` responde **503
  «OnlyOffice no está configurado»** (así sabes que falta el wiring).
- Abre un `.docx` en el Drive → debe abrir el editor.

## Problemas comunes
- **503 «OnlyOffice no está configurado»**: falta `ALMACEN_ONLYOFFICE_SECRET` (o el del webmail).
- **El editor no carga / iframe en blanco**: revisa que `/office/` pase `X-Forwarded-Host
  $host/office` (el DS genera sus URLs bajo `/office/`); y que `ONLYOFFICE_URL` apunte a
  `https://TU-DOMINIO/office`.
- **El guardado no persiste**: el callback va a `URL_PUBLICA/api/almacen/onlyoffice/callback`;
  el `proxy_read_timeout 600s` de `/api/almacen/` debe estar (ya viene en el snippet).
- El JWT **debe ser idéntico** en el DS y en las tres variables de arriba.
