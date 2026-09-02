# -*- coding: utf-8 -*-
"""
«Archivos del correo» en el Drive (T-22): datos del correo dueño de un adjunto y resumen de la carpeta.
Se cuelga del blueprint de extras (misma autenticación y prefijo /api/almacen).
- GET /correo-de?ruta=          → {success, correo:{buzon, carpeta, uid, asunto, remitente, fecha, url}} (404 si no es de correo)
- GET /correo-de/resumen        → {success, archivos, bytes, humano} de /Archivos del correo del usuario
"""
from flask import jsonify, request

import protecciones_sistema as prot


def _humano(n):
    n = float(n or 0)
    for u in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or u == 'TB':
            return f'{n:.1f} {u}'
        n /= 1024


def registrar_rutas(bp):
    @bp.route('/correo-de', methods=['GET'])
    def correo_de_adjunto():
        from api_archivos import usuario_actual
        ruta = request.args.get('ruta') or ''
        if not prot.es_de_correo(ruta):
            return jsonify({'success': False, 'error': 'No es un archivo del correo'}), 404
        datos = prot.datos_correo(usuario_actual(), ruta)
        if not datos:
            return jsonify({'success': False, 'error': 'Sin correo asociado'}), 404
        return jsonify({'success': True, 'correo': datos})

    @bp.route('/correo-de/resumen', methods=['GET'])
    def resumen_archivos_correo():
        from api_archivos import usuario_actual
        from almacen_bd import consultar
        filas = consultar("SELECT COUNT(*) AS n, COALESCE(SUM(tamano), 0) AS b FROM indice_nombres "
                          "WHERE usuario_id = %s AND NOT es_carpeta AND ruta LIKE %s",
                          (usuario_actual(), prot.CARPETA_CORREO + '/%'))
        n = int(filas[0]['n']) if filas else 0
        b = int(filas[0]['b']) if filas else 0
        return jsonify({'success': True, 'archivos': n, 'bytes': b, 'humano': _humano(b)})
