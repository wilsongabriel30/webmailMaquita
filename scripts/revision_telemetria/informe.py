"""Arma el texto del informe en español, ordenado por gravedad."""
from collections import Counter
from datetime import datetime

from .hallazgo import ETIQUETA, CRITICO, ALTO, MEDIO, BAJO, INFO
from . import config
from .nombres import persona

SECCIONES = {
    'a': 'a) Errores JS y eventos de error (app_telemetria)',
    'b': 'b) Búsquedas sin resultados y búsquedas lentas',
    'c': 'c) Respuestas HTTP 5xx y 429 por usuario y ruta',
    'd': 'd) Rechazos del milter DLP',
    'e': 'e) Reintentos, duplicados y contadores de envío',
    'f': 'f) Tiempos de la IA (LLM_LLAMADA)',
}


def _bloque(h):
    lineas = [f'  [{ETIQUETA[h.gravedad]}] {h.titulo}']
    lineas.append(f'      Usuario: {persona(h.usuario)}')
    for ev in h.lineas:
        if ev:
            lineas.append(f'      {ev}')
    if h.sugerencia:
        lineas.append(f'      → {h.sugerencia}')
    return '\n'.join(lineas)


def armar(hallazgos, horas, resumen_extra=None, errores_proceso=None):
    ahora = datetime.now()
    hallazgos = sorted(hallazgos, key=lambda h: h.clave_orden())
    por_gravedad = Counter(h.gravedad for h in hallazgos)
    usuarios_afectados = sorted({h.usuario for h in hallazgos if h.usuario and h.gravedad <= MEDIO})

    out = [
        f'REVISIÓN DIARIA DE TELEMETRÍA — Webmail ({config.URL_CORREO.split("//")[-1]})',
        f'Generado: {ahora:%d/%m/%Y %H:%M} (hora Ecuador) · ventana: últimas {horas} h',
        '',
        'RESUMEN',
        '  ' + ' · '.join(f'{ETIQUETA[g]}: {por_gravedad.get(g, 0)}' for g in (CRITICO, ALTO, MEDIO, BAJO, INFO)),
        f'  Usuarios con algo que merece seguimiento (gravedad media o mayor): {len(usuarios_afectados)}',
    ]
    for u in usuarios_afectados:
        peor = min(h.gravedad for h in hallazgos if h.usuario == u)
        out.append(f'    - {persona(u)} → peor gravedad {ETIQUETA[peor]}')
    if resumen_extra:
        out += ['', 'CIFRAS DEL DÍA'] + [f'  {l}' for l in resumen_extra]
    if errores_proceso:
        out += ['', 'AVISOS DEL PROPIO INFORME (alguna fuente no se pudo leer)'] + [f'  {e}' for e in errores_proceso]

    out += ['', 'PRIORIDADES (gravedad crítica y alta, en orden)']
    prioritarios = [h for h in hallazgos if h.gravedad <= ALTO]
    if prioritarios:
        out += [_bloque(h) for h in prioritarios]
    else:
        out.append('  Sin hallazgos críticos ni altos. Buen día.')

    for letra, nombre in SECCIONES.items():
        out += ['', '=' * 78, nombre, '=' * 78]
        del_bloque = [h for h in hallazgos if h.seccion == letra]
        if not del_bloque:
            out.append('  Sin novedades.')
        out += [_bloque(h) for h in del_bloque]

    out += ['', '-' * 78,
            'Cómo leer: CRÍTICO/ALTO requieren acción hoy; MEDIO conviene preguntar al usuario; '
            'BAJO/INFORMATIVO solo registro.',
            'Informes anteriores: /var/lib/maquita-webmail/revision-telemetria/ · '
            'Ejecución manual: /usr/local/bin/revision-telemetria-webmail --sin-correo']
    return '\n'.join(out) + '\n'
