import { useState, useRef, useCallback, useEffect } from 'react';
import { api } from '../../api/client';
import { getInitials, getAvatarColor } from '../contacts/types';

// ── Types ──

interface Chip {
  email: string;
  display: string;
  source?: string;
  jobTitle?: string;
  department?: string;
  phone?: string;
  photoUrl?: string;
}

interface ContactSuggestion {
  name: string;
  email: string;
  source: string;
  list_id?: number;
  member_count?: number;
  job_title?: string;
  department?: string;
  phone?: string;
  photo_url?: string;
  company?: string;
  location?: string;
}

interface Props {
  label: string;
  value: string;
  onChange: (v: string) => void;
  onToggleExtra?: () => void;
  showExtra?: boolean;
  autoFocus?: boolean;
  primary?: boolean;
  onOpenDirectory?: (target: 'to' | 'cc' | 'bcc') => void;
}

// ── Source badge config ──

const SOURCE_BADGES: Record<string, { label: string; bg: string; text: string }> = {
  mailbox:       { label: 'Usuario',      bg: 'bg-blue-100',   text: 'text-blue-700' },
  directory:     { label: 'Directorio',   bg: 'bg-green-100',  text: 'text-green-700' },
  org_directory: { label: 'Organizacion', bg: 'bg-green-100',  text: 'text-green-700' },
  room:          { label: 'Sala',         bg: 'bg-purple-100', text: 'text-purple-700' },
  list:          { label: 'Grupo',        bg: 'bg-orange-100', text: 'text-orange-700' },
  personal:      { label: 'Personal',     bg: 'bg-gray-100',   text: 'text-gray-600' },
  history:       { label: 'Reciente',     bg: 'bg-gray-50',    text: 'text-gray-500' },
};

// ── Chip color by source ──

function chipBorderColor(source?: string): string {
  switch (source) {
    case 'mailbox':       return 'border-blue-300 bg-blue-50';
    case 'directory':
    case 'org_directory': return 'border-green-300 bg-green-50';
    case 'room':          return 'border-purple-300 bg-purple-50';
    case 'list':          return 'border-orange-300 bg-orange-50';
    default:              return 'border-[#d2d0ce] bg-[#f0f0f0]';
  }
}

// ── Avatar component ──

function SuggestionAvatar({ suggestion, size = 32 }: { suggestion: ContactSuggestion; size?: number }) {
  if (suggestion.photo_url) {
    return (
      <img src={suggestion.photo_url} alt="" className="rounded-full object-cover shrink-0"
        style={{ width: size, height: size }} />
    );
  }
  if (suggestion.source === 'room') {
    return (
      <div className="rounded-full bg-purple-500 flex items-center justify-center shrink-0"
        style={{ width: size, height: size }}>
        <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 110 2h-3a1 1 0 01-1-1v-2a2 2 0 00-4 0v2a1 1 0 01-1 1H3a1 1 0 110-2V4zm3 1h2v2H7V5zm2 4H7v2h2V9zm2-4h2v2h-2V5zm2 4h-2v2h2V9z" clipRule="evenodd" />
        </svg>
      </div>
    );
  }
  const name = suggestion.name || suggestion.email;
  const color = getAvatarColor(suggestion.email || name);
  const initials = getInitials(name);
  return (
    <div className="rounded-full flex items-center justify-center text-white font-semibold shrink-0"
      style={{ width: size, height: size, backgroundColor: color, fontSize: size < 30 ? 11 : 13 }}>
      {initials}
    </div>
  );
}

// ── Source badge ──

function SourceBadge({ source, memberCount }: { source: string; memberCount?: number }) {
  const cfg = SOURCE_BADGES[source];
  if (!cfg) return null;
  const label = source === 'list' && memberCount ? `${cfg.label} (${memberCount})` : cfg.label;
  return (
    <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${cfg.bg} ${cfg.text} whitespace-nowrap`}>
      {label}
    </span>
  );
}

// ── Chip avatar (small) ──

function ChipAvatar({ chip }: { chip: Chip }) {
  if (chip.photoUrl) {
    return <img src={chip.photoUrl} alt="" className="w-5 h-5 rounded-full object-cover" />;
  }
  const name = chip.display || chip.email;
  const color = getAvatarColor(chip.email || name);
  const initials = getInitials(name);
  return (
    <span className="w-5 h-5 rounded-full flex items-center justify-center text-white text-[9px] font-semibold shrink-0"
      style={{ backgroundColor: color }}>
      {initials}
    </span>
  );
}

// ── Main component ──

export function RecipientField({ label, value, onChange, onToggleExtra, showExtra, autoFocus, primary, onOpenDirectory }: Props) {
  const [chips, setChips] = useState<Chip[]>([]);
  const [input, setInput] = useState('');
  const [suggestions, setSuggestions] = useState<ContactSuggestion[]>([]);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [expandingList, setExpandingList] = useState(false);
  const [hoveredChip, setHoveredChip] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const tooltipTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── External sync (same bug fix as before) ──
  // CONTEXTO DEL BUG (2026-04-10):
  //   Al dar "Responder", el campo "Para" quedaba vacio porque:
  //   1. RecipientField "Para" se MONTA con value="" (siempre esta visible)
  //   2. ComposePanel ejecuta su useEffect([editor]) DESPUES del mount
  //   3. ComposePanel llama setTo("email@...") -> value cambia
  //   4. Pero si el useEffect aqui solo tiene deps=[], nunca se re-ejecuta
  //
  // SOLUCION: Dos useEffects complementarios:
  //   1. [value] -> detecta cambios externos (reply pre-fill, draft edit)
  //   2. [] -> sync inicial si value ya tiene dato al montar (CC/CCO)
  //
  // NO CAMBIAR deps=[] a deps=[value] en el segundo — causaria loop infinito

  const prevValueRef = useRef(value);
  useEffect(() => {
    if (value !== prevValueRef.current) {
      prevValueRef.current = value;
      const emails = value ? value.split(",").map(s => s.trim()).filter(Boolean) : [];
      const currentEmails = chips.map(c => c.email).join(", ");
      if (value !== currentEmails) {
        setChips(emails.map(e => ({ email: e, display: e })));
      }
    }
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (value && chips.length === 0) {
      const emails = value.split(",").map(s => s.trim()).filter(Boolean);
      setChips(emails.map(e => ({ email: e, display: e })));
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const updateChips = useCallback((newChips: Chip[]) => {
    setChips(newChips);
    onChange(newChips.map(c => c.email).join(', '));
  }, [onChange]);

  const addChip = useCallback((text: string, suggestion?: ContactSuggestion) => {
    const email = text.trim();
    if (!email || chips.some(c => c.email === email)) return;
    const display = suggestion?.name || email;
    const newChips = [...chips, {
      email,
      display,
      source: suggestion?.source,
      jobTitle: suggestion?.job_title,
      department: suggestion?.department,
      phone: suggestion?.phone,
      photoUrl: suggestion?.photo_url,
    }];
    updateChips(newChips);
    setInput('');
    setSuggestions([]);
  }, [chips, updateChips]);

  const addListChip = useCallback(async (suggestion: ContactSuggestion) => {
    if (!suggestion.list_id) return;
    setExpandingList(true);
    setInput('');
    setSuggestions([]);
    try {
      const members = await api.get<{ name: string; email: string }[]>(
        `/contacts/lists/${suggestion.list_id}/expand`
      );
      const newChips = [...chips];
      for (const m of members) {
        if (!newChips.some(c => c.email === m.email)) {
          newChips.push({ email: m.email, display: m.name ? `${m.name} <${m.email}>` : m.email });
        }
      }
      updateChips(newChips);
    } catch {
      const fallbackEmail = suggestion.email;
      if (!chips.some(c => c.email === fallbackEmail)) {
        updateChips([...chips, { email: fallbackEmail, display: suggestion.name || fallbackEmail }]);
      }
    } finally {
      setExpandingList(false);
    }
  }, [chips, updateChips]);

  const selectSuggestion = useCallback((suggestion: ContactSuggestion) => {
    if (suggestion.source === 'list' && suggestion.list_id) {
      addListChip(suggestion);
    } else {
      addChip(suggestion.email, suggestion);
    }
  }, [addChip, addListChip]);

  const removeChip = (idx: number) => {
    const newChips = chips.filter((_, i) => i !== idx);
    updateChips(newChips);
  };

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleInputChange = (text: string) => {
    setInput(text);
    if (text.length >= 2) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        try {
          // Smart search: "@" prefix = directory only, "sala"/"room" = rooms only
          let query = text;
          let extra = '';
          if (text.startsWith('@')) {
            query = text.slice(1);
            extra = '&source=directory,mailbox';
          } else if (/^(sala|room)\b/i.test(text)) {
            query = text.replace(/^(sala|room)\s*/i, '').trim() || text;
            extra = '&source=room';
          }
          const res = await api.get<{ contacts: ContactSuggestion[] }>(
            `/contacts/search?q=${encodeURIComponent(query)}&limit=10${extra}`
          );
          const filtered = (res.contacts || []).filter(c =>
            c.source === 'list' ? true : !chips.some(ch => ch.email === c.email)
          );
          setSuggestions(filtered);
          setSelectedSuggestion(0);
        } catch {
          setSuggestions([]);
        }
      }, 200);
    } else {
      setSuggestions([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedSuggestion(prev => Math.min(prev + 1, suggestions.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedSuggestion(prev => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        selectSuggestion(suggestions[selectedSuggestion]);
        return;
      }
    }
    if ((e.key === 'Enter' || e.key === 'Tab' || e.key === ',' || e.key === ';') && input.trim()) {
      e.preventDefault();
      addChip(input);
    }
    if (e.key === 'Backspace' && !input && chips.length > 0) {
      removeChip(chips.length - 1);
    }
    if (e.key === 'Escape') {
      setSuggestions([]);
    }
  };

  const handleBlur = () => {
    setTimeout(() => {
      if (input.trim()) addChip(input);
      setSuggestions([]);
    }, 200);
  };

  // Scroll selected suggestion into view
  useEffect(() => {
    if (suggestionsRef.current && suggestions.length > 0) {
      const el = suggestionsRef.current.children[selectedSuggestion] as HTMLElement;
      el?.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedSuggestion, suggestions.length]);

  return (
    <div className="flex items-start border-b border-[#edebe9] min-h-[40px] relative">
      {/* Label button */}
      <button className={`px-3 py-2 text-[13px] font-medium shrink-0 border-r border-[#edebe9] min-w-[48px] text-center ${
        primary ? 'text-[#0078d4] hover:bg-[#deecf9]' : 'text-[#605e5c] hover:bg-[#f3f2f1]'
      } transition-colors`}>
        {label}
      </button>

      {/* Directory button */}
      {onOpenDirectory && (
        <button
          onClick={() => onOpenDirectory(label.toLowerCase() === 'para' ? 'to' : label.toLowerCase() === 'cc' ? 'cc' : 'bcc')}
          className="px-2 py-2 text-[#605e5c] hover:text-[#0078d4] hover:bg-[#deecf9] transition-colors shrink-0 border-r border-[#edebe9]"
          title="Abrir directorio"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
        </button>
      )}

      {/* Chips + input area */}
      <div className="flex-1 flex flex-wrap items-center gap-[3px] px-2 py-[6px] min-h-[40px] cursor-text"
        onClick={() => inputRef.current?.focus()}>
        {chips.map((chip, i) => (
          <div key={i} className="relative"
            onMouseEnter={() => {
              if (tooltipTimerRef.current) clearTimeout(tooltipTimerRef.current);
              tooltipTimerRef.current = setTimeout(() => setHoveredChip(i), 400);
            }}
            onMouseLeave={() => {
              if (tooltipTimerRef.current) clearTimeout(tooltipTimerRef.current);
              setHoveredChip(null);
            }}>
            <span className={`inline-flex items-center gap-1 px-1.5 py-[2px] border rounded-[3px] text-[13px] text-[#323130] hover:shadow-sm transition-all group ${chipBorderColor(chip.source)}`}>
              <ChipAvatar chip={chip} />
              <span className="max-w-[180px] truncate">{chip.display}</span>
              <button onClick={(e) => { e.stopPropagation(); removeChip(i); }}
                className="w-4 h-4 rounded-full flex items-center justify-center text-[#a19f9d] hover:text-[#605e5c] hover:bg-[#c8c6c4] opacity-0 group-hover:opacity-100 transition-all ml-0.5">
                <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
            {/* Tooltip */}
            {hoveredChip === i && (chip.jobTitle || chip.department || chip.phone) && (
              <div className="absolute left-0 top-full mt-1 z-[60] bg-[#323130] text-white rounded-md px-3 py-2 text-[11px] leading-[16px] shadow-xl whitespace-nowrap pointer-events-none">
                <div className="font-semibold text-[12px]">{chip.display}</div>
                <div className="text-gray-300">{chip.email}</div>
                {chip.jobTitle && <div className="mt-1">{chip.jobTitle}{chip.department ? ` - ${chip.department}` : ''}</div>}
                {chip.phone && <div className="mt-0.5">{chip.phone}</div>}
              </div>
            )}
          </div>
        ))}
        <div className="relative flex-1 min-w-[120px]">
          <input ref={inputRef} value={input} onChange={e => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown} onBlur={handleBlur} autoFocus={autoFocus}
            placeholder={chips.length === 0 ? 'Agregar destinatarios' : ''}
            disabled={expandingList}
            className="w-full text-[13px] py-[2px] outline-none text-[#323130] placeholder-[#a19f9d] bg-transparent" />

          {expandingList && (
            <span className="absolute right-0 top-1/2 -translate-y-1/2 text-[11px] text-[#0078d4] flex items-center gap-1">
              <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Expandiendo lista...
            </span>
          )}

          {/* Autocomplete dropdown — enterprise */}
          {suggestions.length > 0 && (
            <div ref={suggestionsRef}
              className="absolute left-0 top-full mt-1 w-[380px] bg-white rounded-lg shadow-xl border border-[#e1dfdd] z-50 py-1 max-h-[360px] overflow-y-auto">
              {suggestions.map((s, i) => (
                <button key={s.source === 'list' ? `list-${s.list_id}` : s.email}
                  onMouseDown={(e) => { e.preventDefault(); selectSuggestion(s); }}
                  className={`w-full text-left px-3 py-2.5 flex items-center gap-3 transition-colors ${
                    i === selectedSuggestion ? 'bg-[#deecf9]' : 'hover:bg-[#f3f2f1]'
                  }`}>
                  <SuggestionAvatar suggestion={s} size={36} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-semibold text-[#323130] truncate">
                        {s.source === 'list' ? `Lista: ${s.name}` : (s.name || s.email.split("@")[0])}
                      </span>
                      <SourceBadge source={s.source} memberCount={s.member_count} />
                    </div>
                    <div className="text-[11px] text-[#605e5c] truncate">{s.email}</div>
                    {(s.job_title || s.department) && (
                      <div className="text-[10px] text-[#a19f9d] truncate mt-0.5">
                        {[s.job_title, s.department].filter(Boolean).join(' - ')}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* CC/BCC toggle */}
      {onToggleExtra && !showExtra && (
        <button onClick={onToggleExtra}
          className="px-3 py-2 text-[12px] text-[#0078d4] hover:bg-[#deecf9] shrink-0 transition-colors font-medium">
          CC
        </button>
      )}
    </div>
  );
}
