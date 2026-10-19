# VM lista para instalar (plantilla «sin personalizar»)

Una plantilla de Proxmox con el código y el asistente de primer arranque, **sin nada configurado**. Cada
organización recibe un clon; en su primer arranque el asistente pregunta lo suyo e instala todo con claves
propias: correo y webmail, chat institucional, panel, sitios web, DNS, cortafuegos y actualizaciones
automáticas.

**Nunca se clona una VM ya configurada**: repetiría en todas las organizaciones las claves DKIM, los
secretos de sesión y las contraseñas de las bases. `sellar.sh` se niega si el correo está instalado.

## 1. Preparar la plantilla (una vez por versión)

1. En Proxmox, una VM desde la imagen cloud de Debian 13 (`debian-13-genericcloud-amd64.qcow2`):
   2 vCPU con `cpu host` (Tableros/BI necesita x86-64-v2), 6 GB de RAM y 80 GB de disco, con unidad
   cloud-init (usuario `root` y su clave SSH, IP).
2. Por SSH:
   ```bash
   curl -fsSLo preparar.sh https://raw.githubusercontent.com/<org>/<repo>/main/deploy/plantilla/preparar.sh
   bash preparar.sh            # última versión estable firmada (o: bash preparar.sh v1.8.0)
   bash /opt/maquita-webmail/deploy/plantilla/sellar.sh
   ```
   `sellar.sh` borra las claves SSH de la máquina, el machine-id, las claves autorizadas, el historial, los
   registros y los datos de cloud-init, bloquea la contraseña de root y apaga la VM.
3. En Proxmox: «Convertir en plantilla».

## 2. Entregar a una organización

- **Clon en el mismo Proxmox**: «Clonar» (completo) y, en «Cloud-Init», la IP y la clave SSH de quien la
  administrará. Arrancar.
- **Otro Proxmox (la sede)**, en el Proxmox que tiene la plantilla:
  ```bash
  bash /opt/maquita-webmail/deploy/plantilla/exportar.sh 9001 /var/lib/vz/dump v1.8.0   # o la ruta del repositorio
  ```
  Deja `plantilla-servidor-v1.8.0/` (≈ 1,6 GB): la copia de Proxmox `vzdump-qemu-….vma.zst` (no cambiar
  su nombre: `qmrestore` lo necesita), el disco `plantilla.qcow2` comprimido, `importar.sh`, `SHA256SUMS` y
  `LEEME.txt`. La copia tarda unos 15 minutos (recorre el disco de 80 GB aunque esté casi vacío).
  Se lleva la carpeta a la sede (disco USB, `scp`) y allá:
  ```bash
  bash importar.sh                         # comprueba las sumas y restaura la plantilla (vmid libre, local-lvm)
  bash importar.sh 9001 otro-almacenamiento
  QCOW2=1 bash importar.sh                 # desde el qcow2, si no se llevó la copia de Proxmox
  ```
  Una copia alterada o dañada se rechaza antes de tocar nada; si la restauración falla a medias, no queda una
  VM a medio crear. La plantilla importada no trae la red de origen: cada clon pone la suya en Cloud-Init.
- **Otro hipervisor** (KVM/libvirt…): `plantilla.qcow2` es el disco (Debian 13 con cloud-init); VM con
  2 vCPU x86-64-v2, 6 GB y una fuente NoCloud de cloud-init para la red y la clave SSH.

## 3. Primer arranque

En la consola de la VM (Proxmox → Consola) aparece el asistente:

1. Red: mantener la actual (DHCP o cloud-init) o poner una IP fija (systemd-networkd; cloud-init deja de
   tocar la red).
2. Dominio principal, nombre de la institución y nombre corto, correo del responsable técnico.
3. Clave inicial (panel, aviso del navegador y primer buzón) y nueva clave de root.
4. Redes o IP de administración (SSH y panel 8443; el cortafuegos cierra el resto).

Luego instala, por este orden: correo y webmail (`deploy/webmail/instalar.sh` con la clave elegida),
sitios web, DNS, cortafuegos, chat (`deploy/chat/instalar.sh`, en el mismo origen que el correo) y
actualizaciones; aplica la identidad (nombre en el correo, el panel, el Drive y las páginas) y pone el nombre
`mail.<dominio>` a la máquina. Al terminar deja `/root/LEEME-primer-arranque.txt` con los primeros pasos y el
registro completo en `/root/instalacion-primer-arranque.log` (tiene claves internas: no compartirlo). Si algo
falla, se corrige la causa y se vuelve a lanzar: los pasos se repiten sin problema.

También por SSH: `bash /opt/maquita-webmail/deploy/plantilla/primer-arranque.sh`.

### Sin preguntas (varias sedes)

Un archivo `/etc/maquita-plantilla/respuestas` (se borra al leerlo):

```bash
DOMINIO=example.org
NOMBRE="Institución de Ejemplo"
CORTO="Ejemplo"
CORREO=tecnologia@example.org
CLAVE_INICIAL=...
CLAVE_ROOT=...
ADMIN_IPS="192.168.1.0/24"
RED=mantener            # o: RED=fija IP=192.0.2.10/24 PUERTA=192.0.2.1 DNS="9.9.9.9 1.1.1.1"
```

## 4. Después

Al entrar al panel aparece **«Primeros pasos»**: subir el logo y completar la información de la institución
(descripción, lema, teléfono, correo, web, color y redes; «Guardar y aplicar en todo» u «Omitir por ahora») y la
lista de lo que queda, cada punto con «hecho» u «omitir». «Terminar» deja de mostrarla; «Más tarde» la pospone y un
aviso arriba la retoma. En resumen, desde el panel `https://mail.<dominio>:8443`: cambiar la clave inicial, subir el logo y «Aplicar en todo», «Nuevo
dominio» con el dominio principal (zona DNS, DKIM, sitio, primer buzón), registros en el registrador,
puertos en el router y «Certificado del correo». Las versiones nuevas llegan solas cada noche
(`docs/ACTUALIZACIONES.md`).
