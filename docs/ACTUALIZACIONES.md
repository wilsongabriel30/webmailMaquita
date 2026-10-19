# Actualizaciones (panel → Protección → Actualizaciones)

Cada servidor (el de la propia institución o la VM de otra organización) se actualiza solo desde este
repositorio. Nunca se edita código en un servidor: todo cambio entra por un PR y llega a los servidores
como versión publicada.

## El flujo, de punta a punta

1. **Cambio** en una rama → PR → integración continua en verde → fusión en `main`.
2. **Producción de referencia** (el servidor de la institución que mantiene el proyecto) se pone al día
   con `main` como hasta ahora (`UPGRADING.md`, `deploy-webmail.sh`). Ahí se prueba con uso real.
3. **Publicar versión** cuando lo de `main` ya está probado en producción:
   ```bash
   git checkout main && git pull
   bash deploy/actualizar/publicar-version.sh v1.8.0
   ```
   Crea la etiqueta `v1.8.0` **firmada** con la clave SSH del equipo, la comprueba contra
   `deploy/actualizar/firmantes` y la sube. Las notas de la versión son los títulos de los commits desde
   la anterior.
4. **Los demás servidores** (canal «estable») la ven esa misma noche: a las 03:30 (más hasta 45 min al
   azar, para no actualizar todos a la vez) buscan, comprueban la firma y, si la actualización automática
   está activada, la instalan. También se puede pulsar «Buscar» e «Instalar ahora» en el panel.

## Qué hace al instalar (`maquita-actualizar`, en segundo plano)

Lo mismo que `UPGRADING.md` manda hacer a mano, en este orden:

| Paso | Detalle |
|---|---|
| Comprobaciones | Sin cambios locales en el código (si los hay, no se actualiza para no pisarlos); al menos 2 GB libres; solo hacia delante (la versión instalada tiene que estar contenida en la nueva). |
| Validación antes | `deploy/tools/validar-despliegue.sh`: se anota el número de fallos. |
| Respaldo | Commit anterior y volcado de `maildb` en `/var/backups/maquita-actualizar/` (se guardan los 3 últimos). |
| Código | `git checkout` de la versión. |
| Dependencias | `pip install -r requirements.txt` en cada entorno de Python que exista. |
| Frontends | Correo (`npm ci` si cambió el package-lock, `deploy-webmail.sh --solo-frontend`) y panel (`npm ci` si cambió, `vite build`). |
| Migraciones | `migrations/*.sql` y `deploy/seeds/*.sql` como el usuario de la aplicación (idempotentes). |
| Secciones | `instalar-app.sh` de cada sección instalada: sitios, DNS, cortafuegos, identidad, chat y el propio actualizador. |
| Ajustes | `deploy/ajustes/aplicar-ajustes.sh --aplicar`. |
| Reinicio | Servicios de la aplicación que estén habilitados (el correo se corta unos 30 s) y recarga de nginx. |
| Validación después | Si hay **más fallos que antes**, vuelve sola a la versión anterior (código, dependencias, frontends, secciones y reinicio). La base no se restaura sola (perdería el correo llegado entretanto): el volcado queda para hacerlo a mano. |

Registro completo de cada actualización en `/var/log/maquita-actualizar/<fecha>.log`; progreso e historial
en `/var/lib/maquita-actualizar/` (los muestra el panel).

## Firma de las versiones

El repositorio es público: cualquiera que consiguiera publicar en él llegaría a todos los servidores si
estos instalaran cualquier etiqueta. Por eso el canal «estable» solo instala etiquetas `vX.Y.Z` con firma
válida de una clave de `deploy/actualizar/firmantes` (copiada en `/etc/maquita-actualizar/firmantes`). Las
etiquetas antiguas, sin firma, no se instalan.

- La clave privada está en el equipo de desarrollo del equipo de tecnología (`/root/.ssh/firma-versiones`).
  Quien la tiene publica versiones: guárdela como una contraseña de administrador.
- Para añadir o cambiar una clave: editar `deploy/actualizar/firmantes` por PR. Los servidores la reciben
  con la versión siguiente (firmada todavía con una clave anterior).

## Canales

- `estable` (por defecto): etiquetas firmadas. Para todos los servidores en uso.
- Una rama (p. ej. `main` o una rama de trabajo): solo en servidores de prueba. Sin firma; el panel lo avisa.

## Instalación

```bash
sudo bash deploy/webmail/instalar-app.sh actualizar
```

Requiere que `/opt/maquita-webmail` sea un clon de git del repositorio. Deja el canal «estable» con la
actualización automática activada; se cambia en el panel.
