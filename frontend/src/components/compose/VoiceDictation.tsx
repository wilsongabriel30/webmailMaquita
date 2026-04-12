import { useState, useRef, useCallback, useEffect } from 'react';

interface VoiceDictationProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

type DictationState = 'idle' | 'recording' | 'processing';

export function VoiceDictation({ onTranscript, disabled = false }: VoiceDictationProps) {
  const [state, setState] = useState<DictationState>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number>(0);
  const streamRef = useRef<MediaStream | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  const startRecording = useCallback(async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });
      streamRef.current = stream;

      // Prefer webm/opus, fallback to wav
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/mp4';

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        streamRef.current = null;

        if (chunksRef.current.length === 0) {
          setState('idle');
          return;
        }

        setState('processing');
        const blob = new Blob(chunksRef.current, { type: mimeType });
        await sendToWhisper(blob, mimeType);
      };

      recorder.start(250); // collect chunks every 250ms
      mediaRecorderRef.current = recorder;
      setState('recording');

      // Timer
      setElapsed(0);
      timerRef.current = window.setInterval(() => {
        setElapsed(prev => prev + 1);
      }, 1000);

    } catch (err: any) {
      if (err.name === 'NotAllowedError') {
        setError('Permiso de micrófono denegado');
      } else if (err.name === 'NotFoundError') {
        setError('No se encontró micrófono');
      } else {
        setError('Error al acceder al micrófono');
      }
      setState('idle');
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = 0;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const sendToWhisper = async (blob: Blob, mimeType: string) => {
    try {
      const formData = new FormData();
      const ext = mimeType.includes('webm') ? 'webm' : mimeType.includes('mp4') ? 'mp4' : 'wav';
      formData.append('file', blob, `recording.${ext}`);
      formData.append('language', 'es');

      const resp = await fetch('/api/whisper/transcribe', {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });

      if (!resp.ok) {
        const err = await resp.text();
        throw new Error(err || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      const text = data.text || data.transcription || '';

      if (text.trim()) {
        onTranscript(text.trim());
      } else {
        setError('No se detectó voz');
      }
    } catch (err: any) {
      setError(err.message || 'Error de transcripción');
    } finally {
      setState('idle');
    }
  };

  const handleClick = () => {
    if (disabled) return;
    if (state === 'recording') {
      stopRecording();
    } else if (state === 'idle') {
      startRecording();
    }
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <button
        onClick={handleClick}
        disabled={disabled || state === 'processing'}
        title={state === 'recording' ? 'Detener grabación' : state === 'processing' ? 'Procesando...' : 'Dictar por voz'}
        style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 32, height: 32, borderRadius: '50%',
          border: state === 'recording' ? '2px solid #d13438' : '1px solid #d2d0ce',
          background: state === 'recording' ? '#fde7e9' : state === 'processing' ? '#f3f2f1' : 'white',
          cursor: disabled || state === 'processing' ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          transition: 'all 0.2s',
        }}
      >
        {state === 'processing' ? (
          <div style={{
            width: 14, height: 14, border: '2px solid #0078d4',
            borderTopColor: 'transparent', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }} />
        ) : state === 'recording' ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="#d13438">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="22" />
          </svg>
        )}
      </button>

      {state === 'recording' && (
        <span style={{
          fontSize: 11, color: '#d13438', fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%', background: '#d13438',
            animation: 'pulse 1s ease-in-out infinite',
          }} />
          {formatTime(elapsed)}
        </span>
      )}

      {state === 'processing' && (
        <span style={{ fontSize: 11, color: '#605e5c' }}>Transcribiendo...</span>
      )}

      {error && (
        <span style={{ fontSize: 11, color: '#d13438', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {error}
        </span>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
      `}</style>
    </div>
  );
}
