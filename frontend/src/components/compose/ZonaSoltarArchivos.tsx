/**
 * Zona para soltar archivos al redactar (07/11/2026).
 *
 * Antes, una imagen soltada sobre el texto quedaba DENTRO del cuerpo y soltada más arriba quedaba
 * como adjunto, sin que se notara la diferencia. Ahora, si lo que se arrastra trae imágenes,
 * aparecen dos zonas claras y se ilumina aquella donde está el ratón:
 *   arriba «Adjuntar» (los adjuntos quedan arriba, debajo del asunto) y abajo «Insertar en el texto».
 * Si no hay imágenes, toda la ventana es «Adjuntar».
 */
export type ZonaSoltar = 'adjuntar' | 'insertar';

const CLIP = 'M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13';
const IMAGEN = 'M3 16.5l5-5 4 4 3-3 6 6M3 5.25h18v13.5H3zM15.75 9a1.5 1.5 0 100-.01';

function Zona({ activa, icono, titulo, detalle }: { activa: boolean; icono: string; titulo: string; detalle: string }) {
  return (
    <div className="flex-1 flex items-center justify-center transition-colors" style={{
      border: `2px dashed ${activa ? '#0078d4' : '#a6c8e8'}`, borderRadius: 10,
      background: activa ? 'rgba(222,236,249,0.97)' : 'rgba(250,252,254,0.93)',
    }}>
      <div className="text-center px-4">
        <svg className="w-12 h-12 mx-auto mb-2" style={{ color: activa ? '#0078d4' : '#8a8886' }} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.4} d={icono} />
        </svg>
        <p className="text-[18px] font-semibold" style={{ color: activa ? '#0078d4' : '#605e5c' }}>{titulo}</p>
        <p className="text-[13px] text-[#605e5c] mt-1">{detalle}</p>
      </div>
    </div>
  );
}

export function ZonaSoltarArchivos({ conImagenes, zona }: { conImagenes: boolean; zona: ZonaSoltar }) {
  return (
    <div className="absolute inset-0 z-50 flex flex-col gap-2 p-2 bg-white/60">
      <Zona activa={!conImagenes || zona === 'adjuntar'} icono={CLIP} titulo="Adjuntar"
        detalle="Suelte aquí: quedan como archivos adjuntos, arriba, debajo del asunto" />
      {conImagenes && (
        <Zona activa={zona === 'insertar'} icono={IMAGEN} titulo="Insertar en el texto"
          detalle="Suelte aquí: las imágenes se ven dentro del mensaje" />
      )}
    </div>
  );
}
