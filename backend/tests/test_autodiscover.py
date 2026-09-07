"""Autodiscover: IMAP/SMTP para Outlook clásico, ActiveSync (XML mobilesync) y JSON v2 para el nuevo Outlook."""

import os

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

os.environ["AUTODISCOVER_MAIL_HOST"] = "mail.prueba.test"
from app import autodiscover_router as ad  # noqa: E402

pytestmark = pytest.mark.asyncio

XML_OUTLOOK = (
    '<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">'
    "<Request><EMailAddress>Ana@Prueba.test</EMailAddress>"
    "<AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>"
    "</Request></Autodiscover>"
)
XML_MOBILE = XML_OUTLOOK.replace(
    "outlook/responseschema/2006a", "mobilesync/responseschema/2006"
)


def _app():
    app = FastAPI()
    app.include_router(ad.router)
    return app


async def test_xml_outlook_e_imap_smtp():
    async with AsyncClient(
        transport=ASGITransport(app=_app()), base_url="https://t"
    ) as c:
        r = await c.post(
            "/autodiscover/autodiscover.xml",
            content=XML_OUTLOOK,
            headers={"content-type": "text/xml"},
        )
    assert (
        r.status_code == 200
        and "<Type>IMAP</Type>" in r.text
        and "<Type>SMTP</Type>" in r.text
    )
    assert (
        "<LoginName>ana@prueba.test</LoginName>" in r.text
        and "<Server>mail.prueba.test</Server>" in r.text
    )
    assert "MobileSync" not in r.text


async def test_xml_mobilesync_devuelve_activesync():
    async with AsyncClient(
        transport=ASGITransport(app=_app()), base_url="https://t"
    ) as c:
        r = await c.post(
            "/Autodiscover/Autodiscover.xml",
            content=XML_MOBILE,
            headers={"content-type": "text/xml"},
        )
    assert r.status_code == 200 and ad.ESQUEMA_MOBILESYNC in r.text
    assert "<Type>MobileSync</Type>" in r.text
    assert "<Url>https://mail.prueba.test/Microsoft-Server-ActiveSync</Url>" in r.text
    assert "<EMailAddress>ana@prueba.test</EMailAddress>" in r.text


async def test_json_v2_para_el_nuevo_outlook():
    async with AsyncClient(
        transport=ASGITransport(app=_app()), base_url="https://t"
    ) as c:
        r = await c.get(
            "/autodiscover/autodiscover.json/v1.0/ana@prueba.test?Protocol=ActiveSync"
        )
        assert r.status_code == 200 and r.json() == {
            "Protocol": "ActiveSync",
            "Url": "https://mail.prueba.test/Microsoft-Server-ActiveSync",
        }
        r = await c.get(
            "/autodiscover/autodiscover.json?Email=ana@prueba.test&Protocol=AutodiscoverV1"
        )
        assert r.status_code == 200 and r.json()["Url"].endswith(
            "/autodiscover/autodiscover.xml"
        )
        r = await c.get(
            "/autodiscover/autodiscover.json?Email=ana@prueba.test&Protocol=Ews"
        )
        assert r.status_code == 400 and r.json()["ErrorCode"] == "ProtocolNotSupported"
        r = await c.get(
            "/autodiscover/autodiscover.json?Email=no-es-correo&Protocol=ActiveSync"
        )
        assert r.status_code == 400


async def test_correo_invalido_y_escape():
    async with AsyncClient(
        transport=ASGITransport(app=_app()), base_url="https://t"
    ) as c:
        r = await c.post(
            "/autodiscover/autodiscover.xml",
            content="<x><EMailAddress>malo</EMailAddress></x>",
        )
        assert r.status_code == 400
        r = await c.post(
            "/autodiscover/autodiscover.xml",
            content=XML_MOBILE.replace("Ana@Prueba.test", "a&b@prueba.test"),
        )
        assert (
            r.status_code == 200
            and "a&amp;b@prueba.test" in r.text
            and "a&b@" not in r.text
        )
