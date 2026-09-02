# -*- coding: utf-8 -*-
"""
Base de datos de Formularios del Almacén Maquita.
=================================================
La DEFINICIÓN del formulario vive en el archivo `.forma` del Drive (JSON), para
que herede permisos de unidad, compartir, papelera, versiones y búsqueda como
cualquier documento. Aquí se guarda solo lo que el archivo no puede saber:

  - `encuestas`            : el enlace público (token), su estado y sus ajustes.
  - `encuesta_respuestas`  : lo que la gente responde.

La unión entre ambos mundos es el `id` (UUID) que se escribe DENTRO del `.forma`:
copiar el archivo no duplica las respuestas hasta que el editor detecta que el id
ya pertenece a otra ruta y le asigna uno nuevo (ver `registrar`).

Autoría: Equipo de Tecnología Maquita — 2026-08-24
"""
import json
import logging
import secrets

import almacen_bd as bd

log = logging.getLogger('almacen.encuestas.bd')

LONGITUD_TOKEN = 22


def asegurar_esquema_encuestas():
    """Crea las tablas de formularios si no existen. Idempotente."""
    with bd.conexion() as con:
        with con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS encuestas (
                    id              TEXT PRIMARY KEY,
                    propietario     INTEGER NOT NULL,
                    ruta            TEXT NOT NULL,
                    titulo          TEXT NOT NULL DEFAULT '',
                    token           TEXT UNIQUE,
                    abierta         BOOLEAN NOT NULL DEFAULT TRUE,
                    solo_internos   BOOLEAN NOT NULL DEFAULT FALSE,
                    una_por_persona BOOLEAN NOT NULL DEFAULT FALSE,
                    creada_en       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    actualizada_en  TIMESTAMPTZ
                );
                CREATE TABLE IF NOT EXISTS encuesta_respuestas (
                    id          SERIAL PRIMARY KEY,
                    encuesta_id TEXT NOT NULL
                                REFERENCES encuestas(id) ON DELETE CASCADE,
                    usuario_id  INTEGER,
                    datos       JSONB NOT NULL,
                    enviada_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS encuesta_preferencias (
                    usuario_id INTEGER PRIMARY KEY,
                    ajustes    JSONB NOT NULL DEFAULT '{}'::jsonb
                );
                CREATE INDEX IF NOT EXISTS ix_encuestas_ruta
                    ON encuestas(propietario, ruta);
                CREATE INDEX IF NOT EXISTS ix_encuesta_resp
                    ON encuesta_respuestas(encuesta_id, enviada_en DESC);
            """)
            # Columnas añadidas después de la primera versión. Van con IF NOT
            # EXISTS para que el módulo siga siendo instalable de cero y
            # actualizable sin tocar la base a mano.
            cur.execute("""
                ALTER TABLE encuestas
                    ADD COLUMN IF NOT EXISTS ajustes JSONB NOT NULL
                        DEFAULT '{}'::jsonb;
                ALTER TABLE encuesta_respuestas
                    ADD COLUMN IF NOT EXISTS correo TEXT,
                    ADD COLUMN IF NOT EXISTS token_edicion TEXT,
                    ADD COLUMN IF NOT EXISTS puntos NUMERIC,
                    ADD COLUMN IF NOT EXISTS puntos_max NUMERIC,
                    ADD COLUMN IF NOT EXISTS calificacion JSONB,
                    ADD COLUMN IF NOT EXISTS revisada BOOLEAN NOT NULL
                        DEFAULT FALSE;
                CREATE INDEX IF NOT EXISTS ix_encuesta_resp_edicion
                    ON encuesta_respuestas(token_edicion)
                    WHERE token_edicion IS NOT NULL;
                ALTER TABLE encuestas
                    ADD COLUMN IF NOT EXISTS codigo TEXT;
                -- Hoja de cálculo vinculada: dónde quedó el .xlsx de las
                -- respuestas, para poder rehacerlo solo cuando llegan más.
                ALTER TABLE encuestas
                    ADD COLUMN IF NOT EXISTS hoja_ruta TEXT;
                CREATE UNIQUE INDEX IF NOT EXISTS ix_encuestas_codigo
                    ON encuestas(codigo) WHERE codigo IS NOT NULL;
            """)


# ---------------------------------------------------------------------------
# Formularios
# ---------------------------------------------------------------------------
def obtener(encuesta_id: str):
    """Fila del formulario, o None."""
    filas = bd.consultar('SELECT * FROM encuestas WHERE id = %s', (encuesta_id,))
    return filas[0] if filas else None


def obtener_por_token(token: str):
    """Fila del formulario a partir del token público, o None."""
    filas = bd.consultar('SELECT * FROM encuestas WHERE token = %s', (token,))
    return filas[0] if filas else None


def registrar(encuesta_id: str, propietario: int, ruta: str, titulo: str):
    """Da de alta el formulario (o refresca ruta y título si ya existía).

    Devuelve la fila resultante. Si el id ya está registrado para OTRA ruta —el
    caso de un `.forma` copiado o movido— no se pisa el original: se avisa al
    llamante devolviendo `None` para que asigne un id nuevo al archivo copiado.

    **También cuenta el PROPIETARIO, no solo la ruta.** Dos personas tienen
    rutas idénticas en sus unidades («/Nuevo Formulario.forma» es el nombre que
    pone el botón «+ Nuevo» a todo el mundo), así que comparar solo la ruta hacía
    que un `.forma` que llegara a la unidad de otra persona —copiado, restaurado
    o recibido en una carpeta compartida— se adueñara del registro del original:
    a partir de ahí las dos personas editaban el MISMO formulario y compartían
    sus respuestas. Con el propietario en la comparación, la copia recibe un id
    nuevo y arranca con su propia hoja de respuestas.
    """
    actual = obtener(encuesta_id)
    if actual and (actual['ruta'] != ruta
                   or int(actual['propietario']) != int(propietario)):
        return None
    if actual:
        bd.ejecutar(
            'UPDATE encuestas SET titulo = %s, actualizada_en = NOW() '
            'WHERE id = %s', (titulo[:300], encuesta_id))
        return obtener(encuesta_id)
    bd.ejecutar(
        'INSERT INTO encuestas (id, propietario, ruta, titulo) '
        'VALUES (%s, %s, %s, %s)',
        (encuesta_id, int(propietario), ruta, titulo[:300]))
    return obtener(encuesta_id)


def mover(encuesta_id: str, ruta_nueva: str):
    """Actualiza la ruta del `.forma` (renombrado o movido dentro del Drive)."""
    bd.ejecutar('UPDATE encuestas SET ruta = %s, actualizada_en = NOW() '
                'WHERE id = %s', (ruta_nueva, encuesta_id))


# Alfabeto del código corto: sin 0/O ni 1/l/I. El enlace se dicta por teléfono
# y se copia a mano de un cartel, y esos caracteres se confunden siempre.
ALFABETO = '23456789abcdefghjkmnpqrstuvwxyz'
# 8 caracteres de 31 posibles = 852.891.037.441 combinaciones. Se bajó de 10 a
# 8 para acortar el enlace; por debajo de 8 la cifra empieza a estar al alcance
# de un rastreo automático, y estos enlaces dan acceso a responder.
# Los códigos de 10 ya repartidos siguen valiendo: la búsqueda es por igualdad,
# no por longitud.
LONGITUD_CODIGO = 8


def _codigo_libre(intentos=12):
    """Un código corto que no esté usado.

    Se comprueba contra la base en vez de fiarse del azar: con 31^10 el choque
    es improbable, pero «improbable» no es «imposible», y el índice único haría
    fallar el guardado en la cara de quien esté publicando.
    """
    for _ in range(intentos):
        codigo = ''.join(secrets.choice(ALFABETO) for _ in range(LONGITUD_CODIGO))
        if not bd.consultar('SELECT 1 FROM encuestas WHERE codigo = %s LIMIT 1',
                            (codigo,)):
            return codigo
    return None      # rarísimo; quien llame decide qué hacer


def obtener_por_codigo(codigo: str):
    """La encuesta a la que apunta un código corto."""
    if not codigo:
        return None
    filas = bd.consultar('SELECT * FROM encuestas WHERE codigo = %s', (codigo,))
    return filas[0] if filas else None


def publicar(encuesta_id: str) -> str:
    """Genera el token del enlace público si aún no tiene, y lo devuelve.

    NO toca `abierta`. Antes lo ponía a TRUE, y eso pisaba en silencio a quien
    había apagado «Aceptar respuestas» a propósito: bastaba pulsar «Publicar» o
    pedir el código QR para que el formulario volviera a admitir envíos sin que
    nadie lo hubiera pedido.

    Son dos cosas distintas: tener enlace y aceptar respuestas. Un formulario
    nuevo ya nace con `abierta = TRUE` por el valor por defecto de la tabla, así
    que no hace falta forzarlo aquí.
    """
    fila = obtener(encuesta_id)
    if fila and fila.get('token'):
        # 27/08/2026 — aquí se salía sin mirar el código corto, y los
        # formularios publicados ANTES de que el código existiera (25/08) se
        # quedaban con token pero sin código para siempre. La pantalla arma el
        # enlace con «/f/<codigo>», así que salía «/f/» a secas y quien lo abría
        # se encontraba «Enlace incompleto». Se le pone el que le falta y se
        # devuelve el token de siempre, que sigue valiendo.
        if not fila.get('codigo'):
            bd.ejecutar('UPDATE encuestas SET codigo = %s WHERE id = %s '
                        'AND codigo IS NULL', (_codigo_libre(), encuesta_id))
        return fila['token']
    token = secrets.token_urlsafe(LONGITUD_TOKEN)
    # El código corto es lo que se comparte; el token largo se conserva porque
    # ya hay enlaces repartidos con él y tienen que seguir funcionando.
    codigo = _codigo_libre()
    bd.ejecutar('UPDATE encuestas SET token = %s, codigo = COALESCE(codigo, %s), '
                'actualizada_en = NOW() WHERE id = %s',
                (token, codigo, encuesta_id))
    return token


def revocar(encuesta_id: str):
    """Anula el enlace público. Las respuestas ya recibidas se conservan."""
    bd.ejecutar('UPDATE encuestas SET token = NULL, actualizada_en = NOW() '
                'WHERE id = %s', (encuesta_id,))


def listar_por_propietario(usuario_id: int, limite: int = 200):
    """Formularios de una persona, del más reciente al más antiguo.

    Lleva el número de respuestas para poder enseñarlo en el selector: ayuda a
    reconocer cuál es cuál cuando hay varios con nombres parecidos.
    """
    return bd.consultar("""
        SELECT e.ruta, e.titulo,
               (SELECT count(*) FROM encuesta_respuestas r
                 WHERE r.encuesta_id = e.id) AS respuestas
        FROM encuestas e
        WHERE e.propietario = %s
        ORDER BY COALESCE(e.actualizada_en, e.creada_en) DESC
        LIMIT %s
    """, (int(usuario_id), int(limite)))


def guardar_ajustes(encuesta_id: str, ajustes: dict):
    """Guarda el bloque JSON de ajustes de la pestaña «Configuración»."""
    bd.ejecutar("UPDATE encuestas SET ajustes = %s::jsonb, "
                "actualizada_en = NOW() WHERE id = %s",
                (json.dumps(ajustes, ensure_ascii=False), encuesta_id))


def preferencias(usuario_id: int):
    """Ajustes predeterminados de esta persona (se aplican a lo que cree)."""
    filas = bd.consultar('SELECT ajustes FROM encuesta_preferencias '
                         'WHERE usuario_id = %s', (int(usuario_id),))
    return (filas[0]['ajustes'] or {}) if filas else {}


def guardar_preferencias(usuario_id: int, ajustes: dict):
    bd.ejecutar(
        'INSERT INTO encuesta_preferencias (usuario_id, ajustes) '
        'VALUES (%s, %s::jsonb) ON CONFLICT (usuario_id) DO UPDATE '
        'SET ajustes = EXCLUDED.ajustes',
        (int(usuario_id), json.dumps(ajustes, ensure_ascii=False)))


def ajustar(encuesta_id: str, abierta=None, solo_internos=None,
            una_por_persona=None):
    """Cambia los ajustes de recepción. Los `None` se dejan como estaban."""
    campos, valores = [], []
    for nombre, valor in (('abierta', abierta),
                          ('solo_internos', solo_internos),
                          ('una_por_persona', una_por_persona)):
        if valor is not None:
            campos.append(nombre + ' = %s')
            valores.append(bool(valor))
    if not campos:
        return
    valores.append(encuesta_id)
    bd.ejecutar('UPDATE encuestas SET ' + ', '.join(campos) +
                ', actualizada_en = NOW() WHERE id = %s', tuple(valores))


# ---------------------------------------------------------------------------
# Respuestas
# ---------------------------------------------------------------------------
def guardar_respuesta(encuesta_id: str, datos: str, usuario_id=None,
                      correo=None, token_edicion=None, calificacion=None):
    """Inserta una respuesta. `datos` ya viene serializado como JSON.

    Devuelve el id y el token de edición, que es lo que necesita la página
    pública para ofrecer «modificar tu respuesta».
    """
    filas = bd.consultar(
        'INSERT INTO encuesta_respuestas '
        '(encuesta_id, usuario_id, datos, correo, token_edicion, '
        ' puntos, puntos_max, calificacion) '
        'VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb) RETURNING id',
        (encuesta_id, usuario_id, datos, correo, token_edicion,
         (calificacion or {}).get('puntos'),
         (calificacion or {}).get('puntos_max'),
         json.dumps(calificacion, ensure_ascii=False) if calificacion else None))
    return filas[0]['id'] if filas else None


def guardar_calificacion(respuesta_id: int, calificacion: dict, revisada=False):
    """Reescribe la nota de una respuesta (recalculada o puesta a mano)."""
    bd.ejecutar(
        'UPDATE encuesta_respuestas SET puntos = %s, puntos_max = %s, '
        'calificacion = %s::jsonb, revisada = %s WHERE id = %s',
        (calificacion.get('puntos'), calificacion.get('puntos_max'),
         json.dumps(calificacion, ensure_ascii=False), bool(revisada),
         int(respuesta_id)))


def respuesta(encuesta_id: str, respuesta_id: int):
    """Una respuesta concreta del formulario indicado.

    El `encuesta_id` va en el WHERE por lo mismo de siempre: un id suelto no
    debe servir para llegar a la respuesta de otro formulario.
    """
    filas = bd.consultar(
        'SELECT id, usuario_id, datos, correo, enviada_en, puntos, puntos_max, '
        'calificacion, revisada FROM encuesta_respuestas '
        'WHERE id = %s AND encuesta_id = %s',
        (int(respuesta_id), encuesta_id))
    return filas[0] if filas else None


def respuesta_por_edicion(encuesta_id: str, token_edicion: str):
    """La respuesta que corresponde a un enlace de modificación.

    El `encuesta_id` va en el WHERE por lo mismo que en el borrado: un token
    suelto no debe servir para llegar a otro formulario.
    """
    if not token_edicion:
        return None
    filas = bd.consultar(
        'SELECT id, usuario_id, datos, correo, enviada_en '
        'FROM encuesta_respuestas WHERE encuesta_id = %s AND token_edicion = %s',
        (encuesta_id, token_edicion))
    return filas[0] if filas else None


def actualizar_respuesta(respuesta_id: int, datos: str):
    """Reescribe una respuesta ya enviada (ajuste «permitir modificar»)."""
    bd.ejecutar('UPDATE encuesta_respuestas SET datos = %s::jsonb, '
                'enviada_en = NOW() WHERE id = %s', (datos, int(respuesta_id)))


def ya_respondio(encuesta_id: str, usuario_id: int) -> bool:
    """¿Este usuario ya envió una respuesta? (ajuste «una por persona»)."""
    if not usuario_id:
        return False
    filas = bd.consultar(
        'SELECT 1 FROM encuesta_respuestas WHERE encuesta_id = %s '
        'AND usuario_id = %s LIMIT 1', (encuesta_id, int(usuario_id)))
    return bool(filas)


def ya_respondio_correo(encuesta_id: str, correo: str) -> bool:
    """¿Este CORREO ya envió una respuesta? (27/08/2026)

    «Una sola respuesta por persona» necesita reconocer a quien responde, y la
    sesión de FARO no es la única forma de hacerlo: si el formulario recoge el
    correo, ese correo identifica igual de bien y además sirve para gente de
    fuera de la casa, que es justo a quien se reparte el enlace o el QR.

    Se compara en minúsculas y sin espacios porque la misma persona escribe su
    correo de formas distintas y, si no, «Ana@x.ec» y «ana@x.ec» contarían como
    dos.
    """
    limpio = (correo or '').strip().lower()
    if not limpio:
        return False
    filas = bd.consultar(
        'SELECT 1 FROM encuesta_respuestas WHERE encuesta_id = %s '
        'AND lower(trim(correo)) = %s LIMIT 1', (encuesta_id, limpio))
    return bool(filas)


def contar_respuestas(encuesta_id: str) -> int:
    filas = bd.consultar('SELECT COUNT(*) AS n FROM encuesta_respuestas '
                         'WHERE encuesta_id = %s', (encuesta_id,))
    return int(filas[0]['n']) if filas else 0


def listar_respuestas(encuesta_id: str, limite: int = 2000):
    """Respuestas de la más reciente a la más antigua."""
    return bd.consultar(
        'SELECT id, usuario_id, datos, correo, enviada_en, puntos, '
        'puntos_max, calificacion, revisada FROM encuesta_respuestas '
        'WHERE encuesta_id = %s ORDER BY enviada_en DESC LIMIT %s',
        (encuesta_id, int(limite)))


def borrar_respuesta(encuesta_id: str, respuesta_id: int) -> bool:
    """Borra UNA respuesta (la papelera de la vista Individual).

    El `encuesta_id` va en el WHERE a propósito: sin él, un id de respuesta
    ajeno bastaría para borrar de otro formulario.
    """
    filas = bd.consultar(
        'DELETE FROM encuesta_respuestas WHERE id = %s AND encuesta_id = %s '
        'RETURNING id', (int(respuesta_id), encuesta_id))
    return bool(filas)


def borrar_respuestas(encuesta_id: str):
    """Vacía las respuestas del formulario (acción del propietario)."""
    bd.ejecutar('DELETE FROM encuesta_respuestas WHERE encuesta_id = %s',
                (encuesta_id,))


def nombres_usuarios(ids):
    """Nombre visible de cada usuario que respondió (para la tabla)."""
    limpios = sorted({int(i) for i in ids if i})
    if not limpios:
        return {}
    try:
        filas = bd.consultar("""
            SELECT u.id,
                   COALESCE(t.nombres || ' ' || t.apellidos,
                            u.full_name, u.username) AS nombre
            FROM usuarios u
            LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.id = ANY(%s)
        """, (limpios,), nomina=True)
    except Exception as excepcion:
        log.warning('No se pudieron leer los nombres: %s', excepcion)
        return {}
    return {f['id']: (f.get('nombre') or ('Usuario ' + str(f['id'])))
            for f in filas}
