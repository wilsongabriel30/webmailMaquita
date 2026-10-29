// Círculo con las iniciales de una persona (asignados de una tarea, miembros de una lista).
import { colorPersona, iniciales } from './iniciales';

export function CirculoPersona({ email, nombre, tamano = 24 }: { email: string; nombre?: string; tamano?: number }) {
  return (
    <span title={nombre ? `${nombre} (${email})` : email} aria-label={nombre || email}
      style={{
        width: tamano, height: tamano, borderRadius: '50%', flexShrink: 0, background: colorPersona(email), color: 'white',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: Math.round(tamano * 0.42), fontWeight: 600,
      }}>
      {iniciales(nombre || email)}
    </span>
  );
}
