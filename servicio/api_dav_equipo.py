# -*- coding: utf-8 -*-
"""
Endpoints del EQUIPO para la app de Windows (autenticados por token DAV).
=========================================================================
Dos cosas que la app necesita hacer sin abrir la web, con el mismo token con
el que monta el disco:

  POST /api/almacen/dav/revocar       «Desconectar» de verdad (P-03): invalida
                                      el token en el servidor, no solo en el PC.
  POST /api/almacen/dav/log-cliente   Enviar un registro de error (P-06), para
                                      que Soporte lo vea sin pedirle archivos
                                      a la persona.

La autenticación es la común de `dav_auth` (Basic: usuario = ID FARO,
contraseña = token del equipo). Sin sesión ni CSRF: la credencial es el token,
por eso van exentos del candado de /api/almacen (ver integracion_faro.py).

Doc: PENDIENTES-BACKEND.md (P-03, P-06)
Autoría: Equipo de Tecnología Maquita — 2026-08-04
"""
import datetime
import json
import logging
import os
import re

from flask import Blueprint, jsonify, request

from almacen_bd import ejecutar
from dav_auth import token_id_por_token, usuario_por_token

log = logging.getLogger('almacen.dav_equipo')

bp_dav_equipo = Blueprint('almacen_dav_equipo', __name__)

# Dónde quedan los registros que mandan los clientes: dentro de la UNIDAD
# COMPARTIDA «Soporte — Registros y auditoría» (id 10), para que Tecnología los
# vea desde la web y desde el disco montado, sin tener que entrar al servidor.
# Sigue estando fuera del espacio personal de quien reporta: no le ocupa cuota
# ni le aparece en su unidad. El acceso lo controlan los miembros de la unidad.
CARPETA_REGISTROS = os.getenv(
    'ALMACEN_REGISTROS_CLIENTES',
    '/mnt/almacen/_unidades/10/archivos/registros-clientes')
MAXIMO_POR_ENVIO = 256 * 1024        # 256 KB por petición
MAXIMO_POR_ARCHIVO = 5 * 1024 * 1024  # 5 MB por equipo y día


def _nombre_seguro(texto, por_defecto='equipo'):
    """Nombre de archivo sin sorpresas: sin rutas, sin acentos raros, corto."""
    limpio = re.sub(r'[^A-Za-z0-9._-]+', '-', (texto or '')).strip('-')
    return limpio[:60] or por_defecto


@bp_dav_equipo.route('/dav/revocar', methods=['POST'])
def revocar_este_equipo():
    """POST /api/almacen/dav/revocar — «Desconectar» (P-03).

    Auth: Basic (usuario = ID FARO, contraseña = token del equipo).
    Revoca EXACTAMENTE el token con el que se llama: los demás equipos de la
    persona siguen conectados. Sin cuerpo. Respuesta: {success, mensaje}.

    Es idempotente en la práctica: si el token ya estaba revocado, la
    autenticación falla y se responde 401 — para la app, «ya está desconectado».
    """
    usuario_id, token_id = token_id_por_token(request.authorization)
    if usuario_id is None:
        return jsonify({'success': False,
                        'error': 'Este equipo ya no está conectado.'}), 401

    fila = ejecutar("""
        UPDATE dav_tokens SET revocado = now()
         WHERE id = %s AND usuario_id = %s AND revocado IS NULL
        RETURNING nombre
    """, (token_id, usuario_id))
    if not fila:
        return jsonify({'success': True,
                        'mensaje': 'Este equipo ya estaba desconectado.'})

    log.info('Equipo DAV %s (%s) desconectado por su propio token, usuario %s',
             token_id, fila['nombre'], usuario_id)
    return jsonify({'success': True,
                    'mensaje': 'Se desconectó «%s» del Drive.' % fila['nombre']})


@bp_dav_equipo.route('/dav/log-cliente', methods=['POST'])
def registro_cliente():
    """POST /api/almacen/dav/log-cliente — registro de error de la app (P-06).

    Auth: Basic (igual que el resto). Cuerpo JSON con lo que la app ya recoge:
      { "equipo": "...", "componente": "...", "descripcion": "...",
        "archivo": "...", "conexion": "...", "usuario_windows": "...",
        "acciones_previas": "...", "version": "..." }
    También se acepta texto plano, que se guarda tal cual.

    Se escribe una línea JSON por envío en
    `<CARPETA_REGISTROS>/<usuario>-<equipo>-<fecha>.log`, con la hora y la IP
    puestas por el SERVIDOR (las del cliente no son de fiar para auditar).
    """
    usuario_id = usuario_por_token(request.authorization)
    if usuario_id is None:
        return jsonify({'success': False,
                        'error': 'No se pudo autenticar el equipo.'}), 401

    # El JSON primero: leer el cuerpo crudo antes lo consumiría y todo entraría
    # como texto plano, perdiendo los campos (y con ellos el nombre del equipo).
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        crudo = request.get_data(cache=True)[:MAXIMO_POR_ENVIO]
        datos = {'texto': crudo.decode('utf-8', 'replace')}

    equipo = _nombre_seguro(str(datos.get('equipo') or ''), 'equipo')
    ahora = datetime.datetime.now()
    registro = {
        'recibido': ahora.isoformat(timespec='seconds'),
        'usuario_faro': usuario_id,
        'ip': request.headers.get('X-Forwarded-For', request.remote_addr or ''),
        'datos': datos,
    }

    try:
        os.makedirs(CARPETA_REGISTROS, exist_ok=True)
        destino = os.path.join(
            CARPETA_REGISTROS,
            '%s-%s-%s.log' % (usuario_id, equipo, ahora.strftime('%Y%m%d')))
        # Tope por equipo y día: un cliente en bucle no debe llenar el disco.
        if (os.path.exists(destino)
                and os.path.getsize(destino) > MAXIMO_POR_ARCHIVO):
            log.warning('Registros de %s/%s superan el tope diario; se descarta',
                        usuario_id, equipo)
            return jsonify({'success': True,
                            'mensaje': 'Registro recibido (límite diario '
                                       'alcanzado, no se guardó).'})
        with open(destino, 'a', encoding='utf-8') as archivo:
            archivo.write(json.dumps(registro, ensure_ascii=False) + '\n')
    except Exception as excepcion:
        # Que un fallo al guardar NO rompa la app de la persona: ya tiene un
        # problema (por eso manda el registro); no se le añade otro error.
        log.warning('No se pudo guardar el registro de %s: %s',
                    usuario_id, excepcion)
        return jsonify({'success': True,
                        'mensaje': 'Registro recibido.'})

    log.info('Registro de cliente guardado: usuario=%s equipo=%s',
             usuario_id, equipo)
    return jsonify({'success': True, 'mensaje': 'Registro recibido.'})


@bp_dav_equipo.route('/dav/uso', methods=['GET'])
def uso_del_espacio():
    """GET /api/almacen/dav/uso — cuánto lleva usado la persona (P-21).

    Auth: Basic (usuario = ID FARO, contraseña = token del equipo).
    OK: { "uso_bytes": 15099494400, "cuota_bytes": 21474836480 }

    Lo consume el menú de la bandeja de la app para mostrar «Espacio: 14,1 GB
    de 20 GB (70 %)» y avisar cuando se pasa del 90 %. Se pide al conectar,
    tras cada sincronización y cada media hora, así que tiene que ser BARATO:
    sale del índice del almacén (milisegundos), no de recorrer el disco.

    A diferencia de `uso_bytes` del instalador —que cuenta solo lo que la app
    va a DESCARGAR—, aquí se informa el uso REAL de la cuota, papelera
    incluida: es lo que la persona tiene que liberar si está llena, y si no se
    contara, vería «tengo sitio» mientras el sistema le dice que no.
    """
    usuario_id = usuario_por_token(request.authorization)
    if usuario_id is None:
        return jsonify({'success': False,
                        'error': 'No se pudo autenticar el equipo.'}), 401
    try:
        import nucleo_archivos as nucleo
        from almacen_bd import consultar

        # NO se fuerza el recálculo. `nucleo.cuota()` recalcula cuando el dato
        # cacheado pasa de 10 minutos, y ese recálculo tardó 7,5 s con el Drive
        # más grande. Como la app pregunta al conectar, tras cada sincronización
        # y cada media hora, eso serían esperas constantes para pintar un
        # renglón de menú: para eso, un dato de hace un rato vale igual.
        # Se lee lo que haya cacheado y solo se calcula si NO hay nada.
        fila = consultar('SELECT usado_bytes FROM cuotas_uso WHERE usuario_id = %s',
                         (usuario_id,))
        if fila:
            usado = int(fila[0]['usado_bytes'])
            # El tope: el asignado a esta persona o, si no tiene, el general.
            # Se lee directo para no pasar por cuota(), que recalcularía.
            from config_almacen import cuota_defecto_bytes
            f_lim = consultar('SELECT limite_bytes FROM cuotas WHERE usuario_id = %s',
                              (usuario_id,))
            total = int(f_lim[0]['limite_bytes']) if f_lim else int(cuota_defecto_bytes())
        else:
            datos = nucleo.cuota(usuario_id)          # primera vez: sí se calcula
            usado, total = int(datos['usado']), int(datos['total'])

        return jsonify({
            'uso_bytes': usado,
            'cuota_bytes': total,
            # Extras por comodidad del cliente; si no los usa, los ignora.
            'libre_bytes': max(0, total - usado),
            'porcentaje': round(usado * 100.0 / total, 1) if total else 0.0,
        })
    except Exception as excepcion:
        log.warning('No se pudo calcular el uso de %s: %s', usuario_id, excepcion)
        return jsonify({'success': False,
                        'error': 'No se pudo calcular el espacio ahora mismo.'}), 503
