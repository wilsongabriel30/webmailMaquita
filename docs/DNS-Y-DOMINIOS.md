# Zonas DNS y «Nuevo dominio» (panel → Hospedaje)

El servidor responde por sus propios dominios (DNS autoritativo con BIND 9) y el panel arma un
dominio completo en un paso.

## Instalación

```bash
sudo bash deploy/webmail/instalar-app.sh dns      # BIND autoritativo
sudo bash deploy/webmail/instalar-app.sh sitios   # si también se quieren sitios web
```

Después, en el panel: **Zonas DNS → Ajustes**: IP pública del correo, de la web (si es otra) y de los
servidores de nombres (2 a 5, `ns1`…`ns5`). Se admiten IP privadas para preparar el servidor antes de
tener el enlace, con un aviso.

Si el servidor está detrás de NAT, redirige al servidor **53/UDP y 53/TCP** de cada IP de los
servidores de nombres, además de los puertos del correo y la web.

## Nuevo dominio

Con el dominio y el nombre de la institución, en un paso:

1. **Correo**: el dominio se da de alta en el servidor y recibe su **clave DKIM** propia (RSA 2048,
   selector `mail`; rspamd firma sola por nombre de archivo).
2. **Zona DNS completa**: servidores de nombres propios (`ns1.<dominio>`… con su IP), `@` y `www`, `mail`,
   MX, SPF (`mx ip4:<IP del correo> -all`), DKIM, DMARC (`p=quarantine`, informes a `postmaster@<dominio>`),
   TLS-RPT, MTA-STS (si el servidor publica la política de ese dominio), autoconfiguración de clientes
   (`autodiscover`, `autoconfig`, SRV de IMAP y envío) y CAA (`letsencrypt.org`).
3. **Sitio web** con una página «en construcción» con el nombre de la institución (menos de 3 KB, sin
   recursos externos, modo oscuro), datos estructurados schema.org `Organization`, Open Graph,
   `robots.txt`, `sitemap.xml` y `llms.txt` (descripción para asistentes de IA).
4. **Primer buzón** (por defecto `info@`, contraseña mostrada una vez) y **alias `postmaster@`** hacia él.

Cada paso respeta lo que ya exista. Al terminar muestra qué poner en el registrador (servidores de
nombres y sus IP, «glue») y un **semáforo** que comprueba cada 5 minutos, por DNS sobre HTTPS
(dns.google), la delegación, que la zona responda y que correo, MX y web apunten al servidor. Cuando
todo está en verde se piden los certificados HTTPS (Sitios web → HTTPS).

Nada en la zona menciona otros dominios del servidor: SOA, NS, SPF y DMARC usan solo el propio dominio.

## Zonas DNS

Lista de zonas, editor de registros (A, AAAA, CNAME, MX, TXT, SRV, CAA, NS) con ayuda por tipo, y la
misma comprobación de propagación. Reglas:

- Cada cambio se valida (formato de cada tipo, CNAME solo en su nombre, al menos un NS) y luego con
  `named-checkzone`; si falla, **no se publica nada** y el archivo anterior sigue en servicio.
- Número de serie nuevo en cada cambio y recarga solo de esa zona.
- Los registros creados por el asistente van marcados (●) y el panel avisa antes de editarlos o borrarlos.
- Nombres de destino: sin punto es relativo a la zona (`mail` → `mail.<dominio>.`); con punto es un
  nombre completo (`ghs.google.com`).
- Borrar una zona pide escribirla; su archivo queda renombrado como `.borrada-<fecha>`.

## Seguridad

- BIND solo autoritativo: sin recursión, transferencias cerradas, versión y nombre ocultos, límite de
  respuestas (contra la amplificación). Preguntado por un dominio ajeno responde REFUSED.
- El panel corre sin privilegios; el ayudante `maquita-dns` (root) solo se llama por `maquita-sudo`,
  que valida cada subacción. Los datos libres viajan en JSON codificado en base64url.
- Todo queda en la auditoría del panel (`dominio_nuevo`, `dns_registro_*`, `dns_servidor`, `dns_zona_borrar`).

## Archivos

- `deploy/dns/instalar.sh`, `deploy/dns/maquita-dns`, `deploy/dns/lib/` (común, registros, zona, dkim, comprobar).
- Datos: `/etc/maquita-dns/<zona>.json` y `servidor.json` (solo root); BIND: `/etc/bind/zonas/db.<zona>` y
  `/etc/bind/maquita-zonas.conf` (incluido desde `named.conf.local`).
- Panel: `admin-panel/backend/app/dns/` (API `/api/dns` y `/api/dominio-nuevo`) y
  `admin-panel/frontend/src/pages/ZonasDns.tsx`, `DominioNuevo.tsx`, `pages/dns/`.
- Página «en construcción»: `deploy/sitios/lib/pagina_inicio.py`.

## Pendiente

- Nombre propio del correo por dominio (`mail.<dominio>`): certificado y SNI en nginx, Postfix y Dovecot
  para que el webmail y los clientes de correo de cada dominio no muestren el nombre del dominio
  principal del servidor.
- DNSSEC opcional por zona.
