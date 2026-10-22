# Vigilantes del servidor de correo

Guiones que avisan (y en algunos casos reparan) antes de que un usuario note el problema. Nacieron en
el servidor de producción tras incidentes reales y aquí están generalizados: no llevan direcciones ni
nombres propios.

| Vigilante | Cuándo | Qué hace |
|---|---|---|
| `vigila-entrega-local.sh` | cron, cada 5 min | Avisa si el correo deja de entrar a los buzones (caídas de LMTP, entregas locales diferidas, cola). No usa tope diario: es crítico. |
| `guardian-web-correo` | timer, cada minuto | Levanta servicios caídos (máx. 3 por hora; nginx solo si `nginx -t` valida) y prueba el webmail por HTTPS, contra el propio servidor y por su nombre público (DNS normal; si solo falla este, aviso «desde Internet no responde», nunca reinicio). Avisa si fail2ban tiene baneado al proxy de confianza (`lib-proxy.sh`, docs/PROXY-CONFIABLE.md). |
| `vigilar-milter.sh` (en `deploy/hardening/`) | timer, cada 3 min | Avisa si el milter DLP no responde y el correo pasa sin inspección. |
| `vigilante-correo.sh` | cron, cada minuto | Señales de intrusión: ejecutables en rutas temporales u ocultas, procesos borrados disfrazados, tareas de usuarios de servicio, unidades nuevas, cortafuegos abierto. Neutraliza solo lo inequívoco. |
| `mail-health-check.sh` | cron, cada 5 min | Cola de Postfix, disco de los buzones y vencimiento del certificado del correo. |
| `verificar-config-panel.sh` | timer, diario | Avisa si los valores prestados del correo al panel (`WEBMAIL_*`) se desalinean. Compara huellas, nunca valores. |
| `informe-diario-correo.sh` | cron, 06:30 | Informe pflogsumm del día anterior en `/var/log/informe-diario-correo/` (no envía nada). |

**A quién avisan** (`lib-avisos.sh`): `ORG_CORREOS_AVISOS` de `/etc/maquita-mail/organizacion.env`; si no
existe, el administrador del panel (`outbound_anomaly_config.notify_admin`); si tampoco, `postmaster@<dominio>`.
Conviene incluir una dirección externa: si el propio servidor deja de recibir, el aviso llega igual.
Casi todo sale por `aviso-limitado` (tope de 8 avisos al día entre todos, `AVISO_TOPE_DIARIO`).
Los registros funcionan con `/var/log/mail.log` o, si no existe, con el diario de systemd.

**Instalación**: `deploy/vigilantes/instalar.sh` (lo llaman `deploy/webmail/instalar.sh` y el ajuste
`deploy/ajustes/53-vigilantes.sh`). Respalda lo que reemplaza, no pisa versiones propias de un servidor
(archivos sin la marca `maquita-vigilantes (repo)` o unidades que no instaló él) y deshace todo si algo falla.

Prueba de los avisos: `guardian-web-correo --prueba`.
