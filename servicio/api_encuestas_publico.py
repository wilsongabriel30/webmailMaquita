# -*- coding: utf-8 -*-
"""
Página pública de Formularios del Almacén Maquita (responder por enlace).
=========================================================================
Esta es la cara que ve quien responde. Va aparte de `api_encuestas.py` a
propósito: aquí NO hay sesión iniciada ni permisos del Drive, y la única llave es
el token del enlace. Mezclar ambos mundos en un archivo es como se cuelan los
agujeros, así que se separan.

Vive FUERA de `/api/almacen` y `/archivos-almacen` para no chocar con el candado
maestro (`integracion_faro`), que exige sesión en esos dos prefijos.

  GET  /formulario/<token>              → página para responder
  GET  /api/formulario/<token>          → definición pública (sin respuestas)
  POST /api/formulario/<token>          → registra una respuesta
  GET  /api/formulario/<token>/imagen/<id> → imagen del formulario

Lo que este módulo NUNCA expone: las respuestas ya recibidas, la ruta del
archivo en el Drive, ni quién es el propietario.

Autoría: Equipo de Tecnología Maquita — 2026-08-24
"""
import json
import logging
import os
import re
import secrets

from flask import Blueprint, current_app, jsonify, request, send_file

import almacen_bd as bd
import encuestas_ajustes as ajustes_mod
import encuestas_bd as ebd
import encuestas_calificar as calificar
import encuestas_correo as correo_mod
import encuestas_imagenes as imagenes
import encuestas_modelo as modelo
from api_encuestas import _leer_definicion, _limpiar_definicion

log = logging.getLogger('almacen.encuestas.publico')

bp_encuestas_publico = Blueprint('almacen_encuestas_publico', __name__)

# Página de inicio de sesión de FARO. Está escrita aquí y no adivinada con
# `url_for`, porque este blueprint se sirve SIN sesión y sin el contexto de los
# módulos de FARO. Si la ruta cambiara, se cambia aquí: la comprobación es
# `curl -o /dev/null -w '%{http_code}' https://datos.maquita.com.ec/auth/iniciar-sesion`
# y tiene que devolver 200.
LOGIN = '/auth/iniciar-sesion'

LIMITE_TEXTO = 5000


def _fallo(mensaje, codigo=400):
    return jsonify({'success': False, 'error': mensaje}), codigo


def _usuario_faro():
    """ID del usuario si quien responde tiene la sesión abierta; si no, None.

    Sirve para dos cosas: mostrar quién respondió cuando es gente de la casa, y
    hacer cumplir los ajustes «solo internos» y «una respuesta por persona».
    """
    try:
        from flask import session
        from flask_login import current_user
        uid = session.get('usuario_id')
        if not uid and getattr(current_user, 'is_authenticated', False):
            uid = current_user.id
        return int(uid) if uid else None
    except Exception:
        return None


MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')


def _en_palabras(momento):
    """«12 de septiembre de 2026 a las 17:30». Quien responde no tiene por qué
    descifrar un 2026-09-12T17:30."""
    if not momento:
        return ''
    return '%d de %s de %d a las %02d:%02d' % (
        momento.day, MESES[momento.month - 1], momento.year,
        momento.hour, momento.minute)


def _fuera_de_plazo(fila):
    """Aviso si el formulario todavía no abre o ya cerró; None si se puede.

    Se comprueba AQUÍ, en el punto por el que pasan tanto el enlace como el
    código QR: el QR no es otra puerta, codifica ese mismo enlace. Ponerlo en la
    página sería inútil, porque la hora del navegador la decide quien responde.
    """
    ajustes = ajustes_mod.limpiar(fila.get('ajustes'))
    estado, apertura, cierre = ajustes_mod.estado_plazo(ajustes)
    if estado == 'antes':
        return _fallo('Este formulario todavía no está abierto. Se podrá '
                      'responder a partir del %s.' % _en_palabras(apertura), 403)
    if estado == 'despues':
        return _fallo('El plazo para responder terminó el %s.'
                      % _en_palabras(cierre), 403)
    return None


def _cargar_publico(token):
    """(fila, definicion) del formulario, o (None, respuesta_error).

    Acepta las DOS llaves: el código corto que se comparte hoy
    (`/f/k3m9pq2xzt`) y el token largo de siempre (`/formulario/H_qSLi…`).
    Los enlaces largos ya están repartidos por correo, en carteles y en códigos
    QR impresos: dejar de reconocerlos sería romperlos.
    """
    llave = token or ''
    fila = ebd.obtener_por_token(llave) or ebd.obtener_por_codigo(llave)
    if not fila:
        return None, _fallo('Este formulario no existe o el enlace fue '
                            'desactivado.', 404)
    if not fila.get('abierta'):
        return None, _fallo('Este formulario ya no recibe respuestas.', 403)
    definicion = _leer_definicion(fila['propietario'], fila['ruta'])
    if definicion is None:
        return None, _fallo('El formulario ya no está disponible.', 404)
    return (fila, _limpiar_definicion(definicion)), None


# ---------------------------------------------------------------------------
# Definición pública
# ---------------------------------------------------------------------------
def _por_que_no(token):
    """¿Por qué NO se puede responder este formulario? (motivo, código HTTP).

    CUIDADO AL EDITAR: esta función auxiliar va ANTES de los decoradores de
    `definicion_publica`, nunca entre ellos y su `def`. El 25/08/2026 se insertó
    justo debajo y se quedó con las rutas: Flask registró ESTA función como
    manejador de `/api/formulario/<token>`, `definicion_publica` se quedó sin
    ruta, y toda la API pública de lectura empezó a devolver 500 —«did not
    return a valid response»— porque aquí se devuelve una tupla `(motivo,
    código)`, no una respuesta. Es la misma trampa que en `api_archivos.subir()`
    el 29/07/2026.


    Devuelve (None, None) si sí se puede.

    Está aparte porque la usan DOS sitios: la API que entrega el formulario y
    la ruta que sirve la página. Antes solo miraba la API, así que la página se
    entregaba siempre y el aviso aparecía un instante después, ya cargada. Con
    esto, un formulario cerrado, caducado o ajeno no llega a mostrarse.
    """
    fila = ebd.obtener_por_token(token or '') or ebd.obtener_por_codigo(token or '')
    if not fila:
        return ('Este formulario no existe o el enlace fue desactivado.', 404)
    if not fila.get('abierta'):
        return ('Este formulario ya no recibe respuestas.', 403)

    definicion = _leer_definicion(fila['propietario'], fila['ruta'])
    if definicion is None:
        return ('El formulario ya no está disponible.', 404)
    definicion = _limpiar_definicion(definicion)

    ajustes = ajustes_mod.limpiar(fila.get('ajustes'))
    estado, apertura, cierre = ajustes_mod.estado_plazo(ajustes)
    if estado == 'antes':
        return ('Este formulario todavía no está abierto. Se podrá responder a '
                'partir del %s.' % _en_palabras(apertura), 403)
    if estado == 'despues':
        return ('El plazo para responder terminó el %s.' % _en_palabras(cierre), 403)

    usuario = _usuario_faro()
    if fila.get('solo_internos') and not usuario:
        return ('Este formulario es solo para personas de Maquita. '
                'Inicia sesión para responderlo.', 401)
    if fila.get('una_por_persona') and usuario and \
            ebd.ya_respondio(definicion['id'], usuario):
        return ('Ya registraste tu respuesta en este formulario.', 409)

    return (None, None)


@bp_encuestas_publico.route('/api/f/<token>', methods=['GET'])
@bp_encuestas_publico.route('/api/formulario/<token>', methods=['GET'])
def definicion_publica(token):
    """Lo mínimo para pintar el formulario. Nunca incluye respuestas."""
    # La MISMA comprobación que hace la página, para que no puedan discrepar:
    # si la página se sirve, esto entrega; si la página avisa, esto también.
    motivo, codigo = _por_que_no(token)
    if motivo:
        return _fallo(motivo, codigo)

    datos, fallo = _cargar_publico(token)
    if fallo:
        return fallo
    fila, definicion = datos
    usuario = _usuario_faro()

    # Se entregan las PÁGINAS ya repartidas: cada sección abre una nueva, y la
    # página pública las presenta de una en una.
    ajustes = ajustes_mod.limpiar(fila.get('ajustes'))
    paginas = modelo.paginas(definicion)
    if ajustes['preguntas_aleatorias']:
        paginas = _barajar(paginas, definicion['id'])
    # SIEMPRE: la clave de respuestas no puede salir de aquí. Iba dentro de
    # cada pregunta y llegaba al navegador antes de contestar, así que quien
    # abriera las herramientas del navegador veía el examen resuelto.
    paginas = _sin_clave(paginas)

    return jsonify({'success': True, 'formulario': {
        'titulo': definicion['titulo'],
        'descripcion': definicion['descripcion'],
        'mensaje_final': definicion['mensaje_final'],
        'tema': definicion.get('tema') or {},
        'cabecera': definicion.get('cabecera'),
        'paginas': paginas,
        # Solo lo que la página pública necesita saber para comportarse: nunca
        # los ajustes internos del formulario.
        'pide_correo': ajustes['recopilar_correo'],
        'correo_sesion': _correo_de(usuario)
        if ajustes['recopilar_correo'] == ajustes_mod.CORREO_VERIFICADO else '',
        'ofrece_copia': ajustes['copia_respuesta'],
        'barra_progreso': ajustes['barra_progreso'],
        'enlace_otra_respuesta': ajustes['enlace_otra_respuesta'],
        'ver_resumen': ajustes['ver_resumen'],
        'sin_autoguardado': ajustes['sin_autoguardado'],
        'permitir_editar': ajustes['permitir_editar'],
        'anonimo': ajustes['anonimo'],
        'cuestionario': ajustes['cuestionario'],
        'puntos_totales': (calificar.total_posible(definicion)
                           if ajustes['cuestionario'] else 0),
    }})


def _sin_clave(paginas):
    """Copia de las páginas sin la clave de respuestas de cada pregunta.

    Se copia en vez de borrar sobre el original porque `definicion` se sigue
    usando después para calificar: si se le quitara la clave aquí, la
    calificación se quedaría sin nada contra lo que comparar.
    """
    limpias = []
    for pagina in paginas:
        elementos = []
        for elemento in pagina:
            if 'clave' in elemento:
                elemento = {k: v for k, v in elemento.items() if k != 'clave'}
            elementos.append(elemento)
        limpias.append(elementos)
    return limpias


def _barajar(paginas, semilla):
    """Orden aleatorio de preguntas, como el ajuste de Google.

    Se baraja DENTRO de cada página y solo las preguntas: mover un título o una
    sección de sitio rompería el hilo de lectura del formulario.
    """
    import random
    revuelto = []
    for pagina in paginas:
        preguntas = [e for e in pagina if e['clase'] == 'pregunta']
        random.shuffle(preguntas)
        salida, siguiente = [], iter(preguntas)
        for elemento in pagina:
            salida.append(next(siguiente) if elemento['clase'] == 'pregunta'
                          else elemento)
        revuelto.append(salida)
    return revuelto


def _correo_de(usuario_id):
    """Correo de quien tiene la sesión abierta (para «correo verificado»).

    Se prefiere el institucional del expediente y, si no, el de la cuenta.
    """
    if not usuario_id:
        return ''
    try:
        filas = bd.consultar("""
            SELECT COALESCE(NULLIF(t.email_institucional, ''),
                            NULLIF(u.email, ''),
                            NULLIF(t.email_personal, '')) AS correo
            FROM usuarios u
            LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.id = %s
        """, (int(usuario_id),), nomina=True)
    except Exception as excepcion:
        log.warning('No se pudo leer el correo del usuario: %s', excepcion)
        return ''
    return (filas[0].get('correo') or '') if filas else ''


# ---------------------------------------------------------------------------
# Envío de una respuesta
# ---------------------------------------------------------------------------
def _admisible(pregunta, texto):
    """¿Ese texto es una opción de la pregunta?

    Con «Otro» activado se admite además cualquier texto que la persona escriba:
    es justo para lo que sirve esa casilla. Sin «Otro», nada fuera de la lista.
    """
    if texto in pregunta['opciones']:
        return True
    return bool(pregunta.get('otro')) and bool(texto)


def _valor_limpio(pregunta, bruto):
    """Normaliza una respuesta al tipo de su pregunta.

    Devuelve `(valor, error)`. El valor `None` significa «sin responder», que
    solo es aceptable si la pregunta no es obligatoria.
    """
    tipo = pregunta['tipo']

    if tipo == 'casillas':
        if not isinstance(bruto, list):
            bruto = [] if bruto in (None, '') else [bruto]
        validas = [str(v)[:300] for v in bruto if _admisible(pregunta, str(v)[:300])]
        return (validas or None), None

    if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
        return None, None

    if tipo in ('opcion_unica', 'desplegable'):
        texto = str(bruto)[:300]
        if not _admisible(pregunta, texto):
            return None, 'Opción no válida en «%s»' % modelo.plano(pregunta['titulo'])
        return texto, None

    if tipo == 'escala':
        try:
            numero = int(bruto)
        except (TypeError, ValueError):
            return None, 'Valor no válido en «%s»' % modelo.plano(pregunta['titulo'])
        if not 1 <= numero <= int(pregunta.get('escala_max') or 5):
            return None, 'Valor fuera de rango en «%s»' % modelo.plano(pregunta['titulo'])
        return numero, None

    # texto_corto, parrafo y fecha se guardan como texto acotado
    return str(bruto).strip()[:LIMITE_TEXTO], None


@bp_encuestas_publico.route('/api/f/<token>', methods=['POST'])
@bp_encuestas_publico.route('/api/formulario/<token>', methods=['POST'])
def enviar_respuesta(token):
    """Registra una respuesta. Valida contra la definición viva del archivo."""
    datos, fallo = _cargar_publico(token)
    if fallo:
        return fallo
    fila, definicion = datos

    fuera = _fuera_de_plazo(fila)     # plazo: vale igual por enlace y por QR
    if fuera:
        return fuera

    usuario = _usuario_faro()
    if fila.get('solo_internos') and not usuario:
        return _fallo('Este formulario es solo para personas de Maquita. '
                      'Inicia sesión para responderlo.', 401)
    if fila.get('una_por_persona') and usuario and \
            ebd.ya_respondio(definicion['id'], usuario):
        return _fallo('Ya registraste tu respuesta en este formulario.', 409)

    cuerpo = request.get_json(silent=True) or {}
    enviado = cuerpo.get('respuestas')
    if not isinstance(enviado, dict):
        return _fallo('No se recibió ninguna respuesta.', 400)

    ajustes = ajustes_mod.limpiar(fila.get('ajustes'))

    # El correo, si el formulario lo pide. «Verificado» no se fía de lo que
    # mande el navegador: se toma de la sesión.
    correo = ''
    if ajustes['recopilar_correo'] == ajustes_mod.CORREO_VERIFICADO:
        correo = _correo_de(usuario)
        if not correo:
            return _fallo('No se pudo obtener el correo de tu cuenta. '
                          'Avisa a quien te compartió el formulario.', 400)
    elif ajustes['recopilar_correo'] == ajustes_mod.CORREO_ESCRITO:
        correo = correo_mod.correo_valido(cuerpo.get('correo'))
        if not correo:
            return _fallo('Escribe un correo electrónico válido.', 400)

    # «Una sola respuesta por persona», también por CORREO. La comprobación por
    # usuario se hizo arriba, al abrir; esta va aquí porque el correo no se sabe
    # hasta que la persona lo escribe. Sin esto, el límite solo se cumplía con
    # la sesión de FARO y quedaba de adorno en los formularios abiertos.
    if fila.get('una_por_persona') and correo and \
            ebd.ya_respondio_correo(definicion['id'], correo):
        return _fallo('Ya se registró una respuesta con ese correo '
                      'electrónico. Este formulario admite una sola por '
                      'persona.', 409)

    limpias = {}
    for pregunta in modelo.preguntas(definicion):
        valor, problema = _valor_limpio(pregunta, enviado.get(pregunta['id']))
        if problema:
            return _fallo(problema, 400)
        if valor is None and pregunta['obligatoria']:
            return _fallo('Falta responder «%s».' % modelo.plano(pregunta['titulo']), 400)
        if valor is not None:
            limpias[pregunta['id']] = valor

    # Si se puede modificar la respuesta, hace falta una llave para volver a
    # ella. Se genera solo en ese caso: sin la opción no hay nada que abrir.
    token_edicion = secrets.token_urlsafe(24) if ajustes['permitir_editar'] else None

    # Modo cuestionario: se califica en el momento de recibir, no al mirar las
    # respuestas. Así la nota queda grabada con la entrega y no cambia si luego
    # se toca la clave; corregir la clave y recalcular es una decisión aparte.
    calificacion = (calificar.calificar(definicion, limpias)
                    if ajustes['cuestionario'] else None)

    # Anónimo: NO se guarda quién responde. Se descarta aquí, en el último
    # momento antes de escribir, y no antes: el usuario se ha necesitado para
    # comprobar el acceso. Lo que no se guarda no se puede filtrar después.
    if ajustes['anonimo']:
        usuario = None
        correo = ''

    try:
        ebd.guardar_respuesta(definicion['id'],
                              json.dumps(limpias, ensure_ascii=False),
                              usuario_id=usuario, correo=correo or None,
                              token_edicion=token_edicion,
                              calificacion=calificacion)
    except Exception as excepcion:
        log.error('respuesta de %s: %s', definicion['id'], excepcion)
        return _fallo('No se pudo registrar tu respuesta. Inténtalo de nuevo.',
                      500)

    # La hoja de cálculo vinculada se rehace sola con cada respuesta, en
    # segundo plano: quien acaba de responder no tiene por qué esperar a que se
    # escriba un Excel, y si eso fallara su respuesta ya está guardada.
    try:
        import encuestas_hoja as hoja_mod
        hoja_mod.refrescar_en_segundo_plano(fila, definicion)
    except Exception as excepcion:
        log.warning('no se pudo refrescar la hoja de %s: %s',
                    definicion['id'], excepcion)

    enlace_edicion = (request.host_url.rstrip('/') + '/formulario/' + token +
                      '?editar=' + token_edicion) if token_edicion else None

    _quiza_enviar_copia(ajustes, cuerpo, correo, definicion, limpias,
                        enlace_edicion)

    respuesta = {'success': True,
                 'mensaje_final': definicion['mensaje_final'],
                 'enlace_edicion': enlace_edicion}

    if calificacion:
        # Lo que se enseña se arma a medida: si el cuestionario no comparte las
        # respuestas correctas, esas respuestas ni siquiera salen del servidor.
        vista = calificar.para_quien_responde(definicion, calificacion, ajustes)
        if vista:
            respuesta['calificacion'] = vista
        elif ajustes['publicar_nota'] == ajustes_mod.NOTA_MANUAL:
            respuesta['nota_pendiente'] = ('Tu cuestionario se revisará y la '
                                           'calificación se publicará después.')

    return jsonify(respuesta)


def _quiza_enviar_copia(ajustes, cuerpo, correo, definicion, limpias,
                        enlace_edicion):
    """Copia por correo, si el formulario la ofrece y procede.

    Va después de guardar y nunca interrumpe: si el correo falla, la respuesta
    ya está a salvo (ver `encuestas_correo`).
    """
    modo = ajustes['copia_respuesta']
    if modo == ajustes_mod.COPIA_NO or not correo:
        return
    if modo == ajustes_mod.COPIA_SOLICITUD and not cuerpo.get('quiere_copia'):
        return

    lineas = []
    for pregunta in modelo.preguntas(definicion):
        valor = limpias.get(pregunta['id'])
        if isinstance(valor, list):
            valor = ', '.join(str(v) for v in valor)
        lineas.append((modelo.plano(pregunta['titulo']),
                       '' if valor is None else str(valor)))
    correo_mod.enviar_copia(correo, modelo.plano(definicion['titulo']), lineas,
                            enlace_edicion)


# ---------------------------------------------------------------------------
# Modificar una respuesta ya enviada
# ---------------------------------------------------------------------------
@bp_encuestas_publico.route('/api/formulario/<token>/editar/<edicion>',
                            methods=['GET', 'POST'])
def editar_respuesta(token, edicion):
    """Lee o reescribe una respuesta, con la llave que se dio al enviarla.

    La llave se comprueba SIEMPRE junto al formulario: un token de edición no
    debe servir para llegar a las respuestas de otro.
    """
    datos, fallo = _cargar_publico(token)
    if fallo:
        return fallo
    fila, definicion = datos

    fuera = _fuera_de_plazo(fila)     # plazo: vale igual por enlace y por QR
    if fuera:
        return fuera

    if not ajustes_mod.limpiar(fila.get('ajustes'))['permitir_editar']:
        return _fallo('Este formulario ya no permite modificar las respuestas.',
                      403)

    respuesta = ebd.respuesta_por_edicion(definicion['id'], edicion)
    if not respuesta:
        return _fallo('Ese enlace de modificación ya no es válido.', 404)

    if request.method == 'GET':
        return jsonify({'success': True, 'respuestas': respuesta['datos'] or {}})

    if not fila.get('abierta'):
        return _fallo('Este formulario ya no acepta cambios.', 403)

    enviado = (request.get_json(silent=True) or {}).get('respuestas')
    if not isinstance(enviado, dict):
        return _fallo('No se recibió ninguna respuesta.', 400)

    limpias = {}
    for pregunta in modelo.preguntas(definicion):
        valor, problema = _valor_limpio(pregunta, enviado.get(pregunta['id']))
        if problema:
            return _fallo(problema, 400)
        if valor is None and pregunta['obligatoria']:
            return _fallo('Falta responder «%s».' % modelo.plano(pregunta['titulo']), 400)
        if valor is not None:
            limpias[pregunta['id']] = valor

    ebd.actualizar_respuesta(respuesta['id'],
                             json.dumps(limpias, ensure_ascii=False))

    # Si es un cuestionario, la nota se rehace: dejar la anterior sobre unas
    # respuestas nuevas sería peor que no tener nota.
    ajustes = ajustes_mod.limpiar(fila.get('ajustes'))
    if ajustes['cuestionario']:
        ebd.guardar_calificacion(respuesta['id'],
                                 calificar.calificar(definicion, limpias))

    return jsonify({'success': True,
                    'mensaje_final': 'Tu respuesta quedó actualizada.'})


# ---------------------------------------------------------------------------
# Resumen para quien respondió
# ---------------------------------------------------------------------------
@bp_encuestas_publico.route('/api/formulario/<token>/resumen', methods=['GET'])
def resumen_publico(token):
    """Resultados agregados, si el formulario los comparte.

    Solo recuentos y promedios: nunca respuestas individuales, ni quién
    respondió, ni los textos libres. Compartir resultados no puede convertirse
    en compartir lo que escribió cada persona.
    """
    datos, fallo = _cargar_publico(token)
    if fallo:
        return fallo
    fila, definicion = datos

    if not ajustes_mod.limpiar(fila.get('ajustes'))['ver_resumen']:
        return _fallo('Este formulario no comparte los resultados.', 403)

    from api_encuestas import _resumen_por_pregunta
    filas = ebd.listar_respuestas(definicion['id'])
    completo = _resumen_por_pregunta(definicion, filas)

    seguro = {}
    for pregunta in modelo.preguntas(definicion):
        dato = completo.get(pregunta['id'])
        if not dato:
            continue
        if dato['tipo'] == 'conteo':
            # Se quitan los «Otro»: son texto libre escrito por personas.
            seguro[pregunta['id']] = {'tipo': 'conteo',
                                      'conteo': dato.get('conteo') or {}}
        elif dato['tipo'] == 'escala':
            seguro[pregunta['id']] = dato

    return jsonify({'success': True,
                    'titulo': definicion['titulo'],
                    'total': len(filas),
                    'preguntas': [{'id': p['id'], 'titulo': p['titulo']}
                                  for p in modelo.preguntas(definicion)
                                  if p['id'] in seguro],
                    'resumen': seguro})


# ---------------------------------------------------------------------------
# Imágenes del formulario
# ---------------------------------------------------------------------------
@bp_encuestas_publico.route('/api/formulario/<token>/imagen/<imagen_id>',
                            methods=['GET'])
def imagen_publica(token, imagen_id):
    """Sirve una imagen del formulario a quien lo está respondiendo.

    Dos comprobaciones, no una: el token tiene que existir Y la imagen tiene que
    estar REFERENCIADA por ese formulario. Con solo lo primero, quien tuviera un
    enlace válido podría pedir imágenes de otros formularios probando ids; con
    ambas, lo único que se puede leer es lo que ese formulario ya muestra.

    No se comprueba `abierta`: un formulario cerrado sigue enseñando su página
    (con el aviso de que ya no recibe respuestas) y debe verse entero.
    """
    fila = ebd.obtener_por_token(token or '')
    if not fila:
        return _fallo('No encontrada', 404)

    definicion = _leer_definicion(fila['propietario'], fila['ruta'])
    if definicion is None:
        return _fallo('No encontrada', 404)
    definicion = _limpiar_definicion(definicion)

    if str(imagen_id).lower() not in imagenes.ids_en_uso(definicion):
        return _fallo('No encontrada', 404)

    camino = imagenes.buscar(definicion['id'], imagen_id)
    if not camino:
        return _fallo('No encontrada', 404)

    respuesta = send_file(camino, mimetype=imagenes.tipo_de(camino))
    respuesta.headers['X-Content-Type-Options'] = 'nosniff'
    respuesta.headers['Cache-Control'] = 'public, max-age=3600'
    respuesta.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return respuesta


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------
# Dos direcciones para la misma página:
#   /f/k3m9pq2xzt                 <- la que se comparte (42 caracteres en total)
#   /formulario/H_qSLiWOPa94…     <- la de siempre, para no romper lo repartido
@bp_encuestas_publico.route('/f/<token>', methods=['GET'])
@bp_encuestas_publico.route('/formulario/<token>', methods=['GET'])
def pagina_publica(token):
    """Página para responder, o el aviso de por qué no se puede.

    La restricción se resuelve AQUÍ, antes de entregar nada. Si el formulario
    está cerrado, fuera de plazo o pide cuenta, no se sirve la página del
    formulario: se sirve una página de aviso. Así no se llega a ver nada del
    formulario ni por un instante, y el código de estado es el correcto para
    quien lo consulte por otros medios.
    """
    motivo, codigo = _por_que_no(token)
    if motivo:
        return _pagina_de_aviso(motivo, codigo)

    plantilla = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'plantillas', 'encuesta_publica.html')
    respuesta = send_file(plantilla, mimetype='text/html')
    respuesta.headers['Permissions-Policy'] = 'unload=*'
    respuesta.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return respuesta


def _url_iniciar_sesion():
    """Dirección del login con la vuelta a ESTE formulario.

    El destino se toma de la petición en curso —vale igual para
    «/formulario/<token>» que para el enlace corto «/f/<codigo>»— y se
    comprueba que es una ruta interna: `next` acaba en un `redirect`, y un
    `next` que apuntara fuera convertiría esta página en un trampolín para
    llevar a la gente a otro sitio con nuestro dominio en la barra.
    """
    from urllib.parse import quote
    destino = request.path or ''
    if request.query_string:
        destino += '?' + request.query_string.decode('utf-8', 'ignore')
    if not destino.startswith('/') or destino.startswith('//'):
        return LOGIN
    return LOGIN + '?next=' + quote(destino, safe='')


def _pagina_de_aviso(motivo, codigo):
    """Pantalla de «no se puede responder», sin nada del formulario.

    Se arma aquí y no con una plantilla aparte porque son diez líneas y no
    carga ningún JS: cuanto menos traiga esta página, antes aparece el aviso y
    menos hay que mantener.
    """
    from html import escape
    acceso = ''
    if codigo == 401:
        # 27/08/2026 — este enlace apuntaba a «/login», que NO EXISTE: da 404.
        # La ruta de verdad es «/auth/iniciar-sesion». Se veía sobre todo al
        # escanear el QR de un formulario interno con el móvil, donde el
        # navegador no tiene sesión y este es el único camino.
        #
        # Y va en la MISMA pestaña con `?next=`, no en otra: el login honra ese
        # parámetro cuando es una ruta interna, así que al entrar se vuelve solo
        # al formulario. Lo de «abre otra pestaña, vuelve aquí y actualiza» era
        # pedirle tres pasos a alguien que está de pie con el teléfono delante
        # de un cartel.
        acceso = ('<p><a class="fm-btn primario" href="' +
                  escape(_url_iniciar_sesion(), quote=True) +
                  '">Iniciar sesión</a></p>'
                  '<p class="fm-nota">Al entrar vuelves a este formulario.</p>')

    html = (
        '<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
        '<title>No se puede responder</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<link rel="stylesheet" href="/static/css/almacen/encuesta-base.css">'
        '<link rel="stylesheet" href="/static/css/almacen/encuesta-publica.css">'
        '</head><body class="fm"><div class="fm-lienzo">'
        '<div class="fm-tarjeta cabecera"><div class="fm-vacio">'
        '<h3>No se puede responder</h3><p>' + escape(motivo) + '</p>'
        + acceso +
        '</div></div></div></body></html>')

    respuesta = current_app.response_class(html, mimetype='text/html')
    respuesta.status_code = codigo
    respuesta.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return respuesta
