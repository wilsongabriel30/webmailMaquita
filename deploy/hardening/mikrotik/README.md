# Hardening — bloqueo perimetral de ataques al correo en MikroTik (RouterOS)

Cuando el correo entra por DNAT de un MikroTik, conviene dropear a los atacantes
**en el router** (antes de que lleguen al servidor). Este módulo sincroniza la
inteligencia del servidor de correo (fail2ban + blacklist curada) hacia una
address-list del router, en **tiempo real** (action de fail2ban) y por **lote**
(cron de respaldo).

> Reutilizable en cualquier infra con MikroTik. Ajustar IPs, usuario y lista.

## Arquitectura
```
fail2ban banea IP  ──(action mikrotik-blacklist, instantáneo)──┐
blacklist-ips.txt  ──(sync-blacklist-mikrotik.sh, cron 10min)──┤
                                                               ▼
                                       address-list "blacklist_mail" (MikroTik)
                                                               ▼
                                       regla raw prerouting: drop puertos correo
```

## 1. Setup en el MikroTik (una vez)
```routeros
# address-list (se crea sola al primer add) + regla raw drop SOLO puertos de correo
/ip firewall raw add chain=prerouting action=drop protocol=tcp \
    dst-port=25,465,587,143,993 src-address-list=blacklist_mail \
    comment="MAIL: Drop atacantes de correo"

# usuario dedicado con permisos limitados (NO usar admin)
/user group add name=sync-fw policy=ssh,read,write
/user add name=CHANGEME_MT_USER group=sync-fw password="<poner-uno-fuerte>"
# subir la clave publica del servidor (scp) e importarla:
/user ssh-keys import user=CHANGEME_MT_USER public-key-file=mikrotik_sync.pub
```

## 2. Setup en el servidor de correo
```bash
# clave SSH dedicada (sin passphrase, para automatizacion)
ssh-keygen -t rsa -b 2048 -f /root/.ssh/mikrotik_sync -N "" -C "mail-blacklist-sync"
# subir /root/.ssh/mikrotik_sync.pub al router (ver paso 1)

# script de sync por lote (cron de respaldo)
cp sync-blacklist-mikrotik.sh /usr/local/sbin/ && chmod 750 /usr/local/sbin/sync-blacklist-mikrotik.sh
echo '*/10 * * * * root /usr/local/sbin/sync-blacklist-mikrotik.sh >/dev/null 2>&1' > /etc/cron.d/sync-blacklist-mikrotik

# action de fail2ban en tiempo real
cp fail2ban/action.d/mikrotik-blacklist.conf /etc/fail2ban/action.d/
# editar el [Init] (mthost, mtuser, sshkey, addrlist)
```

En `jail.local`, añadir la action a los jails de correo (mantiene el ban local + empuja al router):
```ini
[postfix-sasl]
action = %(action_)s
         mikrotik-blacklist
```
(igual en `[dovecot]` y `[recidive]`). Luego `fail2ban-client -t && systemctl reload fail2ban`.

## Notas / gotchas
- En la action usar **comando RouterOS directo**, NO `:do {...} on-error={}`: ese
  cuelga la sesión SSH no-interactiva de RouterOS y bloquea el actionban.
- `actionban` con IP ya existente devuelve "already have such entry" (rc=0, inofensivo).
- El geo-block por país va aparte y SOLO en puertos autenticados; el 25 nunca se
  geo-bloquea (ver `../nftables/README.md`).
- Probar: `fail2ban-client set postfix-sasl banip 203.0.113.222` → debe aparecer en
  `/ip firewall address-list print where list=blacklist_mail`; luego `unbanip`.
