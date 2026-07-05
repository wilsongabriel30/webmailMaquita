# Guía completa: instalar y conectar OnlyOffice al Almacén

> **Para quién:** cualquier estudiante o técnico que quiera darle al
> webmail edición de documentos Word/Excel/PowerPoint en el navegador,
> colaborativa y gratuita. Se explica QUÉ es cada pieza, POR QUÉ se
> configura así y CÓMO verificar cada paso. Tiempo estimado: 30-45 min.

## 1. Qué es OnlyOffice y qué papel juega aquí

**OnlyOffice Document Server (DS)** es un programa de código abierto que
dibuja un editor de documentos completo dentro del navegador (como
Word/Excel/PowerPoint online) y coordina que varias personas editen el
mismo archivo a la vez sin pisarse.

El DS **no guarda tus archivos**: se los pide al Almacén cuando alguien
abre un documento y se los devuelve cuando hay cambios. El circuito es:

```
1. Usuario pulsa "Editar" en Archivos
2. El Almacén genera una CONFIGURACIÓN FIRMADA (JWT) y la página del editor
3. El navegador carga el editor desde /office/ (el DS)
4. El DS descarga el archivo del Almacén (con un token firmado, no con tu sesión)
5. Todos los que abren el mismo archivo entran a la MISMA sala de co-edición
6. Al haber cambios, el DS llama al "callback" del Almacén y este guarda
   (creando además una versión del contenido anterior, restaurable)
```

Tres piezas de seguridad que verás en esta guía:

| Pieza | Para qué sirve |
|---|---|
| **Secreto JWT compartido** | El Almacén firma lo que le manda al DS y el DS firma lo que le manda al Almacén. Nadie sin el secreto puede pedir archivos. |
| **Mismo dominio (/office/)** | Los navegadores bloquean iframes de otros dominios. Servimos el DS bajo el MISMO dominio del webmail y no hay nada que desbloquear. |
| **Tokens de descarga/callback** | El DS nunca usa la sesión del usuario: usa enlaces firmados y con expiración que solo sirven para ese archivo. |

## 2. Dónde instalarlo

Dos opciones válidas:

- **En el mismo servidor del webmail** (lo más simple; suficiente para
  decenas de usuarios). El DS usará el puerto 8080 local.
- **En una VM aparte** (recomendado si habrá mucha gente editando: el DS
  consume CPU/RAM al convertir documentos). Mínimo 2 vCPU / 4 GB RAM /
  40 GB; recomendado 4 vCPU / 8 GB.

La única diferencia entre ambas es la IP que pondrás en dos lugares
(nginx y el `.env`). En esta guía usamos `IP_DEL_DS` — si es el mismo
servidor, `IP_DEL_DS` = `127.0.0.1`.

## 3. Instalación con Docker

```bash
# 3.1 Docker (si no está instalado)
apt update && apt install -y docker.io

# 3.2 Genera el secreto JWT y GUÁRDALO en un lugar seguro
#     (lo usarás también en el .env del Almacén)
JWT_SECRET=$(openssl rand -hex 32) && echo "SECRETO: $JWT_SECRET"

# 3.3 Carpetas persistentes (sobreviven actualizaciones del contenedor)
mkdir -p /opt/onlyoffice/{data,logs,lib,db}

# 3.4 Levantar el Document Server
docker run -i -t -d --name onlyoffice -p 8080:80 --restart=always \
  -e JWT_ENABLED=true -e JWT_SECRET="$JWT_SECRET" \
  -e JWT_HEADER=Authorization -e JWT_IN_BODY=true \
  -v /opt/onlyoffice/logs:/var/log/onlyoffice \
  -v /opt/onlyoffice/data:/var/www/onlyoffice/Data \
  -v /opt/onlyoffice/lib:/var/lib/onlyoffice \
  -v /opt/onlyoffice/db:/var/lib/postgresql \
  onlyoffice/documentserver
```

Qué significa cada opción:

- `-p 8080:80` → el DS escucha en el puerto 8080 del servidor.
- `JWT_ENABLED/JWT_SECRET` → obliga a que TODO lo que entra y sale del
  DS venga firmado con tu secreto. **Nunca lo dejes desactivado.**
- `--restart=always` → arranca solo si se reinicia el servidor.
- Los `-v` → datos, logs y caché fuera del contenedor (persistentes).

**Verificar** (el arranque tarda 1-2 minutos):

```bash
sleep 90 && curl -s http://IP_DEL_DS:8080/healthcheck
# debe responder exactamente: true
```

> **Si el DS está en otra VM** y tu dominio público no se resuelve desde
> dentro de esa red, dile al contenedor cómo encontrarlo agregando al
> `docker run`:  `--add-host TU-DOMINIO:IP_DEL_SERVIDOR_WEBMAIL`
> (sin esto, el paso 6 "guarda" fallaría porque el DS no encuentra el
> callback del Almacén).

## 4. Publicarlo bajo el mismo dominio (nginx)

En el archivo del sitio del webmail (`/etc/nginx/sites-enabled/...`),
dentro del `server { ... }` de tu dominio, agrega el bloque `/office/`
que ya viene listo en **`almacen/deploy/nginx-almacen.conf`** —
cambiando `127.0.0.1` por tu `IP_DEL_DS` si está en otra VM.

La línea que hace la magia es:

```nginx
proxy_set_header X-Forwarded-Host $host/office;
```

Con ella el DS entiende que "vive" en `https://TU-DOMINIO/office/` y
genera TODAS sus URLs internas (editor, websockets de co-edición, caché)
bajo esa ruta. Sin ella, el editor carga a medias o no colabora.

```bash
nginx -t && systemctl reload nginx
```

**Verificar:**

```bash
curl -sk https://TU-DOMINIO/office/healthcheck                                  # true
curl -sk -o /dev/null -w "%{http_code}\n" \
  https://TU-DOMINIO/office/web-apps/apps/api/documents/api.js                  # 200
```

## 5. Conectarlo al Almacén

Edita `/opt/maquita-webmail/almacen/.env`:

```
ALMACEN_ONLYOFFICE_SECRET=el secreto del paso 3.2
ALMACEN_ONLYOFFICE_URL_PUBLICA=https://TU-DOMINIO/office
ALMACEN_ONLYOFFICE_URL_INTERNA=http://IP_DEL_DS:8080
ALMACEN_URL_PUBLICA=https://TU-DOMINIO
```

- `URL_PUBLICA` (del DS) = como lo ven los NAVEGADORES (siempre /office/
  del mismo dominio).
- `URL_INTERNA` = como lo ve el SERVIDOR del Almacén (directo, sin
  pasar por nginx) — se usa para el diagnóstico de conexión.
- `ALMACEN_URL_PUBLICA` = tu dominio; con él se arman los enlaces de
  descarga/callback que usará el DS.

Reinicia y comprueba el diagnóstico integrado:

```bash
systemctl restart maquita-almacen
```

Entra al webmail y abre en otra pestaña:
`https://TU-DOMINIO/api/almacen/onlyoffice/estado`
Debe responder `{"configurado": true, "conectado": true, ...}`.

| Respuesta | Significado |
|---|---|
| `configurado: false` | Falta alguna variable en el `.env` |
| `conectado: false` | El Almacén no llega a `URL_INTERNA` (¿firewall? ¿IP?) |
| ambos `true` | Todo listo, sigue al paso 6 |

## 6. Prueba final (la que vale)

1. Webmail → **Archivos** → sube un `.docx` cualquiera.
2. Pasa el mouse por la fila → **Editar** → se abre el editor completo.
3. Escribe un párrafo. Espera ~10 segundos o cierra la pestaña.
4. Vuelve a abrirlo: tus cambios deben estar.
5. **Co-edición:** abre el MISMO archivo desde otro usuario (u otro
   navegador) a la vez — deben verse los cursores y cambios en vivo.
6. En Archivos, el archivo debe tener su versión anterior recuperable
   (el guardado crea historial, hasta 100 versiones).

Si los 6 puntos pasan, la instalación está completa. 🎉

## 7. Problemas frecuentes y su causa real

| Síntoma | Causa | Arreglo |
|---|---|---|
| El editor no carga (pantalla en blanco) | `api.js` no responde por /office/ | Revisa el bloque nginx del paso 4 (y `nginx -t`) |
| "Documento no se puede abrir" | El DS no puede DESCARGAR el archivo | El secreto JWT no coincide entre `.env` y el contenedor, o el DS no resuelve tu dominio (`--add-host`) |
| Edita pero NO guarda | El callback no llega al Almacén | `ALMACEN_URL_PUBLICA` mal puesta; o timeouts cortos en nginx (usa los del bloque provisto: 600s+) |
| Cada usuario ve su propia copia (no colaboran) | Cambió la "key" del documento entre aperturas | No toques la lógica de sesión del motor; verifica que ambos usuarios abren la MISMA ruta |
| 503 "no configurado" | Variables ONLYOFFICE vacías | Completa el paso 5 y reinicia el servicio |
| El DS consume mucha RAM | Es normal en conversiones grandes | Dale más RAM a la VM o sepáralo del webmail |

Logs útiles:

```bash
docker logs onlyoffice --tail 50                  # el Document Server
journalctl -u maquita-almacen -n 50               # el Almacén (download/callback)
tail -50 /var/log/nginx/error.log                 # el proxy
```

## 8. Mantenimiento

```bash
# Actualizar el DS a la última versión (los datos persisten por los -v)
docker pull onlyoffice/documentserver
docker stop onlyoffice && docker rm onlyoffice
# ...volver a ejecutar el docker run del paso 3.4 (MISMO secreto)

# Respaldo del DS: no hace falta — los documentos viven en el Almacén.
# Lo único a conservar es TU SECRETO JWT y las carpetas /opt/onlyoffice.
```

## Antes de operar en serio: lee las lecciones

Esta no es la primera instalación de OnlyOffice del equipo: una instancia
anterior sufrió pérdida de datos y cortes cuyas causas están documentadas con
sus protecciones en **[LECCIONES-ONLYOFFICE.md](LECCIONES-ONLYOFFICE.md)**
(key de co-edición, timeouts del callback, autoguardado periódico, límite de
20 conexiones del Community, AppArmor y tormenta de conversiones). Diez
minutos de lectura que valen días de diagnóstico.

## Relacionado

- Guía general de instalación del Almacén: `GUIA-PASO-A-PASO.md`
- Contrato de la API: `CONTRATO-API.md`
- Variables de configuración comentadas: `../.env.example`
