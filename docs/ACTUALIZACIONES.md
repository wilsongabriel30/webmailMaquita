# Actualizaciones (panel → Protección → Actualizaciones)

Cada servidor (el de la propia institución o la VM de otra organización) se actualiza solo desde este
repositorio. Nunca se edita código en un servidor: todo cambio entra por un PR y llega a los servidores
como versión publicada.

## El flujo, de punta a punta

1. **Cambio** en una rama → PR → integración continua en verde → fusión en `main`.
2. **Producción de referencia** (el servidor de la institución que mantiene el proyecto) se pone al día
   con `main` como hasta ahora (`UPGRADING.md`, `deploy-webmail.sh`). Ahí se prueba con uso real.
3. **Publicar versión** cuando lo de `main` ya está probado en producción:
   ```bash
   git checkout main && git pull
   bash deploy/actualizar/publicar-version.sh v1.8.0
   ```
   Crea la etiqueta `v1.8.0` **firmada** con la clave SSH del equipo, la comprueba contra
   `deploy/actualizar/firmantes` y la sube. Las notas de la versión son los títulos de los commits desde
   la anterior.
4. **Los demás servidores** (canal «estable») la ven esa misma noche: a las 03:30 (más hasta 45 min al
   azar, para no actualizar todos a la vez) buscan, comprueban la firma y, si la actualización automática
   está activada, la instalan. También se puede pulsar «Buscar» e «Instalar ahora» en el panel.

## Qué hace al instalar (`maquita-actualizar`, en segundo plano)

Lo mismo que `UPGRADING.md` manda hacer a mano, en este orden:

| Paso | Detalle |
|---|---|
| Comprobaciones | Sin cambios locales en el código (si los hay, no se actualiza para no pisarlos); al menos 2 GB libres; solo hacia delante (la versión instalada tiene que estar contenida en la nueva). |
| Validación antes | `deploy/tools/validar-despliegue.sh`: se anota el número de fallos. |
| Respaldo | Commit anterior y volcado de `maildb` en `/var/backups/maquita-actualizar/` (se guardan los 3 últimos). |
| Archivos del sistema (antes) | Sumas sha256 y copia del contenido de los archivos de `deploy/actualizar/vigilados.txt`, y aviso de los que tienen parches locales (ver más abajo). |
| Código | `git checkout` de la versión. |
| Dependencias | `pip install -r requirements.txt` en cada entorno de Python que exista. |
| Frontends | Correo (`npm ci` si cambió el package-lock, `deploy-webmail.sh --solo-frontend`) y panel (`npm ci` si cambió, `vite build`). |
| Migraciones | `migrations/*.sql` y `deploy/seeds/*.sql` como el usuario de la aplicación (idempotentes). |
| Secciones | `instalar-app.sh` de cada sección instalada: sitios, DNS, cortafuegos, identidad, chat y el propio actualizador. |
| Ajustes | `deploy/ajustes/aplicar-ajustes.sh --aplicar`. |
| Reinicio | Servicios de la aplicación que estén habilitados (el correo se corta unos 30 s) y recarga de nginx. |
| Validación después | Si hay **más fallos que antes**, vuelve sola a la versión anterior (código, dependencias, frontends, secciones y reinicio). La base no se restaura sola (perdería el correo llegado entretanto): el volcado queda para hacerlo a mano. |

Registro completo de cada actualización en `/var/log/maquita-actualizar/<fecha>.log`; progreso e historial
en `/var/lib/maquita-actualizar/` (los muestra el panel).

## Archivos del sistema cambiados

El código de `/opt/maquita-webmail` se cambia con git, pero las secciones y los ajustes también reescriben
archivos del sistema. Para que nada cambie sin aviso, el actualizador compara antes y después un conjunto de
rutas vigiladas, declarado en `deploy/actualizar/vigilados.txt` (con comodines, agrupado):

| Grupo | Qué se vigila |
|---|---|
| bind | `/etc/bind/*` y `/etc/bind/zonas/**` (sin diarios `.jnl` ni claves gestionadas) |
| nginx | `/etc/nginx/*.conf`, `conf.d`, `sites-available`, `sites-enabled`, `snippets`, `sitios-waf`, `.htpasswd*` |
| fail2ban | `/etc/fail2ban/*.local`, `jail.d`, `filter.d`, `action.d` |
| postfix, dovecot, rspamd | `/etc/postfix/**` (sin mapas `.db`), `/etc/dovecot/**` (sin `private/`), filtros sieve globales, `/etc/rspamd/{local.d,override.d,maps.d}` |
| systemd | unidades y complementos (`*.d/*.conf`) de `/etc/systemd/system` |
| sudoers, cron y logrotate | `/etc/sudoers`, `/etc/sudoers.d/*`, `/etc/cron.d/*`, `/etc/logrotate.d/*` |
| ssh, php y cortafuegos | `sshd_config` (y `.d`), grupos de PHP-FPM, `/etc/nftables.conf` |
| programas del producto | `/usr/local/{bin,sbin}/*`, `/usr/local/lib/maquita-*/**` |
| configuración y `.env` | `/etc/maquita*/` (`.env`, `.conf`, `.json`) y los `.env` de las aplicaciones en `/opt/maquita-webmail` |

No se vigilan copias de respaldo (`*.bak*`, `*.antes-*`…), claves privadas (`*.pem`, `*.key`) ni los enlaces
por dentro: de un enlace simbólico se anota a dónde apunta.

Al terminar (también si la versión se revirtió: entonces se ve lo que quedó distinto de como estaba):

- **Lista** de creados, modificados (contenido, tipo o solo permisos) y borrados, por grupo. Va al final del
  registro, a la salida de la unidad (`journalctl -u maquita-actualizar-instalar`), a `progreso.json`
  (`"archivos_sistema"`, hasta 200 por categoría) y al panel: «Archivos del sistema cambiados». El historial
  guarda solo los totales.
- **Copia del contenido anterior** de lo modificado o borrado en
  `/var/backups/maquita-actualizar/<fecha>-<versión>/archivos-sistema/<ruta>`: carpetas 0700, archivos 0600
  (también los `.env`), solo root, sin seguir enlaces, hasta 4 MB por archivo y 256 MB en total. Las copias
  de lo que no cambió se borran al terminar. El informe completo queda en `archivos-sistema.json` (0600), en la
  misma carpeta. Se guardan los 3 últimos respaldos, como el volcado de la base.
- **Marca «tenía cambios locales»**: para lo que el producto instala tal cual (segunda columna de
  `vigilados.txt`: `/usr/local/lib/maquita-dns/*.py` ← `deploy/dns/lib/`, `/usr/local/sbin/maquita-*`, los
  filtros y la jaula de fail2ban de sitios, los perfiles del WAF…), se compara el archivo instalado con el del
  repositorio **en la versión instalada antes de actualizar** (el árbol de git del commit anterior). Si no son
  iguales, alguien lo parcheó a mano: si la versión nueva lo reemplaza, se marca, se avisa en el registro y en
  el panel, y su copia queda en el respaldo. No detiene la actualización.

Para ver qué cambió y recuperar un parche:

```bash
R=$(ls -d /var/backups/maquita-actualizar/*/ | tail -1)          # el respaldo de la última
python3 -m json.tool "$R/archivos-sistema.json" | less
diff -u "$R/archivos-sistema/usr/local/lib/maquita-dns/zona.py" /usr/local/lib/maquita-dns/zona.py
```

La comparación la hace el actualizador ya instalado: la primera actualización que trae esta función todavía
corre con el anterior y no la muestra; desde la siguiente, sí.

## Si tiene parches locales

En cada actualización se **regeneran** (y se pierde cualquier edición a mano):

- Los programas y bibliotecas del producto: `/usr/local/sbin/maquita-*`, `/usr/local/lib/maquita-*/`
  (por ejemplo `/usr/local/lib/maquita-dns/zona.py`), `maquita-sudo`.
- Lo que arman las secciones y los ajustes a partir de la configuración: `/etc/bind/maquita-zonas.conf` y las
  zonas (desde `/etc/maquita-dns/<zona>.json` y `servidor.json`), las plantillas y fragmentos de nginx, los
  filtros y jaulas de fail2ban de sitios, unidades de systemd, `sudoers.d` del producto y algunas claves de
  los `.env` de las aplicaciones.

En vez de parchear, use la configuración, que sí se conserva:

- **Transferencias de zona y avisos a secundarios (DNS)**: ya no hace falta tocar `zona.py` ni
  `maquita-zonas.conf`. Se configuran con
  `maquita-dns servidor --transferir-a 198.51.100.53 --notificar-a 198.51.100.53` (`--tsig`, redes, puertos y
  `--quitar-transferencias` en [CONFIGURAR-DNS.md](CONFIGURAR-DNS.md)) o en el panel: **DNS → Secundarios**
  (`deploy/dns/lib/ordenes_transferencias.py`). Quedan en `/etc/maquita-dns/servidor.json` y cada
  regeneración las respeta.
- **fail2ban y el proxy delante del servidor**: por `/etc/maquita-mail/organizacion.env`, con
  `FAIL2BAN_IGNORAR` (direcciones o redes que fail2ban no debe bloquear, en lugar de editar `jail.local` o los
  filtros) y `PROXY_CONFIABLE` (el proxy o balanceador del que nginx toma la IP real del cliente, en lugar de
  editar `set_real_ip_from` en los sitios). Ambas variables llegan en una versión próxima (se están
  implementando): hasta entonces, si las necesita, anote el parche y compruebe tras cada actualización la
  lista «Archivos del sistema cambiados».
- **Cualquier otro caso**: pida el cambio por el repositorio (issue o PR). Si el parche resuelve algo del
  producto, debe entrar como versión; si es propio del servidor, como opción de configuración.

Si mantiene parches igualmente, puede dejar la actualización automática activada: tras cada versión revise
en el panel los archivos marcados «tenía cambios locales» y vuelva a aplicarlos desde la copia (`diff -u` de
arriba). Lo que no esté instalado por el producto (por ejemplo un vhost propio de nginx) no se toca, y si
alguna vez cambiara, aparecería igualmente en la lista.

## Firma de las versiones

El repositorio es público: cualquiera que consiguiera publicar en él llegaría a todos los servidores si
estos instalaran cualquier etiqueta. Por eso el canal «estable» solo instala etiquetas `vX.Y.Z` con firma
válida de una clave de `deploy/actualizar/firmantes` (copiada en `/etc/maquita-actualizar/firmantes`). Las
etiquetas antiguas, sin firma, no se instalan.

- La clave privada está en el equipo de desarrollo del equipo de tecnología (`/root/.ssh/firma-versiones`).
  Quien la tiene publica versiones: guárdela como una contraseña de administrador.
- Para añadir o cambiar una clave: editar `deploy/actualizar/firmantes` por PR. Los servidores la reciben
  con la versión siguiente (firmada todavía con una clave anterior).

## Canales

- `estable` (por defecto): etiquetas firmadas. Para todos los servidores en uso.
- `estable-X.Y` (p. ej. `estable-1.11`): solo las etiquetas firmadas de esa serie (`v1.11.*`), es decir,
  los parches de una versión de soporte largo sin saltar a la siguiente. Ver
  [SOPORTE-Y-VERSIONES.md](SOPORTE-Y-VERSIONES.md).
- Una rama (p. ej. `main` o una rama de trabajo): solo en servidores de prueba. Sin firma; el panel lo avisa.
- Volver de una rama de trabajo a `estable`: si la rama se fusionó con «squash», su último commit no es
  antecesor de la etiqueta y «Buscar» no la ofrece (solo se avanza). Si el contenido es el mismo, se anota
  una sola vez como disponible y se aplica (la firma se comprueba igual, y hay respaldo y vuelta atrás):
  `cd /usr/local/lib/maquita-actualizar && python3 -c 'import version as v; d=v.leer_json(v.DISPONIBLE,{}); assert v.firmada(d["ref"]); d["nueva"]=True; v.guardar_json(v.DISPONIBLE,d)'`
  y luego `maquita-actualizar aplicar <etiqueta>`. Hecho así con la VM de pruebas al publicar v1.8.0.

## Instalación

```bash
sudo bash deploy/webmail/instalar-app.sh actualizar
```

Requiere que `/opt/maquita-webmail` sea un clon de git del repositorio. Deja el canal «estable» con la
actualización automática activada; se cambia en el panel.
