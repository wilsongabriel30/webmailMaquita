"""Cliente del servidor de túneles (Fase B) con un ejecutor simulado: ninguna prueba abre una conexión."""

import asyncio
import os

import pytest

from app.flota import tunel_claves
from app.flota.broker import Broker, ErrorBroker, etiqueta_de

HOST_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEjemploDeClaveDeHostParaLasPruebas00000000000"
)


class Ejecutor:
    """Apunta cada orden y contesta lo preparado para la acción (última palabra clave de la orden)."""

    def __init__(self, respuestas=None):
        self.ordenes: list[list[str]] = []
        self.tiempos: list[float] = []
        self.conocidos: list[str] = []
        self.respuestas = respuestas or {}

    async def __call__(self, orden, tiempo_s):
        self.ordenes.append(orden)
        self.tiempos.append(tiempo_s)
        ruta = next(o for o in orden if o.startswith("UserKnownHostsFile=")).split(
            "=", 1
        )[1]
        with open(ruta, encoding="ascii") as f:
            self.conocidos.append(f.read())
        respuesta = self.respuestas.get(orden[-1].split()[0], (0, "", ""))
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    @property
    def acciones(self):
        return [o[-1] for o in self.ordenes]


def broker(ejecutor, **cambios):
    datos = {
        "host": "tuneles.interno.example",
        "clave": "/ruta/de/ejemplo/gestion.key",
        "host_key": HOST_KEY,
        "tiempo_s": 7,
        "ejecutor": ejecutor,
    }
    return Broker(**{**datos, **cambios})


def correr(tarea):
    return asyncio.run(tarea)


def test_cada_llamada_fija_la_clave_de_host_y_tiene_tiempo_maximo():
    ej = Ejecutor({"puerto-libre": (0, "22007\n", "")})
    assert correr(broker(ej).puerto_libre()) == 22007
    orden = ej.ordenes[0]
    assert (
        orden[0] == "ssh"
        and orden[-2] == "flota-gestor@tuneles.interno.example"
        and orden[-1] == "puerto-libre"
    )
    opciones = [orden[i + 1] for i, o in enumerate(orden) if o == "-o"]
    for esperada in (
        "BatchMode=yes",
        "StrictHostKeyChecking=yes",
        "IdentitiesOnly=yes",
        "GlobalKnownHostsFile=/dev/null",
        "ConnectTimeout=7",
    ):
        assert esperada in opciones
    assert orden[orden.index("-i") + 1] == "/ruta/de/ejemplo/gestion.key"
    assert ej.tiempos == [7.0]
    assert ej.conocidos == [f"tuneles.interno.example {HOST_KEY}\n"]
    ruta = next(o for o in opciones if o.startswith("UserKnownHostsFile=")).split(
        "=", 1
    )[1]
    assert not os.path.exists(ruta)  # el fichero temporal no sobrevive a la llamada


def test_puerto_distinto_del_22_en_la_clave_de_host_fijada():
    ej = Ejecutor({"listar": (0, "", "")})
    correr(broker(ej, puerto=2222).listar())
    assert ej.conocidos == [f"[tuneles.interno.example]:2222 {HOST_KEY}\n"]
    assert ej.ordenes[0][ej.ordenes[0].index("-p") + 1] == "2222"


def test_listar():
    ej = Ejecutor(
        {"listar": (0, "22001\tEQUIPO-A-11111111\n\n22005\tEQUIPO-B-22222222\n", "")}
    )
    assert correr(broker(ej).listar()) == {
        22001: "EQUIPO-A-11111111",
        22005: "EQUIPO-B-22222222",
    }


def test_alta_y_baja():
    _, publica, _ = tunel_claves.generar()
    ej = Ejecutor()
    b = broker(ej)
    correr(b.alta("EQUIPO-A-11111111", 22001, publica + " comentario que se descarta"))
    correr(b.baja("EQUIPO-A-11111111"))
    assert ej.acciones == [
        f"alta EQUIPO-A-11111111 22001 {publica}",
        "baja EQUIPO-A-11111111",
    ]


@pytest.mark.parametrize(
    "etiqueta", ["", "con espacio", "a;id", "$(id)", "-o", "a\nb", "x" * 80]
)
def test_etiquetas_peligrosas_no_llegan_al_servidor(etiqueta):
    _, publica, _ = tunel_claves.generar()
    ej = Ejecutor()
    for llamada in (
        broker(ej).baja(etiqueta),
        broker(ej).alta(etiqueta, 22001, publica),
    ):
        with pytest.raises(ErrorBroker):
            correr(llamada)
    assert ej.ordenes == []


def test_alta_rechaza_puerto_fuera_de_rango_y_clave_que_no_es_publica_ed25519():
    privada, publica, _ = tunel_claves.generar()
    ej = Ejecutor()
    for puerto, clave in (
        (22000, publica),
        (23000, publica),
        (22001, "ssh-rsa AAAA"),
        (22001, privada),
        (22001, publica.split()[1] + "; id"),
    ):
        with pytest.raises(ErrorBroker):
            correr(broker(ej).alta("EQUIPO", puerto, clave))
    assert ej.ordenes == []


def test_errores_del_servidor_de_tuneles():
    ej = Ejecutor(
        {
            "puerto-libre": (0, "no-es-un-puerto\n", ""),
            "listar": (0, "80\tX\n", ""),
            "baja": (255, "", "aviso\nPermission denied (publickey).\n"),
            "alta": asyncio.TimeoutError(),
        }
    )
    _, publica, _ = tunel_claves.generar()
    b = broker(ej)
    for llamada in (b.puerto_libre(), b.listar()):
        with pytest.raises(ErrorBroker):
            correr(llamada)
    with pytest.raises(ErrorBroker) as e:
        correr(b.baja("EQUIPO"))
    assert "Permission denied" in str(e.value) and "baja" in str(e.value)
    with pytest.raises(ErrorBroker) as e:
        correr(b.alta("EQUIPO", 22001, publica))
    assert "no respondió en 7 s" in str(e.value)


def test_sin_configurar_no_se_puede_usar(monkeypatch):
    for nombre in ("FLOTA_BROKER_HOST", "FLOTA_BROKER_CLAVE", "FLOTA_BROKER_HOST_KEY"):
        monkeypatch.delenv(nombre, raising=False)
    with pytest.raises(ErrorBroker):
        Broker.desde_entorno()
    with pytest.raises(ErrorBroker):
        broker(Ejecutor(), host_key="cualquier cosa")
    with pytest.raises(ErrorBroker):
        broker(Ejecutor(), host="-oProxyCommand=id")


def test_desde_el_entorno(monkeypatch):
    monkeypatch.setenv("FLOTA_BROKER_HOST", "tuneles.interno.example")
    monkeypatch.setenv("FLOTA_BROKER_CLAVE", "/ruta/de/ejemplo/gestion.key")
    monkeypatch.setenv("FLOTA_BROKER_HOST_KEY", HOST_KEY)
    monkeypatch.setenv("FLOTA_BROKER_TIEMPO_S", "4")
    b = Broker.desde_entorno(Ejecutor())
    assert (b.host, b.puerto, b.usuario, b.tiempo_s) == (
        "tuneles.interno.example",
        22,
        "flota-gestor",
        4.0,
    )


def test_el_ejecutor_real_corta_al_pasarse_de_tiempo():
    from app.flota.broker import ejecutar_ssh

    with pytest.raises(asyncio.TimeoutError):
        correr(ejecutar_ssh(["sleep", "5"], 0.2))
    assert correr(ejecutar_ssh(["printf", "22001"], 5)) == (0, "22001", "")


def test_etiqueta_de_un_equipo():
    assert (
        etiqueta_de("PORTÁTIL de Ana", "11111111-2222-4333-8444-555555555555")
        == "PORT-TIL-de-Ana-11111111"
    )
    assert etiqueta_de("", "11111111-2222-4333-8444-555555555555") == "equipo-11111111"
