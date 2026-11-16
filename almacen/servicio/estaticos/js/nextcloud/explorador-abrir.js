/**
 * explorador-abrir.js  -  Módulo: abrir archivos que el visor general no atiende en el Almacén
 * Responsabilidad ÚNICA: decidir qué pasa al abrir (doble clic, Intro, «Abrir») un archivo de
 * texto o un diagrama cuando el explorador trabaja con el Almacén del webmail.
 *
 * - Texto (.txt, .md, .log): se muestra en un visor de solo lectura. Antes caía en «otros
 *   archivos» y el doble clic lo descargaba: para la persona, «no se abre». No se ofrece
 *   editarlo en línea: no está comprobado que el guardado del editor conserve el texto plano.
 * - Diagramas (.drawio): el Almacén del webmail no tiene editor de diagramas ni las rutas
 *   /drawio/* del contrato; el visor pedía /drawio/contenido y respondía «No se pudo cargar
 *   el diagrama». Se dice con claridad y se ofrece la descarga.
 *
 * Depende de: API_BASE, MODO_ALMACEN, EXTENSIONES_DRAWIO (config.js), escHtml (escape.js), Swal.
 * abrirArchivo (interactions.js) lo consulta en el momento de abrir.
 */

const EXTENSIONES_TEXTO_VISOR = ['txt', 'md', 'log'];
const LIMITE_VISOR_TEXTO = 200000;   // caracteres que se pintan; el resto, por descarga

function _nombreDeRuta(ruta) {
    return String(ruta || '').split('/').pop();
}

function _urlDescarga(ruta) {
    return API_BASE + '/archivos/descargar?ruta=' + encodeURIComponent(ruta);
}

/** Bytes → texto. Los archivos de texto antiguos suelen venir en Windows-1252, no en UTF-8. */
function decodificarTexto(bytes) {
    try {
        return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    } catch (e) {
        return new TextDecoder('windows-1252').decode(bytes);
    }
}

async function abrirVisorTexto(ruta) {
    const nombre = _nombreDeRuta(ruta);
    Swal.fire({ title: 'Abriendo…', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
    let texto;
    try {
        const respuesta = await fetch(API_BASE + '/archivos/ver?ruta=' + encodeURIComponent(ruta) + '&_t=' + Date.now(),
            { credentials: 'same-origin', cache: 'no-store' });
        if (!respuesta.ok) throw new Error('HTTP ' + respuesta.status);
        texto = decodificarTexto(await respuesta.arrayBuffer());
    } catch (e) {
        Swal.fire('No se pudo abrir', 'No fue posible leer «' + nombre + '». Inténtelo de nuevo o descárguelo.', 'error');
        return;
    }
    const recortado = texto.length > LIMITE_VISOR_TEXTO;
    const cuerpo = texto.length
        ? '<pre id="visorTexto" style="text-align:left;white-space:pre-wrap;word-break:break-word;max-height:60vh;overflow:auto;'
            + 'margin:0;padding:12px;background:#f8f9fa;border:1px solid #dadce0;border-radius:8px;font-size:13px;line-height:1.5;">'
            + escHtml(recortado ? texto.slice(0, LIMITE_VISOR_TEXTO) : texto) + '</pre>'
        : '<p id="visorTexto" style="color:#5f6368;margin:12px 0;">El archivo está vacío.</p>';
    const nota = recortado
        ? '<p style="color:#5f6368;font-size:12px;margin:8px 0 0;">Se muestra solo el comienzo. Descargue el archivo para verlo completo.</p>'
        : '';
    const resultado = await Swal.fire({
        title: escHtml(nombre),
        html: cuerpo + nota,
        width: 820,
        showCloseButton: true,
        showCancelButton: true,
        confirmButtonText: 'Descargar',
        confirmButtonColor: '#1a73e8',
        cancelButtonText: 'Cerrar'
    });
    if (resultado.isConfirmed) window.location.href = _urlDescarga(ruta);
}

async function avisarDiagramaSinEditor(ruta) {
    const resultado = await Swal.fire({
        icon: 'info',
        title: 'Diagrama',
        text: 'Esta nube no tiene editor de diagramas. Puede descargar «' + _nombreDeRuta(ruta)
            + '» y abrirlo con un programa de diagramas compatible con draw.io.',
        showCancelButton: true,
        confirmButtonText: 'Descargar',
        cancelButtonText: 'Cerrar',
        confirmButtonColor: '#1a73e8'
    });
    if (resultado.isConfirmed) window.location.href = _urlDescarga(ruta);
}

/** Lo consulta abrirArchivo antes de decidir. Devuelve true si este módulo se ocupa. */
function abrirArchivoPropio(ruta, ext) {
    if (typeof MODO_ALMACEN === 'undefined' || !MODO_ALMACEN) return false;
    if (EXTENSIONES_TEXTO_VISOR.includes(ext)) {
        abrirVisorTexto(ruta);
        return true;
    }
    if (EXTENSIONES_DRAWIO.includes(ext)) {
        avisarDiagramaSinEditor(ruta);
        return true;
    }
    return false;
}
