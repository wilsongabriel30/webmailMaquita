"""F-02: pruebas negativas del ACS SAML con respuestas firmadas por un IdP de laboratorio."""

import asyncio
import base64
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner, XMLVerifier

from app.sso import saml_seguridad as ss

ACS = "https://correo.example.com/api/sso/saml/acs"
SP = "https://correo.example.com/api/sso/saml/metadata"


@pytest.fixture(scope="module")
def idp():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "idp.example.com")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return {
        "key": key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        "cert": cert.public_bytes(serialization.Encoding.PEM).decode(),
    }


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def respuesta(**k):
    ahora = datetime.now(timezone.utc)
    p = dict(
        destino=ACS,
        recipient=ACS,
        audiencia=SP,
        in_response_to="_req1",
        assertion_id="_a1",
        name_id="ana@example.com",
        not_before=_iso(ahora - timedelta(minutes=1)),
        not_on_or_after=_iso(ahora + timedelta(minutes=5)),
        status="urn:oasis:names:tc:SAML:2.0:status:Success",
    )
    p.update(k)
    return f"""<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
  ID="_r1" Version="2.0" IssueInstant="{_iso(ahora)}" Destination="{p['destino']}" InResponseTo="{p['in_response_to']}">
  <saml:Issuer>https://idp.example.com</saml:Issuer>
  <samlp:Status><samlp:StatusCode Value="{p['status']}"/></samlp:Status>
  <saml:Assertion ID="{p['assertion_id']}" Version="2.0" IssueInstant="{_iso(ahora)}">
    <saml:Issuer>https://idp.example.com</saml:Issuer>
    <saml:Subject>
      <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{p['name_id']}</saml:NameID>
      <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
        <saml:SubjectConfirmationData Recipient="{p['recipient']}" InResponseTo="{p['in_response_to']}" NotOnOrAfter="{p['not_on_or_after']}"/>
      </saml:SubjectConfirmation>
    </saml:Subject>
    <saml:Conditions NotBefore="{p['not_before']}" NotOnOrAfter="{p['not_on_or_after']}">
      <saml:AudienceRestriction><saml:Audience>{p['audiencia']}</saml:Audience></saml:AudienceRestriction>
    </saml:Conditions>
  </saml:Assertion>
</samlp:Response>"""


def firmar(idp, xml: str, que: str = "response"):
    """Firma la Response entera o solo la Assertion, como haría un IdP."""
    root = etree.fromstring(xml.encode())
    signer = XMLSigner(
        method=__import__("signxml").methods.enveloped, signature_algorithm="rsa-sha256"
    )
    if que == "response":
        return signer.sign(root, key=idp["key"], cert=idp["cert"])
    assertion = root.find("saml:Assertion", ss.NS)
    firmada = signer.sign(assertion, key=idp["key"], cert=idp["cert"])
    root.replace(assertion, firmada)
    return root


def procesar(idp, root):
    verified = XMLVerifier().verify(root, x509_cert=idp["cert"])
    response, assertion = ss.extraer_verificado(verified)
    return ss.validar(
        response, assertion, acs_url=ACS, entity_id=SP, response_sin_firmar=root
    )


def test_respuesta_correcta_da_el_name_id(idp):
    r = procesar(idp, firmar(idp, respuesta()))
    assert r["name_id"] == "ana@example.com" and r["in_response_to"] == "_req1"


@pytest.mark.parametrize(
    "cambio, motivo",
    [
        ({"destino": "https://otro.example.com/acs"}, "Destination"),
        ({"recipient": "https://otro.example.com/acs"}, "Recipient"),
        ({"audiencia": "https://otro-sp.example.com"}, "Audience"),
        (
            {
                "not_on_or_after": _iso(
                    datetime.now(timezone.utc) - timedelta(minutes=10)
                )
            },
            "vencida",
        ),
        (
            {"not_before": _iso(datetime.now(timezone.utc) + timedelta(minutes=10))},
            "NotBefore",
        ),
        ({"in_response_to": ""}, "InResponseTo"),
        ({"status": "urn:oasis:names:tc:SAML:2.0:status:Requester"}, "Status"),
    ],
)
def test_condiciones_semanticas_rechazan(idp, cambio, motivo):
    with pytest.raises(ss.SAMLRechazada) as e:
        procesar(idp, firmar(idp, respuesta(**cambio)))
    assert motivo.lower() in str(e.value).lower()


def test_firma_alterada_no_pasa(idp):
    root = firmar(idp, respuesta())
    root.find("saml:Assertion/saml:Subject/saml:NameID", ss.NS).text = (
        "atacante@example.com"
    )
    with pytest.raises(Exception):
        XMLVerifier().verify(root, x509_cert=idp["cert"])


def test_wrapping_la_identidad_sale_solo_del_nodo_firmado(idp):
    """Firma solo la Assertion; el atacante envuelve la firmada con OTRA Assertion sin firmar
    con un NameID distinto. Antes se leía del árbol original (root.find('.//NameID')).
    """
    root = firmar(idp, respuesta(), que="assertion")
    intrusa = etree.fromstring(
        respuesta(name_id="atacante@example.com", assertion_id="_a2").encode()
    ).find("saml:Assertion", ss.NS)
    root.insert(2, intrusa)  # antes de la firmada
    verified = XMLVerifier().verify(root, x509_cert=idp["cert"])
    response, assertion = ss.extraer_verificado(verified)
    r = ss.validar(
        response, assertion, acs_url=ACS, entity_id=SP, response_sin_firmar=root
    )
    assert r["name_id"] == "ana@example.com"


def test_dos_assertions_en_una_response_firmada_se_rechazan(idp):
    root = etree.fromstring(respuesta().encode())
    extra = etree.fromstring(
        respuesta(name_id="b@example.com", assertion_id="_a2").encode()
    ).find("saml:Assertion", ss.NS)
    root.append(extra)
    firmada = XMLSigner(
        method=__import__("signxml").methods.enveloped, signature_algorithm="rsa-sha256"
    ).sign(root, key=idp["key"], cert=idp["cert"])
    verified = XMLVerifier().verify(firmada, x509_cert=idp["cert"])
    with pytest.raises(ss.SAMLRechazada):
        ss.extraer_verificado(verified)


class _RedisFalso:
    def __init__(self):
        self.d = {}

    async def getdel(self, k):
        return self.d.pop(k, None)

    async def set(self, k, v, ex=None, nx=False):
        if nx and k in self.d:
            return None
        self.d[k] = v
        return True


def test_replay_se_consume_una_sola_vez():
    r = _RedisFalso()
    r.d["saml_req:_req1"] = "pending"
    venc = datetime.now(timezone.utc) + timedelta(minutes=5)
    asyncio.run(ss.consumir_una_vez(r, "_req1", "_a1", venc))
    with pytest.raises(ss.SAMLRechazada):  # segunda vez: la petición ya se consumió
        asyncio.run(ss.consumir_una_vez(r, "_req1", "_a1", venc))
    r.d["saml_req:_req2"] = "pending"
    with pytest.raises(
        ss.SAMLRechazada
    ):  # misma Assertion con otra petición: reutilizada
        asyncio.run(ss.consumir_una_vez(r, "_req2", "_a1", venc))
