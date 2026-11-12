"""Buscar por remitente también lo que esa persona escribió y OTRO reenvió (12/11/2026).

Pedido de Contabilidad de Agro: alguien reenvía un correo de Daniel; quien lo recibe filtra por
«de:daniel» y no aparece, porque el remitente del reenvío es quien reenvió. Para IMAP ese correo
es «de» quien lo reenvió; lo único que queda del autor original es su nombre en el cuerpo
(«De: Daniel …») y la marca de reenvío en el asunto.

Criterio: asunto con marca de reenvío (RV:, FW:, Fwd:, Reenv…) Y el nombre buscado en el cuerpo.
Solo se usa cuando el buzón tiene índice de texto (con él tarda décimas de segundo en un buzón de
100 000 correos; sin él habría que abrir cada correo). El índice no distingue «De: Daniel» de
«Daniel» a secas, así que es amplio a propósito: mejor que aparezca de más a que no aparezca.
"""

from __future__ import annotations

# Marcas de reenvío que ponen Outlook («RV:», «FW:»), Gmail y el webmail («Fwd:») y variantes en español.
MARCAS = ("RV:", "FW:", "Fwd:", "Reenv")


def _marcas() -> str:
    partes = [f'SUBJECT "{m}"' for m in MARCAS]
    return " ".join(["OR"] * (len(partes) - 1) + partes)


def solo_reenviados(valor_entrecomillado: str) -> str:
    """Un criterio IMAP entre paréntesis: reenviado y con ese texto en el cuerpo."""
    return f"({_marcas()} BODY {valor_entrecomillado})"


def remitente_o_reenviado(valor_entrecomillado: str) -> list[str]:
    """«de:x» ampliado: lo que envió x, o lo que otro reenvió y menciona a x."""
    return ["OR", "FROM", valor_entrecomillado, solo_reenviados(valor_entrecomillado)]
