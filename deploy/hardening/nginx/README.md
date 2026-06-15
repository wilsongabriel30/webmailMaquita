# IP real detrás de reverse-proxy (risky_login / auditoría / fail2ban)

`real-ip.conf` resuelve el problema más común al desplegar: si nginx no traduce
la IP real del cliente, el backend ve la IP del proxy y **todo parece interno**
→ el "viaje imposible" (risky_login) queda CIEGO y la auditoría registra IPs
equivocadas.

## Instalar
1. Editar `real-ip.conf`: poner la IP del proxy/router de borde en `set_real_ip_from`.
2. Incluirlo dentro del `server { }` del webmail (o `include .../real-ip.conf;`).
3. `nginx -t && systemctl reload nginx`.
4. Verificar: tras un login EXTERNO, `login_events` debe mostrar la IP pública
   real e `is_internal=false`. Gestionar con `maquita-mailadm risky-login status`.

## Activar bloqueo automático
```
maquita-mailadm risky-login auto-block on     # bloquea logins de riesgo ALTO
maquita-mailadm risky-login events            # ver detecciones
```

## Roadmap — extender a IMAP/SMTP (no solo webmail)
Hoy `risky_login.analyze()` se invoca desde el login del **webmail**. Para cubrir
clientes de escritorio/móvil (IMAP/SMTP), pendiente:
- Leer del journal de Dovecot/Postfix los logins exitosos con IP (`imap-login: Login: ... rip=<ip>`).
- Llamar a `analyze()` con esa IP (mismo motor de viaje imposible).
- En riesgo ALTO + auto_block: empujar la IP a fail2ban/`blacklist_mail` del MikroTik
  (ya existe la tubería `fail2ban → MikroTik`, ver `../mikrotik/`).
