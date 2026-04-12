import { getInitials, getAvatarColor } from './types';

export function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const initials = getInitials(name);
  const bg = getAvatarColor(name);
  const fontSize = size < 40 ? 13 : size < 60 ? 16 : 24;
  return (
    <div
      style={{
        width: size, height: size, borderRadius: '50%',
        backgroundColor: bg, color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize, fontWeight: 600, flexShrink: 0,
        fontFamily: "'Segoe UI', Calibri, sans-serif",
      }}
    >
      {initials}
    </div>
  );
}
