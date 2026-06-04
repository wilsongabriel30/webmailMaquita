from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_admin
from app.wrappers.doveadm import get_who

router = APIRouter(prefix="/api/connections", tags=["connections"])

@router.get("")
async def active_connections(admin: dict = Depends(get_current_admin)):
    return await get_who()
