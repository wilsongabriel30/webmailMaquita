import { useState } from 'react';

interface Props {
  onSave: (name: string, description: string) => void;
  onClose: () => void;
  saving: boolean;
}

export function NewListModal({ onSave, onClose, saving }: Props) {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px', fontSize: 14,
    border: '1px solid #8a8886', borderRadius: 4, outline: 'none',
    fontFamily: "'Segoe UI', Calibri, sans-serif", boxSizing: 'border-box',
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9998,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 28, width: 420,
        boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
        fontFamily: "'Segoe UI', Calibri, sans-serif",
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#323130' }}>Nueva lista</h3>
          <button onClick={onClose} style={{
            border: 'none', background: 'none', fontSize: 20,
            cursor: 'pointer', color: '#605e5c', padding: 4,
          }}>&times;</button>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#323130', display: 'block', marginBottom: 4 }}>
            Nombre de la lista *
          </label>
          <input style={inputStyle} value={name} onChange={e => setName(e.target.value)}
            placeholder="Ej: Equipo de ventas"
            onFocus={e => { e.target.style.borderColor = '#0078d4'; }}
            onBlur={e => { e.target.style.borderColor = '#8a8886'; }} />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: '#323130', display: 'block', marginBottom: 4 }}>
            Descripción
          </label>
          <textarea style={{ ...inputStyle, minHeight: 60, resize: 'vertical' }}
            value={desc} onChange={e => setDesc(e.target.value)}
            placeholder="Descripción opcional..."
            onFocus={e => { e.target.style.borderColor = '#0078d4'; }}
            onBlur={e => { e.target.style.borderColor = '#8a8886'; }} />
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 600,
            border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
            color: '#323130', cursor: 'pointer',
          }}>Cancelar</button>
          <button
            onClick={() => onSave(name.trim(), desc.trim())}
            disabled={saving || !name.trim()}
            style={{
              padding: '8px 24px', fontSize: 13, fontWeight: 600,
              border: 'none', borderRadius: 4,
              background: !name.trim() ? '#c8c6c4' : '#0078d4',
              color: '#fff', cursor: saving ? 'wait' : 'pointer',
            }}
          >{saving ? 'Creando...' : 'Crear lista'}</button>
        </div>
      </div>
    </div>
  );
}
