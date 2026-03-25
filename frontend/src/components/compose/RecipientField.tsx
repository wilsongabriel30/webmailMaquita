import { useState, useRef, useCallback, useEffect } from 'react';
import { api } from '../../api/client';

interface Chip {
  email: string;
  display: string;
}

interface Props {
  label: string;
  value: string;
  onChange: (v: string) => void;
  onToggleExtra?: () => void;
  showExtra?: boolean;
  autoFocus?: boolean;
  primary?: boolean;
}


export function RecipientField({ label, value, onChange, onToggleExtra, showExtra, autoFocus, primary }: Props) {
  const [chips, setChips] = useState<Chip[]>([]);
  const [input, setInput] = useState('');
  const [suggestions, setSuggestions] = useState<{ name: string; email: string; source: string }[]>([]);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // Sync from external value on mount
  useEffect(() => {
    if (value) {
      const emails = value.split(',').map(s => s.trim()).filter(Boolean);
      setChips(emails.map(e => ({ email: e, display: e })));
    }
  }, []);

  const addChip = useCallback((text: string) => {
    const email = text.trim();
    if (!email || chips.some(c => c.email === email)) return;
    const display = email;
    const newChips = [...chips, { email, display }];
    setChips(newChips);
    setInput('');
    setSuggestions([]);
    onChange(newChips.map(c => c.email).join(', '));
  }, [chips, onChange]);

  const removeChip = (idx: number) => {
    const newChips = chips.filter((_, i) => i !== idx);
    setChips(newChips);
    onChange(newChips.map(c => c.email).join(', '));
  };

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleInputChange = (text: string) => {
    setInput(text);
    if (text.length >= 2) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        try {
          const res = await api.get<{ contacts: { name: string; email: string; source: string }[] }>(
            `/contacts/search?q=${encodeURIComponent(text)}&limit=8`
          );
          const filtered = (res.contacts || []).filter(c => !chips.some(ch => ch.email === c.email));
          setSuggestions(filtered);
          setSelectedSuggestion(0);
        } catch {
          setSuggestions([]);
        }
      }, 150);
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
        addChip(suggestions[selectedSuggestion].email);
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
    // Delay to allow clicking suggestions
    setTimeout(() => {
      if (input.trim()) addChip(input);
      setSuggestions([]);
    }, 200);
  };

  return (
    <div className="flex items-start border-b border-[#edebe9] min-h-[40px] relative">
      {/* Label button */}
      <button className={`px-3 py-2 text-[13px] font-medium shrink-0 border-r border-[#edebe9] min-w-[48px] text-center ${
        primary ? 'text-[#0078d4] hover:bg-[#deecf9]' : 'text-[#605e5c] hover:bg-[#f3f2f1]'
      } transition-colors`}>
        {label}
      </button>

      {/* Chips + input area */}
      <div className="flex-1 flex flex-wrap items-center gap-[3px] px-2 py-[6px] min-h-[40px] cursor-text"
        onClick={() => inputRef.current?.focus()}>
        {chips.map((chip, i) => (
          <span key={i}
            className="inline-flex items-center gap-1 px-2 py-[2px] bg-[#f0f0f0] border border-[#d2d0ce] rounded-[2px] text-[13px] text-[#323130] hover:bg-[#e1dfdd] transition-colors group">
            <span>{chip.display}</span>
            <button onClick={(e) => { e.stopPropagation(); removeChip(i); }}
              className="w-3 h-3 rounded-full flex items-center justify-center text-[#a19f9d] hover:text-[#605e5c] hover:bg-[#c8c6c4] opacity-0 group-hover:opacity-100 transition-all">
              <svg className="w-2 h-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </span>
        ))}
        <div className="relative flex-1 min-w-[120px]">
          <input ref={inputRef} value={input} onChange={e => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown} onBlur={handleBlur} autoFocus={autoFocus}
            placeholder={chips.length === 0 ? 'Agregar destinatarios' : ''}
            className="w-full text-[13px] py-[2px] outline-none text-[#323130] placeholder-[#a19f9d] bg-transparent" />

          {/* Autocomplete dropdown */}
          {suggestions.length > 0 && (
            <div ref={suggestionsRef}
              className="absolute left-0 top-full mt-1 w-[280px] bg-white rounded shadow-lg border border-[#edebe9] z-50 py-1">
              {suggestions.map((s, i) => (
                <button key={s.email}
                  onMouseDown={(e) => { e.preventDefault(); addChip(s.email); }}
                  className={`w-full text-left px-3 py-[6px] flex items-center gap-2 transition-colors ${
                    i === selectedSuggestion ? 'bg-[#deecf9]' : 'hover:bg-[#f3f2f1]'
                  }`}>
                  <div className={`w-[28px] h-[28px] rounded-full flex items-center justify-center text-white text-[11px] font-semibold shrink-0 ${
                      s.source === 'personal' ? 'bg-[#0078d4]' : s.source === 'directory' ? 'bg-[#107c10]' : 'bg-[#8764b8]'
                    }`}>
                    {(s.name || s.email).charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[13px] text-[#323130] truncate">{s.name || s.email.split("@")[0]}</p>
                    <p className="text-[11px] text-[#a19f9d] truncate flex items-center gap-1">
                      {s.email}
                      {s.source === 'personal' && <span className="text-[9px] bg-[#e1dfdd] px-1 rounded">contacto</span>}
                      {s.source === 'directory' && <span className="text-[9px] bg-[#deecf9] px-1 rounded">directorio</span>}
                      {s.source === 'history' && <span className="text-[9px] bg-[#f3f2f1] px-1 rounded">reciente</span>}
                    </p>
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
