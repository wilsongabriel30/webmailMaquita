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
  const [mode, setMode] = useState<'whisper' | 'browser' | 'whisperlive'>('whisper');
  // 2026-09-16: la persona elige entre «En vivo» (Web Speech del navegador: el texto aparece
  // mientras habla, como en el celular) y «Privado» (Whisper en el servidor, frase a frase).
  // Se recuerda en el navegador. Si el servidor no responde, se pasa solo a «En vivo».
  const soportaVivo = typeof window !== 'undefined' && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  const [preferencia, setPreferencia] = useState<'vivo' | 'privado'>(() => {
    try { return (localStorage.getItem('maquita_dictado_modo') as 'vivo' | 'privado') || (soportaVivo ? 'vivo' : 'privado'); } catch { return 'privado'; }
  });
  const [provisional, setProvisional] = useState('');
  const cambiarPreferencia = (v: 'vivo' | 'privado') => { setPreferencia(v); try { localStorage.setItem('maquita_dictado_modo', v); } catch { /* sin almacenamiento */ } };

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number>(0);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const vadRafRef = useRef<number>(0);
  const recognitionRef = useRef<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const wlCtxRef = useRef<AudioContext | null>(null);
  const wlProcRef = useRef<any>(null);
  const wlSeenRef = useRef<string>('');
  const activeRef = useRef<boolean>(false);

  // Modo configurado por el admin
  useEffect(() => {
    fetch('/api/mail/transcribe/health', { credentials: 'include' })
      .then(r => r.json())
      .then(d => { if (d && (d.mode === 'browser' || d.mode === 'whisperlive')) setMode(d.mode); })
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
    try { if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) { wsRef.current.send('END_OF_AUDIO'); wsRef.current.close(); } } catch { /* ignore */ }
    wsRef.current = null;
    try { if (wlProcRef.current) wlProcRef.current.disconnect(); } catch { /* ignore */ }
    try { if (wlCtxRef.current) wlCtxRef.current.close(); } catch { /* ignore */ }
    wlProcRef.current = null; wlCtxRef.current = null;
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
      const control = new AbortController();
      const limite = window.setTimeout(() => control.abort(), 25000);   // antes esperaba 2 minutos con «Transcribiendo...»
      let resp: Response;
      try { resp = await fetch('/api/mail/transcribe', { method: 'POST', body: formData, credentials: 'include', signal: control.signal }); }
      finally { window.clearTimeout(limite); }
      if (!resp.ok) { const e = await resp.text(); throw new Error(e || `HTTP ${resp.status}`); }
      const data = await resp.json();
      const text = data.full_text || data.text || data.transcription || data.texto || '';
      if (text.trim()) onTranscript(text.trim());
    } catch (err: any) {
      const lento = err?.name === 'AbortError';
      if (soportaVivo) {
        // Sin esperar: se pasa al dictado en vivo del navegador y se sigue dictando.
        activeRef.current = false;
        try { if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') mediaRecorderRef.current.stop(); } catch { /* ignore */ }
        cleanupAudio();
        setError(lento ? 'El servidor de dictado tardó demasiado: seguimos en vivo' : 'Servidor de dictado no disponible: seguimos en vivo');
        cambiarPreferencia('vivo');
        setState('idle');
        setTimeout(() => startBrowser(), 300);
        return;
      }
      setError(lento ? 'El servidor de dictado no respondió. Vuelve a intentarlo.' : (err?.message || 'Error de transcripción'));
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
    const SILENCE_MS = 900;   // pausa que cierra la frase (antes 1300 ms)
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
    rec.lang = 'es-EC';
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.onresult = (e: any) => {
      let parcial = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          const t = e.results[i][0].transcript.trim();
          if (t) onTranscript(t + ' ');
        } else {
          parcial += e.results[i][0].transcript;
        }
      }
      setProvisional(parcial.trim());
    };
    rec.onerror = (e: any) => {
      if (e.error === 'not-allowed') { setError('Permiso de micrófono denegado'); activeRef.current = false; }
      else if (e.error !== 'no-speech') setError('Error de dictado');
    };
    rec.onend = () => { setProvisional(''); if (activeRef.current) { try { rec.start(); } catch { /* ignore */ } } else setState('idle'); };
    activeRef.current = true;
    try { rec.start(); } catch { /* ignore */ }
    recognitionRef.current = rec;
    setState('recording');
  }, [onTranscript]);

  // ---- Modo WHISPERLIVE: streaming en vivo y PRIVADO (WebSocket a tu GPU) ----
  const startWLAudio = (stream: MediaStream, ws: WebSocket) => {
    const AudioCtx = (window as any).AudioContext || (window as any).webkitAudioContext;
    const ctx = new AudioCtx({ sampleRate: 16000 });
    wlCtxRef.current = ctx;
    const source = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    proc.onaudioprocess = (ev: any) => {
      if (ws.readyState !== WebSocket.OPEN) return;
      const input = ev.inputBuffer.getChannelData(0); // Float32 a 16 kHz
      ws.send(new Float32Array(input).buffer);        // PCM float32 mono
    };
    source.connect(proc);
    proc.connect(ctx.destination);
    wlProcRef.current = proc;
  };

  const startWhisperLive = useCallback(async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      streamRef.current = stream;
      const uid = (window.crypto && (window.crypto as any).randomUUID) ? (window.crypto as any).randomUUID() : String(Date.now()) + Math.random();
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${location.host}/whisperlive/`);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;
      wlSeenRef.current = '';
      ws.onopen = () => {
        ws.send(JSON.stringify({ uid, language: 'es', task: 'transcribe', model: 'base', use_vad: true }));
      };
      ws.onmessage = (e) => {
        let m: any;
        try { m = JSON.parse(typeof e.data === 'string' ? e.data : ''); } catch { return; }
        if (!m) return;
        if (m.uid && m.uid !== uid) return;
        if (m.message === 'SERVER_READY') { startWLAudio(stream, ws); return; }
        if (m.status === 'WAIT') { setError('Servidor de dictado ocupado, intenta en un momento'); return; }
        if (m.segments && Array.isArray(m.segments)) {
          const completed = m.segments.filter((sg: any) => sg.completed).map((sg: any) => sg.text).join(' ').replace(/\s+/g, ' ').trim();
          if (completed && completed !== wlSeenRef.current) {
            const nuevo = completed.startsWith(wlSeenRef.current) ? completed.slice(wlSeenRef.current.length) : completed;
            if (nuevo.trim()) onTranscript(nuevo.trim() + ' ');
            wlSeenRef.current = completed;
          }
        }
      };
      ws.onerror = () => { setError('No se pudo conectar al dictado en vivo'); activeRef.current = false; setState('idle'); };
      ws.onclose = () => { if (!activeRef.current) setState('idle'); };
      activeRef.current = true;
      setState('recording');
      setElapsed(0);
      timerRef.current = window.setInterval(() => setElapsed(p => p + 1), 1000);
    } catch (err: any) {
      handleMicError(err);
    }
  }, [onTranscript]);

  const handleClick = () => {
    if (disabled || state === 'processing') return;
    if (state === 'recording') {
      activeRef.current = false;
      if (mode === 'whisperlive') { hardStop(); setState('idle'); }
      else if (mode === 'browser' || recognitionRef.current) { try { recognitionRef.current?.stop(); } catch { /* ignore */ } setProvisional(''); setState('idle'); }
      else {
        if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = 0; }
        try { if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') mediaRecorderRef.current.stop(); } catch { /* ignore */ }
      }
    } else if (state === 'idle') {
      setError('');
      if (mode === 'whisperlive') startWhisperLive();
      else if (mode === 'browser' || (preferencia === 'vivo' && soportaVivo)) startBrowser();
      else startWhisper();
    }
  };
  const enVivo = mode === 'browser' || mode === 'whisperlive' || (preferencia === 'vivo' && soportaVivo);

  const formatTime = (s: number) => { const m = Math.floor(s / 60); const sec = s % 60; return `${m}:${sec.toString().padStart(2, '0')}`; };

  const title = state === 'recording'
    ? (enVivo ? 'Dictando en vivo — clic para terminar' : 'Escuchando — habla; al callar se escribe. Clic para terminar')
    : state === 'processing' ? 'Transcribiendo...'
    : (mode === 'whisperlive' ? 'Dictar en vivo (privado)' : enVivo ? 'Dictar en vivo' : 'Dictar por voz (privado)');

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

      {state === 'idle' && mode !== 'whisperlive' && soportaVivo && (
        <span style={{ display: 'inline-flex', border: '1px solid #d2d0ce', borderRadius: 4, overflow: 'hidden', fontSize: 10 }} title="En vivo: el texto aparece mientras hablas (reconocimiento del navegador). Privado: se transcribe en el servidor de Maquita frase a frase.">
          <button type="button" onClick={() => cambiarPreferencia('vivo')} style={{ padding: '2px 6px', border: 'none', cursor: 'pointer', background: preferencia === 'vivo' ? '#0078d4' : 'white', color: preferencia === 'vivo' ? 'white' : '#605e5c' }}>En vivo</button>
          <button type="button" onClick={() => cambiarPreferencia('privado')} style={{ padding: '2px 6px', border: 'none', cursor: 'pointer', background: preferencia === 'privado' ? '#0078d4' : 'white', color: preferencia === 'privado' ? 'white' : '#605e5c' }}>Privado</button>
        </span>
      )}
      {state === 'recording' && (
        <span style={{ fontSize: 11, color: '#d13438', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#d13438', animation: 'pulse 1s ease-in-out infinite' }} />
          {enVivo ? 'En vivo' : `Escuchando ${formatTime(elapsed)}`}
        </span>
      )}
      {state === 'recording' && provisional && (
        <span style={{ fontSize: 12, color: '#605e5c', fontStyle: 'italic', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{provisional}…</span>
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
