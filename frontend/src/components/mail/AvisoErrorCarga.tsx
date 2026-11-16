/**
 * Aviso de la lista cuando la carga falló y no hay nada que mostrar.
 *
 * Dos motivos distintos, dos textos: el tope de peticiones seguidas del servidor (429) no es un problema
 * de conexión y se arregla esperando unos segundos (informe de Andes, 15/11/2026).
 */
export type MotivoErrorCarga = 'conexion' | 'limite';

export function AvisoErrorCarga({ motivo, alReintentar }: { motivo: MotivoErrorCarga; alReintentar: () => void }) {
  const limite = motivo === 'limite';
  return (
    <div className="flex flex-col items-center justify-center h-40 px-4 text-center text-[#323130]" role="alert">
      <p className="text-[14px] font-semibold">{limite ? 'Demasiadas acciones seguidas' : 'No se pudo cargar el correo'}</p>
      <p className="text-[13px] text-[#605e5c] mt-1">
        {limite
          ? 'Sus correos siguen guardados en el servidor. Espere unos segundos e inténtelo de nuevo.'
          : 'Sus correos siguen guardados en el servidor. Revise la conexión e inténtelo de nuevo.'}
      </p>
      <button onClick={alReintentar}
        className="mt-3 px-4 py-2 text-[14px] font-semibold text-white bg-[#0078d4] hover:bg-[#106ebe] rounded">
        Reintentar
      </button>
    </div>
  );
}
