# -*- coding: utf-8 -*-
"""Puente entre el panel «¿Cómo hago…?» del editor de hojas e IA Maquita (05/10/2026).

El panel resuelve casi todo sin modelo (recetas, explicación de fórmulas,
errores). Esto es SOLO para la pregunta libre, y está hecho para gastar el
modelo lo menos posible:

  · Memoria: una pregunta igual a otra ya respondida (mismas palabras, misma
    fórmula, mismos títulos de columna) se contesta desde la tabla, sin modelo.
  · Encargo y espera: el modelo tarda (hasta minutos). El panel deja la
    pregunta, recibe un número y consulta cada pocos segundos; nadie espera con
    la conexión abierta.
  · Topes: una pregunta en curso por persona y un máximo diario.
  · Registro: cada pregunta queda guardada. Las que se repiten son las recetas
    que le faltan al panel (se escriben y dejan de llegar al modelo).

A IA Maquita se le habla de servidor a servidor; la clave se lee del entorno
(`IA_MAQUITA_API_KEY`), nunca va al navegador. Sin clave, la pregunta libre se
declara no disponible y el resto del panel sigue igual.
"""
import hashlib
import logging
import os
import re
import threading
import unicodedata

import requests
from flask import Blueprint, jsonify, request

import almacen_bd as bd
from api_archivos import error, usuario_actual

log = logging.getLogger('almacen.asistente_hojas')
bp_asistente_hojas = Blueprint('asistente_hojas', __name__)

ENV_RAICES = '/home/sistemas/Maquita/.env'
MAXIMO_DIARIO = 30                 # preguntas al modelo por persona y día
ESPERA_MODELO = 240                # segundos
CADUCA_PENDIENTE = '6 minutes'     # un encargo más viejo que esto se da por perdido
LARGO_PREGUNTA = 600

_esquema_listo = False


def _entorno(clave, defecto=''):
    valor = os.environ.get(clave)
    if valor:
        return valor
    try:
        with open(ENV_RAICES, encoding='utf-8') as fichero:
            for linea in fichero:
                if linea.startswith(clave + '='):
                    return linea.split('=', 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return defecto


def _esquema():
    global _esquema_listo
    if _esquema_listo:
        return
    bd.ejecutar("""
        CREATE TABLE IF NOT EXISTS asistente_hojas_preguntas (
            id BIGSERIAL PRIMARY KEY,
            clave TEXT NOT NULL,
            usuario_id INTEGER NOT NULL,
            pregunta TEXT NOT NULL,
            formula TEXT NOT NULL DEFAULT '',
            encabezados TEXT NOT NULL DEFAULT '',
            estado TEXT NOT NULL DEFAULT 'pendiente',
            respuesta TEXT,
            de_memoria BOOLEAN NOT NULL DEFAULT FALSE,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            respondido_en TIMESTAMPTZ
        )""")
    bd.ejecutar('CREATE INDEX IF NOT EXISTS asistente_hojas_clave ON asistente_hojas_preguntas (clave, estado)')
    bd.ejecutar('CREATE INDEX IF NOT EXISTS asistente_hojas_usuario ON asistente_hojas_preguntas (usuario_id, creado_en)')
    _esquema_listo = True


def _normal(texto):
    texto = unicodedata.normalize('NFD', str(texto or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9=<>$]+', ' ', texto).strip()


def _clave(pregunta, formula, encabezados):
    base = '|'.join((_normal(pregunta), re.sub(r'\s+', '', formula or '').upper(), _normal(' '.join(encabezados))))
    return hashlib.sha256(base.encode()).hexdigest()


def _mensaje(pregunta, formula, encabezados):
    partes = [
        'Eres el ayudante de hojas de cálculo de Maquita. La persona trabaja en un editor compatible con Excel, '
        'en español. Responde en español, en pocas líneas y sin rodeos.',
        'Si la respuesta es una fórmula, da UNA sola, entre acentos graves, escrita con los nombres de función en '
        'INGLÉS y separando los argumentos con coma (por ejemplo `=SUMIF(A2:A100,"Viajes",C2:C100)`); el editor la '
        'traduce solo. Después explica en una frase cómo se lee. No inventes funciones.',
    ]
    if encabezados:
        partes.append('Los títulos de las columnas de su hoja (fila 1) son: ' + '; '.join(encabezados[:26]) + '.')
    if formula:
        partes.append('La fórmula de la celda donde está es: `' + formula[:800] + '`.')
    partes.append('Pregunta: ' + pregunta)
    return '\n'.join(partes)


def _responder(id_pregunta, mensaje):
    """Corre en un hilo: le pregunta al modelo y deja la respuesta en la tabla."""
    try:
        respuesta = requests.post(
            _entorno('IA_MAQUITA_URL', 'http://192.0.2.10:6060').rstrip('/') + '/chat',
            json={'mensaje': mensaje}, timeout=ESPERA_MODELO,
            headers={'X-API-Key': _entorno('IA_MAQUITA_API_KEY')})
        datos = respuesta.json() if respuesta.headers.get('content-type', '').startswith('application/json') else {}
        texto = (datos.get('respuesta') or '').strip()
        if respuesta.status_code == 200 and texto:
            bd.ejecutar("UPDATE asistente_hojas_preguntas SET estado = 'lista', respuesta = %s, respondido_en = NOW() "
                        "WHERE id = %s", (texto, id_pregunta))
            return
        motivo = 'IA Maquita respondió %s' % respuesta.status_code
    except Exception as excepcion:
        motivo = str(excepcion)[:200]
    log.warning('asistente de hojas: sin respuesta para %s (%s)', id_pregunta, motivo)
    try:
        bd.ejecutar("UPDATE asistente_hojas_preguntas SET estado = 'fallo', respuesta = %s, respondido_en = NOW() "
                    "WHERE id = %s", (motivo, id_pregunta))
    except Exception:
        pass


@bp_asistente_hojas.route('/asistente-hojas/preguntar', methods=['POST'])
def preguntar():
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    pregunta = ' '.join(str(datos.get('pregunta') or '').split())[:LARGO_PREGUNTA]
    formula = str(datos.get('formula') or '')[:800]
    encabezados = [str(e)[:60] for e in (datos.get('encabezados') or []) if isinstance(e, str)][:26]
    if len(pregunta) < 4:
        return error('Escribe lo que necesitas.', 400)
    if not _entorno('IA_MAQUITA_API_KEY'):
        return error('La pregunta libre no está configurada.', 503)
    _esquema()

    clave = _clave(pregunta, formula, encabezados)
    sabida = bd.consultar("SELECT respuesta FROM asistente_hojas_preguntas WHERE clave = %s AND estado = 'lista' "
                          "ORDER BY id DESC LIMIT 1", (clave,))
    if sabida:
        bd.ejecutar("INSERT INTO asistente_hojas_preguntas (clave, usuario_id, pregunta, formula, encabezados, estado, "
                    "respuesta, de_memoria, respondido_en) VALUES (%s, %s, %s, %s, %s, 'lista', %s, TRUE, NOW())",
                    (clave, int(usuario), pregunta, formula, '; '.join(encabezados), sabida[0]['respuesta']))
        return jsonify({'respuesta': sabida[0]['respuesta'], 'de_memoria': True})

    bd.ejecutar("UPDATE asistente_hojas_preguntas SET estado = 'fallo', respuesta = 'se perdió el encargo' "
                "WHERE estado = 'pendiente' AND creado_en < NOW() - interval %s", (CADUCA_PENDIENTE,))
    en_curso = bd.consultar("SELECT id, clave FROM asistente_hojas_preguntas WHERE usuario_id = %s AND estado = 'pendiente' "
                            "ORDER BY id DESC LIMIT 1", (int(usuario),))
    if en_curso:
        if en_curso[0]['clave'] == clave:
            return jsonify({'id': en_curso[0]['id']})          # la misma pregunta, aún pensando
        return error('Ya tienes una pregunta en curso; espera a que termine.', 429)
    hoy = bd.consultar("SELECT count(*) AS n FROM asistente_hojas_preguntas WHERE usuario_id = %s AND NOT de_memoria "
                       "AND creado_en > NOW() - interval '1 day'", (int(usuario),))[0]['n']
    if hoy >= MAXIMO_DIARIO:
        return error('Llegaste al máximo de preguntas de hoy. Las recetas y «Esta celda» siguen disponibles.', 429)

    fila = bd.ejecutar("INSERT INTO asistente_hojas_preguntas (clave, usuario_id, pregunta, formula, encabezados) "
                       "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                       (clave, int(usuario), pregunta, formula, '; '.join(encabezados)))
    threading.Thread(target=_responder, args=(fila['id'], _mensaje(pregunta, formula, encabezados)),
                     daemon=True, name='asistente-hojas-%s' % fila['id']).start()
    return jsonify({'id': fila['id']})


@bp_asistente_hojas.route('/asistente-hojas/respuesta/<int:id_pregunta>', methods=['GET'])
def respuesta(id_pregunta):
    usuario = usuario_actual()
    _esquema()
    filas = bd.consultar("SELECT estado, respuesta, creado_en < NOW() - interval %s AS caducada "
                         "FROM asistente_hojas_preguntas WHERE id = %s AND usuario_id = %s",
                         (CADUCA_PENDIENTE, id_pregunta, int(usuario)))
    if not filas:
        return error('No existe esa pregunta.', 404)
    fila = filas[0]
    if fila['estado'] == 'lista':
        return jsonify({'estado': 'lista', 'respuesta': fila['respuesta']})
    if fila['estado'] == 'fallo' or fila['caducada']:
        return jsonify({'estado': 'fallo', 'mensaje': 'IA Maquita no pudo responder ahora. Inténtalo más tarde.'})
    return jsonify({'estado': 'pendiente'})
