export const SYSTEM_FOLDER_LABELS: Record<string, string> = {
  INBOX: 'Bandeja de entrada',
  Sent: 'Enviados',
  Drafts: 'Borradores',
  Trash: 'Papelera',
  Junk: 'Correo no deseado',
  Archive: 'Archivo',
  Snoozed: 'Pospuestos',
  'Virtual.Todo': 'Todo el correo',
};

export function getFolderDisplayName(name: string): string {
  if (!name) return '';
  // Carpeta de una cuenta delegada: Compartidos,<cuenta>,<carpeta> (ver lib/cuentas.ts)
  if (name.startsWith('Compartidos,')) {
    const real = name.split(',').slice(2).join(',') || 'INBOX';
    return getFolderDisplayName(real);
  }
  if (SYSTEM_FOLDER_LABELS[name]) return SYSTEM_FOLDER_LABELS[name];
  if (name.includes('.')) return name.split('.').pop() || name;
  return name;
}
