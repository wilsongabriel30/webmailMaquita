# Safe Attachments — niveles de protección

| Capa | Qué cubre | Estado |
|---|---|---|
| ClamAV (firmas) | Malware conocido | activo (`clamdscan`) |
| oletools (olevba) | Detección de macros AutoExec/Shell en Office | activo |
| **CDR** (`backend/app/security/cdr.py`) | **Desarma** macros de OOXML (quita `vbaProject.bin`) | nuevo |
| Sandbox dinámico | Amenazas no basadas en macros (exploits, droppers) | NO incluido (roadmap) |

> **Importante:** sin sandbox dinámico, esto es antivirus de firmas + análisis y
> desarmado de macros. Para 0-days/exploits embebidos hace falta un sandbox
> (CAPE/Cuckoo) — ver roadmap abajo.

## Activar (incluido en el instalador)
`deploy/seeds/safeattach-seed.sql` deja `enabled=true`, `cdr_enabled=true`,
`quarantine_suspicious=true`.

## CDR — uso
```python
from app.security import cdr
limpio, acciones = cdr.disarm(contenido, nombre_archivo)   # quita macros de OOXML
cdr.has_macros(contenido, nombre_archivo)                  # bool
```
Integración recomendada (al descargar/entregar un adjunto): si
`safeattach_config.cdr_enabled` y `cdr.has_macros(...)`, servir `cdr.disarm(...)`
con sufijo `(desarmado)` y registrar la acción. Validar en staging antes de
activar en la ruta de descarga de producción (afecta a todos los usuarios).

## Roadmap — sandbox
Cola de cuarentena → enviar el adjunto a CAPE/Cuckoo → veredicto → liberar o
bloquear. Empujar IPs/hashes maliciosos a la blacklist (ver `../mikrotik/`).
