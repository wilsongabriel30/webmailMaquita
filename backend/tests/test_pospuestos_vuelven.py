"""Los correos pospuestos vuelven a su carpeta, y vuelve el correo correcto (Andes, 15/11/2026)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.mail.services import pospuestos as p

EN_CARPETA = [
    (11, "Informe de ventas", "ana@example.org"),
    (12, "Acta de la reunión", "luis@example.org"),
    (13, "Acta de la reunión", "luis@example.org"),
]


def test_con_uid_anotado_vuelve_ese_correo_y_no_el_primero():
    assert p.elegir_uid(12, "", "", EN_CARPETA) == (p.DEVUELTO, 12)


def test_con_uid_anotado_que_ya_no_esta_no_se_mueve_otro():
    assert p.elegir_uid(99, "Informe de ventas", "ana@example.org", EN_CARPETA) == (
        p.YA_NO_ESTABA,
        None,
    )


def test_fila_antigua_se_resuelve_por_remitente_y_asunto():
    assert p.elegir_uid(None, "  informe de   VENTAS ", "Ana@example.org", EN_CARPETA) == (
        p.DEVUELTO,
        11,
    )


def test_fila_antigua_ambigua_o_sin_coincidencia_no_mueve_nada():
    assert p.elegir_uid(None, "Acta de la reunión", "luis@example.org", EN_CARPETA)[0] == (
        p.INDETERMINADO
    )
    assert p.elegir_uid(None, "Otro asunto", "ana@example.org", EN_CARPETA)[0] == (
        p.INDETERMINADO
    )


def test_fila_antigua_con_la_carpeta_vacia_se_da_por_cerrada():
    assert p.elegir_uid(None, "Informe", "ana@example.org", []) == (p.YA_NO_ESTABA, None)


def test_el_asunto_se_compara_con_el_mismo_recorte_que_guarda_la_tabla():
    largo = "x" * 700
    assert p.elegir_uid(None, largo[:500], "a@example.org", [(5, largo, "a@example.org")]) == (
        p.DEVUELTO,
        5,
    )


def test_datos_de_cabecera_admite_objeto_y_diccionario():
    class Normalizado:
        uid, subject, from_addr = 7, "Hola", "a@example.org"

    assert p.datos_de_cabecera(Normalizado()) == (7, "Hola", "a@example.org")
    assert p.datos_de_cabecera({"uid": 8, "subject": "Qué tal", "from": "b@example.org"}) == (
        8,
        "Qué tal",
        "b@example.org",
    )


class _Base:
    def __init__(self, filas):
        self.filas, self.marcadas, self.consultas = filas, [], []

    async def fetch(self, sql, *args):
        self.consultas.append(sql)
        return [f for f in self.filas if not args or f["owner"] == args[0]]

    async def execute(self, sql, ident):
        self.marcadas.append(ident)


class _Imap:
    cerrada = False

    async def logout(self):
        self.cerrada = True


def _fila(ident, owner):
    return {
        "id": ident,
        "owner": owner,
        "original_folder": "INBOX",
        "snoozed_uid": ident,
        "subject": "",
        "from_addr": "",
    }


def test_solo_se_marca_lo_devuelto_y_lo_indeterminado_se_reintenta(monkeypatch):
    resultados = {1: p.DEVUELTO, 2: p.INDETERMINADO, 3: p.YA_NO_ESTABA}
    conexiones = []

    async def abrir(owner):
        conexiones.append(_Imap())
        return conexiones[-1]

    async def devolver(imap, fila):
        return resultados[fila["id"]]

    monkeypatch.setattr(p, "abrir_buzon_del_dueno", abrir)
    monkeypatch.setattr(p, "devolver", devolver)
    base = _Base([_fila(1, "a@example.org"), _fila(2, "a@example.org"), _fila(3, "b@example.org")])
    resumen = asyncio.run(p.restaurar_vencidos(base))
    assert base.marcadas == [1, 3]
    assert resumen == {p.DEVUELTO: 1, p.INDETERMINADO: 1, p.YA_NO_ESTABA: 1}
    # una conexión por buzón, y todas cerradas
    assert len(conexiones) == 2 and all(c.cerrada for c in conexiones)


def test_sin_usuario_maestro_no_se_marca_nada(monkeypatch):
    async def abrir(owner):
        return None

    monkeypatch.setattr(p, "abrir_buzon_del_dueno", abrir)
    base = _Base([_fila(1, "a@example.org")])
    assert asyncio.run(p.restaurar_vencidos(base)) == {p.SIN_ACCESO: 1}
    assert base.marcadas == []


def test_con_la_sesion_de_la_persona_no_se_abre_ni_se_cierra_otra_conexion(monkeypatch):
    async def abrir(owner):
        raise AssertionError("no debe usarse el usuario maestro")

    async def devolver(imap, fila):
        return p.DEVUELTO

    monkeypatch.setattr(p, "abrir_buzon_del_dueno", abrir)
    monkeypatch.setattr(p, "devolver", devolver)
    base, sesion = _Base([_fila(1, "a@example.org"), _fila(2, "b@example.org")]), _Imap()
    asyncio.run(p.restaurar_vencidos(base, owner="a@example.org", imap=sesion))
    assert base.marcadas == [1] and not sesion.cerrada


def test_el_vencimiento_se_compara_en_utc_y_el_router_ya_no_lee_la_clave_inexistente():
    assert "NOW() AT TIME ZONE 'UTC'" in p._CONSULTA
    router = (Path(p.__file__).resolve().parents[1] / "routers" / "snooze.py").read_text(
        encoding="utf-8"
    )
    assert "user_password:" not in router and "_get_password_from_redis" not in router
    assert "uid_move_message_detallado" in router and "snoozed_uid" in router
