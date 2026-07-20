# Autodiscover de Outlook — dinámico y multi-dominio

## Qué hace
`POST /autodiscover/autodiscover.xml` (backend) devuelve, para CUALQUIER dominio del correo:
- `<LoginName>` = el correo COMPLETO que el cliente envió (sin tecleo del usuario; evita `user.dominio`).
- `<Server>` = host canónico (`mail.<MAIL_DOMAIN>`, ej. mail.maquita.org), el MISMO Dovecot que sirve
  todos los dominios virtuales (maquita.org, maquita.com.ec, maquitaturismo.com, …).
IMAP 993 SSL / SMTP 465 SSL. Reemplaza el `autodiscover.xml` estático que tenía `<LoginName>` vacío.

## Para que Outlook de un dominio (ej. maquita.com.ec) LLEGUE a este servicio
Outlook de `foo@maquita.com.ec` consulta `autodiscover.maquita.com.ec` y `maquita.com.ec`. Hay que
dirigirlo a nuestro servidor (donde el certificado es válido). Por CADA dominio registrado:

- **Opción A (recomendada, sin cert extra) — registro SRV:**
  `_autodiscover._tcp.<dominio>  SRV  0 0 443 autodiscover.maquita.org.`
  Outlook sigue el SRV a `autodiscover.maquita.org` (cert `*.maquita.org` válido).
- **Opción B — CNAME + cert:**
  `autodiscover.<dominio>  CNAME  autodiscover.maquita.org.` y agregar `autodiscover.<dominio>` al
  certificado (SAN); si no, Outlook rechaza el TLS por hostname.

## Config
- Host canónico: env `AUTODISCOVER_MAIL_HOST` (si no, `mail.<MAIL_DOMAIN>` del .env).
- nginx enruta `/autodiscover/autodiscover.xml` (cualquier mayúscula) al backend. El instalador usa
  esta plantilla; en producción el vhost hecho a mano debe cambiar el `alias .../autodiscover.xml`
  estático por este `proxy_pass` al backend.

## Nota de migración
Apuntar el autodiscover de un dominio que aún está en Zimbra (ej. maquita.com.ec) a VM130 SOLO cuando
sus buzones estén migrados. Thunderbird/móvil ya están cubiertos por autoconfig (`%EMAILADDRESS%`) y
el perfil `.mobileconfig`.
