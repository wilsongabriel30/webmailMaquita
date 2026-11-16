# -*- coding: utf-8 -*-
"""Utilidades de las pruebas del explorador: leer sus archivos y pintar la plantilla real.

`codigo_js` devuelve el JavaScript SIN comentarios: una prueba que busca un texto no debe
darse por buena porque ese texto aparezca en un comentario.
"""
import os
import re

from flask import Flask, render_template

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICIO = os.path.join(RAIZ, "servicio")
JS = os.path.join(SERVICIO, "estaticos", "js", "nextcloud")
CSS = os.path.join(SERVICIO, "estaticos", "css", "nextcloud")
PLANTILLA = os.path.join(SERVICIO, "plantillas", "nextcloud", "explorador.html")

_COMENTARIO_JINJA = re.compile(r"\{#.*?#\}|<!--.*?-->", re.S)


def leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def sin_comentarios_js(fuente):
    """Quita los comentarios de un JavaScript respetando las cadenas: «https://…» o un
    '/api/*' dentro de una cadena no son comentarios, y un «/*» dentro de un comentario de
    línea no abre un bloque."""
    salida, i, n, cadena = [], 0, len(fuente), None
    while i < n:
        c, par = fuente[i], fuente[i:i + 2]
        if cadena:
            salida.append(c)
            if c == "\\" and i + 1 < n:
                salida.append(fuente[i + 1])
                i += 1
            elif c == cadena:
                cadena = None
        elif c in "'\"`":
            cadena = c
            salida.append(c)
        elif par == "//":
            while i < n and fuente[i] != "\n":
                i += 1
            continue
        elif par == "/*":
            fin = fuente.find("*/", i + 2)
            i = n if fin < 0 else fin + 2
            continue
        else:
            salida.append(c)
        i += 1
    return "".join(salida)


def codigo_js(nombre):
    """Contenido de un módulo del explorador sin comentarios de bloque ni de línea."""
    return sin_comentarios_js(leer(os.path.join(JS, nombre)))


def plantilla_sin_comentarios():
    return _COMENTARIO_JINJA.sub("", leer(PLANTILLA))


class _Usuario:
    def __init__(self, rol):
        self.username = self.email = "ana.perez@example.org"
        self.nombre = "Ana Perez"
        self.role = rol
        self.profile_picture = ""
        self.is_authenticated = True


def pintar_explorador(vista="archivos", rol="user"):
    """HTML del explorador tal como lo entrega el Almacén del webmail para esa vista y ese rol."""
    app = Flask("prueba_explorador", template_folder=os.path.join(SERVICIO, "plantillas"),
                static_folder=os.path.join(SERVICIO, "estaticos"), static_url_path="/almacen-static")

    @app.context_processor
    def _contexto():
        from flask import url_for as real

        def url_for(endpoint, **valores):       # igual que app_webmail: enlaces ajenos → /webmail
            try:
                return real(endpoint, **valores)
            except Exception:
                return "/webmail"
        return {"url_for": url_for, "dominios_compartir_internos": []}

    permisos = {k: True for k in ("mi_unidad", "compartidos", "recientes", "favoritos", "papelera")}
    with app.test_request_context("/archivos-almacen"):
        html = render_template("nextcloud/explorador.html", ruta_inicial="/", vista=vista, usuario_nextcloud="",
                               modulos_disponibles={}, nube_subperms=permisos, almacen_modo=True,
                               current_user=_Usuario(rol), usuario=_Usuario(rol), drive_name="Nube")
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)
