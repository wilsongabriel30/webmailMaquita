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


FILAS = [
    ("Fernando Pacheco", "fpacheco@example.org"),
    ("Fernanda Pachano", "fernanda@example.org"),
    ("Hernando Pachacama", "hpachacama@example.org"),
]
VOC_FRASES = qd.vocabulario(FILAS)
GENTE = qd.personas(FILAS)


def test_frase_de_varias_palabras_se_corrige_entera():
    assert qd.sugerir("fernado pachco", VOC_FRASES, GENTE)[0] == "fernando pacheco"
    assert qd.sugerir("pachecco fernando", VOC_FRASES, GENTE) == ["pacheco fernando"]


def test_primero_el_nombre_de_una_misma_persona():
    """«fernanda pachco»: Fernanda es Pachano; «fernanda pacheco» no es nadie."""
    assert qd.sugerir("fernanda pachco", VOC_FRASES, GENTE) == [
        "fernanda pachano",
        "fernanda pacheco",
    ]
    # Sin saber quién es quién, manda el parecido con lo escrito.
    assert qd.sugerir("fernanda pachco", VOC_FRASES)[0] == "fernanda pacheco"


def test_las_comillas_y_los_signos_se_conservan():
    assert qd.sugerir('"fernado pacheco"', VOC_FRASES, GENTE)[0] == '"fernando pacheco"'
    assert qd.sugerir("fernado, factura", VOC_FRASES, GENTE)[0] == "fernando, factura"


def test_frase_bien_escrita_o_demasiado_larga_no_propone_nada():
    assert qd.sugerir("fernando pacheco", VOC_FRASES, GENTE) == []
    assert qd.sugerir("a b c d e f fernado", VOC_FRASES, GENTE) == []
    assert len(qd.sugerir("fernado pachco", VOC_FRASES, GENTE)) <= qd.MAX_SUGERENCIAS
