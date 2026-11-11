"""Estado real de una reunión programada (T-91, 09/11/2026). COPIA de la regla de Raíces
(`modulos/jitsi/aplicacion/servicios/ocupacion_reuniones.estado_vivo`, VM 101): si cambia allá, cambiar aquí.

La ocupación la mide Raíces cada minuto y la deja en `config_sala.ocupacion = {personas, medido_en}`.
Estados: sin_iniciar | en_curso | en_vivo | finalizada | cancelada.
"""
from datetime import datetime, timedelta

MARGEN_FIN = timedelta(minutes=10)
VACIA = timedelta(minutes=10)
FRESCA = timedelta(minutes=3)
MARGEN_SIN_MEDIDA = timedelta(minutes=30)


def _fecha(v):
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(v)).replace(tzinfo=None) if v else None
    except ValueError:
        return None


def estado_vivo(fecha_hora, duracion_horas, estado, cerrada_en, cfg, ahora=None):
    """{'estado': sin_iniciar|en_curso|en_vivo|finalizada|cancelada, 'personas': int|None}."""
    ahora = ahora or datetime.now()
    cfg = cfg if isinstance(cfg, dict) else {}
    if estado == 'cancelada':
        return {'estado': 'cancelada', 'personas': None}
    if cerrada_en or cfg.get('cerrada_en'):
        return {'estado': 'finalizada', 'personas': None}
    inicio = _fecha(fecha_hora)
    if inicio is None:
        return {'estado': 'sin_iniciar', 'personas': None}
    fin = inicio + timedelta(hours=float(duracion_horas or 1))
    abierta = _fecha(cfg.get('abierta_en'))
    oc = cfg.get('ocupacion') if isinstance(cfg.get('ocupacion'), dict) else {}
    medido = _fecha(oc.get('medido_en'))
    if medido is None or ahora - medido > FRESCA:
        if ahora > fin + MARGEN_SIN_MEDIDA:
            return {'estado': 'finalizada', 'personas': None}
        return {'estado': 'en_curso' if abierta else 'sin_iniciar', 'personas': None}
    personas = int(oc.get('personas') or 0)
    if personas > 0:
        return {'estado': 'en_vivo', 'personas': personas}
    if ahora > fin + MARGEN_FIN:
        return {'estado': 'finalizada', 'personas': 0}
    if abierta:
        ultima = max(x for x in (abierta, _fecha(cfg.get('vista_en'))) if x)
        return {'estado': 'finalizada' if ahora - ultima >= VACIA else 'en_curso', 'personas': 0}
    return {'estado': 'sin_iniciar', 'personas': 0}
