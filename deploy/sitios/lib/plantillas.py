"""Plantillas de configuración que genera el ayudante: nginx y PHP-FPM por sitio."""

from string import Template

# Bloque común a HTTP y HTTPS. WordPress y Joomla funcionan con «try_files … /index.php».
# Las zonas de límite (sitios_*), el formato de registro «sitios» y el cortafuegos de aplicación
# (ModSecurity + OWASP CRS, /etc/nginx/sitios-waf/) los instala deploy/sitios/instalar.sh.
_CUERPO = Template(
    r"""
    root $publico;
    index index.php index.html;
    client_max_body_size 64m;

    access_log $registros/acceso.log;
    # Registro común de todos los sitios: lo vigila fail2ban (fuerza bruta, escaneos, abusos).
    access_log /var/log/nginx/sitios-acceso.log sitios;
    error_log $registros/error.log warn;

    # Límites por IP: ráfagas razonables para personas, no para robots.
    limit_conn sitios_conn 50;
    limit_req zone=sitios_general burst=80 nodelay;
    limit_req_status 429;
    limit_conn_status 429;

    # Cortafuegos de aplicación web (OWASP CRS), con las excepciones propias de la aplicación.
    modsecurity on;
    modsecurity_rules_file /etc/nginx/sitios-waf/$waf.conf;

    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    location /.well-known/acme-challenge/ { root $acme; }

    # Archivos ocultos (.git, .env, .htaccess) y copias o volcados: nunca se sirven.
    location ~ /\.(?!well-known) { deny all; }
    location ~* \.(bak|old|orig|save|sql|sqlite|swp|ini|log|sh|dist)$$ { deny all; }
    # Comprimidos en la raíz: el lugar típico de las copias olvidadas (backup.zip, sitio.tar.gz).
    # En subcarpetas (p. ej. documentos para descargar) sí se sirven.
    location ~* ^/[^/]+\.(?:zip|tar|gz|tgz|7z|rar)$$ { deny all; }
    # Nunca ejecutar PHP desde las carpetas de subidas, caché o temporales.
    location ~* /(?:uploads|files|images|media|cache|tmp)/.*\.php$$ { deny all; }
$reglas_app
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

# WordPress: el software más atacado de internet. Fuerza bruta en wp-login, XML-RPC, scripts
# internos llamados directamente, archivos de configuración y de depuración.
_REGLAS_WORDPRESS = Template(
    r"""
    location = /wp-login.php {
        limit_req zone=sitios_login burst=5 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
    }
    location = /xmlrpc.php { deny all; }
    location = /wp-trackback.php { deny all; }
    location = /wp-config.php { deny all; }
    location ~* ^/(?:readme\.html|license\.txt|wp-config-sample\.php)$$ { deny all; }
    location ~* ^/wp-includes/[^/]+\.php$$ { deny all; }
    location ~* ^/wp-includes/js/tinymce/langs/.+\.php$$ { deny all; }
    location ^~ /wp-admin/includes/ { deny all; }
    location ^~ /wp-content/mu-plugins/ { deny all; }
    location ~* ^/wp-content/(?:debug\.log|upgrade/|upgrade-temp-backup/|backup|ai1wm-backups/) { deny all; }
"""
)

# Joomla: fuerza bruta en /administrator, scripts internos y archivos de ejemplo o de configuración.
_REGLAS_JOOMLA = Template(
    r"""
    location = /administrator/index.php {
        limit_req zone=sitios_login burst=20 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
    }
    location = /configuration.php { deny all; }
    location ~* ^/(?:htaccess\.txt|web\.config\.txt|README\.txt|LICENSE\.txt|joomla\.xml)$$ { deny all; }
    location ~* ^/(?:administrator/)?(?:logs|tmp|cache|cli|installation|libraries|includes|layouts)/.*\.php$$ { deny all; }
    location ^~ /administrator/logs/ { deny all; }
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
    app = meta.get("app")
    if app == "wordpress":
        reglas, waf = _REGLAS_WORDPRESS.substitute(socket=socket), "wordpress"
    elif app == "joomla":
        reglas, waf = _REGLAS_JOOMLA.substitute(socket=socket), "joomla"
    else:
        reglas, waf = "", "general"
    cuerpo = _CUERPO.substitute(
        publico=meta["publico"], registros=meta["registros"], acme=acme, socket=socket,
        reglas_app=reglas, waf=waf,
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
