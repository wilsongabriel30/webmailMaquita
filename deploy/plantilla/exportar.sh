#!/usr/bin/env bash
# Exporta la plantilla «sin personalizar» para llevarla al Proxmox de otra sede (o a otro hipervisor).
# Se ejecuta EN EL PROXMOX que tiene la plantilla:
#
#   bash exportar.sh <vmid de la plantilla> [carpeta de destino] [etiqueta]
#   bash exportar.sh 9001 /var/lib/vz/dump v1.8.0
#
# Deja en <carpeta>/plantilla-servidor-<etiqueta>/:
#   vzdump-qemu-….vma.zst  copia de Proxmox (importar.sh o qmrestore; qmrestore exige ese nombre): VM completa
#   plantilla.qcow2     solo el disco, comprimido: para otros hipervisores (KVM/libvirt, …) o Proxmox sin vzdump
#   importar.sh         instalador en el Proxmox de destino
#   SHA256SUMS          sumas de comprobación (importar.sh las verifica antes de nada)
#   LEEME.txt           pasos
set -euo pipefail
ORIGEN="$(cd "$(dirname "$0")" && pwd)"
VMID="${1:?uso: $0 <vmid de la plantilla> [carpeta] [etiqueta]}"
CARPETA="${2:-/var/lib/vz/dump}"
ETIQUETA="${3:-$(date +%Y%m%d)}"
[[ "$ETIQUETA" =~ ^[A-Za-z0-9._-]{1,40}$ ]] || { echo "Etiqueta no válida."; exit 1; }
command -v qm >/dev/null || { echo "Esto se ejecuta en un servidor Proxmox."; exit 1; }
qm config "$VMID" | grep -q '^template: 1' || { echo "La VM $VMID no es una plantilla (bash sellar.sh y «Convertir en plantilla»)."; exit 1; }
if qm config "$VMID" | grep -qE '^(ipconfig0|sshkeys|nameserver):'; then
    echo "AVISO: la plantilla tiene IP, claves SSH o DNS de cloud-init de ESTA red; cada sede pone los suyos."
fi
SALIDA="${CARPETA}/plantilla-servidor-${ETIQUETA}"
mkdir -p "$SALIDA"; cd "$SALIDA"
TMP="$(mktemp -d "${CARPETA}/.exportar-XXXX")"; trap 'rm -rf "$TMP"' EXIT

echo "[1/4] Copia de Proxmox (vzdump; con un disco de 80 GB tarda unos 15 minutos)..."
# Se conserva el nombre que pone vzdump: qmrestore lo necesita para reconocer la copia.
if ls vzdump-qemu-*.vma.zst >/dev/null 2>&1 && [ -z "${REHACER:-}" ]; then
    echo "   ya hay una copia en esta carpeta: se reutiliza (REHACER=1 para hacerla de nuevo)"
else
    rm -f vzdump-qemu-*.vma.zst
    vzdump "$VMID" --mode stop --compress zstd --dumpdir "$TMP" >/dev/null
    mv "$TMP"/vzdump-qemu-"$VMID"-*.vma.zst .
fi

echo "[2/4] Disco qcow2 comprimido..."
DISCO="$(qm config "$VMID" | sed -nE 's/^(scsi0|virtio0|sata0): ([^,]+).*/\2/p' | head -1)"
RUTA="$(pvesm path "$DISCO")"
# En LVM, el disco de una plantilla queda desactivado (y marcado para no activarse solo): se activa
# mientras se copia y se deja como estaba.
ACTIVADO=""
if [ ! -e "$RUTA" ] && [[ "$RUTA" =~ ^/dev/([^/]+)/([^/]+)$ ]]; then
    lvchange -ay -K "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}" && ACTIVADO="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
fi
qemu-img convert -O qcow2 -c "$RUTA" plantilla.qcow2
[ -n "$ACTIVADO" ] && lvchange -an "$ACTIVADO"

echo "[3/4] Importador y guía..."
install -m 755 "${ORIGEN}/importar.sh" importar.sh
cat > LEEME.txt <<LEEME
Plantilla de servidor de correo, chat, panel y sitios — ${ETIQUETA}
Sin personalizar: cada servidor que salga de ella genera sus propias claves en el primer arranque.

En el Proxmox de la sede (copiar esta carpeta, p. ej. con un disco USB o scp):
  bash importar.sh                    # restaura la plantilla desde la copia de Proxmox (vmid libre, almacenamiento local-lvm)
  bash importar.sh 9001 otro-almacen  # vmid y almacenamiento concretos

Después, en la interfaz de Proxmox:
  1. Clic derecho en la plantilla → Clonar → «Clon completo», con el nombre del servidor.
  2. En el clon → Cloud-Init: IP/CIDR y puerta de enlace (o DHCP), servidor DNS y la clave SSH de quien
     lo administrará. CPU tipo «host» (ya viene así). Aumentar disco si hace falta.
  3. Iniciar y abrir la Consola: el asistente pregunta dominio, institución, claves y redes de
     administración, e instala todo (5 a 40 minutos según la conexión).
  4. Entrar al panel https://mail.<dominio>:8443: aparece «Primeros pasos» (logo e información).

Otro hipervisor: plantilla.qcow2 es el disco (Debian 13 con cloud-init). Crear una VM UEFI/BIOS con
ese disco, 2 vCPU con soporte x86-64-v2, 6 GB de RAM y una fuente de datos de cloud-init (NoCloud)
para la red y la clave SSH.

Comprobar las sumas a mano: sha256sum -c SHA256SUMS
LEEME

echo "[4/4] Sumas de comprobación..."
sha256sum vzdump-qemu-*.vma.zst plantilla.qcow2 importar.sh > SHA256SUMS
ls -lh "$SALIDA"
echo "Listo: $SALIDA"
