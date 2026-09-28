# -*- coding: utf-8 -*-
"""
¿Quién puede MOVER dentro de una unidad compartida?
===================================================
Regla del 31/08/2026, en una frase: **cada quien mueve dentro de lo suyo.**

    · Administrador de la unidad (`manager`) → mueve en toda la unidad.
    · Con un rol concedido sobre una CARPETA (editor o manager de esa carpeta)
      → mueve dentro de esa carpeta, y solo ahí.
    · `editor` de la unidad entera, sin carpeta asignada → NO mueve. Puede
      crear, subir y editar, pero no reorganizar la unidad de los demás.
    · `viewer` → no mueve (ni escribe).
    · Master del Drive → mueve en cualquier sitio: es quien recupera lo que se
      pierde, y para eso tiene que poder colocarlo donde iba.

Ejemplo real de la unidad «Procesos Formativos»: quien tiene editor sobre
«1 Esmeraldas…» mueve, edita, copia y borra dentro de Esmeraldas; no puede
tocar «3 Guayas-El Oro…» ni la raíz de la unidad.

Como se pregunta por el ORIGEN y por el DESTINO, sacar algo de Esmeraldas para
llevarlo a Guayas falla por el destino, que es lo que se busca.

### Por qué mover se trata aparte de editar

Editar un archivo es un cambio *dentro* de algo, y queda en el historial de
versiones. Mover es un cambio en la **estructura que todos comparten**, y a
quien no encuentra su archivo el historial no le sirve de nada.

Autoría: Equipo de Tecnología Maquita — 2026-08-31
"""
import logging

from seguridad_rutas import unidad_de_ruta

log = logging.getLogger('almacen.permisos_mover')

# Roles que, sobre una carpeta concedida, permiten reorganizarla.
ROLES_QUE_MUEVEN = ('editor', 'manager')
# Rol de unidad que permite mover en TODA la unidad.
ROL_DE_UNIDAD_QUE_MUEVE = 'manager'


def puede_mover(usuario_id: int, ruta: str) -> bool:
    """¿Puede esta persona mover algo en esta ruta?

    Fuera de las unidades compartidas devuelve True: ahí manda el permiso de
    escritura de siempre, que ya se comprueba aparte. Ante cualquier duda
    responde que NO: es preferible que alguien pida ayuda a que la estructura
    de una unidad se reorganice sola.
    """
    try:
        unidad_id, subruta = unidad_de_ruta(ruta)
    except Exception:
        return False
    if unidad_id is None:
        return True

    try:
        from almacen_bd import es_master
        if es_master(usuario_id):
            return True
    except Exception:
        pass

    try:
        from permisos_unidad_carpeta import rol_en_carpeta
        from api_unidades import rol_en_unidad
    except Exception as excepcion:
        log.warning('no se pudieron leer los roles (%s): no se permite mover', excepcion)
        return False

    try:
        # Primero la carpeta: es lo que acota el ámbito. rol_en_carpeta busca la
        # concesión de esta carpeta o de una superior, así que vale también en
        # las subcarpetas de la que se concedió.
        if rol_en_carpeta(usuario_id, unidad_id, subruta) in ROLES_QUE_MUEVEN:
            return True
        return rol_en_unidad(usuario_id, unidad_id) == ROL_DE_UNIDAD_QUE_MUEVE
    except Exception as excepcion:
        log.warning('fallo comprobando el rol (%s): no se permite mover', excepcion)
        return False


def error_no_puede_mover():
    """El mensaje que se le da a quien no puede. Dice QUIÉN sí puede."""
    return ('Solo puedes mover dentro de las carpetas donde tienes permiso para '
            'hacerlo. Pide a un administrador de la unidad que lo mueva, o que '
            'te dé acceso a esa carpeta.')


# ── Lo propio (17/09/2026) ────────────────────────────────────────────────
# Pedido de Wilson: además de lo anterior, un EDITOR puede mover lo que él
# mismo subió o creó, dentro de la misma unidad. Lo de los demás sigue siendo
# cosa de los administradores. La autoría se reconstruye del registro de
# actividad (autoria_archivos.py); si no se puede saber, NO se permite.
ROLES_QUE_MUEVEN_LO_PROPIO = ('editor', 'manager')


def puede_mover_propios_en(usuario_id: int, ruta: str) -> bool:
    """¿Tiene en esta ruta un rol con el que podría mover LO SUYO?"""
    try:
        unidad_id, subruta = unidad_de_ruta(ruta)
        if unidad_id is None:
            return True
        from permisos_unidad_carpeta import rol_efectivo
        return rol_efectivo(usuario_id, unidad_id, subruta) in ROLES_QUE_MUEVEN_LO_PROPIO
    except Exception as excepcion:
        log.warning('fallo comprobando mover lo propio (%s)', excepcion)
        return False


def puede_mover_lo_propio(usuario_id: int, origen: str, destino: str,
                          sobrescribir: bool = False):
    """(True, None) si puede mover `origen` a `destino` por ser suyo; si no,
    (False, mensaje para la persona)."""
    import os
    from autoria_archivos import es_autor, carpeta_toda_propia
    from seguridad_rutas import ruta_fisica
    try:
        unidad_origen, _ = unidad_de_ruta(origen)
        unidad_destino, _ = unidad_de_ruta(destino)
    except Exception:
        return False, error_no_puede_mover()
    if unidad_origen is None or unidad_origen != unidad_destino:
        return False, error_no_puede_mover()
    if not (puede_mover_propios_en(usuario_id, origen)
            and puede_mover_propios_en(usuario_id, destino)):
        return False, error_no_puede_mover()
    nombre = origen.rstrip('/').rsplit('/', 1)[-1]
    try:
        fisica = ruta_fisica(usuario_id, origen)
    except Exception:
        return False, error_no_puede_mover()
    if os.path.isdir(fisica):
        propio = carpeta_toda_propia(usuario_id, origen, fisica)
        aviso = ('Solo puedes mover carpetas que tú creaste y en las que todo lo '
                 'de dentro lo subiste tú. En «%s» hay cosas de otras personas: '
                 'pide a un administrador de la unidad que la mueva.' % nombre)
    else:
        propio = es_autor(usuario_id, origen)
        aviso = ('Solo puedes mover lo que tú subiste. «%s» lo subió otra persona: '
                 'pide a un administrador de la unidad que lo mueva.' % nombre)
    if not propio:
        return False, aviso
    # Mover encima de algo que ya existe lo reemplaza: tampoco puede ser ajeno.
    if sobrescribir:
        try:
            if os.path.exists(ruta_fisica(usuario_id, destino)) and not es_autor(usuario_id, destino):
                return False, ('En el destino ya hay un «%s» de otra persona: no se '
                               'puede reemplazar. Muévelo con otro nombre.' % nombre)
        except Exception:
            return False, error_no_puede_mover()
    return True, None
