# -*- coding: utf-8 -*-
"""
Formularios del Almacén — la hoja de respuestas se pone al día AL ABRIRLA
========================================================================
La hoja vinculada se rehacía solo cuando pasaba algo: llegaba una respuesta, se
borraba o se editaba el formulario. Si ese aviso se perdía (recarga del
servicio, editor abierto en ese momento, un fallo puntual), el Excel quedaba
desfasado hasta el siguiente cambio, a veces para siempre: «/prueba.forma» tenía
4 respuestas y su Excel 5 filas desde agosto (29/09/2026).

Ahora, al abrir el Excel en el editor, antes de entregar la configuración se
comprueba contra la base y, si no cuadra, se escribe en ese momento: respuestas
nuevas, modificadas y borradas, y columnas de preguntas nuevas o renombradas.

- **Solo si nadie más lo tiene abierto.** Con gente dentro, escribir por fuera
  parte la sala en dos; ahí ya trabaja el complemento «respuestas en vivo».
- **Nunca impide abrir.** Si tarda más de `SEGUNDOS_MAXIMOS` (recálculo de un
  libro con fórmulas) o falla, se abre igual; la escritura sigue en segundo
  plano y, si alguien entra mientras tanto, se aplaza al cierre como siempre.

Autoría: Equipo de Tecnología Maquita — 2026-09-29
"""
import logging
import threading

log = logging.getLogger('almacen.encuestas.hoja_al_abrir')

SEGUNDOS_MAXIMOS = 25


def _formularios_de(usuario, ruta):
    import encuestas_bd as ebd
    return ebd.bd.consultar(
        "SELECT * FROM encuestas WHERE hoja_ruta = %s "
        "AND (propietario = %s OR hoja_ruta LIKE '/unidades/%%')",
        (ruta, int(usuario)))


def poner_al_dia(usuario, ruta):
    """Actualiza la hoja de respuestas (usuario, ruta) si lo es. Nunca lanza."""
    try:
        if not ruta.lower().endswith('.xlsx'):
            return
        import encuestas_hoja as hoja_mod
        from api_encuestas import leer_definicion
        for fila in _formularios_de(usuario, ruta):
            propietario = int(fila['propietario'])
            dentro = hoja_mod._sala_ocupada(propietario, ruta)
            if dentro is None or dentro:
                continue
            with hoja_mod._candado:
                if fila['id'] in hoja_mod._en_marcha:
                    continue            # ya se está escribiendo
                hoja_mod._en_marcha.add(fila['id'])
            try:
                definicion = leer_definicion(propietario, fila['ruta'])
            except Exception:
                definicion = None
            if definicion is None:
                with hoja_mod._candado:
                    hoja_mod._en_marcha.discard(fila['id'])
                continue
            # `_rehacer` libera el turno al terminar.
            hilo = threading.Thread(
                target=hoja_mod._rehacer, args=(dict(fila), definicion, ruta),
                name='hoja-abrir-%s' % fila['id'][:8], daemon=True)
            hilo.start()
            hilo.join(SEGUNDOS_MAXIMOS)
            if hilo.is_alive():
                log.warning('al abrir %s: la actualización sigue en segundo plano', ruta)
    except Exception as excepcion:
        log.warning('al abrir %s: no se pudo poner al día (%s)', ruta, excepcion)
