interface Props {
  name: string;
  permanent?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteDialog({ name, permanent, onConfirm, onCancel }: Props) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 24, width: 400,
        boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
        fontFamily: "'Segoe UI', Calibri, sans-serif",
      }}>
        <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: '#323130' }}>
          {permanent ? 'Eliminar permanentemente' : 'Eliminar contacto'}
        </h3>
        <p style={{ fontSize: 14, color: '#605e5c', margin: '12px 0 24px' }}>
          {permanent
            ? <>¿Eliminar permanentemente a <strong>{name}</strong>? Esta acción no se puede deshacer.</>
            : <>¿Mover a <strong>{name}</strong> a la papelera? Podrás restaurarlo en los próximos 30 días.</>
          }
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onCancel} style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 600,
            border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
            color: '#323130', cursor: 'pointer',
          }}>Cancelar</button>
          <button onClick={onConfirm} style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 600,
            border: 'none', borderRadius: 4, background: '#d13438',
            color: '#fff', cursor: 'pointer',
          }}>{permanent ? 'Eliminar definitivamente' : 'Eliminar'}</button>
        </div>
      </div>
    </div>
  );
}
