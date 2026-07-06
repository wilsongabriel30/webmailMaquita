"""Stub del servicio de auditoria (no-op en el servicio de chat independiente)."""
class AuditService:
    def __init__(self, *a, **k): pass
    def __getattr__(self, _):
        def _f(*a, **k): return None
        return _f
audit_service = AuditService()
