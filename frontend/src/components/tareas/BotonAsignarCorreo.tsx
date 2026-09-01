// Botón «Asignar como tarea» para la vista de un correo: abre el diálogo con el correo enlazado como contexto.
import { useState } from 'react';
import { AsignarTareaDialogo, type CorreoRef } from './AsignarTareaDialogo';

export function BotonAsignarCorreo({ correo, estilo }: { correo: CorreoRef; estilo?: React.CSSProperties }) {
  const [abierto, setAbierto] = useState(false);
  return (<>
    <button style={estilo} onClick={() => setAbierto(true)} title="Convertir este correo en una tarea asignada con plazo">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 2 }}>
        <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
      </svg>
      Asignar como tarea
    </button>
    <AsignarTareaDialogo abierto={abierto} onCerrar={() => setAbierto(false)} correo={correo}
      onCreada={() => { try { (window as any).toastr?.success?.('Tarea asignada'); } catch {} }} />
  </>);
}
