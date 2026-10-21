/* Lo que devuelve GET /sitios/{dominio}/web (deploy/sitios/lib/nginx_web.py → ver). */

export interface Redireccion {
  origen: string; // «/ruta» o «*» (todo el dominio)
  destino: string;
  codigo: 301 | 302;
  subrutas?: boolean;
  conservar_ruta?: boolean;
}

export interface CarpetaPrivada { ruta: string; nombre: string; usuarios: string[] }

export interface Hotlink { activo: boolean; extensiones: string[]; permitidos: string[]; buscadores: boolean }

export interface Optimizacion {
  compresion: boolean;
  estaticos: string;
  cache_pagina: boolean;
  cache_minutos: number;
  brotli?: boolean;
  php?: boolean;
  caducidades?: string[];
}

export interface EstadoWeb {
  dominio: string;
  php: boolean;
  raiz_web: boolean;
  redirecciones: { lista: Redireccion[]; maximo: number };
  privacidad: { carpetas: CarpetaPrivada[]; maximo: number };
  errores: { paginas: Record<string, string>; codigos: string[]; candidatos: string[] };
  hotlink: Hotlink;
  bloqueo: { lista: string[]; maximo: number };
  optimizacion: Optimizacion;
}

export interface PropsPestana {
  dominio: string;
  estado: EstadoWeb;
  ocupado: boolean;
  /* Ejecuta la llamada, muestra el mensaje o el error y aplica el estado nuevo que devuelve el ayudante. */
  hacer: (mensaje: string, fn: () => Promise<EstadoWeb | void>) => Promise<boolean>;
}

export const campo = "px-2 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";
export const botonPrincipal = "px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50";
