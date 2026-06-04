import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { togglePins } from '../../lib/pins';
import { useMailStore } from '../../store/mailStore';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import { Ribbon } from '../compose/Ribbon';
import { getFolderDisplayName } from '../../folders';
import { getCachedLabels, useLabels } from '../../hooks/useLabels';
import { SnoozeModal } from './SnoozeModal';
import { sanitizeHtml } from '../../lib/sanitize';
import { useResponsive } from '../../hooks/useResponsive';


function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

//  Icon SVG paths (heroicons-style)
const ICONS = {
  hamburger: 'M4 6h16M4 12h16M4 18h16',
  newMail: 'M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75',
  ignore: 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
  block: 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z',
  delete: 'M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0',
  archive: 'M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z',
  report: 'M3 3v1.5M3 21v-6m0 0l2.77-1.22a9.7 9.7 0 016.208.682l.108.054a9.7 9.7 0 006.208.682L21 15V3.54a.75.75 0 00-.896-.737 9.7 9.7 0 01-6.208-.682l-.108-.054a9.7 9.7 0 00-6.208-.682L3 3',
  reply: 'M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3',
  replyAll: 'M7 15L1 9m0 0l6-6M1 9h10M11 15L5 9m0 0l6-6M5 9h14a6 6 0 010 12h-3',
  forward: 'M15 15l6-6m0 0l-6-6m6 6H9a6 6 0 000 12h3',
  clean: 'M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.764m3.42 3.42a6.776 6.776 0 00-3.42-3.42',
  move: 'M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z',
  rules: 'M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75',
  read: 'M21.75 9v.906a2.25 2.25 0 01-1.183 1.981l-6.478 3.488M2.25 9v.906a2.25 2.25 0 001.183 1.981l6.478 3.488m8.839 0l.415.223a.75.75 0 00.882-.264l2.197-2.989M2.25 15.577l.415.223a.75.75 0 01.882-.264l2.197-2.989',
  unread: 'M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0l-9.75 6-9.75-6',
  classify: 'M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z M6 6h.008v.008H6V6z',
  flag: 'M3 3v1.5M3 21v-6m0 0l2.77-1.22a9.7 9.7 0 016.208.682l.108.054a9.7 9.7 0 006.208.682L21 15V3.54a.75.75 0 00-.896-.737 9.7 9.7 0 01-6.208-.682l-.108-.054a9.7 9.7 0 00-6.208-.682L3 3',
  pin: 'M15 10.5a3 3 0 11-6 0 3 3 0 016 0z M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z',
  snooze: 'M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z',
  print: 'M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5zm-3 0h.008v.008H15V10.5z',
  apps: 'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z',
  groups: 'M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z',
  undo: 'M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3',
  settings: 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
  conversation: 'M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155',
  preview: 'M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
  zoom: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z',
  sync: 'M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182',
  ribbon: 'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12',
  folderPanel: 'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5',
  readingPane: 'M9 4.5v15m6-15v15M3.75 4.5h16.5a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H3.75a.75.75 0 01-.75-.75V5.25a.75.75 0 01.75-.75z',
  myDay: 'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5',
  density: 'M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5',
  immersive: 'M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25',
  help: 'M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z',
  recommend: 'M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18',
  feedback: 'M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z',
  diagnostic: 'M11.42 15.17l-5.66-5.66a8 8 0 1111.32 0l-5.66 5.66zm0 0L3 23.59m8.42-8.42L19.84 23.6M8.42 20H3.6m12.38 0h4.82',
  mobile: 'M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3',
  chevronDown: 'M19.5 8.25l-7.5 7.5-7.5-7.5',
  chevronUp: 'M4.5 15.75l7.5-7.5 7.5 7.5',
  info: 'M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z',
  export: 'M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3',
  account: 'M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z',
};

//  SVG Icon component
function SvgIcon({ d, size = 28, color = 'currentColor' }: {
  d: string; size?: number; color?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={1.2} strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

//  Dropdown wrapper — portal to body to escape overflow containers
function Dropdown({ open, onClose, children, align = 'left' }: {
  open: boolean; onClose: () => void; children: React.ReactNode; align?: 'left' | 'right';
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  const anchorRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: -9999, left: -9999 });

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node) &&
          anchorRef.current && !anchorRef.current.parentElement?.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, onClose]);

  useEffect(() => {
    if (!open || !anchorRef.current) return;
    const parent = anchorRef.current.parentElement;
    if (!parent) return;
    const rect = parent.getBoundingClientRect();
    const menuWidth = ref_width(menuRef) || 180;
    let left = align === 'right' ? rect.right - menuWidth : rect.left;
    if (left + menuWidth > window.innerWidth) left = window.innerWidth - menuWidth - 8;
    if (left < 4) left = 4;
    let top = rect.bottom + 2;
    // If menu would go below viewport, show above
    if (top + 300 > window.innerHeight) top = rect.top - 300;
    setPos({ top, left });
  }, [open, align]);

  function ref_width(r: React.RefObject<HTMLDivElement | null>) {
    return r.current?.offsetWidth || 0;
  }

  return (
    <>
      <span ref={anchorRef} style={{ position: 'absolute', top: 0, left: 0, width: 0, height: 0, overflow: 'hidden' }} />
      {open && ReactDOM.createPortal(
        <div ref={menuRef} style={{ position: 'fixed', top: pos.top, left: pos.left, zIndex: 9999 }}
          className="bg-white border border-[#e1dfdd] rounded shadow-lg min-w-[180px] py-1 ">
          {children}
        </div>,
        document.body
      )}
    </>
  );
}

function ArchivoMenu({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  const menuRef = useRef<HTMLDivElement>(null);
  const anchorRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: -9999, left: -9999 });

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        const btn = (e.target as HTMLElement).closest('button');
        if (btn && btn.textContent?.trim() === 'Archivo') return;
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  useEffect(() => {
    if (!anchorRef.current) return;
    const parent = anchorRef.current.parentElement;
    if (!parent) return;
    const rect = parent.getBoundingClientRect();
    setPos({ top: rect.bottom, left: rect.left });
  }, []);

  return (
    <>
      <span ref={anchorRef} style={{ position: 'absolute', top: 0, left: 0, width: 0, height: 0, overflow: 'hidden' }} />
      {ReactDOM.createPortal(
        <div ref={menuRef} style={{ position: 'fixed', top: pos.top, left: pos.left, zIndex: 9999 }}
          className="bg-[#0078d4] border border-[#005a9e] rounded shadow-lg min-w-[200px] py-1">
          {children}
        </div>,
        document.body
      )}
    </>
  );
}

function DropdownItem({ label, icon, onClick, danger, active }: {
  label: string; icon?: string; onClick: () => void; danger?: boolean; active?: boolean;
}) {
  return (
    <button onClick={onClick}
      className={`w-full text-left px-3 py-1.5 text-[13px] flex items-center gap-2 hover:bg-[#f3f2f1] ${danger ? 'text-[#d13438]' : active ? 'text-[#0078d4] bg-[#f0f6ff] font-semibold' : 'text-[#323130]'}`}>
      {icon && (/^[Mm]/.test(icon) ? <SvgIcon d={icon} size={16} color={danger ? '#d13438' : active ? '#0078d4' : '#605e5c'} /> : <span className='text-[14px] leading-none'>{icon}</span>)}
      <span>{label}</span>
      {active && <svg width={14} height={14} viewBox="0 0 20 20" fill="#0078d4" className="ml-auto"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>}
    </button>
  );
}

//  Toolbar Button
function ToolbarButton({ icon, label, onClick, hasDropdown, active, primary, danger, disabled, className }: {
  icon: string; label: string; onClick: () => void; hasDropdown?: boolean;
  active?: boolean; primary?: boolean; danger?: boolean; disabled?: boolean; className?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={label}
      className={`
        flex flex-col items-center justify-center px-2 py-1 rounded min-w-[48px] text-center
        transition-colors duration-100 select-none
        ${primary ? 'bg-[#0078d4] text-white hover:bg-[#106ebe]' : ''}
        ${active && !primary ? 'bg-[#e1dfdd] text-[#0078d4]' : ''}
        ${!primary && !active ? 'text-[#323130] hover:bg-[#f3f2f1]' : ''}
        ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
        ${className || ''}
      `}
    >
      <SvgIcon d={icon} size={28} color={danger ? '#d13438' : primary ? 'white' : active ? '#0078d4' : 'currentColor'} />
      <span className={`text-[10px] mt-0.5 leading-tight whitespace-nowrap flex items-center gap-0.5 ${danger ? 'text-[#d13438]' : ''}`}>
        {label}{hasDropdown && <span className="text-[8px]">&#9662;</span>}
      </span>
    </button>
  );
}

//  Group separator
function Sep() {
  return <div className="w-px h-[56px] bg-[#edebe9] mx-1 flex-shrink-0" />;
}

//  Group wrapper with label
function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center">
      <div className="flex items-end gap-0.5">{children}</div>
      <span className="text-[9px] text-[#a19f9d] mt-0.5 leading-none">{label}</span>
    </div>
  );
}


// ── Mobile Toolbar: compact single-row with essential actions + overflow ──
function MobileToolbar({ onCompose, onDelete, onReply, onReplyAll, onForward, onArchive, onFlag, onToggleRead, onPrint, msg }: {
  onCompose: () => void; onDelete: () => void; onReply: () => void; onReplyAll: () => void;
  onForward: () => void; onArchive: () => void; onFlag: () => void; onToggleRead: () => void;
  onPrint: () => void; msg: any;
}) {
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!moreOpen) return;
    const handler = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [moreOpen]);

  const iconBtn = (d: string, label: string, onClick: () => void, opts?: { primary?: boolean; danger?: boolean; active?: boolean }) => (
    <button onClick={onClick} title={label}
      className={`w-10 h-10 flex items-center justify-center rounded-lg transition-colors ${
        opts?.primary ? 'bg-[#0078d4] text-white active:bg-[#106ebe]' :
        opts?.danger ? 'text-[#d13438] active:bg-red-50' :
        opts?.active ? 'text-[#0078d4] bg-[#e1dfdd]' :
        'text-[#323130] active:bg-[#e1dfdd]'
      }`}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
        stroke={opts?.primary ? 'white' : opts?.danger ? '#d13438' : opts?.active ? '#0078d4' : '#323130'}
        strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
    </button>
  );

  return (
    <div className="flex items-center gap-1 px-2 py-1.5 bg-white border-b border-[#edebe9]">
      {iconBtn(ICONS.newMail, 'Nuevo correo', onCompose, { primary: true })}
      <div className="w-px h-6 bg-[#edebe9] mx-0.5" />
      {iconBtn(ICONS.reply, 'Responder', onReply)}
      {iconBtn(ICONS.forward, 'Reenviar', onForward)}
      {iconBtn(ICONS.delete, 'Eliminar', onDelete, { danger: true })}
      {iconBtn(ICONS.archive, 'Archivar', onArchive)}
      {iconBtn(ICONS.flag, 'Marcar', onFlag, { active: msg?.flagged })}
      <div className="flex-1" />
      <div className="relative" ref={moreRef}>
        {iconBtn('M12 6.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 12.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 18.75a.75.75 0 110-1.5.75.75 0 010 1.5z', 'Más acciones', () => setMoreOpen(!moreOpen))}
        {moreOpen && (
          <div className="absolute right-0 top-full mt-1 bg-white border border-[#e1dfdd] rounded-lg shadow-xl z-[200] min-w-[200px] py-1">
            <button onClick={() => { onReplyAll(); setMoreOpen(false); }}
              className="w-full text-left px-4 py-2.5 text-[13px] flex items-center gap-3 hover:bg-[#f3f2f1] text-[#323130]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d={ICONS.replyAll} /></svg>
              Responder a todos
            </button>
            <button onClick={() => { onToggleRead(); setMoreOpen(false); }}
              className="w-full text-left px-4 py-2.5 text-[13px] flex items-center gap-3 hover:bg-[#f3f2f1] text-[#323130]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d={msg?.seen ? ICONS.unread : ICONS.read} /></svg>
              {msg?.seen ? 'Marcar no leído' : 'Marcar leído'}
            </button>
            <button onClick={() => { onPrint(); setMoreOpen(false); }}
              className="w-full text-left px-4 py-2.5 text-[13px] flex items-center gap-3 hover:bg-[#f3f2f1] text-[#323130]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d={ICONS.print} /></svg>
              Imprimir
            </button>
            <div className="h-px bg-[#edebe9] my-1" />
            <button onClick={() => { window.dispatchEvent(new CustomEvent('toggle-sidebar')); setMoreOpen(false); }}
              className="w-full text-left px-4 py-2.5 text-[13px] flex items-center gap-3 hover:bg-[#f3f2f1] text-[#323130]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d={ICONS.folderPanel} /></svg>
              Carpetas
            </button>
            <button onClick={() => { window.dispatchEvent(new CustomEvent('refresh-messages')); setMoreOpen(false); }}
              className="w-full text-left px-4 py-2.5 text-[13px] flex items-center gap-3 hover:bg-[#f3f2f1] text-[#323130]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d={ICONS.sync} /></svg>
              Sincronizar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

//  Main Toolbar Component
export function Toolbar() {
  const navigate = useNavigate();
  const { labels, loading: labelsLoading, supported: labelsSupported, fetchLabels, createLabel, assignLabel, unassignLabel } = useLabels();
  const selectedMessage = useMailStore(s => s.selectedMessage);
  const selectedUids = useMailStore(s => s.selectedUids);
  const currentFolder = useMailStore(s => s.currentFolder);
  const clearSelection = useMailStore(s => s.clearSelection);
  const openCompose = useMailStore(s => s.openCompose);
  const folders = useMailStore(s => s.folders);
  const viewMode = useMailStore(s => s.viewMode);
  const setViewMode = useMailStore(s => s.setViewMode);
  const readingPane = useMailStore(s => s.readingPane);
  const setReadingPane = useMailStore(s => s.setReadingPane);
  const density = useMailStore(s => s.density);
  const setDensity = useMailStore(s => s.setDensity);
  const previewLines = useMailStore(s => s.previewLines);
  const setPreviewLines = useMailStore(s => s.setPreviewLines);
  const showMyDay = useMailStore(s => s.showMyDay);
  const setShowMyDay = useMailStore(s => s.setShowMyDay);
  const composeWindows = useMailStore(s => s.composeWindows);
  const activeEditor = useMailStore(s => s.activeEditor);
  const composeRibbonTab = useMailStore(s => s.composeRibbonTab);
  const setComposeRibbonTab = useMailStore(s => s.setComposeRibbonTab);

    const { isMobile } = useResponsive();

  const [activeTab, setActiveTab] = useState<'inicio' | 'vista' | 'ayuda'>('inicio');
  const [collapsed, setCollapsed] = useState(false);
  const [hamburgerTooltip, setHamburgerTooltip] = useState(false);
  const [archivoOpen, setArchivoOpen] = useState(false);

  // Dropdown states
  const [replyOpen, setReplyOpen] = useState(false);
  const [blockOpen, setBlockOpen] = useState(false);
  const [cleanOpen, setCleanOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [classifyOpen, setClassifyOpen] = useState(false);
  const [flagOpen, setFlagOpen] = useState(false);
  const [snoozeOpen, setSnoozeOpen] = useState(false);
  const [convOpen, setConvOpen] = useState(false);
  const [previewLinesOpen, setPreviewLinesOpen] = useState(false);
  const [ribbonMenuOpen, setRibbonMenuOpen] = useState(false);
  const [folderPanelOpen, setFolderPanelOpen] = useState(false);
  const [readingPaneOpen, setReadingPaneOpen] = useState(false);
  const [densityOpen, setDensityOpen] = useState(false);
  const [, setMyDayOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [addinsOpen, setAddinsOpen] = useState(false);

  // Ribbon scroll indicator
  const ribbonRef = useRef<HTMLDivElement>(null);
  const [showScrollArrow, setShowScrollArrow] = useState(false);

  const checkRibbonOverflow = useCallback(() => {
    const el = ribbonRef.current;
    if (!el) return;
    const hasOverflow = el.scrollWidth > el.clientWidth + 2;
    const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 2;
    setShowScrollArrow(hasOverflow && !atEnd);
  }, []);

  useEffect(() => {
    checkRibbonOverflow();
    window.addEventListener('resize', checkRibbonOverflow);
    return () => window.removeEventListener('resize', checkRibbonOverflow);
  }, [checkRibbonOverflow, activeTab]);

  const scrollRibbonRight = useCallback(() => {
    const el = ribbonRef.current;
    if (el) {
      el.scrollBy({ left: 200, behavior: 'smooth' });
      setTimeout(checkRibbonOverflow, 350);
    }
  }, [checkRibbonOverflow]);

  const hasCompose = composeWindows && composeWindows.some(w => !w.minimized);

  // Compose tabs
  const composeTabs = ['Mensaje', 'Insertar', 'Aplicar formato', 'Opciones'] as const;
  type ComposeTab = typeof composeTabs[number];
  const composeTabMap: Record<ComposeTab, 'message' | 'insert' | 'format' | 'options'> = {
    'Mensaje': 'message', 'Insertar': 'insert', 'Aplicar formato': 'format', 'Opciones': 'options',
  };
  const reverseComposeTabMap: Record<string, ComposeTab> = {
    'message': 'Mensaje', 'insert': 'Insertar', 'format': 'Aplicar formato', 'options': 'Opciones',
  };

  // Auto-switch tabs on compose open/close
  useEffect(() => {
    if (hasCompose) {
      setComposeRibbonTab('message');
    } else {
      setActiveTab('inicio');
    }
  }, [hasCompose, setComposeRibbonTab]);

  const closeAllDropdowns = useCallback(() => {
    setReplyOpen(false); setBlockOpen(false); setCleanOpen(false);
    setMoveOpen(false); setClassifyOpen(false); setFlagOpen(false);
    setSnoozeOpen(false); setConvOpen(false); setPreviewLinesOpen(false);
    setRibbonMenuOpen(false); setFolderPanelOpen(false); setReadingPaneOpen(false);
    setDensityOpen(false); setMyDayOpen(false); setRulesOpen(false);
    setArchivoOpen(false); setAddinsOpen(false);
  }, []);

  //  Actions
  const msg = selectedMessage;
  const uids: number[] = selectedUids.size > 0 ? Array.from(selectedUids) : (msg ? [msg.uid] : []);

  const moveToFolder = async (folder: string, toast?: string) => {
    if (!uids.length) { showToast('Selecciona un mensaje'); return; }
    try {
      await api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, { uids, action: 'move', dest_folder: folder });
      showToast(toast || `Movido a ${getFolderDisplayName(folder)}`);
      clearSelection();
      useMailStore.getState().setSelectedMessage(null);
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    } catch { showToast('Error al mover'); }
  };

  const goToSettings = useCallback((tab: 'general' | 'signature' | 'identities' | 'autoreply' | 'filters' | 'password' = 'general') => {
    closeAllDropdowns();
    navigate(`/settings?tab=${tab}`);
  }, [closeAllDropdowns, navigate]);

  const toggleRead = async () => {
    if (!uids.length) { showToast('Selecciona un mensaje'); return; }
    const seen = msg?.seen ? false : true;
    try {
      await api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, { uids, action: seen ? 'mark_read' : 'mark_unread', dest_folder: '' });
      showToast(seen ? 'Marcado como leído' : 'Marcado como no leído');
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    } catch { showToast('Error'); }
  };

  const toggleFlag = async () => {
    if (!uids.length) { showToast('Selecciona un mensaje'); return; }
    const flagged = msg?.flagged ? false : true;
    try {
      await api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, { uids, action: flagged ? 'flag' : 'unflag', dest_folder: '' });
      showToast(flagged ? 'Marcado con bandera' : 'Bandera eliminada');
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    } catch { showToast('Error'); }
  };

  const handlePin = () => {
    if (!uids.length) { showToast('Selecciona un mensaje'); return; }
    const pinned = togglePins(currentFolder, uids);
    showToast(pinned ? 'Mensaje fijado al inicio de la lista' : 'Mensaje desfijado');
    window.dispatchEvent(new CustomEvent('refresh-messages'));
  };

  const handleSnoozeClick = () => {
    if (!uids.length) { showToast('Selecciona un mensaje'); return; }
    closeAllDropdowns();
    setSnoozeOpen(true);
  };

  const applyPreviewLines = (lines: 1 | 2 | 3) => {
    setPreviewLines(lines);
    showToast(`Vista previa configurada en ${lines} ${lines === 1 ? 'línea' : 'líneas'}`);
    setPreviewLinesOpen(false);
  };

  const buildQuote = () => {
    if (!msg) return '';
    const date = msg.date ? new Date(msg.date).toLocaleString('es-EC') : '';
    const bodyHtml = msg.html_body ? sanitizeHtml(msg.html_body) : escapeHtml(msg.text_body || '');
    return `<br/><br/><div style="border-left:2px solid #0078d4;padding-left:12px;margin-left:0;color:#605e5c">
      <p style="margin:0 0 8px 0"><b>De:</b> ${escapeHtml(msg.from)}<br/>
      <b>Enviado:</b> ${escapeHtml(date)}<br/>
      <b>Para:</b> ${escapeHtml(msg.to)}<br/>
      ${msg.cc ? `<b>CC:</b> ${escapeHtml(msg.cc)}<br/>` : ''}
      <b>Asunto:</b> ${escapeHtml(msg.subject)}</p>
      <div>${bodyHtml}</div></div>`;
  };

  const doReply = () => {
    if (!msg) { showToast('Selecciona un mensaje'); return; }
    openCompose('reply', {
      to: [msg.from], subject: `Re: ${msg.subject}`,
      html_body: buildQuote(), text_body: '', in_reply_to: msg.message_id || '', references: msg.references || '',
    });
    closeAllDropdowns();
  };

  const doReplyAll = () => {
    if (!msg) { showToast('Selecciona un mensaje'); return; }
    openCompose('replyAll', {
      to: [msg.from], cc: msg.cc?.split(',').map(s=>s.trim()) || [], subject: `Re: ${msg.subject}`,
      html_body: buildQuote(), text_body: '', in_reply_to: msg.message_id || '', references: msg.references || '',
    });
    closeAllDropdowns();
  };

  const doForward = () => {
    if (!msg) { showToast('Selecciona un mensaje'); return; }
    openCompose('forward', {
      to: [], subject: `RV: ${msg.subject}`,
      html_body: buildQuote(), text_body: '',
      in_reply_to: msg.message_id || '', references: msg.references || '',
    });
    closeAllDropdowns();
  };

  const doPrint = () => {
    if (!msg) { showToast('Selecciona un mensaje'); return; }
    const w = window.open('', '_blank');
    if (!w) return;
    const date = escapeHtml(msg.date ? new Date(msg.date).toLocaleString('es-EC') : '');
    const safeSubject = escapeHtml(msg.subject || '');
    const safeFrom = escapeHtml(msg.from || '');
    const safeTo = escapeHtml(msg.to || '');
    const safeCc = msg.cc ? escapeHtml(msg.cc) : '';
    const safeBody = msg.html_body ? sanitizeHtml(msg.html_body) : escapeHtml(msg.text_body || '') || '<em>Sin contenido</em>';
    w.document.write(`<!DOCTYPE html><html><head><title>${safeSubject}</title>
      <style>
        @page { size: A4; margin: 20mm; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 12pt; color: #323130; margin: 20mm; }
        .header { border-bottom: 2px solid #0078d4; padding-bottom: 12px; margin-bottom: 16px; }
        .header h1 { font-size: 18pt; margin: 0 0 8px; }
        .header p { margin: 2px 0; font-size: 10pt; color: #605e5c; }
        .body { line-height: 1.6; }
        @media print { body { margin: 0; } }
      </style></head><body>
      <div class="header">
        <h1>${safeSubject}</h1>
        <p><strong>De:</strong> ${safeFrom}</p>
        <p><strong>Para:</strong> ${safeTo}</p>
        ${safeCc ? `<p><strong>CC:</strong> ${safeCc}</p>` : ''}
        <p><strong>Fecha:</strong> ${date}</p>
      </div>
      <div class="body">${safeBody}</div>
      </body></html>`);
    w.document.close();
    w.print();
  };

  const doDelete = async () => {
    if (!uids.length) { showToast('Selecciona un mensaje'); return; }
    if (currentFolder === 'Trash') {
      try {
        await api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, { uids, action: 'delete', dest_folder: '' });
        showToast('Eliminado permanentemente');
        clearSelection();
        useMailStore.getState().setSelectedMessage(null);
        window.dispatchEvent(new CustomEvent('refresh-messages'));
      } catch { showToast('Error al eliminar'); }
    } else {
      moveToFolder('Trash', 'Movido a Papelera');
    }
  };

  const doCleanFolder = async () => {
    try {
      await api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, { uids: [], action: 'delete', dest_folder: '' });
      showToast(`Carpeta ${getFolderDisplayName(currentFolder)} vaciada`);
      clearSelection();
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    } catch { showToast('Error al limpiar'); }
    closeAllDropdowns();
  };

  const doClassify = async (category: string) => {
    if (!uids.length) { showToast('Selecciona un mensaje'); return; }
    if (!labelsSupported) {
      showToast('Etiquetas no están disponibles en este servidor');
      closeAllDropdowns();
      return;
    }
    try {
      const categoryColors: Record<string, string> = {
        'Categoría azul': '#0078d4',
        'Categoría verde': '#107c10',
        'Categoría roja': '#d13438',
        'Categoría amarilla': '#ffb900',
        'Categoría morada': '#8764b8',
      };
      const categoryNames = Object.keys(categoryColors);
      let currentLabels = labels;
      if (labelsLoading || currentLabels.length === 0) {
        await fetchLabels();
        currentLabels = getCachedLabels();
      }
      const categoryLabels = currentLabels.filter((label) => categoryNames.includes(label.name));

      if (!category) {
        await Promise.all(categoryLabels.map((label) => unassignLabel(label.id, currentFolder, uids)));
        showToast('Categorías borradas');
      } else {
        let label = currentLabels.find((item) => item.name === category);
        if (!label) {
          try {
            label = await createLabel(category, categoryColors[category] || '#0078d4');
          } catch {
            await fetchLabels();
            currentLabels = getCachedLabels();
            label = currentLabels.find((item) => item.name === category);
            if (!label) throw new Error('Label sync failed');
          }
        }
        await assignLabel(label.id, currentFolder, uids);
        showToast(`Clasificado: ${category}`);
      }
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    } catch { showToast('Error al clasificar'); }
    closeAllDropdowns();
  };

  const exportSelectedMessage = async () => {
    if (!msg) { showToast('Selecciona un mensaje'); return; }
    try {
      const res = await fetch(`/api/mail/message/${encodeURIComponent(currentFolder)}/${msg.uid}/eml`, {
        credentials: 'include',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const safeSubject = (msg.subject || 'mensaje').replace(/[\\/:*?"<>|]+/g, '_');
      a.href = url;
      a.download = `${safeSubject}.eml`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      showToast('Error al exportar el mensaje');
    }
  };

  const showShortcuts = () => {
    showToast(
      'Atajos de teclado:\n' +
      'N  Nuevo correo\n' +
      'R  Responder\n' +
      'Shift+R  Responder a todos\n' +
      'F  Reenviar\n' +
      'E  Archivar\n' +
      'Delete  Eliminar\n' +
      '  Navegar mensajes\n' +
      'Enter  Abrir mensaje\n' +
      'Ctrl+Enter  Enviar correo\n' +
      'Esc  Cerrar redacción\n' +
      'Ctrl+A  Seleccionar todos\n' +
      '/  Buscar',
    );
  };

  const showDiagnostics = () => {
    const info = `Webmail Maquita v1.0\nNavegador: ${navigator.userAgent}\nResolución: ${window.innerWidth}x${window.innerHeight}\nFecha: ${new Date().toLocaleString('es-EC')}`;
    showToast(info);
  };

  //  Determine which compose tab is active (for highlighting)
  const activeComposeTab = composeRibbonTab ? (reverseComposeTabMap[composeRibbonTab] || 'Mensaje') : 'Mensaje';

  // Show compose ribbon area?
  const showComposeRibbon = hasCompose && composeRibbonTab;

  //  RENDER
  // Mobile: compact toolbar
  if (isMobile) {
    return (
      <MobileToolbar
        onCompose={() => openCompose('new')}
        onDelete={doDelete}
        onReply={doReply}
        onReplyAll={doReplyAll}
        onForward={doForward}
        onArchive={() => moveToFolder('Archive', 'Archivado')}
        onFlag={toggleFlag}
        onToggleRead={toggleRead}
        onPrint={doPrint}
        msg={msg}
      />
    );
  }

  return (
    <div className="flex flex-col bg-[#f3f2f1] border-b border-[#e1dfdd] select-none" style={{ overflow: 'visible' }}>
      {/*  Tab bar  */}
      <div className="flex items-center h-[36px] px-1 bg-[#f3f2f1] border-b border-[#edebe9]">
        {/* Hamburger */}
        <div className="relative">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('toggle-sidebar'))}
            onMouseEnter={() => { setHamburgerTooltip(true); setTimeout(() => setHamburgerTooltip(false), 3000); }}
            onMouseLeave={() => setHamburgerTooltip(false)}
            className="w-[36px] h-[36px] flex items-center justify-center hover:bg-[#e1dfdd] rounded"
          >
            <SvgIcon d={ICONS.hamburger} size={18} />
          </button>
          {hamburgerTooltip && (
            <div className="absolute left-full top-1/2 -translate-y-1/2 ml-1 z-[100] bg-[#323130] text-white text-xs px-2 py-1 rounded whitespace-nowrap">
              Alternar panel de carpetas
            </div>
          )}
        </div>

        {/* Archivo */}
        <div className="relative">
          <button
            onClick={() => { closeAllDropdowns(); setArchivoOpen(!archivoOpen); }}
            className={`px-3 h-[36px] text-[13px] hover:bg-[#e1dfdd] rounded ${archivoOpen ? 'bg-[#0078d4] text-white' : 'text-[#323130]'}`}
          >
            Archivo
          </button>
          {archivoOpen && (
            <ArchivoMenu onClose={() => setArchivoOpen(false)}>
              {[
                { label: 'Info cuenta', icon: ICONS.info, action: () => showToast('Cuenta: gestiontecnologia@ejemplo.com') },
                { label: 'Sincronizar', icon: ICONS.sync, action: () => window.dispatchEvent(new CustomEvent('refresh-messages')) },
                { label: 'Exportar', icon: ICONS.export, action: exportSelectedMessage },
                { label: 'Imprimir', icon: ICONS.print, action: doPrint },
                { label: 'Opciones cuenta', icon: ICONS.account, action: () => goToSettings('general') },
              ].map((item, i) => (
                <button key={i} onClick={() => { item.action(); setArchivoOpen(false); }}
                  className="w-full text-left px-3 py-2 text-[13px] text-white flex items-center gap-2 hover:bg-[#106ebe]">
                  <SvgIcon d={item.icon} size={16} color="white" />
                  <span>{item.label}</span>
                </button>
              ))}
            </ArchivoMenu>
          )}
        </div>

        {/* Main tabs */}
        {(['inicio', 'vista', 'ayuda'] as const).map(tab => (
          <button key={tab}
            onClick={() => { setActiveTab(tab); if (hasCompose) setComposeRibbonTab(null as any); }}
            className={`px-3 h-[36px] text-[13px] rounded capitalize ${
              activeTab === tab && !showComposeRibbon
                ? 'bg-white text-[#0078d4] font-semibold border-b-2 border-[#0078d4]'
                : 'text-[#323130] hover:bg-[#e1dfdd]'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}

        {/* Compose tabs (only when compose active) */}
        {hasCompose && (
          <>
            <div className="w-px h-[20px] bg-[#d2d0ce] mx-1" />
            {composeTabs.map(tab => (
              <button key={tab}
                onClick={() => { setComposeRibbonTab(composeTabMap[tab]); }}
                className={`px-3 h-[36px] text-[13px] rounded ${
                  showComposeRibbon && activeComposeTab === tab
                    ? 'bg-white text-[#0078d4] font-semibold border-b-2 border-[#0078d4]'
                    : 'text-[#323130] hover:bg-[#e1dfdd]'
                }`}
              >
                {tab}
              </button>
            ))}
          </>
        )}

        {/* Spacer + collapse button */}
        <div className="flex-1" />
        <button onClick={() => setCollapsed(!collapsed)}
          className="w-[36px] h-[36px] flex items-center justify-center hover:bg-[#e1dfdd] rounded text-[#605e5c]">
          <SvgIcon d={collapsed ? ICONS.chevronDown : ICONS.chevronUp} size={14} />
        </button>
      </div>

      {/*  Ribbon content area  */}
      {!collapsed && (
        <div className="bg-white" style={{ overflow: 'visible', position: 'relative' }}>
          {/* Compose Ribbon (when compose tab active) */}
          {showComposeRibbon ? (
            <div className="px-2 py-1 overflow-x-auto" style={{ scrollbarWidth: 'thin', scrollbarColor: '#c8c6c4 transparent' }}>
              {activeEditor ? (
                <Ribbon editor={activeEditor}
                  onAttach={() => {
                    // Trigger file input in ComposePanel via custom event
                    window.dispatchEvent(new CustomEvent('compose-attach'));
                  }}
                  onInsertSignature={(html?: string) => {
                    // La firma se gestiona en ComposePanel (se muestra editable
                    // ABAJO, no dentro del editor). El menu de firmas pasa el HTML
                    // elegido; lo mandamos por evento para que REEMPLACE la firma
                    // actual sin duplicar ni insertarla en el cuerpo.
                    window.dispatchEvent(new CustomEvent('compose-insert-signature', { detail: html ?? '' }));
                  }}
                  onSaveDraft={() => window.dispatchEvent(new CustomEvent('compose-save-draft'))}
                  onDownloadDraft={() => {
                    if (!activeEditor) return;
                    const html = activeEditor.getHTML();
                    const blob = new Blob([`<!DOCTYPE html><html><body style="font-family:Calibri">${html}</body></html>`], { type: 'text/html' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = 'borrador.html'; a.click();
                    URL.revokeObjectURL(url);
                  }}
                  onImportanceChange={(v) => showToast(`Importancia: ${v}`)}
                  onImproveWriting={() => window.dispatchEvent(new CustomEvent('compose-improve-writing'))}
                  onScheduleSend={() => window.dispatchEvent(new CustomEvent('compose-schedule-send'))}
                  onOpenApps={() => window.dispatchEvent(new CustomEvent('compose-open-apps'))}
                  onReviewEditor={() => window.dispatchEvent(new CustomEvent('compose-review-editor'))}
                  onCheckAccessibility={() => window.dispatchEvent(new CustomEvent('compose-check-accessibility'))}
                  onDictate={() => window.dispatchEvent(new CustomEvent('compose-dictate'))}
                  onShowCc={() => window.dispatchEvent(new CustomEvent('compose-show-cc'))}
                  onShowBcc={() => window.dispatchEvent(new CustomEvent('compose-show-bcc'))}
                  onTrackingChange={(t) => window.dispatchEvent(new CustomEvent('compose-tracking-change', { detail: t }))}
                />
              ) : (
                <div className="flex items-center justify-center h-[72px] text-[13px] text-[#a19f9d]">
                  Cargando editor...
                </div>
              )}
            </div>
          ) : (
            <div className="relative">
            <div ref={ribbonRef} onScroll={checkRibbonOverflow}
              className="flex items-center gap-0.5 px-2 py-1 overflow-x-auto ribbon-scroll"
              style={{ scrollbarWidth: 'auto', scrollbarColor: '#a19f9d #f3f2f1' }}>
              {/*  INICIO TAB  */}
              {activeTab === 'inicio' && (
                <>
                  {/* Group: Nuevo */}
                  <Group label="Nuevo">
                    <div className="relative">
                      <ToolbarButton icon={ICONS.newMail} label="Nuevo (N)" primary hasDropdown
                        onClick={() => openCompose('new')} />
                    </div>
                  </Group>
                  <Sep />

                  {/* Group: Eliminar */}
                  <Group label="Eliminar">
                    <ToolbarButton icon={ICONS.ignore} label="Ignorar"
                      onClick={() => moveToFolder('Trash', 'Conversación ignorada')} />
                    <div className="relative">
                      <ToolbarButton icon={ICONS.block} label="Bloquear" hasDropdown
                        onClick={() => { closeAllDropdowns(); setBlockOpen(!blockOpen); }} />
                      <Dropdown open={blockOpen} onClose={() => setBlockOpen(false)}>
                        <DropdownItem label="Bloquear remitente" icon={ICONS.block}
                          onClick={() => { moveToFolder('Junk', 'Remitente bloqueado'); setBlockOpen(false); }} />
                        <DropdownItem label="Mover a correo no deseado" icon={ICONS.move}
                          onClick={() => { moveToFolder('Junk', 'Movido a No deseado'); setBlockOpen(false); }} />
                      </Dropdown>
                    </div>
                    <ToolbarButton icon={ICONS.delete} label="Eliminar (Supr)" danger onClick={doDelete} />
                    <ToolbarButton icon={ICONS.archive} label="Archivar (E)"
                      onClick={() => moveToFolder('Archive', 'Archivado')} />
                  </Group>
                  <Sep />

                  {/* Group: Informar */}
                  <Group label="Informar">
                    <ToolbarButton icon={ICONS.report} label="Informar"
                      onClick={() => moveToFolder('Junk', 'Reportado como phishing')} />
                  </Group>
                  <Sep />

                  {/* Group: Responder */}
                  <Group label="Responder">
                    <div className="relative">
                      <ToolbarButton icon={ICONS.reply} label="Responder (R)" hasDropdown
                        onClick={() => { closeAllDropdowns(); setReplyOpen(!replyOpen); }} />
                      <Dropdown open={replyOpen} onClose={() => setReplyOpen(false)}>
                        <DropdownItem label="Responder" icon={ICONS.reply} onClick={doReply} />
                        <DropdownItem label="Responder a todos" icon={ICONS.replyAll} onClick={doReplyAll} />
                        <DropdownItem label="Reenviar" icon={ICONS.forward} onClick={doForward} />
                      </Dropdown>
                    </div>
                  </Group>
                  <Sep />

                  {/* Group: Mover */}
                  <Group label="Mover">
                    <div className="relative">
                      <ToolbarButton icon={ICONS.clean} label="Limpiar" hasDropdown
                        onClick={() => { closeAllDropdowns(); setCleanOpen(!cleanOpen); }} />
                      <Dropdown open={cleanOpen} onClose={() => setCleanOpen(false)}>
                        <DropdownItem label={`Vaciar "${getFolderDisplayName(currentFolder)}"`} icon={ICONS.clean} onClick={doCleanFolder} />
                      </Dropdown>
                    </div>
                    <div className="relative">
                      <ToolbarButton icon={ICONS.move} label="Mover" hasDropdown
                        onClick={() => { closeAllDropdowns(); setMoveOpen(!moveOpen); }} />
                      <Dropdown open={moveOpen} onClose={() => setMoveOpen(false)}>
                        {(folders || []).map((f: any) => (
                          <DropdownItem key={typeof f === 'string' ? f : f.name}
                            label={getFolderDisplayName(typeof f === 'string' ? f : f.name)} icon={ICONS.move}
                            onClick={() => { moveToFolder(typeof f === 'string' ? f : f.name); setMoveOpen(false); }} />
                        ))}
                      </Dropdown>
                    </div>
                    <div className="relative">
                      <ToolbarButton icon={ICONS.rules} label="Reglas" hasDropdown
                        onClick={() => { closeAllDropdowns(); setRulesOpen(!rulesOpen); }} />
                      <Dropdown open={rulesOpen} onClose={() => setRulesOpen(false)}>
                        <DropdownItem label="Crear regla..." icon={ICONS.rules}
                          onClick={() => { goToSettings('filters'); setRulesOpen(false); }} />
                        <DropdownItem label="Administrar reglas" icon={ICONS.settings}
                          onClick={() => { goToSettings('filters'); setRulesOpen(false); }} />
                      </Dropdown>
                    </div>
                  </Group>
                  <Sep />

                  {/* Group: Etiquetas */}
                  <Group label="Etiquetas">
                    <ToolbarButton icon={msg?.seen ? ICONS.unread : ICONS.read}
                      label={msg?.seen ? 'No leído' : 'Leído'} onClick={toggleRead} />
                    <div className="relative">
                      <ToolbarButton icon={ICONS.classify} label="Clasificar" hasDropdown
                        onClick={() => { closeAllDropdowns(); setClassifyOpen(!classifyOpen); }} />
                      <Dropdown open={classifyOpen} onClose={() => setClassifyOpen(false)}>
                        {[
                          { label: 'Categoría azul', color: '#0078d4' },
                          { label: 'Categoría verde', color: '#107c10' },
                          { label: 'Categoría roja', color: '#d13438' },
                          { label: 'Categoría amarilla', color: '#ffb900' },
                          { label: 'Categoría morada', color: '#8764b8' },
                        ].map(cat => (
                          <button key={cat.label}
                            onClick={() => doClassify(cat.label)}
                            className="w-full text-left px-3 py-1.5 text-[13px] flex items-center gap-2 hover:bg-[#f3f2f1] text-[#323130]">
                            <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: cat.color }} />
                            <span>{cat.label}</span>
                          </button>
                        ))}
                        <div className="border-t border-[#edebe9] my-1" />
                        <DropdownItem label="Borrar categorías" icon={ICONS.delete}
                          onClick={() => doClassify('')} />
                      </Dropdown>
                    </div>
                    <div className="relative">
                      <ToolbarButton icon={ICONS.flag} label="Marcar" hasDropdown active={msg?.flagged}
                        onClick={() => { closeAllDropdowns(); setFlagOpen(!flagOpen); }} />
                      <Dropdown open={flagOpen} onClose={() => setFlagOpen(false)}>
                        <DropdownItem label={msg?.flagged ? 'Quitar bandera' : 'Marcar con bandera'} icon={ICONS.flag}
                          onClick={() => { toggleFlag(); setFlagOpen(false); }} />
                        <DropdownItem label="Marcar como completado" icon={ICONS.classify}
                          onClick={() => { showToast('Marcado como completado'); try { const uid = Array.from(selectedUids)[0]; if(uid && currentFolder) { api.put('/mail/flag', { folder: currentFolder, uids: [uid], flag: '\\Flagged', action: 'remove' }).then(() => window.dispatchEvent(new CustomEvent('refresh-messages'))); } } catch {}; setFlagOpen(false); }} />
                      </Dropdown>
                    </div>
                    <ToolbarButton icon={ICONS.pin} label="Chincheta"
                      onClick={handlePin} />
                    <ToolbarButton icon={ICONS.snooze} label="Posponer"
                      onClick={handleSnoozeClick} />
                    <SnoozeModal
                      open={snoozeOpen}
                      onClose={() => setSnoozeOpen(false)}
                      folder={currentFolder}
                      uids={uids}
                      onSnoozed={() => { showToast('Correo pospuesto'); }}
                    />
                  </Group>
                  <Sep />

                  {/* Group: Imprimir */}
                  <Group label="Imprimir">
                    <ToolbarButton icon={ICONS.print} label="Imprimir (Ctrl+P)" onClick={doPrint} />
                  </Group>
                  <Sep />

                  {/* Group: Complementos */}
                  <Group label="Complementos">
                    <div className="relative">
                      <ToolbarButton icon={ICONS.apps} label="Más aplicaciones" hasDropdown
                        onClick={() => { closeAllDropdowns(); setAddinsOpen(!addinsOpen); }} />
                      <Dropdown open={addinsOpen} onClose={() => setAddinsOpen(false)}>
                        <DropdownItem label="Traductor" icon="&#x1F310;"
                          onClick={() => {
                            if (selectedMessage) {
                              const text = selectedMessage.text_body || '';
                              const url = 'https://translate.google.com/?sl=auto&tl=es&text=' + encodeURIComponent(text.slice(0, 2000));
                              window.open(url, '_blank', 'noopener,noreferrer');
                            } else {
                              showToast('Selecciona un mensaje para traducir');
                            }
                            setAddinsOpen(false);
                          }} />
                        <DropdownItem label="Corrector ortográfico" icon="&#x1F4DD;"
                          onClick={() => {
                            showToast('El corrector ortográfico del navegador está activo. Haz clic derecho en texto subrayado para ver sugerencias.');
                            setAddinsOpen(false);
                          }} />
                        <DropdownItem label="Plantillas de correo" icon="&#x1F4CB;"
                          onClick={() => {
                            openCompose('new', {
                              to: [],
                              subject: '',
                              text_body: 'Estimado/a,\n\nLe saludo cordialmente.\n\nAtentamente,',
                              html_body: '<p>Estimado/a,</p><p></p><p>Le saludo cordialmente.</p><p></p><p>Atentamente,</p>',
                            });
                            showToast('Plantilla cargada en nuevo correo');
                            setAddinsOpen(false);
                          }} />
                      </Dropdown>
                    </div>
                  </Group>
                  <Sep />

                  {/* Group: Buscar */}
                  <Group label="Buscar">
                    <ToolbarButton icon={ICONS.groups} label="Descubrir grupos"
                      onClick={() => showToast('Grupos: Usa listas de distribución para comunicarte con equipos. Contacta a gestiontecnologia@ejemplo.com para crear un grupo.')} />
                  </Group>
                  <Sep />

                  {/* Group: Deshacer */}
                  <Group label="Deshacer">
                    <ToolbarButton icon={ICONS.undo} label="Deshacer (Ctrl+Z)"
                      onClick={() => showToast('Deshacer: Ctrl+Z — Las acciones de mover y eliminar tienen opción de deshacer automática de 5 segundos')} />
                  </Group>
                </>
              )}

              {/*  VISTA TAB  */}
              {activeTab === 'vista' && (
                <>
                  {/* Group: Configuración */}
                  <Group label="Configuración">
                    <ToolbarButton icon={ICONS.settings} label="Configuración de vista"
                      onClick={() => { goToSettings('general'); }} />
                  </Group>
                  <Sep />

                  {/* Group: Mensajes */}
                  <Group label="Mensajes">
                    <div className="relative">
                      <ToolbarButton icon={ICONS.conversation} label="Conversaciones" hasDropdown
                        active={viewMode === 'conversations'}
                        onClick={() => { closeAllDropdowns(); setConvOpen(!convOpen); }} />
                      <Dropdown open={convOpen} onClose={() => setConvOpen(false)}>
                        <DropdownItem label="Mensajes individuales" icon={ICONS.unread}
                          active={viewMode === 'messages'}
                          onClick={() => { setViewMode('messages'); setConvOpen(false); }} />
                        <DropdownItem label="Conversaciones agrupadas" icon={ICONS.conversation}
                          active={viewMode === 'conversations'}
                          onClick={() => { setViewMode('conversations'); setConvOpen(false); }} />
                      </Dropdown>
                    </div>
                    <div className="relative">
                      <ToolbarButton icon={ICONS.preview} label="Vista previa" hasDropdown
                        onClick={() => { closeAllDropdowns(); setPreviewLinesOpen(!previewLinesOpen); }} />
                      <Dropdown open={previewLinesOpen} onClose={() => setPreviewLinesOpen(false)}>
                        {([
                          { label: '1 línea', value: 1 },
                          { label: '2 líneas', value: 2 },
                          { label: '3 líneas', value: 3 },
                        ] as const).map(opt => (
                          <DropdownItem
                            key={opt.label}
                            label={opt.label}
                            icon={ICONS.preview}
                            active={previewLines === opt.value}
                            onClick={() => applyPreviewLines(opt.value)}
                          />
                        ))}
                      </Dropdown>
                    </div>
                    <ToolbarButton icon={ICONS.zoom} label="Zoom"
                      onClick={() => showToast('Zoom actual: ' + Math.round(window.devicePixelRatio * 100) + '% — Usa Ctrl+Plus para ampliar, Ctrl+Menos para reducir, Ctrl+0 para restablecer')} />
                    <ToolbarButton icon={ICONS.sync} label="Sincronizar"
                      onClick={() => window.dispatchEvent(new CustomEvent('refresh-messages'))} />
                  </Group>
                  <Sep />

                  {/* Group: Diseño */}
                  <Group label="Diseño">
                    <div className="relative">
                      <ToolbarButton icon={ICONS.ribbon} label="Cinta de opciones" hasDropdown
                        onClick={() => { closeAllDropdowns(); setRibbonMenuOpen(!ribbonMenuOpen); }} />
                      <Dropdown open={ribbonMenuOpen} onClose={() => setRibbonMenuOpen(false)}>
                        <DropdownItem label="Cinta clásica" icon={ICONS.ribbon}
                          active={!collapsed}
                          onClick={() => { setCollapsed(false); setRibbonMenuOpen(false); }} />
                        <DropdownItem label="Cinta simplificada" icon={ICONS.density}
                          active={collapsed}
                          onClick={() => { setCollapsed(true); setRibbonMenuOpen(false); }} />
                      </Dropdown>
                    </div>
                    <div className="relative">
                      <ToolbarButton icon={ICONS.folderPanel} label="Panel de carpetas" hasDropdown
                        onClick={() => { closeAllDropdowns(); setFolderPanelOpen(!folderPanelOpen); }} />
                      <Dropdown open={folderPanelOpen} onClose={() => setFolderPanelOpen(false)}>
                        <DropdownItem label="Mostrar/Ocultar panel" icon={ICONS.folderPanel}
                          onClick={() => {
                            window.dispatchEvent(new CustomEvent('toggle-sidebar'));
                            setFolderPanelOpen(false);
                          }} />
                      </Dropdown>
                    </div>
                    <div className="relative">
                      <ToolbarButton icon={ICONS.readingPane} label="Panel de lectura" hasDropdown
                        active={!!readingPane}
                        onClick={() => { closeAllDropdowns(); setReadingPaneOpen(!readingPaneOpen); }} />
                      <Dropdown open={readingPaneOpen} onClose={() => setReadingPaneOpen(false)}>
                        {([
                          { label: 'Mostrar a la derecha', value: 'right' },
                          { label: 'Mostrar en la parte inferior', value: 'bottom' },
                          { label: 'Rellenar pantalla', value: 'fullscreen' },
                          { label: 'Solo elementos emergentes', value: 'popout' },
                        ] as const).map(opt => (
                          <DropdownItem key={opt.value} label={opt.label} icon={ICONS.readingPane}
                            active={readingPane === opt.value}
                            onClick={async () => {
                              setReadingPane(opt.value as any);
                              try { await api.put('/settings', { reading_pane: opt.value }); } catch {}
                              setReadingPaneOpen(false);
                            }} />
                        ))}
                      </Dropdown>
                    </div>
                    <div className="relative">
                      <ToolbarButton icon={ICONS.myDay} label="Mi día"
                        active={showMyDay}
                        onClick={() => setShowMyDay(!showMyDay)} />
                    </div>
                    <div className="relative">
                      <ToolbarButton icon={ICONS.density} label="Densidad" hasDropdown
                        onClick={() => { closeAllDropdowns(); setDensityOpen(!densityOpen); }} />
                      <Dropdown open={densityOpen} onClose={() => setDensityOpen(false)}>
                        {([
                          { label: 'Compacta', value: 'compact' },
                          { label: 'Media', value: 'medium' },
                          { label: 'Completa', value: 'full' },
                        ] as const).map(opt => (
                          <DropdownItem key={opt.value} label={opt.label} icon={ICONS.density}
                            active={density === opt.value}
                            onClick={() => { setDensity(opt.value); setDensityOpen(false); }} />
                        ))}
                      </Dropdown>
                    </div>
                  </Group>
                  <Sep />

                  {/* Group: Lector inmersivo */}
                  <Group label="Lector inmersivo">
                    <ToolbarButton icon={ICONS.immersive} label="Lector inmersivo"
                      onClick={() => {
                        if (!msg) { showToast('Selecciona un mensaje primero'); return; }
                        const body = msg.html_body || msg.text_body || '';
                        if (!body) { showToast('El mensaje no tiene contenido'); return; }
                        const safeBody = msg.html_body ? sanitizeHtml(msg.html_body) : '<pre style="white-space:pre-wrap">' + escapeHtml(msg.text_body || '') + '</pre>';
                        const w = window.open('', 'Lector', 'width=700,height=600');
                        if (w) {
                          const safeSubj = escapeHtml(msg.subject || 'Mensaje');
                          const safeFrm = escapeHtml(msg.from || '');
                          const safeDate = escapeHtml(msg.date ? new Date(msg.date).toLocaleString('es-EC') : '');
                          w.document.write(
                            '<!DOCTYPE html><html><head><title>' + safeSubj + '</title>' +
                            "<meta http-equiv='Content-Security-Policy' content='default-src \x27none\x27; img-src https: data:; style-src \x27unsafe-inline\x27; font-src https:;'>" +
                            '<style>body{font-family:Georgia,serif;max-width:650px;margin:40px auto;padding:20px;line-height:1.8;font-size:18px;color:#333}' +
                            'h1{font-size:22px;color:#0078d4;border-bottom:2px solid #edebe9;padding-bottom:12px}' +
                            '.meta{font-size:13px;color:#605e5c;margin:4px 0}.content{margin-top:20px}</style>' +
                            '</head><body><h1>' + safeSubj + '</h1>' +
                            '<p class="meta"><b>De:</b> ' + safeFrm + '</p>' +
                            '<p class="meta"><b>Fecha:</b> ' + safeDate + '</p>' +
                            '<div class="content">' + safeBody + '</div></body></html>'
                          );
                          w.document.close();
                          w.focus();
                        }
                      }} />
                  </Group>
                </>
              )}

              {/*  AYUDA TAB  */}
              {activeTab === 'ayuda' && (
                <>
                  {/* Group: Ayuda */}
                  <Group label="Ayuda">
                    <ToolbarButton icon={ICONS.help} label="Ayuda" onClick={showShortcuts} />
                    <ToolbarButton icon={ICONS.recommend} label="Recomendaciones"
                      onClick={() => showToast('Tip: Ctrl+N nuevo correo · Ctrl+R responder · Ctrl+Shift+R resp. todos · Ctrl+Enter enviar · E archivar · Supr eliminar')} />
                    <ToolbarButton icon={ICONS.feedback} label="Comentarios"
                      onClick={() => { showToast('Abriendo formulario de comentarios...'); setTimeout(() => openCompose('new', { to: [], subject: 'Comentario sobre Maquita Mail', text_body: '', html_body: '' }), 300); }} />
                  </Group>
                  <Sep />

                  {/* Group: Diagnósticos */}
                  <Group label="Diagnósticos">
                    <ToolbarButton icon={ICONS.diagnostic} label="Obtener diagnósticos"
                      onClick={showDiagnostics} />
                  </Group>
                  <Sep />

                  {/* Group: Móvil */}
                  <Group label="Móvil">
                    <ToolbarButton icon={ICONS.mobile} label="Outlook móvil"
                      onClick={() => showToast('Maquita Móvil: próximamente')} />
                  </Group>
                </>
              )}
            </div>
            {showScrollArrow && (
              <button
                onClick={scrollRibbonRight}
                className="absolute right-0 top-0 bottom-0 w-[28px] flex items-center justify-center bg-gradient-to-l from-white via-white/95 to-transparent cursor-pointer hover:from-[#f3f2f1] z-10 border-l border-[#edebe9]"
                title="Ver más herramientas"
                style={{ backdropFilter: 'blur(2px)' }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 5l7 7-7 7" />
                </svg>
              </button>
            )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
