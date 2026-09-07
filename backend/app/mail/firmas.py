"""Normalización de firmas HTML: lo que se guarda y lo que se envía se ve igual en todos los clientes.

Hallazgo de usuario (07/09/2026): firmas traídas de Zimbra con logos que se veían gigantes en
Outlook y en el celular. La causa no era el editor sino el HTML: imágenes remotas de 1.200 px
con `width="201"`, tablas sin ancho fijo, `margin` en celdas (Outlook lo ignora) y enlaces
`mailto:` que no coincidían con el correo mostrado.

`normalizar_firma(html)` deja la firma en la forma que TODOS los clientes respetan:
1. Saneado con nh3 (misma lista blanca del correo, más `role` en tablas y `tel:` en enlaces).
2. Imágenes: la remota se descarga (5 s, 2 MB, `image/*`), la incrustada se decodifica; ambas
   se redimensionan al ancho declarado (máximo 600) y se guardan con nombre estable en el
   servidor (`/api/firmas/imagen/<hash>.png`). Nunca queda una URL externa. Siempre
   `width`/`height` como atributo y en `style`, con `max-width:100%` y `display:block`.
3. Tablas: `role="presentation"`, sin relleno ni bordes por defecto, ancho fijo máximo 600.
4. `margin` en celdas pasa a `padding`.
5. Un `mailto:` que no coincide con el texto (o con la dirección de la persona) genera un aviso.

Al enviar, `preparar_envio(html)` normaliza el bloque `email-signature`, ajusta las imágenes
del HTML citado (solo tamaño, sin descargar nada) y convierte las imágenes locales en adjuntos
`cid:` para que el destinatario las vea sin cargar nada externo.
"""

import re
from dataclasses import dataclass, field

import nh3
from lxml import html as lhtml

from app.core.css import limpiar_estilo
from app.core.sanitize import ATRIBUTOS_CORREO, ETIQUETAS_CORREO
from app.mail import firmas_imagenes as imagenes

ANCHO_MAX = imagenes.ANCHO_MAX
_PX = re.compile(r"^\s*(\d{1,4})(?:px)?\s*$", re.IGNORECASE)
_ESQUEMAS = {"http", "https", "mailto", "tel", "cid"}


@dataclass
class Resultado:
    html: str
    avisos: list[str] = field(default_factory=list)
    imagenes: int = 0  # imágenes descargadas o convertidas en esta pasada


# --- saneado -------------------------------------------------------------------------------


def _atributos() -> dict:
    atributos = {k: set(v) for k, v in ATRIBUTOS_CORREO.items()}
    atributos.setdefault("table", set()).add("role")
    atributos.setdefault("td", set()).add("width")
    atributos.setdefault("th", set()).add("width")
    return atributos


def _filtro(elemento: str, atributo: str, valor: str):
    if atributo == "style":
        return limpiar_estilo(valor)
    if atributo in ("href", "src") and valor.strip().lower().startswith("data:"):
        # Solo una imagen puede venir incrustada; se convierte a archivo en el paso siguiente.
        return valor if elemento == "img" and atributo == "src" else None
    return valor


def sanear(html: str, con_data: bool) -> str:
    esquemas = _ESQUEMAS | ({"data"} if con_data else set())
    return nh3.clean(
        html,
        tags=set(ETIQUETAS_CORREO),
        attributes=_atributos(),
        url_schemes=esquemas,
        attribute_filter=_filtro,
    )


# --- utilidades de estilo y árbol -----------------------------------------------------------


def _px(valor: str | None) -> int | None:
    m = _PX.match(valor or "")
    return int(m.group(1)) if m else None


def _estilo(elemento) -> dict[str, str]:
    salida: dict[str, str] = {}
    for declaracion in (elemento.get("style") or "").split(";"):
        if ":" in declaracion:
            k, v = declaracion.split(":", 1)
            if k.strip() and v.strip():
                salida[k.strip().lower()] = v.strip()
    return salida


def _poner_estilo(elemento, estilo: dict[str, str]) -> None:
    texto = "; ".join(f"{k}: {v}" for k, v in estilo.items())
    if texto:
        elemento.set("style", texto)
    elif "style" in elemento.attrib:
        del elemento.attrib["style"]


def _parsear(html: str):
    return lhtml.fragment_fromstring(html or "", create_parent="div")


def _serializar(raiz) -> str:
    partes = [raiz.text or ""]
    partes += [
        lhtml.tostring(hijo, encoding="unicode", with_tail=True) for hijo in raiz
    ]
    return "".join(partes)


def _dentro_de(elemento, etiqueta: str) -> bool:
    return any(a.tag == etiqueta for a in elemento.iterancestors())


def _corto(texto: str, n: int = 70) -> str:
    return texto if len(texto) <= n else texto[: n - 1] + "…"


# --- pasos ----------------------------------------------------------------------------------


def _fijar_tamano(img, ancho: int | None, alto: int | None) -> None:
    estilo = _estilo(img)
    if ancho:
        img.set("width", str(ancho))
        estilo["width"] = f"{ancho}px"
    if alto:
        img.set("height", str(alto))
        estilo["height"] = f"{alto}px"
    estilo["max-width"] = "100%"
    estilo["display"] = "block"
    estilo.setdefault("border", "0")
    _poner_estilo(img, estilo)


def _ancho_declarado(img) -> int | None:
    ancho = _px(img.get("width")) or _px(_estilo(img).get("width"))
    return min(ancho, ANCHO_MAX) if ancho else None


def _procesar_imagen(img, descargar: bool, resultado: Resultado) -> None:
    src = (img.get("src") or "").strip()
    declarado = _ancho_declarado(img)
    try:
        if src.startswith("cid:"):
            _fijar_tamano(img, declarado, _px(img.get("height")) if declarado else None)
            return
        if src.startswith(imagenes.RUTA_PUBLICA):
            info = imagenes.imagen_local(src)
            if info is None:
                raise imagenes.ImagenRechazada("ya no está en el servidor")
            if declarado and declarado < info.ancho:
                datos = imagenes.leer_local(info.nombre) or b""
                info = imagenes.guardar_redimensionada(datos, declarado)
                resultado.imagenes += 1
        elif src.lower().startswith("data:"):
            info = imagenes.guardar_redimensionada(
                imagenes.decodificar_data(src), declarado
            )
            resultado.imagenes += 1
        elif src.lower().startswith(("http://", "https://")):
            if not descargar:
                raise imagenes.ImagenRechazada("es una dirección externa")
            info = imagenes.guardar_redimensionada(imagenes.descargar(src), declarado)
            resultado.imagenes += 1
        else:
            raise imagenes.ImagenRechazada("origen no admitido")
    except imagenes.ImagenRechazada as exc:
        resultado.avisos.append(
            f"Se quitó la imagen «{_corto(src) or 'sin origen'}»: {exc}."
        )
        padre = img.getparent()
        if padre is not None:
            if img.tail:
                anterior = img.getprevious()
                if anterior is not None:
                    anterior.tail = (anterior.tail or "") + img.tail
                else:
                    padre.text = (padre.text or "") + img.tail
            padre.remove(img)
        return
    img.set("src", info.src)
    _fijar_tamano(img, info.ancho, info.alto)


def _procesar_tabla(tabla) -> None:
    tabla.set("role", "presentation")
    for atributo in ("cellpadding", "cellspacing", "border"):
        if tabla.get(atributo) is None:
            tabla.set(atributo, "0")
    estilo = _estilo(tabla)
    ancho = _px(tabla.get("width")) or _px(estilo.get("width"))
    if ancho is None and not _dentro_de(tabla, "table"):
        ancho = ANCHO_MAX  # la tabla exterior siempre lleva ancho fijo
    if ancho is not None:
        ancho = min(ancho, ANCHO_MAX)
        tabla.set("width", str(ancho))
        estilo["width"] = f"{ancho}px"
    estilo["max-width"] = "100%"
    estilo.setdefault("border-collapse", "collapse")
    _poner_estilo(tabla, estilo)


def _procesar_celda(celda) -> None:
    estilo = _estilo(celda)
    for clave in [k for k in estilo if k.startswith("margin")]:
        valor = estilo.pop(clave)
        estilo.setdefault(clave.replace("margin", "padding", 1), valor)
    ancho = _px(celda.get("width"))
    if ancho and ancho > ANCHO_MAX:
        celda.set("width", str(ANCHO_MAX))
    _poner_estilo(celda, estilo)


def _revisar_mailto(enlace, correo_usuario: str | None, avisos: list[str]) -> None:
    href = (enlace.get("href") or "").strip()
    if not href.lower().startswith("mailto:"):
        return
    destino = href[7:].split("?")[0].strip().lower()
    texto = (enlace.text_content() or "").strip().lower()
    if "{{" in destino or "{{" in texto:
        return  # plantilla del panel: se rellena después
    if "@" in texto and texto != destino:
        avisos.append(f"El enlace de correo apunta a {destino} pero muestra {texto}.")
    elif correo_usuario and destino != correo_usuario.strip().lower():
        avisos.append(
            f"El enlace de correo apunta a {destino}, no a tu dirección {correo_usuario}."
        )


# --- API ------------------------------------------------------------------------------------


def normalizar_firma(
    html: str, correo_usuario: str | None = None, descargar: bool = True
) -> Resultado:
    """Devuelve la firma normalizada y los avisos para la persona (imágenes quitadas, mailto)."""
    resultado = Resultado(html="")
    if not (html or "").strip():
        return resultado
    raiz = _parsear(sanear(html, con_data=True))
    for img in list(raiz.iter("img")):
        _procesar_imagen(img, descargar, resultado)
    for tabla in raiz.iter("table"):
        _procesar_tabla(tabla)
    for celda in raiz.iter("td", "th"):
        _procesar_celda(celda)
    for enlace in raiz.iter("a"):
        _revisar_mailto(enlace, correo_usuario, resultado.avisos)
    # Segunda pasada sin `data:`: garantiza que nada incrustado ni externo sobrevive.
    resultado.html = sanear(_serializar(raiz), con_data=False)
    return resultado


def _ajustar_imagen_citada(img) -> None:
    """Solo tamaño: el HTML citado no se descarga ni se reescribe."""
    estilo = _estilo(img)
    ancho = _px(img.get("width")) or _px(estilo.get("width"))
    alto = _px(img.get("height")) or _px(estilo.get("height"))
    if ancho:
        img.set("width", str(ancho))
        estilo["width"] = f"{ancho}px"
        if alto:
            img.set("height", str(alto))
            estilo["height"] = f"{alto}px"
    else:
        estilo.setdefault("height", "auto")
    estilo["max-width"] = "100%"
    _poner_estilo(img, estilo)


def normalizar_html_citado(html: str) -> str:
    """Imágenes del cuerpo y de lo citado con `max-width:100%` y su tamaño declarado en `style`."""
    if not html or "<img" not in html.lower():
        return html
    try:
        raiz = _parsear(html)
    except Exception:
        return html
    for img in raiz.iter("img"):
        _ajustar_imagen_citada(img)
    return _serializar(raiz)


def _es_bloque_firma(elemento) -> bool:
    return (
        elemento.tag == "div"
        and "email-signature" in (elemento.get("class") or "").split()
    )


def preparar_envio(html: str) -> tuple[str, list[dict], list[str]]:
    """HTML listo para salir: firma normalizada, citado ajustado e imágenes locales como `cid:`.

    Devuelve (html, adjuntos_inline, avisos); cada adjunto tiene la forma que espera el
    envío (`filename`, `content`, `content_type`, `is_inline`, `cid`).
    """
    if not html or "<img" not in html.lower():
        return html, [], []
    try:
        raiz = _parsear(html)
    except Exception:
        return html, [], []
    avisos: list[str] = []
    for bloque in [e for e in raiz.iter("div") if _es_bloque_firma(e)]:
        normalizada = normalizar_firma(_serializar(bloque))
        avisos += normalizada.avisos
        for hijo in list(bloque):
            bloque.remove(hijo)
        nuevo = _parsear(normalizada.html)
        bloque.text = nuevo.text
        for hijo in nuevo:
            bloque.append(hijo)
    adjuntos: dict[str, dict] = {}
    for img in raiz.iter("img"):
        src = (img.get("src") or "").strip()
        if src.startswith(imagenes.RUTA_PUBLICA):
            nombre = src[len(imagenes.RUTA_PUBLICA) :]
            datos = imagenes.leer_local(nombre)
            if datos is None:
                continue
            cid = f"{nombre[:-4]}@firma"
            img.set("src", f"cid:{cid}")
            adjuntos.setdefault(
                cid,
                {
                    "filename": nombre,
                    "content": datos,
                    "content_type": "image/png",
                    "is_inline": True,
                    "cid": cid,
                },
            )
        elif not _dentro_de(img, "div") or not any(
            _es_bloque_firma(a) for a in img.iterancestors()
        ):
            _ajustar_imagen_citada(img)
    return _serializar(raiz), list(adjuntos.values()), avisos
