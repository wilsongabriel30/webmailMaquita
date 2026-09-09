// Las secciones del webmail tal como las abre una persona, con lo que debe verse en cada una.
// Sale del enrutador real (frontend/src/App.tsx), no de suposiciones.
const SECCIONES = [
  { id: 'correo', ruta: '/webmail/', nombre: 'Correo (bandeja)' },
  { id: 'contactos', ruta: '/webmail/contacts', nombre: 'Contactos' },
  { id: 'calendario', ruta: '/webmail/calendar', nombre: 'Calendario' },
  { id: 'tareas', ruta: '/webmail/tasks', nombre: 'Tareas' },
  { id: 'archivos', ruta: '/webmail/files', nombre: 'Archivos' },
  { id: 'asistente', ruta: '/webmail/asistente', nombre: 'Asistente' },
  { id: 'ajustes', ruta: '/webmail/settings', nombre: 'Ajustes' },
];

// Las de administración solo las ve quien administra; con la cuenta de pruebas se espera
// que NO se entre. Se recorren igual para comprobar que se rechaza con cabeza y no revienta.
const SECCIONES_ADMIN = [
  { id: 'admin', ruta: '/webmail/admin', nombre: 'Administración (panel)' },
  { id: 'admin-buzones', ruta: '/webmail/admin/mailboxes', nombre: 'Administración: buzones' },
  { id: 'admin-cola', ruta: '/webmail/admin/queue', nombre: 'Administración: cola' },
];

module.exports = { SECCIONES, SECCIONES_ADMIN };
