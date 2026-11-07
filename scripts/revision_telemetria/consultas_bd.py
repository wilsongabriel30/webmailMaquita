"""Consultas a PostgreSQL: app_telemetria (errores, búsquedas) y dlp_violations."""
import re
from collections import defaultdict

import psycopg2

from . import config
from .hallazgo import Hallazgo, CRITICO, ALTO, MEDIO, BAJO, INFO
from .nombres import persona, a_quien_preguntar

_RE_NUMEROS = re.compile(r'\d+')


def conectar():
    return psycopg2.connect(config.dsn_postgres())


def _normalizar(mensaje):
    """Agrupa mensajes iguales salvo números/identificadores."""
    texto = (mensaje or '').strip()
    if len(texto) <= 6:          # "401", "429", "timeout": dejarlos tal cual
        return texto
    return _RE_NUMEROS.sub('#', texto)[:160]


def errores_js(cur, horas):
    """a) Errores JS y eventos de error por usuario, agrupados por mensaje."""
    cur.execute(
        """
        SELECT usuario, evento, nivel, detalle, url, modulo, version,
               ocurrido AT TIME ZONE %s AS cuando
        FROM app_telemetria
        WHERE recibido > now() - make_interval(hours => %s)
          AND (nivel IN ('error', 'critico')
               OR evento IN ('error_js', 'error_no_controlado', 'sesion_fallo',
                             'ui_congelada', 'webview_proceso_caido', 'login_fallo'))
        ORDER BY ocurrido DESC
        """,
        (config.ZONA_HORARIA, horas),
    )
    grupos = defaultdict(list)
    for usuario, evento, nivel, detalle, url, modulo, version, cuando in cur.fetchall():
        grupos[(usuario, evento, nivel, _normalizar(detalle))].append((cuando, detalle, url, modulo, version))

    hallazgos = []
    for (usuario, evento, nivel, msg), filas in grupos.items():
        n = len(filas)
        cuando, detalle, url, modulo, version = filas[0]
        if nivel == 'critico':
            gravedad = CRITICO
        elif n >= config.ERRORES_JS_MINIMO_ALTO or evento in ('error_no_controlado', 'ui_congelada', 'webview_proceso_caido'):
            gravedad = ALTO
        else:
            gravedad = MEDIO
        if usuario in config.CUENTAS_PRUEBA:
            gravedad = max(gravedad, BAJO)
        hallazgos.append(Hallazgo(
            gravedad, 'a', f'{evento} ({nivel}) x{n}: {msg[:90]}', usuario,
            [f'Último: {cuando:%d/%m %H:%M} · módulo={modulo or "-"} · versión={version or "-"} · url={url or "-"}',
             f'Ejemplo: {(detalle or "")[:300]}'],
            a_quien_preguntar(usuario) + ' Confirmar si notó el fallo y qué estaba haciendo.',
        ))
    return hallazgos


def busquedas(cur, horas):
    """b) Búsquedas con 0 resultados y búsquedas lentas por usuario."""
    cur.execute(
        """
        SELECT usuario, detalle, extra->>'carpeta', (extra->>'resultados')::int, (extra->>'ms')::int,
               ocurrido AT TIME ZONE %s
        FROM app_telemetria
        WHERE evento = 'busqueda' AND recibido > now() - make_interval(hours => %s)
          AND extra IS NOT NULL
        ORDER BY ocurrido
        """,
        (config.ZONA_HORARIA, horas),
    )
    ceros, lentas, total = defaultdict(list), defaultdict(list), defaultdict(int)
    for usuario, texto, carpeta, resultados, ms, cuando in cur.fetchall():
        total[usuario] += 1
        if resultados == 0:
            ceros[usuario].append((cuando, texto, carpeta))
        if ms is not None and ms > config.BUSQUEDA_LENTA_MS:
            lentas[usuario].append((cuando, texto, carpeta, ms))

    hallazgos = []
    for usuario, filas in ceros.items():
        textos = sorted({(t or '').strip() for _, t, _ in filas})
        # Muchos textos de una sola letra o que crecen letra a letra suelen ser escritura incremental, no un fallo.
        incremental = sum(1 for t in textos if len(t) <= 2)
        gravedad = MEDIO if len(filas) >= 5 and incremental < len(textos) / 2 else BAJO
        hallazgos.append(Hallazgo(
            gravedad, 'b', f'{len(filas)} búsquedas sin resultados (de {total[usuario]})', usuario,
            [f'Textos: {", ".join(repr(t) for t in textos[:12])}' + (' …' if len(textos) > 12 else ''),
             f'Carpetas: {", ".join(sorted({c or "-" for _, _, c in filas}))}'],
            a_quien_preguntar(usuario) + ' Preguntar si encontró lo que buscaba o si el buscador le falla '
            '(p. ej. espacio o tildes).',
        ))
    for usuario, filas in lentas.items():
        peor = max(filas, key=lambda f: f[3])
        hallazgos.append(Hallazgo(
            ALTO if len(filas) >= 3 else MEDIO, 'b',
            f'{len(filas)} búsquedas lentas (> {config.BUSQUEDA_LENTA_MS // 1000} s), peor {peor[3] / 1000:.1f} s', usuario,
            [f'Peor: {peor[0]:%d/%m %H:%M} texto={peor[1]!r} carpeta={peor[2]}',
             'Todas: ' + ', '.join(f'{f[3] / 1000:.1f}s' for f in sorted(filas, key=lambda f: -f[3])[:10])],
            'Revisar índice FTS (dovecot fts) y carga del servidor a esa hora. ' + a_quien_preguntar(usuario),
        ))
    return hallazgos


def rechazos_dlp(cur, horas):
    """d) Rechazos del milter DLP."""
    cur.execute(
        """
        SELECT username, count(*), min(created_at AT TIME ZONE %s), max(created_at AT TIME ZONE %s),
               array_agg(DISTINCT subject), array_agg(DISTINCT reason), array_agg(DISTINCT data_types::text)
        FROM dlp_violations
        WHERE action = 'milter_reject' AND created_at > now() - make_interval(hours => %s)
        GROUP BY username ORDER BY 2 DESC
        """,
        (config.ZONA_HORARIA, config.ZONA_HORARIA, horas),
    )
    hallazgos = []
    for usuario, n, primero, ultimo, asuntos, motivos, tipos in cur.fetchall():
        gravedad = ALTO if n >= 5 else MEDIO
        hallazgos.append(Hallazgo(
            gravedad, 'd', f'{n} correos rechazados por el DLP (milter_reject)', usuario,
            [f'Entre {primero:%d/%m %H:%M} y {ultimo:%d/%m %H:%M}',
             f'Asuntos: {", ".join(repr(a[:60]) for a in asuntos[:5] if a)}',
             f'Tipos de dato: {", ".join(t for t in tipos if t)[:200]}',
             f'Motivos: {", ".join(m[:120] for m in motivos if m)[:300]}'],
            a_quien_preguntar(usuario) + ' Si el envío es legítimo, orientar sobre la excepción del DLP; '
            'si son reintentos, el usuario probablemente no entendió el rechazo.',
        ))
    return hallazgos


def mapa_ip_usuario(cur, horas):
    """IP -> usuario más frecuente en la telemetría (para líneas de uvicorn sin usuario)."""
    cur.execute(
        """
        SELECT ip, usuario, count(*) FROM app_telemetria
        WHERE recibido > now() - make_interval(hours => %s) AND ip <> '' AND usuario <> ''
        GROUP BY 1, 2 ORDER BY 1, 3 DESC
        """,
        (horas,),
    )
    mapa = {}
    for ip, usuario, _ in cur.fetchall():
        mapa.setdefault(ip, usuario)
    return mapa


def todo(horas):
    """Ejecuta todas las consultas de BD y devuelve (hallazgos, mapa_ip_usuario)."""
    with conectar() as con:
        with con.cursor() as cur:
            hallazgos = errores_js(cur, horas) + busquedas(cur, horas) + rechazos_dlp(cur, horas)
            mapa = mapa_ip_usuario(cur, horas)
    return hallazgos, mapa
