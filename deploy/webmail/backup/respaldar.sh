#!/bin/bash
# ============================================================
# Respaldo CIFRADO de Maquita Webmail
#   - Base de datos PostgreSQL (maildb)
#   - Configuración + secretos (.env, Dovecot, Postfix, claves DKIM, Radicale)
#   - Buzones de correo (/var/vmail) y colecciones de calendario  [opcional]
# Cifra el resultado con GPG. Sin método de cifrado configurado, NO respalda.
# Uso:   sudo bash respaldar.sh
# Config opcional en /etc/maquita-backup.conf (variables de abajo).
# ============================================================
set -euo pipefail

# -------- Configuración (sobrescribible por /etc/maquita-backup.conf) --------
BACKUP_DIR="${BACKUP_DIR:-/var/backups/maquita}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DB_NAME="${DB_NAME:-maildb}"
VMAIL_DIR="${VMAIL_DIR:-/var/vmail}"
INCLUDE_MAILBOXES="${INCLUDE_MAILBOXES:-1}"     # 1 = incluir buzones (pesado); 0 = solo BD+config
APP_DIR="${APP_DIR:-/opt/maquita-webmail}"
# Cifrado: define UNO de los dos
#   BACKUP_GPG_RECIPIENT  -> cifrado asimétrico (recomendado; la clave PRIVADA va offline)
#   BACKUP_PASSPHRASE_FILE -> cifrado simétrico con una frase en un archivo (chmod 600)
BACKUP_GPG_RECIPIENT="${BACKUP_GPG_RECIPIENT:-}"
BACKUP_PASSPHRASE_FILE="${BACKUP_PASSPHRASE_FILE:-}"
[ -f /etc/maquita-backup.conf ] && . /etc/maquita-backup.conf

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

# -------- Validar método de cifrado (nunca respaldar en claro) --------
if [ -z "$BACKUP_GPG_RECIPIENT" ] && [ -z "$BACKUP_PASSPHRASE_FILE" ]; then
    echo -e "${RED}✗ No hay método de cifrado configurado.${NC}"
    echo "  Define en /etc/maquita-backup.conf UNA de estas opciones:"
    echo "    BACKUP_GPG_RECIPIENT=\"tu-clave@dominio\"      # asimétrico (recomendado)"
    echo "    BACKUP_PASSPHRASE_FILE=\"/root/.backup-pass\"   # simétrico (chmod 600)"
    echo "  Generar un par GPG (en una máquina segura):  gpg --gen-key"
    exit 1
fi

mkdir -p "$BACKUP_DIR"; chmod 700 "$BACKUP_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo -e "${GREEN}[1/4] Volcando la base de datos ($DB_NAME)...${NC}"
sudo -u postgres pg_dump -Fc "$DB_NAME" > "$WORK/db-$DB_NAME.dump"

echo -e "${GREEN}[2/4] Empaquetando configuración y secretos...${NC}"
tar czf "$WORK/config.tar.gz" \
    "$APP_DIR/backend/.env" \
    "$APP_DIR/admin-panel/backend/.env" \
    /etc/dovecot /etc/postfix /etc/radicale \
    /var/lib/rspamd/dkim \
    /etc/nginx/sites-available 2>/dev/null || true

if [ "$INCLUDE_MAILBOXES" = "1" ]; then
    echo -e "${GREEN}[3/4] Empaquetando buzones y calendario (puede tardar)...${NC}"
    tar czf "$WORK/mail.tar.gz" -C / "${VMAIL_DIR#/}" var/lib/radicale 2>/dev/null || true
else
    echo -e "${YELLOW}[3/4] Buzones OMITIDOS (INCLUDE_MAILBOXES=0).${NC}"
fi

echo -e "${GREEN}[4/4] Cifrando el respaldo...${NC}"
OUT="$BACKUP_DIR/maquita-$TS.tar.gpg"
if [ -n "$BACKUP_GPG_RECIPIENT" ]; then
    tar cf - -C "$WORK" . | gpg --batch --yes --trust-model always \
        --encrypt --recipient "$BACKUP_GPG_RECIPIENT" --output "$OUT"
else
    tar cf - -C "$WORK" . | gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase-file "$BACKUP_PASSPHRASE_FILE" --output "$OUT"
fi
chmod 600 "$OUT"
sha256sum "$OUT" > "$OUT.sha256"

# Rotación
find "$BACKUP_DIR" -name "maquita-*.tar.gpg*" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true

SIZE="$(du -h "$OUT" | cut -f1)"
echo ""
echo -e "${GREEN}✓ Respaldo cifrado listo: $OUT ($SIZE)${NC}"
echo "  Verificación de integridad: $OUT.sha256"
echo "  Retención: $RETENTION_DAYS días."
echo -e "${YELLOW}  IMPORTANTE: copia este archivo (y la clave privada/passphrase) a OTRO lugar"
echo -e "  (otro servidor, almacenamiento externo). Un backup en el mismo disco no protege.${NC}"
