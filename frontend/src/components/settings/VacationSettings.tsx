import { useState, useEffect } from 'react';
import { api } from '../../api/client';

interface VacationData {
  enabled: boolean;
  subject: string;
  body: string;
  start_date: string | null;
  end_date: string | null;
}

export function VacationSettings() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const data = await api.get<VacationData>('/sieve/vacation');
        setEnabled(data.enabled);
        setSubject(data.subject || '');
        setBody(data.body || '');
        setStartDate(data.start_date || '');
        setEndDate(data.end_date || '');
      } catch {
        setError('No se pudo cargar la configuración de auto-respuesta');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleSave = async () => {
    if (enabled && !subject.trim()) {
      setError('El asunto es obligatorio cuando las respuestas están activas');
      return;
    }
    setError('');
    setSuccess('');
    setSaving(true);
    try {
      await api.put('/sieve/vacation', {
        enabled,
        subject: subject.trim(),
        body: body.trim(),
        start_date: startDate || null,
        end_date: endDate || null,
      });
      setDirty(false);
      setSuccess('Configuración guardada correctamente');
      setTimeout(() => setSuccess(''), 3000);
    } catch {
      setError('Error al guardar. Intenta de nuevo.');
    } finally {
      setSaving(false);
    }
  };

  const markDirty = () => { setDirty(true); setError(''); setSuccess(''); };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-6 w-6 border-2 border-[#0078d4] border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-5 max-w-[600px]">
      <h3 className="text-[16px] font-semibold text-[#323130] dark:text-[#e0e0e0] flex items-center gap-2">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
        </svg>
        Respuestas automáticas
      </h3>

      {/* Toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          onClick={() => { setEnabled(!enabled); markDirty(); }}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            enabled ? 'bg-[#0078d4]' : 'bg-[#c8c6c4] dark:bg-[#555]'
          }`}
        >
          <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow ${
            enabled ? 'translate-x-6' : 'translate-x-1'
          }`} />
        </button>
        <span className="text-[14px] text-[#323130] dark:text-[#e0e0e0]">
          Enviar respuestas automáticas
        </span>
      </div>

      {enabled && (
        <>
          {/* Subject */}
          <div>
            <label className="block text-[13px] font-medium text-[#323130] dark:text-[#e0e0e0] mb-1">
              Asunto
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => { setSubject(e.target.value); markDirty(); }}
              placeholder="Fuera de oficina"
              className="w-full px-3 py-2 border border-[#edebe9] dark:border-[#444] rounded bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4] outline-none text-[14px]"
            />
          </div>

          {/* Body */}
          <div>
            <label className="block text-[13px] font-medium text-[#323130] dark:text-[#e0e0e0] mb-1">
              Mensaje
            </label>
            <textarea
              value={body}
              onChange={(e) => { setBody(e.target.value); markDirty(); }}
              placeholder="Estoy de vacaciones. Para urgencias contactar a..."
              className="w-full px-3 py-2 border border-[#edebe9] dark:border-[#444] rounded bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] focus:border-[#0078d4] outline-none text-[14px] min-h-[120px] resize-y"
            />
          </div>

          {/* Date range */}
          <div>
            <label className="block text-[13px] font-medium text-[#323130] dark:text-[#e0e0e0] mb-1">
              Periodo (opcional)
            </label>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <label className="block text-[12px] text-[#605e5c] dark:text-[#999] mb-0.5">Desde</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => { setStartDate(e.target.value); markDirty(); }}
                  className="w-full px-3 py-2 border border-[#edebe9] dark:border-[#444] rounded bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] focus:border-[#0078d4] outline-none text-[14px]"
                />
              </div>
              <div className="flex-1">
                <label className="block text-[12px] text-[#605e5c] dark:text-[#999] mb-0.5">Hasta</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => { setEndDate(e.target.value); markDirty(); }}
                  className="w-full px-3 py-2 border border-[#edebe9] dark:border-[#444] rounded bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] focus:border-[#0078d4] outline-none text-[14px]"
                />
              </div>
            </div>
          </div>
        </>
      )}

      {error && (
        <div className="text-[13px] text-[#a4262c] dark:text-[#f1707b] bg-[#fde7e9] dark:bg-[#442726] px-3 py-2 rounded">
          {error}
        </div>
      )}
      {success && (
        <div className="text-[13px] text-[#107c10] dark:text-[#6bb700] bg-[#dff6dd] dark:bg-[#1e3a1e] px-3 py-2 rounded">
          {success}
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={!dirty || saving}
        className="px-4 py-2 bg-[#0078d4] text-white rounded hover:bg-[#106ebe] disabled:opacity-50 disabled:cursor-not-allowed text-[14px] font-medium"
      >
        {saving ? 'Guardando...' : 'Guardar'}
      </button>

      <p className="text-[12px] text-[#605e5c] dark:text-[#999] mt-4">
        Las respuestas automáticas se envían máximo una vez cada 7 días a cada remitente.
        {startDate && endDate && ' Se activarán solo durante el periodo seleccionado.'}
      </p>
    </div>
  );
}
