# Hardening nftables — geo-blocking del correo

Estrategia de bloqueo geográfico por país, **solo en puertos autenticados**.
Sí se trae al repo como scripts/sets (no queda como guía manual).

## Principio clave
- **Puertos de login** (443, 465, 587, 143, 993, 4190): solo se permite el acceso
  desde los países donde hay usuarios reales. Todo lo demás se descarta.
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
        tcp dport { 443, 465, 587, 143, 993, 4190 } ip saddr != @paises_permitidos drop
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
