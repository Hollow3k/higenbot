# Scaffold API Reference

All scaffold classes are **inlined** into `src/main.ts` before your code runs.
Do NOT write or modify scaffold files. Import them by writing your game code
after the scaffold preamble — all names are already in scope.

---

## InputManager

```ts
const input = new InputManager({
  action_name: { keys: ["ArrowLeft", "KeyA"] },
  // ... all actions
});
input.attachCanvas(canvas, logicalW, logicalH);  // call once after setupCanvas
input.touchControls({
  joystick?: { side: "left" | "right" },
  buttons?: [{ action, label, x, y, r }],   // x,y,r in logical coords
  tapAnywhere?: "action_name",
});

// Query in update(dt) only:
input.isDown("action")       // true while held
input.wasPressed("action")   // true for ONE frame only (use for jump, restart, pause)
input.wasReleased("action")  // true for ONE frame on key-up
input.axis("neg_action", "pos_action")     // returns -1, 0, or +1
input.joyAxis("neg", "pos")    // joystick + keyboard combined, with dead zone
input.joyAxisY("neg", "pos")   // vertical axis
input.pointer  // { x, y, down, justPressed } in logical coords
input.isTouch  // true if a touch event was ever seen
input.endFrame()   // MUST be called at the END of every update() frame
input.drawTouchControls(ctx)  // call in render(), draws joystick+buttons on touch
```

**Rules:** No raw addEventListener for gameplay. No `event.keyCode`. One-shot
actions (jump, restart, pause) → `wasPressed`. Continuous → `isDown` or `axis`.
All bound keys + Space + Arrows automatically prevent host-page scroll.
All state cleared on window blur and visibilitychange.

---

## GameLoop

```ts
const loop = new GameLoop(ctx, update, render);
// update: (dt: number) => void   — dt is always 1/60 s (fixed timestep)
// render: (ctx, alpha) => void   — alpha 0..1 for interpolation (usually ignored)
loop.start();
loop.pause();
loop.resume();
loop.stop();
loop.isPaused  // boolean
```

Auto-pauses on `visibilitychange`. dt is clamped to ≤ 50 ms.

---

## setupCanvas

```ts
const { canvas, ctx, scale, offsetX, offsetY, toLogical } =
  setupCanvas(logicalW, logicalH);
// Handles DPR, letterbox scaling, canvas focus, pointer-to-logical conversion.
// Call BEFORE constructing InputManager so attachCanvas gets the right element.
```

After calling `setupCanvas`, pass the canvas to `input.attachCanvas(...)`.
The canvas already has `tabIndex=0` and focuses on first pointerdown.

---

## AudioManager

```ts
const audio = new AudioManager();
audio.sweep("sine"|"square"|"sawtooth"|"triangle", freqStart, freqEnd, durationMs, volume?)
audio.beep("sine", 440, 120)              // flat tone
audio.noise(durationMs, volume?)          // white noise
audio.toggleMute()                        // or press M
audio.isMuted                             // boolean
```

Lazily unlocked on first gesture. Fails silently if WebAudio unavailable.
M key wired automatically.

---

## Particles

```ts
const particles = new Particles();
particles.burst(x, y, count, color, {
  speed?,     // px/s, default 120
  radius?,    // dot radius, default 3
  lifetime?,  // seconds, default 0.4
  spread?,    // radians full arc, default 2π
  angle?,     // center angle
});
particles.update(dt);
particles.draw(ctx);
```

---

## Shake

```ts
const shake = new Shake();
shake.trigger(amplitudePx, durationSeconds);
shake.update(dt);
// In render:
ctx.save(); shake.apply(ctx); /* draw world */ ctx.restore();
shake.active  // boolean
```

---

## FloatingText

```ts
const floatText = new FloatingText();
floatText.spawn(x, y, "+10", "#ffdd00", fontSize?);
floatText.update(dt);
floatText.draw(ctx);  // call after world, before HUD
```

---

## Ease

```ts
Ease.outQuad(t)   Ease.outCubic(t)  Ease.outBack(t)
Ease.inQuad(t)    Ease.inOutQuad(t) Ease.outBounce(t)
Ease.outElastic(t) Ease.linear(t)
// t is 0..1, returns 0..1
```

---

## Tween

```ts
const tween = new Tween(fromValue, toValue, durationSeconds, Ease.outQuad, onDone?);
tween.update(dt);
tween.value   // current interpolated value
tween.done    // boolean
```

---

## StateMachine

```ts
const sm = new StateMachine();
sm.register("menu", {
  enter?() {},
  exit?() {},
  update?(dt: number) {},
  render?(ctx: CanvasRenderingContext2D) {},
});
sm.set("menu");   // triggers exit on old state, enter on new
sm.current        // string
sm.update(dt);    // delegates to current state
sm.render(ctx);   // delegates to current state
```

---

## Storage (high score)

```ts
getHighScore(key?)          // returns number, default 0
saveHighScore(score, key?)  // saves if new best, returns best score
```

try/catch-safe — works in sandboxed iframes with an in-memory fallback.

---

## Typical main.ts structure

```ts
// 1. CONFIG object with every tunable number
const CONFIG = { W: 960, H: 540, PLAYER_SPEED: 280, ... };

// 2. Setup
const { canvas, ctx } = setupCanvas(CONFIG.W, CONFIG.H);
const input    = new InputManager({ move_left: { keys: [...] }, ... });
input.attachCanvas(canvas, CONFIG.W, CONFIG.H);
input.touchControls({ joystick: { side: "left" }, buttons: [...] });
const audio    = new AudioManager();
const particles = new Particles();
const shake    = new Shake();
const floatText = new FloatingText();
const sm       = new StateMachine();

// 3. Register states (menu, playing, paused, game_over)
sm.register("menu", { update(dt) { ... }, render(ctx) { ... } });
sm.register("playing", { ... });
sm.register("paused",  { ... });
sm.register("game_over", { ... });

// 4. Start
sm.set("menu");
const loop = new GameLoop(ctx,
  (dt) => { sm.update(dt); input.endFrame(); },
  (ctx)  => { sm.render(ctx); },
);
loop.start();
```
