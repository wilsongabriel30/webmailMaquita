/* Chat institucional - Panel «Información del grupo» (T-94, 09/11/2026)
 *  Panel lateral al estilo Teams/WhatsApp: foto grande, nombre y descripción editables, quién puede editar,
 *  miembros (agregar, quitar, nombrar administradores) y salir del grupo.
 *  - Se abre con el botón (i) de la cabecera o pulsando la foto/nombre del grupo en la cabecera.
 *  - La foto se recorta en cuadrado y se reduce a 512 px (WebP) EN EL NAVEGADOR antes de subirla: pesa poco
 *    (conexiones lentas) y no hace falta procesar imágenes en el servidor.
 *  - Sustituye, solo para grupos, al modal de chat-grupos.js; los chats directos siguen con su ficha.
 *  Backend: GET/PUT /grupo, PUT /grupo/permisos, POST/DELETE /avatar, PUT /miembros/<id>/rol,
 *           POST/DELETE /participants, POST /leave. */
(function () {
    'use strict';

    const API = '/api/chat/conversations/';
    const LADO = 512;
    let abierto = null;      // id del grupo mostrado
    let datos = null;        // último detalle cargado

    function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
    function aviso(m, t) { if (window.toastr) toastr[t || 'info'](m); else if (t === 'error') alert(m); }
    function convs() { try { return Array.isArray(conversations) ? conversations : []; } catch (e) { return []; } }
    function convActual() { try { return currentConversationId; } catch (e) { return null; } }
    function recargarLista() { if (typeof window.loadConversations === 'function') window.loadConversations(); }
    function iniciales(n) {
        const p = String(n || 'G').trim().split(/\s+/).filter(Boolean);
        return ((p[0] || 'G').charAt(0) + (p.length > 1 ? p[p.length - 1].charAt(0) : '')).toUpperCase();
    }
    function color(n) {   // color estable por nombre para el avatar sin foto
        let h = 0; for (const ch of String(n || '')) h = (h * 31 + ch.charCodeAt(0)) % 360;
        return 'hsl(' + h + ', 45%, 42%)';
    }
    async function pedir(url, opciones) {
        const r = await fetch(url, Object.assign({ credentials: 'same-origin' }, opciones || {}));
        let d = {}; try { d = await r.json(); } catch (e) { /* sin cuerpo */ }
        if (!r.ok || d.success === false || d.exito === false) throw new Error(d.error || d.mensaje || 'No se pudo completar');
        return d;
    }
    function json(metodo, cuerpo) { return { method: metodo, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo || {}) }; }

    // ---------------------------------------------------------------- estructura
    function panel() {
        let p = document.getElementById('mqGrupoPanel');
        if (p) return p;
        p = document.createElement('aside');
        p.id = 'mqGrupoPanel'; p.className = 'mq-grupo-panel'; p.setAttribute('aria-label', 'Información del grupo');
        p.innerHTML = '<div class="mq-gp-cabecera"><h5>Información del grupo</h5>' +
            '<button type="button" class="mq-gp-cerrar" title="Cerrar" aria-label="Cerrar"><i class="fas fa-times"></i></button></div>' +
            '<div class="mq-gp-cuerpo"></div>';
        const fondo = document.createElement('div');
        fondo.id = 'mqGrupoFondo'; fondo.className = 'mq-grupo-fondo';
        fondo.onclick = cerrar;
        document.body.appendChild(fondo);
        document.body.appendChild(p);
        p.querySelector('.mq-gp-cerrar').onclick = cerrar;
        document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && abierto) cerrar(); });
        return p;
    }
    function cerrar() {
        abierto = null;
        document.body.classList.remove('mq-grupo-abierto');
    }

    async function abrir(id) {
        const p = panel();
        abierto = id;
        document.body.classList.add('mq-grupo-abierto');
        p.querySelector('.mq-gp-cuerpo').innerHTML = '<div class="mq-gp-cargando"><i class="fas fa-spinner fa-spin"></i></div>';
        try {
            datos = (await pedir(API + id + '/grupo')).grupo;
            if (abierto === id) pintar();
        } catch (e) {
            p.querySelector('.mq-gp-cuerpo').innerHTML = '<p class="text-muted p-3">' + esc(e.message) + '</p>';
        }
    }

    function avatarHtml(g, clase) {
        return g.avatar ? '<img class="' + clase + '" src="' + esc(g.avatar) + '" alt="">'
            : '<span class="' + clase + ' mq-gp-ini" style="background:' + color(g.nombre) + '">' + esc(iniciales(g.nombre)) + '</span>';
    }

    function pintar() {
        const g = datos, cuerpo = panel().querySelector('.mq-gp-cuerpo');
        const editar = g.puede_editar && !g.notas, admin = g.soy_admin && !g.notas;
        let h = '<div class="mq-gp-foto">' + avatarHtml(g, 'mq-gp-avatar') +
            (editar ? '<button type="button" class="mq-gp-camara" title="Cambiar foto" data-accion="menu-foto"><i class="fas fa-camera"></i></button>' +
                      '<div class="mq-gp-menu" hidden><button type="button" data-accion="elegir-foto"><i class="fas fa-image"></i> Subir foto</button>' +
                      (g.avatar ? '<button type="button" data-accion="quitar-foto"><i class="fas fa-trash-alt"></i> Quitar foto</button>' : '') + '</div>' +
                      '<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden data-accion="archivo">' : '') +
            '</div>';
        h += campo('nombre', g.notas ? 'Mis notas' : g.nombre, 'Nombre del grupo', 60, editar);
        if (!g.notas) h += campo('descripcion', g.descripcion, 'Añade una descripción', 120, editar);
        if (g.notas) {
            h += '<p class="mq-gp-nota">Este chat es solo tuyo: guarda notas, enlaces y archivos. Nadie más lo ve.</p>';
            cuerpo.innerHTML = h; enganchar(cuerpo); return;
        }
        h += '<p class="mq-gp-sub">Grupo · ' + g.miembros.length + ' miembro' + (g.miembros.length === 1 ? '' : 's') + '</p>';

        h += '<section class="mq-gp-seccion"><h6>Quién puede cambiar el nombre y la foto</h6>';
        h += admin ? ('<label class="mq-gp-opcion"><input type="radio" name="mqEdicion" value="admins"' + (g.edicion !== 'todos' ? ' checked' : '') + '> Solo administradores</label>' +
                      '<label class="mq-gp-opcion"><input type="radio" name="mqEdicion" value="todos"' + (g.edicion === 'todos' ? ' checked' : '') + '> Todos los miembros</label>')
                   : '<p class="mq-gp-texto">' + (g.edicion === 'todos' ? 'Todos los miembros' : 'Solo administradores') + '</p>';
        h += '</section>';

        h += '<section class="mq-gp-seccion"><h6>Miembros (' + g.miembros.length + ')</h6>';
        if (admin) h += '<div class="mq-gp-buscar"><i class="fas fa-user-plus"></i><input type="text" placeholder="Agregar compañero…" autocomplete="off" data-accion="buscar"></div><div class="mq-gp-resultados"></div>';
        h += '<div class="mq-gp-miembros">' + g.miembros.slice().sort(function (a, b) { return (b.es_admin - a.es_admin) || 0; }).map(function (m) {
            const foto = m.foto ? '<img src="' + esc(m.foto) + '" alt="">' : '<span style="background:' + color(m.nombre) + '">' + esc(iniciales(m.nombre)) + '</span>';
            let acciones = '';
            if (admin && !m.es_yo) {
                acciones = '<button type="button" class="mq-gp-mas" title="Opciones" data-accion="menu-miembro" data-id="' + m.id + '"><i class="fas fa-ellipsis-v"></i></button>' +
                    '<div class="mq-gp-menu" hidden data-menu="' + m.id + '">' +
                    (m.es_admin ? (m.id !== g.creado_por ? '<button type="button" data-accion="rol" data-id="' + m.id + '" data-admin="0"><i class="fas fa-user-shield"></i> Quitar como administrador</button>' : '')
                                : '<button type="button" data-accion="rol" data-id="' + m.id + '" data-admin="1"><i class="fas fa-user-shield"></i> Hacer administrador</button>') +
                    '<button type="button" class="mq-gp-peligro" data-accion="quitar" data-id="' + m.id + '"><i class="fas fa-user-minus"></i> Quitar del grupo</button></div>';
            }
            return '<div class="mq-gp-miembro"><div class="mq-gp-mav">' + foto + '</div><div class="mq-gp-mdatos"><div>' + esc(m.nombre) +
                (m.es_yo ? ' <span class="mq-gp-tu">Tú</span>' : '') + '</div>' +
                (m.es_admin ? '<small class="mq-gp-admin">Administrador</small>' : '<small>Miembro</small>') + '</div>' + acciones + '</div>';
        }).join('') + '</div></section>';
        h += '<button type="button" class="mq-gp-salir" data-accion="salir"><i class="fas fa-sign-out-alt"></i> Salir del grupo</button>';
        cuerpo.innerHTML = h;
        enganchar(cuerpo);
    }

    function campo(nombre, valor, marcador, max, editable) {
        return '<div class="mq-gp-campo mq-gp-' + nombre + '" data-campo="' + nombre + '">' +
            '<div class="mq-gp-valor"><span class="' + (valor ? '' : 'mq-gp-vacio') + '">' + esc(valor || (editable ? marcador : '')) + '</span>' +
            (editable ? '<button type="button" title="Editar" data-accion="editar" data-campo="' + nombre + '"><i class="fas fa-pen"></i></button>' : '') + '</div>' +
            (editable ? '<form class="mq-gp-edicion" hidden data-campo="' + nombre + '"><input type="text" maxlength="' + max + '" value="' + esc(valor) + '" placeholder="' + esc(marcador) + '"' + (nombre === 'nombre' ? ' required' : '') + '>' +
                        '<button type="submit" title="Guardar"><i class="fas fa-check"></i></button><button type="button" title="Cancelar" data-accion="cancelar"><i class="fas fa-times"></i></button></form>' : '') +
            '</div>';
    }

    // ---------------------------------------------------------------- acciones
    function enganchar(cuerpo) {
        cuerpo.onclick = function (e) {
            const b = e.target.closest('[data-accion]');
            if (!b || b.tagName === 'INPUT') { cerrarMenus(); return; }
            const acc = b.dataset.accion, id = Number(b.dataset.id);
            if (acc !== 'menu-foto' && acc !== 'menu-miembro') cerrarMenus();
            if (acc === 'menu-foto') alternar(b.parentNode.querySelector('.mq-gp-menu'));
            else if (acc === 'menu-miembro') alternar(cuerpo.querySelector('[data-menu="' + id + '"]'));
            else if (acc === 'elegir-foto') cuerpo.querySelector('[data-accion="archivo"]').click();
            else if (acc === 'quitar-foto') quitarFoto();
            else if (acc === 'editar') { const c = b.closest('.mq-gp-campo'); c.querySelector('.mq-gp-valor').hidden = true; const f = c.querySelector('form'); f.hidden = false; f.querySelector('input').focus(); }
            else if (acc === 'cancelar') pintar();
            else if (acc === 'rol') cambiarRol(id, b.dataset.admin === '1');
            else if (acc === 'quitar') quitarMiembro(id);
            else if (acc === 'agregar') agregarMiembro(id);
            else if (acc === 'salir') salir();
        };
        cuerpo.querySelectorAll('form.mq-gp-edicion').forEach(function (f) {
            f.onsubmit = function (e) { e.preventDefault(); guardarCampo(f.dataset.campo, f.querySelector('input').value.trim()); };
        });
        const arch = cuerpo.querySelector('[data-accion="archivo"]');
        if (arch) arch.onchange = function () { if (arch.files && arch.files[0]) recortar(arch.files[0]); arch.value = ''; };
        cuerpo.querySelectorAll('input[name="mqEdicion"]').forEach(function (r) { r.onchange = function () { cambiarEdicion(r.value); }; });
        const buscar = cuerpo.querySelector('[data-accion="buscar"]');
        if (buscar) { let t = null; buscar.oninput = function () { clearTimeout(t); t = setTimeout(function () { buscarCompanero(buscar.value); }, 250); }; }
    }
    function alternar(m) { if (!m) return; const ver = m.hidden; cerrarMenus(); m.hidden = !ver; }
    function cerrarMenus() { panel().querySelectorAll('.mq-gp-menu').forEach(function (m) { m.hidden = true; }); }

    function actualizarCabecera() {
        if (convActual() !== abierto || !datos) return;
        const n = document.getElementById('chatHeaderName'); if (n) n.textContent = datos.nombre;
        const a = document.getElementById('chatHeaderAvatar');
        if (a) a.innerHTML = datos.avatar ? '<img src="' + esc(datos.avatar) + '" alt="">' : '<span class="avatar-initials">' + esc(iniciales(datos.nombre)) + '</span>';
    }

    async function guardarCampo(nombre, valor) {
        if (nombre === 'nombre' && !valor) { aviso('El nombre no puede quedar vacío', 'warning'); return; }
        const cuerpo = { nombre: datos.nombre, descripcion: datos.descripcion };
        cuerpo[nombre] = valor;
        try {
            const d = await pedir(API + abierto + '/grupo', json('PUT', cuerpo));
            datos.nombre = d.grupo.nombre; datos.descripcion = d.grupo.descripcion;
            pintar(); actualizarCabecera(); recargarLista();
            aviso(nombre === 'nombre' ? 'Nombre del grupo actualizado' : 'Descripción actualizada', 'success');
        } catch (e) { aviso(e.message, 'error'); }
    }
    async function cambiarEdicion(valor) {
        try { await pedir(API + abierto + '/grupo/permisos', json('PUT', { edicion: valor })); datos.edicion = valor; aviso('Permisos del grupo actualizados', 'success'); }
        catch (e) { aviso(e.message, 'error'); pintar(); }
    }
    async function cambiarRol(id, admin) {
        try { await pedir(API + abierto + '/miembros/' + id + '/rol', json('PUT', { admin: admin })); aviso(admin ? 'Ahora es administrador' : 'Ya no es administrador', 'success'); abrir(abierto); }
        catch (e) { aviso(e.message, 'error'); }
    }
    async function quitarMiembro(id) {
        const m = datos.miembros.find(function (x) { return x.id === id; });
        if (!confirm('¿Quitar a ' + (m ? m.nombre : 'esta persona') + ' del grupo?')) return;
        try { await pedir(API + abierto + '/participants/' + id, { method: 'DELETE' }); aviso('Quitado del grupo', 'success'); abrir(abierto); }
        catch (e) { aviso(e.message, 'error'); }
    }
    async function agregarMiembro(id) {
        try { await pedir(API + abierto + '/participants', json('POST', { usuario_id: id })); aviso('Agregado al grupo', 'success'); abrir(abierto); }
        catch (e) { aviso(e.message, 'error'); }
    }
    async function buscarCompanero(q) {
        const caja = panel().querySelector('.mq-gp-resultados'); if (!caja) return;
        if (!q || q.trim().length < 2) { caja.innerHTML = ''; return; }
        try {
            const d = await pedir('/api/chat/users/search?q=' + encodeURIComponent(q.trim()));
            const ya = new Set(datos.miembros.map(function (m) { return m.id; }));
            const lista = (d.users || d.usuarios || d.results || d.data || []).filter(function (u) { return !ya.has(u.id || u.usuario_id); });
            caja.innerHTML = lista.slice(0, 8).map(function (u) {
                return '<button type="button" class="mq-gp-resultado" data-accion="agregar" data-id="' + (u.id || u.usuario_id) + '"><i class="fas fa-user-plus"></i> ' + esc(u.name || u.nombre || u.full_name || u.email) + '</button>';
            }).join('') || '<div class="mq-gp-texto">Sin resultados</div>';
        } catch (e) { caja.innerHTML = ''; }
    }
    async function salir() {
        if (!confirm('¿Salir de «' + datos.nombre + '»? Dejarás de recibir sus mensajes.')) return;
        try {
            await pedir(API + abierto + '/leave', { method: 'POST' });
            cerrar(); recargarLista();
            if (typeof window.volverAListaChat === 'function') window.volverAListaChat();
        } catch (e) { aviso(e.message, 'error'); }
    }
    async function quitarFoto() {
        if (!confirm('¿Quitar la foto del grupo?')) return;
        try { await pedir(API + abierto + '/avatar', { method: 'DELETE' }); datos.avatar = null; pintar(); actualizarCabecera(); recargarLista(); aviso('Foto quitada', 'success'); }
        catch (e) { aviso(e.message, 'error'); }
    }

    // ---------------------------------------------------------------- recorte cuadrado de la foto
    function recortar(archivo) {
        if (!/^image\//.test(archivo.type)) { aviso('Elige una imagen (PNG, JPG o WebP)', 'warning'); return; }
        if (archivo.size > 15 * 1024 * 1024) { aviso('La imagen es demasiado grande (máximo 15 MB)', 'warning'); return; }
        const url = URL.createObjectURL(archivo), img = new Image();
        img.onload = function () { mostrarRecorte(img, url); };
        img.onerror = function () { URL.revokeObjectURL(url); aviso('No se pudo leer la imagen', 'error'); };
        img.src = url;
    }
    function mostrarRecorte(img, url) {
        const V = 260;   // lado de la vista previa
        const base = Math.max(V / img.width, V / img.height);
        let zoom = 1, dx = 0, dy = 0, arrastre = null;
        const capa = document.createElement('div');
        capa.className = 'mq-gp-recorte';
        capa.innerHTML = '<div class="mq-gp-recorte-caja"><h6>Ajusta la foto del grupo</h6>' +
            '<canvas width="' + V + '" height="' + V + '"></canvas>' +
            '<label class="mq-gp-zoom"><i class="fas fa-search-minus"></i><input type="range" min="1" max="3" step="0.01" value="1"><i class="fas fa-search-plus"></i></label>' +
            '<p class="mq-gp-texto">Arrastra para encuadrar.</p>' +
            '<div class="mq-gp-recorte-botones"><button type="button" class="btn btn-light" data-r="no">Cancelar</button><button type="button" class="btn btn-primary" data-r="si">Usar foto</button></div></div>';
        document.body.appendChild(capa);
        const cv = capa.querySelector('canvas'), cx = cv.getContext('2d');
        function limitar() {
            const w = img.width * base * zoom, h = img.height * base * zoom;
            dx = Math.min(0, Math.max(V - w, dx)); dy = Math.min(0, Math.max(V - h, dy));
        }
        function dibujar() { limitar(); cx.clearRect(0, 0, V, V); cx.drawImage(img, dx, dy, img.width * base * zoom, img.height * base * zoom); }
        dx = (V - img.width * base) / 2; dy = (V - img.height * base) / 2; dibujar();
        capa.querySelector('input[type=range]').oninput = function () {
            const antes = zoom; zoom = Number(this.value);
            dx = V / 2 - (V / 2 - dx) * zoom / antes; dy = V / 2 - (V / 2 - dy) * zoom / antes; dibujar();
        };
        cv.onpointerdown = function (e) { arrastre = { x: e.clientX - dx, y: e.clientY - dy }; cv.setPointerCapture(e.pointerId); };
        cv.onpointermove = function (e) { if (arrastre) { dx = e.clientX - arrastre.x; dy = e.clientY - arrastre.y; dibujar(); } };
        cv.onpointerup = cv.onpointercancel = function () { arrastre = null; };
        function terminar() { URL.revokeObjectURL(url); capa.remove(); }
        capa.onclick = function (e) {
            const r = e.target.dataset && e.target.dataset.r;
            if (r === 'no' || e.target === capa) terminar();
            if (r !== 'si') return;
            const out = document.createElement('canvas'); out.width = out.height = LADO;
            const k = LADO / V;
            out.getContext('2d').drawImage(img, dx * k, dy * k, img.width * base * zoom * k, img.height * base * zoom * k);
            const subir = function (blob) { terminar(); if (blob) subirFoto(blob); else aviso('No se pudo preparar la imagen', 'error'); };
            out.toBlob(function (b) { if (b && b.type === 'image/webp') subir(b); else out.toBlob(subir, 'image/jpeg', 0.85); }, 'image/webp', 0.82);
        };
    }
    async function subirFoto(blob) {
        const fd = new FormData();
        fd.append('file', blob, blob.type === 'image/webp' ? 'grupo.webp' : 'grupo.jpg');
        try {
            const d = await pedir(API + abierto + '/avatar', { method: 'POST', body: fd });
            datos.avatar = d.avatar; pintar(); actualizarCabecera(); recargarLista(); aviso('Foto del grupo actualizada', 'success');
        } catch (e) { aviso(e.message, 'error'); }
    }

    // ---------------------------------------------------------------- integración
    function esGrupo(id) { const c = convs().find(function (x) { return x.id === id; }); return !!c && (c.conversation_type === 'group' || c.tipo === 'group'); }
    function instalar() {
        const previo = window.showChatInfo;
        window.showChatInfo = function () {
            const id = convActual();
            if (id && esGrupo(id)) return abrir(id);
            if (typeof previo === 'function') return previo.apply(this, arguments);
        };
        window.abrirInfoGrupo = abrir;
        const cab = document.querySelector('.chat-main-header .user-info');
        if (cab && !cab.dataset.mqGrupo) {
            cab.dataset.mqGrupo = '1';
            cab.addEventListener('click', function () { const id = convActual(); if (id && esGrupo(id)) abrir(id); });
        }
        // Al cambiar de conversación, el panel se cierra (no mostrar la información de otro grupo)
        const abrirPrevio = window.openConversation;
        if (typeof abrirPrevio === 'function' && !abrirPrevio.mqGrupo) {
            window.openConversation = function (id) { if (abierto && Number(id) !== abierto) cerrar(); return abrirPrevio.apply(this, arguments); };
            window.openConversation.mqGrupo = true;
        }
    }
    function engancharSocket() {
        const s = window._chatSocketVistos || window.chatSocket || window.socket;
        if (!s || typeof s.on !== 'function' || s.mqGrupoPanel) return;
        s.mqGrupoPanel = true;
        s.on('conversation_updated', function (d) { if (abierto && d && Number(d.conversation_id) === abierto) abrir(abierto); });
    }
    // Se instala después de chat-grupos.js (que también envuelve showChatInfo / openConversation)
    function iniciar() { setTimeout(instalar, 0); setTimeout(engancharSocket, 3000); setTimeout(engancharSocket, 7000); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar); else iniciar();
})();
