# SafeAttach — análisis de adjuntos (multi-motor + detonación aislada)

Código del motor: `backend/app/safeattach/` (un archivo por analizador).
Entrada estable: `from app.safeattach import scan_attachment`.

## Motores estáticos (activos siempre)
- **clamav** — firmas (clamd).
- **filetype** — MIME real vs extensión (disfraz).
- **oletools** — macros en documentos Office (olevba).
- **archive** — ejecutables ocultos dentro de ZIP.
- **yara** — reglas estáticas en `deploy/safeattach/yara/` (var `SAFEATTACH_YARA_DIR`).

## Detonación dinámica (opcional, aislada en Docker)
Corre el adjunto en un contenedor **sin red, sin privilegios, FS de solo lectura,
con límites de CPU/memoria y timeout**. Nunca se ejecuta en el host.

### Construir la imagen
```bash
cd deploy/safeattach
docker build -t maquita-safeattach-sandbox .
```

### Habilitar
En el `.env` del backend:
```
SAFEATTACH_DETONATE=1
SAFEATTACH_SANDBOX_IMAGE=maquita-safeattach-sandbox
SAFEATTACH_DETONATE_TIMEOUT=90
SAFEATTACH_YARA_DIR=/opt/maquita-webmail/deploy/safeattach/yara
```
Reiniciar `maquita-webmail`. Con `SAFEATTACH_DETONATE=0` (default) solo corren los
motores estáticos; el envío nunca se bloquea si docker/imagen no están.

## Agregar un motor nuevo
1. Crear `backend/app/safeattach/analyzers/mi_motor.py` heredando de `Analyzer`.
2. Añadirlo a `ANALYZERS` en `pipeline.py`. Nada más.
