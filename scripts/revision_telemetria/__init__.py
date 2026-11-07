"""Revisión diaria y proactiva de la telemetría del webmail Maquita.

Paquete modular: cada archivo tiene una responsabilidad única.
  config.py            rutas, umbrales y lectura del .env
  nombres.py           correo -> nombre de la persona (para saber a quién preguntar)
  hallazgo.py          estructura común de un hallazgo y su gravedad
  consultas_bd.py      app_telemetria y dlp_violations (PostgreSQL)
  consultas_journal.py registro de uvicorn/journal (HTTP 5xx/429, reintentos, LLM)
  consultas_redis.py   contadores de envío send_rl:*
  informe.py           texto final en español ordenado por gravedad
  correo.py            envío por sendmail local (remitente de organizacion.env)
  __main__.py          orquestación y argumentos
"""
