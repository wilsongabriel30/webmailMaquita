"""Stub del servicio de IA del chat (desactivado en el servicio independiente).
El chat-IA no forma parte del piloto; estas clases evitan romper imports.
"""
class _NoDisponible:
    def __init__(self, *a, **k): pass
    def __getattr__(self, _): 
        def _f(*a, **k): raise RuntimeError("chat-IA desactivado en este servicio")
        return _f

OllamaService = _NoDisponible
ChatResponse = _NoDisponible
class BusquedaIAMejorada(_NoDisponible): pass
class KnowledgeService(_NoDisponible): pass
class WebSearchService(_NoDisponible): pass
