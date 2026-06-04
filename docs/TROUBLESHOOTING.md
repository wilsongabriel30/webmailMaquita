# Solucion de Problemas — Fundacion Maquita Webmail

> **Proyecto de la Fundacion Maquita** — Comercializadora asociativa sin fines de lucro, Ecuador.

---

## Problemas comunes

| Problema | Solucion |
|----------|----------|
| No carga la interfaz | `systemctl status maquita-webmail` — verificar backend activo |
| Error 502 Bad Gateway | Backend no responde: `curl http://127.0.0.1:8000/docs` |
| No llegan correos | Verificar: `tail -f /var/log/mail.log` y registros MX en DNS |
| Correos van a spam en Gmail | Verificar DKIM: `dig +short TXT mail._domainkey.tudominio.com` |
| No se puede enviar | Verificar Dovecot SASL y puerto 587 |
| Busqueda lenta | Reindexar FTS: `doveadm fts rescan -u usuario@tudominio.com` |
| Cache vieja del navegador | Ctrl+Shift+R o borrar Service Worker en DevTools |
| Error de certificado | Renovar: `certbot renew` |
| Calendario no funciona | Verificar Radicale: `systemctl status radicale` |
| Correos legitimos en Junk | Agregar dominio a whitelist desde Admin > Anti-Spam > Whitelist |
| Login lento | Verificar Redis: `redis-cli ping` |
| Adjuntos no se descargan | Verificar permisos en /var/vmail y espacio en disco |

## Diagnostico rapido

```bash
# 1. Estado de todos los servicios
systemctl status postfix dovecot rspamd clamav-daemon \
  redis-server postgresql nginx radicale maquita-webmail

# 2. Puertos que deben estar escuchando
ss -tlnp | grep -E "25|80|143|443|587|993|5232|8000"

# 3. API del webmail
curl -s http://localhost:8000/api/health

# 4. Logs del webmail
journalctl -u maquita-webmail -f --no-pager -n 50

# 5. Logs de correo
tail -50 /var/log/mail.log

# 6. Log del filtro anti-spam
tail -50 /var/log/maquita-spam-filter.log

# 7. Espacio en disco
df -h /var/vmail

# 8. Uso de RAM
free -h
```

## Problemas de correo

### No llegan correos

1. Verificar que el puerto 25 esta abierto:
   ```bash
   ss -tlnp | grep :25
   ```
2. Verificar registros DNS:
   ```bash
   dig +short MX tudominio.com
   dig +short A mail.tudominio.com
   ```
3. Revisar logs de Postfix:
   ```bash
   tail -100 /var/log/mail.log | grep -i "reject\|error\|warning"
   ```

### Correos van a Junk sin razon

1. Revisar por que fue clasificado:
   ```bash
   tail -50 /var/log/maquita-spam-filter.log | grep "from=remitente"
   ```
2. Si el score es bajo pero esta en Junk, revisar Rspamd:
   ```bash
   rspamc stat
   ```
3. Agregar a whitelist desde Admin > Anti-Spam > Whitelist

### No se pueden enviar correos

1. Verificar autenticacion SASL:
   ```bash
   doveadm auth test usuario@tudominio.com password
   ```
2. Verificar que el puerto 587 acepta conexiones:
   ```bash
   openssl s_client -starttls smtp -connect localhost:587
   ```

## Problemas del webmail

### Backend no arranca

1. Ver error especifico:
   ```bash
   journalctl -u maquita-webmail -n 100 --no-pager
   ```
2. Verificar que .env existe y tiene valores correctos
3. Verificar que PostgreSQL y Redis estan corriendo
4. Probar manualmente:
   ```bash
   cd /opt/maquita-webmail/backend
   source venv/bin/activate
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

### Frontend no carga

1. Verificar que los archivos existen:
   ```bash
   ls /opt/maquita-webmail/www/webmail/
   ```
2. Si no existen, reconstruir:
   ```bash
   bash /opt/maquita-webmail/deploy-webmail.sh
   ```
3. Verificar configuracion de Nginx:
   ```bash
   nginx -t
   ```

### Error 401 en API

- Token JWT expirado: cerrar sesion y volver a entrar
- Password cambiada: limpiar cookies del navegador

## Problemas de rendimiento

### Todo esta lento

1. Verificar uso de recursos:
   ```bash
   htop
   df -h
   free -h
   ```
2. Verificar que Redis esta funcionando:
   ```bash
   redis-cli ping
   ```
3. Verificar indices de busqueda:
   ```bash
   doveadm fts rescan -u usuario@tudominio.com
   ```

### Busqueda no encuentra correos

```bash
# Reindexar un usuario
doveadm fts rescan -u usuario@tudominio.com

# Reindexar todos
doveadm fts rescan -A
```

## Comandos utiles

```bash
# Reiniciar webmail
systemctl restart maquita-webmail

# Ver logs en tiempo real
journalctl -u maquita-webmail -f

# Log del filtro anti-spam
tail -f /var/log/maquita-spam-filter.log

# Deploy seguro (frontend)
bash /opt/maquita-webmail/deploy-webmail.sh

# Ver buzones de un usuario
doveadm mailbox list -u usuario@tudominio.com

# Buscar en emails (FTS)
doveadm search -u usuario@tudominio.com mailbox INBOX text "busqueda"

# Generar password para nuevo buzon
doveadm pw -s BLF-CRYPT

# Backup de base de datos
pg_dump -U mailserver maildb > backup_$(date +%Y%m%d).sql

# Actualizar desde GitHub
cd /opt/maquita-webmail
git pull origin main
bash deploy-webmail.sh
```

## Migracion desde Zimbra

El proyecto incluye un script para migrar buzones:

```bash
bash zimbra-sync.sh usuario@tudominio.com IP_SERVIDOR_ZIMBRA
```

Usa `imapsync` para copiar todos los correos preservando carpetas, fechas y flags.

---

*Fundacion Maquita — Tecnologia al servicio de todos, no solo de quienes pueden pagarla.*
