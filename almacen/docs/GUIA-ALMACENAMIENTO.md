# Guía de almacenamiento: dónde viven los archivos y cómo moverlos a donde quieras

> **Para quién:** administradores de una instalación del Almacén. Explica dónde
> se guardan físicamente los archivos de los usuarios y cómo apuntarlos a un
> disco externo, un NAS, otro servidor o una nube (Google Drive/OneDrive) —
> desde el propio panel, sin tocar código. Un sinfín de posibilidades con el
> mismo proyecto.

## 1. Dónde viven los archivos

Los archivos son **archivos normales en una carpeta del servidor** (el disco es
la fuente de verdad; la base de datos solo guarda metadatos: compartidos,
papelera, versiones, cuotas). La carpeta raíz se define, en orden de prioridad:

1. Lo elegido desde el panel (se guarda en la BD, clave `raiz_datos`) — **gana siempre**.
2. La variable `ALMACEN_RAIZ_DATOS` del `.env`.
3. El default: `/opt/maquita-webmail/almacen/datos`.

Estructura dentro de la raíz (no la toques a mano):

```
<raíz>/
├── 14/                  ← un directorio por usuario (su id numérico)
│   ├── archivos/        ← su unidad ("Mis archivos")
│   ├── papelera/        ← lo eliminado (restaurable por el usuario)
│   ├── versiones/       ← historial de versiones de sus archivos
│   └── retencion/       ← papelera vaciada (solo admins, 90 días)
├── 187/
│   └── ...
└── _unidades/           ← unidades compartidas de equipo
```

> Gracias a la deduplicación, dos archivos idénticos (aunque sean de usuarios
> distintos) ocupan el espacio de UNO (enlaces duros al mismo contenido).

## 2. Cambiarlo desde el panel (sin comandos)

Como administrador, abre el explorador (`https://TU-DOMINIO/drive`) →
menú lateral → **Configuración** → **Almacenamiento**:

- Ves el **destino actual**, su espacio usado/libre, y una lista de
  **destinos candidatos**: todos los discos y monturas que el servidor ya
  tiene conectados (particiones, USB montados, NAS por NFS/SMB, nubes rclone).
- Eliges uno → **"Usar este destino"** → efecto inmediato: los archivos nuevos
  se guardan ahí (se crea una subcarpeta `almacen-datos` para no mezclar).
- Si el destino aún no está conectado, el panel te **genera el comando exacto**
  para conectarlo (lo corres una vez como root y reaparece como candidato).

## 3. Recetas por tipo de destino

### Disco duro externo (USB)
```bash
lsblk                                   # identifica el disco (ej: /dev/sdb1)
mkdir -p /mnt/disco-externo
mount /dev/sdb1 /mnt/disco-externo
# permanente (sobrevive reinicios):
echo "/dev/sdb1 /mnt/disco-externo auto defaults,nofail 0 0" >> /etc/fstab
```
Luego panel → Almacenamiento → elegir `/mnt/disco-externo`.

### NAS o otro servidor (NFS — lo típico entre servidores Linux)
```bash
apt install -y nfs-common
mkdir -p /mnt/nas
mount -t nfs IP_DEL_NAS:/ruta/exportada /mnt/nas
echo "IP_DEL_NAS:/ruta/exportada /mnt/nas nfs defaults,_netdev,nofail 0 0" >> /etc/fstab
```

### NAS o compartido de Windows (SMB/CIFS)
```bash
apt install -y cifs-utils
mkdir -p /mnt/nas-windows
mount -t cifs //IP_DEL_NAS/compartido /mnt/nas-windows -o username=USUARIO,password=CLAVE,uid=root
```

### Google Drive, OneDrive u otra nube (rclone)
```bash
apt install -y rclone
rclone config        # asistente: crea un "remoto" (elige drive, onedrive, s3, ...)
mkdir -p /mnt/nube
rclone mount minube: /mnt/nube --vfs-cache-mode full --allow-other --daemon
```
> Ojo: una nube montada es MÁS LENTA que un disco local o un NAS de red
> local. Sirve muy bien como destino de RESPALDO o para instalaciones
> pequeñas; para uso intensivo, prefiere disco/NAS.

## 4. Migrar los archivos existentes al destino nuevo

Cambiar el destino en el panel afecta a los archivos NUEVOS. Para llevarte
los existentes:

```bash
# 1. Detén el servicio un momento (ventana corta, avisa a los usuarios)
systemctl stop maquita-almacen

# 2. Copia TODO preservando permisos y enlaces duros (la -H importa: es la deduplicación)
rsync -aH --info=progress2 /ruta/raiz/vieja/ /ruta/raiz/nueva/

# 3. Apunta el almacén a la raíz nueva (o hazlo desde el panel al arrancar)
#    (el panel guarda en BD; esto es el equivalente manual)
#    UPDATE config_kv SET valor='/ruta/raiz/nueva' WHERE clave='raiz_datos';

# 4. Arranca y verifica
systemctl start maquita-almacen
# entra al explorador: deben verse los mismos archivos
```

## 5. Respaldos (la pregunta que salva empleos)

Respaldar TODO el almacén = **2 cosas**:
1. La carpeta raíz de datos (`rsync -aH` a otro disco/NAS/nube).
2. Un dump de la base `almacen`: `pg_dump -U almacen almacen > almacen.sql`.

Con esos dos elementos puedes reconstruir la instalación completa en
cualquier servidor (restaurar BD + copiar carpeta + apuntar la raíz).

## Relacionado
- Instalación desde cero: `GUIA-PASO-A-PASO.md`
- OnlyOffice: `GUIA-ONLYOFFICE.md` · Lecciones: `LECCIONES-ONLYOFFICE.md`
