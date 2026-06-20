# AIR — Automated Investigation & Response (IA-asistido)

Cierra el gap de E5 "AIR/Threat Explorer". Modular (un archivo por rol),
con la IA local (Qwen vía Ollama) como segunda opinión.

## Módulos (`backend/app/air/`)
- `signals.py` — correlaciona señales de riesgo por usuario (risky_logins, dlp_violations, safelinks_clicks).
- `playbooks.py` — reglas deterministas → severidad + acción recomendada.
- `triage.py` — **neurona Qwen**: resume el incidente y recomienda (lock/review/monitor) + confianza.
- `responder.py` — contención (desactiva buzón + mata sesión Redis) y registro en `threat_actions`.
- `engine.py` — orquesta. **Seguro por defecto: solo detecta y recomienda.**
- `router.py` — API admin: `GET /api/air/incidents`, `POST /api/air/run`, `POST /api/air/act`.
- `run.py` — runner cron/CLI (detect-only).

## Uso
- Consola: `maquita-mailadm air incidents [horas]`
- API (admin): `GET /api/air/incidents?hours=24`
- Cron nocturno: `deploy/air/maquita-air.cron` → `/etc/cron.d/maquita-air`

## Contención automática
Solo si `threat_config.auto_disable_on_compromise=true` Y se llama con `auto_respond=true`.
Por defecto NO contiene (evita falsos positivos): registra el incidente para revisión humana.
