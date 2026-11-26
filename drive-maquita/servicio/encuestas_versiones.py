"""Formularios del Almacén — encuestas de campo: versiones publicadas y caducidad (Fase 1, paso 5, 10/11/2026).

Un formulario normal del Drive se responde siempre con lo último guardado: si
alguien cambia una pregunta, el enlace lo enseña al momento. Para el trabajo de
campo eso no sirve: los promotores y la app trabajan días sin señal con una
copia, y las respuestas de un mismo levantamiento tienen que responder TODAS a
las mismas preguntas.

Una ENCUESTA DE CAMPO (ajuste `campo`) se responde con su VERSIÓN PUBLICADA:
  · «Publicar versión» congela la definición tal como está (v1, v2…) en
    `encuesta_versiones`. Lo que se edite después no llega al campo hasta
    publicar la siguiente versión.
  · La fecha de caducidad es OBLIGATORIA. Es el `cierra_en` de siempre, así
    que el plazo lo sigue haciendo cumplir `_fuera_de_plazo`, por enlace y por QR.
    Una encuesta de campo sin caducidad no se sirve.
  · Cada respuesta guarda con qué versión se respondió (`encuesta_respuestas.version`).

Publicar sin cambios no crea versión nueva (misma huella): solo actualiza la caducidad.
"""
import hashlib
import json
from datetime import datetime, timedelta

import almacen_bd as bd
import encuestas_ajustes as ajustes_mod
import encuestas_bd as ebd

DIAS_MAX = 730               # una campaña de campo no dura más de dos años
_instalado = False


class PublicacionInvalida(ValueError):
    pass


def _instalar():
    global _instalado
    if _instalado:
        return
    bd.ejecutar("""
        CREATE TABLE IF NOT EXISTS encuesta_versiones (
            encuesta_id   TEXT NOT NULL REFERENCES encuestas(id) ON DELETE CASCADE,
            version       INTEGER NOT NULL,
            definicion    JSONB NOT NULL,
            huella        TEXT NOT NULL,
            publicada_en  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            publicada_por INTEGER,
            caduca        TIMESTAMP,
            PRIMARY KEY (encuesta_id, version)
        );
        ALTER TABLE encuesta_respuestas ADD COLUMN IF NOT EXISTS version INTEGER;
    """)
    _instalado = True


def huella(definicion):
    texto = json.dumps(definicion, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def es_campo(fila):
    return bool(ajustes_mod.limpiar((fila or {}).get('ajustes')).get('campo'))


def vigente(encuesta_id):
    """La última versión publicada (con su definición) o None."""
    _instalar()
    filas = bd.consultar('SELECT version, definicion, huella, publicada_en, publicada_por, caduca '
                         'FROM encuesta_versiones WHERE encuesta_id = %s '
                         'ORDER BY version DESC LIMIT 1', (encuesta_id,))
    return filas[0] if filas else None


def listar(encuesta_id):
    _instalar()
    filas = bd.consultar('SELECT v.version, v.publicada_en, v.caduca, v.publicada_por, '
                         '(SELECT COUNT(*) FROM encuesta_respuestas r '
                         ' WHERE r.encuesta_id = v.encuesta_id AND r.version = v.version) AS respuestas '
                         'FROM encuesta_versiones v WHERE v.encuesta_id = %s ORDER BY v.version DESC',
                         (encuesta_id,))
    return [{'version': f['version'],
             'publicada_en': f['publicada_en'].isoformat() if f['publicada_en'] else None,
             'caduca': f['caduca'].strftime('%Y-%m-%dT%H:%M') if f['caduca'] else None,
             'publicada_por': f['publicada_por'], 'respuestas': int(f['respuestas'] or 0)}
            for f in filas]


def _caducidad(texto, ahora=None):
    momento = ajustes_mod.momento(texto)
    if not momento:
        raise PublicacionInvalida('Pon la fecha de caducidad: en las encuestas de campo es obligatoria.')
    ahora = ahora or datetime.now()
    if momento <= ahora + timedelta(minutes=30):
        raise PublicacionInvalida('La fecha de caducidad tiene que ser futura.')
    if momento > ahora + timedelta(days=DIAS_MAX):
        raise PublicacionInvalida(f'La caducidad no puede pasar de {DIAS_MAX // 365} años.')
    return momento


def publicar(fila, definicion, usuario_id, caduca_texto):
    """Publica (o confirma) la versión de campo. Devuelve (version, nueva: bool)."""
    _instalar()
    caduca = _caducidad(caduca_texto)
    ajustes = ajustes_mod.limpiar(fila.get('ajustes'))
    ajustes['campo'] = True
    ajustes['cierra_en'] = caduca.strftime('%Y-%m-%dT%H:%M')
    ebd.guardar_ajustes(fila['id'], ajustes)
    ebd.publicar(fila['id'])                           # que tenga enlace
    actual = vigente(fila['id'])
    h = huella(definicion)
    if actual and actual['huella'] == h:
        bd.ejecutar('UPDATE encuesta_versiones SET caduca = %s WHERE encuesta_id = %s AND version = %s',
                    (caduca, fila['id'], actual['version']))
        return actual['version'], False
    numero = (actual['version'] if actual else 0) + 1
    bd.ejecutar('INSERT INTO encuesta_versiones (encuesta_id, version, definicion, huella, publicada_por, caduca) '
                'VALUES (%s, %s, %s::jsonb, %s, %s, %s)',
                (fila['id'], numero, json.dumps(definicion, ensure_ascii=False), h, usuario_id, caduca))
    return numero, True


def quitar(fila):
    """Deja de ser encuesta de campo: vuelve a responderse con lo último guardado.
    Las versiones y las respuestas se conservan."""
    ajustes = ajustes_mod.limpiar(fila.get('ajustes'))
    ajustes['campo'] = False
    ebd.guardar_ajustes(fila['id'], ajustes)


def para_responder(fila, definicion):
    """(definición con la que se responde, mensaje de error).

    Formulario normal → la de siempre. Encuesta de campo → la versión publicada,
    con `_version`; sin versión o sin caducidad no se sirve."""
    if not es_campo(fila):
        return definicion, None
    if not ajustes_mod.limpiar(fila.get('ajustes')).get('cierra_en'):
        return None, 'Esta encuesta de campo no tiene fecha de caducidad. Pide a quien la creó que la publique de nuevo.'
    actual = vigente(fila['id'])
    if not actual:
        return None, 'Esta encuesta de campo todavía no tiene una versión publicada.'
    congelada = dict(actual['definicion'])
    congelada['_version'] = actual['version']
    return congelada, None


def estado(fila, definicion):
    """Lo que enseña el panel «Publicar» del editor."""
    actual = vigente(fila['id']) if fila else None
    ajustes = ajustes_mod.limpiar((fila or {}).get('ajustes'))
    return {
        'campo': bool(ajustes.get('campo')),
        'caduca': ajustes.get('cierra_en') or None,
        'vigente': actual['version'] if actual else None,
        'pendiente': bool(actual) and actual['huella'] != huella(definicion),
        'versiones': listar(fila['id']) if fila else [],
    }


def conservar(nuevos, antes, forzados):
    """Al guardar la pestaña «Configuración»: `campo` solo cambia desde el panel
    de campo (la pantalla de ajustes no lo conoce), y una encuesta de campo no
    puede quedarse sin caducidad."""
    antes = ajustes_mod.limpiar(antes)
    nuevos = dict(nuevos)
    nuevos['campo'] = antes.get('campo', False)
    if nuevos['campo'] and not nuevos.get('cierra_en'):
        nuevos['cierra_en'] = antes.get('cierra_en') or ''
        forzados = list(forzados) + ['Se mantuvo la fecha de cierre: en una encuesta de campo es obligatoria.']
    return nuevos, forzados
