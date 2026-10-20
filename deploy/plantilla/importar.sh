#!/usr/bin/env bash
# Importa la plantilla «sin personalizar» en este Proxmox (la carpeta que deja exportar.sh).
#
#   bash importar.sh [vmid] [almacenamiento]        desde la copia de Proxmox vzdump-qemu-….vma.zst (lo normal)
#   QCOW2=1 bash importar.sh [vmid] [almacenamiento] desde plantilla.qcow2 (si no se trajo la copia de Proxmox)
#
# Comprueba las sumas, restaura y deja una PLANTILLA lista para «Clonar». No arranca nada.
set -euo pipefail
cd "$(dirname "$0")"
command -v qm >/dev/null || { echo "Esto se ejecuta en un servidor Proxmox."; exit 1; }
VMID="${1:-$(pvesh get /cluster/nextid)}"
ALMACEN="${2:-local-lvm}"
[[ "$VMID" =~ ^[0-9]{3,9}$ ]] || { echo "vmid no válido."; exit 1; }
qm status "$VMID" >/dev/null 2>&1 && { echo "Ya existe una VM con el número $VMID: elija otro."; exit 1; }
pvesm status --storage "$ALMACEN" >/dev/null 2>&1 || { echo "No existe el almacenamiento $ALMACEN (pvesm status)."; exit 1; }

echo "[1/3] Sumas de comprobación..."
if [ -n "${QCOW2:-}" ]; then grep -E ' (plantilla\.qcow2)$' SHA256SUMS | sha256sum -c --quiet -
else grep -E ' vzdump-qemu-[^ ]+\.vma\.zst$' SHA256SUMS | sha256sum -c --quiet -; fi
echo "   correctas"

echo "[2/3] Restaurando como VM $VMID en $ALMACEN..."
# Si algo falla a medias, no se deja una VM a medio crear.
trap 'echo "Falló la importación: se quita la VM $VMID a medio crear."; qm destroy "$VMID" --purge >/dev/null 2>&1 || true' ERR
if [ -z "${QCOW2:-}" ]; then
    COPIA="$(ls vzdump-qemu-*.vma.zst | head -1)"
    qmrestore "$COPIA" "$VMID" --storage "$ALMACEN" --unique 1 >/dev/null
else
    qm create "$VMID" --name plantilla-servidor-org --memory 6144 --cores 2 --cpu host \
        --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-single --ostype l26 --vga std >/dev/null
    qm importdisk "$VMID" plantilla.qcow2 "$ALMACEN" >/dev/null
    DISCO="$(qm config "$VMID" | sed -nE 's/^unused0: (.+)$/\1/p')"
    qm set "$VMID" --scsi0 "${DISCO},discard=on,iothread=1,ssd=1" --boot order=scsi0 --ide2 "${ALMACEN}:cloudinit" --ciuser root >/dev/null
    qm resize "$VMID" scsi0 80G >/dev/null
fi

trap - ERR
echo "[3/3] Plantilla..."
qm config "$VMID" | grep -q '^template: 1' || qm template "$VMID" >/dev/null
# La red de la sede de origen no sirve aquí: cada clon pone la suya en Cloud-Init.
qm set "$VMID" --delete ipconfig0,sshkeys,nameserver,searchdomain >/dev/null 2>&1 || true
qm config "$VMID" | grep -E '^(name|memory|cores|scsi0|template):'
echo "Listo. En Proxmox: VM $VMID → Clonar (clon completo) → Cloud-Init (IP y clave SSH) → Iniciar → Consola."
