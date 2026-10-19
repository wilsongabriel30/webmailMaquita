# Respaldos (panel → Protección → Respaldos)

Dos capas que se complementan:

| Capa | Para qué | Dónde |
|---|---|---|
| **Respaldos del servidor** (restic, desde el panel) | Devolver un sitio web o los correos de un buzón; tener los datos fuera del servidor | Dentro de la VM y, opcional, en un destino externo |
| **Respaldo de la VM completa** (vzdump de Proxmox) | Volver a tener el servidor entero tras un desastre (`qmrestore`) | Un almacenamiento de respaldos del Proxmox (USB, NAS, PBS), nunca el disco de la VM |

## Respaldos del servidor (restic)

```bash
sudo bash deploy/webmail/instalar-app.sh respaldos   # lo hace solo el primer arranque de la plantilla
```

- **Qué**: cada base de datos en su archivo (PostgreSQL y MariaDB), correo y calendarios, Drive, sitios web, `/etc`
  (configuración, certificados, zonas, sitios, cortafuegos), claves DKIM, secretos (`.env`) y el código sin
  dependencias. Restic guarda solo lo que cambió y lo cifra con la **clave de recuperación**
  (`/etc/maquita-respaldos/clave`).
- **Cuándo**: cada noche a las 02:30 (antes de las actualizaciones de las 03:30) y con «Respaldar ahora».
- **Cuánto**: los 10 últimos siempre, más 7 diarios, 4 semanales y 6 mensuales (configurable). Los respaldos
  «antes-de-restaurar» no caducan.
- **Destino externo** (recomendado; sin él, una avería del disco se lleva también los respaldos): SFTP a otro
  servidor (autorizar allí la clave SSH pública que muestra el panel), servidor REST de restic, S3 compatible o un
  disco montado. Cada respaldo se copia allí con `restic copy`. Las credenciales no vuelven al panel.
- **Clave de recuperación**: el panel la muestra («Ver claves») para guardarla FUERA del servidor. Sin ella los
  respaldos externos no se pueden abrir.

### Restaurar (panel)

- **Correos de un buzón**: los del respaldo aparecen en una carpeta nueva `Restaurado-AAAAMMDD-HHMM` del mismo buzón,
  con sus subcarpetas (`doveadm import`), suscrita para que se vea en el webmail. No se borra ni se cambia nada de lo
  actual: la persona recupera lo que necesite y luego se borra la carpeta.
- **Un sitio web**: archivos y bases (la principal y las adicionales) vuelven a como estaban. Antes se respalda el
  estado actual (etiqueta `antes-de-restaurar`), así que se puede deshacer restaurando esa instantánea. Si falta o
  no se puede leer algún volcado, no se toca nada.
- **Comprobar**: lee un 5 % de los datos del repositorio y restaura la base del correo en una base desechable.
  Hágalo cada mes.

Registros en `/var/log/maquita-respaldos/`; estado en `/var/lib/maquita-respaldos/estado.json`.

## Respaldo de la VM completa (Proxmox)

En el Proxmox de la sede:

```bash
bash /ruta/del/repositorio/deploy/plantilla/respaldo-vm.sh <vmid> <almacenamiento de respaldos> "sun 01:00"
```

Crea un trabajo de vzdump semanal en modo snapshot (la VM sigue funcionando), 4 semanales y 3 mensuales. Rechaza
un almacenamiento que no admita respaldos o que sea el del disco de la VM. Restaurar: `qmrestore <archivo>
<vmid nuevo> --unique 1`.

## Pendiente

Reconstruir un servidor entero **solo** desde restic (sin el respaldo de Proxmox) exige recrear roles de las bases,
usuarios del sistema y claves en el orden correcto: no está automatizado ni probado. Hasta entonces, el respaldo de
la VM completa es el camino para un desastre.

El respaldo anterior (`deploy/webmail/backup`, tar cifrado con GPG, `docs/BACKUP-RESTAURACION.md`) sigue
funcionando donde ya se usa.
