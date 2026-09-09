// Meter a alguien más en una llamada que ya está en marcha.
//
// Una llamada de dos vive en la sala `llamada_<a>_<b>`, y el servidor solo da entrada a esos dos
// —y hace bien: así nadie se cuela—. Por eso «agregar participante» no es meter a un tercero en
// esa sala, sino **pasar a una conferencia**: se crea una sala nueva, se invita a los dos que ya
// hablaban y al que se suma, y los tres se mudan allí.
//
// Se apoya en lo que ya existía para las llamadas grupales (`conference_invite` en el servidor,
// que guarda quién está invitado y solo deja entrar a esos, y el aviso con timbre que ya escucha
// el chat). Aquí no se inventa señalización nueva.
(function (global) {
  'use strict';

  let cache = null;

  /** Las personas a las que se puede llamar. Se piden una vez por llamada. */
  async function personas(busqueda) {
    if (cache && !busqueda) return cache;
    const url = '/api/chat/search/users' + (busqueda ? '?q=' + encodeURIComponent(busqueda) : '');
    const r = await fetch(url, { credentials: 'same-origin' });
    if (!r.ok) throw new Error('No se pudo obtener la lista de personas');
    const d = await r.json();
    const lista = d.users || d.usuarios || d.results || [];
    if (!busqueda) cache = lista;
    return lista;
  }

  function cerrar() {
    const m = document.getElementById('modalAgregar');
    if (m) m.remove();
  }

  /**
   * Abre el buscador para elegir a quién sumar.
   *
   * @param opciones { yo, otro:{id,nombre}, conversationId, tipo, alInvitar(roomId, invitados) }
   *        `alInvitar` lo decide quien llama: aquí no se navega ni se cuelga nada por nuestra
   *        cuenta, que es cosa de la pantalla de llamada.
   */
  function abrir(opciones) {
    cerrar();
    const modal = document.createElement('div');
    modal.id = 'modalAgregar';
    modal.className = 'agregar-fondo';
    modal.innerHTML =
      '<div class="agregar-caja" onclick="event.stopPropagation()">' +
      '  <div class="agregar-titulo">Agregar a la llamada</div>' +
      '  <div class="agregar-aviso">La llamada pasará a ser grupal: se avisará a ' +
           (opciones.otro && opciones.otro.nombre ? escapar(opciones.otro.nombre) : 'la otra persona') +
      '     y a quien elijas.</div>' +
      '  <input id="agregarBuscar" class="agregar-buscar" placeholder="Buscar persona…" autocomplete="off">' +
      '  <div id="agregarLista" class="agregar-lista"><div class="agregar-cargando">Cargando…</div></div>' +
      '  <button class="agregar-cancelar">Cancelar</button>' +
      '</div>';
    modal.onclick = cerrar;
    modal.querySelector('.agregar-cancelar').onclick = cerrar;
    document.body.appendChild(modal);

    const caja = modal.querySelector('#agregarLista');
    const buscador = modal.querySelector('#agregarBuscar');

    async function pintar(busqueda) {
      caja.innerHTML = '<div class="agregar-cargando">Buscando…</div>';
      let lista;
      try {
        lista = await personas(busqueda);
      } catch (e) {
        caja.innerHTML = '<div class="agregar-cargando">No se pudo cargar la lista de personas</div>';
        return;
      }
      // Fuera quien ya está en la llamada: ofrecerlos solo confunde.
      // El buscador del chat ya no se devuelve a sí mismo; basta con quitar a quien está al
      // otro lado de esta llamada.
      const fuera = new Set([String(opciones.otro && opciones.otro.id)]);
      const util = lista.filter((p) => !fuera.has(String(p.id)));
      if (!util.length) {
        caja.innerHTML = '<div class="agregar-cargando">Nadie más que añadir</div>';
        return;
      }
      caja.innerHTML = '';
      for (const p of util.slice(0, 40)) {
        const fila = document.createElement('button');
        fila.className = 'agregar-persona';
        fila.textContent = p.nombre || p.name || p.username || ('Usuario ' + p.id);
        fila.onclick = () => invitar(p);
        caja.appendChild(fila);
      }
    }

    function invitar(persona) {
      // La sala nueva: id irrepetible, como las que ya crea el chat para las grupales.
      const roomId = 'conf_' + Date.now() + '_' + Math.random().toString(36).slice(2, 11);
      const invitados = [
        { id: opciones.otro.id, nombre: opciones.otro.nombre || '' },
        { id: persona.id, nombre: persona.nombre || persona.name || '' },
      ];
      cerrar();
      opciones.alInvitar(roomId, invitados, persona);
    }

    let temporizador = null;
    buscador.oninput = () => {
      clearTimeout(temporizador);
      temporizador = setTimeout(() => pintar(buscador.value.trim()), 280);
    };
    buscador.focus();
    pintar('');
  }

  function escapar(s) {
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  global.LlamadaAgregar = { abrir, cerrar };
})(window);
