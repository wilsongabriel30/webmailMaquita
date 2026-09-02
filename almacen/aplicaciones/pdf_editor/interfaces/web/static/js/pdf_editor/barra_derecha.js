/* ============================================================
   Raíces Maquita - Editor PDF: los iconos de la BARRA DERECHA

   La auditoría del 28-jul-2026 encontró tres iconos de esa barra que no tenían
   manejador en ningún sitio: se pulsaban y no pasaba nada, aunque su globo de
   ayuda prometía una acción. Es el mismo caso que el icono de la mano
   (27-jul-2026): el botón estaba dibujado, pero sin puerta detrás.

     💬 Comentarios → enciende la herramienta de comentarios
     ⬆ Exportar     → despliega el menú Exportar de la barra de arriba
     ✎ Rellenar     → abre "Preparar formulario", que es lo que rellena campos

   Cada uno se limita a llamar a la función que YA existe en el editor, así que
   no hay lógica nueva que mantener ni riesgo de que se comporten distinto que
   la ruta larga. Va en su propio archivo para no engordar `editor_nucleo.js`.

   IMPORTANTE: nginx sirve /static con caché de 1 año; cualquier cambio aquí
   exige subir la versión ?v= en el template.
   ============================================================ */
(function () {
    'use strict';

    // A qué botón de siempre corresponde cada icono de la barra derecha
    const EQUIVALENCIAS = [
        {icono: 'btnRightComment', hace: 'btnComment',       nombre: 'Comentarios'},
        {icono: 'btnRightExport',  hace: 'btnExportarMenu',  nombre: 'Exportar'},
        {icono: 'btnRightFill',    hace: 'toolFormulario',   nombre: 'Rellenar'},
    ];

    function conectar() {
        EQUIVALENCIAS.forEach(par => {
            const icono = document.getElementById(par.icono);
            if (!icono || icono.dataset.conectado) return;
            icono.dataset.conectado = '1';
            icono.addEventListener('click', e => {
                e.preventDefault();
                // Sin esto, el menú Exportar se abre y se cierra en el mismo
                // clic: el editor lo cierra al detectar un clic en el documento,
                // y este venía burbujeando desde aquí.
                e.stopPropagation();
                const destino = document.getElementById(par.hace);
                if (destino) {
                    destino.click();
                    return;
                }
                // Si el botón de destino no está en esta pantalla, se dice en
                // vez de dejar al usuario pulsando un icono mudo.
                if (window.PDFEditorToast) window.PDFEditorToast(par.nombre + ' no está disponible aquí.');
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', conectar);
    } else {
        conectar();
    }
})();
