"""COPYUID (RFC 4315): del texto de la respuesta al mapa {uid origen: uid destino}."""

from app.mail.clients.imap_copyuid import expandir_conjunto, mapa_copyuid


def test_expandir_conjunto_con_rangos_y_listas():
    assert expandir_conjunto("1,3:5,9") == [1, 3, 4, 5, 9]
    assert expandir_conjunto("5:3") == [3, 4, 5]
    assert expandir_conjunto("") == []


def test_mapa_copyuid_de_respuesta_dovecot():
    lineas = [b"OK [COPYUID 1779177635 5,7:8 1095:1097] Moved UIDs."]
    assert mapa_copyuid(lineas) == {5: 1095, 7: 1096, 8: 1097}


def test_mapa_copyuid_acepta_str_y_minusculas():
    assert mapa_copyuid(["* OK [copyuid 1 12 40] ok"]) == {12: 40}


def test_mapa_copyuid_sin_copyuid_es_none():
    assert mapa_copyuid([b"MOVE completed", b"* 3 EXPUNGE"]) is None
    assert mapa_copyuid(None) is None


def test_mapa_copyuid_tamanos_distintos_se_descarta():
    assert mapa_copyuid([b"OK [COPYUID 1 1:3 10:11] x"]) is None
