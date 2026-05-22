export const SYSTEM_FOLDER_LABELS: Record<string, string> = {
  INBOX: 'Bandeja de entrada',
  Sent: 'Enviados',
  Drafts: 'Borradores',
  Trash: 'Papelera',
  Junk: 'Correo no deseado',
  Archive: 'Archivo',
  Snoozed: 'Pospuestos',
};

export function getFolderDisplayName(name: string): string {
  if (!name) return '';
  if (SYSTEM_FOLDER_LABELS[name]) return SYSTEM_FOLDER_LABELS[name];
  if (name.includes('.')) return name.split('.').pop() || name;
  return name;
}
