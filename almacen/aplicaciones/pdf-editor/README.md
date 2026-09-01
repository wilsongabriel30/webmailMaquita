# Editor de PDF — Aplicación del Drive Maquita

Herramienta para **anotar, firmar y rellenar PDF** que se abre desde el
[Drive Maquita (Almacén)](../../README.md) y trabaja los archivos del Drive.

- Firma digital con certificados `.p12`/`.pfx` (la clave maestra de cifrado se
  genera en el servidor, nunca viaja en el código).
- Anotaciones, formularios y visor.
- Arquitectura hexagonal: `dominio/`, `aplicacion/`, `infraestructura/`, `interfaces/`.

## Estado

- **Fase 1 (hecha):** código base traído y auditado (sin secretos, sin IPs internas).
- **Fase 2 (pendiente):** empaquetado como app autónoma del Drive:
  - Resolver la dependencia `from config import Config` con una configuración propia.
  - Autenticación por el **token del usuario del Drive** (igual que el resto del
    Almacén: cookie `access_token`, sesión viva).
  - Abrir un PDF desde el Drive y **guardarlo de vuelta** en la misma ruta.

Hasta completar la Fase 2, este directorio es el **código fuente de referencia**, no
un servicio listo para arrancar por sí solo.
