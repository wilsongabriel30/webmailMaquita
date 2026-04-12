#!/bin/bash
# Maquita Webmail — Ejecutar migraciones
# Uso: sudo bash migrate.sh
set -e
SCRIPT_DIR=$(dirname "$0")
sudo -u postgres psql -d maildb -f "$SCRIPT_DIR/init_tables.sql"
echo "Migración ejecutada: $(date)"
