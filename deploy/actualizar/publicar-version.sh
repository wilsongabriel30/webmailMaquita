#!/usr/bin/env bash
# Publica una versión del canal «estable»: etiqueta vX.Y.Z FIRMADA sobre main y la sube a GitHub.
# Los servidores solo instalan etiquetas firmadas por una clave de deploy/actualizar/firmantes.
#
# Uso (en el equipo que tiene la clave privada):  bash deploy/actualizar/publicar-version.sh v1.8.0
#   CLAVE_FIRMA=/ruta/a/la/clave  (por defecto /root/.ssh/firma-versiones)
#
# Antes: lo publicado tiene que estar fusionado en main con la integración continua en verde y probado
# en producción. Las notas de la versión salen de los títulos de los commits desde la versión anterior.
set -euo pipefail
VERSION="${1:-}"
CLAVE="${CLAVE_FIRMA:-/root/.ssh/firma-versiones}"
[[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "uso: $0 vX.Y.Z"; exit 2; }
[ -f "$CLAVE" ] || { echo "No está la clave de firma ($CLAVE)."; exit 1; }
cd "$(git rev-parse --show-toplevel)"
git fetch --quiet --tags origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "HEAD no es origin/main: haga «git checkout main && git pull» antes."; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "Hay cambios sin confirmar."; exit 1; }
git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null && { echo "$VERSION ya existe."; exit 1; }
ANTERIOR="$(git tag -l 'v*' --sort=-v:refname | head -1)"
if [ -n "$ANTERIOR" ] && [ "$(printf '%s\n%s\n' "$ANTERIOR" "$VERSION" | sort -V | tail -1)" != "$VERSION" ]; then
    echo "$VERSION no es mayor que $ANTERIOR."; exit 1
fi
NOTAS="$(git log --no-merges --format='- %s' ${ANTERIOR:+$ANTERIOR..}HEAD | head -80)"
git -c gpg.format=ssh -c user.signingkey="$CLAVE" tag -s "$VERSION" -m "Versión $VERSION" -m "$NOTAS"
git -c gpg.format=ssh -c gpg.ssh.allowedSignersFile=deploy/actualizar/firmantes verify-tag "$VERSION"
git push origin "$VERSION"
echo "Publicada $VERSION. Los servidores con actualización automática la instalarán esta noche."
