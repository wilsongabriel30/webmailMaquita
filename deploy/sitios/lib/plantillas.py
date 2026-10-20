"""Plantillas de configuración que genera el ayudante: nginx y PHP-FPM por sitio."""

import os
import re
from string import Template

# Común a todos los sitios: registros, límites, cortafuegos de aplicación, cabeceras y archivos que
# nunca se sirven. Las zonas de límite (sitios_*), el formato de registro «sitios» y el cortafuegos de
# aplicación (ModSecurity + OWASP CRS, /etc/nginx/sitios-waf/) los instala deploy/sitios/instalar.sh.
_COMUN = r"""    client_max_body_size 64m;
    # Un enlace simbólico (subido por SFTP o traído en un repositorio) solo se sigue si apunta a algo del
    # mismo dueño: así no puede exponer archivos de otro sitio, que www-data sí puede leer.
    disable_symlinks if_not_owner from=$$document_root;

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
"""

# Sitios con PHP (página «en construcción», WordPress, Joomla y el catálogo): «try_files … /index.php».
_CUERPO = Template(
    r"""
    root $publico;
    index index.php index.html;
"""
    + _COMUN
    + r"""    # Comprimidos en la raíz: el lugar típico de las copias olvidadas (backup.zip, sitio.tar.gz).
    # En subcarpetas (p. ej. documentos para descargar) sí se sirven.
    location ~* ^/[^/]+\.(?:zip|tar|gz|tgz|7z|rar)$$ { deny all; }
    # Nunca ejecutar PHP desde las carpetas de subidas, caché o temporales.
    location ~* /(?:uploads|files|images|media|cache|tmp)/.*\.php$$ { deny all; }
$reglas_app
    location / { try_files $$uri $$uri/ /index.php?$$args; }

    # «archivo.php/ruta» (PATH_INFO) lo usan Moodle y otras aplicaciones; fastcgi-php.conf separa
    # la ruta y con «try_files $$fastcgi_script_name =404» solo ejecuta archivos .php que existen.
    location ~ [^/]\.php(/|$$) {
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

# Aplicación propia estática (HTML/CSS/JS): sin PHP. Con «spa», las rutas desconocidas van a index.html
# (aplicaciones de una sola página: React, Vue, Svelte…).
_CUERPO_ESTATICO = Template(
    r"""
    root $publico;
    index index.html index.htm;
"""
    + _COMUN
    + r"""    location ~* \.php$$ { deny all; }
    location / { try_files $$uri $$uri/ $$uri.html $respaldo; }

    location ~* \.(?:css|js|mjs|jpg|jpeg|gif|png|webp|avif|svg|ico|woff2?|wasm)$$ {
        expires 30d;
        access_log off;
        try_files $$uri =404;
    }
"""
)

# Aplicación propia Python o Node.js: un servicio que escucha solo en 127.0.0.1 y recibe todo por nginx
# (con el cortafuegos de aplicación delante). Admite WebSocket.
_CUERPO_PROXY = Template(
    r"""
"""
    + _COMUN
    + r"""    location / {
        proxy_pass http://127.0.0.1:$puerto;
        proxy_http_version 1.1;
        proxy_set_header Host $$host;
        proxy_set_header X-Real-IP $$remote_addr;
        proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $$scheme;
        proxy_set_header Upgrade $$http_upgrade;
        proxy_set_header Connection $$http_connection;
        proxy_read_timeout 300s;
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
php_admin_value[max_input_vars] = 5000
php_admin_value[disable_functions] = exec,passthru,shell_exec,system,proc_open,popen,pcntl_exec
php_admin_flag[expose_php] = off
php_admin_flag[allow_url_include] = off
php_admin_value[error_log] = $tmp/php-errores.log
php_admin_flag[log_errors] = on
"""
)


# Aplicaciones que solo admiten su dominio principal (rechazan otro Host): www y los alias redirigen a él,
# salvo el desafío de Let's Encrypt (los alias también llevan certificado).
_SOLO_PRINCIPAL = Template(r"""
    set $$redirigir_principal 0;
    if ($$host != "$dominio") { set $$redirigir_principal 1; }
    if ($$uri ~ "^/\.well-known/acme-challenge/") { set $$redirigir_principal 0; }
    if ($$redirigir_principal) { return 301 $$scheme://$dominio$$request_uri; }
""")


def vhost(meta, socket, acme, con_ssl):
    import alias
    import avanzado

    cuerpo = _cuerpo(meta, socket, acme)
    if os.path.exists(avanzado.ruta_extra(meta["dominio"])):
        cuerpo += f"\n    # Reglas propias del sitio (panel → Avanzado)\n    include {avanzado.ruta_extra(meta['dominio'])};\n"
    if not con_ssl:
        return _HTTP.substitute(nombres=" ".join(alias.nombres(meta)), cuerpo=cuerpo)
    texto = _HTTPS.substitute(nombres=" ".join(alias.certificables(meta)), cuerpo=cuerpo, acme=acme, dominio=meta["dominio"])
    # Alias que todavía no apuntan a este servidor: fuera del certificado, se sirven solo por HTTP.
    sin_https = [n for n in alias.nombres(meta) if n not in alias.certificables(meta)]
    if sin_https:
        texto += "\n" + _HTTP.substitute(nombres=" ".join(sin_https), cuerpo=cuerpo)
    return texto


def _cuerpo(meta, socket, acme):
    from apps import CATALOGO

    app = meta.get("app")
    raiz = meta["publico"]
    if app == "propia":
        return _cuerpo_propia(meta, acme)
    if app == "wordpress":
        reglas, waf = _REGLAS_WORDPRESS.substitute(socket=socket), "wordpress"
    elif app == "joomla":
        reglas, waf = _REGLAS_JOOMLA.substitute(socket=socket), "joomla"
    elif app == "paquete":
        # Paquete subido por la persona: reglas comunes y el perfil general del cortafuegos de aplicación.
        reglas, waf = "", "aplicacion"
        if (meta.get("paquete") or {}).get("raiz"):
            raiz = f"{meta['publico']}/{meta['paquete']['raiz']}"
    elif app in CATALOGO:
        modulo = CATALOGO[app]
        reglas, waf = Template(modulo.REGLAS_NGINX).substitute(socket=socket), "aplicacion"
        if getattr(modulo, "UN_SOLO_DOMINIO", False):
            reglas = _SOLO_PRINCIPAL.substitute(dominio=meta["dominio"]) + reglas
        if modulo.RAIZ_WEB:
            raiz = f"{meta['publico']}/{modulo.RAIZ_WEB}"
    else:
        reglas, waf = "", "general"
    return _CUERPO.substitute(
        publico=raiz, registros=meta["registros"], acme=acme, socket=socket,
        reglas_app=reglas, waf=waf,
    )


def _cuerpo_propia(meta, acme):
    propia = meta["propia"]
    comunes = {"registros": meta["registros"], "acme": acme, "waf": "general"}
    if propia["tipo"] == "estatico":
        return _CUERPO_ESTATICO.substitute(publico=propia["raiz"], respaldo="/index.html" if propia.get("spa") else "=404",
                                           **comunes)
    return _CUERPO_PROXY.substitute(puerto=propia["puerto"], **comunes)


def pool(meta, socket):
    texto = _POOL.substitute(
        pool=meta["usuario"],
        usuario=meta["usuario"],
        socket=socket,
        publico=meta["publico"],
        tmp=meta["tmp"],
    )
    # Ajustes de «Avanzado» (ya validados por avanzado.py): reemplazan los valores por defecto.
    import avanzado

    for nombre, linea in avanzado.lineas_pool(meta.get("php_ajustes")).items():
        texto, n = re.subn(rf"^php_admin_(?:value|flag)\[{re.escape(nombre)}\] = .*$", lambda m: linea, texto, flags=re.M)
        if not n:
            texto += linea + "\n"
    return texto
