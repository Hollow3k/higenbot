// ── FX: Particles, Shake, FloatingText, Tween, easing ───────────────────────

// ── Easing ───────────────────────────────────────────────────────────────────

export const Ease = {
  linear:      (t: number) => t,
  outQuad:     (t: number) => 1 - (1 - t) * (1 - t),
  outCubic:    (t: number) => 1 - Math.pow(1 - t, 3),
  outBack:     (t: number) => { const c = 1.70158; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
  inQuad:      (t: number) => t * t,
  inOutQuad:   (t: number) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2,
  outBounce:   (t: number) => {
    const n = 7.5625, d = 2.75;
    if (t < 1/d)      return n * t * t;
    if (t < 2/d)      return n * (t -= 1.5/d)   * t + 0.75;
    if (t < 2.5/d)    return n * (t -= 2.25/d)  * t + 0.9375;
    return n * (t -= 2.625/d) * t + 0.984375;
  },
  outElastic:  (t: number) => {
    if (t === 0 || t === 1) return t;
    return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * (2 * Math.PI) / 3) + 1;
  },
};

// ── Tween ────────────────────────────────────────────────────────────────────

export class Tween {
  private _from: number;
  private _to:   number;
  private _dur:  number;
  private _ease: (t: number) => number;
  private _elapsed = 0;
  private _done    = false;
  private _onDone?: () => void;

  constructor(
    from: number,
    to: number,
    durationSeconds: number,
    ease: (t: number) => number = Ease.outQuad,
    onDone?: () => void,
  ) {
    this._from  = from;
    this._to    = to;
    this._dur   = durationSeconds;
    this._ease  = ease;
    this._onDone = onDone;
  }

  update(dt: number) {
    if (this._done) return;
    this._elapsed += dt;
    if (this._elapsed >= this._dur) {
      this._elapsed = this._dur;
      this._done    = true;
      this._onDone?.();
    }
  }

  get value(): number {
    const t = this._dur > 0 ? this._elapsed / this._dur : 1;
    return this._from + (this._to - this._from) * this._ease(Math.min(t, 1));
  }

  get done(): boolean { return this._done; }
}

// ── Particle ────────────────────────────────────────────────────────────────

interface Particle {
  x: number; y: number;
  vx: number; vy: number;
  life: number;  // 0..1 (1 = just born, 0 = dead)
  decay: number; // life units per second
  r: number;
  color: string;
}

export class Particles {
  private _pool: Particle[] = [];

  /** Burst `count` particles from (x,y). */
  burst(x: number, y: number, count: number, color: string, options?: {
    speed?: number;     // px/s, default 120
    radius?: number;    // particle dot radius, default 3
    lifetime?: number;  // seconds, default 0.4
    spread?: number;    // radians full spread, default 2π
    angle?: number;     // center angle, default random
  }) {
    const speed    = options?.speed    ?? 120;
    const radius   = options?.radius   ?? 3;
    const lifetime = options?.lifetime ?? 0.4;
    const spread   = options?.spread   ?? Math.PI * 2;
    const baseAngle = options?.angle   ?? Math.random() * Math.PI * 2;

    for (let i = 0; i < count; i++) {
      const angle = baseAngle + (i / count - 0.5) * spread;
      const spd   = speed * (0.6 + Math.random() * 0.8);
      this._pool.push({
        x, y,
        vx: Math.cos(angle) * spd,
        vy: Math.sin(angle) * spd,
        life: 1,
        decay: 1 / lifetime,
        r: radius * (0.7 + Math.random() * 0.6),
        color,
      });
    }
  }

  update(dt: number) {
    for (let i = this._pool.length - 1; i >= 0; i--) {
      const p = this._pool[i];
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vy += 200 * dt; // slight gravity
      p.life -= p.decay * dt;
      if (p.life <= 0) this._pool.splice(i, 1);
    }
  }

  draw(ctx: CanvasRenderingContext2D) {
    for (const p of this._pool) {
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  get count(): number { return this._pool.length; }
}

// ── Screen Shake ─────────────────────────────────────────────────────────────

export class Shake {
  private _amplitude = 0;
  private _elapsed   = 0;
  private _duration  = 0;
  private _x = 0;
  private _y = 0;

  /** @param amplitude max offset px, @param duration seconds */
  trigger(amplitude: number, durationSeconds: number) {
    // Allow re-triggering to bump amplitude
    this._amplitude = Math.max(this._amplitude, amplitude);
    this._duration  = durationSeconds;
    this._elapsed   = 0;
  }

  update(dt: number) {
    if (this._elapsed >= this._duration) {
      this._x = this._y = 0;
      return;
    }
    this._elapsed += dt;
    const progress = this._elapsed / this._duration;
    const strength = this._amplitude * (1 - progress);
    this._x = (Math.random() * 2 - 1) * strength;
    this._y = (Math.random() * 2 - 1) * strength;
  }

  /** Apply shake offset to canvas context. Call ctx.save() before, ctx.restore() after. */
  apply(ctx: CanvasRenderingContext2D) {
    if (this._elapsed < this._duration) {
      ctx.translate(this._x, this._y);
    }
  }

  get active(): boolean { return this._elapsed < this._duration; }
}

// ── FloatingText ──────────────────────────────────────────────────────────────

interface FloatText {
  text:  string;
  x:     number;
  y:     number;
  vy:    number;   // px/s upward
  life:  number;   // 0..1
  decay: number;
  color: string;
  size:  number;
}

export class FloatingText {
  private _pool: FloatText[] = [];

  spawn(x: number, y: number, text: string, color = "#ffffff", size = 16) {
    this._pool.push({
      text, x, y, color, size,
      vy:    -60,
      life:   1,
      decay:  1 / 0.8,
    });
  }

  update(dt: number) {
    for (let i = this._pool.length - 1; i >= 0; i--) {
      const f = this._pool[i];
      f.y    += f.vy * dt;
      f.life -= f.decay * dt;
      if (f.life <= 0) this._pool.splice(i, 1);
    }
  }

  draw(ctx: CanvasRenderingContext2D) {
    for (const f of this._pool) {
      ctx.globalAlpha = Math.max(0, f.life);
      ctx.fillStyle   = f.color;
      ctx.font        = `bold ${f.size}px monospace`;
      ctx.textAlign   = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(f.text, f.x, f.y);
    }
    ctx.globalAlpha = 1;
    ctx.textAlign   = "left";
    ctx.textBaseline = "alphabetic";
  }
}
