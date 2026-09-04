# Prueba de restauración desde respaldo — 2026-09-04 12:52:59 -05

Ejecutada por el equipo de Tecnología sobre la VM 130. **No se tocó la base de producción**:
la copia se restauró en una base desechable (`restauracion_prueba`) que se eliminó al terminar.

| Dato | Valor |
|---|---|
| Copia usada | `maildb_20260904_0200.sql.gz` |
| Fecha de la copia | 2026-09-04 02:00 |
| Tamaño | 11M |
| Integridad (`gzip -t`) | correcta |
| Duración de la restauración | 6 segundos |
| Errores durante la restauración | 0 |
| Tablas en producción / restaurado | 145 / 144 (ver nota) |

**Nota sobre la tabla de diferencia:** la única tabla que producción tiene y la copia no es
`alias_respaldo_20260904`, creada a mano hoy DESPUÉS de las 02:00, que es cuando corrió el
respaldo. No es una pérdida: la copia reproduce fielmente el estado de ese momento. Se comprobó
comparando la lista completa de tablas en ambos lados; no falta ninguna otra ni sobra ninguna.

## Filas por tabla: producción frente a lo restaurado

| Tabla | Producción | Restaurado |
|---|---|---|
| `mailbox` | 496 | 496 |
| `alias` | 212 | 212 |
| `admin_users` | 2 | 2 |
| `domain` | 11 | 11 |
| `compliance_cases` | 3 | 3 |
| `ediscovery_exports` | 3 | 3 |
| `audit_retention_config` | 1 | 1 |

## Comprobación funcional sobre lo restaurado

- Buzones activos: **298**
- Dominios servidos: **11**

## Alcance y lo que NO cubre esta prueba

- El respaldo diario (`/etc/cron.d/backup-maildb`, 02:00, 30 días de retención) cubre **la base
  de datos del correo**. Hay 31 copias; la más reciente es de hoy.
- **NO** cubre los buzones en disco (`/var/vmail`) ni los archivos del Almacén (`/mnt/almacen`).
  Restaurar solo la base devuelve cuentas, alias y configuración, pero no los mensajes.
  Falta definir y probar el respaldo de esos dos árboles.

## Veredicto

La copia diaria de la base **es restaurable y fiel**: 6 segundos, cero errores, mismas tablas y
mismos recuentos de filas que producción, y consultas funcionales sobre lo restaurado. Lo que
falta para poder decir que la plataforma entera es recuperable es el respaldo de los buzones en
disco y de los archivos del Almacén, que hoy no está cubierto.
