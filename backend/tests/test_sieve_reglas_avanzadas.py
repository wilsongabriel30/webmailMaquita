"""Reglas de correo avanzadas (10/11/2026): varias condiciones y acciones, negaciones, cuerpo,
tamaño, encabezado a elegir, expresiones regulares, copia, leído, reenvío de copia, regla
desactivada. Ida y vuelta por el script sin pérdidas y compatibilidad con la forma antigua.
Sin red ni base de datos.
"""

import shutil
import subprocess

import pytest
from pydantic import ValidationError

from app.sieve import analizador, generador
from app.sieve.modelos import FilterAction, FilterCondition, FilterRule

generar = generador.generate_sieve_script
leer = analizador.parse_filters_from_script


def cond(field, operator, value="", header=None):
    return FilterCondition(field=field, operator=operator, value=value, header=header)


def acc(tipo, valor=None):
    return FilterAction(type=tipo, value=valor)


REGLA_COMPLETA = FilterRule(
    name="Proveedores: facturas grandes",
    match="anyof",
    conditions=[
        cond("from", "contains", "@example.org"),
        cond("recipients", "is", "compras@example.com"),
        cond("subject", "regex", "^(factura|invoice)"),
        cond("body", "not_contains", "borrador"),
        cond("size", "over", "5000"),
        cond("header", "exists", header="X-Priority"),
        cond("list", "not_is", "boletin.example.org"),
    ],
    actions=[
        acc("copy", "Proveedores.Facturas"),
        acc("read"),
        acc("flag", "\\Flagged"),
        acc("forward_copy", "contabilidad@example.com"),
    ],
    stop=False,
    enabled=True,
)


# ── Generación ────────────────────────────────────────────────────────────────


def test_varias_condiciones_con_anyof_y_varias_acciones():
    script = generar(None, [REGLA_COMPLETA])
    assert "if anyof (" in script
    assert 'header :contains "From" "@example.org"' in script
    assert 'address :is ["To", "Cc"] "compras@example.com"' in script
    assert 'header :regex "Subject" "^(factura|invoice)"' in script
    assert 'not body :contains "borrador"' in script
    assert "size :over 5000K" in script
    assert 'exists "X-Priority"' in script
    assert (
        'not address :is "List-Id" "boletin.example.org"' not in script
    )  # list va por header
    assert 'not header :is "List-Id" "boletin.example.org"' in script
    assert 'fileinto :copy :create "Proveedores.Facturas";' in script
    assert 'addflag "\\\\Seen";' in script
    assert 'addflag "\\\\Flagged";' in script
    assert 'redirect :copy "contabilidad@example.com";' in script
    assert "stop;" not in script


def test_require_declara_solo_lo_que_se_usa():
    script = generar(None, [REGLA_COMPLETA])
    primera = script.splitlines()[0]
    assert (
        primera
        == 'require ["body", "copy", "fileinto", "imap4flags", "mailbox", "regex"];'
    )
    sencilla = FilterRule(
        name="x", conditions=[cond("subject", "contains", "a")], actions=[acc("delete")]
    )
    assert not generar(None, [sencilla]).startswith("require")


def test_regla_desactivada_nunca_se_cumple_pero_queda_en_el_script():
    regla = FilterRule(
        name="Apagada",
        conditions=[cond("from", "contains", "a@example.org")],
        actions=[acc("move", "Carpeta")],
        enabled=False,
    )
    script = generar(None, [regla])
    assert 'if allof (false, header :contains "From" "a@example.org") {' in script
    leida = leer(script)[0]
    assert leida.enabled is False
    assert leida.match == "allof"
    assert len(leida.conditions) == 1


def test_detener_por_defecto_salvo_que_solo_marque():
    mueve = FilterRule(
        name="m",
        conditions=[cond("subject", "contains", "a")],
        actions=[acc("move", "X")],
    )
    marca = FilterRule(
        name="f",
        conditions=[cond("subject", "contains", "a")],
        actions=[acc("flag"), acc("read")],
    )
    assert mueve.stop is True and marca.stop is False
    script = generar(None, [mueve, marca])
    assert script.count("stop;") == 1


def test_sievec_compila_el_script_completo(tmp_path):
    sievec = shutil.which("sievec")
    if not sievec:
        pytest.skip("sievec no está instalado")
    script = generar(
        None,
        [
            REGLA_COMPLETA,
            FilterRule(
                name="Apagada",
                match="anyof",
                enabled=False,
                conditions=[
                    cond("to", "matches", "*@example.net"),
                    cond("cc", "not_exists"),
                ],
                actions=[acc("forward", "x@example.org"), acc("delete")],
            ),
        ],
    )
    origen = tmp_path / "prueba.sieve"
    origen.write_text(script, encoding="utf-8")
    r = subprocess.run(
        [sievec, str(origen), str(tmp_path / "prueba.svbin")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr


# ── Relectura ─────────────────────────────────────────────────────────────────


def test_ida_y_vuelta_de_la_regla_completa():
    script = generar(None, [REGLA_COMPLETA])
    (leida,) = leer(script)
    assert leida == generador._normalizar(REGLA_COMPLETA)
    assert [c.field for c in leida.conditions] == [
        c.field for c in REGLA_COMPLETA.conditions
    ]
    assert [a.type for a in leida.actions] == ["copy", "read", "flag", "forward_copy"]
    generador.comprobar_relectura(script, None, [REGLA_COMPLETA])


@pytest.mark.parametrize(
    "condicion",
    [
        cond("from", "not_contains", "a, b"),  # coma dentro de la cadena
        cond("subject", "is", 'con "comillas" y \\ barra'),
        cond("header", "not_regex", "^.*$", header="Reply-To"),
        cond("size", "under", "1"),
        cond("recipients", "not_exists"),
        cond("body", "regex", "urgente|inmediato"),
    ],
)
def test_ida_y_vuelta_de_cada_condicion(condicion):
    regla = FilterRule(name="r", conditions=[condicion], actions=[acc("move", "X")])
    (leida,) = leer(generar(None, [regla]))
    assert leida.conditions[0] == condicion
    generador.comprobar_relectura(generar(None, [regla]), None, [regla])


def test_tamano_en_bytes_o_megas_de_otro_cliente_se_convierte_a_kb():
    script = (
        "# filter[0]: a\nif size :over 2M {\n    discard;\n}\n"
        "# filter[1]: b\nif not size :under 3000 {\n    discard;\n}\n"
    )
    a, b = leer(script)
    assert a.conditions[0] == cond("size", "over", "2048")
    # «not size :under» equivale a «size :over»; 3000 bytes suben a 3 KB
    assert b.conditions[0] == cond("size", "over", "3")


def test_script_antiguo_de_una_condicion_se_lee_en_la_forma_nueva():
    script = (
        '# filter[0]: Antigua\nif header :is "From" "jefe@example.org" {\n'
        '    fileinto "Jefe";\n    stop;\n}\n'
    )
    (leida,) = leer(script)
    assert leida.match == "allof"
    assert leida.conditions == [cond("from", "is", "jefe@example.org")]
    assert leida.actions == [acc("move", "Jefe")]
    assert leida.stop is True and leida.enabled is True
    # Y la forma antigua sigue disponible para el cliente que la lea
    assert leida.condition == leida.conditions[0] and leida.action == leida.actions[0]


def test_lo_que_no_se_entiende_se_omite_sin_romper_las_demas():
    script = (
        '# filter[0]: rara\nif allof (header :contains "From" "a", anyof (true, false)) {\n    discard;\n}\n'
        '# filter[1]: buena\nif header :contains "From" "b" {\n    discard;\n}\n'
    )
    reglas = leer(script)
    assert [r.name for r in reglas] == ["buena"]


# ── Compatibilidad y validación del modelo ────────────────────────────────────


def test_forma_antigua_condition_action_se_acepta():
    regla = FilterRule(
        name="vieja",
        condition=cond("from", "contains", "x"),
        action=acc("flag", "\\\\Flagged"),
    )
    assert len(regla.conditions) == 1 and len(regla.actions) == 1
    assert regla.stop is False


@pytest.mark.parametrize(
    "campo, operador, valor, header",
    [
        ("size", "contains", "5", None),  # operador que no es de tamaño
        ("size", "over", "cinco", None),  # tamaño no numérico
        ("body", "is", "x", None),  # el cuerpo no admite «es exactamente»
        ("header", "contains", "x", "Nombre con espacios"),
        ("header", "contains", "x", None),  # sin nombre de encabezado
        ("from", "contains", "   ", None),  # sin valor
    ],
)
def test_condiciones_invalidas_se_rechazan(campo, operador, valor, header):
    with pytest.raises(ValidationError):
        FilterCondition(field=campo, operator=operador, value=valor, header=header)


def test_regla_sin_condiciones_o_sin_acciones_se_rechaza():
    with pytest.raises(ValidationError):
        FilterRule(name="x", conditions=[], actions=[acc("delete")])
    with pytest.raises(ValidationError):
        FilterRule(name="x", conditions=[cond("subject", "contains", "a")], actions=[])
