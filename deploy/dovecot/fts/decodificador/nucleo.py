"""Reparte cada adjunto (o cada archivo dentro de un comprimido) al lector de su formato.

Un error en un miembro no tumba el resto: se anota y se sigue. Un límite superado (LimiteSuperado)
sí corta todo, porque el presupuesto es del adjunto entero; lo extraído hasta ahí se conserva.
"""

import io
import os
import shutil
import tempfile
import zipfile

import comprimidos
import externos
import ofimatica
import textos
import tipos
from limites import Limites, LimiteSuperado, Presupuesto

_CONTENEDORES = {"zip", "tar", "gzip", "bzip2", "xz", "7z"}
_EXTENSION_OLE = {"application/msword": "doc", "application/vnd.ms-excel": "xls", "application/vnd.ms-powerpoint": "ppt"}


class Decodificador:
    def __init__(self, lim: Limites, presupuesto: Presupuesto, tmp: str):
        self.lim = lim
        self.p = presupuesto
        self.tmp = tmp

    def decodificar(self, datos: bytes, declarado: str = "", nombre: str = "", profundidad: int = 0) -> None:
        declarado = (declarado or "").split(";", 1)[0].strip().lower()
        clase = tipos.decidir(declarado, datos, nombre)
        if clase is None:
            return
        try:
            self._por_clase(clase, datos, declarado, nombre, profundidad)
        except LimiteSuperado:
            raise
        except Exception as exc:  # noqa: BLE001  archivo dañado o con trampa: se salta solo este
            self.p.avisos.append(f"{nombre or declarado}: {type(exc).__name__}")

    def _hijo(self, profundidad: int):
        def recursar(datos: bytes, nombre: str) -> None:
            self.decodificar(datos, "", nombre, profundidad + 1)

        return recursar

    def _hondo(self, clase: str, profundidad: int, nombre: str) -> bool:
        if clase in _CONTENEDORES and profundidad >= self.lim.max_profundidad:
            self.p.avisos.append(f"{nombre or clase}: demasiados niveles de comprimido")
            return True
        return False

    def _por_clase(self, clase: str, datos: bytes, declarado: str, nombre: str, profundidad: int) -> None:
        p = self.p
        if clase == "zip":
            zf = zipfile.ZipFile(io.BytesIO(datos))
            fina = tipos.clase_de_zip(zf)
            if fina in ("ooxml", "odf"):
                ofimatica.documento(zf, fina, p)
            elif not self._hondo("zip", profundidad, nombre):
                comprimidos.zip_(zf, p, self._hijo(profundidad))
        elif clase == "tar":
            if not self._hondo(clase, profundidad, nombre):
                comprimidos.tar(datos, p, self._hijo(profundidad))
        elif clase in ("gzip", "bzip2", "xz"):
            if not self._hondo(clase, profundidad, nombre):
                interior = comprimidos.descomprimir(datos, clase, p)
                # Lo de dentro se reconoce por su firma (un .tar.gz da un TAR).
                self._hijo(profundidad)(interior, nombre.rsplit(".", 1)[0] if "." in nombre else "")
        elif clase == "7z":
            if not self._hondo(clase, profundidad, nombre):
                with self._archivo(datos, ".7z") as (ruta, tmp):
                    comprimidos.siete_z(ruta, p, self._hijo(profundidad), tmp)
        elif clase == "pdf":
            with self._archivo(datos, ".pdf") as (ruta, tmp):
                texto = externos.pdf_texto(ruta, self.lim, tmp)
                if not texto.strip():
                    texto = externos.ocr_pdf(ruta, self.lim, tmp)  # PDF escaneado (si OCR=1)
                p.añadir_texto(texto + "\n")
        elif clase == "ole":
            ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else _EXTENSION_OLE.get(declarado, "doc")
            with self._archivo(datos, "." + ext) as (ruta, tmp):
                p.añadir_texto(externos.office_antiguo(ruta, ext, self.lim, tmp) + "\n")
        elif clase == "rtf":
            p.añadir_texto(textos.rtf(datos) + "\n")
        elif clase == "html":
            p.añadir_texto(textos.html(datos) + "\n")
        elif clase == "texto":
            p.añadir_texto(textos.a_texto(datos) + "\n")
        elif clase == "imagen":
            with self._archivo(datos, ".img") as (ruta, tmp):
                p.añadir_texto(externos.exif(ruta, self.lim, tmp) + "\n")
                p.añadir_texto(externos.ocr_imagen(ruta, self.lim, tmp) + "\n")

    def _archivo(self, datos: bytes, sufijo: str):
        """Copia temporal (en una carpeta propia, borrada al salir) para los programas externos."""
        return _Temporal(self.tmp, datos, sufijo)


class _Temporal:
    def __init__(self, base: str, datos: bytes, sufijo: str):
        self.base, self.datos, self.sufijo = base, datos, sufijo

    def __enter__(self):
        self.dir = tempfile.mkdtemp(dir=self.base)
        ruta = os.path.join(self.dir, "adjunto" + self.sufijo)
        with open(ruta, "wb") as f:
            f.write(self.datos)
        return ruta, self.dir

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)
        return False
