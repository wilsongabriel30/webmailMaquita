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

- `deploy/dns/instalar.sh`, `deploy/dns/maquita-dns`, `deploy/dns/lib/` (común, registros, zona, dkim, comprobar;
  certificado, certificado_base, certificado_espera, certificado_dominios, certificado_sni, certificado_sni_nginx).
- Datos: `/etc/maquita-dns/<zona>.json` y `servidor.json` (solo root); BIND: `/etc/bind/zonas/db.<zona>` y
  `/etc/bind/maquita-zonas.conf` (incluido desde `named.conf.local`).
- Panel: `admin-panel/backend/app/dns/` (API `/api/dns` y `/api/dominio-nuevo`) y
  `admin-panel/frontend/src/pages/ZonasDns.tsx`, `DominioNuevo.tsx`, `pages/dns/`.
- Página «en construcción»: `deploy/sitios/lib/pagina_inicio.py`.

## Certificado del correo (Zonas DNS → Certificado del correo)

El certificado del servidor es un linaje de Let's Encrypt con el **nombre del servidor tal cual**
(`MAIL_HOST`, el `myhostname` de Postfix: `mail.<dominio>`, `hosting.<dominio>`, `correo.<dominio>`…)
como nombre principal. Solo incluye los nombres que, consultados por DNS sobre HTTPS, ya apuntan a la IP
del correo. El **dominio principal** (correo de contacto de Let's Encrypt, `postmaster@<dominio>`) es, en
este orden: el del nombre si empieza por `mail.`; `ORG_DOMINIO` de `/etc/maquita-mail/organizacion.env`;
la zona más corta del servidor que contiene el nombre; el nombre sin su primera etiqueta.

El temporizador `maquita-certificado-correo.timer` (cada 30 min, `maquita-dns certificado-auto`) emite o
amplía lo que haga falta sin pulsar nada. Un **error de configuración** (nombre del servidor que no es un
nombre completo, `CERTIFICADO_MODO` no válido, falta el sitio del webmail…) no se arregla reintentando:
sale como `{"accion": "aviso", …}` con código 0, así que el temporizador no queda en `failed`, y el panel
lo muestra como «Aviso de configuración» en «Certificado del correo». Un fallo de Let's Encrypt sí da
código de error esa vez; después el linaje **espera** 1 h, 2 h, 4 h… hasta 7 días antes de reintentarse
(estado en `/var/lib/maquita-dns/certificados.json`; el botón del panel lo intenta sin esperar).

Al emitirlo:

- nginx sirve el webmail también con cada `mail.<dominio>` (snippet `/etc/nginx/snippets/correo-nombres.conf`
  incluido tras `server_name` del sitio del webmail);
- el certificado pasa a usarse en el webmail, el panel (8443), el portal de dominio (8444), la
  autoconfiguración, MTA-STS, Postfix (25/465/587), Dovecot (IMAP/POP3) y vsftpd (FTPS); cada archivo
  tocado se respalda antes (`.bak.<fecha>`);
- `--reuse-key --key-type ecdsa` en **toda** petición a certbot (`certificado_base.pedir`): la clave no
  cambia al renovar, ampliar ni reducir nombres. Es obligatorio por DANE: una clave nueva deja los TLSA
  publicados sin coincidir y los servidores que validan DANE dejan de entregar el correo de todos los
  dominios. Ningún linaje se borra nunca;
- el gancho `/etc/letsencrypt/renewal-hooks/deploy/servicios-correo.sh` recarga esos servicios en cada renovación.

### Modo «compartido» (por defecto)

El certificado del servidor cubre `mail.`, `autoconfig.`, `autodiscover.` (y `mta-sts.` si se publica)
de **todos** los dominios con zona en el servidor. Pensado para dominios de **una misma organización**:
el certificado es público (Certificate Transparency) y lista todos sus nombres, y el saludo SMTP es el
del dominio principal.

Probado con un certificado de prueba: webmail, panel, SMTP (587), IMAP (993) y FTPS presentaron el
certificado nuevo (comparando huellas), el webmail respondió con un `mail.<otro dominio>` y todo volvió
al estado anterior al restaurar.

### Modo «por-dominio» (hospedaje de clientes)

Con `CERTIFICADO_MODO=por-dominio` en `/etc/maquita-mail/organizacion.env`, los clientes **no comparten
certificado**: el del servidor cubre solo el dominio principal y cada otro dominio con zona en el
servidor tiene su linaje `mail.<dominio>` con `mail.`, `webmail.`, `autoconfig.`, `autodiscover.` (y
`mta-sts.` si se publica), solo los nombres que ya resuelven a la IP del correo, validados por webroot.

- **Mientras el dominio no está delegado** (`mail.<dominio>` no resuelve aquí), sus nombres se sirven con
  el certificado del servidor (provisional) y se vuelve a mirar en cada pasada sin pedir nada a Let's
  Encrypt. Cuando resuelve, se emite y se activa sin intervención.
- **Instalación por SNI** (`deploy/dns/lib/certificado_sni.py`), cada servicio con copia previa,
  comprobación y vuelta atrás si falla:
  - nginx: `/etc/nginx/sites-available/correo-dominio-<dominio>` (enlazado en `sites-enabled`) con copias
    de los bloques del webmail (443), del portal de dominio (8444) y de la autoconfiguración (443), con
    los nombres y el certificado del dominio. Se rehacen en cada pasada desde los archivos vivos, que no
    se tocan; `default_server` y demás opciones únicas de `listen` se quedan en el original. MTA-STS ya
    tiene un archivo por dominio: ahí solo cambian las rutas del certificado. Respaldos en
    `/etc/nginx/respaldos/`. Comprobación: `nginx -t`.
  - Postfix: `tls_server_sni_maps = hash:/etc/postfix/sni-correo`, compilado con `postmap -F` y
    `systemctl restart postfix` (con reload no relee el mapa). Si ya hay otro `tls_server_sni_maps`, no
    se toca y sale un aviso. Comprobación: `postfix check`.
  - Dovecot: `/etc/dovecot/maquita.d/90-sni-correo.conf` (o `conf.d/` en una configuración de Debian)
    con un bloque `local_name mail.<dominio> { … }` por dominio, con la sintaxis de la versión instalada
    (`dovecot --version`): 2.4 `ssl_server_cert_file = ruta`, 2.3 `ssl_cert = <ruta`. Comprobación:
    `doveconf -n`.
  - Gancho `/etc/letsencrypt/renewal-hooks/deploy/sni-correo.sh`: tras renovar un linaje del mapa,
    recompila el mapa de Postfix (guarda una copia del certificado), reinicia Postfix y recarga Dovecot y
    nginx. Cada pasada recompila también si un certificado es más nuevo que el mapa.
- **Al pasar de «compartido» a «por-dominio»** los nombres de clientes que ya estaban en el certificado
  del servidor siguen ahí hasta que su certificado propio existe; entonces el del servidor se vuelve a
  pedir sin ellos, con la misma clave. Lo que ya se publicó en Certificate Transparency no se puede borrar.
- El panel muestra el modo y, por dominio, su certificado propio, el vencimiento o el último fallo.

Para activarlo: añadir la línea a `organizacion.env` y esperar a la siguiente pasada (o
`sudo maquita-dns certificado-auto`). Volver a «compartido» deja de gestionar los certificados por
dominio pero no retira lo instalado (certbot los sigue renovando).

## Pendiente

- DNSSEC opcional por zona.
