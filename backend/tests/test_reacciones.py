"""Reacciones a un correo: una por persona, cambiar, quitar y resumen por emoji."""

import email

from app.mail.services import reacciones as r


class _Db:
    def __init__(self):
        self.filas: dict[tuple[str, str], str] = {}

    async def fetchval(self, sql, *a):
        if "FROM mail_reacciones" in sql:
            return self.filas.get((a[0], a[1]))
        return {"ana@example.org": "Ana Pérez"}.get(a[0])

    async def execute(self, sql, *a):
        if sql.lstrip().startswith("DELETE"):
            self.filas.pop((a[0], a[1]), None)
        else:
            self.filas[(a[0], a[1])] = a[2]

    async def fetch(self, sql, *a):
        if "FROM mail_reacciones" in sql:
            return [
                {"usuario": u, "emoji": e, "nombre": u.split("@")[0]}
                for (mid, u), e in self.filas.items()
                if mid == a[0]
            ]
        return [{"username": d} for d in a[0] if d.endswith("@example.org")]


def test_catalogo():
    assert r.emoji_valido("👍") and r.emoji_valido("😢")
    assert (
        not r.emoji_valido("💩")
        and not r.emoji_valido("")
        and not r.emoji_valido("👍👍")
    )


async def test_poner_cambiar_y_quitar():
    db = _Db()
    assert await r.alternar(db, "<m1>", "ana@example.org", "👍") == "puesta"
    assert await r.alternar(db, "<m1>", "ana@example.org", "🎉") == "cambiada"
    assert db.filas == {("<m1>", "ana@example.org"): "🎉"}  # una sola por persona
    assert await r.alternar(db, "<m1>", "ana@example.org", "🎉") == "quitada"
    assert db.filas == {}


async def test_resumen_agrupa_y_marca_la_mia():
    db = _Db()
    await r.alternar(db, "<m1>", "ana@example.org", "🎉")
    await r.alternar(db, "<m1>", "luis@example.org", "👍")
    await r.alternar(db, "<m1>", "eva@example.org", "👍")
    await r.alternar(db, "<otro>", "eva@example.org", "😢")
    grupos = await r.resumen(db, "<m1>", "eva@example.org")
    assert [(g["emoji"], g["total"], g["mia"]) for g in grupos] == [
        ("👍", 2, True),
        ("🎉", 1, False),
    ]
    assert grupos[0]["personas"] == ["luis", "eva"]


async def test_participantes_y_cuentas_locales():
    msg = email.message_from_string(
        "From: Ana <ANA@example.org>\nTo: luis@example.org, Externo <x@gmail.test>\nCc: eva@example.org\n\n"
    )
    autor, todos = r.participantes(msg)
    assert autor == "ana@example.org"
    assert todos == {
        "ana@example.org",
        "luis@example.org",
        "x@gmail.test",
        "eva@example.org",
    }
    locales = await r.cuentas_locales(_Db(), todos - {"luis@example.org"})
    assert locales == ["ana@example.org", "eva@example.org"]


class _DbLista:
    async def fetch(self, _sql, ids):
        assert "<m1@x>" in ids and "m2@x" in ids
        return [
            {"message_id": "<m1@x>", "emoji": "🎉", "n": 1},
            {"message_id": "<m1@x>", "emoji": "👍", "n": 2},
            {"message_id": "m2@x", "emoji": "❤️", "n": 1},
        ]


async def test_la_lista_marca_los_correos_con_reacciones():
    mensajes = [
        {"uid": 1, "message_id": "<m1@x>"},
        {"uid": 2, "message_id": "<m2@x>"},
        {"uid": 3, "message_id": ""},
        {"uid": 4},
    ]
    await r.anotar_en_lista(_DbLista(), mensajes)
    assert mensajes[0]["reacciones"] == {"total": 3, "emojis": ["👍", "🎉"]}
    assert mensajes[1]["reacciones"] == {"total": 1, "emojis": ["❤️"]}
    assert "reacciones" not in mensajes[2] and "reacciones" not in mensajes[3]


async def test_la_lista_sale_aunque_falle_la_consulta():
    class _Roto:
        async def fetch(self, *a):
            raise RuntimeError("sin base")

    mensajes = [{"uid": 1, "message_id": "<m1@x>"}]
    await r.anotar_en_lista(_Roto(), mensajes)
    assert mensajes == [{"uid": 1, "message_id": "<m1@x>"}]
