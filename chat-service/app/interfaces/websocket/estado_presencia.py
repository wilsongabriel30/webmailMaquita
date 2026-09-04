# -*- coding: utf-8 -*-
"""T-48 - La REGLA del estado de presencia (que puntito se ve).

Aqui vive solo la decision, sin rutas ni HTML, para poder usarla desde cualquier sitio: la
lista de conversaciones, la ficha del companero (T-43) y el endpoint del cliente Windows.

La regla la pidio soporte con una idea clara: **el puntito no debe mentir**. De poco sirve
que alguien diga "conectado" si cerro el equipo hace dos horas; por eso el estado elegido a
mano solo manda mientras la persona esta realmente conectada.

Orden de decision (gana el primero que se cumple):
  1. eligio "aparecer desconectado" -> DESCONECTADO (manda sobre todo lo demas)
  2. esta en una llamada o reunion  -> OCUPADO      (lo sabe el servidor, es global)
  3. eligio ocupado o no molestar   -> eso mismo    (aguantan la jornada)
  4. no tiene ninguna conexion viva -> DESCONECTADO (ver _conexion_viva: no vale con que
                                                     exista la clave, tiene que estar fresca)
  5. lleva mas de 5 minutos quieto  -> AUSENTE
  6. eligio ausente o vuelvo enseguida -> eso mismo
  7. en cualquier otro caso         -> DISPONIBLE
"""
import time

# La lista es la de Teams, para que la gente reconozca los puntitos sin explicaciones.
DISPONIBLE = 'disponible'           # verde
OCUPADO = 'ocupado'                 # rojo solido
NO_MOLESTAR = 'no_molestar'         # rojo con raya; ademas silencia lo no urgente
VUELVO_ENSEGUIDA = 'vuelvo_enseguida'   # amarillo con reloj
AUSENTE = 'ausente'                 # amarillo con reloj ("aparecer como ausente")
DESCONECTADO = 'desconectado'       # gris con equis ("aparecer desconectado")
AUTO = 'auto'                       # no es un estado: significa "vuelve al automatico"

VALIDOS = (DISPONIBLE, OCUPADO, NO_MOLESTAR, VUELVO_ENSEGUIDA, AUSENTE, DESCONECTADO)
ACEPTADOS = VALIDOS + (AUTO,)

# el cliente antiguo mandaba "conectado"; se sigue aceptando para no romperlo
SINONIMOS = {'conectado': DISPONIBLE, 'online': DISPONIBLE, 'disponible ': DISPONIBLE,
             'no molestar': NO_MOLESTAR, 'nomolestar': NO_MOLESTAR,
             'no_disponible': DESCONECTADO, 'offline': DESCONECTADO}

# los que la persona elige y mandan aunque el automatico opine otra cosa
ELECCIONES_FIRMES = (OCUPADO, NO_MOLESTAR, DESCONECTADO)

CONECTADO = DISPONIBLE   # nombre viejo, para no romper lo que ya lo usaba


def normalizar(valor):
    """Convierte lo que llegue en uno de los valores validos, o None si no lo es."""
    v = str(valor or '').strip().lower().replace('-', '_').replace(' ', '_')
    v = SINONIMOS.get(v, v)
    return v if v in ACEPTADOS else None

INACTIVIDAD = 5 * 60          # 5 minutos quieto y se pasa a Ausente
VIDA_ELECCION = 16 * 60 * 60  # lo elegido a mano dura la jornada
VIDA_ACTIVIDAD = 30 * 60      # cuanto se recuerda la ultima senal de vida
VIDA_LLAMADA = 4 * 60 * 60    # tope de seguridad si nunca llega el "sali de la llamada"
VIDA_CONEXION = 300           # el TTL con que el socket refresca su senal de vida
LATIDO_FRESCO = 60            # refrescada hace menos de un minuto = alguien esta ahi de verdad

CLAVE_ELECCION = 'chat:estado:%s'
CLAVE_ACTIVIDAD = 'chat:actividad:%s'
CLAVE_LLAMADA = 'chat:enllamada:%s'
CLAVE_CONEXION = 'chat:presence:%s'   # la que ya escribia el socket al conectarse


def _redis():
    """El mismo Redis que usa el resto del chat; si no hay, se sigue sin estados."""
    try:
        from interfaces.websocket import manejador_websocket as mw
        return mw._ws_redis
    except Exception:
        return None


def guardar_eleccion(usuario_id, estado):
    """Guarda lo que la persona eligio a mano. Devuelve si se pudo guardar."""
    estado = normalizar(estado)
    if estado is None:
        raise ValueError('estado no valido')
    r = _redis()
    if not r:
        return False
    if estado in (AUTO, DISPONIBLE):
        # "Restablecer estado" y "Disponible" son lo mismo: quitar la eleccion y dejar
        # que mande la realidad (si esta conectada dira Disponible; si no, la verdad)
        r.delete(CLAVE_ELECCION % usuario_id)
    else:
        r.set(CLAVE_ELECCION % usuario_id, estado, ttl_segundos=VIDA_ELECCION)
    marcar_actividad(usuario_id)
    return True


def marcar_actividad(usuario_id):
    """Deja constancia de que la persona sigue ahi (lo llama cada peticion suya)."""
    r = _redis()
    if r:
        r.set(CLAVE_ACTIVIDAD % usuario_id, str(int(time.time())), ttl_segundos=VIDA_ACTIVIDAD)


def marcar_en_llamada(usuario_id, en_llamada):
    """Lo llama el servidor cuando alguien entra o sale de una llamada o reunion."""
    r = _redis()
    if not r:
        return
    if en_llamada:
        r.set(CLAVE_LLAMADA % usuario_id, '1', ttl_segundos=VIDA_LLAMADA)
    else:
        r.delete(CLAVE_LLAMADA % usuario_id)


def _conexion_viva(r, uid):
    """Decide si de verdad hay alguien conectado.

    No basta con que exista la clave del socket: cuando una conexion muere de mala manera
    puede quedar un "fantasma" en la lista de sesiones y esa clave no se borra (por eso
    existe la herramienta limpiar-fantasmas-chat). Fiarse solo de ella haria que el
    Ausente automatico no llegara NUNCA para esas personas, que es justo el falso positivo
    que se quiere evitar.

    Asi que se exige una senal de vida REFRESCADA: o el socket volvio a marcar su presencia
    hace menos de un minuto (se mira cuanta vida le queda a la clave), o la persona ha hecho
    algo hace poco. Un fantasma que nadie refresca deja de contar en cuanto caduca.
    """
    if not r.exists(CLAVE_CONEXION % uid):
        return False
    try:
        restante = r.ttl(CLAVE_CONEXION % uid)
    except Exception:
        restante = -1
    if restante > (VIDA_CONEXION - LATIDO_FRESCO):
        return True                      # refrescada hace nada: hay alguien
    return _actividad_reciente(r, uid)


def _actividad_reciente(r, uid):
    """Si la persona ha dado senales de vida en los ultimos 5 minutos."""
    try:
        ultima = int(r.get(CLAVE_ACTIVIDAD % uid) or 0)
    except (TypeError, ValueError):
        return False
    return bool(ultima) and (time.time() - ultima) <= INACTIVIDAD


def estado_de(usuario_id):
    """Devuelve el estado que hay que PINTAR para ese usuario, aplicando la regla."""
    r = _redis()
    if not r:
        # sin Redis no hay forma de saberlo; se dice Desconectado antes que mentir
        return DESCONECTADO
    uid = usuario_id
    eleccion = normalizar(r.get(CLAVE_ELECCION % uid))

    # "Aparecer desconectado" manda sobre todo: si alguien pidio no figurar, no figura,
    # ni siquiera aunque entre a una llamada.
    if eleccion == DESCONECTADO:
        return DESCONECTADO
    if r.exists(CLAVE_LLAMADA % uid):
        return OCUPADO
    if eleccion in ELECCIONES_FIRMES:
        return eleccion
    if not _conexion_viva(r, uid):
        # sin ninguna conexion viva la verdad es que no esta: gris, como en Teams
        return DESCONECTADO
    if not _actividad_reciente(r, uid):
        return AUSENTE
    if eleccion in (AUSENTE, VUELVO_ENSEGUIDA):
        return eleccion
    return DISPONIBLE


def estados_de(usuario_ids):
    """El estado de varios usuarios de una vez (para pintar una lista)."""
    return {uid: estado_de(uid) for uid in set(usuario_ids or []) if uid}


def detalle_de(usuario_id):
    """El estado mas el porque, para que el cliente pueda explicarlo si quiere."""
    r = _redis()
    estado = estado_de(usuario_id)
    eleccion = normalizar(r.get(CLAVE_ELECCION % usuario_id)) if r else None
    return {
        'estado': estado,
        'elegido': eleccion or AUTO,
        'automatico': eleccion is None,
        'silencia_avisos': estado == NO_MOLESTAR,
        'en_llamada': bool(r and r.exists(CLAVE_LLAMADA % usuario_id)),
        'conectado': bool(r and r.exists(CLAVE_CONEXION % usuario_id)),
    }
