# Respaldos cifrados y restauración

Un sistema de correo institucional **no puede perder la evidencia ni los buzones**.
Esta guía cubre el respaldo cifrado, el respaldo automático diario, y —lo más
importante— **cómo probar que el respaldo de verdad se restaura** (un backup que
nunca se ha restaurado no es un backup, es una esperanza).

Scripts en `deploy/webmail/backup/`:
- `respaldar.sh` — genera un respaldo **cifrado** (GPG).
- `restaurar.sh` — restaura, con un **modo de prueba** que no toca producción.
- `maquita-backup.service` + `.timer` — respaldo automático diario.

## Qué se respalda

| Componente | Contenido |
|---|---|
| Base de datos (`maildb`) | Cuentas, auditoría, cumplimiento, tareas, calendario meta, etc. |
| Configuración + secretos | `.env` (backend y panel), Dovecot, Postfix, Radicale, **claves DKIM**, nginx |
| Buzones (opcional) | `/var/vmail` (los correos) y `/var/lib/radicale` (calendarios/contactos) |

El resultado es **un solo archivo `.tar.gpg` cifrado** + su `.sha256`.

## 1. Configurar el cifrado (obligatorio)

El respaldo **nunca** se guarda en claro. Elige un método en
`/etc/maquita-backup.conf`:

**Opción A — asimétrico (recomendado).** La clave **privada** vive *fuera* del
servidor; ni siquiera quien entre al servidor puede descifrar los backups.

```bash
# En una máquina segura (tu PC), genera un par y exporta la pública:
gpg --quick-generate-key "Backups Maquita <backups@tudominio.com>"
gpg --export --armor backups@tudominio.com > maquita-backup.pub
# Cópiala al servidor e impórtala:
gpg --import maquita-backup.pub
# Configura:
echo 'BACKUP_GPG_RECIPIENT="backups@tudominio.com"' >> /etc/maquita-backup.conf
```

**Opción B — simétrico (más simple).** Una frase en un archivo protegido:

```bash
openssl rand -base64 32 > /root/.backup-pass
chmod 600 /root/.backup-pass
echo 'BACKUP_PASSPHRASE_FILE="/root/.backup-pass"' >> /etc/maquita-backup.conf
```

> ⚠️ Guarda la clave privada / la passphrase **en otro lugar**. Si la pierdes,
> los respaldos son irrecuperables (esa es justamente la idea del cifrado).

## 2. Respaldo manual

```bash
sudo bash deploy/webmail/backup/respaldar.sh
# Solo BD + config (rápido, sin los buzones):
sudo INCLUDE_MAILBOXES=0 bash deploy/webmail/backup/respaldar.sh
```

Se guarda en `/var/backups/maquita/` (configurable con `BACKUP_DIR`), con
retención de 14 días (`RETENTION_DAYS`).

## 3. Respaldo automático diario

```bash
sudo cp deploy/webmail/backup/maquita-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now maquita-backup.timer
systemctl list-timers maquita-backup.timer   # ver próxima ejecución (02:30 a diario)
```

## 4. Copiar el respaldo FUERA del servidor

Un backup en el mismo disco no protege contra un disco muerto o un ransomware.
Cópialo a otro nodo o almacenamiento (ejemplo con `rsync` por SSH):

```bash
rsync -az /var/backups/maquita/ usuario@otro-servidor:/respaldos/maquita/
```

Defínelo en un cron/timer aparte, o añádelo al final de `respaldar.sh`.

## 5. PROBAR la restauración (hazlo cada mes)

El paso que casi todos olvidan. **No toca producción** — restaura la BD a una base
desechable y la valida:

```bash
sudo bash deploy/webmail/backup/restaurar.sh --verificar /var/backups/maquita/maquita-AAAAMMDD-HHMMSS.tar.gpg
```

Salida esperada:

```
✓ PRUEBA DE RESTAURACIÓN OK: la BD restaura (93 tablas, 487 buzones en el dump).
```

Si esto falla, tu backup no sirve y hay que arreglarlo **antes** de necesitarlo.

## 6. Restauración real (recuperación ante desastre)

**Destructiva**: sobrescribe la BD, la configuración y (si están en el respaldo)
los buzones. Pide confirmación escribiendo `RESTAURAR`.

```bash
sudo bash deploy/webmail/backup/restaurar.sh --restaurar /var/backups/maquita/maquita-AAAAMMDD-HHMMSS.tar.gpg
```

Detiene los servicios, restaura, y los vuelve a arrancar.

## RPO / RTO (qué prometer a la institución)

- **RPO (cuánto dato puedes perder):** con el timer diario, hasta **24 h**. Si
  necesitas menos, programa el respaldo más seguido (p. ej. cada 6 h) o añade
  archivado WAL de PostgreSQL.
- **RTO (cuánto tardas en volver):** depende del tamaño de `/var/vmail`. La BD y la
  config restauran en minutos; los buzones, según el volumen.

## Buenas prácticas

- Prueba de restauración **mensual** (`--verificar`) y anótala.
- La clave de cifrado, **fuera** del servidor.
- Al menos **una copia externa** (otro nodo / almacenamiento).
- Vigila el espacio en disco de `/var/backups`.
- Backups y restauraciones se registran; revísalos.
