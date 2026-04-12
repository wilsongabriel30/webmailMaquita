"""
Módulo de contactos — routers organizados por funcionalidad.

Archivos:
  helpers.py        → funciones compartidas (row_to_dict, audit, etc.)
  avatars.py        → GET /avatars (lookup batch)
  search.py         → GET /search (autocomplete compose)
  crud.py           → GET list, POST create, PUT update, DELETE soft-delete
  favorites.py      → PUT favorite, POST restore, DELETE permanent, DELETE trash
  categories.py     → CRUD categorías + asignar a contacto
  lists.py          → CRUD listas + miembros + expand para compose
  bulk.py           → acciones masivas (delete, favorite, category)
  import_export.py  → POST import CSV, GET export CSV/vCard
  from_email.py     → POST from-email (crear desde correo)
  interactions.py   → GET interactions + stats por contacto
  score.py          → POST recalculate-scores
  gravatar.py       → GET gravatar check
  duplicates.py     → GET duplicates + POST merge
  reminders.py      → CRUD reminders por contacto
  custom_fields.py  → CRUD campos personalizados + valores
  relationships.py  → CRUD relaciones entre contactos
  directory.py      → Directorio institucional compartido
  shared_notes.py   → Notas colaborativas
  carddav.py        → Sincronización CardDAV / vCard
  signature.py      → Enriquecimiento desde firma de correo
  multi_import.py   → Importación multi-servicio (vCard, LinkedIn, etc.)
"""
from fastapi import APIRouter
from .avatars import router as avatars_router
from .search import router as search_router
from .crud import router as crud_router
from .favorites import router as favorites_router
from .categories import router as categories_router
from .lists import router as lists_router
from .bulk import router as bulk_router
from .import_export import router as import_export_router
from .from_email import router as from_email_router
from .interactions import router as interactions_router
from .score import router as score_router
from .gravatar import router as gravatar_router
from .duplicates import router as duplicates_router
from .reminders import router as reminders_router
from .custom_fields import router as custom_fields_router
from .relationships import router as relationships_router
from .directory import router as directory_router
from .shared_notes import router as shared_notes_router
from .carddav import router as carddav_router
from .signature import router as signature_router
from .multi_import import router as multi_import_router

# Router combinado para registrar en main.py
router = APIRouter()

# Orden importa: rutas específicas antes de rutas con parámetros
router.include_router(avatars_router)
router.include_router(search_router)
router.include_router(bulk_router)          # /bulk/* antes de /{contact_id}
router.include_router(categories_router)    # /categories antes de /{contact_id}
router.include_router(lists_router)         # /lists/* antes de /{contact_id}
router.include_router(import_export_router) # /import, /export antes de /{contact_id}
router.include_router(from_email_router)    # /from-email antes de /{contact_id}
router.include_router(score_router)         # /recalculate-scores antes de /{contact_id}
router.include_router(gravatar_router)      # /gravatar antes de /{contact_id}
router.include_router(duplicates_router)    # /duplicates, /merge antes de /{contact_id}
router.include_router(reminders_router)     # /reminders antes de /{contact_id}
router.include_router(custom_fields_router) # /custom-fields antes de /{contact_id}
router.include_router(relationships_router) # /relationships antes de /{contact_id}
router.include_router(directory_router)     # /directory/* antes de /{contact_id}
router.include_router(shared_notes_router)  # /shared-notes antes de /{contact_id}
router.include_router(carddav_router)       # /carddav/* antes de /{contact_id}
router.include_router(signature_router)     # /signature/* antes de /{contact_id}
router.include_router(multi_import_router)  # /import/* antes de /{contact_id}
router.include_router(interactions_router)  # /{contact_id}/interactions, /{contact_id}/stats
router.include_router(favorites_router)     # /{contact_id}/favorite, etc.
router.include_router(crud_router)          # /{contact_id} al final (catch-all)
