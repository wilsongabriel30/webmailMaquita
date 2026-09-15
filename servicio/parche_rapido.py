# -*- coding: utf-8 -*-
import sys, os, re
D = '/home/sistemas/almacen-maquita/servicio/'
V = '20260911-vivo5'


def parchar(p, cambios):
    s = open(p, encoding='utf-8').read()
    os.system('cp -p "%s" "%s.bak.20260911-rapido"' % (p, p))
    for a, n in cambios:
        if s.count(a) != 1:
            sys.exit('ABORTADO %s ancla %d:\n%s' % (p, s.count(a), a))
        s = s.replace(a, n)
    open(p, 'w', encoding='utf-8').write(s)
    print('OK', p)


# 1. Consolidador: estado desde rutas_estado; guarda la caché de bloques por fuente.
parchar(D + 'consolidados/consolidar_asc.py', [
    ("ESTADO_DIR = '/mnt/almacen/_sincronizacion-asc/estado-consolidados'\n",
     "from rutas_estado import ESTADO_DIR  # noqa: E402  (compartido con la API en vivo)\n"
     "import bloques_cache  # noqa: E402  (caché por fuente para el camino rápido, 11/09/2026)\n"),
    ("    lector = motor.LectorFuentes()\n"
     "    bloques_escritos = []          # (celda, alto, ancho) para señalarlos en vivo\n"
     "    for bloque, fuentes in planes:\n"
     "        matrices = []\n"
     "        for fuente in fuentes:\n"
     "            ruta = resolver_fuente(fuente, indice, equivalencias)\n"
     "            if not ruta:\n"
     "                continue\n"
     "            matrices.append(lector.leer_rango(ruta, fuente.hoja, fuente.rango))\n",
     "    lector = motor.LectorFuentes()\n"
     "    bloques_escritos = []          # (celda, alto, ancho) para señalarlos en vivo\n"
     "    fuentes_leidas = {}            # celda → [{archivo, hoja, rango, filas}] (caché)\n"
     "    for bloque, fuentes in planes:\n"
     "        matrices = []\n"
     "        for fuente in fuentes:\n"
     "            ruta = resolver_fuente(fuente, indice, equivalencias)\n"
     "            if not ruta:\n"
     "                continue\n"
     "            matrices.append(lector.leer_rango(ruta, fuente.hoja, fuente.rango))\n"
     "            fuentes_leidas.setdefault(bloque['destino'], []).append(\n"
     "                {'archivo': ruta, 'hoja': fuente.hoja, 'rango': fuente.rango,\n"
     "                 'filas': matrices[-1]})\n"),
    ("    # Si alguien tiene el consolidado abierto, que le llegue ahora (en vivo).\n"
     "    vivo.registrar_bloques(USUARIO, BASE_VIRTUAL + '/' + definicion['archivo'],\n"
     "                           definicion['hoja'], bloques_escritos)\n",
     "    # Caché por fuente: es lo que relee el camino rápido y lo que lee la API\n"
     "    # en vivo. Se escribe antes de señalar, para que el editor lea lo nuevo.\n"
     "    try:\n"
     "        bloques_cache.guardar(ESTADO_DIR, definicion['archivo'], definicion['hoja'],\n"
     "                              fuentes_leidas)\n"
     "    except Exception as excepcion:\n"
     "        log.warning('  caché de bloques: %s', excepcion)\n"
     "    # Si alguien tiene el consolidado abierto, que le llegue ahora (en vivo).\n"
     "    vivo.registrar_bloques(USUARIO, BASE_VIRTUAL + '/' + definicion['archivo'],\n"
     "                           definicion['hoja'], bloques_escritos)\n"),
])

# 2. vivo.registrar_bloques: parámetro `invalidar` (el rápido no toca el disco).
parchar(D + 'consolidados/vivo.py', [
    ("def registrar_bloques(usuario, ruta_virtual, hoja, bloques):\n",
     "def registrar_bloques(usuario, ruta_virtual, hoja, bloques, invalidar=True):\n"),
    ("        try:\n"
     "            from api_onlyoffice import invalidar_cache\n"
     "            invalidar_cache(int(usuario), ruta_virtual)\n",
     "        if not invalidar:\n"
     "            return          # camino rápido: el disco no cambió, la caché del DS vale\n"
     "        try:\n"
     "            from api_onlyoffice import invalidar_cache\n"
     "            invalidar_cache(int(usuario), ruta_virtual)\n"),
])

# 3. Enganche: primero el camino rápido (cola, sin -n), después la completa.
parchar(D + 'consolidados/enganche.py', [
    ("GUION = os.path.join(DIRECTORIO, 'consolidar_asc.py')\n",
     "GUION = os.path.join(DIRECTORIO, 'consolidar_asc.py')\n"
     "GUION_RAPIDO = os.path.join(DIRECTORIO, 'consolidar_rapido.py')\n"
     "CERROJO_RAPIDO = '/var/lib/almacen-maquita/cerrojos/consolidados-asc-rapido.lock'\n"),
    ("        os.makedirs(os.path.dirname(registro), exist_ok=True)\n"
     "        with open(registro, 'a', encoding='utf-8') as salida:\n"
     "            subprocess.Popen(\n",
     "        os.makedirs(os.path.dirname(registro), exist_ok=True)\n"
     "        # Camino rápido (segundos): relee solo esta matriz y avisa a los\n"
     "        # consolidados abiertos. Cerrojo SIN -n: si llegan dos guardados\n"
     "        # seguidos, el segundo espera; no se pierde ninguno (11/09/2026).\n"
     "        with open(registro, 'a', encoding='utf-8') as salida:\n"
     "            subprocess.Popen(\n"
     "                ['flock', CERROJO_RAPIDO, PYTHON, GUION_RAPIDO, ruta] + extra,\n"
     "                stdout=salida, stderr=subprocess.STDOUT,\n"
     "                stdin=subprocess.DEVNULL, start_new_session=True)\n"
     "        with open(registro, 'a', encoding='utf-8') as salida:\n"
     "            subprocess.Popen(\n"),
])

# 4. API en vivo: los autovínculos leen el bloque de la caché (y al abrir, si la
#    caché es más nueva que el archivo, se rellena).
parchar(D + 'api_vinculos_vivo.py', [
    ("        autovinculo = v['origen_ruta'] == ruta\n"
     "        if (marca > desde) if desde else (not autovinculo):\n"
     "            try:\n"
     "                item['filas'] = _recortar(_leer_rango(\n"
     "                    v['origen_usuario'], v['origen_ruta'],\n"
     "                    v['origen_hoja'], v['origen_rango']))\n"
     "            except Exception as excepcion:\n"
     "                log.warning('vivo %s: no se pudo leer el origen (%s)', v['id'], excepcion)\n",
     "        autovinculo = v['origen_ruta'] == ruta\n"
     "        if autovinculo:\n"
     "            # Consolidado ASC: el bloque sale de la caché por fuente (la\n"
     "            # escribe la consolidación y el camino rápido). Al abrir solo se\n"
     "            # rellena si la caché es más nueva que el archivo del disco.\n"
     "            if (marca > desde) if desde else _cache_mas_nueva(usuario, ruta):\n"
     "                try:\n"
     "                    bloque = _bloque_de_cache(ruta, v['destino_celda'])\n"
     "                    if bloque is None:\n"
     "                        bloque = _leer_rango(v['origen_usuario'], v['origen_ruta'],\n"
     "                                             v['origen_hoja'], v['origen_rango'])\n"
     "                    item['filas'] = _recortar(bloque)\n"
     "                except Exception as excepcion:\n"
     "                    log.warning('vivo %s: no se pudo leer el bloque (%s)', v['id'], excepcion)\n"
     "        elif (marca > desde) if desde else True:\n"
     "            try:\n"
     "                item['filas'] = _recortar(_leer_rango(\n"
     "                    v['origen_usuario'], v['origen_ruta'],\n"
     "                    v['origen_hoja'], v['origen_rango']))\n"
     "            except Exception as excepcion:\n"
     "                log.warning('vivo %s: no se pudo leer el origen (%s)', v['id'], excepcion)\n"),
    ("@bp_vinculos_vivo.route('/vinculos/vivo', methods=['GET'])\n",
     "def _bloque_de_cache(ruta, celda):\n"
     "    from consolidados import bloques_cache, rutas_estado\n"
     "    return bloques_cache.bloque_apilado(rutas_estado.estado_dir_de(ruta), ruta, celda)\n"
     "\n"
     "\n"
     "def _cache_mas_nueva(usuario, ruta):\n"
     "    \"\"\"¿La caché de bloques es más reciente que el archivo del consolidado?\"\"\"\n"
     "    try:\n"
     "        import os\n"
     "        from consolidados import bloques_cache, rutas_estado\n"
     "        return (bloques_cache.mtime(rutas_estado.estado_dir_de(ruta), ruta)\n"
     "                > os.path.getmtime(ruta_fisica(usuario, ruta)))\n"
     "    except Exception:\n"
     "        return False\n"
     "\n"
     "\n"
     "@bp_vinculos_vivo.route('/vinculos/vivo', methods=['GET'])\n"),
])

# 5. Registro del latido y del JS.
parchar(D + 'integracion_faro.py', [
    ("        from api_vinculos_vivo import bp_vinculos_vivo   # respuestas en vivo (11/09/2026)\n",
     "        from api_vinculos_vivo import bp_vinculos_vivo   # respuestas en vivo (11/09/2026)\n"
     "        from api_consolidados_latido import bp_consolidados_latido   # matrices ASC (11/09/2026)\n"),
    ("bp_formulario_libro, bp_vinculos_vivo):\n",
     "bp_formulario_libro, bp_vinculos_vivo, bp_consolidados_latido):\n"),
])
s = open(D + 'arreglos_editor.py', encoding='utf-8').read()
m = re.search(r"VERSION = '([^']+)'\n", s)
parchar(D + 'arreglos_editor.py', [
    (m.group(0), "VERSION = '%s'\n" % V),
    ("    '<script src=\"/static/js/almacen/editor-respuestas-vivo.js?v={v}\"></script>\\n'\n",
     "    '<script src=\"/static/js/almacen/editor-respuestas-vivo.js?v={v}\"></script>\\n'\n"
     "    '<!-- Latido sobre las matrices ASC: guardado forzado para que el consolidado abierto de otro se actualice en segundos (11/09/2026). -->\\n'\n"
     "    '<script src=\"/static/js/almacen/editor-consolidado-latido.js?v={v}\"></script>\\n'\n"),
])
print('TODOS_OK')
