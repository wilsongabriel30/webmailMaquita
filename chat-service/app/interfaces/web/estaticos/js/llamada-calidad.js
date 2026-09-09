// Decir en la propia llamada cómo va la conexión, y de quién es el problema.
//
// LiveKit ya baja la calidad solo cuando la red aprieta (adaptiveStream + dynacast), pero lo
// hacía en silencio: la imagen se veía peor o el audio se entrecortaba y nadie sabía si era su
// internet, el del otro, o que el sistema estaba fallando. Eso acaba en un parte de soporte.
//
// Aquí se enseña: una barra de señal para uno mismo y otra para la otra persona, y un aviso en
// palabras cuando la cosa se pone fea. Nombrar de quién es el problema evita media discusión.
(function (global) {
  'use strict';

  // Lo que LiveKit dice de una conexión, traducido a algo que una persona entienda.
  const NIVELES = {
    excellent: { barras: 3, color: '#107c10', texto: 'buena' },
    good:      { barras: 2, color: '#107c10', texto: 'aceptable' },
    poor:      { barras: 1, color: '#d18b00', texto: 'débil' },
    lost:      { barras: 0, color: '#a4262c', texto: 'perdida' },
    unknown:   { barras: 0, color: '#8a8886', texto: 'desconocida' },
  };

  function nivelDe(calidad) {
    const c = String(calidad || '').toLowerCase();
    return NIVELES[c] || NIVELES.unknown;
  }

  /** Dibuja tres barritas de señal, como las de la cobertura del móvil. */
  function pintarSenal(elemento, nivel) {
    elemento.innerHTML = '';
    for (let i = 1; i <= 3; i++) {
      const b = document.createElement('span');
      b.className = 'señal-barra';
      b.style.height = (4 + i * 3) + 'px';
      b.style.background = i <= nivel.barras ? nivel.color : 'rgba(255,255,255,.22)';
      elemento.appendChild(b);
    }
  }

  /**
   * Vigila la calidad de la llamada y la cuenta en pantalla.
   *
   * @param room       la sala de LiveKit ya conectada
   * @param opciones   { contenedor, avisar(texto|null), nombreDelOtro }
   *                   `avisar` recibe el texto del problema, o `null` cuando todo vuelve a ir
   *                   bien, para que quien llama decida dónde enseñarlo.
   */
  function vigilar(room, opciones) {
    const cont = opciones.contenedor;
    const avisar = opciones.avisar || function () {};
    const nombreDelOtro = opciones.nombreDelOtro || 'la otra persona';

    cont.innerHTML =
      '<div class="calidad-fila"><span class="calidad-etq">Tú</span>' +
      '<span class="señal" id="señalPropia"></span></div>' +
      '<div class="calidad-fila"><span class="calidad-etq">' + nombreDelOtro + '</span>' +
      '<span class="señal" id="señalOtro"></span></div>';

    const señalPropia = cont.querySelector('#señalPropia');
    const señalOtro = cont.querySelector('#señalOtro');
    pintarSenal(señalPropia, NIVELES.unknown);
    pintarSenal(señalOtro, NIVELES.unknown);

    const estado = { propia: 'unknown', otro: 'unknown', reconectando: false };

    /** El aviso que se enseña, si hay alguno que merezca la pena. */
    function repasar() {
      if (estado.reconectando) {
        avisar('Reconectando… la llamada sigue abierta');
        return;
      }
      const mala = (c) => c === 'poor' || c === 'lost';
      if (mala(estado.propia) && mala(estado.otro)) {
        avisar('La conexión va mal por los dos lados: el vídeo puede cortarse');
      } else if (mala(estado.propia)) {
        // Decírselo a quien puede hacer algo: acercarse al router, dejar de descargar…
        avisar('Tu conexión es ' + nivelDe(estado.propia).texto +
               ': se bajará la calidad del vídeo para que no se corte el audio');
      } else if (mala(estado.otro)) {
        avisar('La conexión de ' + nombreDelOtro + ' es ' + nivelDe(estado.otro).texto +
               ': puede que se le vea entrecortado');
      } else {
        avisar(null);
      }
    }

    const RE = global.LivekitClient && global.LivekitClient.RoomEvent;
    if (!RE) return { repasar };

    room.on(RE.ConnectionQualityChanged, (calidad, participante) => {
      const esMio = participante &&
        room.localParticipant && participante.sid === room.localParticipant.sid;
      const nivel = nivelDe(calidad);
      if (esMio) { estado.propia = String(calidad).toLowerCase(); pintarSenal(señalPropia, nivel); }
      else { estado.otro = String(calidad).toLowerCase(); pintarSenal(señalOtro, nivel); }
      repasar();
    });

    // Reconexión: LiveKit aguanta cortes cortos sin cerrar la llamada. Conviene decirlo, porque
    // si no la persona ve la imagen congelada y cuelga creyendo que se acabó.
    room.on(RE.Reconnecting, () => { estado.reconectando = true; repasar(); });
    room.on(RE.Reconnected, () => { estado.reconectando = false; repasar(); });

    room.on(RE.ParticipantDisconnected, () => {
      estado.otro = 'lost';
      pintarSenal(señalOtro, NIVELES.lost);
      repasar();
    });

    return { repasar };
  }

  global.LlamadaCalidad = { vigilar };
})(window);
