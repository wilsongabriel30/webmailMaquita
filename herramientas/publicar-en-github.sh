#!/usr/bin/env bash
# =============================================================================
#  Publicar el Drive Maquita (Almacén de VM 101) en GitHub
# -----------------------------------------------------------------------------
#  El servicio vive en /home/sistemas/almacen-maquita (repo git local, rama main)
#  y se publica como carpeta drive-maquita/ del repo webmailMaquita mediante
#  git subtree, desde el clon /root/repos/webmailMaquita.
#
#  USO (como root, tras terminar y probar un cambio):
#     publicar-en-github.sh "mensaje del commit"
#
#  Qué hace: 1) commit local de todo lo pendiente en almacen-maquita (como
#  usuario sistemas)  2) trae ese commit al clon con subtree pull  3) push.
#  El guardián de secretos/IA/.bak de FARO revisa antes de publicar.
# =============================================================================
set -euo pipefail
MENSAJE="${1:-}"
[ -n "$MENSAJE" ] || { echo "Uso: $0 \"mensaje del commit\""; exit 1; }
ALMACEN=/home/sistemas/almacen-maquita
CLON=/root/repos/webmailMaquita
GUARDIAN=/home/sistemas/Maquita/scripts/guardian.sh

cd "$ALMACEN"
if [ -n "$(sudo -u sistemas git status --porcelain)" ]; then
  echo "== Revisando con el guardián lo que cambió..."
  sudo -u sistemas git status --porcelain | awk '{print $2}' | grep -v -i bak | xargs -r bash "$GUARDIAN"
  sudo -u sistemas git add -A
  sudo -u sistemas git commit -q -m "$MENSAJE"
  echo "== Commit local: $(sudo -u sistemas git log --oneline -1)"
else
  echo "== Sin cambios locales pendientes; se publica lo ya commiteado."
fi

cd "$CLON"
git pull -q --ff-only origin main
git subtree pull -q --prefix=drive-maquita "$ALMACEN" main -m "Drive Maquita: $MENSAJE"
git push -q origin main
echo "== Publicado en GitHub: $(git log --oneline -1)"
