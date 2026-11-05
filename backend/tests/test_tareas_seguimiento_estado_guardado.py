"""Seguimiento (T-34): la salida lleva el estado guardado además del calculado.

Una tarea vencida sale con `estado = "vencida"` (calculado por el plazo) y `estado_guardado` con lo que hay en la
base (pendiente / en curso): el tablero la pone en esa columna y así se puede arrastrar a otra.
"""

import uuid
from datetime import datetime, timedelta, timezone

from app.tareas.servicio import a_salida


def _fila(estado, plazo, completed=False):
    ahora = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(),
        "title": "Revisar informe",
        "description": "",
        "asignados": ["ana@example.org"],
        "created_by": "jefa@example.org",
        "due_date": plazo,
        "priority": "medium",
        "etiquetas": "[]",
        "labels": "[]",
        "estado": estado,
        "completed": completed,
        "aceptacion": "aceptada",
        "motivo_rechazo": "",
        "recurrence": None,
        "activa_a": None,
        "activa_tarea_id": None,
        "escalar_a": None,
        "escalado_en": None,
        "correo_ref": None,
        "st_total": 0,
        "st_hechas": 0,
        "n_com": 0,
        "completed_by": None,
        "completed_at": None,
        "created_at": ahora,
        "updated_at": ahora,
    }


def test_vencida_conserva_el_estado_guardado():
    ayer = datetime.now(timezone.utc) - timedelta(days=1)
    t = a_salida(_fila("en_curso", ayer))
    assert t.estado == "vencida" and t.estado_guardado == "en_curso"
    assert t.semaforo == "rojo"


def test_a_tiempo_estado_y_guardado_iguales():
    manana = datetime.now(timezone.utc) + timedelta(days=5)
    t = a_salida(_fila("pendiente", manana))
    assert t.estado == t.estado_guardado == "pendiente"


def test_completada_y_espera_no_se_vuelven_vencidas():
    ayer = datetime.now(timezone.utc) - timedelta(days=1)
    assert a_salida(_fila("completada", ayer, completed=True)).estado == "completada"
    t = a_salida(_fila("espera", ayer))
    assert t.estado == t.estado_guardado == "espera"
