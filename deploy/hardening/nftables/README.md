# Hardening nftables — geo-blocking del correo

Estrategia de bloqueo geográfico por país, **solo en puertos autenticados**.
Sí se trae al repo como scripts/sets (no queda como guía manual).

## Principio clave
- **Puertos de login del correo** (465, 587, 143, 993, 4190): solo se permite el acceso
  desde los países donde hay usuarios reales. Todo lo demás se descarta en el cortafuegos.
- **Puerto 443: el filtro por país lo hace nginx, no el cortafuegos** (desde la 1.19). El
  cortafuegos filtra en bloque y no distingue rutas; con el 443 cerrado por país, un servidor
  de otro país no puede pedir la recuperación de un correo ni avisar una reacción
  (`/api/federacion/`), y quien recibe fuera un enlace seguro (`/api/safelink`) no puede
  abrirlo. nginx corta el webmail y la API fuera de los países permitidos (444) y deja abiertas
  solo esas rutas y `/.well-known/`. La lista de nginx la genera `deploy/tools/geo-nginx-rebuild.sh`
  a partir de los mismos conjuntos del cortafuegos (`paises_permitidos` y la nube de Microsoft):
  abrir o cerrar un país en el panel vale para los dos. Instalaciones anteriores: ajuste 82.
- **Puerto 25 (SMTP entrante): NUNCA se geo-bloquea.** Gmail/Outlook/Microsoft
  envían desde USA; bloquear por país en el 25 haría perder correo legítimo.
  El 25 se defiende por otras capas (AUTH off, postscreen+DNSBL, blacklist de
  IPs maliciosas, fail2ban). Ver `../postfix/README.md`.

## Componentes
- `update-geoip.sh` → descarga los rangos de ipdeny.com de los países permitidos
  y repuebla el set `paises_permitidos`. Instalar como `/etc/cron.weekly/update-geoip.sh`.
  Editar la lista de países (`for c in ec es co mx`) según la institución.
- Set + reglas en `/etc/nftables.conf`.

## Estructura nftables (resumen)
```
table inet filter {
    set paises_permitidos { type ipv4_addr; flags interval; }
    set blacklist_ips     { type ipv4_addr; flags interval; }

    chain input {
        type filter hook input priority filter; policy drop;
        ct state established,related accept
        iif "lo" accept
        # redes internas siempre permitidas
        ip saddr { <LAN_CIDR>, 10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12 } accept
        # geo-block SOLO en puertos autenticados (NO el 25)
        tcp dport { 465, 587, 143, 993, 4190 } ip saddr != @paises_permitidos drop   # el 443 lo filtra nginx
        # blacklist de IPs maliciosas (incluye sync de correo)
        ip saddr @blacklist_ips drop
        ...
    }
}
```

## Instalación
1. Definir los sets y reglas en `/etc/nftables.conf` (ver estructura arriba).
2. `cp update-geoip.sh /etc/cron.weekly/ && chmod +x /etc/cron.weekly/update-geoip.sh`
3. Ejecutar una vez para poblar: `/etc/cron.weekly/update-geoip.sh`
4. Verificar: `nft list set inet filter paises_permitidos | head`

> El servicio `nftables` puede mostrar `inactive (dead)` en Debian aunque las
> reglas estén cargadas en memoria (normal). Verificar con `nft list ruleset`.

## Abrir y cerrar países desde el panel

La lista de países vive en la base (tabla `geo_webmail_countries`, migración
`2026-10-03-acceso-por-pais.sql`) y se administra desde el panel («Acceso por país») o por consola:

```bash
install -m 750 deploy/tools/geoip-country.sh deploy/tools/geoip-rebuild.sh /usr/local/sbin/
geoip-country.sh list
geoip-country.sh enable es      # abre España; aplica al cortafuegos en el acto
printf '#!/bin/bash\n/usr/local/sbin/geoip-rebuild.sh\n' > /etc/cron.weekly/update-geoip.sh && chmod +x /etc/cron.weekly/update-geoip.sh
```

- `geoip-rebuild.sh` reconstruye el conjunto en una sola transacción (nunca queda vacío a medias) y
  siempre incluye las redes privadas y las de `ORG_REDES`. El país base (`ORG_PAIS_BASE`, por omisión
  `ec`) no se puede cerrar; si sus rangos no se pueden descargar, no se cambia nada.
- Si aplicar al cortafuegos falla, `geoip-country.sh` deshace el cambio en la base.
- El panel y el webmail lo ejecutan a través de `maquita-sudo`, que solo admite
  `enable|disable <país>`. Con el confinamiento del panel hace falta
  `ReadWritePaths=-/etc/nftables.conf` (ya está en `deploy/hardening/systemd/`).
- Este mecanismo sustituye a `update-geoip.sh` (lista de países escrita en el guion).
