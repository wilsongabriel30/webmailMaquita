import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMailStore } from '../../store/mailStore';
import { useThemeStore } from '../../store/themeStore';
import { api } from '../../api/client';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Command {
  id: string;
  label: string;
  category: string;
  icon: string;       // SVG path(s)
  shortcut?: string;
  action: () => void;
  keywords?: string;   // extra search tokens
}

interface ContactResult {
  id?: number;
  name: string;
  email: string;
}

/* ------------------------------------------------------------------ */
/*  SVG icon paths (heroicons-style, 24x24 viewBox)                   */
/* ------------------------------------------------------------------ */

const ICONS = {
  compose:     'M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z',
  reply:       'M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3',
  forward:     'M15 15l6-6m0 0l-6-6m6 6H9a6 6 0 000 12h3',
  search:      'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z',
  inbox:       'M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859M12 3v8.25m0 0l-3-3m3 3l3-3',
  sent:        'M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5',
  drafts:      'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z',
  trash:       'M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0',
  contacts:    'M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128H5.228A2 2 0 013 17.208V5.792A2 2 0 015.228 4h13.544A2 2 0 0121 5.792v3.252M15 19.128a9.308 9.308 0 01-3.214-5.198M12 12a3 3 0 100-6 3 3 0 000 6z',
  calendar:    'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5',
  settings:    'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
  admin:       'M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z',
  read:        'M21.75 9v.906a2.25 2.25 0 01-1.183 1.981l-6.478 3.488M2.25 9v.906a2.25 2.25 0 001.183 1.981l6.478 3.488m8.839 2.51l-4.66-2.51m0 0l-1.023-.55a2.25 2.25 0 00-2.134 0l-1.022.55m0 0l-4.661 2.51',
  archive:     'M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z',
  deleteMsg:   'M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0',
  selectAll:   'M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  moon:        'M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z',
  layout:      'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z',
  density:     'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5',
  contactSearch: 'M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128H5.228A2 2 0 013 17.208V5.792A2 2 0 015.228 4h13.544A2 2 0 0121 5.792v3.252M15 19.128a9.308 9.308 0 01-3.214-5.198M12 12a3 3 0 100-6 3 3 0 000 6z',
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const RECENT_KEY = 'cmdpalette_recent';
const MAX_RECENT = 3;

function getRecentIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveRecentId(id: string) {
  const recent = getRecentIds().filter((r) => r !== id);
  recent.unshift(id);
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)));
}

/** Simple fuzzy match: every character of the query appears in order in the target */
function fuzzyMatch(query: string, target: string): boolean {
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  let qi = 0;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) qi++;
  }
  return qi === q.length;
}

/* ------------------------------------------------------------------ */
/*  Icon component                                                     */
/* ------------------------------------------------------------------ */

function CmdIcon({ paths, className }: { paths: string; className?: string }) {
  const pathList = paths.split(' M').map((p, i) => (i === 0 ? p : 'M' + p));
  return (
    <svg
      className={className || 'w-4 h-4'}
      fill=none
      stroke=currentColor
      strokeWidth={1.5}
      strokeLinecap=round
      strokeLinejoin=round
      viewBox=0 0 24 24
    >
      {pathList.map((d, i) => (
        <path key={i} d={d} />
      ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [contactResults, setContactResults] = useState<ContactResult[]>([]);
  const [contactLoading, setContactLoading] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const contactTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  const mailStore = useMailStore();
  const themeStore = useThemeStore();

  /* ---------- build commands list ---------- */
  const commands: Command[] = useMemo(() => {
    const close = () => setOpen(false);
    return [
      // --- Correo ---
      {
        id: 'new-mail', label: 'Nuevo correo', category: 'Correo',
        icon: ICONS.compose, shortcut: 'N',
        action: () => { mailStore.openCompose('new'); close(); },
        keywords: 'componer escribir redactar nuevo',
      },
      {
        id: 'reply', label: 'Responder', category: 'Correo',
        icon: ICONS.reply, shortcut: 'R',
        action: () => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'r' })); close(); },
        keywords: 'responder contestar reply',
      },
      {
        id: 'forward', label: 'Reenviar', category: 'Correo',
        icon: ICONS.forward, shortcut: 'F',
        action: () => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'f' })); close(); },
        keywords: 'reenviar forward',
      },
      {
        id: 'search-mail', label: 'Buscar correos', category: 'Correo',
        icon: ICONS.search, shortcut: '/',
        action: () => { close(); setTimeout(() => document.getElementById('search-input')?.focus(), 50); },
        keywords: 'buscar search correo',
      },

      // --- Navegar ---
      {
        id: 'nav-inbox', label: 'Bandeja de entrada', category: 'Navegar',
        icon: ICONS.inbox,
        action: () => { mailStore.setCurrentFolder('INBOX'); navigate('/'); close(); },
        keywords: 'inbox bandeja entrada',
      },
      {
        id: 'nav-sent', label: 'Enviados', category: 'Navegar',
        icon: ICONS.sent,
        action: () => { mailStore.setCurrentFolder('Sent'); navigate('/'); close(); },
        keywords: 'enviados sent',
      },
      {
        id: 'nav-drafts', label: 'Borradores', category: 'Navegar',
        icon: ICONS.drafts,
        action: () => { mailStore.setCurrentFolder('Drafts'); navigate('/'); close(); },
        keywords: 'borradores drafts',
      },
      {
        id: 'nav-trash', label: 'Papelera', category: 'Navegar',
        icon: ICONS.trash,
        action: () => { mailStore.setCurrentFolder('Trash'); navigate('/'); close(); },
        keywords: 'papelera trash basura',
      },
      {
        id: 'nav-contacts', label: 'Contactos', category: 'Navegar',
        icon: ICONS.contacts,
        action: () => { navigate('/contacts'); close(); },
        keywords: 'contactos contacts',
      },
      {
        id: 'nav-calendar', label: 'Calendario', category: 'Navegar',
        icon: ICONS.calendar,
        action: () => { navigate('/calendar'); close(); },
        keywords: 'calendario calendar',
      },
      {
        id: 'nav-settings', label: 'Configuracion', category: 'Navegar',
        icon: ICONS.settings,
        action: () => { navigate('/settings'); close(); },
        keywords: 'configuracion ajustes settings',
      },
      {
        id: 'nav-admin', label: 'Admin', category: 'Navegar',
        icon: ICONS.admin,
        action: () => { navigate('/admin'); close(); },
        keywords: 'admin administracion panel',
      },

      // --- Acciones ---
      {
        id: 'mark-read', label: 'Marcar como leido', category: 'Acciones',
        icon: ICONS.read,
        action: () => {
          const st = useMailStore.getState();
          const uids = st.selectedUids.size > 0 ? Array.from(st.selectedUids)
            : st.selectedMessage ? [st.selectedMessage.uid] : [];
          if (uids.length) {
            api.post('/mail/bulk-action/' + encodeURIComponent(st.currentFolder), { uids, action: 'mark_read' });
            window.dispatchEvent(new CustomEvent('refresh-messages'));
          }
          close();
        },
        keywords: 'leido read marcar',
      },
      {
        id: 'archive', label: 'Archivar', category: 'Acciones',
        icon: ICONS.archive, shortcut: 'E',
        action: () => {
          const st = useMailStore.getState();
          const uids = st.selectedUids.size > 0 ? Array.from(st.selectedUids)
            : st.selectedMessage ? [st.selectedMessage.uid] : [];
          if (uids.length) {
            api.post('/mail/bulk-action/' + encodeURIComponent(st.currentFolder), { uids, action: 'archive' });
            st.setSelectedMessage(null);
            st.clearSelection();
            window.dispatchEvent(new CustomEvent('refresh-messages'));
          }
          close();
        },
        keywords: 'archivar archive',
      },
      {
        id: 'delete', label: 'Eliminar', category: 'Acciones',
        icon: ICONS.deleteMsg, shortcut: 'Del',
        action: () => {
          const st = useMailStore.getState();
          const uids = st.selectedUids.size > 0 ? Array.from(st.selectedUids)
            : st.selectedMessage ? [st.selectedMessage.uid] : [];
          if (uids.length) {
            const dest = st.currentFolder === 'Trash' ? '' : 'Trash';
            const act = st.currentFolder === 'Trash' ? 'delete' : 'move';
            api.post('/mail/bulk-action/' + encodeURIComponent(st.currentFolder), { uids, action: act, dest_folder: dest });
            st.setSelectedMessage(null);
            st.clearSelection();
            window.dispatchEvent(new CustomEvent('refresh-messages'));
          }
          close();
        },
        keywords: 'eliminar borrar delete',
      },
      {
        id: 'select-all', label: 'Seleccionar todos', category: 'Acciones',
        icon: ICONS.selectAll, shortcut: 'Ctrl+A',
        action: () => { mailStore.selectAll(); close(); },
        keywords: 'seleccionar todos select all',
      },

      // --- Vista ---
      {
        id: 'dark-mode', label: 'Modo oscuro', category: 'Vista',
        icon: ICONS.moon,
        action: () => { themeStore.toggle(); close(); },
        keywords: 'oscuro dark modo theme tema claro light',
      },
      {
        id: 'pane-right', label: 'Panel de lectura: Derecha', category: 'Vista',
        icon: ICONS.layout,
        action: () => { mailStore.setReadingPane('right'); close(); },
        keywords: 'panel lectura derecha right',
      },
      {
        id: 'pane-bottom', label: 'Panel de lectura: Abajo', category: 'Vista',
        icon: ICONS.layout,
        action: () => { mailStore.setReadingPane('bottom'); close(); },
        keywords: 'panel lectura abajo bottom',
      },
      {
        id: 'pane-off', label: 'Panel de lectura: Oculto', category: 'Vista',
        icon: ICONS.layout,
        action: () => { mailStore.setReadingPane('off'); close(); },
        keywords: 'panel lectura oculto off hidden',
      },
      {
        id: 'density-compact', label: 'Densidad: Compacta', category: 'Vista',
        icon: ICONS.density,
        action: () => { mailStore.setDensity('compact'); close(); },
        keywords: 'densidad compacta compact',
      },
      {
        id: 'density-medium', label: 'Densidad: Media', category: 'Vista',
        icon: ICONS.density,
        action: () => { mailStore.setDensity('medium'); close(); },
        keywords: 'densidad media medium',
      },
      {
        id: 'density-full', label: 'Densidad: Completa', category: 'Vista',
        icon: ICONS.density,
        action: () => { mailStore.setDensity('full'); close(); },
        keywords: 'densidad completa full',
      },

      // --- Contactos ---
      {
        id: 'search-contact', label: 'Buscar contacto', category: 'Contactos',
        icon: ICONS.contactSearch,
        action: () => { navigate('/contacts'); close(); },
        keywords: 'buscar contacto contact search',
      },
    ];
  }, [mailStore, themeStore, navigate]);

  /* ---------- filter commands ---------- */
  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    return commands.filter((c) => {
      const haystack = c.label + ' ' + (c.keywords || '') + ' ' + c.category;
      return fuzzyMatch(query, haystack);
    });
  }, [query, commands]);

  /* ---------- recent commands ---------- */
  const recentIds = useMemo(() => getRecentIds(), [open]);
  const recentCommands = useMemo(() => {
    if (query.trim()) return [];
    return recentIds
      .map((id) => commands.find((c) => c.id === id))
      .filter(Boolean) as Command[];
  }, [query, recentIds, commands]);

  /* ---------- grouped filtered results ---------- */
  const grouped = useMemo(() => {
    const cats: { category: string; items: Command[] }[] = [];
    const order = ['Correo', 'Navegar', 'Acciones', 'Vista', 'Contactos'];
    for (const cat of order) {
      const items = filtered.filter((c) => c.category === cat);
      if (items.length) cats.push({ category: cat, items });
    }
    return cats;
  }, [filtered]);

  /* ---------- flat list for keyboard nav ---------- */
  const flatItems = useMemo(() => {
    const items: Command[] = [];
    if (recentCommands.length && !query.trim()) {
      items.push(...recentCommands);
    }
    for (const g of grouped) {
      items.push(...g.items);
    }
    return items;
  }, [recentCommands, grouped, query]);

  /* ---------- contact search (live) ---------- */
  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setContactResults([]);
      return;
    }
    if (contactTimer.current) clearTimeout(contactTimer.current);
    contactTimer.current = setTimeout(async () => {
      setContactLoading(true);
      try {
        const res = await api.get<{ name: string; email: string }[]>(
          '/contacts/search?q=' + encodeURIComponent(query) + '&limit=5'
        );
        setContactResults(Array.isArray(res) ? res : []);
      } catch {
        setContactResults([]);
      }
      setContactLoading(false);
    }, 300);
    return () => { if (contactTimer.current) clearTimeout(contactTimer.current); };
  }, [query]);

  /* ---------- clamp selected index ---------- */
  const totalItems = flatItems.length + contactResults.length;
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  /* ---------- open/close with Ctrl+K ---------- */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        e.stopPropagation();
        setOpen((prev) => {
          if (!prev) {
            setQuery('');
            setSelectedIndex(0);
            setContactResults([]);
          }
          return !prev;
        });
      }
    };
    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, []);

  /* ---------- auto-focus input ---------- */
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [open]);

  /* ---------- execute a command ---------- */
  const execute = useCallback(
    (cmd: Command) => {
      saveRecentId(cmd.id);
      cmd.action();
    },
    []
  );

  /* ---------- execute contact action ---------- */
  const executeContact = useCallback(
    (c: ContactResult) => {
      setOpen(false);
      mailStore.openCompose('new', {
        to: [c.email],
        subject: '',
        text_body: '',
        html_body: '',
      });
    },
    [mailStore]
  );

  /* ---------- keyboard nav ---------- */
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const max = totalItems;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => (i + 1 >= max ? 0 : i + 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => (i - 1 < 0 ? max - 1 : i - 1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedIndex < flatItems.length) {
          execute(flatItems[selectedIndex]);
        } else {
          const ci = selectedIndex - flatItems.length;
          if (ci >= 0 && ci < contactResults.length) {
            executeContact(contactResults[ci]);
          }
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setOpen(false);
      }
    },
    [totalItems, flatItems, selectedIndex, contactResults, execute, executeContact]
  );

  /* ---------- scroll selected into view ---------- */
  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector('[data-selected=true]');
    if (el) el.scrollIntoView({ block: 'nearest' });
  }, [selectedIndex]);

  /* ---------- render nothing if closed ---------- */
  if (!open) return null;

  /* ---------- category order helper for rendering ---------- */
  let flatIndex = recentCommands.length && !query.trim() ? recentCommands.length : 0;

  return (
    <div
      className=fixed inset-0 z-[9999] flex items-start justify-center pt-[15vh]
      onClick={() => setOpen(false)}
    >
      {/* overlay */}
      <div className=absolute inset-0 bg-black/40 dark:bg-black/60 />

      {/* modal */}
      <div
        className=relative w-full max-w-[540px] bg-white dark:bg-[#2d2d2d] rounded-xl shadow-2xl border border-[#edebe9] dark:border-[#444] overflow-hidden
        onClick={(e) => e.stopPropagation()}
      >
        {/* search input */}
        <div className=flex items-center gap-2 px-4 py-3 border-b border-[#edebe9] dark:border-[#444]>
          <svg className=w-5 h-5 text-[#a19f9d] dark:text-[#888] flex-shrink-0 fill=none stroke=currentColor strokeWidth={1.5} viewBox=0 0 24 24>
            <path strokeLinecap=round strokeLinejoin=round d=M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z />
          </svg>
          <input
            ref={inputRef}
            type=text
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder=Escribe un comando o busca...
            className=flex-1 bg-transparent text-[14px] text-[#323130] dark:text-[#e0e0e0] placeholder-[#a19f9d] dark:placeholder-[#777] outline-none
          />
          <kbd className=hidden sm:inline-block text-[11px] text-[#a19f9d] dark:text-[#777] border border-[#edebe9] dark:border-[#555] rounded px-1.5 py-0.5 font-mono>
            ESC
          </kbd>
        </div>

        {/* results list */}
        <div ref={listRef} className=max-h-[360px] overflow-y-auto py-1>
          {/* recent */}
          {recentCommands.length > 0 && !query.trim() && (
            <div>
              <div className=px-4 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-[#a19f9d] dark:text-[#888]>
                Recientes
              </div>
              {recentCommands.map((cmd, i) => (
                <CommandItem
                  key={'recent-' + cmd.id}
                  cmd={cmd}
                  selected={selectedIndex === i}
                  index={i}
                  onClick={() => execute(cmd)}
                  onHover={() => setSelectedIndex(i)}
                />
              ))}
            </div>
          )}

          {/* grouped results */}
          {grouped.map((group) => {
            const startIdx = flatIndex;
            flatIndex += group.items.length;
            return (
              <div key={group.category}>
                <div className=px-4 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-[#a19f9d] dark:text-[#888]>
                  {group.category}
                </div>
                {group.items.map((cmd, i) => (
                  <CommandItem
                    key={cmd.id}
                    cmd={cmd}
                    selected={selectedIndex === startIdx + i}
                    index={startIdx + i}
                    onClick={() => execute(cmd)}
                    onHover={() => setSelectedIndex(startIdx + i)}
                  />
                ))}
              </div>
            );
          })}

          {/* contact results */}
          {contactResults.length > 0 && (
            <div>
              <div className=px-4 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-[#a19f9d] dark:text-[#888]>
                Contactos
              </div>
              {contactResults.map((c, i) => {
                const idx = flatItems.length + i;
                return (
                  <div
                    key={'contact-' + c.email}
                    data-selected={selectedIndex === idx}
                    className={
                      'flex items-center gap-3 px-4 py-2 cursor-pointer text-[13px] ' +
                      (selectedIndex === idx
                        ? 'bg-[#deecf9] dark:bg-[#264f78] text-[#323130] dark:text-white'
                        : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#383838]')
                    }
                    onClick={() => executeContact(c)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                  >
                    <CmdIcon paths={ICONS.contacts} className=w-4 h-4 text-[#605e5c] dark:text-[#aaa] />
                    <span className=flex-1 truncate>
                      {c.name ? c.name + ' — ' + c.email : c.email}
                    </span>
                    <span className=text-[11px] text-[#a19f9d] dark:text-[#777]>Correo</span>
                  </div>
                );
              })}
            </div>
          )}

          {contactLoading && query.length >= 2 && (
            <div className=px-4 py-2 text-[12px] text-[#a19f9d] dark:text-[#777]>Buscando contactos...</div>
          )}

          {/* empty state */}
          {flatItems.length === 0 && contactResults.length === 0 && !contactLoading && query.trim() && (
            <div className=px-4 py-8 text-center text-[13px] text-[#a19f9d] dark:text-[#777]>
              No se encontraron resultados
            </div>
          )}
        </div>

        {/* footer */}
        <div className=flex items-center gap-4 px-4 py-2 border-t border-[#edebe9] dark:border-[#444] text-[11px] text-[#a19f9d] dark:text-[#777]>
          <span className=flex items-center gap-1>
            <kbd className=border border-[#edebe9] dark:border-[#555] rounded px-1 py-0.5 font-mono>↑↓</kbd>
            navegar
          </span>
          <span className=flex items-center gap-1>
            <kbd className=border border-[#edebe9] dark:border-[#555] rounded px-1 py-0.5 font-mono>↵</kbd>
            seleccionar
          </span>
          <span className=flex items-center gap-1>
            <kbd className=border border-[#edebe9] dark:border-[#555] rounded px-1 py-0.5 font-mono>esc</kbd>
            cerrar
          </span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Command Item sub-component                                        */
/* ------------------------------------------------------------------ */

function CommandItem({
  cmd,
  selected,
  index,
  onClick,
  onHover,
}: {
  cmd: Command;
  selected: boolean;
  index: number;
  onClick: () => void;
  onHover: () => void;
}) {
  return (
    <div
      data-selected={selected}
      data-index={index}
      className={
        'flex items-center gap-3 px-4 py-2 cursor-pointer text-[13px] ' +
        (selected
          ? 'bg-[#deecf9] dark:bg-[#264f78] text-[#323130] dark:text-white'
          : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#383838]')
      }
      onClick={onClick}
      onMouseEnter={onHover}
    >
      <CmdIcon paths={cmd.icon} className=w-4 h-4 text-[#605e5c] dark:text-[#aaa] flex-shrink-0 />
      <span className=flex-1 truncate>{cmd.label}</span>
      {cmd.shortcut && (
        <kbd className=text-[11px] text-[#a19f9d] dark:text-[#777] border border-[#edebe9] dark:border-[#555] rounded px-1.5 py-0.5 font-mono flex-shrink-0>
          {cmd.shortcut}
        </kbd>
      )}
    </div>
  );
}
