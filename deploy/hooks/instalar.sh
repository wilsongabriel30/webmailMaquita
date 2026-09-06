#!/bin/bash
# Instala el Guardián pre-commit en este clon y prepara el fichero local de
# patrones prohibidos. Ejecutar desde la raíz del repositorio:
#   bash deploy/hooks/instalar.sh
#
# El fichero de patrones (.git/guardian-patrones-locales) NO se versiona:
# contiene lo que el Guardián debe impedir que se publique, así que no puede
# vivir en lo que se publica. Se crea a partir de la plantilla y hay que
# rellenarlo a mano, una expresión regular por línea.
set -e
RAIZ=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "Ejecutar dentro del repositorio."; exit 1; }
cd "$RAIZ"

install -m 755 deploy/hooks/pre-commit .git/hooks/pre-commit
echo "Guardián instalado en .git/hooks/pre-commit"

if [ ! -f .git/guardian-patrones-locales ]; then
    install -m 600 deploy/hooks/guardian-patrones-locales.ejemplo .git/guardian-patrones-locales
    echo "Creado .git/guardian-patrones-locales a partir de la plantilla."
    echo "RELLÉNALO: hasta que tenga patrones, el Guardián no bloquea secretos ni términos vetados."
else
    echo ".git/guardian-patrones-locales ya existe: no se toca."
fi

command -v python3 >/dev/null || echo "AVISO: sin python3 no funciona el barrido de datos personales."
