# -*- coding: utf-8 -*-
"""T-49 parte 3 - La HORA ORIGINAL de escritura de un mensaje.

Cuando alguien escribe sin internet, el mensaje se queda en la cola del equipo y sale al
volver la conexion. Si al entregarse solo se viera la hora de llegada, parecerian mensajes
tardios de una persona lenta; en realidad la demora fue del internet. Por eso el cliente
manda tambien CUANDO SE ESCRIBIO, y aqui se guarda para que el receptor pueda ver
"escrito 10:02 - entregado 10:20".

Se guarda dentro de `metadata` del mensaje (columna jsonb que ya existia): no hace falta
cambiar el esquema de la base, que en produccion siempre es lo mas delicado.

La hora la da el equipo de quien escribe, asi que NO es de fiar: puede venir mal por un
reloj desajustado o por alguien que quiera aparentar. Por eso se valida:
  * si viene en el futuro (mas de 2 minutos), se descarta;
  * si viene de hace mas de 7 dias, se descarta;
  * si es posterior a la hora de llegada, se descarta.
Descartar significa quedarse solo con la hora real de llegada, que siempre es del servidor.
"""
from datetime import datetime, timedelta, timezone

CAMPO = 'escrito_en'
MARGEN_FUTURO = timedelta(minutes=2)
ANTIGUEDAD_MAXIMA = timedelta(days=7)


def leer(datos):
    """Saca la hora de escritura de lo que manda el cliente. Devuelve None si no vale."""
    if not isinstance(datos, dict):
        return None
    crudo = datos.get(CAMPO) or datos.get('written_at') or datos.get('escritoEn')
    if not crudo:
        return None
    try:
        texto = str(crudo).replace('Z', '+00:00')
        cuando = datetime.fromisoformat(texto)
    except (TypeError, ValueError):
        return None
    if cuando.tzinfo is None:
        cuando = cuando.replace(tzinfo=timezone.utc)
    ahora = datetime.now(timezone.utc)
    if cuando > ahora + MARGEN_FUTURO:
        return None
    if cuando < ahora - ANTIGUEDAD_MAXIMA:
        return None
    return cuando


def guardar(sesion, mensaje_id, cuando):
    """Anota la hora de escritura en el mensaje ya creado. Nunca lanza: si falla, el
    mensaje ya se envio y lo unico que se pierde es el matiz de la hora."""
    if not (mensaje_id and cuando):
        return False
    try:
        from sqlalchemy import text
        sesion.execute(text(
            "UPDATE chat_messages "
            "SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('escrito_en', :v) "
            "WHERE id = :id"
        ), {'v': cuando.isoformat(), 'id': int(mensaje_id)})
        # confirmar aqui mismo: el mensaje ya salio, y sin esto la anotacion se perderia
        # si la peticion termina sin confirmar la transaccion
        sesion.commit()
        return True
    except Exception:
        return False


def para_mostrar(cuando):
    """Devuelve la hora en el MISMO formato que usa `created_at` al salir hacia el cliente:
    hora local del servidor y sin indicar el huso.

    No es un capricho: `created_at` viaja asi, y si `escrito_en` fuera en UTC con huso, el
    cliente compararia dos horas que no son comparables y mostraria diferencias absurdas
    (se vio en la prueba: casi un dia de diferencia en un mensaje de hace 18 minutos).
    Las dos horas que se muestran juntas tienen que medirse con la misma vara.
    """
    if cuando is None:
        return None
    if isinstance(cuando, str):
        try:
            cuando = datetime.fromisoformat(cuando.replace('Z', '+00:00'))
        except ValueError:
            return cuando
    if cuando.tzinfo is None:
        return cuando.isoformat()
    return cuando.astimezone().replace(tzinfo=None).isoformat()


def desde_metadata(metadata):
    """La hora de escritura guardada, para devolverla al pintar el mensaje."""
    if isinstance(metadata, dict):
        return metadata.get(CAMPO)
    return None


def hubo_demora(escrito_en, entregado_en, minutos=2):
    """Si merece la pena ENSENAR las dos horas. Si el mensaje salio enseguida, mostrar
    "escrito 10:02 - entregado 10:02" solo seria ruido."""
    if not (escrito_en and entregado_en):
        return False
    try:
        a = datetime.fromisoformat(str(escrito_en).replace('Z', '+00:00'))
        b = datetime.fromisoformat(str(entregado_en).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return False
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return (b - a) >= timedelta(minutes=minutos)


# Nota para quien lea esto mas adelante: en la base se guarda la hora con su huso (dato
# integro); lo de arriba es solo como se muestra.
