"""«¿Quiso decir…?»: nombres mal escritos en la búsqueda."""

from app.mail.services import quiso_decir as qd

VOC = qd.vocabulario(
    [
        ("Thiago Andrade", "thiago.andrade@example.org"),
        ("Michelle Lounge", "mlounge@example.org"),
        ("María José Pérez", "mjperez@example.org"),
        (None, "contabilidadpuertoballesta@example.org"),
    ]
)


def test_corrige_un_nombre_mal_escrito():
    assert qd.sugerir("tiagho", VOC) == ["thiago"]
    assert qd.sugerir("loungg", VOC)[0] == "lounge"
    assert qd.sugerir("michele", VOC)[0] == "michelle"


def test_devuelve_el_nombre_con_su_tilde():
    assert qd.sugerir("mria", VOC)[0] == "maría"


def test_lo_bien_escrito_no_se_toca():
    assert qd.sugerir("thiago", VOC) == []
    assert qd.sugerir("maria perez", VOC) == [], "sin tildes también está bien escrito"
    assert (
        qd.sugerir("contabilidadpuert", VOC) == []
    ), "el principio de un nombre no es un error"


def test_solo_cambia_la_palabra_mal_escrita():
    assert qd.sugerir("factura tiagho 2026", VOC) == ["factura thiago 2026"]


def test_operadores_direcciones_y_numeros_se_respetan():
    assert qd.sugerir("de:tiagho", VOC) == []
    assert qd.sugerir("tiagho@example.org", VOC) == []
    assert qd.sugerir("5045694709", VOC) == []


def test_sin_vocabulario_o_sin_parecidos_no_propone_nada():
    assert qd.sugerir("tiagho", {}) == []
    assert qd.sugerir("xyzxyzxyz", VOC) == []
    assert qd.sugerir("", VOC) == []


def test_no_propone_palabras_que_empiezan_distinto():
    voc = qd.vocabulario([("Ana Ibarra Conforme", "aibarra@example.org")])
    assert qd.sugerir("barbra", voc) == [] and qd.sugerir("informe", voc) == []
    assert qd.sugerir("ibara", voc) == ["ibarra"]
