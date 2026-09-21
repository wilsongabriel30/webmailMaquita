/**
 * Dónde dibujar un menú contextual para que se vea entero.
 *
 * Al hacer clic derecho cerca del borde de abajo, el menú se abría hacia abajo igual y las
 * últimas opciones quedaban fuera de la pantalla. Aquí se mira el hueco que queda a cada lado
 * del cursor y, si no cabe hacia abajo pero sí hacia arriba, se abre hacia arriba. Lo mismo a
 * derecha e izquierda. Si no cabe por ningún lado, se pega al borde y se limita la altura para
 * que el propio menú pueda desplazarse.
 *
 * Es cálculo puro (sin DOM) para poder razonarlo y probarlo por separado.
 */

export interface Medidas {
  ancho: number;
  alto: number;
}

export interface Colocacion {
  left: number;
  top: number;
  /** Tope de altura cuando no cabe entero; el menú se desplaza por dentro. */
  maxAlto: number;
}

/** Aire que se deja contra el borde de la ventana. */
export const MARGEN = 8;

function encajar(valor: number, minimo: number, maximo: number): number {
  return Math.max(minimo, Math.min(valor, maximo));
}

/**
 * Coloca un menú abierto desde el punto (x, y) — normalmente el cursor.
 *
 * `preferirArriba` sirve para submenús alineados a un elemento: no hay «punto de clic», sino
 * un borde del que colgar.
 */
export function colocarMenu(
  x: number,
  y: number,
  menu: Medidas,
  ventana: Medidas,
  margen: number = MARGEN,
): Colocacion {
  // --- vertical ---
  const huecoAbajo = ventana.alto - y - margen;
  const huecoArriba = y - margen;
  let top: number;
  let maxAlto: number;

  if (menu.alto <= huecoAbajo) {
    top = y;
    maxAlto = huecoAbajo;
  } else if (menu.alto <= huecoArriba) {
    // Cabe arriba: se abre hacia arriba, con el borde de abajo en el cursor.
    top = y - menu.alto;
    maxAlto = huecoArriba;
  } else if (huecoAbajo >= huecoArriba) {
    // No cabe por ninguno: se usa el lado con más sitio y el menú se desplaza por dentro.
    top = y;
    maxAlto = huecoAbajo;
  } else {
    maxAlto = huecoArriba;
    top = margen;
  }

  // --- horizontal ---
  let left: number;
  if (x + menu.ancho + margen <= ventana.ancho) {
    left = x;
  } else if (x - menu.ancho >= margen) {
    left = x - menu.ancho;
  } else {
    left = ventana.ancho - menu.ancho - margen;
  }

  return {
    left: encajar(left, margen, Math.max(margen, ventana.ancho - margen)),
    top: encajar(top, margen, Math.max(margen, ventana.alto - margen)),
    maxAlto: Math.max(0, maxAlto),
  };
}

/** A qué lado y a qué altura cuelga un submenú del elemento que lo abre. */
export interface ColocacionSubmenu {
  /** `false` cuando no cabe a la derecha y hay que sacarlo por la izquierda. */
  aLaDerecha: boolean;
  /** Desplazamiento vertical respecto al elemento, en píxeles. */
  desplazamientoY: number;
  maxAlto: number;
}

export function colocarSubmenu(
  elemento: { left: number; right: number; top: number },
  submenu: Medidas,
  ventana: Medidas,
  margen: number = MARGEN,
): ColocacionSubmenu {
  const aLaDerecha =
    elemento.right + submenu.ancho + margen <= ventana.ancho ||
    elemento.left - submenu.ancho < margen;

  // El submenú arranca a la altura del elemento; si se sale por abajo, se sube lo justo.
  const desbordeAbajo = elemento.top + submenu.alto + margen - ventana.alto;
  const subir = desbordeAbajo > 0 ? Math.min(desbordeAbajo, elemento.top - margen) : 0;

  return {
    aLaDerecha,
    desplazamientoY: -subir,
    maxAlto: Math.max(0, ventana.alto - 2 * margen),
  };
}
