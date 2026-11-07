"""Lectura del registro de uvicorn (journal) de maquita-webmail.

Se lee UNA sola vez con --since acotado y se recorre línea a línea (puede
superar 500 000 líneas al día; nunca cargar todo en memoria ni sin --since).
Formatos que se reconocen:
  2026-11-05 09:54:26 [INFO] rid=… | action=http_request | module=core | user=X | ms=10.2 | status=200 | method=POST | path=/api/…
  INFO:     10.10.100.10:0 - "GET /api/… HTTP/1.0" 500 Internal Server Error
  2026-11-05 15:40:44 [WARNING] LLM_LLAMADA modelo=… gpu=… ms=35015 estado=timeout intento=1
  asyncpg.exceptions.UniqueViolationError: duplicate key value …   (última línea de un traceback)
"""
import re
import subprocess
from collections import defaultdict

from . import config
from .hallazgo import Hallazgo, CRITICO, ALTO, MEDIO, BAJO, INFO
from .nombres import a_quien_preguntar

RE_ESTRUCTURADA = re.compile(
    r'^(?P<fecha>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[\w+\] rid=\w+ \| action=http_request(?: \| module=\S+)?'
    r'(?: \| user=(?P<user>\S+))? \| ms=(?P<ms>[\d.]+) \| status=(?P<status>\d{3}) \| method=(?P<method>\w+) \| path=(?P<path>\S+)')
RE_UVICORN = re.compile(r'^INFO:\s+(?P<ip>[\d.]+):\d+ - "(?P<method>\w+) (?P<path>\S+) HTTP/[\d.]+" (?P<status>\d{3})')
RE_LLM = re.compile(r'^(?P<fecha>\S+ \S+) \[\w+\] LLM_LLAMADA modelo=(?P<modelo>\S+) gpu=(?P<gpu>\S+) ms=(?P<ms>\d+) estado=(?P<estado>\S+) intento=(?P<intento>\d+)')
RE_EXCEPCION = re.compile(r'^(?:[\w.]+\.)?(\w*(?:Error|Exception|Violation|Timeout)\w*): (.+)')
RE_SEGMENTO_ID = re.compile(r'^(\d+|[0-9a-f]{8}-[0-9a-f-]{27,}|[0-9a-f]{24,})$')
RE_PREFIJO_JOURNAL = re.compile(r'^(?P<ts>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)[+-]\d\d:?\d\d \S+ \S+: (?P<msg>.*)$')
RUTAS_RUIDO = ('/api/csp-report', '/api/branding', '/api/presence/heartbeat', '/api/auth/login', '/api/auth/login/2fa')
MARCA_REINICIO = 'graceful shutdown'


def _ruta_sin_consulta(path):
    """Quita la query y sustituye por # los segmentos que son identificadores (números, UUID)."""
    partes = path.split('?', 1)[0].split('/')
    return '/'.join('#' if RE_SEGMENTO_ID.match(p) else p for p in partes)


def leer_journal(horas):
    proc = subprocess.Popen(
        ['journalctl', '-u', config.SERVICIO_JOURNAL, '--since', f'{horas} hours ago', '--no-pager', '-o', 'short-iso'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors='replace')
    for linea in proc.stdout:
        m = RE_PREFIJO_JOURNAL.match(linea.rstrip('\n'))
        if m:
            yield m['ts'].replace('T', ' '), m['msg']
    proc.wait()


def recolectar(horas, mapa_ip_usuario):
    """Recorre el journal y devuelve contadores crudos."""
    http = defaultdict(list)        # (usuario, status, método, ruta) -> [(fecha, ms, excepción)]
    reintentos = defaultdict(int)   # (usuario, método POST, ruta) -> fallos (>= 400)
    llm = []                        # (fecha, modelo, gpu, ms, estado, intento)
    leidas = 0
    ultima_excepcion = ''
    ultimo_usuario_ip = dict(mapa_ip_usuario)
    # La línea estructurada (con usuario) precede a la de uvicorn (con IP) para la misma petición:
    # emparejándolas se aprende qué usuario hay detrás de cada IP sin consultar nada más.
    pendiente_por_ruta = {}
    usuarios_por_ip = defaultdict(set)   # IP compartidas (NAT de una sede) -> usuario incierto

    for ts, linea in leer_journal(horas):
        leidas += 1
        m = RE_ESTRUCTURADA.match(linea)
        if m:
            status = int(m['status'])
            usuario = m['user'] or ''
            ruta = _ruta_sin_consulta(m['path'])
            if usuario:
                pendiente_por_ruta[(m['method'], m['path'])] = usuario
            if status >= 500 or status == 429:
                http[(usuario, status, m['method'], ruta)].append((m['fecha'], float(m['ms']), ultima_excepcion))
                ultima_excepcion = ''
            if status >= 400 and m['method'] in ('POST', 'PUT', 'DELETE'):
                reintentos[(usuario, m['method'], ruta)] += 1
            continue
        m = RE_UVICORN.match(linea)
        if m:
            status = int(m['status'])
            usuario_par = pendiente_por_ruta.pop((m['method'], m['path']), None)
            if usuario_par:
                ultimo_usuario_ip[m['ip']] = usuario_par
                usuarios_por_ip[m['ip']].add(usuario_par)
            if status >= 500:
                # El middleware no registra la línea estructurada cuando la excepción no se controló:
                # se usa la línea de uvicorn con la IP y el último usuario visto desde esa IP.
                usuario = ultimo_usuario_ip.get(m['ip'], '')
                compartida = len(usuarios_por_ip.get(m['ip'], ())) > 3
                clave = (usuario, status, m['method'], _ruta_sin_consulta(m['path']))
                nota = 'IP compartida por varias personas, usuario INCIERTO' if compartida else 'usuario probable'
                http[clave].append((f'{ts} (por IP {m["ip"]}, {nota})', 0.0, ultima_excepcion))
                ultima_excepcion = ''
                if m['method'] in ('POST', 'PUT', 'DELETE'):
                    reintentos[(usuario, m['method'], _ruta_sin_consulta(m['path']))] += 1
            continue
        m = RE_LLM.match(linea)
        if m:
            llm.append((m['fecha'], m['modelo'], m['gpu'], int(m['ms']), m['estado'], int(m['intento'])))
            continue
        m = RE_EXCEPCION.match(linea)
        if m:
            ultima_excepcion = f'{m.group(1)}: {m.group(2)[:200]}'
    if leidas == 0:
        raise RuntimeError('journalctl no devolvió líneas reconocibles (¿cambió el formato o no hay permisos?)')
    return http, reintentos, llm


def hallazgos_http(http):
    """c) Respuestas 5xx y 429 por usuario y ruta."""
    salida = []
    for (usuario, status, metodo, ruta), filas in http.items():
        n = len(filas)
        excepciones = sorted({f[2] for f in filas if f[2]})
        por_reinicio = sum(1 for f in filas if MARCA_REINICIO in f[2])
        if status >= 500:
            gravedad = CRITICO if n >= 10 else ALTO
            titulo = f'HTTP {status} x{n} en {metodo} {ruta}'
            sugerencia = 'Error del servidor: corresponde al equipo de desarrollo del webmail. '
            if por_reinicio and por_reinicio >= n * 0.8:
                gravedad = MEDIO
                sugerencia = ('Casi todos coinciden con un reinicio del servicio (despliegue): peticiones cortadas a medio '
                              'camino. Si se repite sin despliegue, escalar a desarrollo. ')
            elif por_reinicio:
                sugerencia += f'{por_reinicio} de {n} coinciden con reinicio del servicio. '
        else:
            gravedad = ALTO if n >= 10 else (MEDIO if n >= 5 else BAJO)
            titulo = f'HTTP 429 (límite de peticiones) x{n} en {metodo} {ruta}'
            sugerencia = 'El usuario quedó bloqueado por reintentos; revisar si hubo un 500 previo que lo provocó. '
        if ruta in RUTAS_RUIDO and (not usuario or status == 429):
            gravedad = INFO
        if usuario in config.CUENTAS_PRUEBA:
            gravedad = max(gravedad, BAJO)
        ultima = filas[-1][0]
        salida.append(Hallazgo(
            gravedad, 'c', titulo, usuario,
            [f'Última vez: {ultima}', 'Excepciones: ' + ('; '.join(excepciones)[:400] if excepciones else '(sin traza asociada)')],
            sugerencia + (a_quien_preguntar(usuario) if usuario else 'Sin usuario en la línea (petición anónima o sin sesión).'),
        ))
    return salida


def hallazgos_reintentos(reintentos):
    """e) Misma ruta POST fallando más de N veces para el mismo usuario."""
    salida = []
    for (usuario, metodo, ruta), n in reintentos.items():
        if n <= config.REINTENTOS_MINIMO:
            continue
        gravedad = INFO if (ruta in RUTAS_RUIDO and not usuario) or usuario in config.CUENTAS_PRUEBA else (ALTO if n >= 20 else MEDIO)
        salida.append(Hallazgo(
            gravedad, 'e', f'{n} fallos (>= 400) en {metodo} {ruta}: reintentos o duplicados', usuario,
            [f'Más de {config.REINTENTOS_MINIMO} fallos seguidos en la misma acción en 24 h.'],
            a_quien_preguntar(usuario) + ' Preguntar si tuvo que reintentar varias veces (p. ej. enviar o guardar borrador).',
        ))
    return salida


def hallazgos_llm(llm):
    """f) Llamadas a la IA lentas o fallidas."""
    lentas = [l for l in llm if l[3] > config.LLM_LENTO_MS or l[4] not in ('ok', 'vacia')]
    if not lentas:
        return []
    por_modelo = defaultdict(list)
    for fecha, modelo, gpu, ms, estado, intento in lentas:
        por_modelo[(modelo, gpu)].append((fecha, ms, estado))
    salida = []
    for (modelo, gpu), filas in por_modelo.items():
        timeouts = sum(1 for f in filas if f[2] == 'timeout')
        gravedad = ALTO if timeouts >= 3 else MEDIO
        salida.append(Hallazgo(
            gravedad, 'f', f'IA {modelo} en {gpu}: {len(filas)} llamadas lentas/fallidas (> {config.LLM_LENTO_MS // 1000} s), {timeouts} por tiempo agotado', '',
            [f'Total de llamadas del día: {len(llm)}; ' + ', '.join(f'{f[0][11:16]} {f[1] / 1000:.0f}s {f[2]}' for f in filas[:8])],
            'Revisar carga de la GPU y el servicio de IA; si hay reintento automático al modelo 7b, el usuario solo nota lentitud.',
        ))
    return salida


def todo(horas, mapa_ip_usuario):
    http, reintentos, llm = recolectar(horas, mapa_ip_usuario)
    return hallazgos_http(http) + hallazgos_reintentos(reintentos) + hallazgos_llm(llm), len(llm)
