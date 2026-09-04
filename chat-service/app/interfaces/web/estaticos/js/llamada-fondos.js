/* =============================================================================
   T-52 · Desenfocar el fondo, ponerse un fondo y verse en espejo
   -----------------------------------------------------------------------------
   QUE HACE: añade a la ventana de llamada del chat los botones para desenfocar el
   fondo o poner uno de los fondos de Maquita, muestra la propia imagen en espejo
   (como un espejo de verdad, que es lo que la gente espera) y hace que los
   selectores de cámara y micrófono arranquen en el dispositivo que la persona
   dejó elegido.
   POR QUE:  es lo que traen Zoom y Teams, y en casa o en una sala compartida hace
   falta. Puntos 2 y 3 del encargo.

   TODO SE SIRVE DESDE AQUI: la librería y el modelo de segmentación viven en
   nuestro servidor, no en un CDN de fuera. Si dependiera de internet, el
   desenfoque fallaría justo cuando la conexión va mal —que es cuando más se
   usa— y además cada equipo estaría pidiendo archivos a un tercero durante una
   reunión de trabajo.

   DONDE SE LLAMA: plantillas/chat/llamada.html y conferencia.html.
   ============================================================================= */
(function (global) {
    'use strict';

    var BASE = '/static/js/lib/';
    var FONDOS = [
        {id: 'ninguno', nombre: 'Sin fondo', icono: '🚫'},
        {id: 'desenfoque', nombre: 'Desenfocar', icono: '🌫'},
        {id: 'maquita-1-azul', nombre: 'Maquita azul', icono: '🟦'},
        {id: 'maquita-3-claro', nombre: 'Maquita claro', icono: '⬜'},
    ];
    var URL_FONDOS = 'https://meet.maquita.com.ec/images/virtual-background/';

    var procesadores = null;      // la librería, una vez cargada
    var actual = 'ninguno';
    var pistaVideo = null;        // la pista de vídeo de LiveKit, si la hay

    /* La librería pesa y solo hace falta cuando alguien pulsa: se carga entonces, no antes.
       Así la llamada empieza igual de rápido para quien no use fondos. */
    async function cargarLibreria() {
        if (procesadores) return procesadores;
        try {
            procesadores = await import(BASE + 'livekit-track-processors.mjs');
            return procesadores;
        } catch (e) {
            console.warn('T-52: no se pudo cargar el procesador de fondos', e);
            return null;
        }
    }

    var OPCIONES_LOCALES = {
        // se le dice DONDE estan las cosas: nada sale a internet
        assetPaths: {
            tasksVisionFileSet: BASE + 'mediapipe/wasm',
            modelAssetPath: BASE + 'modelos/selfie_segmenter.tflite',
        },
    };

    async function aplicar(id) {
        var lib = await cargarLibreria();
        if (!lib || !pistaVideo) return false;
        try {
            if (id === 'ninguno') {
                await pistaVideo.stopProcessor();
            } else if (id === 'desenfoque') {
                await pistaVideo.setProcessor(lib.BackgroundBlur(12, OPCIONES_LOCALES));
            } else {
                await pistaVideo.setProcessor(
                    lib.VirtualBackground(URL_FONDOS + id + '.jpg', OPCIONES_LOCALES));
            }
            actual = id;
            pintarSeleccion();
            return true;
        } catch (e) {
            console.warn('T-52: no se pudo aplicar el fondo «' + id + '»', e);
            avisar('No se pudo aplicar el fondo en este equipo');
            return false;
        }
    }

    function avisar(texto) {
        var d = document.createElement('div');
        d.className = 'mq-aviso-fondo';
        d.textContent = texto;
        document.body.appendChild(d);
        setTimeout(function () { d.remove(); }, 4000);
    }

    /* --- el botón y su menú --- */
    function montar(barra) {
        if (!barra || document.getElementById('mqFondos')) return;
        var b = document.createElement('button');
        b.id = 'mqFondos';
        b.type = 'button';
        b.className = 'mq-boton-fondo';
        b.title = 'Fondo de la cámara';
        b.innerHTML = '🌫';
        b.addEventListener('click', alternarMenu);
        barra.appendChild(b);

        var menu = document.createElement('div');
        menu.id = 'mqMenuFondos';
        menu.className = 'mq-menu-fondos';
        menu.style.display = 'none';
        FONDOS.forEach(function (f) {
            var o = document.createElement('button');
            o.type = 'button';
            o.className = 'mq-opcion-fondo';
            o.dataset.fondo = f.id;
            o.innerHTML = '<span>' + f.icono + '</span>' + f.nombre;
            o.addEventListener('click', function () { aplicar(f.id); });
            menu.appendChild(o);
        });
        document.body.appendChild(menu);
        pintarSeleccion();
    }

    function alternarMenu() {
        var m = document.getElementById('mqMenuFondos');
        var b = document.getElementById('mqFondos');
        if (!m || !b) return;
        var abierto = m.style.display !== 'none';
        m.style.display = abierto ? 'none' : 'block';
        if (!abierto) {
            var r = b.getBoundingClientRect();
            m.style.left = Math.max(8, r.left - 40) + 'px';
            m.style.bottom = (window.innerHeight - r.top + 10) + 'px';
        }
    }

    function pintarSeleccion() {
        Array.prototype.forEach.call(document.querySelectorAll('.mq-opcion-fondo'), function (o) {
            o.classList.toggle('activo', o.dataset.fondo === actual);
        });
    }

    /* --- el espejo: SOLO en la vista propia --- */
    function espejo() {
        // Verse al revés desconcierta: uno levanta la mano derecha y en pantalla sube la
        // izquierda. Se voltea la vista PROPIA, nunca la de los demás ni lo que se envía.
        ['localVideo', 'videoLocal', 'miVideo'].forEach(function (id) {
            var v = document.getElementById(id);
            if (v) v.classList.add('mq-espejo');
        });
    }

    /* --- que la cámara y el micrófono arranquen en el que la persona dejó elegido --- */
    function dispositivosPreferidos() {
        // La aplicación los inyecta como `deviceId` ideal en getUserMedia. Aquí solo se
        // respeta lo que llegue: si el selector de la página trae su propia lista, se
        // coloca en el que se está usando de verdad.
        try {
            var pref = (global.maquitaApp && global.maquitaApp.dispositivosPreferidos) || null;
            if (!pref) return;
            ['selCamara', 'selectCamara', 'camaraSelect'].forEach(function (id) {
                var s = document.getElementById(id);
                if (s && pref.camara) s.value = pref.camara;
            });
            ['selMicrofono', 'selectMicrofono', 'micSelect'].forEach(function (id) {
                var s = document.getElementById(id);
                if (s && pref.microfono) s.value = pref.microfono;
            });
        } catch (e) { /* si no hay preferencias, se queda como estaba */ }
    }

    /* Se engancha a la pista de vídeo de LiveKit en cuanto exista. */
    function buscarPista() {
        var sala = global.room || global.lkRoom || (global.est && global.est.room);
        if (!sala || !sala.localParticipant) return false;
        var pubs = sala.localParticipant.videoTrackPublications
            || sala.localParticipant.videoTracks;
        if (!pubs) return false;
        var encontrada = null;
        pubs.forEach(function (p) { if (p && p.track && !encontrada) encontrada = p.track; });
        if (!encontrada) return false;
        pistaVideo = encontrada;
        return true;
    }

    function iniciar() {
        espejo();
        dispositivosPreferidos();
        var barra = document.querySelector('.call-controls, .controles, #controles, .barra-llamada');
        if (barra) montar(barra);
        return buscarPista();
    }

    document.addEventListener('DOMContentLoaded', function () { setTimeout(iniciar, 1200); });
    var intentos = 0;
    var reloj = setInterval(function () {
        if (iniciar() || ++intentos > 40) clearInterval(reloj);
    }, 1000);

    global.MaquitaFondos = {aplicar: aplicar, FONDOS: FONDOS,
                            listo: function () { return !!pistaVideo; }};
})(window);
