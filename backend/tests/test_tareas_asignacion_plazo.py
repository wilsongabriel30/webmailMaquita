"""«Asignar tarea a:» con plazo e indicaciones, y aviso de tarea realizada (30/10/2026).

- El aviso de asignación lleva quién asignó, el plazo en palabras y las indicaciones.
- El plazo llega como día («AAAA-MM-DD») y queda como fecha de vencimiento; las indicaciones se guardan por asignación.
- Al completarse, se avisa (pantalla y correo) a quien la asignó, nunca a quien la completó; sin asignación, nada.
"""

import asyncio
from datetime import datetime

from app.tasks import asignar, aviso_asignacion, avisos_listas


def test_fecha_larga_en_espanol():
    assert (
        aviso_asignacion.fecha_larga(datetime(2026, 10, 31))
        == "sábado 31 de octubre de 2026"
    )
    assert (
        aviso_asignacion.fecha_larga(datetime(2026, 11, 2))
        == "lunes 2 de noviembre de 2026"
    )


def test_texto_con_plazo_e_indicaciones(monkeypatch):
    monkeypatch.setattr(aviso_asignacion.avisos, "nombre", lambda c: "Ana Pérez")
    t = aviso_asignacion.texto_asignada(
        "ana@x.org",
        "Informe",
        "Trabajo",
        datetime(2026, 11, 2),
        "  Revisar el anexo 3  ",
    )
    assert t.startswith("Ana Pérez te asignó la tarea «Informe» (lista «Trabajo»).")
    assert "Plazo para realizarla: lunes 2 de noviembre de 2026." in t
    assert t.endswith("Indicaciones: «Revisar el anexo 3»")


def test_texto_sin_plazo_ni_indicaciones(monkeypatch):
    monkeypatch.setattr(aviso_asignacion.avisos, "nombre", lambda c: "Ana")
    t = aviso_asignacion.texto_asignada("ana@x.org", "Informe", "Trabajo", None, "   ")
    assert "Plazo" not in t and "Indicaciones" not in t


def test_asignacion_acepta_el_dia_como_plazo():
    a = asignar.Asignacion(emails=["Beto@X.org"], mensaje="hazlo", plazo="2026-11-02")
    assert a.plazo == datetime(2026, 11, 2) and a.emails == ["beto@x.org"]
    assert asignar.Asignacion(emails=[]).plazo is None


class _DBAsignar:
    """Tarea de una lista propia; quien asigna la ve. Guarda lo que se escribe."""

    def __init__(self):
        self.escrito = []

    async def fetchrow(self, sql, *a):
        return {
            "id": a[0],
            "title": "Informe",
            "list_id": "L",
            "asignada": False,
            "lista": "Trabajo",
            "list_type": "custom",
        }

    async def fetch(self, sql, *a):
        return []

    async def execute(self, sql, *a):
        self.escrito.append((sql, a))


def test_asignar_guarda_indicaciones_y_plazo(monkeypatch):
    async def puede(*a):
        return True

    async def registrar(*a, **k):
        return None

    monkeypatch.setattr(asignar.acceso, "puede_ver_tarea", puede)
    monkeypatch.setattr(asignar.actividad, "registrar", registrar)
    monkeypatch.setattr(asignar.compartir, "de_la_casa", lambda e: True)
    db = _DBAsignar()
    plazo = datetime(2026, 11, 2)
    nuevos, _ = asyncio.run(
        asignar.asignar(db, "ana@x.org", "C1", ["beto@x.org"], " Revisar ", plazo)
    )
    assert nuevos == ["beto@x.org"]
    alta = next(a for s, a in db.escrito if s.startswith("INSERT INTO task_asignados"))
    assert alta == ("C1", "beto@x.org", "ana@x.org", "Revisar")
    tarjeta = next(a for s, a in db.escrito if s.startswith("UPDATE task_cards"))
    assert tarjeta == ("C1", "beto@x.org", plazo)


class _DBRealizada:
    def __init__(self, asignadores):
        self.asignadores = asignadores

    async def fetchrow(self, sql, *a):
        return {"title": "Informe"}

    async def fetch(self, sql, *a):
        return [{"asignado_por": p} for p in self.asignadores]


def _realizar(monkeypatch, asignadores, quien):
    enviados = []

    async def avisar(
        redis, db, destinatarios, por, accion, titulo, texto, task_id=None, correo=False
    ):
        enviados.append((sorted(destinatarios), por, titulo, texto, correo))

    monkeypatch.setattr(avisos_listas, "avisar", avisar)
    monkeypatch.setattr(aviso_asignacion.avisos, "nombre", lambda c: "Beto")
    asyncio.run(
        aviso_asignacion.avisar_realizada(_DBRealizada(asignadores), None, quien, "C1")
    )
    return enviados


def test_realizada_avisa_por_correo_a_quien_asigno(monkeypatch):
    enviados = _realizar(monkeypatch, ["ana@x.org"], "beto@x.org")
    assert len(enviados) == 1
    destinatarios, por, titulo, texto, correo = enviados[0]
    assert destinatarios == ["ana@x.org"] and por == "beto@x.org" and correo is True
    assert (
        titulo == "Tarea realizada"
        and "Beto marcó como realizada la tarea «Informe»" in texto
    )


def test_realizada_sin_asignacion_no_avisa(monkeypatch):
    assert _realizar(monkeypatch, [], "beto@x.org") == []


def test_aviso_nunca_a_quien_hizo_el_cambio():
    """avisos_listas.avisar descarta a quien completó: si la asignadora completa su propia tarea, no se avisa."""
    publicados = []

    class _Redis:
        async def publish(self, canal, msg):
            publicados.append(canal)

    asyncio.run(
        avisos_listas.avisar(
            _Redis(), None, ["ana@x.org"], "ana@x.org", "completed", "t", "x"
        )
    )
    assert publicados == []
