# Búsqueda de texto completo y texto de los adjuntos

El correo se busca con el índice nativo de **Dovecot 2.4**: plugin FTS con el motor **fts-flatcurve**
(Xapian, paquete `dovecot-flatcurve` de Debian 13). Busca por remitente, asunto, texto del mensaje y
**texto de los adjuntos** en décimas de segundo, también en buzones de más de cien mil correos.

> En Dovecot 2.4 el motor solo se activa con el bloque `fts flatcurve { }` (aunque esté vacío). Sin él,
> `doveadm fts rescan` responde «fts not enabled for user's namespace» y las búsquedas no usan el índice.

| Parte | Dónde | Qué hace |
|---|---|---|
| Motor e idiomas | `deploy/dovecot/busqueda/` (ajuste 52) | fts-flatcurve, índice al llegar el correo (`fts_autoindex`), español e inglés con tildes y mayúsculas indiferentes, indexación nocturna del correo antiguo. |
| Texto de adjuntos | `deploy/dovecot/fts/` (ajuste 63) | Decodificador propio (`fts_decoder_driver = script`), papelera y no deseado sin indexar al llegar, ayudante `maquita-fts` e indexación inicial. |
| Webmail | `backend/app/mail/` | IMAP `SEARCH`/`SORT` con `BODY`/`TEXT`: Dovecot usa el índice solo. La casilla «Buscar también dentro del texto» dice «y de sus adjuntos» cuando el índice los incluye (`/api/mail/search/capacidades` → `adjuntos`). |
| eDiscovery | `backend/app/compliance/busqueda_doveadm.py` | Las palabras clave van dentro de `doveadm search` (`text …` unidas con OR), así que se responden desde el índice, adjuntos incluidos. |
| Panel | Servicios → «Búsqueda de texto completo» | Estado del índice, buzones indexados, herramientas instaladas y botón «Reindexar buzón». |

## Formatos de adjunto

PDF (`pdftotext`; OCR con Tesseract opcional), DOCX/XLSX/PPTX y sus variantes con macros (solo el
texto: el código VBA ni se abre), ODT/ODS/ODP, Word/Excel/PowerPoint 97-2003 (`catdoc`), RTF, HTML,
ZIP, TAR, gzip, bzip2, xz y 7z (también anidados), y metadatos EXIF de las fotos (`exiftool`). Los
nombres de los archivos dentro de un comprimido también se indexan. El tipo se comprueba por los
primeros bytes, no solo por el MIME declarado: un ejecutable disfrazado de PDF no se abre.

## Seguridad del decodificador

- Corre como **`maquita-fts`**, usuario de sistema sin acceso a los buzones: recibe el adjunto por la
  entrada estándar y devuelve texto. El socket solo lo abre `vmail` (modo 0600).
- Límites (en `/etc/maquita-fts/decodificador.conf`, con topes duros que el archivo no puede pasar):
  adjunto de 50 MB como mucho, 100 MB descomprimidos por adjunto contando los bytes **reales**, 2000
  archivos, 3 niveles de comprimido, proporción de compresión, 4 MB de texto, 20 s por programa
  externo y 60 s por adjunto, 1 GB de memoria (`ulimit`), prioridad baja (`nice`, `ionice`).
- Bombas de descompresión: el presupuesto es común a todos los niveles; un miembro que descomprime
  más de lo que declara corta la lectura. Nada se extrae a disco con su nombre (sin «zip slip»).
- XML con `DOCTYPE` o entidades: se descarta (bombas de entidades). Nunca se ejecutan macros: no se
  usa LibreOffice ni nada que interprete el documento.
- OCR desactivado por defecto: `bash deploy/dovecot/fts/instalar.sh --con-ocr` instala
  `tesseract-ocr` (español e inglés) y lo activa, con un tope de páginas por PDF.

## Instalación

- **Servidores nuevos:** `deploy/webmail/instalar.sh` (paso 10, Dovecot) llama a los dos instaladores.
- **Servidores ya instalados:** `sudo bash deploy/ajustes/aplicar-ajustes.sh --aplicar` (ajustes 52 y
  63), o solo este: `sudo bash deploy/ajustes/63-busqueda-en-adjuntos.sh --simular` y sin `--simular`.

El ajuste 63 instala los paquetes (`poppler-utils`, `catdoc`, `libimage-exiftool-perl`, `7zip`),
respalda `dovecot.conf` (`.bak.FECHA`), valida con `doveconf -n` (si falla, deja todo como estaba),
recarga Dovecot sin cortar conexiones y lanza la **indexación inicial** en segundo plano
(`systemd-run`, `nice 19`, E/S en clase idle, una cuenta a la vez y esperando si el disco está
cargado). `maquita-fts estado` dice cómo va.

**Correo ya indexado antes del ajuste:** Dovecot no vuelve a leer lo que ya tiene en el índice, así
que los adjuntos de esos correos entran al **reindexar el buzón** (panel, o `maquita-fts reindexar
<buzón>`). No se reindexa todo de golpe a propósito: mientras se reconstruye, buscar dentro del texto
de ese buzón tarda más.

## Retenciones legales

El índice es un dato derivado: guarda palabras, no mensajes. Indexar, reindexar o borrar el índice no
modifica ni borra correo, tampoco el que está bajo retención legal. La papelera y el no deseado no se
indexan al llegar, pero siguen siendo buscables (Dovecot indexa lo que falte al buscar dentro del
texto), así que el eDiscovery los encuentra igual. Si los buzones se cifran con `mail_crypt`, el
índice queda fuera de ese cifrado (ver `deploy/dovecot/busqueda/README.md`).
