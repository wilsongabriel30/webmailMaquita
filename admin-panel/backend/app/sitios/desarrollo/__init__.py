"""Para desarrolladores (v1.11): usuarios de bases con permisos y acceso remoto, cortafuegos de aplicaciones web y
claves SSH de cada sitio. main.py registra todos con `routers`."""

from app.sitios.desarrollo import bases_usuarios, claves_ssh, cortafuegos

routers = [m.router for m in (bases_usuarios, cortafuegos, claves_ssh)]
