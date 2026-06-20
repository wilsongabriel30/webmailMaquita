#!/bin/bash
# Sincroniza los buzones activos de maildb -> directorio LDAP (ou=people).
# Reutiliza los hashes existentes: {SHA512-CRYPT}->{CRYPT}, {SSHA512}/{SSHA} tal cual.
# Config (URI/base/admin/clave) en /etc/maquita/ldap-sync.env (fuera del repo).
set -uo pipefail
source /etc/maquita/ldap-sync.env
PSQL="psql -h localhost -U mailserver -d maildb -tA -F $'\t'"
export PGPASSWORD   # viene de /etc/maquita/ldap-sync.env
LDIF=$(mktemp)

$PSQL -c "SELECT username, COALESCE(NULLIF(name,''),username), password FROM mailbox WHERE active ORDER BY username" \
| while IFS=$'\t' read -r user name pass; do
    [ -n "$user" ] || continue
    case "$pass" in
      '{SHA512-CRYPT}'*) pass="{CRYPT}${pass#\{SHA512-CRYPT\}}";;
    esac
    cnb=$(printf '%s' "$name" | base64 -w0)
    printf 'dn: uid=%s,ou=people,%s\nobjectClass: inetOrgPerson\nuid: %s\ncn:: %s\nsn:: %s\nmail: %s\nuserPassword: %s\n\n' \
      "$user" "$LDAP_BASE" "$user" "$cnb" "$cnb" "$user" "$pass" >> "$LDIF"
  done

echo "Cargando $(grep -c '^dn:' "$LDIF") usuarios en LDAP..."
ldapadd -c -x -H "$LDAP_URI" -D "$LDAP_ADMIN_DN" -w "$LDAP_ADMIN_PW" -f "$LDIF" 2>&1 \
  | grep -ciE 'adding|already' >/dev/null
# resumen
TOTAL=$(ldapsearch -x -H "$LDAP_URI" -D "$LDAP_ADMIN_DN" -w "$LDAP_ADMIN_PW" -b "ou=people,$LDAP_BASE" "(uid=*)" dn 2>/dev/null | grep -c '^dn:')
echo "LDAP ahora tiene $TOTAL usuarios en ou=people."
rm -f "$LDIF"
