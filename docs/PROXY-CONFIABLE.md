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

Si el servidor usa el cortafuegos del panel (`maquita-cortafuegos`), abra **4443 y 4444** como puertos
adicionales con origen «admin» y con la dirección del proxy entre las IP de administración (las redes
privadas ya lo son por defecto). No conviene abrirlos a todo Internet: aunque nginx no cree la cabecera PROXY
de nadie más, esos puertos son solo para el proxy.

## nginx en modo `cabecera` (el proxy termina el TLS)

El proxy descifra y vuelve a conectar al 443 del servidor como un cliente HTTPS más, con
`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`. El ajuste genera solo
`/etc/nginx/conf.d/maquita-ip-real.conf` con `set_real_ip_from <proxy>;`, `real_ip_header X-Forwarded-For;`
y `real_ip_recursive on;`; no hay puertos nuevos. (Sustituye a editar a mano `deploy/hardening/nginx/real-ip.conf`.)

## El guardián

`guardian-web-correo` prueba, además de `localhost`, el nombre público del correo (`MAIL_HOST`) con el DNS
normal, como un visitante. Si `localhost` responde y el nombre público no, avisa «desde Internet no
responde; ¿proxy baneado por fail2ban?». Nunca reinicia nada por eso, y solo avisa si ese nombre respondió
alguna vez desde el propio servidor: hay redes en las que un equipo no puede llegar a su propia IP pública
(NAT sin *hairpin*). En ese caso se puede apagar con `GUARDIAN_PROBAR_PUBLICO=no`.

Si fail2ban tiene baneada alguna dirección de `PROXY_CONFIABLE` o `FAIL2BAN_IGNORAR`, el guardián lo dice
siempre (con la cárcel y la orden para desbanearla).

## Límite conocido

Con el proxy en modo `proxy_protocol`, fail2ban banea la IP real del atacante en el cortafuegos del servidor,
pero sus paquetes llegan desde el proxy: ese bloqueo no corta lo que entra por el proxy (sí lo que entra
directo). Para cortar en el borde, bloquee también en el proxy (por ejemplo, con `deny` en su `stream{}` o en
el cortafuegos del router) las direcciones que fail2ban banea.

## Comprobarlo en el servidor

```sh
sudo fail2ban-client -d | grep addignoreip | head -3       # la lista en cada cárcel
sudo nginx -T 2>/dev/null | grep -E 'set_real_ip_from|real_ip_header|listen 444[34]'
sudo ss -ltnp | grep -E ':444[34] '                          # nginx escucha en 4443 y 4444
curl -sk --haproxy-protocol --haproxy-clientip 203.0.113.7 \
     --resolve mail.example.org:4443:127.0.0.1 https://mail.example.org:4443/webmail/ -o /dev/null -w '%{http_code}\n'
```

(La última prueba simula el proxy desde el propio servidor: solo cambia la IP registrada si 127.0.0.1 está en
`PROXY_CONFIABLE`.) Después, una visita desde Internet debe aparecer en `/var/log/nginx/sitios-acceso.log` con
la IP del visitante, no con la del proxy.
