# Cortafuegos (panel → Protección → Cortafuegos)

Decide qué puertos del servidor se pueden usar desde Internet, sobre **iptables** (en Debian 13,
iptables-nft). Todo lo que no esté abierto se descarta, aunque haya un programa escuchando.

## Instalación

```bash
sudo ADMIN_IPS="203.0.113.0/24 198.51.100.7" bash deploy/webmail/instalar-app.sh cortafuegos
```

`ADMIN_IPS`: IP o redes desde donde se administra (SSH y panel). Si no se indica, se usan las redes
privadas y la IP de la sesión SSH que instala. Si `ufw` está activo, el instalador se detiene (dos
programas manejando el cortafuegos se pisan). La configuración inicial cierra DNS o FTP si no están
instalados.

## Qué viene preconfigurado

| Servicio | Puertos | Origen por defecto |
|---|---|---|
| SSH / SFTP | 22 | Solo administración |
| Panel | 8443 | Solo administración |
| Correo SMTP | 25, 465, 587 | Todo Internet |
| Correo IMAP/POP3 | 143, 993, 110, 995 | Todo Internet |
| ManageSieve | 4190 | Cerrado |
| Web y webmail | 80, 443 | Todo Internet |
| DNS | 53 TCP/UDP | Todo Internet (si está instalado) |
| FTP seguro | 21, 40000–40100 | Todo Internet (si está instalado) |

Además: tráfico local y conexiones ya establecidas, contenedores locales (Docker), ping limitado
(5/s), ICMPv6 completo en IPv6. Lo descartado se anota en el registro del sistema
(`cortafuegos-descartado:`, máximo 6 por minuto); la difusión de la red local se descarta sin anotar.

## Cómo funciona

- Cadena propia `CORTAFUEGOS` en IPv4 e IPv6, enganchada **al final** de `INPUT`. fail2ban inserta sus
  cadenas al principio, así que una IP bloqueada por fail2ban se rechaza aunque el puerto esté abierto.
- Carga atómica (`iptables-restore --noflush`) y al arrancar (`maquita-cortafuegos.service`).
- **Cambios a prueba:** cada cambio desde el panel se aplica con vuelta atrás automática a los 60
  segundos (`systemd-run`). Si no se confirma —por ejemplo, porque la regla dejó fuera a quien la
  puso— se restaura la configuración anterior. Si el servidor se reinicia con un cambio sin
  confirmar, arranca con la anterior.
- **No dejarse fuera:** el panel no acepta una configuración que cierre el panel a la IP desde la que
  se está usando.
- **Puertos adicionales:** para aplicaciones propias que necesiten un puerto (TCP o UDP, uno, lista o
  rango), abiertos a todos o solo a administración.
- **Bloqueos manuales** de IP o redes.
- **fail2ban:** lista de IP bloqueadas por vigilancia, con botón para desbloquear.
- **Programas escuchando:** muestra qué escucha el servidor y si el cortafuegos lo deja pasar.

El panel corre sin privilegios: el ayudante root `maquita-cortafuegos` solo se llama por `maquita-sudo`
(subacciones `estado`, `aplicar`, `confirmar`, `revertir`, `desbloquear`; `cargar`, `quitar` e `inicial`
quedan solo para el sistema). Todo queda en la auditoría (`cortafuegos_*`).

Desactivarlo por completo (desde la consola): `maquita-cortafuegos quitar` y
`systemctl disable maquita-cortafuegos`.

## Archivos

`deploy/cortafuegos/` (instalador, ayudante y `lib/`: config, reglas, aplicar, estado), configuración en
`/etc/maquita-cortafuegos/` (solo root), panel en `admin-panel/backend/app/cortafuegos/` y
`admin-panel/frontend/src/pages/Cortafuegos.tsx`, `pages/cortafuegos/`.
