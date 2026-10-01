// ── GameLoop ─────────────────────────────────────────────────────────────────
// Fixed-timestep accumulator at 60 Hz.
// dt is clamped to ≤ 50 ms to survive tab-switch spikes.
// Auto-pauses on visibilitychange.

type _Loop_UpdateFn = (dt: number) => void;
type _Loop_RenderFn = (ctx: CanvasRenderingContext2D, alpha: number) => void;

const FIXED_DT   = 1 / 60;      // seconds
const MAX_DT     = 0.05;         // seconds — clamp to prevent spiral of death

export class GameLoop {
  private _update: _Loop_UpdateFn;
  private _render: _Loop_RenderFn;
  private _ctx:    CanvasRenderingContext2D;

  private _running    = false;
  private _paused     = false;
  private _rafId      = 0;
  private _lastTime   = 0;
  private _accumulator = 0;

  constructor(
    ctx: CanvasRenderingContext2D,
    update: _Loop_UpdateFn,
    render: _Loop_RenderFn,
  ) {
    this._ctx    = ctx;
    this._update = update;
    this._render = render;
    document.addEventListener("visibilitychange", this._onVisibility);
  }

  start() {
    if (this._running) return;
    this._running     = true;
    this._paused      = false;
    this._lastTime    = performance.now();
    this._accumulator = 0;
    this._rafId = requestAnimationFrame(this._tick);
  }

  pause() {
    this._paused = true;
  }

  resume() {
    if (!this._running) return;
    this._paused     = false;
    this._lastTime   = performance.now();  // reset to avoid dt spike
    this._accumulator = 0;
  }

  stop() {
    this._running = false;
    cancelAnimationFrame(this._rafId);
  }

  get isPaused(): boolean { return this._paused; }

  private _onVisibility = () => {
    if (document.hidden) this._paused = true;
  };

  private _tick = (now: number) => {
    if (!this._running) return;
    this._rafId = requestAnimationFrame(this._tick);

    if (this._paused) {
      this._render(this._ctx, 1);
      this._lastTime = now;
      return;
    }

    let elapsed = (now - this._lastTime) / 1000;
    this._lastTime = now;
    if (elapsed > MAX_DT) elapsed = MAX_DT;

    this._accumulator += elapsed;

    while (this._accumulator >= FIXED_DT) {
      this._update(FIXED_DT);
      this._accumulator -= FIXED_DT;
    }

    // alpha for interpolation (pass to render if needed)
    const alpha = this._accumulator / FIXED_DT;
    this._render(this._ctx, alpha);
  };

  destroy() {
    this.stop();
    document.removeEventListener("visibilitychange", this._onVisibility);
  }
}
