/**
 * explorador-ayuda.js  -  Módulo: botón de ayuda (?) de la cabecera
 * Responsabilidad ÚNICA: mostrar una guía breve de uso del Drive.
 * El botón existía sin ninguna acción asociada: se pulsaba y no pasaba nada.
 *
 * Depende de: Swal, mostrarAtajosTeclado (core.js), window.DRIVE_NAME.
 */

const TEMAS_AYUDA = [
    ['upload_file', 'Subir archivos', 'Arrastre archivos o carpetas a la ventana, o use el botón «Nuevo».'],
    ['folder_open', 'Abrir', 'Haga doble clic sobre una carpeta o un archivo. Los documentos, hojas de cálculo y presentaciones se abren en el editor en línea.'],
    ['more_vert', 'Más acciones', 'Con el botón derecho sobre un elemento puede descargarlo, cambiarle el nombre, moverlo, copiarlo o compartirlo.'],
    ['person_add', 'Compartir', 'Elija «Compartir» para dar acceso a otra persona o crear un enlace. Lo que le compartan a usted aparece en «Compartido conmigo».'],
    ['delete', 'Papelera', 'Lo que elimina va a la Papelera. Desde allí puede restaurarlo o eliminarlo definitivamente.'],
    ['cloud', 'Espacio', 'En «Almacenamiento» (panel izquierdo) se ve cuánto espacio usa su cuenta y cuánto tiene disponible.']
];

function abrirAyudaNube() {
    const filas = TEMAS_AYUDA.map(t =>
        '<div style="display:flex;gap:12px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #eee;">'
        + '<span class="material-icons" style="color:#5f6368;">' + t[0] + '</span>'
        + '<div><strong>' + t[1] + '</strong><br><span style="color:#5f6368;font-size:13px;">' + t[2] + '</span></div></div>'
    ).join('');
    Swal.fire({
        title: 'Ayuda de ' + (window.DRIVE_NAME || 'Nube'),
        html: '<div id="ayudaNube" style="text-align:left;">' + filas
            + '<p style="color:#5f6368;font-size:13px;margin:12px 0 0;">Si necesita más ayuda, escriba al área de Tecnología de su organización.</p></div>',
        width: 560,
        showCloseButton: true,
        showCancelButton: true,
        confirmButtonText: 'Combinaciones de teclas',
        confirmButtonColor: '#1a73e8',
        cancelButtonText: 'Cerrar'
    }).then(resultado => {
        if (resultado.isConfirmed && typeof mostrarAtajosTeclado === 'function') mostrarAtajosTeclado();
    });
}
