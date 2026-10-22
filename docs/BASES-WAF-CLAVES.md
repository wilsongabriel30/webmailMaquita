# Bases, cortafuegos de aplicaciones, claves SSH y fichas de API (v1.11)

Cuatro funciones «para desarrolladores» que cierran las filas 27, 29, 33, 37 y 38 de la
[alternativa a cPanel](ALTERNATIVA-CPANEL.md). Están en el **panel general** (Sitios web) y en el **portal del
cliente** (Mi sitio web). Como todo lo de los sitios, el portal (puerto 8444) no tiene privilegios: cada acción
pasa por el intermediario `maquita-sitios-portal`, que vuelve a comprobar la sesión (o la ficha de API) y que el
sitio es de ese administrador de dominio; después, `maquita-sudo` valida la forma de cada argumento y
`maquita-sitios` la vuelve a validar antes de tocar el sistema.

Para servidores ya instalados: `deploy/ajustes/71-bases-waf-claves-sitios.sh` (todo menos el acceso remoto) y
`deploy/ajustes/72-bases-acceso-remoto-tls.sh` (acceso remoto con TLS). Los dos admiten `--simular`.

---

## 1. Usuarios de base con permisos a medida

Además del usuario de cada base, se pueden crear **usuarios adicionales** (hasta 20 por sitio), cada uno de UNA
base del sitio (la de la aplicación o una adicional, MariaDB o PostgreSQL).

- **Nombre**: lo pone el servidor, con el prefijo del sitio: `u_<sitio>_<sufijo>`. Solo se elige el sufijo (de 2 a
  10 minúsculas o números, empezando por letra).
- **Permisos**:

  | Perfil | MariaDB | PostgreSQL |
  |---|---|---|
  | Lectura | `SELECT`, `SHOW VIEW` | `SELECT` en tablas y secuencias |
  | Escritura | + `INSERT`, `UPDATE`, `DELETE`, `LOCK TABLES`, `CREATE TEMPORARY TABLES`, `EXECUTE` | + `INSERT`, `UPDATE`, `DELETE`, `TEMPORARY` |
  | Estructura | + `CREATE`, `DROP`, `INDEX`, `ALTER`, `REFERENCES`, `CREATE VIEW`, `TRIGGER` | + `TRUNCATE`, `REFERENCES`, `TRIGGER`, `CREATE` en el esquema `public` |
  | Todo | `ALL PRIVILEGES` sobre esa base (sin `GRANT OPTION`) | miembro del rol dueño de la base (lo que cree queda a nombre del dueño) |
  | A medida | cualquier combinación de la lista de MariaDB | cualquier combinación de la lista de PostgreSQL |

  En PostgreSQL los permisos valen también para las tablas que se creen después (`ALTER DEFAULT PRIVILEGES`).
- **Contraseña**: la genera el servidor (24 caracteres) y se muestra **una sola vez**; no se guarda en ningún
  sitio. «Clave nueva» la cambia en todas las cuentas del usuario (local y remotas).
- **Borrar**: quita el usuario (en PostgreSQL antes reasigna lo suyo al dueño). Al borrar una base, o el sitio, se
  borran antes sus usuarios adicionales y sus reglas de acceso remoto.

**Seguridad del SQL**: ningún texto de la persona llega al SQL tal cual. Base, usuario y dueño pasan por
`re.fullmatch` sobre `[a-z][a-z0-9_]*` antes de ir entre comillas (`` ` `` en MariaDB, `"` en PostgreSQL), los
privilegios salen de listas cerradas y los orígenes remotos se normalizan con `ipaddress`
(`deploy/sitios/lib/bases_privilegios.py`, `bases_usuarios.py`).

## 2. Acceso remoto a las bases (por IP y con TLS)

Cada usuario adicional puede tener una lista de **IP o redes** (hasta 20) desde las que entrar. Sin lista, solo
entra desde el propio servidor.

- **MariaDB**: cada origen es una cuenta más del usuario (`'u'@'192.0.2.10'` o `'u'@'192.0.2.0/255.255.255.0'`) con
  la misma clave (se copia su hash; nadie la conoce), los mismos permisos y **`REQUIRE SSL`**. MariaDB no admite
  máscaras en IPv6: ahí solo direcciones sueltas.
- **PostgreSQL** (16 o posterior): una línea `hostssl <base> <usuario> <red> scram-sha-256` por origen en
  `/etc/postgresql/maquita-bases-remoto.conf`, incluido desde `pg_hba.conf`. Antes de recargar se comprueba con
  `pg_hba_file_rules`; si PostgreSQL no lo acepta, se deja lo anterior.
- **Cortafuegos del proyecto**: `maquita-sitios` deja `/etc/maquita-cortafuegos/bases.d/<dominio>.json` y
  `maquita-cortafuegos` abre el 3306 o el 5432 **solo para esos orígenes** (nunca para todos: una red `/0` o un
  puerto que no sea de bases se ignoran).
- **Límites**: nunca `/0`. Desde el portal, como mucho `/16` en IPv4 y `/48` en IPv6. Una red más amplia (hasta
  `/8` o `/32`) solo la puede autorizar el **superadministrador** desde el panel general, marcando la
  confirmación y con una sesión abierta con segundo factor (no con una ficha de API). Tampoco valen el bucle
  local, multidifusión ni direcciones de enlace local.
- **Certificado**: el de Let's Encrypt del propio servidor (`MAIL_HOST`), copiado para MariaDB y PostgreSQL (no
  pueden leer `/etc/letsencrypt`) por `maquita-bases-tls`, que también es gancho de certbot: tras cada renovación
  lo vuelve a copiar y recarga los dos motores sin reiniciar. No pide certificados ni toca la clave (no afecta a
  DANE). El cliente se conecta al nombre del servidor que muestra el panel, con TLS obligatorio (por ejemplo
  `sslmode=verify-full` en PostgreSQL o `--ssl-verify-server-cert` en MariaDB).

**Preparar el servidor (ajuste 72)**: copia el certificado, hace que MariaDB y PostgreSQL escuchen en la red con
TLS 1.2 o superior (`90-maquita-bases-remoto.cnf` y `conf.d/90-maquita-bases-remoto.conf`), añade el
`include_if_exists` a `pg_hba.conf` y escribe `/etc/maquita-sitios/bases-remoto.json`. **Reinicia MariaDB y
PostgreSQL una vez** (unos segundos sin bases: el correo y el panel esperan). **No hace nada sin el cortafuegos del
proyecto activo**, porque escuchar en la red sin él dejaría los puertos abiertos a todo Internet. Si un motor no
arranca con la configuración nueva, vuelve a la anterior. Hasta que se aplica, el panel y el portal avisan de que
el servidor no está preparado y no abren nada.

## 3. Cortafuegos de aplicaciones web (OWASP CRS)

Ya estaba **ModSecurity v3** (conector de nginx de Debian, `libnginx-mod-http-modsecurity`) con las reglas
**OWASP CRS completas** de Debian (`modsecurity-crs`) en modo bloqueo para todos los sitios, con excepciones para
WordPress, Joomla y el catálogo. Se eligió seguir con ModSecurity y no Coraza porque Coraza no tiene conector
para nginx: obligaría a poner otro proxy delante de cada sitio. Lo nuevo es **por sitio**:

- **Modo**: apagado (sin ModSecurity en ese sitio), solo detectar (anota y no bloquea) o bloquear (de serie).
- **Nivel de paranoia**: 1 (de serie) o 2 (detecta más y da más falsos positivos).
- **Exclusiones por regla** (hasta 50): el número de una regla de CRS (9xxxxx) en todo el sitio
  (`SecRuleRemoveById`, al final) o solo en una ruta (`ctl:ruleRemoveById` antes de las reglas). No se pueden
  excluir las reglas de puesta en marcha ni las de puntuación (900xxx–901xxx, 949xxx, 959xxx, 980xxx): para dejar
  de bloquear está el modo «solo detectar».
- **Visor de los últimos bloqueos**: fecha, IP, método, ruta, código y reglas que saltaron, con «Excluir esta
  regla». No muestra la consulta ni los datos que hicieron saltar la regla (pueden llevar contraseñas o datos
  personales de quien visitó el sitio).

Cada sitio carga sus reglas de `/etc/maquita-sitios/waf/<dominio>.conf` (generado por
`deploy/sitios/lib/waf_sitio.py`), en el orden que exige CRS: base del servidor, motor, registro del sitio
(`/var/log/nginx/sitios-waf/<dominio>.log`), `crs-setup.conf`, paranoia, **perfil de la aplicación**
(`/etc/nginx/sitios-waf/perfil-<perfil>.conf`, las mismas excepciones de antes: las de WordPress siguen
funcionando), exclusiones por ruta, reglas de CRS y exclusiones de todo el sitio. Cada cambio se aplica con el
mecanismo de las funciones web: copia previa, `nginx -t` y vuelta atrás si nginx lo rechaza. Cada sitio con
cortafuegos carga su propia copia de CRS en memoria (unos MB por sitio).

## 4. Claves SSH de las cuentas SFTP

Para la cuenta principal del sitio y para cada cuenta FTP/SFTP adicional (hasta 10 claves por cuenta):

- Se pega la clave **pública** (una línea, sin opciones delante). Solo **ed25519**, **ECDSA** o **RSA de 3072 bits
  o más**: se comprueba que el tipo declarado coincide con el de dentro de la clave y con `ssh-keygen -l`, que da
  los bits y la huella SHA256 que se muestran.
- sshd la lee de `/etc/ssh/claves-sitios/<usuario>` (`AuthorizedKeysFile` del bloque `Match Group sitios`):
  archivos de root, fuera del encierro, que la cuenta no puede cambiar. Cada línea lleva `restrict` (sin reenvíos
  ni terminal) y la cuenta sigue encerrada con `internal-sftp` en su carpeta, como con contraseña.
- La clave de la cuenta principal solo vale **mientras el acceso FTP/SFTP está activado**; la de una cuenta
  adicional, mientras exista. Al quitar la cuenta o el sitio, sus claves se borran.
- En la auditoría queda la huella, no la clave.

## 5. Fichas de API

Para usar la API del portal (fichas `mqd_…`) o del panel general (fichas `mqa_…`) desde programas propios, con
`Authorization: Bearer <ficha>`.

- **Alcance**: «lectura» (ver) y las áreas donde podrá hacer cambios. Portal: cuentas, alias, reenvíos, grupos,
  DNS y sitios web. Panel general: dominios, buzones, alias, reenvíos, grupos, DNS, sitios web, cola, respaldos y
  estado del servidor. **Falla cerrado**: lo que no está en la lista no se puede pedir con una ficha, ni para
  ver. Nunca con una ficha: la propia cuenta (contraseña, segundo factor, sesiones), los administradores, las
  propias fichas, leer o recuperar correo ajeno, el cortafuegos del servidor ni las actualizaciones.
- **Caducidad**: de 1 a 365 días. Se puede **revocar** en cualquier momento (el superadministrador también las de
  los demás en el panel general). Hasta 10 activas por cuenta.
- **Se muestra una sola vez**; se guarda solo su hash SHA-256 y sus primeros caracteres para reconocerla.
- **Segundo factor**: una ficha solo la crea una sesión abierta en pantalla, con un **código nuevo** del segundo
  factor; con una ficha no se puede crear otra. La ficha no lleva segundo factor, así que lo que lo exige en la
  interfaz (por ejemplo, entrar a un buzón) sigue fuera de su alcance. Vale con las mismas condiciones de la cuenta
  que una sesión (activa, sin la contraseña inicial y con segundo factor si es obligatorio).
- **Auditoría**: crear, revocar y cada acción hecha con ella (en el portal, con el número de la ficha en los
  detalles; en el panel general, una entrada `ficha_api_uso` por cada petición que cambia algo).
- En el portal, el intermediario de los sitios **vuelve a comprobar el alcance** de cada orden: una ficha de
  lectura no puede, por ejemplo, entrar al escritorio de WordPress, abrir una base ni descargar copias.

Tablas: `pd_fichas_api` (portal: `panel-dominio/deploy/esquema-5-fichas-api.sql` y `permisos-5-fichas-api.sql`,
que aplica el ajuste 71 si la base es local) y `admin_fichas_api` (panel general: la crea el propio panel al
arrancar). Al cambiar la contraseña de la cuenta, las fichas siguen vigentes: revócalas si sospechas que alguien
las tiene.

---

## Órdenes del ayudante

`maquita-sitios` (detalle en `deploy/sitios/lib/ordenes_desarrollo.py`, validadas en `maquita-sudo`,
`_validar_sitios_desarrollo`):

```
bases-usuarios <dominio>
base-usuario-crear <dominio> <base> <sufijo> <permisos JSON b64>
base-usuario-permisos <dominio> <usuario> <permisos JSON b64>
base-usuario-clave|base-usuario-borrar <dominio> <usuario>
base-usuario-remoto <dominio> <usuario> <lista JSON b64> [amplia]
waf <dominio> · waf-guardar <dominio> <JSON b64> · waf-bloqueos <dominio> [1-200]
ssh-claves <dominio> · ssh-clave-agregar <dominio> <cuenta> <clave b64> · ssh-clave-borrar <dominio> <id>
```

## Pruebas

`backend/tests/test_sitios_bases_usuarios.py`, `test_sitios_waf_claves.py`, `test_sitios_portal_v111.py`,
`test_maquita_sudo_desarrollo.py`, `test_panel_fichas_alcance.py`; en el portal,
`panel-dominio/backend/tests/test_sitios_v111.py` y `test_fichas_api.py`. Cubren, entre otras cosas, la inyección
en identificadores y rutas, las redes demasiado amplias, las claves débiles o con opciones, el alcance de las
fichas y la vuelta atrás cuando nginx rechaza un cambio.
