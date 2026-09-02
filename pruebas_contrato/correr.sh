#!/bin/bash
# Ejecuta la suite de contrato de la Nube.
#   bash correr.sh            → contra el sistema actual (FARO + Nextcloud)
#   bash correr.sh almacen    → contra el Almacén Maquita
# Verde en ambos = el Almacén es compatible por definición.
export OBJETIVO_CONTRATO="${1:-faro}"
cd /home/sistemas/Maquita || exit 1
echo "── Suite de contrato contra: $OBJETIVO_CONTRATO ──"
exec ./venv/bin/python3 -m unittest discover -s /home/sistemas/almacen-maquita/pruebas_contrato -v
