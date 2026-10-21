"""El único error que sale del intermediario hacia el portal: un código y un texto para la persona."""


class ErrorPortal(Exception):
    """codigo ∈ 400, 403, 404, 409, 413, 503 (los del contrato con el portal)."""

    def __init__(self, codigo, texto):
        super().__init__(texto)
        self.codigo = codigo
        self.texto = texto


def no_encontrado():
    # Lo ajeno nunca se confirma: no existe y no es tuyo responden igual.
    return ErrorPortal(404, "No encontrado")
