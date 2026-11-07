"""Texto de los correos encontrados que se entrega a la IA para responder (con su carpeta)."""

from app.rag.carpetas import etiqueta

# Caracteres de cada correo en el contexto (6 correos, unos 1.200 tokens)
MAX_POR_CORREO = 700


def _extracto(contenido: str) -> str:
    """El contenido indexado ya empieza por «Carpeta: … | Fecha: … | De: …»."""
    c = (contenido or "").strip()
    return c[:MAX_POR_CORREO] + ("…" if len(c) > MAX_POR_CORREO else "")


def bloque(filas) -> str:
    lineas = []
    for r in filas:
        contenido = r["content"] or ""
        if contenido.startswith("Carpeta:"):
            lineas.append(f"- {_extracto(contenido)}")
        else:  # indexado con el formato anterior (solo remitente y asunto)
            lineas.append(
                f"- Carpeta: {etiqueta(r['folder'])} | {r['subject']} (de {r['sender']})"
            )
    return "\n".join(lineas)
