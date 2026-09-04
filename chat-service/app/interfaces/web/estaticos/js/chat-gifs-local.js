/* Chat institucional - Biblioteca LOCAL de GIF (2026-08-27)
 * Reemplaza al buscador externo (Tenor cerró su API). Redefine las funciones
 * globales que usa chat-page.js (loadTrendingGifs / performGifSearch / displayGifs)
 * para que consulten /api/chat/gifs/* del propio servicio. Nada sale a Internet. */
(function () {
    'use strict';

    const API = '/api/chat/gifs';

    function contenedor() { return document.getElementById('gifPickerContent'); }

    function cargando() {
        const c = contenedor();
        if (c) c.innerHTML = '<div class="gif-loading"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';
    }

    function vacio(texto) {
        return '<div class="gif-placeholder"><i class="fas fa-images fa-2x mb-2 text-muted"></i>' +
               '<p class="text-muted">' + texto + '</p>' +
               '<button type="button" class="btn btn-sm btn-outline-primary" onclick="abrirSubirGif()">' +
               '<i class="fas fa-upload me-1"></i>Subir un GIF</button></div>';
    }

    function escapar(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;');
    }

    async function pedir(url) {
        const r = await fetch(url, { credentials: 'same-origin' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    }

    window.loadTrendingGifs = async function () {
        if (!contenedor()) return;
        cargando();
        try {
            const d = await pedir(API + '/trending?limit=40');
            if (!d.results.length) { contenedor().innerHTML = vacio('La biblioteca está vacía. ¡Sé el primero en subir un GIF!'); return; }
            window.displayGifs(d.results);
        } catch (e) {
            console.error('GIF local:', e);
            contenedor().innerHTML = vacio('No se pudo cargar la biblioteca');
        }
    };

    window.performGifSearch = async function (query) {
        if (!contenedor()) return;
        cargando();
        try {
            const d = await pedir(API + '/search?q=' + encodeURIComponent(query) + '&limit=40');
            ultimaBusqueda = query;
            if (!d.results.length) { contenedor().innerHTML = vacio('Sin resultados en la biblioteca para «' + escapar(query) + '»') + botonExternos(query); return; }
            window.displayGifs(d.results);
            contenedor().insertAdjacentHTML('beforeend', botonExternos(query));
        } catch (e) {
            console.error('GIF local:', e);
            contenedor().innerHTML = vacio('Error en la búsqueda');
        }
    };

    window.displayGifs = function (gifs) {
        const c = contenedor();
        if (!c) return;
        c.innerHTML = gifs.map(function (g) {
            const t = escapar(g.titulo);
            return '<div class="gif-item" data-gif-id="' + g.id + '" data-gif-url="' + escapar(g.url) + '" data-description="' + t + '" ' +
                   'title="' + t + '" onclick="sendGifFromElement(this)">' +
                   '<img src="' + escapar(g.url) + '" alt="' + t + '" loading="lazy">' +
                   (g.propio ? '<button type="button" class="gif-borrar" title="Quitar de la biblioteca" ' +
                       'onclick="event.stopPropagation();borrarGifLocal(' + g.id + ')"><i class="fas fa-times"></i></button>' : '') +
                   '</div>';
        }).join('') +
        '<div class="gif-item gif-item-subir" onclick="abrirSubirGif()" title="Subir un GIF a la biblioteca">' +
        '<div><i class="fas fa-plus fa-2x"></i><br><small>Subir GIF</small></div></div>';
    };

    // Contar uso al enviar (envuelve la función original de chat-page.js)
    const enviarOriginal = window.sendGifFromElement;
    window.sendGifFromElement = function (el) {
        const id = el && el.dataset.gifId;
        if (id) fetch(API + '/' + id + '/usar', { method: 'POST', credentials: 'same-origin' }).catch(function () {});
        if (typeof enviarOriginal === 'function') enviarOriginal(el);
    };

    window.abrirSubirGif = function () {
        let input = document.getElementById('gifUploadInput');
        if (!input) {
            input = document.createElement('input');
            input.type = 'file';
            input.id = 'gifUploadInput';
            input.accept = '.gif,.webp,image/gif,image/webp';
            input.style.display = 'none';
            input.addEventListener('change', function () {
                if (input.files && input.files[0]) subirGif(input.files[0]);
                input.value = '';
            });
            document.body.appendChild(input);
        }
        input.click();
    };

    async function subirGif(archivo) {
        if (archivo.size > 8 * 1024 * 1024) { toastr.warning('El GIF supera los 8 MB'); return; }
        const nombre = archivo.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ');
        const etiquetas = prompt('Etiquetas para encontrar este GIF (separadas por espacio):', nombre);
        if (etiquetas === null) return;
        const fd = new FormData();
        fd.append('file', archivo);
        fd.append('titulo', nombre);
        fd.append('etiquetas', etiquetas);
        cargando();
        try {
            const r = await fetch(API + '/upload', { method: 'POST', body: fd, credentials: 'same-origin' });
            const d = await r.json();
            if (!d.success) { toastr.error(d.mensaje || 'No se pudo subir el GIF'); window.loadTrendingGifs(); return; }
            toastr.success('GIF agregado a la biblioteca');
            const buscador = document.getElementById('gifSearch');
            if (buscador) buscador.value = '';
            window.loadTrendingGifs();
        } catch (e) {
            console.error('Subir GIF:', e);
            toastr.error('Error de conexión al subir el GIF');
            window.loadTrendingGifs();
        }
    }

    window.borrarGifLocal = async function (id) {
        if (!confirm('¿Quitar este GIF de la biblioteca?')) return;
        try {
            const r = await fetch(API + '/' + id, { method: 'DELETE', credentials: 'same-origin' });
            const d = await r.json();
            if (d.success) { toastr.success('GIF eliminado'); window.loadTrendingGifs(); }
            else toastr.error(d.mensaje || 'No se pudo eliminar');
        } catch (e) { toastr.error('Error de conexión'); }
    };

    // Abrir/cerrar el selector y buscar con retardo (traído del selector antiguo al retirar Tenor, 28/08/2026)
    let gifSearchTimeout = null;
    window.toggleGifPicker = function () {
        const picker = document.getElementById('gifPicker');
        const emojiPicker = document.getElementById('emojiPicker');
        const btn = document.querySelector('.chat-input-actions .gif-btn');
        const emojiBtn = document.querySelector('.chat-input-actions .emoji-btn');

        if (!picker) {
            console.error('GIF picker no encontrado');
            return;
        }

        // Cerrar emoji picker si está abierto
        if (emojiPicker.style.display === 'block') {
            emojiPicker.style.display = 'none';
            emojiBtn.classList.remove('active');
        }

        // Toggle GIF picker
        if (picker.style.display === 'none' || !picker.style.display) {
            picker.style.display = 'block';
            btn.classList.add('active');
            // Cargar GIFs trending por defecto
            if (!picker.dataset.loaded) {
                loadTrendingGifs();
                picker.dataset.loaded = 'true';
            }
        } else {
            picker.style.display = 'none';
            btn.classList.remove('active');
        }
    };
    window.searchGifs = function (query) {
        clearTimeout(gifSearchTimeout);

        if (!query.trim()) {
            loadTrendingGifs();
            return;
        }

        gifSearchTimeout = setTimeout(() => {
            performGifSearch(query);
        }, 500); // Debounce de 500ms
    };

    // ---- Segunda opción: fuentes externas (GIPHY / Wikimedia Commons). Lo elegido se DESCARGA a la biblioteca
    //      propia (una sola vez) y el mensaje sale con la copia local. (28/08/2026)
    let ultimaBusqueda = '';
    function botonExternos(query) {
        return '<div class="gif-externos-pie"><button type="button" class="btn btn-sm btn-outline-secondary" ' +
               'onclick="buscarGifsExternos(' + JSON.stringify(query).replace(/"/g, '&quot;') + ')">' +
               '<i class="fas fa-globe me-1"></i>¿No está? Buscar en fuentes externas</button></div>';
    }
    window.buscarGifsExternos = async function (query) {
        const c = contenedor();
        if (!c) return;
        cargando();
        try {
            const d = await pedir(API + '/externos?q=' + encodeURIComponent(query) + '&limit=24');
            if (!d.results.length) { c.innerHTML = vacio('Nada en las fuentes externas para «' + escapar(query) + '»'); return; }
            c.innerHTML = '<div class="gif-externos-aviso"><i class="fas fa-globe me-1"></i>Resultados externos para «' + escapar(query) +
                '»: al elegir uno se guarda en la biblioteca Maquita. <a href="#" onclick="performGifSearch(' +
                JSON.stringify(query).replace(/"/g, '&quot;') + ');return false;">Volver a la biblioteca</a></div>' +
                d.results.map(function (g, i) {
                    const t = escapar(g.titulo);
                    return '<div class="gif-item gif-item-externo" title="' + t + ' (' + g.fuente + ')" data-idx="' + i + '" ' +
                           'onclick="importarGifExterno(this)"><img src="' + escapar(g.url_vista) + '" alt="' + t + '" loading="lazy">' +
                           '<span class="gif-fuente">' + (g.local ? 'ya en biblioteca' : g.fuente) + '</span></div>';
                }).join('');
            c._externos = d.results;
        } catch (e) {
            console.error('GIF externos:', e);
            c.innerHTML = vacio('No se pudo consultar las fuentes externas');
        }
    };
    window.importarGifExterno = async function (el) {
        const c = contenedor();
        const g = c && c._externos && c._externos[parseInt(el.dataset.idx, 10)];
        if (!g) return;
        function enviarLocal(local) {
            el.dataset.gifId = local.id;
            el.dataset.gifUrl = local.url;
            el.dataset.description = local.titulo || '';
            window.sendGifFromElement(el);
        }
        if (g.local) { enviarLocal(g.local); return; }
        el.classList.add('gif-importando');
        try {
            const r = await fetch(API + '/externos/importar', { method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fuente: g.fuente, id: g.id, url: g.url, titulo: g.titulo, etiquetas: ultimaBusqueda }) });
            const d = await r.json();
            if (!d.success) { toastr.error(d.mensaje || 'No se pudo traer el GIF'); return; }
            g.local = d.gif;
            enviarLocal(d.gif);
        } catch (e) {
            toastr.error('Error de conexión al traer el GIF');
        } finally {
            el.classList.remove('gif-importando');
        }
    };
})();
