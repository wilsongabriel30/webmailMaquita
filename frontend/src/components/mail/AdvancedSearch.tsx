/**
 * AdvancedSearch.tsx
 *
 * Drop-down panel for building fine-grained IMAP search queries.
 * Renders below the main search bar when the user clicks the filter icon.
 *
 * Props:
 *   folders      list of available IMAP folder names
 *   onSearch     callback that receives the structured criteria
 *   onClose      close the panel
 *   initialCriteria  optional pre-filled criteria (e.g. from a previous search)
 */

import { useState, useCallback, useRef, useEffect } from 'react';

//  Types

export interface SearchCriteria {
  from?: string;
  to?: string;
  subject?: string;
  hasAttachments?: boolean;
  dateFrom?: string;   // ISO date yyyy-mm-dd
  dateTo?: string;     // ISO date yyyy-mm-dd
  unreadOnly?: boolean;
  folder: string;      // 'ALL' or a specific folder name
}

export interface AdvancedSearchProps {
  folders: string[];
  onSearch: (criteria: SearchCriteria) => void;
  onClose: () => void;
  initialCriteria?: Partial<SearchCriteria>;
}

//  Helpers

const EMPTY_CRITERIA: SearchCriteria = {
  from: '',
  to: '',
  subject: '',
  hasAttachments: false,
  dateFrom: '',
  dateTo: '',
  unreadOnly: false,
  folder: 'ALL',
};

/** Build an IMAP-compatible search query string from structured criteria. */
export function buildImapSearchQuery(c: SearchCriteria): string {
  const parts: string[] = [];

  if (c.from?.trim()) parts.push(`FROM "${c.from.trim()}"`);
  if (c.to?.trim()) parts.push(`TO "${c.to.trim()}"`);
  if (c.subject?.trim()) parts.push(`SUBJECT "${c.subject.trim()}"`);
  if (c.hasAttachments) parts.push('HAS attachment');
  if (c.unreadOnly) parts.push('UNSEEN');

  if (c.dateFrom) {
    const d = formatImapDate(c.dateFrom);
    if (d) parts.push(`SINCE ${d}`);
  }
  if (c.dateTo) {
    const d = formatImapDate(c.dateTo);
    if (d) parts.push(`BEFORE ${d}`);
  }

  return parts.join(' ');
}

function formatImapDate(iso: string): string | null {
  const date = new Date(iso);
  if (isNaN(date.getTime())) return null;
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  return `${date.getDate()}-${months[date.getMonth()]}-${date.getFullYear()}`;
}

//  Component

export function AdvancedSearch({
  folders,
  onSearch,
  onClose,
  initialCriteria,
}: AdvancedSearchProps) {
  const [criteria, setCriteria] = useState<SearchCriteria>({
    ...EMPTY_CRITERIA,
    ...initialCriteria,
  });

  const panelRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onClose]);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const update = useCallback(
    <K extends keyof SearchCriteria>(field: K, value: SearchCriteria[K]) => {
      setCriteria((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const handleReset = useCallback(() => {
    setCriteria({ ...EMPTY_CRITERIA });
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      onSearch(criteria);
    },
    [criteria, onSearch],
  );

  // Determine if any filter is active (to highlight the search button)
  const hasFilters =
    !!criteria.from?.trim() ||
    !!criteria.to?.trim() ||
    !!criteria.subject?.trim() ||
    !!criteria.hasAttachments ||
    !!criteria.unreadOnly ||
    !!criteria.dateFrom ||
    !!criteria.dateTo;

  return (
    <div
      ref={panelRef}
      className="absolute left-0 right-0 top-full z-50 mt-1 rounded border border-[#edebe9] bg-white shadow-lg"
      style={{ fontFamily: "'Calibri', 'Segoe UI', sans-serif" }}
    >
      <form onSubmit={handleSubmit}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#edebe9] px-4 py-2">
          <span className="text-[14px] font-semibold text-[#323130]">
            Búsqueda avanzada
          </span>
          <button
            type="button"
            onClick={onClose}
            className="text-[18px] leading-none text-[#605e5c] hover:text-[#323130]"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 px-4 py-3">
          {/* Folder */}
          <div className="col-span-2">
            <Label htmlFor="adv-folder">Search in</Label>
            <select
              id="adv-folder"
              value={criteria.folder}
              onChange={(e) => update('folder', e.target.value)}
              className={selectClass}
            >
              <option value="ALL">All folders</option>
              {folders.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>

          {/* From */}
          <div>
            <Label htmlFor="adv-from">From</Label>
            <input
              id="adv-from"
              type="text"
              value={criteria.from ?? ''}
              onChange={(e) => update('from', e.target.value)}
              placeholder="sender@example.com"
              className={inputClass}
            />
          </div>

          {/* To */}
          <div>
            <Label htmlFor="adv-to">To</Label>
            <input
              id="adv-to"
              type="text"
              value={criteria.to ?? ''}
              onChange={(e) => update('to', e.target.value)}
              placeholder="recipient@example.com"
              className={inputClass}
            />
          </div>

          {/* Subject */}
          <div className="col-span-2">
            <Label htmlFor="adv-subject">Subject</Label>
            <input
              id="adv-subject"
              type="text"
              value={criteria.subject ?? ''}
              onChange={(e) => update('subject', e.target.value)}
              placeholder="Keywords in subject..."
              className={inputClass}
            />
          </div>

          {/* Date from */}
          <div>
            <Label htmlFor="adv-datefrom">Date from</Label>
            <input
              id="adv-datefrom"
              type="date"
              value={criteria.dateFrom ?? ''}
              onChange={(e) => update('dateFrom', e.target.value)}
              className={inputClass}
            />
          </div>

          {/* Date to */}
          <div>
            <Label htmlFor="adv-dateto">Date to</Label>
            <input
              id="adv-dateto"
              type="date"
              value={criteria.dateTo ?? ''}
              onChange={(e) => update('dateTo', e.target.value)}
              className={inputClass}
            />
          </div>

          {/* Checkboxes row */}
          <div className="col-span-2 flex items-center gap-6 pt-1">
            <label className="flex items-center gap-2 text-[13px] text-[#323130]">
              <input
                type="checkbox"
                checked={criteria.hasAttachments ?? false}
                onChange={(e) => update('hasAttachments', e.target.checked)}
                className="accent-[#0078d4]"
              />
              Has attachments
            </label>

            <label className="flex items-center gap-2 text-[13px] text-[#323130]">
              <input
                type="checkbox"
                checked={criteria.unreadOnly ?? false}
                onChange={(e) => update('unreadOnly', e.target.checked)}
                className="accent-[#0078d4]"
              />
              Unread only
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-[#edebe9] px-4 py-2">
          <button
            type="button"
            onClick={handleReset}
            className="rounded px-3 py-[5px] text-[13px] text-[#323130] hover:bg-[#f3f2f1]"
          >
            Reset
          </button>
          <button
            type="submit"
            className={[
              'rounded px-4 py-[5px] text-[13px] font-semibold text-white',
              hasFilters ? 'bg-[#0078d4] hover:bg-[#106ebe]' : 'bg-[#0078d4] hover:bg-[#106ebe]',
            ].join(' ')}
          >
            Search
          </button>
        </div>
      </form>
    </div>
  );
}

//  Shared styles

const inputClass = [
  'mt-1 block w-full rounded border border-[#edebe9] bg-white px-2 py-[5px]',
  'text-[13px] text-[#323130] placeholder-[#a19f9d]',
  'outline-none focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4]',
].join(' ');

const selectClass = [
  'mt-1 block w-full rounded border border-[#edebe9] bg-white px-2 py-[5px]',
  'text-[13px] text-[#323130]',
  'outline-none focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4]',
].join(' ');

function Label({
  htmlFor,
  children,
}: {
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="block text-[12px] font-semibold text-[#605e5c]"
    >
      {children}
    </label>
  );
}
