# Z-Push — ActiveSync para Maquita Mail

Sincronización de **correo, calendario, contactos y tareas** por Exchange ActiveSync con Outlook
de escritorio (clásico y nuevo), Android e iOS. Componente de primera clase desde 1.7.8
(`DECISIONES.md` D-9, corregida): la dirección y las gerencias trabajan en Outlook, que solo
sincroniza calendario y contactos por ActiveSync.

## Un solo origen de datos

Z-Push no guarda correo, eventos ni contactos: los sirve desde donde ya están, así el webmail, el
teléfono y Outlook ven lo mismo.

| Tipo | Backend de Z-Push | Origen |
|---|---|---|
| Correo | `BackendIMAP` | Dovecot (IMAP) y Postfix (SMTP) |
| Calendario y **tareas** | `BackendCalDAV` | Radicale (CalDAV), el mismo del webmail |
| Contactos | `BackendCardDAV` | Radicale (CardDAV), el mismo del webmail |

`BackendCombined` une los tres. Solo hay estado propio de Z-Push (qué vio cada dispositivo) en
`/var/lib/z-push`.

## Arquitectura

```
Outlook / Android / iOS
        │ ActiveSync (HTTPS 443, /Microsoft-Server-ActiveSync)
        ▼
    nginx (snippets/maquita-apps/activesync.conf)
        │ FastCGI → 127.0.0.1:9000
        ▼
  contenedor «zpush» (php:8.3-fpm-bookworm + Z-Push 2.7.6)
     ├── IMAP/SMTP → host.docker.internal (Dovecot 993, Postfix 465)
     └── CalDAV/CardDAV → host.docker.internal:5232 (Radicale)
```

El **autodiscover** (Outlook clásico, nuevo Outlook, Android, iOS) lo sirve el **backend del
correo**, no Z-Push: `/autodiscover/autodiscover.xml` (esquema `outlook` para IMAP/SMTP y esquema
`mobilesync` para ActiveSync) y `/autodiscover/autodiscover.json` (v2, el que usa el nuevo
Outlook). Ver `backend/app/autodiscover_router.py`.

## Instalar o actualizar

```bash
bash deploy/z-push/instalar.sh midominio.org
# → construye la imagen (base actual + apt-get upgrade), escribe /opt/z-push-docker/*.php,
#   arranca el contenedor «zpush» en 127.0.0.1:9000 y deja el snippet de nginx.
# Añade en el server{} HTTPS del correo:  include snippets/maquita-apps/activesync.conf;
nginx -t && systemctl reload nginx
```

Requisitos: Docker, Radicale escuchando también en la IP del puente de Docker
(`hosts = 127.0.0.1:5232, 172.17.0.1:5232` en `/etc/radicale/config`), DNS
`autodiscover.midominio.org` → el servidor (con certificado que lo cubra: `emitir-certificado.sh`).

Las configuraciones viven en `/opt/z-push-docker/` y se montan en el contenedor: editarlas no
exige reconstruir (`docker restart zpush`). Los archivos de `configs/` de este directorio son la
plantilla (`mail.example.org` se sustituye por tu servidor).

## Operación

- **Reconstrucción mensual** con base actualizada: `bash deploy/z-push/instalar.sh` (conserva
  estado y configuración). El CI escanea la imagen con Trivy y bloquea solo por avisos con
  corrección disponible.
- **Diagnóstico**: `docker exec zpush z-push-top` (sesiones en vivo), `docker exec zpush
  z-push-admin -a list -u correo@dominio` (dispositivos de una cuenta), `/var/log/z-push/z-push.log`
  y `z-push-error.log`, `/var/log/nginx/activesync-*.log`. Detalle y configuración de Outlook en
  `OPERACION.md` («Z-Push / ActiveSync»).
- **Quitar un dispositivo**: `docker exec zpush z-push-admin -a remove -u correo -d <deviceid>`.
- **Borrar el estado de una cuenta** (resincronización completa): `docker exec zpush z-push-admin
  -a clearloop` / `-a resync -u correo`.

## Alcance y límites

- ActiveSync 14.1 (correo, calendario, contactos, tareas, notas no).
- Sin políticas de dispositivo forzadas (`LOOSE_PROVISIONING`): el correo no exige PIN ni borrado
  remoto; se documenta a propósito.
- Un usuario se autentica con su correo completo y su contraseña de buzón (la misma de IMAP; el
  segundo factor no aplica a ActiveSync, ver `DECISIONES.md` D-5).
