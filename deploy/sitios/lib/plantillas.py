"""Plantillas de configuración que genera el ayudante: nginx y PHP-FPM por sitio."""

from string import Template

# Bloque común a HTTP y HTTPS. WordPress y Joomla funcionan con «try_files … /index.php».
_CUERPO = Template(
    r"""
    root $publico;
    index index.php index.html;
    client_max_body_size 64m;

    access_log $registros/acceso.log;
    error_log $registros/error.log warn;

    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    location /.well-known/acme-challenge/ { root $acme; }

    # Archivos ocultos (.git, .env, .htaccess) y copias de configuración: nunca se sirven.
    location ~ /\.(?!well-known) { deny all; }
    location ~* \.(bak|old|orig|sql|swp|ini|log|sh)$$ { deny all; }
    # XML-RPC de WordPress: blanco habitual de ataques de contraseñas. Cerrado por defecto.
    location = /xmlrpc.php { deny all; }
    # Nunca ejecutar PHP desde las carpetas de subidas.
    location ~* /(?:uploads|files|images|media|cache|tmp)/.*\.php$$ { deny all; }

    location / { try_files $$uri $$uri/ /index.php?$$args; }

    location ~ \.php$$ {
        # fastcgi-php.conf ya incluye «try_files $$fastcgi_script_name =404».
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 120s;
    }

    location ~* \.(?:css|js|jpg|jpeg|gif|png|webp|avif|svg|ico|woff2?)$$ {
        expires 30d;
        access_log off;
        try_files $$uri =404;
    }
"""
)

_HTTP = Template(
    r"""# Generado por maquita-sitios. No editar a mano: el panel lo regenera.
server {
    listen 80;
    listen [::]:80;
    server_name $nombres;
$cuerpo}
"""
)

_HTTPS = Template(
    r"""# Generado por maquita-sitios. No editar a mano: el panel lo regenera.
server {
    listen 80;
    listen [::]:80;
    server_name $nombres;
    location /.well-known/acme-challenge/ { root $acme; }
    location / { return 301 https://$$host$$request_uri; }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $nombres;
    ssl_certificate /etc/letsencrypt/live/$dominio/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$dominio/privkey.pem;
    include snippets/tls-intermedio.conf;
    add_header Strict-Transport-Security "max-age=31536000" always;
$cuerpo}
"""
)

_POOL = Template(
    r"""; Generado por maquita-sitios. No editar a mano.
[$pool]
user = $usuario
group = $usuario
listen = $socket
listen.owner = www-data
listen.group = www-data
listen.mode = 0660

pm = ondemand
pm.max_children = 6
pm.process_idle_timeout = 30s
pm.max_requests = 500

php_admin_value[open_basedir] = $publico:$tmp:/usr/share/php
php_admin_value[upload_tmp_dir] = $tmp
php_admin_value[session.save_path] = $tmp
php_admin_value[sys_temp_dir] = $tmp
php_admin_value[upload_max_filesize] = 64M
php_admin_value[post_max_size] = 64M
php_admin_value[memory_limit] = 256M
php_admin_value[max_execution_time] = 120
php_admin_value[disable_functions] = exec,passthru,shell_exec,system,proc_open,popen,pcntl_exec
php_admin_flag[expose_php] = off
php_admin_flag[allow_url_include] = off
php_admin_value[error_log] = $tmp/php-errores.log
php_admin_flag[log_errors] = on
"""
)


def vhost(meta, socket, acme, con_ssl):
    nombres = " ".join([meta["dominio"]] + (["www." + meta["dominio"]] if meta.get("www", True) else []))
    cuerpo = _CUERPO.substitute(
        publico=meta["publico"], registros=meta["registros"], acme=acme, socket=socket
    )
    plantilla = _HTTPS if con_ssl else _HTTP
    return plantilla.substitute(nombres=nombres, cuerpo=cuerpo, acme=acme, dominio=meta["dominio"])


def pool(meta, socket):
    return _POOL.substitute(
        pool=meta["usuario"],
        usuario=meta["usuario"],
        socket=socket,
        publico=meta["publico"],
        tmp=meta["tmp"],
    )
