# -*- coding: utf-8 -*-
"""
El proceso que hace el trabajo con los PDF.
============================================
Arranca una vez, se queda esperando encargos por su tubo de entrada y contesta
por el de salida. No sabe nada de web, ni de eventlet, ni de la base de datos:
solo PyMuPDF. Por eso, pase lo que pase aquí dentro, el servidor que atiende a
la gente no se entera.

Protocolo, en los dos sentidos: ocho bytes con el tamaño y detrás el paquete.
El encargo es `(tarea, argumentos, nombrados)` y la respuesta,
`('bien', resultado)` o `('mal', (tipo, mensaje))`.

Se lanza solo, desde `pool_pdf`. No es para ejecutarlo a mano.

Autoría: Equipo de Tecnología Maquita — 2026-07-29
"""

import os
import pickle
import struct
import sys

# Este archivo se ejecuta suelto (ver pool_pdf), así que su propia carpeta tiene que
# estar en el camino para poder pedir `carga_ligera`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _tareas():
    """Lo que este proceso sabe hacer, por nombre.

    Un registro explícito y no «la función que venga en el paquete»: así lo que
    llega por el tubo no puede pedir que se ejecute cualquier cosa.
    """
    # Por la vía corta: pedirlos por el paquete arrastraba FARO entero y el primer
    # encargo tardaba 3,8 s en vez de los 50 ms que cuesta el trabajo de verdad.
    import carga_ligera
    base = 'modulos.pdf_editor.infraestructura.externos.'
    parrafos_pdf = carga_ligera.importar(base + 'parrafos_pdf')
    tablas_medidas = carga_ligera.importar(base + 'tablas_medidas')
    tablas_mover = carga_ligera.importar(base + 'tablas_mover')
    tablas_pdf = carga_ligera.importar(base + 'tablas_pdf')
    return {
        'detectar': tablas_pdf.detectar,
        'cambiar_columna': tablas_pdf.cambiar_columna,
        'cambiar_fila': tablas_pdf.cambiar_fila,
        'escribir_celda': tablas_pdf.escribir_celda,
        'mover_columna': tablas_pdf.mover_columna,
        'mover_fila': tablas_pdf.mover_fila,
        'redimensionar': tablas_medidas.redimensionar,
        'mover_tabla': tablas_mover.mover_tabla,
        'parrafo_en': parrafos_pdf.parrafo_en,
        'reemplazar_parrafo': parrafos_pdf.reemplazar,
        'ping': lambda: 'listo',
        # La misma operación, pero sobre un documento que ya está en el
        # servidor: se le pasa la ruta y devuelve solo lo que cambió.
        'en_sesion': _en_sesion,
    }


def _en_sesion(nombre_operacion, ruta, *argumentos, **nombrados):
    """Hace la operación sobre el documento que ya está en el servidor.

    Devuelve `(trozo, desde, aviso)`. Si `desde` es mayor que cero, `trozo` es
    solo **lo que se añadió** al final del documento: el navegador lo pega a su
    copia y ya está. Si es cero, el documento hubo que rehacerlo entero (toca de
    vez en cuando, al compactar) y `trozo` es el PDF completo.
    """
    import carga_ligera
    guardado_pdf = carga_ligera.importar(
        'modulos.pdf_editor.infraestructura.externos.guardado_pdf')
    tareas = _tareas()
    funcion = tareas.get(nombre_operacion)
    if funcion is None:
        raise ValueError('Tarea desconocida: %s' % nombre_operacion)

    en_ruta = guardado_pdf.PdfEnRuta(ruta)
    salida = funcion(en_ruta, *argumentos, **nombrados)

    # Las operaciones devuelven (pdf, aviso); `detectar` y `parrafo_en` no pasan
    # por aquí porque no cambian nada.
    completo, aviso = salida
    por_anadido, desde = guardado_pdf.ultimo_guardado()
    if por_anadido and 0 < desde < len(completo):
        return completo[desde:], desde, aviso
    return completo, 0, aviso


def _leer(descriptor, cuantos):
    partes, faltan = [], cuantos
    while faltan > 0:
        trozo = os.read(descriptor, min(faltan, 1 << 20))
        if not trozo:
            raise EOFError
        partes.append(trozo)
        faltan -= len(trozo)
    return b''.join(partes)


def _escribir(descriptor, datos):
    puestos = 0
    while puestos < len(datos):
        puestos += os.write(descriptor, datos[puestos:puestos + (1 << 20)])


def main():
    # Ni una palabra por la salida estándar: es el tubo de respuesta, y
    # cualquier cosa impresa ahí rompería el paquete.
    entrada, salida = sys.stdin.fileno(), sys.stdout.fileno()
    sys.stdout = sys.stderr

    tareas = _tareas()

    while True:
        try:
            (largo,) = struct.unpack('!Q', _leer(entrada, 8))
            tarea, argumentos, nombrados = pickle.loads(_leer(entrada, largo))
        except (EOFError, OSError, struct.error, ValueError):
            return 0                       # el servidor cerró: se acabó el turno

        try:
            funcion = tareas.get(tarea)
            if funcion is None:
                raise ValueError('Tarea desconocida: %s' % tarea)
            respuesta = ('bien', funcion(*argumentos, **nombrados))
        except BaseException as excepcion:                       # noqa: BLE001
            respuesta = ('mal', (type(excepcion).__name__, str(excepcion)))

        try:
            paquete = pickle.dumps(respuesta, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as excepcion:
            paquete = pickle.dumps(
                ('mal', ('RuntimeError',
                         'no se pudo devolver el resultado: %s' % excepcion)))
        try:
            _escribir(salida, struct.pack('!Q', len(paquete)))
            _escribir(salida, paquete)
        except OSError:
            return 0


if __name__ == '__main__':
    sys.exit(main())
