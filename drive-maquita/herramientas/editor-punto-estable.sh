#!/bin/bash
# Drive Maquita — Puntos estables del editor de hojas
# ===================================================
# 02/09/2026. Wilson Argüello.
#
# Para qué: se van a seguir haciendo cambios en el editor. Esto permite GUARDAR
# un estado que funciona y VOLVER a él en un solo comando, sin depender de
# acordarse de qué archivo se tocó.
#
#   editor-punto-estable.sh guardar  "por que es bueno"   → congela el estado de ahora
#   editor-punto-estable.sh listar                        → los puntos que hay
#   editor-punto-estable.sh probar                        → pasa las 21 pruebas
#   editor-punto-estable.sh volver   <nombre-del-punto>   → restaura ese estado
#
# Lo que se guarda: los módulos del editor, el inyector (que dice cuáles se
# cargan y con qué versión) y las pruebas. Es TODO lo que hace falta para
# reconstruir el estado.
#
# Antes de restaurar, guarda solo un punto «antes-de-volver-…», así que volver
# nunca pierde nada.

set -u

MODULOS=/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen
PRUEBAS=/home/sistemas/almacen-maquita/pruebas
INYECTOR=/home/sistemas/almacen-maquita/servicio/arreglos_editor.py
PUNTOS=/home/sistemas/almacen-maquita/backups/puntos-editor

verde() { printf '\033[0;32m%s\033[0m\n' "$1"; }
rojo()  { printf '\033[0;31m%s\033[0m\n' "$1"; }

guardar() {
    local nombre="punto-$(date +%Y%m%d-%H%M%S)"
    local destino="$PUNTOS/$nombre"
    mkdir -p "$destino/modulos" "$destino/pruebas"
    cp -p "$MODULOS"/editor-*.js "$destino/modulos/" 2>/dev/null
    # Los respaldos con fecha no hacen falta: ocupan y no aportan.
    rm -f "$destino/modulos"/*.bak.* "$destino/modulos"/*.rechazado.*
    cp -p "$PRUEBAS"/prueba-*.js "$destino/pruebas/" 2>/dev/null
    rm -f "$destino/pruebas"/*.bak.*
    cp -p "$INYECTOR" "$destino/arreglos_editor.py"
    grep -o "VERSION = '[^']*'" "$INYECTOR" > "$destino/version.txt"
    echo "${1:-sin motivo escrito}" > "$destino/por-que.txt"
    date '+%d/%m/%Y %H:%M' > "$destino/cuando.txt"
    verde "✓ punto guardado: $nombre"
    echo "  $(cat "$destino/version.txt")  ·  $(cat "$destino/por-que.txt")"
    echo "  $(ls "$destino/modulos" | wc -l) módulos, $(ls "$destino/pruebas" | wc -l) pruebas"
}

listar() {
    [ -d "$PUNTOS" ] || { echo "todavía no hay ningún punto guardado"; return; }
    for p in "$PUNTOS"/punto-*; do
        [ -d "$p" ] || continue
        printf '%-26s %s  %s\n' "$(basename "$p")" \
            "$(cat "$p/cuando.txt" 2>/dev/null)" "$(cat "$p/por-que.txt" 2>/dev/null)"
    done
}

probar() {
    local total=0 malas=0
    cd "$PRUEBAS" || return 1
    for f in prueba-*.js; do
        case "$f" in *.bak.*) continue;; esac
        salida=$(node "$f" 2>&1)
        bien=$(echo "$salida" | grep -c '^OK')
        mal=$(echo "$salida" | grep -c '^MAL')
        total=$((total + bien))
        malas=$((malas + mal))
        [ "$mal" -gt 0 ] && rojo "  $f: $mal en rojo"
    done
    if [ "$malas" -eq 0 ]; then
        verde "✓ $total comprobaciones, 0 en rojo"
        return 0
    fi
    rojo "✗ $total comprobaciones, $malas EN ROJO — no publiques esto"
    return 1
}

volver() {
    local nombre="${1:-}"
    local origen="$PUNTOS/$nombre"
    [ -d "$origen" ] || { rojo "no existe el punto «$nombre»"; listar; return 1; }

    # Volver tampoco pierde nada: se guarda antes lo que hay ahora.
    guardar "antes de volver a $nombre" > /dev/null
    cp -p "$origen/modulos"/*.js "$MODULOS/" && chown sistemas:www-data "$MODULOS"/editor-*.js
    cp -p "$origen/pruebas"/*.js "$PRUEBAS/"
    cp -p "$origen/arreglos_editor.py" "$INYECTOR"
    verde "✓ restaurado $nombre  ($(cat "$origen/version.txt"))"
    echo "  Ahora hay que recargar:  faro-reload maquita"
}

case "${1:-}" in
    guardar) guardar "${2:-}" ;;
    listar)  listar ;;
    probar)  probar ;;
    volver)  volver "${2:-}" ;;
    *) echo "uso: $(basename "$0") guardar «motivo» | listar | probar | volver <punto>" ;;
esac
