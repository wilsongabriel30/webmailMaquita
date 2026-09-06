/* [A-13] Escape de HTML para TODO lo que el explorador pinta con innerHTML a partir de
 * datos (nombres de archivos y carpetas, rutas, nombres de personas). Se carga antes que
 * el resto de explorador-*.js. El backend además rechaza < > " ' \ y caracteres de control
 * en nombres nuevos, pero los nombres antiguos y los datos de otras fuentes pasan por aquí. */
function escHtml(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
}
