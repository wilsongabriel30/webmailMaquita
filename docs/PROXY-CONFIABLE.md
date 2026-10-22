# Servidor detrás de un proxy: IP real y fail2ban

Cuando Maquita Mail está detrás de un proxy (por ejemplo, un nginx `stream` que reparte el puerto 443 por
SNI entre varios servidores), el servidor solo ve la dirección **del proxy**. Sin más ajustes:

- nginx registra la IP del proxy en todos los registros, también en `/var/log/nginx/sitios-acceso.log`;
- las cárceles de fail2ban de los sitios (`sitios-escaneo`, `sitios-abuso`, `sitios-wp-login`) leen ese
  registro y, en cuanto un visitante cualquiera escanea un sitio, **banean al proxy**: el servidor entero
  (webmail, portal 8444 y sitios) queda fuera de Internet hasta que vence el bloqueo;
- los límites por IP (`limit_req`), el «viaje imposible» y la auditoría tratan a todo Internet como una sola IP.

Así le pasó a Andes el 22/10/2026: el proxy quedó baneado 24 h y el servidor estuvo 11 h sin servicio para
Internet, mientras el guardián (que solo probaba `localhost`) lo veía todo sano.

## Las variables

Van en `/etc/maquita-mail/organizacion.env` (el mismo archivo de los datos de la organización). Los valores
con espacios van entre comillas.

| Variable | Qué es |
|---|---|
| `FAIL2BAN_IGNORAR` | Direcciones o redes (CIDR) que fail2ban **nunca** banea, en **todas** las cárceles. Separadas por espacios. |
| `PROXY_CONFIABLE` | Direcciones o redes del proxy de confianza. Se suman solas a `FAIL2BAN_IGNORAR` y nginx toma de ellas la IP real del cliente. |
| `PROXY_MODO` | `proxy_protocol` (por defecto si hay `PROXY_CONFIABLE`): el proxy reenvía la conexión TCP tal cual (TLS *passthrough*) y antepone la cabecera PROXY. `cabecera`: el proxy termina el TLS y manda `X-Forwarded-For`. |
| `GUARDIAN_PROBAR_PUBLICO` | `no` apaga la prueba del guardián por el nombre público (servidores que no pueden llegar a su propia IP pública). |

```sh
# /etc/maquita-mail/organizacion.env
FAIL2BAN_IGNORAR="203.0.113.0/24"      # p. ej. la red de una oficina
PROXY_CONFIABLE="192.0.2.51"            # el proxy TLS
PROXY_MODO=proxy_protocol
```

Después:

```sh
sudo bash /opt/maquita-webmail/deploy/ajustes/75-fail2ban-proxy.sh --simular   # qué cambiaría
sudo bash /opt/maquita-webmail/deploy/ajustes/75-fail2ban-proxy.sh             # aplicarlo
```

Cada valor se valida como dirección o red IP (se rechaza cualquier otra cosa y las redes más amplias que /8
en IPv4 o /16 en IPv6). Con un valor no válido el ajuste termina con error y **no cambia nada**. El
actualizador aplica el ajuste en cada actualización, y los instaladores (`deploy/webmail/instalar.sh`,
`deploy/sitios/instalar.sh`) lo aplican al terminar.

## fail2ban: una lista para todas las cárceles

El ajuste genera `/etc/fail2ban/jail.d/zz-maquita-ignorar.local`:

```ini
[DEFAULT]
ignoreip = 127.0.0.1/8 ::1 <lo que ya tenía el servidor> <FAIL2BAN_IGNORAR> <PROXY_CONFIABLE>
```

fail2ban lee `jail.conf`, `jail.d/*.conf`, `jail.local` y **por último** `jail.d/*.local` (en orden
alfabético). Por eso esta lista gana a la de `jail.local`, que los instaladores reescriben, y a un parche
propio como `jail.d/zz-andes-ignoreip.local`. Para no perder nada, el ajuste copia en la lista las
direcciones que ya traían el `ignoreip` de `jail.local` y de los demás `jail.d/*.local` (como fail2ban no
admite `%(known/ignoreip)s` en `[DEFAULT]`, no hay otra forma de sumarlas). Un `jail.d/*.conf` no sirve: lo
pisa `jail.local`.

Si alguna dirección de esas listas está baneada al aplicar el ajuste, se desbanea (`fail2ban-client unban`).
Sin `FAIL2BAN_IGNORAR` ni `PROXY_CONFIABLE`, el archivo no existe (y si existía, se quita).

## nginx en modo `proxy_protocol` (TLS passthrough)

Con `proxy_protocol` en un `listen`, nginx exige la cabecera PROXY en **todas** las conexiones a ese puerto:
la red local, el propio servidor, el guardián y `deploy-webmail.sh` (que prueba con `--resolve` a
127.0.0.1) dejarían de entrar. Por eso el proxy tiene **sus propios puertos** y el 443 sigue directo:

| Puerto | Para qué |
|---|---|
| 443 | HTTPS directo, como siempre (red local, el propio servidor, Internet sin proxy). |
| **4443** | HTTPS del webmail y de los sitios **a través del proxy**, con PROXY protocol. |
| **4444** | Portal de dominio (el 8444) **a través del proxy**, con PROXY protocol. |
| 80 | HTTP directo. El proxy lo reenvía sin cabecera PROXY: allí se ve la IP del proxy, que fail2ban ignora; solo redirige a HTTPS y atiende la validación de Let's Encrypt. |

El panel general (8443) no se publica por el proxy: es solo para administración.

El ajuste genera, desde las variables:

- `/etc/nginx/conf.d/maquita-ip-real.conf` (en `http{}`): `set_real_ip_from <proxy>;` y
  `real_ip_header proxy_protocol;`. En el 443 directo no hay cabecera PROXY y no cambia nada. nginx solo cree
  la cabecera si la conexión viene de `PROXY_CONFIABLE`: desde otra dirección, `$remote_addr` sigue siendo
  la de la conexión.
- `/etc/nginx/snippets/maquita-ip-real.conf`: `listen 4443 ssl proxy_protocol;` (y `[::]:4443` si el proxy
  tiene dirección IPv6).
- `/etc/nginx/snippets/maquita-ip-real-defecto.conf`: lo mismo con `default_server`, para el vhost del
  webmail (un nombre desconocido que llegue por el proxy cae en el webmail, como en el 443).
- `/etc/nginx/snippets/maquita-ip-real-portal.conf`: `listen 4444 ssl proxy_protocol;` para el portal.

Los vhosts los incluyen con `include snippets/maquita-ip-real.con[f];`: el corchete convierte la ruta en un
patrón y, si el archivo no existe (servidor sin proxy), nginx no se queja. Ya lo traen las plantillas del
webmail, de los sitios (`maquita-sitios`), de autodiscover/autoconfig, de MTA-STS y del portal; en los
servidores ya instalados el ajuste lo añade tras cada `listen 443 ssl` (y `listen 8444 ssl`) de IPv4 de los
vhosts de `sites-enabled`. Antes de tocar nada copia cada archivo en `/etc/nginx/respaldos/` (nunca en
`sites-enabled`, que nginx lee) y los de fail2ban en `/var/backups/maquita-webmail/`; después prueba
`nginx -t` y `fail2ban-client -t` y, si alguno falla, lo deja todo como estaba.

El registro `sitios-acceso.log` (`$remote_addr`) y fail2ban pasan a ver la IP real del visitante.

### El proxy (nginx `stream`)

```nginx
# En el proxy, dentro de stream { } (módulos ngx_stream_ssl_preread y, si hace falta, ngx_stream_realip).
map $ssl_preread_server_name $maquita_https {
    ~^(mail|autodiscover|autoconfig|mta-sts)\.example\.org$  198.51.100.20:4443;
    sitio.example.com                                         198.51.100.20:4443;
    default                                                   otro_servidor:443;
}

server {
    listen 443;
    ssl_preread on;
    proxy_pass $maquita_https;
    proxy_protocol on;          # antepone la cabecera PROXY con la IP del visitante
}

server {
    listen 8444;                # portal de dominio
    proxy_pass 198.51.100.20:4444;
    proxy_protocol on;
}
```

(`198.51.100.20` es la dirección del servidor de correo vista desde el proxy; la del proxy, vista desde el
servidor, es la que va en `PROXY_CONFIABLE`.) Si el proxy reenvía también el puerto 80, que apunte al 80 del
servidor **sin** `proxy_protocol`.

### El cortafuegos

Si el servidor usa el cortafuegos del panel (`maquita-cortafuegos`, `deploy/cortafuegos`), el ajuste escribe
`/etc/maquita-cortafuegos/proxy.json` con las direcciones de `PROXY_CONFIABLE` y lo recarga
(`maquita-cortafuegos recargar`): **4443 y 4444 quedan abiertos solo para el proxy**, nunca para todo
Internet, en IPv4 y en IPv6. Es persistente: el cortafuegos lo lee también al arrancar. Si se quita
`PROXY_CONFIABLE` (o se pasa a modo `cabecera`), el archivo se borra y los puertos se cierran. Si el
cortafuegos instalado es de una versión anterior que no lee `proxy.json`, el ajuste lo avisa (actualícelo con
`sudo bash deploy/webmail/instalar-app.sh cortafuegos`).

Si el servidor no usa ese cortafuegos, el ajuste solo avisa: abra 4443 y 4444 solo para el proxy en el que
use (nftables, el del hipervisor, el del router). Aunque nginx no cree la cabecera PROXY de nadie más, esos
puertos son solo para el proxy.

## nginx en modo `cabecera` (el proxy termina el TLS)

El proxy descifra y vuelve a conectar al 443 del servidor como un cliente HTTPS más, con
`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`. El ajuste genera solo
`/etc/nginx/conf.d/maquita-ip-real.conf` con `set_real_ip_from <proxy>;`, `real_ip_header X-Forwarded-For;`
y `real_ip_recursive on;`; no hay puertos nuevos. (Sustituye a editar a mano `deploy/hardening/nginx/real-ip.conf`.)
Los snippets de los vhosts llevan solo el corte de los baneados (siguiente apartado).

## Lo que banea fail2ban se corta también en nginx

Tras el proxy, fail2ban banea la IP real del atacante en el cortafuegos del servidor, pero sus paquetes llegan
desde el proxy: ese bloqueo no corta lo que entra por él. Por eso, con `PROXY_CONFIABLE` (en los dos modos),
el ajuste añade un bloqueo en nginx, que sí conoce la IP real:

- `/etc/nginx/conf.d/maquita-ip-real.conf` lleva
  `geo $maquita_baneado { default 0; include maquita-baneados.conf; }` (geo usa la dirección del cliente,
  la real tras `realip`), y los snippets de los vhosts, `if ($maquita_baneado) { return 444; }` (nginx cierra
  la conexión sin responder). Vale también para el 443 directo, además del cortafuegos.
- La acción de fail2ban `action.d/maquita-nginx-baneo.conf` (ayudante `/usr/local/sbin/maquita-nginx-baneo`)
  apunta la IP en `/etc/nginx/maquita-baneados.conf` al banear y la quita al desbanear. Cada cárcel guarda su
  lista en `/var/lib/maquita-nginx-baneo/` y el archivo de nginx es la unión sin repetidos; solo admite
  direcciones IP (lo comprueba con `ipaddress`), escribe en un temporal y lo mueve (nunca queda a medias),
  usa un cerrojo (`flock`) para los baneos simultáneos y agrupa las recargas (`nginx -t` y
  `systemctl reload nginx`): varios baneos seguidos causan una sola recarga.
- `jail.d/zz-maquita-proxy-baneo.local` suma esa acción a las cárceles `sitios-escaneo`, `sitios-abuso`,
  `sitios-wp-login`, `nginx-http-auth`, `nginx-limit-req` y `maquita-webmail` con
  `action = %(known/action)s maquita-nginx-baneo`: se **añade** a la acción que ya tenga cada cárcel (el
  cortafuegos y, si la hay, la del MikroTik), no la sustituye. Las cárceles que no existan en el servidor no
  se activan por esto.

Sin `PROXY_CONFIABLE`, el ajuste quita `zz-maquita-proxy-baneo.local` y el `geo`; la acción y su ayudante se
quedan instalados (una cárcel que se para todavía los llama) y no hacen nada.

## El guardián

`guardian-web-correo` prueba, además de `localhost`, el nombre público del correo (`MAIL_HOST`) con el DNS
normal, como un visitante. Si `localhost` responde y el nombre público no, avisa «desde Internet no
responde; ¿proxy baneado por fail2ban?». Nunca reinicia nada por eso, y solo avisa si ese nombre respondió
alguna vez desde el propio servidor: hay redes en las que un equipo no puede llegar a su propia IP pública
(NAT sin *hairpin*). En ese caso se puede apagar con `GUARDIAN_PROBAR_PUBLICO=no`.

Si fail2ban tiene baneada alguna dirección de `PROXY_CONFIABLE` o `FAIL2BAN_IGNORAR`, el guardián lo dice
siempre (con la cárcel y la orden para desbanearla).

## Límites conocidos

- Por el 4443, el webmail atiende en HTTP/1.1, no en HTTP/2: `webmail.conf` activa HTTP/2 con el parámetro
  `http2` de `listen 443`, que solo vale para ese puerto, y no se cambia a la directiva `http2 on;` porque
  nginx 1.22 (Debian 12) no la admite. Los sitios de los clientes ya la usan y van en HTTP/2 por los dos
  puertos.
- El corte en nginx llega tras el saludo TLS: quien está baneado todavía completa la conexión con el proxy y
  con el servidor antes de recibir el cierre. Para cortarlo en el borde, bloquee también en el proxy (por
  ejemplo, con `deny` en su `stream{}` o en el cortafuegos del router).

## Comprobarlo en el servidor

```sh
sudo fail2ban-client -d | grep addignoreip | head -3       # la lista en cada cárcel
sudo nginx -T 2>/dev/null | grep -E 'set_real_ip_from|real_ip_header|listen 444[34]'
sudo ss -ltnp | grep -E ':444[34] '                          # nginx escucha en 4443 y 4444
sudo iptables -S CORTAFUEGOS | grep 4443                     # solo con -s <proxy> (cortafuegos del panel)
sudo fail2ban-client -d | grep "addaction', 'maquita-nginx-baneo" # la acción en las cárceles de nginx
cat /etc/nginx/maquita-baneados.conf                         # lo baneado que nginx corta con 444
curl -sk --haproxy-protocol --haproxy-clientip 203.0.113.7 \
     --resolve mail.example.org:4443:127.0.0.1 https://mail.example.org:4443/webmail/ -o /dev/null -w '%{http_code}\n'
```

(La última prueba simula el proxy desde el propio servidor: solo cambia la IP registrada si 127.0.0.1 está en
`PROXY_CONFIABLE`.) Después, una visita desde Internet debe aparecer en `/var/log/nginx/sitios-acceso.log` con
la IP del visitante, no con la del proxy.
