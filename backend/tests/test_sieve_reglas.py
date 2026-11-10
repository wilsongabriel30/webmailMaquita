"""Reglas de correo: generación del Sieve y relectura (ida y vuelta sin pérdidas).

Cubre los defectos C1, C2, A2, A3, A5 y M1 de la revisión independiente del 09/11/2026.
Sin red ni base de datos.
"""

import pytest

from app.sieve import analizador, escapado, generador
from app.sieve.modelos import (
    FilterAction,
    FilterCondition,
    FilterRule,
    VacationSettings,
    bandera_canonica,
)

generar = generador.generate_sieve_script
leer_reglas = analizador.parse_filters_from_script
leer_vacaciones = analizador.parse_vacation_from_script


def regla(nombre, campo, operador, valor, tipo, destino=None):
    return FilterRule(
        name=nombre,
        condition=FilterCondition(field=campo, operator=operador, value=valor),
        action=FilterAction(type=tipo, value=destino),
    )


# ── Escapado ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "texto",
    [
        'Oferta "especial"',
        "ruta C:\\Users\\ana",
        "termina en barra \\",
        'comilla y barra \\" juntas',
        "\\\\ dos barras \\\\",
        "Planificación y evaluación — año 2026 ñ á é í ó ú",
        "x" * 2000,
        "",
    ],
)
def test_escapar_y_desescapar_son_inversos(texto):
    assert escapado.desescapar(escapado.escapar(texto)) == texto.strip()


def test_escapar_dobla_la_barra_antes_que_la_comilla():
    assert escapado.escapar('a\\"b') == 'a\\\\\\"b'
    assert escapado.escapar("fin\\") == "fin\\\\"


def test_sanear_quita_saltos_y_controles():
    assert escapado.sanear("hola\r\n# filter[9]: x\nif true { discard; }") == (
        "hola# filter[9]: xif true { discard; }"
    )


# ── Semántica de la condición (C1) ────────────────────────────────────────────


def test_de_es_exactamente_usa_address():
    script = generar(None, [regla("Jefe", "from", "is", "jefe@example.org", "move", "INBOX.Jefe")])
    assert 'if address :is "From" "jefe@example.org" {' in script
    # «address» es una prueba básica: no se declara en «require» (sievec lo rechaza).
    assert '"address"' not in script.split("\n", 1)[0]


def test_para_coincide_con_patron_usa_address():
    script = generar(None, [regla("Alias", "to", "matches", "*@example.org", "flag")])
    assert 'if address :matches "To" "*@example.org" {' in script


def test_contiene_sigue_usando_header_para_filtrar_por_dominio():
    script = generar(None, [regla("Dominio", "from", "contains", "example.org", "move", "Proveedores")])
    assert 'if header :contains "From" "example.org" {' in script
    assert '"address"' not in script


def test_asunto_siempre_usa_header():
    script = generar(None, [regla("Asunto", "subject", "is", "Factura", "delete")])
    assert 'if header :is "Subject" "Factura" {' in script
    assert '"address"' not in script


# ── Acciones: :create, stop, addflag (A2, A3, M1) ─────────────────────────────


def test_mover_crea_la_carpeta_y_detiene():
    script = generar(None, [regla("R", "from", "contains", "a", "move", "INBOX.Carpeta")])
    assert '    fileinto :create "INBOX.Carpeta";\n    stop;\n}' in script
    assert 'require ["fileinto", "mailbox"];' in script


def test_eliminar_y_reenviar_detienen():
    script = generar(
        None,
        [
            regla("E", "from", "contains", "a", "delete"),
            regla("F", "from", "contains", "b", "forward", "x@example.org"),
        ],
    )
    assert "    discard;\n    stop;\n}" in script
    assert '    redirect "x@example.org";\n    stop;\n}' in script


def test_marcar_anade_la_bandera_y_no_detiene():
    script = generar(None, [regla("M", "from", "contains", "a", "flag")])
    assert '    addflag "\\\\Flagged";\n}' in script
    assert "stop;" not in script
    assert 'require ["imap4flags"];' in script


def test_bandera_canonica_admite_las_formas_del_cliente_antiguo():
    assert bandera_canonica(None) == "\\Flagged"
    assert bandera_canonica("") == "\\Flagged"
    assert bandera_canonica("\\\\Flagged") == "\\Flagged"
    assert bandera_canonica("\\Seen") == "\\Seen"


# ── Ida y vuelta (C2, A5) ─────────────────────────────────────────────────────

CASOS = [
    'Oferta "especial"',
    "con barra \\ en medio",
    "termina en barra \\",
    'mezcla \\" rara \\\\',
    "Planificación — Ñandú á é í ó ú",
    "texto largo " * 60,
]


@pytest.mark.parametrize("valor", CASOS)
@pytest.mark.parametrize("tipo", ["move", "flag", "delete", "forward"])
def test_ida_y_vuelta_de_cada_regla(valor, tipo):
    destino = {
        "move": f"INBOX.{valor}",
        "flag": None,
        "delete": None,
        "forward": "dest@example.org",
    }[tipo]
    original = regla(f"Nombre {valor}", "from", "is", valor, tipo, destino)
    script = generar(None, [original])
    leidas = leer_reglas(script)
    assert len(leidas) == 1
    leida = leidas[0]
    assert leida.name == original.name.strip()
    assert leida.condition.value == valor.strip()
    assert (leida.condition.field, leida.condition.operator) == ("from", "is")
    assert leida.action.type == tipo
    if tipo == "move":
        assert leida.action.value == destino.strip()
    elif tipo == "flag":
        assert leida.action.value == "\\Flagged"
    elif tipo == "forward":
        assert leida.action.value == destino
    # Guardar → releer → guardar: el segundo script es idéntico al primero.
    assert generar(None, leidas) == script
    generador.comprobar_relectura(script, None, [original])


def test_varias_reglas_conservan_el_orden_y_el_total():
    reglas = [
        regla("Uno", "from", "contains", "a@example.org", "move", "A"),
        regla("Dos", "subject", "is", 'Dice "hola"', "flag"),
        regla("Tres", "to", "matches", "*@example.org", "delete"),
        regla("Cuatro", "from", "is", "x\\", "forward", "y@example.org"),
        regla("Cinco", "subject", "contains", "é ñ", "move", "INBOX.Ñ"),
    ]
    script = generar(None, reglas)
    leidas = leer_reglas(script)
    assert [r.name for r in leidas] == ["Uno", "Dos", "Tres", "Cuatro", "Cinco"]
    assert [r.condition.value for r in leidas] == [r.condition.value for r in reglas]
    assert generar(None, leidas) == script


def test_el_nombre_con_salto_de_linea_no_inyecta_codigo():
    peligroso = regla("x\n# filter[9]: y\nif true { discard; }", "from", "contains", "a", "move", "A")
    script = generar(None, [peligroso])
    leidas = leer_reglas(script)
    assert len(leidas) == 1
    assert "if true" not in script.replace(leidas[0].name, "")


# ── Vacaciones con comillas y barras (C2) ─────────────────────────────────────


@pytest.mark.parametrize("texto", CASOS)
def test_vacaciones_con_comillas_sobreviven_a_editar_reglas(texto):
    vac = VacationSettings(enabled=True, subject=f'Fuera "oficina" {texto}', body=texto)
    script = generar(vac, [regla("R", "from", "contains", "a", "move", "A")])
    leida = leer_vacaciones(script)
    assert leida.enabled is True
    assert leida.subject == vac.subject.strip()
    assert leida.body == texto.strip()
    # Editar reglas regenera el script a partir de lo releído: la respuesta sigue encendida.
    otra_vez = generar(leida, leer_reglas(script) + [regla("S", "to", "is", "b@example.org", "flag")])
    assert leer_vacaciones(otra_vez).enabled is True
    assert leer_vacaciones(otra_vez).body == texto.strip()


def test_vacaciones_con_fechas():
    vac = VacationSettings(enabled=True, subject="S", body="B", start_date="2026-11-10", end_date="2026-11-20")
    script = generar(vac, [])
    assert 'require ["date", "relational", "vacation"];' in script
    leida = leer_vacaciones(script)
    assert (leida.start_date, leida.end_date) == ("2026-11-10", "2026-11-20")


def test_vacaciones_apagadas():
    script = generar(VacationSettings(enabled=False), [])
    assert leer_vacaciones(script).enabled is False
    assert "require" not in script


# ── Scripts antiguos (producción antes del 09/11/2026) ────────────────────────

SCRIPT_ANTIGUO = '''require ["fileinto", "imap4flags"];

# --- VACATION ---
# vacation disabled

# --- FILTERS ---
# filter[0]: Jefe
if header :is "From" "jefe@example.org" {
    fileinto "INBOX.Jefe";
}
# filter[1]: Importante
if header :contains "Subject" "urgente" {
    setflag "\\\\Flagged";
}
# filter[2]: Basura
if header :contains "From" "spam.example" {
    discard;
}
# filter[3]: Copia
if header :is "To" "alias@example.org" {
    redirect "otro@example.org";
}

# --- REGLAS TRAIDAS DE ZIMBRA (no se editan desde el webmail) ---
if allof (address :all :contains "from" "x@y.z", header :contains "Cc" "z") { fileinto "Z"; stop; }
# --- FIN REGLAS TRAIDAS DE ZIMBRA ---
'''


def test_script_antiguo_se_lee_y_se_regenera_con_address():
    leidas = leer_reglas(SCRIPT_ANTIGUO)
    assert [(r.condition.field, r.condition.operator, r.action.type) for r in leidas] == [
        ("from", "is", "move"),
        ("subject", "contains", "flag"),
        ("from", "contains", "delete"),
        ("to", "is", "forward"),
    ]
    assert leidas[0].action.value == "INBOX.Jefe"
    assert leidas[1].action.value == "\\Flagged"
    assert leidas[3].action.value == "otro@example.org"
    nuevo = generar(None, leidas)
    assert 'if address :is "From" "jefe@example.org" {' in nuevo
    assert 'if address :is "To" "alias@example.org" {' in nuevo
    assert 'if header :contains "Subject" "urgente" {' in nuevo
    assert 'fileinto :create "INBOX.Jefe";' in nuevo
    assert 'addflag "\\\\Flagged";' in nuevo
    assert "setflag" not in nuevo
    assert nuevo.startswith('require ["fileinto", "imap4flags", "mailbox"];')
    # Y lo regenerado se vuelve a leer igual (las reglas de Zimbra no cuentan como propias).
    assert leer_reglas(nuevo) == leidas


def test_comprobar_relectura_detecta_perdidas():
    reglas = [regla("R", "from", "contains", "a", "move", "A")]
    script = generar(None, reglas)
    with pytest.raises(ValueError):
        generador.comprobar_relectura(script.replace("# filter[0]", "# roto"), None, reglas)
    vac = VacationSettings(enabled=True, subject="S", body="B")
    with pytest.raises(ValueError):
        generador.comprobar_relectura(generar(None, reglas), vac, reglas)
    generador.comprobar_relectura(generar(vac, reglas), vac, reglas)
