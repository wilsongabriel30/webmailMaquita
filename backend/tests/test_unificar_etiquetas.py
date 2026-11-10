"""Fusión de etiquetas de una cuenta con dominio doble: función pura del script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.unificar_etiquetas_dominio_doble import Plan, planificar_fusion  # noqa: E402


def et(id_, name, color="#000"):
    return {"id": id_, "name": name, "color": color}


def asg(id_, folder, uid, label_id):
    return {"id": id_, "folder": folder, "message_uid": uid, "label_id": label_id}


def test_fusion_por_nombre_y_creacion_de_las_que_faltan():
    plan = planificar_fusion(
        [et(1, "Trabajo"), et(2, "  proyecto X "), et(3, "Zimbra")],
        [et(10, "trabajo"), et(11, "Proyecto x")],
        [], [],
    )
    assert plan.mapa_etiqueta == {1: 10, 2: 11}
    assert plan.etiquetas_crear == [("Zimbra", "#000", 3)]
    assert sorted(plan.etiquetas_borrar) == [1, 2, 3]
    assert plan.etiquetas_conservadas == []


def test_asignaciones_sin_duplicar_mismo_buzon():
    plan = planificar_fusion(
        [et(1, "Trabajo")],
        [et(10, "Trabajo")],
        [asg(100, "INBOX", 5, 1), asg(101, "INBOX", 6, 1), asg(102, "INBOX", 6, 1)],
        [asg(200, "INBOX", 5, 10)],  # ya existe en destino
        mapa_uid=None,
    )
    assert plan.asignaciones_insertar == [("INBOX", 6, 1)]
    assert sorted(plan.asignaciones_borrar) == [100, 101, 102]
    assert plan.asignaciones_sin_resolver == []


def test_uids_resueltos_por_message_id_y_pendientes_conservan_la_etiqueta():
    plan = planificar_fusion(
        [et(1, "A"), et(2, "B")],
        [],
        [asg(100, "INBOX", 5, 1), asg(101, "INBOX", 9, 2)],
        [],
        mapa_uid={("INBOX", 5): 77, ("INBOX", 9): None},
    )
    assert plan.asignaciones_insertar == [("INBOX", 77, 1)]
    assert plan.asignaciones_borrar == [100]
    assert [a["id"] for a in plan.asignaciones_sin_resolver] == [101]
    assert plan.etiquetas_borrar == [1]
    assert plan.etiquetas_conservadas == [2]  # borrarla arrastraría la asignación pendiente (CASCADE)


def test_trasladar_sin_resolver_copia_el_uid_tal_cual():
    plan = planificar_fusion([et(2, "B")], [], [asg(101, "INBOX", 9, 2)], [], mapa_uid={("INBOX", 9): None}, trasladar_sin_resolver=True)
    assert plan.asignaciones_insertar == [("INBOX", 9, 2)]
    assert plan.asignaciones_sin_resolver == [] and plan.etiquetas_borrar == [2]


def test_idempotente_segunda_pasada_no_hace_nada():
    # Tras aplicar la primera pasada, el origen queda vacío: el plan es vacío.
    plan = planificar_fusion([], [et(10, "Trabajo")], [], [asg(200, "INBOX", 5, 10)])
    assert plan == Plan()
    assert "0 por insertar" in plan.resumen()
