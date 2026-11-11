"""El contador de no leídos también sale en carpetas con tildes o caracteres especiales (11/11/2026).

`list_folders` pedía el STATUS con el nombre ya codificado en UTF-7 y `_quote_folder` lo volvía a
codificar («Direcci&APM-n» → «Direcci&-APM-n»): el servidor respondía que la carpeta no existía y el
contador quedaba en 0.
"""

from types import SimpleNamespace

from app.mail.clients import imap_client


class _Imap:
    def __init__(self):
        self.pedidos: list[str] = []

    async def list(self, _ref, _patron):
        return SimpleNamespace(
            result="OK",
            lines=[
                b'(\\HasNoChildren) "." INBOX.1&ICQ-Direcci&APM-n',
                b'(\\HasNoChildren) "." "INBOX.12_ Planificaci&APM-n"',
                b'(\\HasNoChildren) "." INBOX',
                b"LIST completed.",
            ],
        )

    async def status(self, nombre, _campos):
        self.pedidos.append(nombre)
        return SimpleNamespace(result="OK", lines=[b"x (MESSAGES 9 UNSEEN 3)"])


async def test_status_se_pide_con_el_nombre_codificado_una_sola_vez():
    imap = _Imap()
    carpetas = await imap_client.list_folders(imap)
    assert imap.pedidos == [
        "INBOX.1&ICQ-Direcci&APM-n",
        '"INBOX.12_ Planificaci&APM-n"',
        "INBOX",
    ]
    assert [c["unseen"] for c in carpetas] == [3, 3, 3]
    assert carpetas[0]["name"] == "INBOX.1․Dirección"
