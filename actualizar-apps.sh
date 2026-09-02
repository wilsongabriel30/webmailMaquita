#!/bin/bash
# Actualiza las Aplicaciones del Drive Maquita (Almacén, Tableros/BI, Editor de PDF)
# tras traer los últimos cambios del repositorio.
#   git pull  ->  reinstala dependencias si cambiaron  ->  reinicia cada servicio
set -e
APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
cd "$APP_DIR"

echo "==> Trayendo cambios del repositorio..."
git pull --ff-only

_actualizar() {  # nombre  directorio  servicio
    local nombre="$1" dir="$2" servicio="$3"
    [ -d "$dir/venv" ] || { echo "==> $nombre: no instalado, se omite"; return 0; }
    echo "==> $nombre: dependencias..."
    "$dir/venv/bin/pip" install -q -r "$dir/requirements.txt" 2>/dev/null || true
    echo "==> $nombre: reiniciando ($servicio)..."
    systemctl restart "$servicio" 2>/dev/null || true
}

_actualizar "Almacen (Drive)" "$APP_DIR/almacen" "maquita-almacen"
_actualizar "Tableros/BI"     "$APP_DIR/almacen/aplicaciones/bi" "maquita-bi"
_actualizar "Editor de PDF"   "$APP_DIR/almacen/aplicaciones/pdf_editor" "maquita-pdf-editor"

# El editor puede traer tablas nuevas (idempotente)
PDFED="$APP_DIR/almacen/aplicaciones/pdf_editor"
[ -x "$PDFED/venv/bin/python" ] && "$PDFED/venv/bin/python" "$PDFED/crear_tablas.py" 2>/dev/null || true

echo "==> Listo. Aplicaciones del Drive actualizadas."
