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
from app.resend.router import router as resend_router  # reenvio de correos rebotados
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
from app import config
from app.ai_config.router import router as ai_config_router
from app.office_config.router import router as office_config_router
from app.voice_config.router import router as voice_config_router
from app.dlp_config.router import router as dlp_config_router
from app.security_policies.router import router as security_policies_router
from app.secure_config.router import router as secure_config_router
from app.safelinks_config.router import router as safelinks_config_router
from app.phish_campaigns.router import router as phish_router
from app.threats.router import router as threats_router
from app.air.router import router as air_router
from app.sso.router import router as sso_router
from app.agents.router import router as agents_router
from app.copiloto.router import router as copiloto_router
from app.conditional_access.router import router as condaccess_router
from app.geo_access.router import router as geoaccess_router
from app.outbound_anomaly.router import router as anomaly_router
from app.outbound.router import router as outbound_router
from app.admin_recovery.router import router as adminrec_router
from app.rag.router import router as rag_router
from app.retention.router import router as retention_router
from app.comm_compliance.router import router as comm_router
from app.insider_risk.router import router as insider_router
from app.ediscovery_premium.router import router as edp_router
from app.advanced_audit.router import router as advanced_audit_router
from app.risky_login.router import router as risky_login_router
from app.antispam_avanzado.router import router as antispam_avanzado_router
from app.zap.router import router as zap_router
from app.safeattach.router import router as safeattach_router

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


_es_dev = config.ENVIRONMENT.lower() in ("development", "dev", "local")
_docs = {} if _es_dev else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(
    title="Maquita Mail Admin",
    description="Panel de administracion de correo - Maquita",
    version="1.0.0",
    lifespan=lifespan,
    **_docs,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
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
app.include_router(resend_router)
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
app.include_router(office_config_router)
app.include_router(voice_config_router)
app.include_router(dlp_config_router)
app.include_router(security_policies_router)
app.include_router(secure_config_router)
app.include_router(safelinks_config_router)
app.include_router(phish_router)
app.include_router(threats_router)
app.include_router(air_router)
app.include_router(sso_router)
app.include_router(agents_router)
app.include_router(copiloto_router)
app.include_router(condaccess_router)
app.include_router(rag_router)
app.include_router(retention_router)
app.include_router(comm_router)
app.include_router(insider_router)
app.include_router(edp_router)
app.include_router(advanced_audit_router)
app.include_router(risky_login_router)
app.include_router(antispam_avanzado_router)
app.include_router(zap_router)
app.include_router(safeattach_router)
app.include_router(nextcloud_router)
app.include_router(ediscovery_router)
app.include_router(branding_router)
app.include_router(geoaccess_router)
app.include_router(anomaly_router)
app.include_router(outbound_router)
app.include_router(adminrec_router)


@app.get("/api/health-check")
async def health_check():
    return {"status": "ok", "service": "maquita-admin", "version": "1.0.0"}
