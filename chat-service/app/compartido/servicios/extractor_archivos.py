"""Stub del extractor de archivos (no-op; el chat guarda adjuntos sin extraer texto)."""
class ExtractorArchivosService:
    def __init__(self, *a, **k): pass
    def __getattr__(self, _):
        def _f(*a, **k): return None
        return _f
extractor_archivos = ExtractorArchivosService()
