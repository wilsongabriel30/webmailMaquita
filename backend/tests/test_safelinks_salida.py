"""Al enviar, los enlaces de nuestra pasarela vuelven a su destino real; los de la casa no se envuelven."""

from __future__ import annotations

import pytest

from app.safelinks import propios, rewriter, salida

BASE = "https://correo.example.org"
DRIVE = "https://drive.example.org/almacen-s/abc123?x=1&y=2"
FUERA = "https://tienda.example.net/oferta?a=1&b=2"


@pytest.fixture(autouse=True)
def _casa(monkeypatch):
    monkeypatch.setattr(
        propios, "dominios_de_la_casa", lambda: frozenset({"example.org"})
    )


def _envuelto(url: str) -> str:
    ub = rewriter.encode_url(url)
    return f"{BASE}/api/safelink?u={ub}&s={rewriter.sign(ub)}"


def test_html_el_enlace_envuelto_sale_con_su_destino_real():
    html = f'<p>Vea <a href="{_envuelto(FUERA).replace("&", "&amp;")}">el documento</a></p>'
    nuevo, n = salida.desenvolver_html(html)
    assert n == 1 and "/api/safelink" not in nuevo
    assert 'href="https://tienda.example.net/oferta?a=1&amp;b=2"' in nuevo


def test_html_tambien_cuando_la_envoltura_es_el_texto_visible():
    env = _envuelto(DRIVE).replace("&", "&amp;")
    nuevo, n = salida.desenvolver_html(f'<a href="{env}">{env}</a>')
    assert n == 2 and "/api/safelink" not in nuevo


def test_texto_plano():
    nuevo, n = salida.desenvolver_texto(f"Abra {_envuelto(DRIVE)} y avise.")
    assert n == 1 and nuevo == f"Abra {DRIVE} y avise."


def test_envoltura_doble_llega_al_destino_final():
    nuevo, n = salida.desenvolver_texto(_envuelto(_envuelto(FUERA)))
    assert n == 1 and nuevo == FUERA


def test_un_safelink_de_otro_servidor_no_se_toca():
    ajeno = "https://correo.otra-empresa.example.net/api/safelink?u=aHR0cHM6Ly9hLmI&s=x"
    assert salida.desenvolver_texto(ajeno) == (ajeno, 0)
    assert salida.desenvolver_html(f'<a href="{ajeno}">x</a>')[1] == 0


def test_sin_enlaces_envueltos_no_cambia_nada():
    assert salida.desenvolver_html("<p>Hola</p>") == ("<p>Hola</p>", 0)
    assert salida.desenvolver_texto("") == ("", 0) and salida.desenvolver_html(
        None
    ) == (None, 0)


def test_envoltura_ilegible_se_deja_como_esta():
    roto = f"{BASE}/api/safelink?s=sin-destino"
    assert salida.desenvolver_texto(roto) == (roto, 0)


def test_los_enlaces_de_la_casa_no_se_envuelven():
    assert rewriter.gateway_link(DRIVE.replace("&", "&amp;"), BASE) == DRIVE
    assert "/api/safelink?u=" in rewriter.gateway_link(FUERA, BASE)


def test_una_envoltura_antigua_de_un_enlace_de_la_casa_se_muestra_directa():
    assert rewriter.gateway_link(_envuelto(DRIVE).replace("&", "&amp;"), BASE) == DRIVE
    # la de un enlace externo se conserva: sigue protegiendo a quien lee
    assert rewriter.gateway_link(_envuelto(FUERA), BASE) == _envuelto(FUERA)


def test_el_mensaje_que_sale_no_lleva_la_pasarela():
    from app.mail.clients.smtp_client import OutgoingEmail, build_mime_message

    env = _envuelto(DRIVE)
    correo = OutgoingEmail(
        from_addr="yo@example.org",
        to=["financista@example.net"],
        subject="Documentos",
        text_body=f"Enlace: {env}",
        html_body=f'<p><a href="{env.replace("&", "&amp;")}">Documentos</a></p>',
    )
    crudo = build_mime_message(correo)
    cuerpos = "".join(
        p.get_payload(decode=True).decode("utf-8")
        for p in crudo.walk()
        if not p.is_multipart()
    )
    assert (
        "/api/safelink" not in cuerpos
        and "drive.example.org/almacen-s/abc123" in cuerpos
    )
    assert correo.text_body == f"Enlace: {env}"  # el objeto de quien llama no se altera
