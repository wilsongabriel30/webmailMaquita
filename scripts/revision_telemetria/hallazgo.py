"""Estructura común de un hallazgo y su gravedad."""
from dataclasses import dataclass, field

CRITICO, ALTO, MEDIO, BAJO, INFO = 1, 2, 3, 4, 5
ETIQUETA = {CRITICO: 'CRÍTICO', ALTO: 'ALTO', MEDIO: 'MEDIO', BAJO: 'BAJO', INFO: 'INFORMATIVO'}


@dataclass
class Hallazgo:
    gravedad: int
    seccion: str          # letra/nombre de la comprobación (a, b, c, d, e, f)
    titulo: str
    usuario: str = ''
    lineas: list = field(default_factory=list)   # evidencia, una línea por elemento
    sugerencia: str = ''

    def clave_orden(self):
        return (self.gravedad, self.seccion, self.usuario, self.titulo)
