/* T-101 · Sección «Archivos» (/chat/archivos): todos los archivos y fotos de mis conversaciones. */
(function () {
    'use strict';
    if (!window.MaquitaArchivos) return;
    var incrustado = new URLSearchParams(location.search).get('embed') === '1';
    var volver = document.getElementById('archVolver');
    if (volver && incrustado) volver.setAttribute('href', '/chat/?embed=1');

    var lista = window.MaquitaArchivos.crear(document.getElementById('archLista'), {
        conversacion: null, clase: 'archivos', mostrarConversacion: true,
        verEnChat: function (a) { location.href = '/chat/?conv=' + encodeURIComponent(a.conversacion_id) + (incrustado ? '&embed=1' : ''); },
        vacio: { archivos: 'Todavía no has enviado ni recibido archivos por el chat.', fotos: 'Todavía no has enviado ni recibido fotos por el chat.' }
    });
    document.addEventListener('click', function (e) {
        var f = e.target.closest && e.target.closest('.arch-filtro');
        if (!f) return;
        document.querySelectorAll('.arch-filtro').forEach(function (x) { x.setAttribute('aria-pressed', x === f ? 'true' : 'false'); });
        lista.clase(f.getAttribute('data-clase'));
    });
})();
