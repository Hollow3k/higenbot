/**
 * SKELETON GAME — "Dot Dash"
 * ──────────────────────────
 * A complete, tiny reference implementation that uses EVERY scaffold module.
 * Compiles under strict mode with zero errors.
 *
 * Mechanics: move a square, collect dots for points, dodge hazards,
 * game over on hit, one-input restart, pause, touch controls, sounds,
 * particles, screen shake, floating score text, high score.
 *
 * This file demonstrates the STRUCTURE your game must follow:
 *   1. CONFIG object at top with every tunable number
 *   2. Typed entities as classes with update(dt)/draw(ctx)
 *   3. StateMachine driving all states
 *   4. InputManager for all input (no raw event listeners)
 *   5. GameLoop with fixed timestep
 *   6. All motion using dt
 *   7. setupCanvas for letterboxing + focus
 *   8. Particles, Shake, FloatingText for juice
 *   9. AudioManager for all sounds (lazily unlocked)
 *  10. storage.ts for high score (try/catch-safe)
 */

// ── CONFIG ────────────────────────────────────────────────────────────────────
// All tunable numbers live here. No magic numbers elsewhere.
const CONFIG = {
  // Canvas
  W: 960, H: 540,

  // Player
  PLAYER_SIZE:   32,
  PLAYER_SPEED:  280,    // px/s
  PLAYER_COLOR:  "#00ffcc",
  PLAYER_HIT_BOX: 24,   // hitbox slightly smaller than visual

  // Dot (collectible)
  DOT_RADIUS:    10,
  DOT_COLOR:     "#ffdd00",
  DOT_SCORE:     10,

  // Hazard
  HAZ_SIZE:      28,
  HAZ_COLOR:     "#ff4455",
  HAZ_MIN_SPEED: 100,
  HAZ_MAX_SPEED: 220,
  HAZ_SPAWN_INT: 2.2,   // seconds between spawns

  // Invincibility after hit
  INVINCE_DUR:   1.2,   // seconds
  INVINCE_HZ:    10,    // flicker frequency

  // Juice
  SHAKE_AMP:     5,     // px
  SHAKE_DUR:     0.25,  // seconds

  // Palette
  BG:     "#0d0d1a",
  TEXT:   "#e0e0ff",
  DIM:    "#555577",
};

// ── SCAFFOLD CLASSES ─────────────────────────────────────────────────────────
// NOTE: In the real pipeline the scaffold is INLINED above this file by the
// backend before sending to the in-browser TypeScript compiler.
// When testing locally, import from the actual paths:
//   import { InputManager }   from "./input.js";   (etc.)
// The backend strips these imports before inlining.

// (In the inlined pipeline, InputManager, GameLoop, setupCanvas, AudioManager,
//  Particles, Shake, FloatingText, StateMachine, getHighScore, saveHighScore
//  are already declared above this code block.)

// ── TYPES ─────────────────────────────────────────────────────────────────────

interface Dot {
  x: number; y: number; active: boolean;
}

interface Hazard {
  x: number; y: number;
  vx: number; vy: number;
  active: boolean;
}

// ── STATE ─────────────────────────────────────────────────────────────────────

let score   = 0;
let hiScore = 0;
let lives   = 3;

let playerX = CONFIG.W / 2;
let playerY = CONFIG.H / 2;
let invince = 0;         // remaining invincibility seconds

let dots:    Dot[]    = [];
let hazards: Hazard[] = [];
let hazTimer = 0;
let dotTimer = 0;

// ── SETUP ─────────────────────────────────────────────────────────────────────

const { canvas, ctx } = setupCanvas(CONFIG.W, CONFIG.H);
canvas.style.background = CONFIG.BG;

const input = new InputManager({
  move_left:  { keys: ["ArrowLeft",  "KeyA"] },
  move_right: { keys: ["ArrowRight", "KeyD"] },
  move_up:    { keys: ["ArrowUp",    "KeyW"] },
  move_down:  { keys: ["ArrowDown",  "KeyS"] },
  primary:    { keys: ["Space", "Enter"] },
  pause:      { keys: ["KeyP", "Escape"] },
  restart:    { keys: ["KeyR", "Enter"] },
  mute:       { keys: ["KeyM"] },
});

input.attachCanvas(canvas, CONFIG.W, CONFIG.H);

// Touch controls: joystick left, tap-anywhere for menus
input.touchControls({
  joystick: { side: "left" },
  buttons: [
    { action: "pause",   label: "⏸",  x: CONFIG.W - 44, y: 44,              r: 28 },
  ],
  tapAnywhere: "primary",
});

const audio     = new AudioManager();
const particles = new Particles();
const shake     = new Shake();
const floatText = new FloatingText();
const sm        = new StateMachine();

// ── HELPERS ───────────────────────────────────────────────────────────────────

function resetGame() {
  score   = 0;
  lives   = 3;
  playerX = CONFIG.W / 2;
  playerY = CONFIG.H / 2;
  invince = 0;
  dots    = [];
  hazards = [];
  hazTimer = 0;
  dotTimer = 0;
  spawnDot();
}

function spawnDot() {
  dots.push({
    x: CONFIG.DOT_RADIUS + Math.random() * (CONFIG.W - CONFIG.DOT_RADIUS * 2),
    y: CONFIG.DOT_RADIUS + Math.random() * (CONFIG.H - CONFIG.DOT_RADIUS * 2),
    active: true,
  });
}

function spawnHazard() {
  // Spawn from a random edge
  const edge = Math.floor(Math.random() * 4);
  let x = 0, y = 0;
  const spd = CONFIG.HAZ_MIN_SPEED + Math.random() * (CONFIG.HAZ_MAX_SPEED - CONFIG.HAZ_MIN_SPEED);
  const angle = Math.random() * Math.PI * 0.5 - Math.PI * 0.25; // toward center-ish
  let vx = 0, vy = 0;
  if (edge === 0) { x = Math.random() * CONFIG.W;  y = -CONFIG.HAZ_SIZE; vx = Math.sin(angle) * spd; vy =  spd * Math.cos(angle); }
  if (edge === 1) { x = CONFIG.W + CONFIG.HAZ_SIZE; y = Math.random() * CONFIG.H; vx = -spd * Math.cos(angle); vy = Math.sin(angle) * spd; }
  if (edge === 2) { x = Math.random() * CONFIG.W;  y = CONFIG.H + CONFIG.HAZ_SIZE; vx = Math.sin(angle) * spd; vy = -spd * Math.cos(angle); }
  if (edge === 3) { x = -CONFIG.HAZ_SIZE;           y = Math.random() * CONFIG.H; vx =  spd * Math.cos(angle); vy = Math.sin(angle) * spd; }
  hazards.push({ x, y, vx, vy, active: true });
}

function checkHit(ax: number, ay: number, bx: number, by: number, r: number): boolean {
  const dx = ax - bx, dy = ay - by;
  return dx * dx + dy * dy < r * r;
}

// ── UPDATE / RENDER ───────────────────────────────────────────────────────────

function updatePlaying(dt: number) {
  // Player movement via joyAxis (supports joystick AND keyboard)
  const dx = input.joyAxis("move_left", "move_right");
  const dy = input.joyAxisY("move_up",  "move_down");
  // Normalize diagonal
  const len = Math.sqrt(dx * dx + dy * dy);
  const nx  = len > 0 ? dx / len : 0;
  const ny  = len > 0 ? dy / len : 0;

  playerX = Math.max(CONFIG.PLAYER_SIZE / 2,
            Math.min(CONFIG.W - CONFIG.PLAYER_SIZE / 2,
              playerX + nx * CONFIG.PLAYER_SPEED * dt));
  playerY = Math.max(CONFIG.PLAYER_SIZE / 2,
            Math.min(CONFIG.H - CONFIG.PLAYER_SIZE / 2,
              playerY + ny * CONFIG.PLAYER_SPEED * dt));

  // Invincibility countdown
  if (invince > 0) invince -= dt;

  // Dot spawner
  dotTimer -= dt;
  if (dotTimer <= 0) { spawnDot(); dotTimer = 3 + Math.random() * 2; }

  // Hazard spawner
  hazTimer -= dt;
  if (hazTimer <= 0) { spawnHazard(); hazTimer = CONFIG.HAZ_SPAWN_INT; }

  // Dot collection
  const hb2 = (CONFIG.PLAYER_HIT_BOX / 2 + CONFIG.DOT_RADIUS);
  for (const dot of dots) {
    if (!dot.active) continue;
    if (checkHit(playerX, playerY, dot.x, dot.y, hb2)) {
      dot.active = false;
      score += CONFIG.DOT_SCORE;
      audio.sweep("sine", 440, 880, 80);
      particles.burst(dot.x, dot.y, 8, CONFIG.DOT_COLOR);
      floatText.spawn(dot.x, dot.y - 10, `+${CONFIG.DOT_SCORE}`, CONFIG.DOT_COLOR);
    }
  }
  dots = dots.filter(d => d.active);

  // Hazard movement + collision
  for (const h of hazards) {
    if (!h.active) continue;
    h.x += h.vx * dt;
    h.y += h.vy * dt;
    // Remove if far off-screen
    if (h.x < -200 || h.x > CONFIG.W + 200 || h.y < -200 || h.y > CONFIG.H + 200) {
      h.active = false;
      continue;
    }
    // Collision with player
    if (invince <= 0) {
      const hitR = CONFIG.PLAYER_HIT_BOX / 2 + CONFIG.HAZ_SIZE / 2;
      if (checkHit(playerX, playerY, h.x, h.y, hitR)) {
        h.active = false;
        lives--;
        invince = CONFIG.INVINCE_DUR;
        audio.noise(120, 0.4);
        shake.trigger(CONFIG.SHAKE_AMP, CONFIG.SHAKE_DUR);
        particles.burst(playerX, playerY, 12, CONFIG.HAZ_COLOR, { speed: 180 });
        if (lives <= 0) {
          hiScore = saveHighScore(score);
          sm.set("game_over");
          return;
        }
      }
    }
  }
  hazards = hazards.filter(h => h.active);

  // Particles / fx
  particles.update(dt);
  floatText.update(dt);
  shake.update(dt);

  // Pause
  if (input.wasPressed("pause")) {
    audio.beep("sine", 330, 60);
    sm.set("paused");
  }
}

function renderPlaying(ctx: CanvasRenderingContext2D) {
  // Background
  ctx.fillStyle = CONFIG.BG;
  ctx.fillRect(0, 0, CONFIG.W, CONFIG.H);

  // Apply shake
  ctx.save();
  shake.apply(ctx);

  // Dots
  for (const dot of dots) {
    ctx.beginPath();
    ctx.arc(dot.x, dot.y, CONFIG.DOT_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = CONFIG.DOT_COLOR;
    ctx.fill();
  }

  // Hazards
  ctx.fillStyle = CONFIG.HAZ_COLOR;
  for (const h of hazards) {
    if (!h.active) continue;
    const hs = CONFIG.HAZ_SIZE;
    ctx.fillRect(h.x - hs / 2, h.y - hs / 2, hs, hs);
  }

  // Player (flicker during invincibility)
  const flicker = invince > 0 && Math.floor(invince * CONFIG.INVINCE_HZ) % 2 === 0;
  if (!flicker) {
    const ps = CONFIG.PLAYER_SIZE;
    ctx.shadowBlur   = 12;
    ctx.shadowColor  = CONFIG.PLAYER_COLOR;
    ctx.fillStyle    = CONFIG.PLAYER_COLOR;
    ctx.fillRect(playerX - ps / 2, playerY - ps / 2, ps, ps);
    ctx.shadowBlur   = 0;
  }

  ctx.restore();

  // Particles & floating text (not affected by shake)
  particles.draw(ctx);
  floatText.draw(ctx);

  // Touch controls (always on top)
  input.drawTouchControls(ctx);

  // HUD
  ctx.fillStyle = CONFIG.TEXT;
  ctx.font      = "16px monospace";
  ctx.textAlign = "left";
  ctx.fillText(`Score: ${score}`, 16, 28);
  ctx.textAlign = "right";
  ctx.fillText(`Lives: ${"♥ ".repeat(Math.max(0, lives)).trim()}`, CONFIG.W - 16, 28);
  if (audio.isMuted) {
    ctx.fillStyle = CONFIG.DIM;
    ctx.font      = "12px monospace";
    ctx.fillText("🔇 M to unmute", CONFIG.W - 16, 48);
  }
  ctx.textAlign = "left";
}

// ── STATE MACHINE REGISTRATION ────────────────────────────────────────────────

sm.register("menu", {
  enter() { hiScore = getHighScore(); },
  update(dt: number) {
    particles.update(dt);
    if (input.wasPressed("primary")) {
      resetGame();
      audio.sweep("square", 220, 440, 120);
      sm.set("playing");
    }
  },
  render(ctx: CanvasRenderingContext2D) {
    ctx.fillStyle = CONFIG.BG;
    ctx.fillRect(0, 0, CONFIG.W, CONFIG.H);
    particles.draw(ctx);

    ctx.fillStyle = CONFIG.PLAYER_COLOR;
    ctx.shadowBlur  = 20;
    ctx.shadowColor = CONFIG.PLAYER_COLOR;
    ctx.font        = "bold 48px monospace";
    ctx.textAlign   = "center";
    ctx.fillText("DOT DASH", CONFIG.W / 2, CONFIG.H / 2 - 60);
    ctx.shadowBlur = 0;

    ctx.fillStyle = CONFIG.TEXT;
    ctx.font      = "16px monospace";
    ctx.fillText("Collect dots. Dodge hazards.", CONFIG.W / 2, CONFIG.H / 2);

    if (hiScore > 0) {
      ctx.fillStyle = CONFIG.DIM;
      ctx.font = "14px monospace";
      ctx.fillText(`Best: ${hiScore}`, CONFIG.W / 2, CONFIG.H / 2 + 30);
    }

    ctx.fillStyle = CONFIG.TEXT;
    ctx.font = "14px monospace";
    const helpText = input.isTouch
      ? "Tap to start · Left joystick to move"
      : "Arrows / WASD to move · Space to start · P to pause · M to mute";
    ctx.fillText(helpText, CONFIG.W / 2, CONFIG.H / 2 + 68);

    input.drawTouchControls(ctx);
    ctx.textAlign = "left";
  },
});

sm.register("playing", {
  enter:  resetGame,
  update: updatePlaying,
  render: renderPlaying,
});

sm.register("paused", {
  update(_dt: number) {
    if (input.wasPressed("pause") || input.wasPressed("primary")) {
      sm.set("playing");
    }
  },
  render(ctx: CanvasRenderingContext2D) {
    // Re-render the game world frozen
    renderPlaying(ctx);
    // Overlay
    ctx.fillStyle = "rgba(0,0,0,0.5)";
    ctx.fillRect(0, 0, CONFIG.W, CONFIG.H);
    ctx.fillStyle = CONFIG.TEXT;
    ctx.font      = "bold 36px monospace";
    ctx.textAlign = "center";
    ctx.fillText("PAUSED", CONFIG.W / 2, CONFIG.H / 2 - 16);
    ctx.font = "14px monospace";
    ctx.fillStyle = CONFIG.DIM;
    ctx.fillText("P / Escape to resume", CONFIG.W / 2, CONFIG.H / 2 + 24);
    ctx.textAlign = "left";
  },
});

sm.register("game_over", {
  update(_dt: number) {
    particles.update(_dt);
    // Single input to restart: R, Enter, Space, or tap
    if (input.wasPressed("restart") || input.wasPressed("primary")) {
      audio.sweep("square", 220, 440, 120);
      sm.set("playing");
    }
  },
  render(ctx: CanvasRenderingContext2D) {
    ctx.fillStyle = CONFIG.BG;
    ctx.fillRect(0, 0, CONFIG.W, CONFIG.H);
    particles.draw(ctx);

    ctx.fillStyle = CONFIG.HAZ_COLOR;
    ctx.shadowBlur  = 16;
    ctx.shadowColor = CONFIG.HAZ_COLOR;
    ctx.font        = "bold 40px monospace";
    ctx.textAlign   = "center";
    ctx.fillText("GAME OVER", CONFIG.W / 2, CONFIG.H / 2 - 50);
    ctx.shadowBlur  = 0;

    ctx.fillStyle = CONFIG.TEXT;
    ctx.font      = "20px monospace";
    ctx.fillText(`Score: ${score}`, CONFIG.W / 2, CONFIG.H / 2 + 4);
    ctx.font = "16px monospace";
    ctx.fillStyle = CONFIG.DIM;
    ctx.fillText(`Best: ${hiScore}`, CONFIG.W / 2, CONFIG.H / 2 + 32);

    ctx.fillStyle = CONFIG.TEXT;
    ctx.font      = "14px monospace";
    const restartText = input.isTouch ? "Tap to restart" : "R / Enter / Space to restart";
    ctx.fillText(restartText, CONFIG.W / 2, CONFIG.H / 2 + 72);

    input.drawTouchControls(ctx);
    ctx.textAlign = "left";
  },
});

// ── MAIN LOOP ─────────────────────────────────────────────────────────────────

sm.set("menu");

const loop = new GameLoop(ctx,
  (dt) => {
    sm.update(dt);
    input.endFrame();          // ALWAYS last in update
  },
  (renderCtx) => {
    sm.render(renderCtx);
  },
);

loop.start();
