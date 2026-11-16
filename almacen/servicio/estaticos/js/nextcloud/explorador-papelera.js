/**
 * explorador-papelera.js  -  Módulo: la sección «Papelera»
 * Responsabilidad ÚNICA: lo que cambia en la interfaz cuando se mira la Papelera:
 *   - el menú del elemento ofrece «Restaurar» y «Eliminar definitivamente» (no el menú de
 *     siempre, que terminaba en «Mover a la papelera»);
 *   - una franja con el número de elementos y el botón «Vaciar papelera»;
 *   - el aviso propio cuando está vacía y el doble clic, que no abre lo eliminado.
 *
 * Lo que se muestra y lo que se oculta lo decide la clase `gd-en-papelera` de <body>
 * (explorador-papelera.css). Las rutas del servicio ya existían: POST /papelera/restaurar,
 * /papelera/eliminar y /papelera/vaciar. En la Papelera la «ruta» de cada elemento es su
 * identificador dentro de ella, no una ruta de la unidad.
 *
 * Depende de: API_BASE (config.js), escHtml (escape.js), elementosSeleccionados,
 *   limpiarSeleccion, restaurarSeleccionado y vaciarPapelera (interactions.js),
 *   cargarArchivos (navegacion.js), mostrarNotificacion, Swal.
 * Cargar ANTES de explorador-navegacion.js (que llama a ajustarVistaPapelera).
 */

const CLASE_EN_PAPELERA = 'gd-en-papelera';
let _avisoVacioPapeleraPuesto = false;

function estaEnPapelera() {
    return document.body.classList.contains(CLASE_EN_PAPELERA);
}

/** Texto de la franja: «3 elementos en la papelera». */
function textoConteoPapelera(total) {
    return total === 1 ? '1 elemento en la papelera' : total + ' elementos en la papelera';
}

function _pintarFranjaPapelera(total) {
    const anterior = document.getElementById('papeleraAcciones');
    if (anterior) anterior.remove();
    if (!(total > 0)) return;
    const destino = document.getElementById('filesContainer');
    if (!destino || !destino.parentElement) return;
    const franja = document.createElement('div');
    franja.id = 'papeleraAcciones';
    franja.className = 'gd-papelera-franja';
    franja.innerHTML = '<span class="material-icons">delete_sweep</span>'
        + '<span class="gd-papelera-texto"><strong>' + escHtml(textoConteoPapelera(total)) + '.</strong> '
        + 'Con el botón derecho puede restaurar un elemento o eliminarlo definitivamente.</span>'
        + '<button type="button" id="btnVaciarPapelera" onclick="vaciarPapelera()" '
        + 'title="Elimina definitivamente todo lo que hay en la papelera">'
        + '<span class="material-icons">delete_forever</span> Vaciar papelera</button>';
    destino.parentElement.insertBefore(franja, destino);
}

/** El estado vacío general invita a subir archivos; en la Papelera no corresponde. */
function _avisoVacioPapelera(enPapelera, total) {
    const vacio = document.getElementById('emptyState');
    if (!vacio) return;
    const titulo = vacio.querySelector('h2');
    const texto = vacio.querySelector('p');
    if (!titulo || !texto) return;
    if (enPapelera && !(total > 0)) {
        titulo.textContent = 'La papelera está vacía';
        texto.textContent = 'Lo que usted elimine aparecerá aquí y podrá restaurarlo.';
        _avisoVacioPapeleraPuesto = true;
    } else if (_avisoVacioPapeleraPuesto) {
        titulo.textContent = 'Bienvenido a ' + (window.DRIVE_NAME || 'Nube');
        texto.textContent = 'Arrastre archivos y carpetas aquí, o use el botón «Nuevo»';
        _avisoVacioPapeleraPuesto = false;
    }
}

/** Lo llama cargarArchivos después de pintar cualquier lista. */
function ajustarVistaPapelera(enPapelera, total) {
    document.body.classList.toggle(CLASE_EN_PAPELERA, !!enPapelera);
    _pintarFranjaPapelera(enPapelera ? total : 0);
    _avisoVacioPapelera(!!enPapelera, total);
}

/** Doble clic o Intro sobre un elemento. Devuelve true si la Papelera lo atendió:
 *  lo eliminado no se abre (su «ruta» no existe en la unidad); primero se restaura. */
function abrirItemEnPapelera() {
    if (!estaEnPapelera()) return false;
    mostrarNotificacion('Para abrirlo, primero restáurelo (botón derecho → Restaurar)', 'info');
    return true;
}

/** «Eliminar definitivamente» para uno o varios elementos seleccionados. */
async function eliminarDefinitivoSeleccionados() {
    const menu = document.getElementById('contextMenu');
    if (menu) menu.classList.remove('show');
    const elegidos = (typeof elementosSeleccionados !== 'undefined' ? elementosSeleccionados : []).slice();
    if (!elegidos.length) {
        mostrarNotificacion('Seleccione un elemento de la papelera', 'warning');
        return;
    }
    const cuales = elegidos.length === 1 ? '«' + elegidos[0].nombre + '»' : elegidos.length + ' elementos';
    const confirmacion = await Swal.fire({
        title: '¿Eliminar definitivamente?',
        text: 'Se eliminará ' + cuales + ' de la papelera. Usted no podrá restaurarlo después.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d93025',
        confirmButtonText: 'Eliminar definitivamente',
        cancelButtonText: 'Cancelar'
    });
    if (!confirmacion.isConfirmed) return;

    let fallidos = 0;
    for (const elemento of elegidos) {
        try {
            const respuesta = await fetch(API_BASE + '/papelera/eliminar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ruta: elemento.ruta })
            });
            if (!respuesta.ok) fallidos++;
        } catch (e) {
            fallidos++;
        }
    }
    const hechos = elegidos.length - fallidos;
    if (hechos > 0) mostrarNotificacion(hechos === 1 ? 'Elemento eliminado definitivamente' : hechos + ' elementos eliminados definitivamente', 'success');
    if (fallidos > 0) mostrarNotificacion(fallidos === 1 ? 'Un elemento no se pudo eliminar' : fallidos + ' elementos no se pudieron eliminar', 'error');
    if (typeof limpiarSeleccion === 'function') limpiarSeleccion();
    await cargarArchivos(rutaActual, true);
}
