// ── AudioManager ─────────────────────────────────────────────────────────────
// Tiny WebAudio synthesiser. Lazily unlocked on the first user gesture.
// Fails silently if WebAudio is unavailable.
// Mute toggle on key M (or call .toggleMute()).

type OscType = "sine" | "square" | "sawtooth" | "triangle";

export class AudioManager {
  private _ctx: AudioContext | null = null;
  private _muted = false;
  private _unlocked = false;
  private _masterGain: GainNode | null = null;

  constructor() {
    // Unlock on first gesture
    const unlock = () => {
      if (this._unlocked) return;
      this._ensureContext();
      if (this._ctx?.state === "suspended") {
        this._ctx.resume().catch(() => {/* ignore */});
      }
      this._unlocked = true;
    };
    window.addEventListener("pointerdown", unlock, { once: true });
    window.addEventListener("keydown",     unlock, { once: true });

    // M key mute toggle
    window.addEventListener("keydown", (e) => {
      if (e.code === "KeyM") this.toggleMute();
    });
  }

  private _ensureContext(): AudioContext | null {
    if (this._ctx) return this._ctx;
    try {
      this._ctx = new AudioContext();
      this._masterGain = this._ctx.createGain();
      this._masterGain.connect(this._ctx.destination);
      this._masterGain.gain.value = this._muted ? 0 : 1;
    } catch {
      this._ctx = null;
    }
    return this._ctx;
  }

  toggleMute() {
    this._muted = !this._muted;
    if (this._masterGain) {
      this._masterGain.gain.value = this._muted ? 0 : 1;
    }
  }

  get isMuted(): boolean { return this._muted; }

  /**
   * Play a frequency sweep.
   * @param type      Oscillator waveform
   * @param freqStart Start frequency in Hz
   * @param freqEnd   End frequency in Hz
   * @param durationMs Duration in milliseconds
   * @param volume    0–1
   */
  sweep(type: OscType, freqStart: number, freqEnd: number, durationMs: number, volume = 0.3) {
    if (this._muted) return;
    const ctx = this._ensureContext();
    if (!ctx || !this._masterGain) return;
    try {
      const t0  = ctx.currentTime;
      const dur = durationMs / 1000;

      const osc  = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freqStart, t0);
      osc.frequency.linearRampToValueAtTime(freqEnd, t0 + dur);

      gain.gain.setValueAtTime(volume, t0);
      gain.gain.linearRampToValueAtTime(0, t0 + dur);

      osc.connect(gain);
      gain.connect(this._masterGain);

      osc.start(t0);
      osc.stop(t0 + dur + 0.01);
    } catch {/* ignore */}
  }

  /** Flat beep at a fixed frequency. */
  beep(type: OscType, freq: number, durationMs: number, volume = 0.3) {
    this.sweep(type, freq, freq, durationMs, volume);
  }

  /** White-noise burst. */
  noise(durationMs: number, volume = 0.2) {
    if (this._muted) return;
    const ctx = this._ensureContext();
    if (!ctx || !this._masterGain) return;
    try {
      const sampleRate = ctx.sampleRate;
      const frameCount = Math.ceil(sampleRate * durationMs / 1000);
      const buffer = ctx.createBuffer(1, frameCount, sampleRate);
      const data   = buffer.getChannelData(0);
      for (let i = 0; i < frameCount; i++) data[i] = Math.random() * 2 - 1;

      const t0   = ctx.currentTime;
      const dur  = durationMs / 1000;
      const src  = ctx.createBufferSource();
      const gain = ctx.createGain();
      src.buffer = buffer;
      gain.gain.setValueAtTime(volume, t0);
      gain.gain.linearRampToValueAtTime(0, t0 + dur);
      src.connect(gain);
      gain.connect(this._masterGain!);
      src.start(t0);
    } catch {/* ignore */}
  }
}
