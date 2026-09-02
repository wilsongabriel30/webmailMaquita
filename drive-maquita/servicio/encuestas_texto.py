# -*- coding: utf-8 -*-
"""
Formularios del Almacén — texto con formato (negrita, cursiva, subrayado, fuente)

Los títulos y descripciones admiten formato, como en Google Forms. Se guardan
como HTML, así que TODO lo que entra pasa por aquí antes de tocar el disco y
antes de servirse: el `.forma` es un archivo del Drive y cualquiera puede
subirlo editado a mano, de modo que el saneamiento es la frontera de seguridad,
no una comodidad del editor.

Criterio: lista BLANCA cerrada. Lo que no está permitido no se filtra ni se
intenta arreglar — se descarta la etiqueta y se conserva su texto.

Permitido:
    <b> <i> <u> <br> <span style="font-family: ..."> <a href="...">

Todo lo demás (script, style, img, on*, javascript:, style libre, atributos
sueltos) desaparece. Los <div> y <p> que mete el navegador al pulsar Intro se
convierten en <br>, que es lo que la persona quiso decir.

Sobre los enlaces (27/08/2026): se admiten SOLO `http`, `https` y `mailto`.
`javascript:` y `data:` son las dos formas clásicas de convertir un enlace en
código, y `data:` además permite servir una página entera desde nuestro dominio.
Lo que se guarda no es lo que se escribió: el destino se reconstruye desde sus
piezas y se le añaden siempre `target="_blank"` y
`rel="noopener noreferrer nofollow"` —sin `noopener`, la página de destino puede
manipular la pestaña del formulario y llevarse a quien responde a otro sitio.

Autoría: Equipo de Tecnología Maquita — 2026-08-25
"""
import re
from html import escape
from html.parser import HTMLParser

# Debe coincidir con FUENTES de encuestas_modelo. Se recibe por parámetro para
# no crear un import circular entre los dos módulos.
ETIQUETAS = ('b', 'i', 'u')
SALTOS = ('br',)
BLOQUES = ('div', 'p')          # del navegador: se traducen a salto de línea
# De estas no se copia ni el texto: «<script>alert(1)</script>» no es peligroso
# una vez escapado, pero dejar «alert(1)» a la vista en un título es basura.
MUDAS = ('script', 'style', 'template', 'noscript', 'title', 'head')
LIMITE_HTML = 8000              # tope duro del HTML resultante

_FUENTE = re.compile(r'font-family\s*:\s*([^;]+)', re.I)


class _Saneador(HTMLParser):
    """Reconstruye el HTML dejando solo lo permitido y cerrando bien todo."""

    def __init__(self, fuentes_validas, maximo_texto):
        super().__init__(convert_charrefs=True)
        self.fuentes = {f.lower(): f for f in fuentes_validas}
        self.maximo = maximo_texto
        self.partes = []
        self.pila = []          # etiquetas abiertas, para cerrarlas en orden
        self.largo = 0          # longitud del TEXTO visible, no del HTML
        self.mudo = 0           # profundidad dentro de una etiqueta MUDA

    # -- texto ---------------------------------------------------------
    def handle_data(self, dato):
        if self.mudo or self.largo >= self.maximo:
            return
        dato = dato[:self.maximo - self.largo]
        self.largo += len(dato)
        self.partes.append(escape(dato, quote=False))

    # -- apertura ------------------------------------------------------
    def handle_starttag(self, etiqueta, atributos):
        etiqueta = etiqueta.lower()

        if etiqueta in MUDAS:
            self.mudo += 1
            self.pila.append(None)
            return
        if self.mudo:
            self.pila.append(None)
            return

        if etiqueta in SALTOS:
            self.partes.append('<br>')
            return

        if etiqueta in ('strong',):
            etiqueta = 'b'
        elif etiqueta in ('em',):
            etiqueta = 'i'

        if etiqueta in ETIQUETAS:
            self.partes.append('<' + etiqueta + '>')
            self.pila.append(etiqueta)
            return

        if etiqueta == 'a':
            destino = self._enlace_de(atributos)
            if destino:
                self.partes.append(
                    '<a href="' + destino + '" target="_blank" '
                    'rel="noopener noreferrer nofollow">')
                self.pila.append('a')
            else:
                # Enlace con destino inaceptable: se tira el enlace y se
                # conserva su texto, para no dejar a nadie sin lo que escribió.
                self.pila.append(None)
            return

        if etiqueta == 'span':
            fuente = self._fuente_de(atributos)
            if fuente:
                self.partes.append(
                    '<span style="font-family:\'' + fuente + '\'">')
                self.pila.append('span')
            else:
                # Un span sin fuente válida no aporta nada: se ignora la
                # etiqueta, pero su texto se conserva.
                self.pila.append(None)
            return

        if etiqueta in BLOQUES:
            # El primer bloque no lleva salto: el navegador envuelve la primera
            # línea en un <div> y añadirlo dejaría el texto con un hueco arriba.
            if self.partes:
                self.partes.append('<br>')
            self.pila.append(None)
            return

        # Cualquier otra etiqueta: se descarta. Si es de las que llevan cierre,
        # se apila un hueco para no descuadrar la pila al cerrarla.
        if etiqueta not in ('img', 'input', 'hr', 'meta', 'link'):
            self.pila.append(None)

    def handle_startendtag(self, etiqueta, atributos):
        if etiqueta.lower() in SALTOS:
            self.partes.append('<br>')

    # -- cierre --------------------------------------------------------
    def handle_endtag(self, etiqueta):
        if etiqueta.lower() in MUDAS and self.mudo:
            self.mudo -= 1
        if not self.pila:
            return
        abierta = self.pila.pop()
        if abierta:
            self.partes.append('</' + abierta + '>')

    # -- lo que nunca se copia ----------------------------------------
    def handle_comment(self, dato):
        pass

    def handle_decl(self, dato):
        pass

    def unknown_decl(self, dato):
        pass

    def handle_pi(self, dato):
        pass

    # -- utilidades ----------------------------------------------------
    def _fuente_de(self, atributos):
        for nombre, valor in atributos:
            if nombre.lower() != 'style' or not valor:
                continue
            hallazgo = _FUENTE.search(valor)
            if not hallazgo:
                continue
            pedida = hallazgo.group(1).strip().strip('"\'').strip()
            # Solo fuentes de la lista: un font-family libre permite colar
            # url(...) y otras expresiones dentro del atributo style.
            return self.fuentes.get(pedida.lower())
        return None

    def _enlace_de(self, atributos):
        """Destino seguro del enlace, o None si no se puede admitir.

        No se «limpia» lo recibido: se comprueba y se vuelve a escribir desde
        `urlsplit`, que es lo que impide colar cosas por la forma de escribir la
        dirección (espacios, saltos de línea o mayúsculas dentro del esquema,
        que es como se disfraza `javascript:`).
        """
        for nombre, valor in atributos:
            if nombre.lower() != 'href' or not valor:
                continue
            return _destino_seguro(valor)
        return None

    def resultado(self):
        while self.pila:
            abierta = self.pila.pop()
            if abierta:
                self.partes.append('</' + abierta + '>')
        return ''.join(self.partes)[:LIMITE_HTML]


ESQUEMAS = ('http', 'https', 'mailto')
LIMITE_ENLACE = 2000       # una dirección más larga que esto no es una dirección


def _destino_seguro(bruto):
    """Dirección admisible para un enlace, o None.

    Se reconstruye desde las piezas que devuelve `urlsplit` en vez de devolver
    lo recibido: así una dirección escrita de forma retorcida
    (`java\\nscript:`, `JaVaScRiPt:`, con espacios delante) no puede colarse por
    parecer otra cosa.
    """
    from urllib.parse import urlsplit, urlunsplit
    texto = str(bruto or '').strip()
    # Los caracteres de control se quitan ANTES de mirar el esquema: son el
    # truco de siempre para partir la palabra «javascript» por la mitad.
    texto = ''.join(c for c in texto if ord(c) >= 32 and c != '\x7f')
    if not texto or len(texto) > LIMITE_ENLACE:
        return None
    try:
        partes = urlsplit(texto)
    except ValueError:
        return None

    esquema = (partes.scheme or '').lower()
    if not esquema:
        # Lo normal al escribirla a mano: «maquita.com.ec». Se asume https,
        # nunca http: si el sitio no lo admite, mejor que falle a la vista que
        # mandar a la gente por una conexión sin cifrar.
        if texto.startswith('//') or texto.startswith('/'):
            return None      # rutas del propio sitio: no son enlaces externos
        try:
            partes = urlsplit('https://' + texto)
        except ValueError:
            return None
        esquema = 'https'
    if esquema not in ESQUEMAS:
        return None
    if esquema in ('http', 'https') and not partes.netloc:
        return None
    if esquema == 'mailto' and '@' not in partes.path:
        return None

    limpia = urlunsplit((esquema, partes.netloc, partes.path,
                         partes.query, partes.fragment))
    return escape(limpia, quote=True)


def sanear(bruto, fuentes_validas, maximo_texto=500):
    """Devuelve HTML seguro con solo el formato permitido."""
    if bruto is None:
        return ''
    texto = str(bruto)
    if not texto.strip():
        return ''
    saneador = _Saneador(fuentes_validas, maximo_texto)
    try:
        saneador.feed(texto)
        saneador.close()
    except Exception:
        # Ante un HTML que ni siquiera se puede parsear, se guarda el texto
        # plano escapado: nunca el original.
        return escape(quitar_etiquetas(texto)[:maximo_texto], quote=False)
    return saneador.resultado()


_ETIQUETA = re.compile(r'<[^>]*>')
_ESPACIOS = re.compile(r'\s+')


def quitar_etiquetas(html_texto):
    """Texto plano. Lo usan el Excel, la tabla, el título de la pestaña y todo
    lo que no puede mostrar formato."""
    if html_texto is None:
        return ''
    from html import unescape
    plano = _ETIQUETA.sub(' ', str(html_texto))
    return _ESPACIOS.sub(' ', unescape(plano)).strip()
