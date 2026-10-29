// Sonido corto al completar una tarea (como en To Do; se apaga en la ⚙ de Tareas). Se genera en el navegador: no
// descarga ningún archivo.
export function sonarCompletada(): void {
  try {
    const Contexto = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Contexto) return;
    const ctx = new Contexto();
    const t = ctx.currentTime;
    [880, 1318.5].forEach((frecuencia, i) => {
      const osc = ctx.createOscillator();
      const vol = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = frecuencia;
      vol.gain.setValueAtTime(0.0001, t + i * 0.09);
      vol.gain.exponentialRampToValueAtTime(0.18, t + i * 0.09 + 0.02);
      vol.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.09 + 0.25);
      osc.connect(vol).connect(ctx.destination);
      osc.start(t + i * 0.09);
      osc.stop(t + i * 0.09 + 0.3);
    });
    window.setTimeout(() => { void ctx.close(); }, 800);
  } catch { /* sin audio: se sigue sin sonido */ }
}
