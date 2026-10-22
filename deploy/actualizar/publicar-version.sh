#!/usr/bin/env bash
# Publica una versión del canal «estable»: etiqueta vX.Y.Z FIRMADA sobre main y la sube a GitHub.
# Los servidores solo instalan etiquetas firmadas por una clave de deploy/actualizar/firmantes.
#
# Uso (en el equipo que tiene la clave privada):  bash deploy/actualizar/publicar-version.sh v1.8.0
#   CLAVE_FIRMA=/ruta/a/la/clave  (por defecto /root/.ssh/firma-versiones)
#
# Parche de una rama de soporte largo (canal «estable-X.Y», docs/SOPORTE-Y-VERSIONES.md):
#   git checkout estable/1.11 && git pull
#   RAMA=estable/1.11 bash deploy/actualizar/publicar-version.sh v1.11.4
# La versión tiene que ser de esa serie (v1.11.*) y mayor que la última de la serie.
#
# Antes: lo publicado tiene que estar fusionado en main (o en la rama de soporte) con la integración
# continua en verde y probado. Las notas de la versión salen de los títulos de los commits desde la
# versión anterior.
set -euo pipefail
VERSION="${1:-}"
CLAVE="${CLAVE_FIRMA:-/root/.ssh/firma-versiones}"
RAMA="${RAMA:-main}"
[[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "uso: $0 vX.Y.Z"; exit 2; }
PATRON='v*'
if [ "$RAMA" != main ]; then
    [[ "$RAMA" =~ ^estable/([0-9]+)\.([0-9]+)$ ]] || { echo "RAMA tiene que ser main o estable/X.Y"; exit 2; }
    SERIE="v${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"
    [[ "$VERSION" == "$SERIE".* ]] || { echo "$VERSION no es de la serie $SERIE de la rama $RAMA."; exit 2; }
    PATRON="$SERIE.*"
fi
[ -f "$CLAVE" ] || { echo "No está la clave de firma ($CLAVE)."; exit 1; }
cd "$(git rev-parse --show-toplevel)"
git fetch --quiet --tags origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$RAMA")" ] || { echo "HEAD no es origin/$RAMA: haga «git checkout $RAMA && git pull» antes."; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "Hay cambios sin confirmar."; exit 1; }
git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null && { echo "$VERSION ya existe."; exit 1; }
ANTERIOR="$(git tag -l "$PATRON" --sort=-v:refname | head -1)"
if [ -n "$ANTERIOR" ] && [ "$(printf '%s\n%s\n' "$ANTERIOR" "$VERSION" | sort -V | tail -1)" != "$VERSION" ]; then
    echo "$VERSION no es mayor que $ANTERIOR."; exit 1
fi
NOTAS="$(git log --no-merges -n 80 --format='- %s' ${ANTERIOR:+$ANTERIOR..}HEAD)"  # -n y no «| head»: con pipefail, head cortaba con SIGPIPE
git -c gpg.format=ssh -c user.signingkey="$CLAVE" tag -s "$VERSION" -m "Versión $VERSION" -m "$NOTAS"
git -c gpg.format=ssh -c gpg.ssh.allowedSignersFile=deploy/actualizar/firmantes verify-tag "$VERSION"
git push origin "$VERSION"
echo "Publicada $VERSION. Los servidores con actualización automática la instalarán esta noche."
