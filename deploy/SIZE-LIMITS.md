# Limite de tamano de adjuntos — fuente unica

Todo el limite de tamano se deriva de **`MAX_ATTACHMENT_MB`** (en `.env`), el tamano
maximo del adjunto REAL en MB. Las demas capas se calculan solas:

    nginx client_max_body_size  >=  postfix message_size_limit  >=  MAX_ATTACHMENT_MB * 1.37

(1.37 = inflacion al codificar el adjunto en base64 dentro del correo.)

## Como se aplica
`deploy/tools/aplicar-limites-tamano.sh [MAX_MB]`:
1. Genera `/etc/nginx/snippets/maquita-max-body.conf` con `client_max_body_size`.
2. `postconf -e message_size_limit=...`.
3. Da lectura de `/var/log/mail.log` al usuario del backend (grupo `adm` + ACL) — evita el
   `PermissionError: [Errno 13]` en bucle de la auditoria/antifraude (Debian 13, junto al rsyslog del 15-jun).
4. `nginx -t && reload`, `postfix reload`.

El instalador (`deploy/webmail/instalar.sh`) ya lo ejecuta y compila el frontend con
`VITE_MAX_ATTACHMENT_MB` para validar/mostrar el limite en el cliente.

## IMPORTANTE: proxy frontal
Si hay un **reverse proxy delante** (otro host/sitio), nginx por defecto limita el body a **1 MB**
y rechaza con **413** ANTES de llegar al backend. En el vhost del proxy frontal hay que:

    include snippets/maquita-max-body.conf;   # dentro del server { }

y correr ahi tambien `aplicar-limites-tamano.sh <MAX_MB>`. Si no, los adjuntos grandes fallan
aunque el servidor de correo este bien configurado.
