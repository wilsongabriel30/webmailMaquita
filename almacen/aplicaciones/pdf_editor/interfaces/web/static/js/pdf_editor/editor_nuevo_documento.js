/* ============================================================
   Raíces Maquita — Editor PDF · abrir otro documento
   Esta es UNA PARTE del editor (ver el reparto en editor_nucleo.js).

   «Necesito un botoncito en la parte superior derecha que diga "nuevo, para abrir
   otro pdf"; recuerda solicitar la confirmación de salir sin cambios guardados»
   — el usuario, 31-jul-2026.

   Hasta ahora, para abrir otro PDF había que volver al inicio o saber que existe
   Ctrl+O. Y ninguno de los dos avisaba: se abría el nuevo documento y lo que llevaras
   hecho en el anterior se perdía sin decir nada. El aviso al cerrar la pestaña sí
   existía (`beforeunload` en el núcleo), pero abrir otro documento no pasa por ahí.
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.nuevo_documento = function (E) {
    'use strict';

    const { $, fileInput, state } = E;

    const AVISO = 'Tienes cambios SIN DESCARGAR en este documento.\n\n'
                + 'Si abres otro PDF, se perderán: el editor trabaja sobre una copia y '
                + 'los cambios solo quedan guardados cuando descargas el documento.\n\n'
                + '¿Abrir otro PDF de todas formas?';

    /** Abre el selector para elegir otro PDF, avisando antes si hay trabajo sin
     *  descargar. Lo usa el botón «Nuevo» y también el atajo Ctrl+O del núcleo, para
     *  que las dos vías avisen igual. */
    function abrirOtroPDF() {
        if (state.hayCambios && !confirm(AVISO)) return;
        fileInput.click();
    }

    // Por delegación: no depende de que el botón exista justo cuando arranca esta
    // parte (fue el fallo de «pulso y no pasa nada» del 31-jul-2026).
    document.addEventListener('click', e => {
        if (e.target.closest('#btnNuevoPDF')) {
            e.preventDefault();
            abrirOtroPDF();
        }
    });

    // Lo que esta parte ofrece al resto del editor:
    Object.assign(E, { _abrirOtroPDF: abrirOtroPDF });
};
