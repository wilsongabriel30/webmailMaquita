# -*- coding: utf-8 -*-
"""
Conversión automática de formatos antiguos al subirlos (20/10/2026).
====================================================================
PEDIDO de Wilson: «que se conviertan solos al subir». Hasta hoy un .xls/.doc/.ppt/.xlsb
se guardaba tal cual y se convertía recién en el PRIMER clic de alguien con permiso
(conversion_edicion.preparar_para_editar): con un .xls de 188 MB eso eran varios
minutos de espera delante de «cargando», y en modo lectura mientras tanto.

CÓMO: al subir (web o enlace externo) el archivo se ENCOLA en `conversiones_pendientes`;
un proceso aparte (herramientas/convertir_pendientes.py, cron cada 3 min) llama al mismo
preparar_para_editar de siempre: .xlsx/.docx/.pptx en la misma carpeta, el original a
la papelera (recuperable), enlaces cortos y compartidos que siguen al nuevo. Así, cuando
alguien lo abre, ya está listo. La conversión NO corre dentro de la petición web: el
conversor del Document Server es lento con archivos grandes y atiende de a uno.

También se puede encolar lo que YA estaba en el Drive (encolar_antiguos): va del más
pequeño al más grande y en lotes, porque son miles de archivos (13.600 el 20/10/2026).

Nada de aquí lanza excepciones hacia quien sube: encolar falla en silencio (se registra).
Autoría: Equipo de Tecnología Maquita — 2026-10-20
"""
import logging
import os
import time

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.conversion_automatica')

MAX_INTENTOS = 20      # cada intento espera su plazo; el conversor atiende de a uno y un libro enorme puede tenerlo ocupado media hora
_esquema_listo = False


def _asegurar_esquema():
    global _esquema_listo
    if _esquema_listo:
        return
    ejecutar("""
        CREATE TABLE IF NOT EXISTS conversiones_pendientes (
            usuario_id  INTEGER NOT NULL,          -- quien tiene permiso para convertirlo
            ruta        TEXT    NOT NULL,          -- ruta virtual vista por ese usuario
            estado      TEXT    NOT NULL DEFAULT 'pendiente',   -- pendiente | hecho | fallido | desaparecido
            intentos    INTEGER NOT NULL DEFAULT 0,
            detalle     TEXT,
            creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado TIMESTAMPTZ,
            PRIMARY KEY (usuario_id, ruta)
        );
        CREATE INDEX IF NOT EXISTS ix_conversiones_pendientes_estado
            ON conversiones_pendientes (estado, creado_en);
    """)
    _esquema_listo = True


def _convertible(ruta_virtual: str) -> bool:
    try:
        import conversion_edicion
        return conversion_edicion.es_convertible(conversion_edicion.extension_de(ruta_virtual))
    except Exception:
        return False


def encolar(usuario_id: int, ruta_virtual: str) -> bool:
    """Marca un archivo recién subido para convertirlo en segundo plano.
    Devuelve True si quedó en cola. Nunca lanza."""
    try:
        if not _convertible(ruta_virtual):
            return False
        from archivos_internos import en_carpeta_interna
        if en_carpeta_interna(ruta_virtual):
            return False
        _asegurar_esquema()
        ejecutar("""
            INSERT INTO conversiones_pendientes (usuario_id, ruta)
            VALUES (%s, %s)
            ON CONFLICT (usuario_id, ruta) DO UPDATE
               SET estado = 'pendiente', intentos = 0, detalle = NULL, creado_en = NOW()
        """, (int(usuario_id), ruta_virtual))
        log.info('conversión automática: en cola %s (usuario %s)', ruta_virtual, usuario_id)
        return True
    except Exception as excepcion:
        log.warning('conversión automática: no se pudo encolar %s de %s: %s',
                    ruta_virtual, usuario_id, excepcion)
        return False


def _marcar(usuario_id, ruta, estado, detalle=None, sumar_intento=False):
    ejecutar("""
        UPDATE conversiones_pendientes
           SET estado = %s, detalle = %s, actualizado = NOW(),
               intentos = intentos + %s
         WHERE usuario_id = %s AND ruta = %s
    """, (estado, (detalle or '')[:500], 1 if sumar_intento else 0, int(usuario_id), ruta))


def procesar(limite: int = 20, segundos_max: int = 1500) -> dict:
    """Convierte lo pendiente, de a uno, hasta `limite` archivos o `segundos_max`.
    Lo llama herramientas/convertir_pendientes.py (cron). Devuelve un resumen."""
    _asegurar_esquema()
    import conversion_edicion
    from seguridad_rutas import RutaInvalida, ruta_fisica
    resumen = {'hechos': 0, 'fallidos': 0, 'desaparecidos': 0, 'reintentar': 0}
    inicio = time.monotonic()
    filas = consultar("""
        SELECT usuario_id, ruta, intentos FROM conversiones_pendientes
         WHERE estado = 'pendiente' AND intentos < %s
         ORDER BY creado_en LIMIT %s
    """, (MAX_INTENTOS, int(limite)))
    for fila in filas:
        if time.monotonic() - inicio > segundos_max:
            break
        uid, ruta = int(fila['usuario_id']), fila['ruta']
        try:
            fisica = ruta_fisica(uid, ruta)
        except RutaInvalida as excepcion:
            _marcar(uid, ruta, 'fallido', 'sin acceso: %s' % excepcion)
            resumen['fallidos'] += 1
            continue
        if not os.path.isfile(fisica):
            # Si ya está la copia moderna al lado (alguien lo abrió y se convirtió
            # en ese momento), no «desapareció»: está hecho.
            moderna = conversion_edicion.ruta_moderna(ruta)
            try:
                if moderna and os.path.isfile(ruta_fisica(uid, moderna)):
                    _marcar(uid, ruta, 'hecho', '%s ya existía' % moderna)
                    resumen['hechos'] += 1
                    continue
            except RutaInvalida:
                pass
            _marcar(uid, ruta, 'desaparecido', 'el archivo ya no está en esa ruta')
            resumen['desaparecidos'] += 1
            continue
        t0 = time.monotonic()
        ruta_nueva, _ = conversion_edicion.preparar_para_editar(uid, ruta, fisica)
        segundos = time.monotonic() - t0
        if ruta_nueva != ruta:
            _marcar(uid, ruta, 'hecho', '%s en %.0f s' % (ruta_nueva, segundos))
            resumen['hechos'] += 1
            log.info('conversión automática: %s → %s (%.0f s)', ruta, ruta_nueva, segundos)
            continue
        # No se convirtió: conversor ocupado, plazo agotado (el servidor la sigue
        # haciendo y el próximo intento la recoge) o fallo real.
        if int(fila['intentos']) + 1 >= MAX_INTENTOS:
            _marcar(uid, ruta, 'fallido', 'no se convirtió tras %d intentos' % MAX_INTENTOS, sumar_intento=True)
            resumen['fallidos'] += 1
            try:
                import limites_editor
                limites_editor.avisar_tecnologia(
                    'Conversión automática fallida',
                    'usuario %s · %s · %s · no se convirtió tras %d intentos (ver registro)'
                    % (uid, ruta, limites_editor.humano(os.path.getsize(fisica)), MAX_INTENTOS))
            except Exception:
                pass
        else:
            _marcar(uid, ruta, 'pendiente', 'intento sin resultado (%.0f s)' % segundos, sumar_intento=True)
            resumen['reintentar'] += 1
    return resumen


def _usuario_para_unidad(unidad_id: int):
    """Un miembro con permiso de escritura en la unidad (manager primero)."""
    filas = consultar("""
        SELECT usuario_id FROM unidad_miembros
         WHERE unidad_id = %s AND rol IN ('manager', 'editor')
         ORDER BY CASE rol WHEN 'manager' THEN 0 ELSE 1 END, usuario_id
         LIMIT 1
    """, (int(unidad_id),))
    return int(filas[0]['usuario_id']) if filas else None


def encolar_antiguos(limite: int = 300, maximo_bytes: int = None) -> int:
    """Encola archivos de formato antiguo que ya estaban en el Drive (del índice
    de nombres), del más pequeño al más grande, saltando los ya tratados.
    Devuelve cuántos encoló."""
    _asegurar_esquema()
    import re
    condicion_tamano = 'AND n.tamano <= %d' % int(maximo_bytes) if maximo_bytes else ''
    filas = consultar("""
        SELECT n.usuario_id, n.ruta, n.tamano
          FROM indice_nombres n
         WHERE n.es_carpeta = false
           AND lower(n.extension) IN ('xls', 'doc', 'ppt', 'xlt', 'dot', 'pot', 'xlsb')
           AND n.ruta NOT LIKE '%%/.formularios/%%'
           AND NOT EXISTS (SELECT 1 FROM conversiones_pendientes c
                            WHERE c.ruta = n.ruta
                              AND (c.usuario_id = n.usuario_id OR n.usuario_id = 0))
           """ + condicion_tamano + """
         ORDER BY n.tamano LIMIT %s
    """, (int(limite),))
    encolados = 0
    for fila in filas:
        uid, ruta = int(fila['usuario_id']), fila['ruta']
        if uid == 0:                       # unidad compartida: hace falta un miembro con permiso
            m = re.match(r'^/unidades/(\d+)/', ruta)
            uid = _usuario_para_unidad(int(m.group(1))) if m else None
            if not uid:
                continue
        if encolar(uid, ruta):
            encolados += 1
    return encolados


def resumen_estado() -> dict:
    _asegurar_esquema()
    filas = consultar('SELECT estado, count(*) AS n FROM conversiones_pendientes GROUP BY estado')
    return {f['estado']: int(f['n']) for f in filas}
