# Soporte y versiones

Qué versiones reciben parches, durante cuánto tiempo, cómo se publican y cómo llegan a los servidores.
Complementa a [SECURITY.md](../SECURITY.md) (cómo reportar una vulnerabilidad),
[RELEASE_PROCESS.md](RELEASE_PROCESS.md) (cómo se prepara una versión) y
[ACTUALIZACIONES.md](ACTUALIZACIONES.md) (cómo se instala en cada servidor).

## Numeración

Versionado semántico `vMAYOR.MENOR.PARCHE`:

- **PARCHE** (`v1.11.3`): correcciones y parches de seguridad. Nunca cambia la API, el esquema de la
  base de forma incompatible ni el comportamiento de serie.
- **MENOR** (`v1.12.0`): funciones nuevas compatibles hacia atrás. Las migraciones solo añaden.
- **MAYOR** (`v2.0.0`): puede romper compatibilidad; se anuncia con al menos 6 meses y una guía en
  [UPGRADING.md](../UPGRADING.md).

## Canales de actualización

| Canal | Qué instala | Para quién |
|---|---|---|
| `estable` (de serie) | La última etiqueta `vX.Y.Z` firmada, sea de la serie que sea | La mayoría: siempre la última versión |
| `estable-X.Y` (p. ej. `estable-1.11`) | Solo etiquetas `vX.Y.*` firmadas: parches de esa serie, sin saltar a la siguiente | Organizaciones que prefieren cambiar de versión menor cuando ellas decidan (soporte largo) |
| nombre de una rama (`main`…) | La punta de la rama, **sin firma** | Solo servidores de prueba |

El canal se elige en el panel (Protección → Actualizaciones) o en `/etc/maquita-actualizar/config.json`.
Los dos canales «estable» exigen firma: una etiqueta sin firma válida no se instala nunca. Un canal que
empieza por `estable-` y no es `estable-X.Y` se rechaza (no se toma por una rama sin firma).

## Cuánto dura el soporte

| Tipo de versión | Parches de seguridad | Correcciones de errores |
|---|---|---|
| Serie de **soporte largo** (LTS): una por año, anunciada en el CHANGELOG | **24 meses** desde su `X.Y.0` | 12 meses |
| Resto de series menores | Hasta 3 meses después de publicada la siguiente menor | Hasta publicarse la siguiente menor |
| Series sin soporte | Ninguno: actualice | — |

- La **primera serie de soporte largo propuesta es la 1.11** (provisional: lo será al publicarse
  `v1.11.0` firmada). Mientras tanto la tabla de [SECURITY.md](../SECURITY.md) manda.
- Al terminar el soporte de una serie LTS tiene que haber otra LTS publicada desde hace al menos 6
  meses, para que el salto se haga con tiempo.
- «Parche de seguridad» incluye las dependencias (Python, npm, paquetes del sistema que instala el
  proyecto, como el ajuste de PHP o la imagen de Z-Push), no solo el código propio.
- Plazos de corrección según la severidad: los de [SECURITY.md](../SECURITY.md) (15 días hábiles para
  crítica o alta, 30 para media o baja); en las series LTS se aplican igual.

## Cómo se publica un parche

1. **Corrección en `main`** por PR, con su prueba y con la integración continua en verde.
2. **Llevarla a las ramas de soporte** que la necesiten: `git checkout estable/1.11 && git cherry-pick
   <commit>` (o la corrección adaptada, si el código cambió), PR contra `estable/1.11`, CI en verde.
   La rama `estable/X.Y` nace de la etiqueta `vX.Y.0` cuando la serie se declara LTS.
3. **Publicar**, en el equipo que tiene la clave de firma:
   ```bash
   bash deploy/actualizar/publicar-version.sh v1.12.1                        # serie actual (main)
   RAMA=estable/1.11 bash deploy/actualizar/publicar-version.sh v1.11.4      # rama de soporte
   ```
   El script exige que HEAD sea la punta de esa rama en el repositorio, que la versión sea mayor que la
   última de su serie (y de la serie de la rama, en el caso LTS), firma la etiqueta con la clave SSH del
   equipo, la verifica contra `deploy/actualizar/firmantes` y la sube.
4. **Aviso**: entrada en [CHANGELOG.md](../CHANGELOG.md) con sección «Seguridad» (CVE si lo hay, a qué
   versiones afecta y qué hacer) y, si es una vulnerabilidad, aviso de seguridad de GitHub
   (Security → Advisories) cuando el parche ya está publicado.
5. **Llegada a los servidores**: los de canal `estable` o `estable-X.Y` con actualización automática la
   instalan esa misma noche (03:30 más hasta 45 minutos al azar), con respaldo previo y vuelta atrás
   automática si la validación empeora. Ver [ACTUALIZACIONES.md](ACTUALIZACIONES.md).

## Comprobar una versión a mano

```bash
git fetch --tags
git -c gpg.format=ssh -c gpg.ssh.allowedSignersFile=deploy/actualizar/firmantes verify-tag v1.11.4
```

Una etiqueta que no pasa esta comprobación no es del equipo, aunque esté en el repositorio.

## Clústeres (varias réplicas)

El actualizador automático está pensado para una sola máquina (reinicia todos los servicios a la vez).
Con 2+ réplicas detrás de un balanceador ([GRAN-ESCALA.md](GRAN-ESCALA.md)):

- Desactive la actualización automática en los nodos de aplicación y actualice con
  `deploy/escala/actualizar-sin-corte.sh` (`PASO_PREVIO` hace el `git checkout` de la etiqueta firmada
  y la instalación de dependencias en cada nodo), después de comprobar la firma como arriba.
- Lance las migraciones una vez, antes del primer nodo. Dentro de una misma serie (y siempre en los
  parches) las migraciones solo añaden, así que la versión anterior sigue funcionando mientras conviven.

## API

- Las rutas `/api/...` de siempre siguen funcionando.
- `/api/v1/...` es la **versión estable** de la API del webmail: hoy es la misma API (un alias), con
  el compromiso de que dentro de la serie 1.x no se elimina ni cambia de forma incompatible ninguna ruta
  ni campo de respuesta. Lo nuevo se añade; lo que se retire se marca obsoleto en el CHANGELOG al menos
  una versión menor antes y sigue funcionando hasta la siguiente mayor. Las respuestas por `/api/v1`
  llevan la cabecera `API-Version: 1`.
- Una futura `/api/v2` (vista previa) convivirá con `/api/v1` mientras esta tenga soporte.
- Especificación: `docs/api/webmail-openapi.json` y `docs/api/panel-openapi.json`, regeneradas con
  `python3 scripts/exportar-openapi.py` (`--comprobar` falla si están desactualizadas; `webmail --v1`
  genera la copia con las rutas `/api/v1` para crear clientes con un generador de OpenAPI).
- La API del panel de administración es interna (la usa su interfaz) y no tiene compromiso de
  estabilidad.
