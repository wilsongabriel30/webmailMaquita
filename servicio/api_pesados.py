# -*- coding: utf-8 -*-
"""
Vista «Almacenamiento»: carpetas más pesadas de la unidad del usuario (T-23).
GET /almacenamiento/carpetas?limit=  → {success, carpetas:[{ruta, nombre, bytes, humano, archivos}]}
Se calcula desde el índice de nombres (ruta + tamaño por archivo) acumulando en cada carpeta ancestro: milisegundos,
sin tocar el NFS.
"""
from flask import jsonify, request


def _humano(n):
    n = float(n or 0)
    for u in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or u == 'TB':
            return f'{n:.1f} {u}'
        n /= 1024


def carpetas_pesadas(usuario_id, limite=30):
    from almacen_bd import consultar
    filas = consultar("SELECT ruta, tamano FROM indice_nombres WHERE usuario_id = %s AND NOT es_carpeta "
                      "AND ruta NOT LIKE '%%/.%%'", (usuario_id,))
    acum, cuenta = {}, {}
    for f in filas:
        partes = str(f['ruta']).strip('/').split('/')[:-1]
        t = int(f['tamano'] or 0)
        ruta = ''
        for p in partes:
            ruta += '/' + p
            acum[ruta] = acum.get(ruta, 0) + t
            cuenta[ruta] = cuenta.get(ruta, 0) + 1
    orden = sorted(acum.items(), key=lambda kv: kv[1], reverse=True)[:limite]
    return [{'ruta': r, 'nombre': r.rsplit('/', 1)[-1], 'bytes': b, 'humano': _humano(b), 'archivos': cuenta[r],
             'nivel': r.count('/')} for r, b in orden]


def registrar_rutas(bp):
    @bp.route('/almacenamiento/carpetas', methods=['GET'])
    def almacenamiento_carpetas():
        from api_archivos import usuario_actual
        try:
            limite = max(1, min(int(request.args.get('limit', 30)), 200))
        except (TypeError, ValueError):
            limite = 30
        return jsonify({'success': True, 'carpetas': carpetas_pesadas(usuario_actual(), limite)})
