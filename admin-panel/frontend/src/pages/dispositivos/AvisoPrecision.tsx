// Aviso de precisión de una posición (pedido de dirección 22/09/2026): la ubicación de un celular es
// SIEMPRE aproximada; hay que decirlo con claridad y con el margen de error, para que nadie la tome
// como exacta. Solo mejora cuando la contrastan los avistamientos de otros teléfonos de la organización
// (baliza Bluetooth de la fase 2). También ofrece «Ver en mapa» en OpenStreetMap, Google Maps y Google Earth.

export interface PosicionAviso { lat: number; lon: number; precision_m?: number | null; fuente?: string; origen?: string; tomada_en?: string }

function grado(p: PosicionAviso): { titulo: string; color: string; texto: string } {
  const m = p.precision_m ? Math.round(p.precision_m) : null;
  if (p.origen === "avistamiento") return { titulo: "Ubicación por cercanía a otro teléfono", color: "bg-purple-50 border-purple-200 text-purple-900",
    texto: "Otro teléfono de la organización detectó este equipo por Bluetooth: está a unas decenas de metros de la posición de ESE teléfono, no en este punto exacto." };
  if (m == null) return { titulo: "Ubicación aproximada (margen desconocido)", color: "bg-amber-50 border-amber-200 text-amber-900",
    texto: "El teléfono no informó su margen de error. Tómela como una zona, no como un punto." };
  if (m <= 30) return { titulo: `Ubicación aproximada: margen de unos ${m} m (GPS)`, color: "bg-green-50 border-green-200 text-green-900",
    texto: "Buena precisión, típica de GPS al aire libre. Aun así, el punto puede estar desplazado ese margen: en un edificio o entre casas, mire toda la zona del círculo." };
  if (m <= 200) return { titulo: `Ubicación aproximada: margen de unos ${m} m`, color: "bg-amber-50 border-amber-200 text-amber-900",
    texto: "Precisión media (wifi o GPS bajo techo). El equipo puede estar en cualquier punto del círculo: una manzana entera, no una casa." };
  return { titulo: `Ubicación MUY aproximada: margen de unos ${m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${m} m`}`, color: "bg-red-50 border-red-200 text-red-900",
    texto: "Posición por antena de celular o red: solo indica el sector o barrio. No sirve para ubicar una casa o una calle." };
}

export function AvisoPrecision({ p, corroborada }: { p: PosicionAviso; corroborada?: boolean }) {
  const g = grado(p);
  const osm = `https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lon}#map=18/${p.lat}/${p.lon}`;
  const gmaps = `https://www.google.com/maps?q=${p.lat},${p.lon}`;
  const earth = `https://earth.google.com/web/@${p.lat},${p.lon},0a,600d,35y,0h,0t,0r`;
  return (
    <div className={`rounded border p-3 text-sm mb-3 ${g.color}`}>
      <div className="font-semibold">{g.titulo}</div>
      <p className="text-xs mt-1">{g.texto}</p>
      <p className="text-xs mt-1">
        {corroborada
          ? <>Coincide con avistamientos de otros teléfonos de la organización en la última hora: la zona es más fiable.</>
          : <>Ningún otro teléfono de la organización lo ha visto cerca en la última hora. La ubicación de un celular <strong>nunca es exacta</strong>; solo se afina cuando varios teléfonos lo detectan (triangulación por Bluetooth, disponible al declarar el equipo perdido).</>}
      </p>
      <div className="flex flex-wrap gap-3 mt-2 text-xs">
        <span className="font-medium">Ver en mapa:</span>
        <a className="text-ms-blue hover:underline" target="_blank" rel="noreferrer" href={osm}>OpenStreetMap</a>
        <a className="text-ms-blue hover:underline" target="_blank" rel="noreferrer" href={gmaps}>Google Maps</a>
        <a className="text-ms-blue hover:underline" target="_blank" rel="noreferrer" href={earth}>Google Earth</a>
        <span className="text-ms-gray-60">({p.lat.toFixed(5)}, {p.lon.toFixed(5)})</span>
      </div>
    </div>
  );
}
