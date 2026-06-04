import logging
from contextlib import asynccontextmanager

import bcrypt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback
import logging as _logging
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_pool, init_admin_tables
from app.auth.router import router as auth_router
from app.dashboard.router import router as dashboard_router
from app.domains.router import router as domains_router
from app.mailboxes.router import router as mailboxes_router
from app.aliases.router import router as aliases_router
from app.queue.router import router as queue_router
from app.tracking.router import router as tracking_router
from app.recovery.router import router as recovery_router
from app.quarantine.router import router as quarantine_router
from app.forwarding.router import router as forwarding_router
from app.health.router import router as health_router
from app.connections.router import router as connections_router
from app.audit.router import router as audit_router
from app.services.router import router as services_router
from app.groups.router import router as groups_router
from app.mailviewer.router import router as mailviewer_router
from app.signatures.router import router as signatures_router
from app.autoresponder.router import router as autoresponder_router
from app.dnscheck.router import router as dnscheck_router
from app.shared.router import router as shared_router
from app.nextcloud.router import router as nextcloud_router
from app.ediscovery.router import router as ediscovery_router
from app.branding.router import router as branding_router
from app.ai_config.router import router as ai_config_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Maquita Admin Panel starting...")
    pool = await create_pool()
    app.state.db = pool

    await init_admin_tables(pool)

    # Create default superadmin if none exists
    count = await pool.fetchval("SELECT count(*) FROM admin_users")
    if count == 0:
        default_hash = bcrypt.hashpw(b"MaquitaAdmin2026.", bcrypt.gensalt()).decode()
        await pool.execute(
            """INSERT INTO admin_users (username, password_hash, display_name, role)
               VALUES ($1, $2, $3, $4)""",
            "admin", default_hash, "Administrador", "superadmin",
        )
        logger.info("Default superadmin created: admin / MaquitaAdmin2026.")

    logger.info("Maquita Admin Panel ready on port 8001")
    yield
    await pool.close()


app = FastAPI(
    title="Maquita Mail Admin",
    description="Panel de administracion de correo - Maquita",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    _logging.getLogger("admin").error(f"Unhandled: {exc}\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

# Mount all routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(domains_router)
app.include_router(mailboxes_router)
app.include_router(aliases_router)
app.include_router(queue_router)
app.include_router(tracking_router)
app.include_router(recovery_router)
app.include_router(quarantine_router)
app.include_router(forwarding_router)
app.include_router(health_router)
app.include_router(connections_router)
app.include_router(audit_router)
app.include_router(services_router)
app.include_router(groups_router)
app.include_router(mailviewer_router)
app.include_router(signatures_router)
app.include_router(autoresponder_router)
app.include_router(dnscheck_router)
app.include_router(shared_router)
app.include_router(ai_config_router)
app.include_router(nextcloud_router)
app.include_router(ediscovery_router)
app.include_router(branding_router)


@app.get("/api/health-check")
async def health_check():
    return {"status": "ok", "service": "maquita-admin", "version": "1.0.0"}
