"""Validación semántica de una respuesta SAML (F-02, tercera revisión).

Verificar la firma no basta. Aquí se hace lo que faltaba, y SIEMPRE sobre el XML que
devolvió el verificador (`signed_xml`), nunca sobre el árbol original (XML Signature
Wrapping):

- exactamente UNA Assertion, con estructura esperada;
- Status Success;
- `InResponseTo` presente y correlacionado con un AuthnRequest nuestro, consumido de un solo
  uso (GETDEL);
- `Destination` de la Response y `Recipient` de la confirmación = nuestra URL ACS;
- `AudienceRestriction` = nuestro entityID;
- `NotBefore` / `NotOnOrAfter` (Conditions y SubjectConfirmationData) con tolerancia de reloj;
- `ID` de la Assertion de un solo uso (SET NX) durante su vida útil.

Devuelve el NameID. Cualquier condición que falle lanza `SAMLRechazada` con un motivo corto
(el detalle nunca incluye el XML).
"""

from datetime import datetime, timedelta, timezone

NS = {
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
}
TOLERANCIA_RELOJ = timedelta(seconds=120)
TTL_ASSERTION_USADA = 12 * 3600


class SAMLRechazada(Exception):
    pass


def _fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    v = valor.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(v)
    except ValueError as exc:
        raise SAMLRechazada("fecha SAML ilegible") from exc
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _uno(nodo, ruta: str, que: str):
    hallados = nodo.findall(ruta, NS)
    if len(hallados) != 1:
        raise SAMLRechazada(f"{que}: se esperaba exactamente uno, hay {len(hallados)}")
    return hallados[0]


def extraer_verificado(verified) -> tuple:
    """(response, assertion) a partir de lo que devolvió XMLVerifier.

    signxml devuelve el elemento FIRMADO: puede ser la Response entera (firma en la Response)
    o solo la Assertion (firma en la Assertion). En ambos casos todo lo que se lee sale de
    ese elemento verificado; el árbol original no se vuelve a mirar.
    """
    firmado = verified.signed_xml
    etiqueta = firmado.tag
    if etiqueta == "{%s}Response" % NS["samlp"]:
        response = firmado
        assertion = _uno(response, "saml:Assertion", "Assertion")
    elif etiqueta == "{%s}Assertion" % NS["saml"]:
        response = None
        assertion = firmado
    else:
        raise SAMLRechazada("el elemento firmado no es una Response ni una Assertion")
    if assertion.find("saml:Subject", NS) is None:
        raise SAMLRechazada("Assertion sin Subject")
    return response, assertion


def validar(
    response,
    assertion,
    *,
    acs_url: str,
    entity_id: str,
    ahora: datetime | None = None,
    response_sin_firmar=None,
) -> dict:
    """Comprueba la semántica. `response_sin_firmar` solo se usa para leer Status/InResponseTo
    cuando la firma cubre únicamente la Assertion (esos campos no están dentro de ella); su
    valor nunca se usa para decidir identidad.

    Devuelve {"name_id", "in_response_to", "assertion_id", "not_on_or_after"}.
    """
    ahora = ahora or datetime.now(timezone.utc)
    resp = response if response is not None else response_sin_firmar
    if resp is None:
        raise SAMLRechazada("sin Response")

    # Estado
    estado = resp.find("samlp:Status/samlp:StatusCode", NS)
    if estado is None or "Success" not in (estado.get("Value") or ""):
        raise SAMLRechazada("Status no es Success")

    # Correlación y destino de la Response
    in_response_to = (resp.get("InResponseTo") or "").strip()
    if not in_response_to:
        raise SAMLRechazada("Response sin InResponseTo (no correlacionada)")
    destino = (resp.get("Destination") or "").strip()
    if destino != acs_url:
        raise SAMLRechazada("Destination no es nuestra URL ACS")

    # Assertion: id, sujeto, confirmación
    assertion_id = (assertion.get("ID") or "").strip()
    if not assertion_id:
        raise SAMLRechazada("Assertion sin ID")
    name_id = _uno(assertion, "saml:Subject/saml:NameID", "NameID")
    if not (name_id.text or "").strip():
        raise SAMLRechazada("NameID vacío")
    conf = _uno(
        assertion, "saml:Subject/saml:SubjectConfirmation", "SubjectConfirmation"
    )
    if conf.get("Method") != "urn:oasis:names:tc:SAML:2.0:cm:bearer":
        raise SAMLRechazada("SubjectConfirmation no es bearer")
    datos = _uno(conf, "saml:SubjectConfirmationData", "SubjectConfirmationData")
    if (datos.get("Recipient") or "").strip() != acs_url:
        raise SAMLRechazada("Recipient no es nuestra URL ACS")
    if (datos.get("InResponseTo") or "").strip() not in ("", in_response_to):
        raise SAMLRechazada("InResponseTo de la confirmación no coincide")
    venc_conf = _fecha(datos.get("NotOnOrAfter"))
    if venc_conf is None or venc_conf + TOLERANCIA_RELOJ <= ahora:
        raise SAMLRechazada("SubjectConfirmationData vencida o sin NotOnOrAfter")

    # Condiciones: ventana temporal y audiencia
    cond = _uno(assertion, "saml:Conditions", "Conditions")
    nb = _fecha(cond.get("NotBefore"))
    noa = _fecha(cond.get("NotOnOrAfter"))
    if nb is not None and nb - TOLERANCIA_RELOJ > ahora:
        raise SAMLRechazada("Assertion todavía no válida (NotBefore)")
    if noa is None or noa + TOLERANCIA_RELOJ <= ahora:
        raise SAMLRechazada("Assertion vencida (NotOnOrAfter)")
    audiencias = [
        (a.text or "").strip()
        for a in cond.findall("saml:AudienceRestriction/saml:Audience", NS)
    ]
    if entity_id not in audiencias:
        raise SAMLRechazada("AudienceRestriction no incluye nuestro entityID")

    return {
        "name_id": name_id.text.strip().lower(),
        "in_response_to": in_response_to,
        "assertion_id": assertion_id,
        "not_on_or_after": min(noa, venc_conf),
    }


async def consumir_una_vez(
    redis, in_response_to: str, assertion_id: str, not_on_or_after: datetime
) -> None:
    """La petición correlacionada se consume (GETDEL) y la Assertion se marca usada (SET NX)."""
    try:
        pendiente = await redis.getdel(f"saml_req:{in_response_to}")
    except Exception:
        pendiente = await redis.get(f"saml_req:{in_response_to}")
        if pendiente:
            await redis.delete(f"saml_req:{in_response_to}")
    if not pendiente:
        raise SAMLRechazada("SAML response no correlacionada o ya utilizada")
    restante = int(
        (not_on_or_after - datetime.now(timezone.utc)).total_seconds()
    ) + int(TOLERANCIA_RELOJ.total_seconds())
    ttl = max(60, min(TTL_ASSERTION_USADA, restante))
    if not await redis.set(
        f"saml_assertion_usada:{assertion_id}", "1", ex=ttl, nx=True
    ):
        raise SAMLRechazada("Aserción SAML reutilizada")
