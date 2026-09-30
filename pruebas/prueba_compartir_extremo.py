# -*- coding: utf-8 -*-
"""Compartir, de extremo a extremo: lo que hace la gente sin ayuda.

Recorre por la API y por las direcciones web lo mismo que hace una persona
desde el diálogo «Compartir»: dar acceso de lector y de editor, cambiar el
permiso, quitarlo, crear el enlace público, y después RENOMBRAR y MOVER la
carpeta compartida, que es cuando los accesos se rompían.

Se ejecuta con:
    cd /home/sistemas/Maquita
    sudo -u sistemas ./venv/bin/python3 /home/sistemas/almacen-maquita/pruebas/prueba_compartir_extremo.py

Cuentas: la dueña es la cuenta de pruebas (54); quien recibe es la cuenta de
pruebas de la pasante (187, su correo se lee de la base); el tercero es el 14. No se
manda ningún correo. Al final se borra todo lo que se creó.
"""
import io
import sys

sys.path.insert(0, '/home/sistemas/Maquita')
sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

DUENA = 54
RECIBE = 187
RECIBE_USUARIO = 'alejandra.calvache'
RECIBE_CORREO = None          # se lee de la base al arrancar (sin dominios en el código)
TERCERO = 14
API = '/api/almacen'
RAIZ = '/__prueba_compartir__'
CARPETA = RAIZ + '/Informes 2026'

fallos = []


def comprobar(condicion, texto, detalle=''):
    if not condicion:
        fallos.append(texto)
    print(('OK   ' if condicion else 'MAL  ') + texto
          + ((' — ' + str(detalle)) if (detalle and not condicion) else ''))
    return bool(condicion)


from app import crear_aplicacion          # noqa: E402
from almacen_bd import consultar as _consultar   # noqa: E402
RECIBE_CORREO = (_consultar('SELECT email FROM usuarios WHERE id = %s', (RECIBE,), nomina=True)[0]['email'] or '').lower()
app = crear_aplicacion()
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

# El correo de invitación no se manda en la prueba.
import correo_compartir                    # noqa: E402
correo_compartir.enviar_invitacion = lambda compartido, usuario: False


def cliente(usuario_id=None):
    c = app.test_client()
    if usuario_id:
        with c.session_transaction() as s:
            s['_user_id'] = str(usuario_id)
            s['_fresh'] = True
            s['usuario_id'] = usuario_id
            # La cabecera de las páginas pinta el nombre de la sesión.
            s['usuario_nombre'] = 'prueba%d' % usuario_id
            s['usuario_rol'] = 'user'
            s['usuario_correo'] = 'prueba%d@prueba.invalid' % usuario_id
    return c


duena, recibe, tercero, anonimo = cliente(DUENA), cliente(RECIBE), cliente(TERCERO), cliente()


def limpiar():
    from almacen_bd import ejecutar
    for ruta in (RAIZ, RAIZ + '_movida'):
        duena.delete(API + '/archivos?ruta=' + ruta)
    ejecutar("DELETE FROM compartidos WHERE propietario_id = %s "
             "AND (ruta = %s OR left(ruta, length(%s) + 1) = %s || '/')",
             (DUENA, RAIZ, RAIZ, RAIZ))


def subir(c, carpeta, nombre, contenido=b'contenido de prueba\n'):
    return c.post(API + '/archivos', data={
        'archivo': (io.BytesIO(contenido), nombre), 'carpeta': carpeta},
        content_type='multipart/form-data')


def compartido(ruta):
    return '/compartido/%d%s' % (DUENA, ruta)


def compartir_con(ruta, permisos):
    return duena.post(API + '/compartir', json={
        'ruta': ruta, 'tipo': 0, 'destinatario': RECIBE_USUARIO, 'permisos': permisos,
        'email': RECIBE_CORREO, 'rol': 'editor' if permisos & 2 else 'lector'})


def en_compartido_conmigo(nombre):
    r = recibe.get(API + '/compartidos?tipo=conmigo')
    datos = r.get_json() or {}
    return any((i.get('nombre') == nombre) for i in (datos.get('compartidos') or []))


try:
    limpiar()
    print('== preparar ==')
    comprobar(duena.post(API + '/carpetas', json={'nombre': RAIZ.strip('/'), 'ruta': '/'}
                         ).status_code in (200, 201), 'la dueña crea la carpeta de trabajo')
    comprobar(duena.post(API + '/carpetas', json={'nombre': 'Informes 2026', 'ruta': RAIZ}
                         ).status_code in (200, 201), 'la dueña crea la carpeta a compartir')
    comprobar(subir(duena, CARPETA, 'informe.txt').status_code in (200, 201),
              'la dueña sube un archivo')
    comprobar(subir(duena, RAIZ, 'privado.txt').status_code in (200, 201),
              'la dueña sube otro archivo FUERA de lo compartido')

    print('\n== antes de compartir ==')
    comprobar(recibe.get(API + '/archivos?ruta=' + compartido(CARPETA)).status_code == 403,
              'quien no tiene acceso no puede listar')

    print('\n== lector ==')
    r = compartir_con(CARPETA, 1)
    comprobar(r.status_code == 201, 'compartir como lector', r.get_data(as_text=True)[:200])
    comp = ((r.get_json() or {}).get('compartido') or {})
    comprobar(en_compartido_conmigo('Informes 2026'), 'aparece en «Compartido conmigo»')
    r = recibe.get(API + '/archivos?ruta=' + compartido(CARPETA))
    comprobar(r.status_code == 200, 'el lector lista la carpeta', r.status_code)
    comprobar(recibe.get(API + '/archivos/descargar?ruta=' + compartido(CARPETA) + '/informe.txt'
                         ).status_code == 200, 'el lector descarga el archivo')
    comprobar(subir(recibe, compartido(CARPETA), 'intruso.txt').status_code == 403,
              'el lector NO puede subir')
    comprobar(recibe.post(API + '/archivos/renombrar', json={
        'ruta': compartido(CARPETA) + '/informe.txt', 'nuevo_nombre': 'x.txt'}).status_code == 403,
        'el lector NO puede renombrar')
    comprobar(recibe.delete(API + '/archivos?ruta=' + compartido(CARPETA) + '/informe.txt'
                            ).status_code == 403, 'el lector NO puede eliminar')
    comprobar(recibe.get(API + '/archivos/descargar?ruta=' + compartido(RAIZ) + '/privado.txt'
                         ).status_code == 403, 'el lector NO alcanza lo que está fuera de lo compartido')
    comprobar(tercero.get(API + '/archivos?ruta=' + compartido(CARPETA)).status_code == 403,
              'un tercero NO puede listar')

    print('\n== compartir dos veces con la misma persona ==')
    r = compartir_con(CARPETA, 15)
    comprobar(r.status_code in (200, 201), 'la segunda vez no da error', r.status_code)
    from almacen_bd import consultar
    filas = consultar("SELECT id, permisos, puede_editar FROM compartidos WHERE propietario_id = %s "
                      "AND ruta = %s AND destinatario = %s", (DUENA, CARPETA, RECIBE_USUARIO))
    comprobar(len(filas) == 1, 'no quedan accesos duplicados de la misma persona', len(filas))
    comprobar(all(f['puede_editar'] for f in filas), 'queda con el permiso más reciente (editor)')

    print('\n== editor ==')
    comprobar(subir(recibe, compartido(CARPETA), 'aporte.txt').status_code in (200, 201),
              'el editor sube un archivo')
    comprobar(recibe.post(API + '/archivos/renombrar', json={
        'ruta': compartido(CARPETA) + '/aporte.txt', 'nuevo_nombre': 'aporte-v2.txt'}
        ).status_code == 200, 'el editor renombra')
    comprobar(subir(recibe, compartido(RAIZ), 'fuera.txt').status_code == 403,
              'el editor NO escribe fuera de lo compartido')

    print('\n== bajar a lector desde «Personas con acceso» ==')
    id_comp = filas[0]['id'] if filas else comp.get('id')
    r = duena.put(API + '/compartidos/%s' % id_comp, json={'permisos': 1})
    comprobar(r.status_code == 200, 'la dueña cambia el permiso a lector', r.status_code)
    comprobar(subir(recibe, compartido(CARPETA), 'otro.txt').status_code == 403,
              'tras bajarlo a lector ya NO puede subir')
    duena.put(API + '/compartidos/%s' % id_comp, json={'permisos': 15})

    print('\n== direcciones web ==')
    from urllib.parse import quote
    r = recibe.get('/archivos-almacen' + quote(CARPETA))
    comprobar(r.status_code == 302 and '/compartido/%d' % DUENA in (r.headers.get('Location') or ''),
              'la dirección interna lleva a quien recibe a «Compartido conmigo»',
              '%s %s' % (r.status_code, r.headers.get('Location')))
    r = tercero.get('/archivos-almacen' + quote(CARPETA))
    comprobar(r.status_code == 403, 'a un tercero le ofrece pedir acceso (403)', r.status_code)
    r = recibe.get('/archivos-almacen' + quote(compartido(CARPETA)))
    comprobar(r.status_code == 200, 'la dirección con dueño abre a quien recibe', r.status_code)
    r = duena.get('/archivos-almacen' + quote(compartido(CARPETA)))
    comprobar(r.status_code in (200, 302), 'la dirección con dueño le abre a la propia dueña',
              r.status_code)
    r = tercero.get('/archivos-almacen' + quote(compartido(CARPETA)))
    comprobar(r.status_code == 403, 'la dirección con dueño, a un tercero: pedir acceso (403)',
              r.status_code)
    r = anonimo.get('/archivos-almacen' + quote(compartido(CARPETA)))
    comprobar(r.status_code == 302 and 'iniciar-sesion' in (r.headers.get('Location') or ''),
              'sin sesión: al inicio de sesión y de vuelta', r.status_code)

    print('\n== dirección de un archivo (la que entrega «Copiar enlace») ==')
    del_archivo = '/archivos-almacen/editar?ruta=' + quote(compartido(CARPETA) + '/informe.txt', safe='')
    r = duena.get(del_archivo)
    comprobar(r.status_code == 302 and '/compartido/' not in (r.headers.get('Location') or ''),
              'a la dueña la lleva a su propio archivo',
              '%s %s' % (r.status_code, r.headers.get('Location')))
    r = recibe.get(del_archivo)
    comprobar(r.status_code == 200, 'a quien recibe le abre el archivo', r.status_code)
    r = tercero.get(del_archivo)
    comprobar(r.status_code == 403, 'a un tercero le ofrece pedir acceso (403)', r.status_code)
    r = tercero.get(API + '/onlyoffice/config?ruta=' + quote(compartido(CARPETA) + '/informe.txt', safe=''))
    comprobar(r.status_code in (400, 403, 404), 'y el editor NO le entrega el contenido', r.status_code)

    print('\n== enlace público ==')
    r = duena.post(API + '/compartir', json={'ruta': CARPETA, 'tipo': 3, 'permisos': 1,
                                             'rol': 'lector'})
    comprobar(r.status_code == 201, 'crear enlace público de lectura', r.status_code)
    enlace = ((r.get_json() or {}).get('compartido') or {})
    token = enlace.get('token')
    r = anonimo.get('/almacen-s/%s' % token)
    comprobar(r.status_code == 200, 'cualquiera abre el enlace sin sesión', r.status_code)
    r = anonimo.get('/almacen-s/%s/archivo/informe.txt' % token)
    # Un .txt se abre en el editor en línea: la respuesta es una redirección.
    comprobar(r.status_code in (200, 302), 'cualquiera abre un archivo del enlace', r.status_code)
    r = anonimo.get('/almacen-s/%s/archivo/../privado.txt' % token)
    comprobar(r.status_code in (400, 403, 404), 'el enlace NO deja salir de la carpeta', r.status_code)
    r = recibe.get('/almacen-s/%s' % token)
    comprobar(r.status_code in (200, 302), 'quien ya tiene acceso también abre el enlace', r.status_code)

    print('\n== enlace con código al correo ==')
    r = duena.post(API + '/compartir', json={'ruta': RAIZ, 'tipo': 3, 'permisos': 1,
                                             'rol': 'lector', 'requiere_otp': True})
    con_codigo = ((r.get_json() or {}).get('compartido') or {})
    comprobar(r.status_code == 201 and con_codigo.get('requiere_otp') is True,
              'crear enlace que pide código al correo', r.status_code)
    sin_codigo = cliente()
    r = sin_codigo.get('/almacen-s/%s/archivo/privado.txt' % con_codigo.get('token'))
    cuerpo = r.get_data(as_text=True)
    comprobar(r.status_code != 302 and 'contenido de prueba' not in cuerpo,
              'sin el código NO se entrega el archivo por su dirección directa', r.status_code)
    r = sin_codigo.get('/almacen-s/%s/descargar' % con_codigo.get('token'))
    comprobar('zip' not in (r.headers.get('Content-Type') or ''),
              'sin el código NO se entrega el ZIP de la carpeta', r.headers.get('Content-Type'))
    duena.delete(API + '/compartidos/%s' % con_codigo.get('id'))

    print('\n== renombrar la carpeta compartida ==')
    r = duena.post(API + '/archivos/renombrar', json={'ruta': CARPETA,
                                                      'nuevo_nombre': 'Informes 2026 final'})
    comprobar(r.status_code == 200, 'la dueña renombra la carpeta compartida', r.status_code)
    NUEVA = RAIZ + '/Informes 2026 final'
    comprobar(recibe.get(API + '/archivos?ruta=' + compartido(NUEVA)).status_code == 200,
              'tras renombrar, quien recibe SIGUE entrando')
    comprobar(en_compartido_conmigo('Informes 2026 final'),
              'tras renombrar, sigue en «Compartido conmigo» con el nombre nuevo')
    comprobar(anonimo.get('/almacen-s/%s' % token).status_code == 200,
              'tras renombrar, el enlace público SIGUE abriendo')

    print('\n== mover la carpeta compartida ==')
    duena.post(API + '/carpetas', json={'nombre': 'Archivo', 'ruta': RAIZ})
    r = duena.post(API + '/archivos/mover', json={'origen': NUEVA,
                                                  'destino': RAIZ + '/Archivo/Informes 2026 final'})
    comprobar(r.status_code == 200, 'la dueña mueve la carpeta compartida', r.status_code)
    MOVIDA = RAIZ + '/Archivo/Informes 2026 final'
    comprobar(recibe.get(API + '/archivos?ruta=' + compartido(MOVIDA)).status_code == 200,
              'tras mover, quien recibe SIGUE entrando')
    comprobar(anonimo.get('/almacen-s/%s' % token).status_code == 200,
              'tras mover, el enlace público SIGUE abriendo')

    print('\n== quitar accesos ==')
    r = duena.delete(API + '/compartidos/%s' % enlace.get('id'))
    comprobar(r.status_code == 200, 'pasar a «Restringido» borra el enlace', r.status_code)
    comprobar(anonimo.get('/almacen-s/%s' % token).status_code == 404,
              'el enlace borrado deja de abrir')
    r = duena.delete(API + '/compartidos/%s' % id_comp)
    comprobar(r.status_code == 200, 'la dueña quita el acceso de la persona', r.status_code)
    comprobar(recibe.get(API + '/archivos?ruta=' + compartido(MOVIDA)).status_code == 403,
              'sin acceso, quien recibía ya NO entra')

    print('\n== un archivo suelto ==')
    r = compartir_con(RAIZ + '/privado.txt', 1)
    comprobar(r.status_code == 201, 'compartir un archivo suelto', r.status_code)
    comprobar(recibe.get(API + '/archivos/descargar?ruta=' + compartido(RAIZ) + '/privado.txt'
                         ).status_code == 200, 'quien recibe descarga ese archivo')
    comprobar(recibe.get(API + '/archivos?ruta=' + compartido(RAIZ)).status_code == 403,
              'pero NO ve la carpeta que lo contiene')
finally:
    try:
        limpiar()
    except Exception as excepcion:
        print('AVISO: no se pudo limpiar: %s' % excepcion)

print('\n%s — %d fallos' % ('TODO BIEN' if not fallos else 'HAY FALLOS', len(fallos)))
for f in fallos:
    print('  · ' + f)
sys.exit(1 if fallos else 0)
