/**
 * Zona para soltar archivos al redactar (07/11/2026; límite por el editor desde el 08/11/2026).
 *
 * Antes, una imagen soltada sobre el texto quedaba DENTRO del cuerpo y soltada más arriba quedaba
 * como adjunto, sin que se notara la diferencia. Ahora, si lo que se arrastra trae imágenes,
 * aparecen dos zonas claras y se ilumina aquella donde está el ratón:
 *   arriba «Adjuntar» (los adjuntos quedan arriba, debajo del asunto) y abajo «Insertar en el texto».
 * El límite entre ambas es el borde superior del editor de texto (no la mitad de la ventana), así la
 * zona «Insertar» coincide con el cuerpo del mensaje. Si no hay imágenes, toda la ventana es «Adjuntar».
 * Los colores van por clases para que el modo oscuro los pueda cambiar (dark-theme.css).
 */
export type ZonaSoltar = 'adjuntar' | 'insertar';

const CLIP = 'M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13';
const IMAGEN = 'M3 16.5l5-5 4 4 3-3 6 6M3 5.25h18v13.5H3zM15.75 9a1.5 1.5 0 100-.01';

function Zona({ activa, icono, titulo, detalle, estilo }: { activa: boolean; icono: string; titulo: string; detalle: string; estilo?: React.CSSProperties }) {
  return (
    <div className={`zona-soltar flex items-center justify-center transition-colors ${activa ? 'zona-soltar-activa' : ''}`}
      style={{ flex: '1 1 0', borderRadius: 10, ...estilo }}>
      <div className="text-center px-4">
        <svg className="zona-soltar-icono w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.4} d={icono} />
        </svg>
        <p className="zona-soltar-titulo text-[18px] font-semibold">{titulo}</p>
        <p className="zona-soltar-detalle text-[13px] mt-1">{detalle}</p>
      </div>
    </div>
  );
}

export function ZonaSoltarArchivos({ conImagenes, zona, limite }: { conImagenes: boolean; zona: ZonaSoltar; limite?: number | null }) {
  // Con imágenes: la zona de arriba mide hasta el borde del editor (limite, en px desde arriba del panel).
  const arriba: React.CSSProperties | undefined = conImagenes && limite ? { flex: `0 0 ${Math.max(60, limite - 12)}px` } : undefined;
  return (
    <div className="zona-soltar-fondo absolute inset-0 z-50 flex flex-col gap-2 p-2">
      <Zona activa={!conImagenes || zona === 'adjuntar'} icono={CLIP} titulo="Adjuntar" estilo={arriba}
        detalle="Suelte aquí: quedan como archivos adjuntos, arriba, debajo del asunto" />
      {conImagenes && (
        <Zona activa={zona === 'insertar'} icono={IMAGEN} titulo="Insertar en el texto"
          detalle="Suelte aquí: las imágenes se ven dentro del mensaje" />
      )}
    </div>
  );
}
