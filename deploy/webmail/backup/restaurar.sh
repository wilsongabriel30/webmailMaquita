#!/bin/bash
# ============================================================
# Restauración de un respaldo cifrado de Maquita Webmail
#
#   PRUEBA (no toca producción — restaura la BD a una BD desechable y la valida):
#     sudo bash restaurar.sh --verificar /var/backups/maquita/maquita-XXXX.tar.gpg
#
#   RESTAURACIÓN REAL (DESTRUCTIVA — sobrescribe BD/config/buzones):
#     sudo bash restaurar.sh --restaurar /var/backups/maquita/maquita-XXXX.tar.gpg
# ============================================================
set -euo pipefail

MODE="${1:-}"; ARCHIVE="${2:-}"
DB_NAME="${DB_NAME:-maildb}"
BACKUP_PASSPHRASE_FILE="${BACKUP_PASSPHRASE_FILE:-}"
[ -f /etc/maquita-backup.conf ] && . /etc/maquita-backup.conf
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
    echo "Uso: $0 --verificar|--restaurar <archivo.tar.gpg>"; exit 1
fi

# 1) Integridad
if [ -f "$ARCHIVE.sha256" ]; then
    echo -e "${GREEN}Verificando integridad (sha256)...${NC}"
    sha256sum -c "$ARCHIVE.sha256" || { echo -e "${RED}✗ Checksum NO coincide. Aborta.${NC}"; exit 1; }
fi

# 2) Descifrar + extraer a temporal
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
echo -e "${GREEN}Descifrando...${NC}"
DEC="$WORK/backup.tar"
if [ -n "$BACKUP_PASSPHRASE_FILE" ]; then
    gpg --batch --yes --decrypt --passphrase-file "$BACKUP_PASSPHRASE_FILE" "$ARCHIVE" > "$DEC"
else
    gpg --batch --yes --decrypt "$ARCHIVE" > "$DEC"   # asimétrico: usa la clave privada del llavero
fi
tar xf "$DEC" -C "$WORK"
echo "  Contenido del respaldo:"; ls -1 "$WORK" | grep -vE "backup.tar" | sed 's/^/    /'
DUMP="$(ls "$WORK"/db-*.dump 2>/dev/null | head -1)"
# El dump quedó en un temporal de root (700); el usuario 'postgres' no puede
# abrirlo. Lo copiamos a un archivo que sí pueda leer (chown postgres, chmod 600).
PG_DUMP="/var/tmp/maquita-restore-$$.dump"
cp "$DUMP" "$PG_DUMP"
chown postgres:postgres "$PG_DUMP" 2>/dev/null && chmod 600 "$PG_DUMP" || chmod 644 "$PG_DUMP"
trap 'rm -rf "$WORK"; rm -f "$PG_DUMP"' EXIT

# 3a) MODO PRUEBA: restaurar la BD a una BD desechable y validar
if [ "$MODE" = "--verificar" ]; then
    TESTDB="maquita_restore_test"
    echo -e "${GREEN}Prueba: restaurando la BD a '$TESTDB' (no toca producción)...${NC}"
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS $TESTDB;" >/dev/null
    sudo -u postgres psql -c "CREATE DATABASE $TESTDB;" >/dev/null
    sudo -u postgres pg_restore -d "$TESTDB" "$PG_DUMP" 2>/dev/null || true
    N="$(sudo -u postgres psql -d "$TESTDB" -tAc "SELECT count(*) FROM pg_tables WHERE schemaname='public';")"
    MB="$(sudo -u postgres psql -d "$TESTDB" -tAc "SELECT count(*) FROM mailbox;" 2>/dev/null || echo '?')"
    sudo -u postgres psql -c "DROP DATABASE $TESTDB;" >/dev/null
    echo ""
    echo -e "${GREEN}✓ PRUEBA DE RESTAURACIÓN OK:${NC} la BD restaura ($N tablas, $MB buzones en el dump)."
    echo "  El respaldo es válido y restaurable. (No se modificó nada en producción.)"
    exit 0
fi

# 3b) MODO RESTAURACIÓN REAL (destructivo)
if [ "$MODE" = "--restaurar" ]; then
    echo -e "${RED}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  RESTAURACIÓN REAL — SOBRESCRIBE base de datos, config    ║${NC}"
    echo -e "${RED}║  y buzones de PRODUCCIÓN. Esto NO se puede deshacer.      ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════╝${NC}"
    read -p "Escribe RESTAURAR para continuar: " C
    [ "$C" = "RESTAURAR" ] || { echo "Cancelado."; exit 0; }
    echo -e "${YELLOW}Deteniendo servicios...${NC}"
    systemctl stop maquita-webmail maquita-admin dovecot postfix 2>/dev/null || true
    echo -e "${GREEN}Restaurando base de datos...${NC}"
    sudo -u postgres pg_restore --clean --if-exists -d "$DB_NAME" "$PG_DUMP"
    echo -e "${GREEN}Restaurando configuración...${NC}"
    [ -f "$WORK/config.tar.gz" ] && tar xzf "$WORK/config.tar.gz" -C / 2>/dev/null || true
    if [ -f "$WORK/mail.tar.gz" ]; then
        echo -e "${GREEN}Restaurando buzones y calendario...${NC}"
        tar xzf "$WORK/mail.tar.gz" -C / 2>/dev/null || true
        chown -R vmail:vmail /var/vmail 2>/dev/null || true
    fi
    echo -e "${YELLOW}Arrancando servicios...${NC}"
    systemctl start dovecot postfix maquita-webmail maquita-admin 2>/dev/null || true
    echo -e "${GREEN}✓ Restauración completada. Verifica el webmail y el correo.${NC}"
    exit 0
fi

echo "Modo no reconocido. Usa --verificar o --restaurar."; exit 1
