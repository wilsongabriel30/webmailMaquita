import asyncio
import threading
import time

from app.mail.services.consulta_en_paralelo import en_paralelo


def test_mismo_orden_y_lista_vacia():
    assert asyncio.run(en_paralelo(lambda x: x * 2, [3, 1, 2])) == [6, 2, 4]
    assert asyncio.run(en_paralelo(lambda x: x, [])) == []


def test_van_a_la_vez_pero_sin_pasar_del_tope():
    activas = 0
    maximo_visto = 0
    candado = threading.Lock()

    def lenta(x):
        nonlocal activas, maximo_visto
        with candado:
            activas += 1
            maximo_visto = max(maximo_visto, activas)
        time.sleep(0.05)
        with candado:
            activas -= 1
        return x

    inicio = time.monotonic()
    assert asyncio.run(en_paralelo(lenta, list(range(12)), maximo=4)) == list(range(12))
    duracion = time.monotonic() - inicio
    assert maximo_visto <= 4
    assert maximo_visto > 1
    assert duracion < 0.05 * 12  # más rápido que una tras otra
