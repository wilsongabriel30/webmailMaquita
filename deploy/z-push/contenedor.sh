# Arranque del contenedor «zpush» (lo usan instalar.sh y directorio/instalar.sh). Se carga con «source».
# Requiere CONF, ESTADO y LOGS. Recrea el contenedor: los teléfonos se reconectan solos en segundos.

zpush_arrancar() {
    local busqueda=()
    [ -f "$CONF/searchmaquita.php" ] && \
        busqueda=(-v "$CONF/searchmaquita.php":/opt/z-push/src/backend/searchmaquita/searchmaquita.php:ro)
    docker rm -f zpush >/dev/null 2>&1 || true
    docker run -d --name zpush --restart unless-stopped \
        --add-host host.docker.internal:host-gateway \
        -p 127.0.0.1:9000:9000 \
        -v "$ESTADO":/var/lib/z-push \
        -v "$LOGS":/var/log/z-push \
        -v "$CONF/config.php":/opt/z-push/src/config.php:ro \
        -v "$CONF/backend-imap.php":/opt/z-push/src/backend/imap/config.php:ro \
        -v "$CONF/backend-caldav.php":/opt/z-push/src/backend/caldav/config.php:ro \
        -v "$CONF/backend-carddav.php":/opt/z-push/src/backend/carddav/config.php:ro \
        -v "$CONF/backend-combined.php":/opt/z-push/src/backend/combined/config.php:ro \
        -v "$CONF/autodiscover.php":/opt/z-push/src/autodiscover/config.php:ro \
        "${busqueda[@]}" \
        zpush:latest >/dev/null
    sleep 2
    docker ps --format '{{.Names}} {{.Status}}' | grep -q '^zpush Up'
}
