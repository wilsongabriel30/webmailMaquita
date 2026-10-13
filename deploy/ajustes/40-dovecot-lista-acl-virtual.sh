#!/usr/bin/env bash
# Buzón virtual Virtual.Todo (2026-10-13): sin la lista de permisos vacía, el plugin acl intenta
# crearla en /etc/dovecot/virtual (solo lectura para Dovecot) y mail.log se llena de
# «open(/etc/dovecot/virtual/.temp…) failed: Read-only file system», dos por cada entrega.
set -euo pipefail
VIRTUAL="${DOVECOT_VIRTUAL:-/etc/dovecot/virtual}"
if [ ! -d "$VIRTUAL" ]; then echo "Sin cambios: no hay buzón virtual ($VIRTUAL)."; exit 0; fi
if [ -e "$VIRTUAL/dovecot-acl-list" ]; then echo "Sin cambios: $VIRTUAL/dovecot-acl-list ya existe."; exit 0; fi
echo "Pendiente: crear $VIRTUAL/dovecot-acl-list vacío"
[ "${1:-}" = "--simular" ] && exit 0
install -o root -g vmail -m 644 /dev/null "$VIRTUAL/dovecot-acl-list"
[ "$VIRTUAL" = /etc/dovecot/virtual ] && doveadm reload
echo "Listo: lista de permisos creada."
