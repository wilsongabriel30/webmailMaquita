import { useState, useRef, useEffect, useCallback } from 'react';

const OPERATORS = [
  { op: 'from:', desc: 'Remitente', icon: '👤' },
  { op: 'to:', desc: 'Destinatario', icon: '📩' },
  { op: 'subject:', desc: 'Asunto', icon: '📋' },
  { op: 'has:attachment', desc: 'Con adjuntos', icon: '📎' },
  { op: 'before:', desc: 'Antes de fecha', icon: '📅' },
  { op: 'after:', desc: 'Después de fecha', icon: '📅' },
  { op: 'is:unread', desc: 'No leídos', icon: '✉' },
  { op: 'is:flagged', desc: 'Con bandera', icon: '🚩' },
  { op: 'larger:', desc: 'Mayor a tamaño', icon: '📦' },
  { op: 'smaller:', desc: 'Menor a tamaño', icon: '📦' },
];

interface SearchAdvancedProps {
  value: string;
  onChange: (query: string) => void;
  onSearch: (query: string) => void;
  placeholder?: string;
}

export function SearchAdvanced({ value, onChange, onSearch, placeholder = 'Buscar correos...' }: SearchAdvancedProps) {
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredOps, setFilteredOps] = useState(OPERATORS);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Parse current chips from the query
  const chips = parseChips(value);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    onChange(val);

    // Filter suggestions based on last word
    const lastWord = val.split(' ').pop()?.toLowerCase() || '';
    if (lastWord.length > 0) {
      setFilteredOps(OPERATORS.filter(o => o.op.toLowerCase().startsWith(lastWord) || o.desc.toLowerCase().includes(lastWord)));
      setShowSuggestions(true);
    } else {
      setFilteredOps(OPERATORS);
      setShowSuggestions(false);
    }
  }, [onChange]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      setShowSuggestions(false);
      onSearch(value);
    }
    if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  }, [value, onSearch]);

  const insertOperator = useCallback((op: string) => {
    const words = value.split(' ');
    words[words.length - 1] = op;
    const newVal = words.join(' ');
    onChange(newVal);
    setShowSuggestions(false);
    inputRef.current?.focus();
  }, [value, onChange]);

  const removeChip = useCallback((chipText: string) => {
    const newVal = value.replace(chipText, '').replace(/\s+/g, ' ').trim();
    onChange(newVal);
    onSearch(newVal);
  }, [value, onChange, onSearch]);

  return (
    <div ref={containerRef} className="relative flex-1">
      {/* Search input with chips */}
      <div className="flex items-center gap-1 bg-[#f3f2f1] dark:bg-[#2d2d2d] rounded px-2 py-1 border border-transparent focus-within:border-[#0078d4] focus-within:bg-white dark:focus-within:bg-[#1e1e1e] transition-colors">
        {/* Render parsed chips */}
        {chips.map((chip, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-[#deecf9] dark:bg-[#1a3a5c] text-[11px] text-[#0078d4] dark:text-[#6cb6ff] rounded font-medium whitespace-nowrap"
          >
            {chip.label}
            <button
              onClick={() => removeChip(chip.raw)}
              className="hover:text-[#d13438] ml-0.5 leading-none"
            >x</button>
          </span>
        ))}

        {/* Search icon */}
        <svg className="w-3.5 h-3.5 text-[#a19f9d] flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>

        <input
          ref={inputRef}
          type="text"
          value={getInputPart(value)}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => { if (value.split(' ').pop()?.includes(':')) setShowSuggestions(true); }}
          placeholder={chips.length ? '' : placeholder}
          className="flex-1 bg-transparent outline-none text-[13px] text-[#323130] dark:text-[#e0e0e0] placeholder-[#a19f9d] min-w-[100px]"
        />

        {value && (
          <button
            onClick={() => { onChange(''); onSearch(''); }}
            className="text-[#a19f9d] hover:text-[#323130] dark:hover:text-[#e0e0e0]"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && filteredOps.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-[#2d2d2d] border border-[#e1dfdd] dark:border-[#444] rounded shadow-lg z-50 py-1 max-h-[240px] overflow-y-auto">
          <div className="px-3 py-1 text-[10px] text-[#a19f9d] uppercase tracking-wider">Operadores de búsqueda</div>
          {filteredOps.map(({ op, desc, icon }) => (
            <button
              key={op}
              onClick={() => insertOperator(op)}
              className="w-full text-left px-3 py-1.5 text-[13px] flex items-center gap-2 hover:bg-[#f3f2f1] dark:hover:bg-[#383838]"
            >
              <span className="text-[14px] w-5 text-center">{icon}</span>
              <span className="font-mono text-[#0078d4] dark:text-[#6cb6ff]">{op}</span>
              <span className="text-[#605e5c] dark:text-[#999]">{desc}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Helpers

interface Chip {
  label: string;
  raw: string;
}

function parseChips(query: string): Chip[] {
  const chips: Chip[] = [];
  const opPattern = /(?:from|to|cc|subject|body|has|is|before|after|since|larger|smaller):[^\s]*/gi;
  let match;
  while ((match = opPattern.exec(query)) !== null) {
    const raw = match[0];
    const [op, val] = raw.split(':');
    if (val) {
      chips.push({ label: `${op}: ${val}`, raw });
    } else {
      chips.push({ label: raw, raw });
    }
  }
  return chips;
}

function getInputPart(query: string): string {
  // Return the part of the query that's not a recognized operator
  return query.replace(/(?:from|to|cc|subject|body|has|is|before|after|since|larger|smaller):[^\s]*/gi, '').trim();
}
