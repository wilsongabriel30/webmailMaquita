#!/usr/bin/env bash
# Programa en Proxmox el respaldo de la VM COMPLETA (vzdump), para volver a tener el servidor entero tras un
# desastre. Se ejecuta EN EL PROXMOX de la sede:
#
#   bash respaldo-vm.sh <vmid> <almacenamiento de respaldos> ["día y hora"]
#   bash respaldo-vm.sh 105 usb-respaldos "sun 01:00"
#
# El almacenamiento debe admitir respaldos (contenido «VZDump backup file»): un disco USB, un NAS o un Proxmox
# Backup Server, NUNCA el mismo disco de la VM. Conserva 4 semanales y 3 mensuales. Modo «snapshot»: la VM
# sigue funcionando. Los respaldos dentro del servidor (Panel → Respaldos, restic) complementan a este: sirven
# para devolver un sitio o un buzón; este, para devolver la máquina entera (qmrestore).
set -euo pipefail
VMID="${1:?uso: $0 <vmid> <almacenamiento> [\"sun 01:00\"]}"
ALMACEN="${2:?indique el almacenamiento de respaldos (pvesm status)}"
CUANDO="${3:-sun 01:00}"
command -v pvesh >/dev/null || { echo "Esto se ejecuta en un servidor Proxmox."; exit 1; }
qm status "$VMID" >/dev/null || { echo "No existe la VM $VMID."; exit 1; }
pvesm status --storage "$ALMACEN" --content backup >/dev/null 2>&1 && pvesm status --storage "$ALMACEN" --content backup | grep -q "$ALMACEN" \
    || { echo "El almacenamiento $ALMACEN no existe o no admite respaldos (Centro de datos → Almacenamiento → Contenido: VZDump)."; exit 1; }
DISCO_VM="$(qm config "$VMID" | sed -nE 's/^(scsi0|virtio0|sata0): ([^:]+):.*/\2/p' | head -1)"
[ "$DISCO_VM" != "$ALMACEN" ] || { echo "No respalde en el mismo almacenamiento que el disco de la VM."; exit 1; }
ID="maquina-${VMID}"
if pvesh get /cluster/backup --output-format json | grep -q "\"id\":\"${ID}\""; then
    pvesh set "/cluster/backup/${ID}" --schedule "$CUANDO" --storage "$ALMACEN" >/dev/null
    echo "Trabajo $ID actualizado."
else
    pvesh create /cluster/backup --id "$ID" --vmid "$VMID" --storage "$ALMACEN" --schedule "$CUANDO" --mode snapshot \
        --compress zstd --prune-backups "keep-weekly=4,keep-monthly=3" --enabled 1 \
        --notes-template "{{guestname}}: respaldo completo" >/dev/null
    echo "Trabajo $ID creado."
fi
pvesh get "/cluster/backup/${ID}" --output-format json-pretty | grep -E '"(schedule|storage|vmid|prune-backups)"'
echo "Para probarlo ya: vzdump $VMID --storage $ALMACEN --mode snapshot --compress zstd"
echo "Para restaurar en otra VM: qmrestore <archivo .vma.zst> <vmid nuevo> --unique 1"
