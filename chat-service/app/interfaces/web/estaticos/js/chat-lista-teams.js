/* =============================================================================
   T-50 tanda 1 · EL PANEL DE LA IZQUIERDA COMO TEAMS
   -----------------------------------------------------------------------------
   QUE HACE: reorganiza la lista de conversaciones en dos secciones —Favoritos y
   Chats—, marca en negrita con un punto las que tienen mensajes sin leer, y
   pone SIEMPRE el indicador de presencia sobre el avatar. Anade tambien los
   filtros «No leído» y «Chats de reuniones».
   POR QUE:  es lo que pidio soporte en los puntos 1, 2, 5, 6, 8, 9 y 35 del
   requerimiento. Va en su propio archivo y NO toca chat-lista.js: envuelve lo
   que ya hay, para no romper nada de lo entregado antes.
   DONDE SE LLAMA: lo carga plantillas/chat/index.html despues de chat-lista.js.
   ============================================================================= */
(function () {
    'use strict';

    var favoritos = new Set();
    var filtro = 'todos';     // todos | no_leido | reuniones

    /* ---- Favoritos: se guardan por persona en el servidor ---- */
    async function cargarFavoritos() {
        try {
            var r = await fetch('/api/chat/favoritos');
            var d = await r.json();
            favoritos = new Set((d.favoritos || []).map(Number));
        } catch (e) {
            favoritos = new Set();
        }
    }

    async function alternarFavorito(id) {
        var esFavorito = favoritos.has(Number(id));
        try {
            await fetch('/api/chat/favoritos/' + id, {method: esFavorito ? 'DELETE' : 'POST'});
            if (esFavorito) favoritos.delete(Number(id)); else favoritos.add(Number(id));
            reorganizar();
        } catch (e) {
            console.warn('no se pudo cambiar el favorito', e);
        }
    }

    /* ---- Reparto en secciones ---- */
    function cabecera(texto, cuantos) {
        var d = document.createElement('div');
        d.className = 'mq-seccion-lista';
        d.innerHTML = '<span>' + texto + '</span><span class="mq-seccion-cuenta">' +
                      (cuantos || '') + '</span>';
        return d;
    }

    function esNoLeida(fila) {
        var b = fila.querySelector('.unread-badge, .badge, .conversation-unread');
        return !!(b && (b.textContent || '').trim() && b.textContent.trim() !== '0');
    }

    function esDeReunion(fila) {
        // por el tipo que ya trae la fila, y si no por el nombre
        if ((fila.dataset.convType || '') === 'meeting') return true;
        var t = (fila.dataset.convName || fila.textContent || '').toLowerCase();
        return t.indexOf('reunión') >= 0 || t.indexOf('reunion') >= 0 || t.indexOf('meet') >= 0;
    }

    /* De quién es cada conversación y en qué estado está, para que el puntito de
       presencia (T-48) pueda pintarse SIEMPRE sobre el avatar (punto 6). La fila no
       trae ese dato, así que se pide una vez y se anota en cada fila. */
    var personaDe = {};

    async function cargarPersonas() {
        try {
            var r = await fetch('/api/chat/conversations');
            var d = await r.json();
            var lista = d.conversations || d.conversaciones || [];
            lista.forEach(function (c) {
                if (c && c.other_user && c.other_user.id) {
                    personaDe[c.id] = {id: c.other_user.id, estado: c.other_user.estado || ''};
                }
            });
        } catch (e) {
            console.warn('no se pudieron leer las personas de las conversaciones', e);
        }
    }

    function reorganizar() {
        var lista = document.getElementById('conversationsList');
        if (!lista || reorganizando) return;
        if (ratonEncima) {          // se hará en cuanto el cursor salga
            quedaPendiente = true;
            return;
        }
        reorganizando = true;
        try {
            _reorganizar(lista);
        } finally {
            // se suelta en el siguiente ciclo, para no captar los cambios propios
            setTimeout(function () { reorganizando = false; }, 0);
        }
    }

    function _reorganizar(lista) {
        var filas = Array.prototype.slice.call(
            lista.querySelectorAll('.conversation-item[data-conv-id]'));
        if (!filas.length) return;

        // se quitan las cabeceras de una pasada anterior
        Array.prototype.forEach.call(lista.querySelectorAll('.mq-seccion-lista'), function (c) {
            c.remove();
        });

        var arriba = [], abajo = [];
        filas.forEach(function (fila) {
            var id = Number(fila.dataset.convId);
            var sinLeer = esNoLeida(fila);

            // punto 35: la conversacion sin leer va en negrita y con un punto
            fila.classList.toggle('mq-no-leida', sinLeer);

            // punto 6: el indicador de presencia SIEMPRE sobre el avatar
            var avatar = fila.querySelector('.conversation-avatar, .avatar');
            if (avatar) {
                avatar.classList.add('mq-estado');
                var quien = personaDe[id];
                if (quien) {
                    // se anota de quién es para que el módulo de estados lo mantenga al día
                    fila.dataset.usuarioId = quien.id;
                    if (!avatar.dataset.estado) avatar.dataset.estado = quien.estado || 'desconectado';
                } else if (!avatar.dataset.estado) {
                    // conversación de grupo o sin dato: el aro gris, nunca un verde falso
                    avatar.dataset.estado = 'desconocido';
                }
            }

            // el boton de fijar, que aparece al pasar el raton
            if (!fila.querySelector('.mq-fijar')) {
                var b = document.createElement('button');
                b.className = 'mq-fijar';
                b.type = 'button';
                b.addEventListener('click', function (ev) {
                    ev.stopPropagation();
                    alternarFavorito(id);
                });
                fila.appendChild(b);
            }
            var fav = favoritos.has(id);
            fila.classList.toggle('mq-favorita', fav);
            var boton = fila.querySelector('.mq-fijar');
            boton.title = fav ? 'Quitar de Favoritos' : 'Fijar en Favoritos';
            boton.innerHTML = fav ? '★' : '☆';

            // los filtros del punto 2
            var visible = (filtro === 'todos')
                || (filtro === 'no_leido' && sinLeer)
                || (filtro === 'reuniones' && esDeReunion(fila));
            fila.style.display = visible ? '' : 'none';
            if (!visible) return;
            (fav ? arriba : abajo).push(fila);
        });

        // puntos 8 y 9: Favoritos arriba, Chats debajo.
        // Se arma el orden deseado y solo se TOCA el DOM si de verdad cambia: mover
        // nodos que ya estan bien colocados es lo que hacia parpadear la lista.
        var deseado = [];
        if (arriba.length) {
            deseado.push(cabecera('Favoritos', arriba.length));
            arriba.forEach(function (f) { deseado.push(f); });
            if (abajo.length) deseado.push(cabecera('Chats', abajo.length));
        }
        abajo.forEach(function (f) { deseado.push(f); });

        var actuales = Array.prototype.filter.call(lista.children, function (n) {
            return n.classList.contains('conversation-item') || n.classList.contains('mq-seccion-lista');
        });
        var igual = actuales.length === deseado.length && actuales.every(function (n, i) {
            return n === deseado[i];
        });
        if (igual) return;

        var trozo = document.createDocumentFragment();
        deseado.forEach(function (n) { trozo.appendChild(n); });
        lista.insertBefore(trozo, lista.firstChild);
    }

    /* ---- Los filtros nuevos ---- */
    function montarFiltros() {
        var barra = document.querySelector('.chat-tabs');
        if (!barra || barra.querySelector('.mq-filtro')) return;
        [['todos', 'Todos'], ['no_leido', 'No leído'], ['reuniones', 'Chats de reuniones']]
            .forEach(function (par) {
                var b = document.createElement('button');
                b.className = 'chat-tab mq-filtro' + (par[0] === 'todos' ? ' active' : '');
                b.dataset.filtro = par[0];
                b.textContent = par[1];
                b.addEventListener('click', function () {
                    filtro = par[0];
                    Array.prototype.forEach.call(barra.querySelectorAll('.mq-filtro'), function (o) {
                        o.classList.toggle('active', o.dataset.filtro === filtro);
                    });
                    reorganizar();
                });
                barra.appendChild(b);
            });
        // las pestanas viejas (Todos/Directos/Grupos/Archivados) se ocultan: el
        // requerimiento pide los filtros de Teams, pero no se borran para no
        // romper switchTab, del que dependen otras partes.
        Array.prototype.forEach.call(barra.querySelectorAll('.chat-tab[data-tab]'), function (t) {
            t.style.display = 'none';
        });
    }

    /* la lista se repinta sola cada vez que llegan mensajes: se vuelve a ordenar */
    var observador = null;
    var reorganizando = false;
    var ratonEncima = false;
    var quedaPendiente = false;

    /* Mientras el cursor está sobre la lista NO se reordena.
       Mover una fila bajo el ratón hace que el puntero salga y entre del elemento; si algo
       vuelve a pintar la lista con ese evento, se realimenta y la lista titila sin parar.
       Reordenar debajo del cursor es además molesto de por sí: se pospone a cuando el
       ratón se va, que es cuando a nadie le estorba. */
    function vigilarRaton(lista) {
        if (lista.__mqRaton) return;
        lista.__mqRaton = true;
        lista.addEventListener('mouseenter', function () { ratonEncima = true; });
        lista.addEventListener('mouseleave', function () {
            ratonEncima = false;
            if (quedaPendiente) {
                quedaPendiente = false;
                reorganizar();
            }
        });
    }

    function vigilar() {
        var lista = document.getElementById('conversationsList');
        if (!lista || lista.__mqVigilada) return;
        lista.__mqVigilada = true;
        var pendiente = null;
        // El observador tiene que ignorar los cambios que hace ESTE modulo. Sin esa
        // precaucion se disparaba a si mismo: reordenar movia nodos, el observador lo
        // veia, volvia a reordenar... y la lista titilaba al hacer clic.
        observador = new MutationObserver(function () {
            if (reorganizando) return;
            clearTimeout(pendiente);
            pendiente = setTimeout(reorganizar, 150);
        });
        observador.observe(lista, {childList: true});
        vigilarRaton(lista);
    }

    async function iniciar() {
        montarFiltros();
        await Promise.all([cargarFavoritos(), cargarPersonas()]);
        vigilar();
        reorganizar();
    }

    document.addEventListener('DOMContentLoaded', function () { setTimeout(iniciar, 800); });
    window.mqReorganizarLista = reorganizar;   // para las pruebas de humo
    window.mqAlternarFavorito = alternarFavorito;
})();
