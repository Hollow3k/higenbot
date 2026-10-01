// ── setupCanvas ───────────────────────────────────────────────────────────────
// Creates or reuses a <canvas>, handles devicePixelRatio, letterbox scaling,
// pointer-to-logical coordinate conversion, and keyboard focus.

export interface CanvasSetup {
  canvas:  HTMLCanvasElement;
  ctx:     CanvasRenderingContext2D;
  /** Current DPR-aware scale factor (logical → physical) */
  scale:   number;
  /** Pixel offset from window origin to the letterboxed canvas area */
  offsetX: number;
  offsetY: number;
  /** Convert a clientX/Y to logical coordinates */
  toLogical: (clientX: number, clientY: number) => [number, number];
}

export function setupCanvas(logicalW: number, logicalH: number): CanvasSetup {
  let canvas = document.querySelector<HTMLCanvasElement>("canvas");
  if (!canvas) {
    canvas = document.createElement("canvas");
    document.body.appendChild(canvas);
  }

  // Keyboard focus
  canvas.tabIndex = 0;
  canvas.style.outline = "none";
  canvas.style.display = "block";
  canvas.style.cursor  = "default";

  const ctx = canvas.getContext("2d")!;

  let scale   = 1;
  let offsetX = 0;
  let offsetY = 0;

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    const winW = window.innerWidth;
    const winH = window.innerHeight;

    // Letterbox: fit logical rect into window keeping aspect ratio
    const scaleX = winW / logicalW;
    const scaleY = winH / logicalH;
    scale = Math.min(scaleX, scaleY);

    const displayW = Math.round(logicalW * scale);
    const displayH = Math.round(logicalH * scale);

    offsetX = Math.round((winW - displayW) / 2);
    offsetY = Math.round((winH - displayH) / 2);

    // Physical pixel size
    canvas!.width  = displayW * dpr;
    canvas!.height = displayH * dpr;

    // CSS size — the visible letterboxed area
    canvas!.style.width  = `${displayW}px`;
    canvas!.style.height = `${displayH}px`;
    canvas!.style.position = "absolute";
    canvas!.style.left = `${offsetX}px`;
    canvas!.style.top  = `${offsetY}px`;

    // Scale context so we draw in logical pixels
    ctx.setTransform(dpr * scale, 0, 0, dpr * scale, 0, 0);
  }

  window.addEventListener("resize", resize);
  resize();

  // Focus canvas on first pointerdown (gives keyboard events)
  canvas.addEventListener("pointerdown", () => canvas!.focus(), { once: false });
  // Focus immediately on load
  requestAnimationFrame(() => canvas!.focus());

  const toLogical = (clientX: number, clientY: number): [number, number] => [
    (clientX - offsetX) / scale,
    (clientY - offsetY) / scale,
  ];

  return {
    canvas,
    ctx,
    get scale()   { return scale;   },
    get offsetX() { return offsetX; },
    get offsetY() { return offsetY; },
    toLogical,
  };
}
