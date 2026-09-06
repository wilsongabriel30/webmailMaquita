"""Interfaz común de un analizador de adjuntos.

Cada analizador es un archivo aparte que hereda de Analyzer e implementa
`analyze`. No debe lanzar excepciones hacia afuera: el pipeline las captura,
pero conviene manejar errores y registrarlos en `report.engines`.
"""


class Analyzer:
    name = "base"
    # Un motor OBLIGATORIO que no responde es fallo CERRADO (R-04): el adjunto queda
    # como sospechoso y va a cuarentena; nunca «clean» por accidente.
    obligatorio = False

    def applies(self, filename: str, mime: str) -> bool:
        """¿Aplica este analizador a este archivo? Por defecto, sí."""
        return True

    def analyze(self, path: str, content: bytes, report) -> None:
        raise NotImplementedError
