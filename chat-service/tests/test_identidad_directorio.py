# -*- coding: utf-8 -*-
"""Un alta o una baja de buzón no puede cambiar de dueño una conversación."""
from identidad_directorio import asignar_ids


def fila(correo, id_origen=None, usuario=None):
    return (id_origen, usuario or correo.split("@")[0], correo, "external-idp",
            usuario or correo.split("@")[0], True, None)


def test_quien_ya_esta_conserva_su_id():
    filas = [fila("ana@ejemplo.org"), fila("luis@ejemplo.org")]
    salida, nuevos = asignar_ids(filas, {"ana@ejemplo.org": 7, "luis@ejemplo.org": 3}, 100)
    assert [f[0] for f in salida] == [7, 3]
    assert nuevos == 0


def test_un_alta_que_ordena_primero_no_desplaza_a_nadie():
    """El caso que reportaron: `aaa@` entra y antes se llevaba por delante todos los ids."""
    conocidos = {"demo@ejemplo.org": 1, "dos@ejemplo.org": 2, "nav@ejemplo.org": 3}
    filas = [fila("aaa@ejemplo.org"), fila("demo@ejemplo.org"),
             fila("dos@ejemplo.org"), fila("nav@ejemplo.org")]
    salida, nuevos = asignar_ids(filas, conocidos, 4)
    por_correo = {f[2]: f[0] for f in salida}
    assert por_correo["demo@ejemplo.org"] == 1
    assert por_correo["dos@ejemplo.org"] == 2
    assert por_correo["nav@ejemplo.org"] == 3
    assert por_correo["aaa@ejemplo.org"] == 4      # el nuevo va al final, no al principio
    assert nuevos == 1


def test_una_baja_tampoco_mueve_a_los_demas():
    conocidos = {"ana@ejemplo.org": 1, "luis@ejemplo.org": 2, "eva@ejemplo.org": 3}
    salida, _ = asignar_ids([fila("ana@ejemplo.org"), fila("eva@ejemplo.org")], conocidos, 4)
    assert {f[2]: f[0] for f in salida} == {"ana@ejemplo.org": 1, "eva@ejemplo.org": 3}


def test_el_correo_manda_aunque_cambie_el_nombre():
    conocidos = {"ana@ejemplo.org": 5}
    salida, _ = asignar_ids([fila("ana@ejemplo.org", usuario="ana.perez")], conocidos, 9)
    assert salida[0][0] == 5


def test_mayusculas_en_el_correo_no_crean_otra_persona():
    salida, nuevos = asignar_ids([fila("Ana@Ejemplo.org")], {"ana@ejemplo.org": 5}, 9)
    assert salida[0][0] == 5 and nuevos == 0


def test_fuente_con_ids_propios_los_respeta():
    salida, nuevos = asignar_ids([fila("ana@ejemplo.org", id_origen=42)], {}, 1)
    assert salida[0][0] == 42 and nuevos == 1 - 1


def test_varias_altas_reciben_ids_distintos():
    salida, nuevos = asignar_ids([fila("a@e.org"), fila("b@e.org"), fila("c@e.org")], {}, 10)
    assert [f[0] for f in salida] == [10, 11, 12] and nuevos == 3


def test_repetir_la_sincronizacion_no_cambia_nada():
    filas = [fila("a@e.org"), fila("b@e.org")]
    primera, _ = asignar_ids(filas, {}, 1)
    conocidos = {f[2]: f[0] for f in primera}
    segunda, nuevos = asignar_ids(filas, conocidos, 3)
    assert [f[0] for f in primera] == [f[0] for f in segunda]
    assert nuevos == 0
