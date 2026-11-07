export const SYSTEM_FOLDER_LABELS: Record<string, string> = {
  INBOX: 'Bandeja de entrada',
  Sent: 'Enviados',
  Drafts: 'Borradores',
  Trash: 'Papelera',
  Junk: 'Correo no deseado',
  Archive: 'Archivo',
  Snoozed: 'Pospuestos',
  'Virtual.Todo': 'Todo el correo',
  // Nombres que traen otros servidores (Outlook, Thunderbird, migraciones) para las mismas carpetas.
  Spam: 'Correo no deseado',
  'Sent Items': 'Enviados',
  'Sent Messages': 'Enviados',
  'Deleted Items': 'Papelera',
  'Deleted Messages': 'Papelera',
  // Carpeta especial que crea Zimbra con las direcciones a las que se escribió; llega con la
  // migración. Solo cambia el nombre que se ve (revisión 04/11/2026, n.º 17).
  'Emailed Contacts': 'Contactos de correos enviados',
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
