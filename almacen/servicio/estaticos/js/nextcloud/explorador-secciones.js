/**
 * explorador-secciones.js  -  Módulo: sección que se está viendo y su título
 * Responsabilidad ÚNICA: decidir a qué sección corresponde una carga (Mi unidad, Papelera,
 * Destacados, Recientes, Compartido conmigo) y escribir su nombre en el encabezado y en la
 * pestaña del navegador.
 *
 * En el Almacén del webmail el servidor abre cada sección con una `vista` y ruta '/': quien
 * mire solo la ruta cree que siempre está en «Mi unidad» (el encabezado no cambiaba nunca).
 *
 * Depende de: vistaActual (plantilla). Cargar ANTES de explorador-navegacion.js.
 */

const TITULOS_SECCION = {
    archivos: 'Mi unidad',
    unidades: 'Unidades compartidas',
    compartidos: 'Compartido conmigo',
    compartidos_por_mi: 'Compartido por mí',
    papelera: 'Papelera',
    favoritos: 'Destacados',
    recientes: 'Recientes'
};

/** Sección de una carga, con la misma precedencia con que cargarArchivos elige la API:
 *  primero la ruta pedida, después la vista con la que el servidor abrió la página. */
function seccionDeCarga(ruta) {
    const r = String(ruta || '').replace(/\/+$/, '');
    const vista = typeof vistaActual !== 'undefined' ? vistaActual : 'archivos';
    if (r === '/compartidos') return 'compartidos';
    if (r === '/compartidos_por_mi') return 'compartidos_por_mi';
    if (r === '/papelera' || vista === 'papelera') return 'papelera';
    if (r === '/favoritos' || vista === 'favoritos') return 'favoritos';
    if (r === '/recientes' || vista === 'recientes') return 'recientes';
    if (vista === 'compartidos' && r === '') return 'compartidos';
    if (r === '/unidades' || r.startsWith('/unidades/')) return 'unidades';
    return 'archivos';
}

function tituloDeSeccion(seccion) {
    return TITULOS_SECCION[seccion] || TITULOS_SECCION.archivos;
}

/** Escribe el nombre de la sección en el encabezado y en el título de la pestaña. */
function actualizarTituloSeccion(seccion) {
    const titulo = tituloDeSeccion(seccion);
    const encabezado = document.getElementById('sectionTitle');
    if (encabezado) encabezado.textContent = titulo;
    const partes = document.title.split(' - ');
    document.title = titulo + (partes.length > 1 ? ' - ' + partes.slice(1).join(' - ') : '');
}
