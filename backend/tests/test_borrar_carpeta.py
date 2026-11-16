"""Eliminar una carpeta con subcarpetas (informe de Andes, 15/11/2026).

El servidor de mentira se porta como Dovecot 2.4.1 (comprobado): `DELETE` de una carpeta con
hijas responde OK y el nombre sigue en la lista; el segundo `DELETE` responde NO.
"""

from types import SimpleNamespace

import pytest

from app.mail.services import borrar_carpeta as bc


class _Imap:
    def __init__(self, carpetas, separador=".", intocables=(), especiales=()):
        self.buzones = set(carpetas)  # las que existen como buzón
        self.sep = separador
        self.intocables = set(intocables)  # el servidor se niega a borrarlas
        self.especiales = set(especiales)
        self.ordenes: list[tuple[str, str]] = []

    def _visibles(self) -> set[str]:
        """Los buzones y los nombres que siguen como contenedores de sus hijas."""
        nombres = set(self.buzones)
        for b in self.buzones:
            trozos = b.split(self.sep)
            nombres.update(self.sep.join(trozos[:i]) for i in range(1, len(trozos)))
        return nombres

    async def list(self, _ref, patron):
        patron = patron.strip('"')
        lineas = []
        for n in sorted(self._visibles()):
            casa = (
                n.startswith(patron[:-1]) and n != patron[:-1]
                if patron.endswith("*")
                else n == patron
            )
            if not casa:
                continue
            marca = "\\Sent" if n in self.especiales else "\\HasNoChildren"
            lineas.append(f'({marca}) "{self.sep}" "{n}"'.encode())
        return SimpleNamespace(result="OK", lines=lineas + [b"List completed."])

    async def unsubscribe(self, nombre):
        self.ordenes.append(("unsubscribe", nombre.strip('"')))
        return SimpleNamespace(result="OK", lines=[])

    async def delete(self, nombre):
        nombre = nombre.strip('"')
        self.ordenes.append(("delete", nombre))
        if nombre in self.intocables:
            return SimpleNamespace(
                result="NO", lines=[b"[NOPERM] Permission denied (0.001 + 0.000 secs)."]
            )
        if nombre not in self.buzones:
            return SimpleNamespace(
                result="NO",
                lines=[f"[NONEXISTENT] Mailbox doesn't exist: {nombre}".encode()],
            )
        self.buzones.discard(nombre)
        return SimpleNamespace(result="OK", lines=[b"Delete completed."])


def _borradas(imap):
    return [n for o, n in imap.ordenes if o == "delete"]


async def test_borra_las_hijas_antes_de_la_mas_profunda_a_la_raiz():
    imap = _Imap(
        ["INBOX", "Padre", "Padre.Hija", "Padre.Hija.Nieta", "Padre.Otra", "Padres"]
    )
    hecho = await bc.borrar_con_subcarpetas(imap, "Padre")
    assert _borradas(imap) == ["Padre.Hija.Nieta", "Padre.Hija", "Padre.Otra", "Padre"]
    assert hecho == {"subcarpetas": 3}
    assert imap.buzones == {"INBOX", "Padres"}, "«Padres» no es hija de «Padre»"
    # Cada suscripción se quita antes de borrar su carpeta.
    for i, (orden, nombre) in enumerate(imap.ordenes):
        if orden == "delete":
            assert imap.ordenes[i - 1] == ("unsubscribe", nombre)


async def test_una_carpeta_sin_hijas_se_borra_igual_que_antes():
    imap = _Imap(["INBOX", "Suelta"])
    assert await bc.borrar_con_subcarpetas(imap, "Suelta") == {"subcarpetas": 0}
    assert _borradas(imap) == ["Suelta"]


async def test_termina_lo_que_un_intento_anterior_dejo_a_medias():
    # Tras el fallo antiguo: «Padre» ya no es buzón, pero sigue en la lista por sus hijas.
    imap = _Imap(["INBOX", "Padre.Hija", "Padre.Hija.Nieta"])
    await bc.borrar_con_subcarpetas(imap, "Padre")
    assert imap.buzones == {"INBOX"}
    assert _borradas(imap)[-1] == "Padre", "responde NO y aun así ya no queda nada"


async def test_si_el_servidor_no_deja_borrar_una_hija_no_se_da_por_eliminada():
    imap = _Imap(["Padre", "Padre.Hija", "Padre.Libre"], intocables=["Padre.Hija"])
    with pytest.raises(bc.NoSePudoBorrar) as e:
        await bc.borrar_con_subcarpetas(imap, "Padre")
    assert e.value.estado == 400
    assert "Padre.Hija" in e.value.mensaje and "Permission denied" in e.value.mensaje
    assert "secs" not in e.value.mensaje


async def test_una_carpeta_del_sistema_dentro_detiene_el_borrado_antes_de_empezar():
    imap = _Imap(["Padre", "Padre.Enviados"], especiales=["Padre.Enviados"])
    with pytest.raises(bc.NoSePudoBorrar):
        await bc.borrar_con_subcarpetas(imap, "Padre")
    assert _borradas(imap) == []


async def test_carpeta_que_ya_no_existe_responde_404():
    with pytest.raises(bc.NoSePudoBorrar) as e:
        await bc.borrar_con_subcarpetas(_Imap(["INBOX"]), "Fantasma")
    assert e.value.estado == 404


async def test_respeta_el_separador_del_servidor_y_los_nombres_con_tildes():
    imap = _Imap(
        ["Archivo", "Archivo/2025", "Archivo/2025/Planificaci&APM-n"], separador="/"
    )
    await bc.borrar_con_subcarpetas(imap, "Archivo")
    assert _borradas(imap) == [
        "Archivo/2025/Planificaci&APM-n",
        "Archivo/2025",
        "Archivo",
    ]
    # El nombre llega legible y se codifica una sola vez.
    imap = _Imap(["Direcci&APM-n", "Direcci&APM-n.Actas 2026"])
    await bc.borrar_con_subcarpetas(imap, "Dirección")
    assert _borradas(imap) == ["Direcci&APM-n.Actas 2026", "Direcci&APM-n"]


def test_leer_lista_entiende_comillas_nil_y_la_linea_final():
    carpetas = bc.leer_lista(
        [
            b'(\\HasChildren) "." Padre',
            b'(\\HasNoChildren \\Sent) "." "Padre.Con espacio"',
            b"(\\Noselect) NIL Rara",
            b"List completed (0.001 + 0.000 secs).",
        ]
    )
    assert [(c.nombre, c.separador) for c in carpetas] == [
        ("Padre", "."),
        ("Padre.Con espacio", "."),
        ("Rara", ""),
    ]
    assert "sent" in carpetas[1].marcas


def test_la_ruta_no_anuncia_el_borrado_si_el_servicio_falla():
    # La ruta convierte el fallo en un error HTTP: la interfaz solo dice «Carpeta eliminada» con 200.
    import inspect

    from app.mail.routers import folders

    fuente = inspect.getsource(folders.delete_folder)
    assert "borrar_con_subcarpetas" in fuente and "NoSePudoBorrar" in fuente
    assert "Failed to delete folder" not in fuente
