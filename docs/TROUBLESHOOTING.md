# Solución de Problemas — Fundacion Maquita Webmail

> **Proyecto de la Fundacion Maquita** — Comercializadora asociativa sin fines de lucro, Ecuador.

---

## Problemas comunes

| Problema | Solución |
|----------|----------|
| No carga la interfaz | `systemctl status maquita-webmail` — verificar que el backend esté activo |
| Error 502 Bad Gateway | El backend no responde: `curl http://127.0.0.1:8000/docs` |
| No llegan correos | Verificar: `tail -f /var/log/mail.log` y registros MX en DNS |
| Correos van a spam en Gmail | Verificar DKIM: `dig +short TXT mail._domainkey.tudominio.com` |
| No se puede enviar | Verificar Dovecot SASL y puerto 587 |
| Búsqueda lenta | Reindexar FTS: `doveadm fts rescan -u usuario@tudominio.com` |
| Caché vieja del navegador | Ctrl+Shift+R o borrar el Service Worker en DevTools |
| Error de certificado | Renovar: `certbot renew` |
| Calendario no funciona | Verificar Radicale: `systemctl status radicale` |
| Correos legítimos en Junk | Agregar dominio a la lista blanca desde Admin > Anti-Spam > Whitelist |
| Login lento | Verificar Redis: `redis-cli ping` |
| Adjuntos no se descargan | Verificar permisos en /var/vmail y espacio en disco |

## Diagnóstico rápido

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

1. Verificar que el puerto 25 está abierto:
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

### Correos van a Junk sin razón

1. Revisar por qué fue clasificado:
   ```bash
   tail -50 /var/log/maquita-spam-filter.log | grep "from=remitente"
   ```
2. Si el puntaje es bajo pero está en Junk, revisar Rspamd:
   ```bash
   rspamc stat
   ```
3. Agregar a la lista blanca desde Admin > Anti-Spam > Whitelist

### No se pueden enviar correos

1. Verificar autenticación SASL:
   ```bash
   doveadm auth test usuario@tudominio.com password
   ```
2. Verificar que el puerto 587 acepta conexiones:
   ```bash
   openssl s_client -starttls smtp -connect localhost:587
   ```

## Problemas del webmail

### El backend no arranca

1. Ver el error específico:
   ```bash
   journalctl -u maquita-webmail -n 100 --no-pager
   ```
2. Verificar que el archivo .env existe y tiene los valores correctos
3. Verificar que PostgreSQL y Redis están corriendo
4. Probar manualmente:
   ```bash
   cd /opt/maquita-webmail/backend
   source venv/bin/activate
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

### El frontend no carga

1. Verificar que los archivos existen:
   ```bash
   ls /opt/maquita-webmail/www/webmail/
   ```
2. Si no existen, reconstruir:
   ```bash
   bash /opt/maquita-webmail/deploy-webmail.sh
   ```
3. Verificar la configuración de Nginx:
   ```bash
   nginx -t
   ```

### Error 401 en API

- Token JWT expirado: cerrar sesión y volver a entrar
- Contraseña cambiada: limpiar las cookies del navegador

## Problemas de rendimiento

### Todo está lento

1. Verificar uso de recursos:
   ```bash
   htop
   df -h
   free -h
   ```
2. Verificar que Redis está funcionando:
   ```bash
   redis-cli ping
   ```
3. Verificar índices de búsqueda:
   ```bash
   doveadm fts rescan -u usuario@tudominio.com
   ```

### La búsqueda no encuentra correos

```bash
# Reindexar un usuario
doveadm fts rescan -u usuario@tudominio.com

# Reindexar todos los usuarios
doveadm fts rescan -A
```

## Comandos útiles

```bash
# Reiniciar el webmail
systemctl restart maquita-webmail

# Ver logs en tiempo real
journalctl -u maquita-webmail -f

# Log del filtro anti-spam
tail -f /var/log/maquita-spam-filter.log

# Deploy seguro (frontend)
bash /opt/maquita-webmail/deploy-webmail.sh

# Ver buzones de un usuario
doveadm mailbox list -u usuario@tudominio.com

# Buscar en correos (FTS)
doveadm search -u usuario@tudominio.com mailbox INBOX text "busqueda"

# Generar contraseña para nuevo buzón
doveadm pw -s BLF-CRYPT

# Backup de base de datos
pg_dump -U mailserver maildb > backup_$(date +%Y%m%d).sql

# Actualizar desde GitHub
cd /opt/maquita-webmail
git pull origin main
bash deploy-webmail.sh
```

## Migración desde Zimbra

El proyecto incluye un script para migrar buzones:

```bash
bash zimbra-sync.sh usuario@tudominio.com IP_SERVIDOR_ZIMBRA
```

Usa `imapsync` para copiar todos los correos preservando carpetas, fechas y flags.

---

*Fundacion Maquita — Tecnología al servicio de todos, no solo de quienes pueden pagarla.*


## Pantalla en blanco: "Failed to find a valid digest in the integrity attribute"

**Causa:** se editó a mano un archivo JavaScript ya compilado en `dist/`. El build
usa SRI (Subresource Integrity): `index.html` guarda un hash de cada `.js`, y al
modificar el `.js` el hash deja de coincidir, por lo que el navegador bloquea el
archivo y no carga nada.

**Solución:** no parchees nunca el `dist/`. Corrige el **código fuente** (`src/`) y
reconstruye:

```bash
cd frontend && npx vite build            # webmail
cd admin-panel/frontend && npx vite build # panel
```

Al reconstruir, los hashes de integridad se recalculan y la app vuelve a cargar.
