#!/usr/bin/env bash
# Prepara una VM Debian 13 recién creada para convertirla en la plantilla «sin personalizar».
#
#   1. Crear la VM desde la imagen cloud de Debian 13 (2 vCPU con «cpu host», 6 GB, 80 GB).
#   2. Entrar por SSH y ejecutar:  curl … | o bien copiar este archivo y  bash preparar.sh [vX.Y.Z]
#   3. bash /opt/maquita-webmail/deploy/plantilla/sellar.sh   (apaga la VM)
#   4. En Proxmox: «Convertir en plantilla». Cada clon arranca con el asistente en la consola.
#
# Trae el código en la última versión ESTABLE firmada (o la indicada) y deja el asistente activado.
# No instala ni configura nada del correo: eso lo hace el asistente en cada clon, con sus claves.
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/wilsongabriel30/webmailMaquita.git}"
APP_DIR=/opt/maquita-webmail
[ "$EUID" -eq 0 ] || { echo "Ejecutar como root."; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git whiptail curl ca-certificates openssh-server >/dev/null
if [ ! -d "${APP_DIR}/.git" ]; then
    git clone --quiet "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
git fetch --quiet --tags --force origin
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    VERSION="$(git tag -l 'v*' --sort=-v:refname | while read -r t; do
        git -c gpg.format=ssh -c gpg.ssh.allowedSignersFile=deploy/actualizar/firmantes verify-tag "$t" >/dev/null 2>&1 && { echo "$t"; break; }; done)"
    [ -n "$VERSION" ] || { echo "No hay ninguna versión estable firmada. Indique una versión o rama: bash preparar.sh <ref>"; exit 1; }
fi
git checkout --quiet --detach "$VERSION"
echo "Código en $(git describe --tags --always)"
install -d -m 755 /etc/maquita-plantilla
install -m 644 deploy/plantilla/maquita-primer-arranque.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable maquita-primer-arranque.service >/dev/null
touch /etc/maquita-plantilla/sin-configurar
echo "Listo para sellar: bash ${APP_DIR}/deploy/plantilla/sellar.sh"
