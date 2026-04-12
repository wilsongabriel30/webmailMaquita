/**
 * PasswordChange.tsx
 *
 * Settings section for changing the user's mail password.
 * Validates strength requirements (8+ chars, uppercase, lowercase, digit),
 * shows a visual strength indicator, and calls POST /api/auth/change-password.
 */

import { useState, useCallback, useMemo } from 'react';
import { api } from '../../api/client';

//  Types

interface PasswordForm {
  current: string;
  next: string;
  confirm: string;
}

interface Feedback {
  type: 'success' | 'error';
  message: string;
}

type StrengthLevel = 'weak' | 'fair' | 'good' | 'strong';

interface StrengthResult {
  level: StrengthLevel;
  score: number;   // 0-4
  label: string;
  color: string;
}

//  Password rules

const RULES = [
  { id: 'length', label: 'Al menos 8 caracteres', test: (p: string) => p.length >= 8 },
  { id: 'upper', label: 'One uppercase letter', test: (p: string) => /[A-Z]/.test(p) },
  { id: 'lower', label: 'One lowercase letter', test: (p: string) => /[a-z]/.test(p) },
  { id: 'digit', label: 'One number', test: (p: string) => /[0-9]/.test(p) },
] as const;

function evaluateStrength(password: string): StrengthResult {
  if (!password) return { level: 'weak', score: 0, label: '', color: '#a19f9d' };

  let score = 0;
  for (const rule of RULES) {
    if (rule.test(password)) score++;
  }

  // Bonus for length > 12
  const lengthBonus = password.length >= 12 ? 1 : 0;
  const total = Math.min(score + lengthBonus, 4);

  const map: Record<number, Omit<StrengthResult, 'score'>> = {
    0: { level: 'weak', label: 'Débil', color: '#d13438' },
    1: { level: 'weak', label: 'Débil', color: '#d13438' },
    2: { level: 'fair', label: 'Aceptable', color: '#ca5010' },
    3: { level: 'good', label: 'Good', color: '#498205' },
    4: { level: 'strong', label: 'Fuerte', color: '#0b6a0b' },
  };

  const info = map[total] ?? map[0];
  return { ...info, score: total };
}

function allRulesPass(password: string): boolean {
  return RULES.every((r) => r.test(password));
}

//  Component

export function PasswordChange() {
  const [form, setForm] = useState<PasswordForm>({
    current: '',
    next: '',
    confirm: '',
  });
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [loading, setLoading] = useState(false);
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);

  const strength = useMemo(() => evaluateStrength(form.next), [form.next]);

  const mismatch = form.confirm.length > 0 && form.next !== form.confirm;
  const canSubmit =
    form.current.length > 0 &&
    allRulesPass(form.next) &&
    form.next === form.confirm &&
    !loading;

  const updateField = useCallback(
    (field: keyof PasswordForm) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      setFeedback(null);
    },
    [],
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!canSubmit) return;

      setLoading(true);
      setFeedback(null);

      try {
        await api.post('/auth/change-password', {
          current_password: form.current,
          new_password: form.next,
        });
        setFeedback({ type: 'success', message: 'Contraseña cambiada correctamente.' });
        setForm({ current: '', next: '', confirm: '' });
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : 'No se pudo cambiar la contraseña. Inténtalo de nuevo.';
        setFeedback({ type: 'error', message });
      } finally {
        setLoading(false);
      }
    },
    [canSubmit, form],
  );

  return (
    <section
      className="rounded border border-[#edebe9] bg-white"
      style={{ fontFamily: "'Calibri', 'Segoe UI', sans-serif" }}
    >
      {/* Section header */}
      <div className="border-b border-[#edebe9] px-5 py-3">
        <h2 className="text-[15px] font-semibold text-[#323130]">
          Cambiar contraseña
        </h2>
        <p className="mt-0.5 text-[12px] text-[#605e5c]">
          Actualiza la contraseña de tu cuenta de correo.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="max-w-md px-5 py-4">
        {/* Current password */}
        <FieldGroup label="Contraseña actual" htmlFor="pw-current">
          <div className="relative">
            <input
              id="pw-current"
              type={showCurrent ? 'text' : 'password'}
              value={form.current}
              onChange={updateField('current')}
              autoComplete="current-password"
              className={inputClass}
            />
            <ToggleEye
              show={showCurrent}
              onToggle={() => setShowCurrent((v) => !v)}
            />
          </div>
        </FieldGroup>

        {/* New password */}
        <FieldGroup label="Nueva contraseña" htmlFor="pw-new">
          <div className="relative">
            <input
              id="pw-new"
              type={showNext ? 'text' : 'password'}
              value={form.next}
              onChange={updateField('next')}
              autoComplete="new-password"
              className={inputClass}
            />
            <ToggleEye
              show={showNext}
              onToggle={() => setShowNext((v) => !v)}
            />
          </div>

          {/* Strength bar */}
          {form.next.length > 0 && (
            <div className="mt-2">
              <div className="flex gap-1">
                {[0, 1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-[3px] flex-1 rounded-full transition-colors"
                    style={{
                      backgroundColor:
                        i < strength.score ? strength.color : '#edebe9',
                    }}
                  />
                ))}
              </div>
              <span
                className="mt-1 block text-[11px] font-semibold"
                style={{ color: strength.color }}
              >
                {strength.label}
              </span>
            </div>
          )}

          {/* Rules checklist */}
          {form.next.length > 0 && (
            <ul className="mt-2 space-y-0.5">
              {RULES.map((rule) => {
                const pass = rule.test(form.next);
                return (
                  <li
                    key={rule.id}
                    className="flex items-center gap-1.5 text-[11px]"
                    style={{ color: pass ? '#0b6a0b' : '#a19f9d' }}
                  >
                    <span>{pass ? '\u2713' : '\u2022'}</span>
                    {rule.label}
                  </li>
                );
              })}
            </ul>
          )}
        </FieldGroup>

        {/* Confirm password */}
        <FieldGroup label="Confirmar nueva contraseña" htmlFor="pw-confirm">
          <input
            id="pw-confirm"
            type="password"
            value={form.confirm}
            onChange={updateField('confirm')}
            autoComplete="new-password"
            className={[
              inputClass,
              mismatch ? 'border-[#d13438] focus:border-[#d13438] focus:ring-[#d13438]' : '',
            ].join(' ')}
          />
          {mismatch && (
            <p className="mt-1 text-[11px] text-[#d13438]">
              Las contraseñas no coinciden.
            </p>
          )}
        </FieldGroup>

        {/* Feedback */}
        {feedback && (
          <div
            className={[
              'mb-3 rounded px-3 py-2 text-[13px]',
              feedback.type === 'success'
                ? 'bg-[#dff6dd] text-[#0b6a0b]'
                : 'bg-[#fde7e9] text-[#d13438]',
            ].join(' ')}
          >
            {feedback.message}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={!canSubmit}
          className={[
            'rounded px-4 py-[6px] text-[13px] font-semibold text-white transition-colors',
            canSubmit
              ? 'bg-[#0078d4] hover:bg-[#106ebe] active:bg-[#005a9e]'
              : 'cursor-not-allowed bg-[#c8c6c4]',
          ].join(' ')}
        >
          {loading ? 'Guardando...' : 'Cambiar contraseña'}
        </button>
      </form>
    </section>
  );
}

//  Subcomponents & helpers

function FieldGroup({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-4">
      <label
        htmlFor={htmlFor}
        className="mb-1 block text-[12px] font-semibold text-[#605e5c]"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function ToggleEye({
  show,
  onToggle,
}: {
  show: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      tabIndex={-1}
      className="absolute right-2 top-1/2 -translate-y-1/2 text-[13px] text-[#605e5c] hover:text-[#323130]"
      aria-label={show ? 'Ocultar contraseña' : 'Mostrar contraseña'}
    >
      {show ? '\u25C9' : '\u25CE'}
    </button>
  );
}

const inputClass = [
  'block w-full rounded border border-[#edebe9] bg-white px-2 py-[5px] pr-8',
  'text-[13px] text-[#323130]',
  'outline-none focus:border-[#0078d4] focus:ring-1 focus:ring-[#0078d4]',
].join(' ');
