# Búsqueda de texto completo del correo

Dovecot 2.4 con **fts-flatcurve** (paquete `dovecot-flatcurve` de Debian): busca por remitente, asunto
y dentro del texto en décimas de segundo, también en buzones de más de cien mil correos.

| Archivo | Se instala en | Qué hace |
|---|---|---|
| `60-busqueda.conf` | `/etc/dovecot/maquita.d/` | Motor, idioma (tildes y mayúsculas indiferentes), índice al llegar el correo, tope de 2 indexadores. |
| `busqueda-indexar-noche` | `/usr/local/sbin/` | Indexa el correo antiguo cuenta por cuenta, de 19:00 a 05:15, con prioridad mínima y esperando si el disco está cargado. Retoma donde quedó. `busqueda-indexar-noche estado` dice cuántas cuentas van. |
| `busqueda-adjuntos-precalentar` | `/usr/local/sbin/` | Deja en caché la estructura de los mensajes con adjunto para que la búsqueda por adjunto sea rápida. |
| `maquita-busqueda.cron` | `/etc/cron.d/maquita-busqueda` | Indexación nocturna, pasada semanal de lo que falte, compactación diaria de índices y caché de adjuntos. |
| `instalar.sh` | — | Instala todo; idempotente, con respaldo y vuelta atrás si `doveconf` rechaza la configuración. |

- **Servidores nuevos:** lo llama `deploy/webmail/instalar.sh` (paso 10, Dovecot).
- **Servidores ya instalados:** lo aplica el ajuste `deploy/ajustes/52-busqueda-texto-completo.sh` con la actualización.
- Si Dovecot ya tiene otro motor de búsqueda configurado fuera de `/etc/dovecot/maquita.d/`, no se toca.
- `dovecot.conf` incluye `/etc/dovecot/maquita.d/*.conf`; cada módulo opcional deja ahí su archivo.
  En `protocol lmtp`, `mail_plugins` va en forma de bloque (`sieve = yes`) para **sumarse** a los módulos
  globales: con `mail_plugins = sieve` la entrega no indexaría el correo al llegar.

**Por qué flatcurve y no fts-xapian:** se midieron los dos con el mismo buzón de 120.871 correos:
0,05–0,3 s por carpeta frente a 1–18 s, e índice de 373 MB frente a 847 MB. El servidor de referencia
pasó todas sus cuentas a flatcurve en octubre de 2026.

**Seguridad:** el índice guarda las palabras de los mensajes. Si los buzones se cifran en disco con
`mail_crypt`, el índice queda fuera de ese cifrado: valorarlo antes de activarlo en un servidor así.
