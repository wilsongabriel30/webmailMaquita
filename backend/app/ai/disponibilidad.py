"""¿Tiene esta instalación una IA configurada? Lo pregunta la interfaz para decidir si enseña el asistente.

Sin IA, el botón «Asistente» seguía visible y cada acción terminaba en 502 (informe de Andes, 15/11/2026).
Aquí solo se mira la configuración: no se llama al modelo (para eso está `/api/ai/health`, que es lento) ni se
cuenta nada de la red interna. Hay IA cuando hay un modelo definido, en el `.env` (`IA_MODEL`) o en el panel.
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai"])


def hay_modelo(configuracion: dict) -> bool:
    return bool((configuracion.get("model") or "").strip())


@router.get("/disponible")
async def ia_disponible(_usuario: str = Depends(get_current_user)):
    from app.ai.router import _get_ia_config

    try:
        return {"disponible": hay_modelo(await _get_ia_config())}
    except Exception:
        return {"disponible": False}
