# ALMACÉN MAQUITA

Motor de almacenamiento propio de Fundación Maquita, reemplazo incremental de Nextcloud.
El explorador web (frontend estilo Drive de FARO) se mantiene tal cual: este proyecto
construye el servicio que responde a su API.

**Estado:** Fase 0 — contrato congelado y verificado contra el sistema actual.

## Arquitectura decidida (2026-07-03)

| Capa | Tecnología | Por qué |
|---|---|---|
| Bytes (plano de datos) | **nginx** (`X-Accel-Redirect`, streaming) | Componente en C probado por la industria entera durante 20 años. Descargas zero-copy desde disco. Nosotros no escribimos C: lo aprovechamos. |
| Cerebro (plano de control) | **Python / Flask magro** | El mismo stack que ya opera FARO: un solo stack que parchar, todo el equipo lo lee. Sin clase de errores de memoria (recomendación NSA/Microsoft/Google para código nuevo). |
| Metadatos | **PostgreSQL** (193.16.0.132) | Ya lo operamos y respaldamos. |
| Archivos | Filesystem plano por usuario | Respaldos simples (rsync/zfs del árbol + dump de BD). |

### Política de dependencias (superficie de ataque mínima)
Exactamente **4**: `flask`, `gunicorn`, `psycopg2`, `requests` (transición). Nada más.
Si algo se puede hacer con la librería estándar, se hace con la librería estándar.
El servicio JAMÁS se expone directo: siempre detrás de nginx, en red privada.

## Normas del código (obligatorias)
1. **Ningún archivo supera ~1,500 líneas** (máximo duro: 2,000). Si crece, se divide en módulos.
2. **Todos los comentarios y docstrings en español.**
3. Autoría: Equipo de Tecnología Maquita.
4. Toda función pública con docstring: qué hace, parámetros, qué devuelve.
5. Cambios de contrato = actualizar `docs/CONTRATO-API.md` + la suite de pruebas, siempre.

## Estructura
```
almacen-maquita/
├── README.md                 ← este archivo
├── docs/
│   └── CONTRATO-API.md       ← contrato congelado de la API (la especificación)
├── pruebas_contrato/
│   ├── test_contrato_nube.py ← suite que verifica el contrato (hoy contra Nextcloud,
│   │                            mañana contra el Almacén: misma suite, verde en ambos)
│   └── correr.sh             ← ejecutar la suite
└── (fase 1: servicio/)
```

## Fases del proyecto
- **Fase 0 (actual):** contrato + suite verde contra el sistema actual. No toca producción.
- **Fase 1:** PoC del núcleo (listar/subir/bajar/carpetas/papelera) que pase la MISMA suite. Benchmark lado a lado.
- **Fase 2:** piloto sombra con usuarios de TI (flag por usuario, mismo frontend).
- **Fase 3:** paridad (versiones, OnlyOffice, previews, notificaciones).
- **Fase 4:** migración por olas; Nextcloud queda de solo lectura 1-2 meses y se apaga.

## Cómo correr las pruebas de contrato
```bash
cd /home/sistemas/almacen-maquita/pruebas_contrato && bash correr.sh
```
Usa el usuario de pruebas `master_pruebas` (id 54, cuenta Nube `pruebas`) — nunca datos reales.
