# Sitios web en el portal, v1.11

Seis funciones que antes eran solo del panel general (o no existían) y ahora tiene también cada cliente en su
portal (`https://<servidor>:8444/` → «Mi sitio web»). Como todo el portal, ninguna tiene privilegios propios:
cada orden pasa por el intermediario `maquita-sitios-portal`, que vuelve a comprobar la sesión y que el sitio (o
la zona) sea de quien lo pide, y por el validador de `maquita-sudo` antes de llegar a `maquita-sitios` o
`maquita-dns`. Lo ajeno responde 404 y lo reservado (nombres del correo, del panel o de los portales), 403.

| Función | Dónde | Código |
|---|---|---|
| Alias de dominio | Ficha del sitio → «Dominios» | `deploy/sitios/portal/lib/ordenes_dominios.py` |
| Despliegue desde git de sitios PHP | Ficha del sitio → «Git» (y en el panel general: «Archivos y datos» → «Git») | `deploy/sitios/lib/git_sitio.py`, `git_despliegue.py` |
| Aplicaciones Node.js y Python | Ficha del sitio → «Node.js y Python» | `deploy/sitios/portal/lib/ordenes_propias.py` |
| CPU y memoria por sitio | Ficha del sitio → «CPU y memoria» (y en el panel general) | `deploy/sitios/lib/recursos.py` |
| Información del servidor | «Mi sitio web» → «Información del servidor» | `deploy/sitios/portal/lib/ordenes_servidor.py` |
| DNS dinámico | Zona DNS de cada dominio → «DNS dinámico» | `deploy/sitios/portal/lib/ordenes_ddns.py`, `ddns.py`, `publico.py` |

## Instalación en un servidor que ya funciona

```bash
sudo bash deploy/ajustes/aplicar-ajustes.sh            # qué falta (69 y 70 dicen «Pendiente»)
sudo bash deploy/ajustes/aplicar-ajustes.sh --aplicar
```

- **Ajuste 69** (`deploy/sitios/recursos/instalar.sh`): temporizador `sitios-recursos` (cada 5 minutos), carpeta
  `/var/lib/maquita-sitios/recursos` y los módulos de `maquita-sitios` que lo usan.
- **Ajuste 70** (`deploy/sitios/publico/instalar.sh`): `git`, `rsync` y `ssh-keygen`; las carpetas de root
  `/etc/maquita-sitios/ganchos` y `/etc/maquita-sitios/ddns` (0700); y, si está el portal, las rutas públicas
  `/git-despliegue/` y `/nic/update` en el `server{}` HTTPS del correo (`snippets/maquita-apps/sitios-publico.conf`,
  con su límite de 30 peticiones por minuto e IP en `conf.d/maquita-sitios-publico.conf`). Respaldo en
  `/var/backups/maquita-sitios-publico/` y vuelta atrás si `nginx -t` falla. Si el sitio del correo no incluye
  `snippets/maquita-apps/*.conf`, el ajuste avisa: hay que añadir esa línea (como en `deploy/webmail/nginx/webmail.conf`).

Una instalación nueva lo hace sola (`instalar-app.sh sitios` y `instalar-app.sh portal-dominio`). El intermediario
y sus módulos nuevos los pone al día el ajuste 58, como siempre.

## Alias de dominio

Otros nombres que muestran el mismo sitio (el `.com` y el `.org` de la organización, `tienda.` y `shop.`…), hasta
10. Cada alias tiene que ser uno de los dominios asignados al cliente o un subdominio suyo; no puede ser un sitio
que ya existe ni el alias de otro sitio (409, sin decir de cuál), ni un nombre reservado (403). Si el sitio tiene
HTTPS, el certificado se amplía con los alias que ya apuntan al servidor; los demás quedan «sin HTTPS» hasta que
se vuelva a guardar. Es la misma orden del panel general (`maquita-sitios alias`).

## Despliegue desde git (sitios PHP)

Para sitios vacíos o con un paquete propio (no para WordPress y compañía del catálogo, que se actualizan solos, ni
para las aplicaciones Node.js o Python, que tienen su propio «Desplegar»).

1. **Configurar**: repositorio (`git@servidor:org/sitio.git`, `ssh://…` o `https://…` si es público), rama,
   carpeta del repositorio que se publica (vacía: todo), carpeta que sirve la web (p. ej. `public` en Laravel: lo
   que queda fuera, como `.env`, no se ve desde internet) y lo que el despliegue no toca nunca (lo que sube la
   aplicación: `wp-content/uploads`, `storage`…). Siempre se conservan `.well-known` y el archivo de IndexNow.
2. **Clave de despliegue**: se genera una ed25519 por sitio; se copia la pública en el servidor de git como clave
   de **solo lectura**. La privada vive en `/srv/sitios/<sitio>/despliegues/.ssh/`, del usuario del sitio y fuera
   del alcance de PHP (`open_basedir`).
3. **Desplegar**: el botón arranca el despliegue en segundo plano en su unidad `sitio-git-<usuario>` (systemd no
   deja dos a la vez; además hay un cerrojo) y la pantalla consulta el estado. Cada despliegue:
   - hace `git clone --depth 1` de la rama **con el usuario del sitio**, sin ganchos de git, solo por https o ssh
     (`GIT_ALLOW_PROTOCOL`) y solo si el servidor de git tiene dirección pública (nunca la red interna);
   - publica con `rsync --checksum --delay-updates --delete-delay --safe-links`, también como el usuario del
     sitio: los archivos cambian casi de golpe al final, lo que ya no está en el repositorio se borra, las
     exclusiones no se tocan y los enlaces que salen del repositorio no se copian. Lo nuevo queda 0640 con el grupo
     de nginx heredado de la carpeta pública;
   - guarda las 3 últimas versiones (`despliegues/versiones/`) y anota commit, autor, mensaje, duración y el
     resumen de rsync (los últimos 10 despliegues);
   - antes del **primero** hace una copia del sitio (pestaña «Copias»), porque rsync borra lo que había.
   El despliegue cuenta para el disco del dominio (desde el portal se comprueba la cuota antes).
4. **Volver a una versión**: otra pasada de rsync desde la carpeta de esa versión, sin red.
5. **Gancho (webhook)**: al activarlo se genera un secreto (se muestra una vez) y la dirección
   `https://<servidor>/git-despliegue/<sitio>`. En GitHub, Gitea o Forgejo: «Webhooks», tipo de contenido
   `application/json`, evento push, con ese secreto (firma `X-Hub-Signature-256` o `X-Gitea-Signature`); en
   GitLab, el secreto va como «Secret token» (`X-Gitlab-Token`). Solo despliega un push firmado a la rama
   configurada; un `ping` responde «listo»; dos ganchos seguidos esperan 20 s. El secreto lo guarda root en
   `/etc/maquita-sitios/ganchos/` y lo comprueba el intermediario (HMAC-SHA256 en tiempo constante): el portal
   solo deja el cuerpo, de hasta 1 MB, en su carpeta de subidas. Cualquier fallo (sitio, gancho o firma) responde
   lo mismo: 403 «Firma no válida o gancho sin activar».

Quitar el despliegue desde git borra la configuración, la clave, el gancho y las versiones guardadas; lo publicado
se queda. Órdenes: `maquita-sitios git-estado|git-configurar|git-clave|git-gancho|git-desplegar|git-volver|git-quitar`.

## Aplicaciones Node.js y Python

Las aplicaciones propias del panel general (`docs/APPS-PROPIAS.md`), ahora también desde el portal: estática,
Python (WSGI o ASGI, con gunicorn) o Node.js (un `.js` o `npm start`), con código por SFTP en la carpeta `app` o
desde un repositorio público por https. Corren con el usuario del sitio en su unidad de systemd, con 768 MB de
memoria, 1,5 núcleos y 256 tareas como máximo, escuchando solo en 127.0.0.1 detrás de nginx y del cortafuegos de
aplicación. Desde el portal, además: **sin puerto público** (abrir puertos lo hace el administrador general), el
repositorio tiene que estar en Internet, crear y desplegar cuentan para el disco del dominio, y de las variables de
entorno solo los nombres van a la auditoría.

## CPU y memoria por sitio

El temporizador `sitios-recursos` lee cada 5 minutos, para cada sitio:
- su aplicación propia, si la tiene, en su grupo de control de systemd (`cpu.stat`, `memory.current`), exacto;
- el resto (su pool de PHP-FPM, sus tareas, el FTP) por el usuario del sitio en `/proc`: CPU como diferencia entre
  dos lecturas de cada proceso y memoria PSS (la parte de lo compartido que le toca). Los pools de PHP-FPM comparten
  el grupo de control del servicio php-fpm, por eso se cuentan por usuario; lo que nace y muere entre dos lecturas
  no se ve, así que es una medida orientativa.

Guarda 24 horas por sitio en `/var/lib/maquita-sitios/recursos/<sitio>.json` (`[hora, % de CPU, MB]`; 100 % = un
núcleo) y borra las series de los sitios dados de baja. El portal y el panel general muestran el gráfico de las
últimas 24 horas, la media, el máximo y los límites del sitio. Orden: `maquita-sitios recursos <sitio>`.

## Información del servidor

Lo que el cliente necesita para configurar sus programas, sin nada sensible: nombre del servidor, IP compartida
(la de la web en «Zonas DNS → Ajustes»), servidores de nombres de **sus** dominios (solo las zonas que sirve este
servidor), versiones de PHP instaladas y la de serie (sin decir cuántos sitios usan cada una), límites de PHP y de
las aplicaciones, cuotas de su plan, rutas de sus sitios (también por SFTP), puertos de FTP (con los pasivos) y de
SFTP, servidores IMAP y SMTP y la dirección del DNS dinámico.

## DNS dinámico

En la zona DNS de cada dominio (si la sirve este servidor), una **ficha** por nombre (`casa.<dominio>`,
`oficina.quito.<dominio>`), hasta 20 por dominio, con su usuario (`ddns-xxxxxxxx`) y su contraseña al azar (144
bits, se muestra una vez; se guarda solo su hash). No se admiten nombres del correo ni de los servidores de nombres,
sitios web del servidor, nombres con CNAME ni registros que puso el asistente del dominio.

El router o el programa (ddclient, inadyn: proveedor «dyndns2») llama a

```
https://<servidor>/nic/update?hostname=casa.<dominio>&myip=<IP>
```

con autenticación básica (usuario y contraseña de la ficha). Sin `myip`, vale la IP desde la que llega la petición.
Las respuestas son las de dyndns2: `good <ip>`, `nochg <ip>`, `badauth`, `notfqdn`, `nohost`, `abuse` (más de 10
actualizaciones en 10 minutos), `dnserr` y `911`. Cada ficha cambia solo el registro A (o AAAA, con IPv6) de su
nombre, con TTL de 60 s, por `maquita-dns` (no se toca `deploy/dns`). Quitar una ficha deja su registro en la zona.

## Pruebas

```bash
cd backend && pytest tests/test_sitios_git.py tests/test_sitios_recursos.py tests/test_sitios_portal_v111.py \
  tests/test_maquita_sudo_sitios_v111.py
cd panel-dominio/backend && PYTHONPATH=. pytest tests/test_sitios_v111.py
```

Las de git usan git, rsync y ssh-keygen de verdad sobre un repositorio local (exclusiones, borrado, enlaces
inseguros, permisos, versiones y vuelta atrás). Las del intermediario prueban el alcance de cada orden, los alias
ajenos y reservados, el repositorio en la red interna, la firma del gancho (buena, mala, de otro sitio, sin gancho,
GitLab), el DNS dinámico (contraseña, nombre, frecuencia, IP no válidas) y que la información del servidor no
enseña nada ajeno.
