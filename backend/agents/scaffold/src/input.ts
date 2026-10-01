// ── InputManager ─────────────────────────────────────────────────────────────
// Handles keyboard, pointer, and virtual touch controls.
// Prevents Arrow/Space from scrolling the host page.
// Clears all state on blur / visibilitychange so keys never get "stuck".

interface ActionBindings {
  [action: string]: { keys: string[] };
}

interface TouchButton {
  action: string;
  label: string;
  x: number;  // logical coords
  y: number;
  r: number;  // radius
}

interface TouchControlsConfig {
  joystick?: { side: "left" | "right" };
  buttons?: TouchButton[];
  tapAnywhere?: string;  // action triggered by a tap with no other match
}

const SCROLL_PREVENT = new Set([
  "Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
]);

export class InputManager {
  private bindings: ActionBindings;
  // current frame
  private _down  = new Map<string, boolean>();
  private _pressed  = new Map<string, boolean>();
  private _released = new Map<string, boolean>();
  // pointer
  private _ptrX = 0;
  private _ptrY = 0;
  private _ptrDown = false;
  private _ptrJustPressed = false;
  // logical canvas dimensions (set by setupCanvas or manually)
  private _logW = 960;
  private _logH = 540;
  // touch controls
  private _touchCfg: TouchControlsConfig | null = null;
  private _isTouch = false;
  // joystick tracking
  private _joyId: number | null = null;
  private _joyOriginX = 0;
  private _joyOriginY = 0;
  private _joyDx = 0;
  private _joyDy = 0;
  private static readonly JOY_RADIUS = 48;
  private static readonly JOY_DEAD = 0.25;
  // button touch tracking (pointerId → action)
  private _btnTouches = new Map<number, string>();
  // canvas ref for drawing touch controls
  private _canvas: HTMLCanvasElement | null = null;
  // scale factor (logical → screen), used for pointer conversion
  private _scale = 1;
  private _offsetX = 0;
  private _offsetY = 0;

  constructor(bindings: ActionBindings) {
    this.bindings = bindings;
    this._buildKeyMap();
    window.addEventListener("keydown", this._onKeyDown);
    window.addEventListener("keyup",   this._onKeyUp);
    window.addEventListener("blur",    this._clear);
    document.addEventListener("visibilitychange", this._onVisibility);
  }

  // Call once with the canvas from setupCanvas
  attachCanvas(canvas: HTMLCanvasElement, logW: number, logH: number) {
    this._canvas   = canvas;
    this._logW     = logW;
    this._logH     = logH;
    canvas.addEventListener("pointerdown",   this._onPtrDown);
    canvas.addEventListener("pointermove",   this._onPtrMove);
    canvas.addEventListener("pointerup",     this._onPtrUp);
    canvas.addEventListener("pointercancel", this._onPtrUp);
    canvas.style.touchAction = "none";
  }

  // Called by setupCanvas when it resizes
  updateScale(scale: number, offsetX: number, offsetY: number) {
    this._scale   = scale;
    this._offsetX = offsetX;
    this._offsetY = offsetY;
  }

  // Enable virtual touch controls; draws on the canvas each frame
  touchControls(cfg: TouchControlsConfig) {
    this._touchCfg = cfg;
  }

  get isTouch(): boolean { return this._isTouch; }

  // ── Key map ───────────────────────────────────────────────────────────────

  private _keyToAction = new Map<string, string>();

  private _buildKeyMap() {
    for (const [action, { keys }] of Object.entries(this.bindings)) {
      for (const k of keys) {
        this._keyToAction.set(k.toLowerCase(), action);
      }
    }
  }

  private _onKeyDown = (e: KeyboardEvent) => {
    const code = e.code.toLowerCase();
    const key  = e.key.toLowerCase();
    if (SCROLL_PREVENT.has(e.code)) e.preventDefault();
    const action = this._keyToAction.get(code) ?? this._keyToAction.get(key);
    if (!action || e.repeat) return;
    if (!this._down.get(action)) {
      this._pressed.set(action, true);
    }
    this._down.set(action, true);
  };

  private _onKeyUp = (e: KeyboardEvent) => {
    const code = e.code.toLowerCase();
    const key  = e.key.toLowerCase();
    const action = this._keyToAction.get(code) ?? this._keyToAction.get(key);
    if (!action) return;
    this._down.set(action, false);
    this._released.set(action, true);
  };

  private _clear = () => {
    this._down.clear();
    this._pressed.clear();
    this._released.clear();
    this._ptrDown = false;
    this._joyId   = null;
    this._joyDx   = 0;
    this._joyDy   = 0;
    this._btnTouches.clear();
  };

  private _onVisibility = () => {
    if (document.hidden) this._clear();
  };

  // ── Pointer / touch ───────────────────────────────────────────────────────

  private _screenToLogical(screenX: number, screenY: number): [number, number] {
    return [
      (screenX - this._offsetX) / this._scale,
      (screenY - this._offsetY) / this._scale,
    ];
  }

  private _onPtrDown = (e: PointerEvent) => {
    e.preventDefault();
    if (e.pointerType === "touch" || e.pointerType === "pen") this._isTouch = true;
    const [lx, ly] = this._screenToLogical(e.clientX, e.clientY);

    // Check touch buttons first
    if (this._touchCfg?.buttons && this._isTouch) {
      for (const btn of this._touchCfg.buttons) {
        const dx = lx - btn.x, dy = ly - btn.y;
        if (dx * dx + dy * dy <= btn.r * btn.r) {
          this._btnTouches.set(e.pointerId, btn.action);
          this._pressed.set(btn.action, true);
          this._down.set(btn.action, true);
          this._canvas?.setPointerCapture(e.pointerId);
          return;
        }
      }
    }

    // Check joystick
    if (this._touchCfg?.joystick && this._isTouch) {
      const side = this._touchCfg.joystick.side;
      const inSide = side === "left" ? lx < this._logW / 2 : lx >= this._logW / 2;
      if (inSide && this._joyId === null) {
        this._joyId      = e.pointerId;
        this._joyOriginX = lx;
        this._joyOriginY = ly;
        this._joyDx      = 0;
        this._joyDy      = 0;
        this._canvas?.setPointerCapture(e.pointerId);
        return;
      }
    }

    // Fallback: pointer for non-touch or tap-anywhere
    this._ptrX = lx;
    this._ptrY = ly;
    this._ptrDown = true;
    this._ptrJustPressed = true;

    if (this._touchCfg?.tapAnywhere && this._isTouch) {
      const act = this._touchCfg.tapAnywhere;
      this._pressed.set(act, true);
      this._down.set(act, true);
    }
  };

  private _onPtrMove = (e: PointerEvent) => {
    e.preventDefault();
    const [lx, ly] = this._screenToLogical(e.clientX, e.clientY);
    if (e.pointerId === this._joyId) {
      const r = InputManager.JOY_RADIUS;
      let dx = lx - this._joyOriginX;
      let dy = ly - this._joyOriginY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > r) { dx = dx / dist * r; dy = dy / dist * r; }
      this._joyDx = dx / r;
      this._joyDy = dy / r;
      return;
    }
    this._ptrX = lx;
    this._ptrY = ly;
  };

  private _onPtrUp = (e: PointerEvent) => {
    e.preventDefault();
    if (e.pointerId === this._joyId) {
      this._joyId = null;
      this._joyDx = 0;
      this._joyDy = 0;
      return;
    }
    const action = this._btnTouches.get(e.pointerId);
    if (action) {
      this._down.set(action, false);
      this._released.set(action, true);
      this._btnTouches.delete(e.pointerId);
      return;
    }
    if (this._touchCfg?.tapAnywhere && this._isTouch) {
      const act = this._touchCfg.tapAnywhere;
      this._down.set(act, false);
      this._released.set(act, true);
    }
    this._ptrDown = false;
  };

  // ── Public query API ─────────────────────────────────────────────────────

  isDown(action: string):     boolean { return this._down.get(action)     ?? false; }
  wasPressed(action: string): boolean { return this._pressed.get(action)  ?? false; }
  wasReleased(action: string):boolean { return this._released.get(action) ?? false; }

  /** Returns −1, 0, or +1 (normalized) for an axis pair. */
  axis(neg: string, pos: string): number {
    const n = this.isDown(neg) ? -1 : 0;
    const p = this.isDown(pos) ?  1 : 0;
    return n + p;
  }

  /** Joystick axis value −1..+1, with dead zone applied. */
  joyAxis(neg: string, pos: string): number {
    // prefer joystick if active
    const jx = Math.abs(this._joyDx) > InputManager.JOY_DEAD ? this._joyDx : 0;
    const kb  = this.axis(neg, pos);
    return jx !== 0 ? jx : kb;
  }

  joyAxisY(neg: string, pos: string): number {
    const jy = Math.abs(this._joyDy) > InputManager.JOY_DEAD ? this._joyDy : 0;
    const kb  = this.axis(neg, pos);
    return jy !== 0 ? jy : kb;
  }

  get pointer() {
    return {
      x: this._ptrX,
      y: this._ptrY,
      down: this._ptrDown,
      justPressed: this._ptrJustPressed,
    };
  }

  // Call at the END of each frame (after update + render)
  endFrame() {
    this._pressed.clear();
    this._released.clear();
    this._ptrJustPressed = false;
  }

  // ── Touch controls rendering ─────────────────────────────────────────────

  drawTouchControls(ctx: CanvasRenderingContext2D) {
    if (!this._isTouch || !this._touchCfg) return;
    ctx.save();
    ctx.globalAlpha = 0.45;

    // Joystick
    const cfg = this._touchCfg;
    if (cfg.joystick) {
      const r = InputManager.JOY_RADIUS;
      const side = cfg.joystick.side;
      const ox = side === "left" ? r + 24 : this._logW - r - 24;
      const oy = this._logH - r - 24;
      // outer ring
      ctx.beginPath();
      ctx.arc(ox, oy, r, 0, Math.PI * 2);
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.stroke();
      // thumb nub
      const nx = ox + this._joyDx * r;
      const ny = oy + this._joyDy * r;
      ctx.beginPath();
      ctx.arc(nx, ny, r * 0.4, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.fill();
    }

    // Buttons
    if (cfg.buttons) {
      for (const btn of cfg.buttons) {
        ctx.beginPath();
        ctx.arc(btn.x, btn.y, btn.r, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        ctx.fillStyle = "#000000";
        ctx.font = `${Math.round(btn.r * 0.55)}px monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(btn.label, btn.x, btn.y);
      }
    }

    ctx.restore();
  }

  destroy() {
    window.removeEventListener("keydown", this._onKeyDown);
    window.removeEventListener("keyup",   this._onKeyUp);
    window.removeEventListener("blur",    this._clear);
    document.removeEventListener("visibilitychange", this._onVisibility);
  }
}
