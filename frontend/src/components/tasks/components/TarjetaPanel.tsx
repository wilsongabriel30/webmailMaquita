// Tarjeta del panel de detalle (como en Outlook): agrupa filas y pone una línea fina entre ellas.
import { Children, Fragment, type ReactNode } from 'react';
import { LINEA_TARJETA, tarjeta } from './estiloPanel';

export function TarjetaPanel({ children }: { children: ReactNode }) {
  const filas = Children.toArray(children).filter(Boolean);
  return (
    <div style={tarjeta}>
      {filas.map((f, i) => (
        <Fragment key={i}>
          {i > 0 && <div style={{ height: 1, background: LINEA_TARJETA, margin: '0 16px' }} />}
          {f}
        </Fragment>
      ))}
    </div>
  );
}
