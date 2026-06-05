import { useState, useRef, useCallback, useEffect } from 'react';

interface VoiceDictationProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

type DictationState = 'idle' | 'recording' | 'processing';

// Dictado por voz con dos modos (configurables por el admin en :8443 -> Dictado):
//  - whisper: graba una frase, detecta el silencio, transcribe en TU servidor
//    Whisper y vuelve a escuchar. Privado. Pulsas una vez y hablas; al callar
//    se escribe solo. Pulsas de nuevo para terminar.
//  - browser: Web Speech del navegador (streaming en vivo, como el celular),
//    pero el audio pasa por Google y solo va en Chrome/Edge.
export function VoiceDictation({ onTranscript, disabled = false }: VoiceDictationProps) {
  const [state, setState] = useState<DictationState>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');
  const [mode, setMode] = useState<'whisper' | 'browser'>('whisper');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number>(0);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const vadRafRef = useRef<number>(0);
  const recognitionRef = useRef<any>(null);
  const activeRef = useRef<boolean>(false);

  // Modo configurado por el admin
  useEffect(() => {
    fetch('/api/mail/transcribe/health', { credentials: 'include' })
      .then(r => r.json())
      .then(d => { if (d && d.mode === 'browser') setMode('browser'); })
      .catch(() => {});
  }, []);

  useEffect(() => () => { hardStop(); }, []);

  const cleanupAudio = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = 0; }
    if (vadRafRef.current) { cancelAnimationFrame(vadRafRef.current); vadRafRef.current = 0; }
    if (audioCtxRef.current) { try { audioCtxRef.current.close(); } catch { /* ignore */ } audioCtxRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
  };

  const hardStop = () => {
    activeRef.current = false;
    try { if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') mediaRecorderRef.current.stop(); } catch { /* ignore */ }
    try { if (recognitionRef.current) recognitionRef.current.stop(); } catch { /* ignore */ }
    recognitionRef.current = null;
    cleanupAudio();
  };

  const handleMicError = (err: any) => {
    if (err?.name === 'NotAllowedError') setError('Permiso de micrófono denegado');
    else if (err?.name === 'NotFoundError') setError('No se encontró micrófono');
    else setError('Error al acceder al micrófono');
    activeRef.current = false;
    cleanupAudio();
    setState('idle');
  };

  const sendToWhisper = async (blob: Blob, mimeType: string) => {
    try {
      const formData = new FormData();
      const ext = mimeType.includes('webm') ? 'webm' : mimeType.includes('mp4') ? 'mp4' : 'wav';
      formData.append('audio', blob, `recording.${ext}`);
      formData.append('language', 'es');
      const resp = await fetch('/api/mail/transcribe', { method: 'POST', body: formData, credentials: 'include' });
      if (!resp.ok) { const e = await resp.text(); throw new Error(e || `HTTP ${resp.status}`); }
      const data = await resp.json();
      const text = data.full_text || data.text || data.transcription || data.texto || '';
      if (text.trim()) onTranscript(text.trim());
    } catch (err: any) {
      setError(err?.message || 'Error de transcripción');
    }
  };

  // ---- Modo WHISPER: detecta el silencio y transcribe por frase (continuo) ----
  const setupVAD = (stream: MediaStream, recorder: MediaRecorder) => {
    const AudioCtx = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!audioCtxRef.current) audioCtxRef.current = new AudioCtx();
    const ctx = audioCtxRef.current!;
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    let spoke = false;
    let silenceStart = 0;
    const SILENCE_MS = 1300;
    const THRESHOLD = 6;
    const check = () => {
      if (recorder.state === 'inactive') return;
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) { const v = (data[i] - 128) / 128; sum += v * v; }
      const rms = Math.sqrt(sum / data.length) * 100;
      const now = performance.now();
      if (rms > THRESHOLD) { spoke = true; silenceStart = 0; }
      else if (spoke) {
        if (silenceStart === 0) silenceStart = now;
        else if (now - silenceStart > SILENCE_MS) { try { recorder.stop(); } catch { /* ignore */ } return; }
      }
      vadRafRef.current = requestAnimationFrame(check);
    };
    vadRafRef.current = requestAnimationFrame(check);
  };

  const recordPhrase = useCallback(async () => {
    try {
      const stream = streamRef.current || await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      streamRef.current = stream;
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4';
      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = async () => {
        if (vadRafRef.current) { cancelAnimationFrame(vadRafRef.current); vadRafRef.current = 0; }
        if (chunksRef.current.length > 0) {
          setState('processing');
          await sendToWhisper(new Blob(chunksRef.current, { type: mimeType }), mimeType);
        }
        if (activeRef.current) { setState('recording'); recordPhrase(); }
        else { cleanupAudio(); setState('idle'); }
      };
      recorder.start(250);
      mediaRecorderRef.current = recorder;
      setupVAD(stream, recorder);
    } catch (err: any) {
      handleMicError(err);
    }
  }, [onTranscript]);

  const startWhisper = useCallback(async () => {
    setError('');
    activeRef.current = true;
    setState('recording');
    setElapsed(0);
    timerRef.current = window.setInterval(() => setElapsed(p => p + 1), 1000);
    await recordPhrase();
  }, [recordPhrase]);

  // ---- Modo BROWSER: Web Speech (streaming en vivo) ----
  const startBrowser = useCallback(() => {
    setError('');
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setError('Este navegador no soporta dictado en vivo (usa Chrome o Edge)'); return; }
    const rec = new SR();
    rec.lang = 'es-ES';
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (e: any) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          const t = e.results[i][0].transcript.trim();
          if (t) onTranscript(t + ' ');
        }
      }
    };
    rec.onerror = (e: any) => {
      if (e.error === 'not-allowed') { setError('Permiso de micrófono denegado'); activeRef.current = false; }
      else if (e.error !== 'no-speech') setError('Error de dictado');
    };
    rec.onend = () => { if (activeRef.current) { try { rec.start(); } catch { /* ignore */ } } else setState('idle'); };
    activeRef.current = true;
    try { rec.start(); } catch { /* ignore */ }
    recognitionRef.current = rec;
    setState('recording');
  }, [onTranscript]);

  const handleClick = () => {
    if (disabled || state === 'processing') return;
    if (state === 'recording') {
      activeRef.current = false;
      if (mode === 'browser') { try { recognitionRef.current?.stop(); } catch { /* ignore */ } setState('idle'); }
      else {
        if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = 0; }
        try { if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') mediaRecorderRef.current.stop(); } catch { /* ignore */ }
      }
    } else if (state === 'idle') {
      if (mode === 'browser') startBrowser(); else startWhisper();
    }
  };

  const formatTime = (s: number) => { const m = Math.floor(s / 60); const sec = s % 60; return `${m}:${sec.toString().padStart(2, '0')}`; };

  const title = state === 'recording'
    ? (mode === 'browser' ? 'Dictando en vivo — clic para terminar' : 'Escuchando — habla; al callar se escribe. Clic para terminar')
    : state === 'processing' ? 'Transcribiendo...'
    : (mode === 'browser' ? 'Dictar en vivo' : 'Dictar por voz (privado)');

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <button
        onClick={handleClick}
        disabled={disabled || state === 'processing'}
        title={title}
        style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 32, height: 32, borderRadius: '50%',
          border: state === 'recording' ? '2px solid #d13438' : '1px solid #d2d0ce',
          background: state === 'recording' ? '#fde7e9' : state === 'processing' ? '#f3f2f1' : 'white',
          cursor: disabled || state === 'processing' ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1, transition: 'all 0.2s',
        }}
      >
        {state === 'processing' ? (
          <div style={{ width: 14, height: 14, border: '2px solid #0078d4', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        ) : state === 'recording' ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="#d13438"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="22" />
          </svg>
        )}
      </button>

      {state === 'recording' && (
        <span style={{ fontSize: 11, color: '#d13438', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#d13438', animation: 'pulse 1s ease-in-out infinite' }} />
          {mode === 'browser' ? 'En vivo' : formatTime(elapsed)}
        </span>
      )}
      {state === 'processing' && (<span style={{ fontSize: 11, color: '#605e5c' }}>Transcribiendo...</span>)}
      {error && (<span style={{ fontSize: 11, color: '#d13438', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{error}</span>)}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
      `}</style>
    </div>
  );
}
