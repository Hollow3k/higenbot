// Snake Odyssey - Retro Arcade Survival
const canvas = document.getElementById('game') as HTMLCanvasElement;
const ctx = canvas.getContext('2d')!;

const COLS = 40, ROWS = 30, CELL = 20;
const TARGET_SCORE = 1000, SURVIVE_TIME = 180;

// Simple Web Audio Synthesizer
const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
function playSound(type: 'eat' | 'mult' | 'hit' | 'win') {
  if (audioCtx.state === 'suspended') audioCtx.resume();
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain); gain.connect(audioCtx.destination);
  const now = audioCtx.currentTime;
  if (type === 'eat') {
    osc.frequency.setValueAtTime(440, now);
    osc.frequency.exponentialRampToValueAtTime(880, now + 0.08);
    gain.gain.setValueAtTime(0.2, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.08);
    osc.start(now); osc.stop(now + 0.08);
  } else if (type === 'mult') {
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(587, now);
    osc.frequency.exponentialRampToValueAtTime(1174, now + 0.15);
    gain.gain.setValueAtTime(0.3, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.15);
    osc.start(now); osc.stop(now + 0.15);
  } else if (type === 'hit') {
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(180, now);
    osc.frequency.linearRampToValueAtTime(40, now + 0.35);
    gain.gain.setValueAtTime(0.4, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.35);
    osc.start(now); osc.stop(now + 0.35);
  } else if (type === 'win') {
    osc.type = 'square';
    [523, 659, 783, 1046].forEach((f, i) => {
      osc.frequency.setValueAtTime(f, now + i * 0.1);
    });
    gain.gain.setValueAtTime(0.25, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.45);
    osc.start(now); osc.stop(now + 0.45);
  }
}

type Point = { x: number; y: number };
type Particle = { x: number; y: number; vx: number; vy: number; life: number; color: string };

let score = 0, multiplier = 1, multTimer = 0, gameTime = 0, paused = false, state: 'play' | 'win' | 'lose' = 'play';
let shake = 0, playerTimer = 0, enemyTimer = 0;

let player: Point[] = [];
let dir: Point = { x: 1, y: 0 }, nextDir: Point = { x: 1, y: 0 };
let foods: { x: number; y: number; type: 'normal' | 'star' }[] = [];
let walls: Point[] = [];
let enemies: { body: Point[]; dir: Point; speed: number; color: string }[] = [];
let particles: Particle[] = [];

function isOccupied(x: number, y: number): boolean {
  if (walls.some(w => w.x === x && w.y === y)) return true;
  if (player.some(p => p.x === x && p.y === y)) return true;
  if (foods.some(f => f.x === x && f.y === y)) return true;
  return enemies.some(e => e.body.some(b => b.x === x && b.y === y));
}

function spawnFood() {
  while (foods.length < 5) {
    const x = Math.floor(Math.random() * (COLS - 4)) + 2;
    const y = Math.floor(Math.random() * (ROWS - 4)) + 2;
    if (!isOccupied(x, y)) {
      foods.push({ x, y, type: Math.random() < 0.25 ? 'star' : 'normal' });
    }
  }
}

function initGame() {
  score = 0; multiplier = 1; multTimer = 0; gameTime = 0;
  state = 'play'; paused = false; shake = 0;
  dir = { x: 1, y: 0 }; nextDir = { x: 1, y: 0 };
  
  // Player initial body in center
  player = [{ x: 10, y: 15 }, { x: 9, y: 15 }, { x: 8, y: 15 }, { x: 7, y: 15 }];

  // Generate retro symmetrical obstacles
  walls = [];
  for (let x = 0; x < COLS; x++) { walls.push({ x, y: 0 }); walls.push({ x, y: ROWS - 1 }); }
  for (let y = 0; y < ROWS; y++) { walls.push({ x: 0, y }); walls.push({ x: COLS - 1, y }); }
  
  // Internal obstacles
  const clusters: [number, number][] = [[10, 8], [30, 8], [10, 22], [30, 22], [20, 15]];
  clusters.forEach(([cx, cy]) => {
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        if (Math.random() > 0.35 && !(cx + dx === 10 && cy + dy === 15)) {
          walls.push({ x: cx + dx, y: cy + dy });
        }
      }
    }
  });

  // Spawn 2 enemy chaser/patrol snakes
  enemies = [
    { body: [{ x: 32, y: 6 }, { x: 33, y: 6 }, { x: 34, y: 6 }], dir: { x: -1, y: 0 }, speed: 0.13, color: '#ff0055' },
    { body: [{ x: 32, y: 24 }, { x: 33, y: 24 }, { x: 34, y: 24 }], dir: { x: -1, y: 0 }, speed: 0.14, color: '#ff5500' }
  ];

  foods = [];
  particles = [];
  spawnFood();
}

function addParticles(x: number, y: number, color: string, count = 12) {
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const spd = Math.random() * 4 + 1;
    particles.push({
      x: x * CELL + CELL / 2,
      y: y * CELL + CELL / 2,
      vx: Math.cos(angle) * spd,
      vy: Math.sin(angle) * spd,
      life: 1.0,
      color
    });
  }
}

// Input Handlers
window.addEventListener('keydown', (e) => {
  if (audioCtx.state === 'suspended') audioCtx.resume();
  if (e.code === 'Space') {
    if (state !== 'play') initGame();
    else paused = !paused;
    return;
  }
  if (state !== 'play') { initGame(); return; }

  const k = e.key.toLowerCase();
  if ((k === 'arrowup' || k === 'w') && dir.y !== 1) nextDir = { x: 0, y: -1 };
  else if ((k === 'arrowdown' || k === 's') && dir.y !== -1) nextDir = { x: 0, y: 1 };
  else if ((k === 'arrowleft' || k === 'a') && dir.x !== 1) nextDir = { x: -1, y: 0 };
  else if ((k === 'arrowright' || k === 'd') && dir.x !== -1) nextDir = { x: 1, y: 0 };
});

canvas.addEventListener('pointerdown', () => {
  if (state !== 'play') initGame();
});

let lastTime = performance.now();
function update(dt: number) {
  if (paused || state !== 'play') return;

  gameTime += dt;
  if (gameTime >= SURVIVE_TIME || score >= TARGET_SCORE) {
    state = 'win';
    playSound('win');
    return;
  }

  if (multTimer > 0) {
    multTimer -= dt;
    if (multTimer <= 0) multiplier = 1;
  }

  // Update Player (12 moves per sec)
  playerTimer += dt;
  if (playerTimer >= 0.08) {
    playerTimer = 0;
    dir = nextDir;
    const head = { x: player[0].x + dir.x, y: player[0].y + dir.y };

    // Collision with Walls
    if (walls.some(w => w.x === head.x && w.y === head.y)) {
      state = 'lose'; shake = 15; playSound('hit'); return;
    }
    // Collision with Self
    if (player.some(p => p.x === head.x && p.y === head.y)) {
      state = 'lose'; shake = 15; playSound('hit'); return;
    }
    // Collision with Enemies
    for (const en of enemies) {
      if (en.body.some(b => b.x === head.x && b.y === head.y)) {
        state = 'lose'; shake = 15; playSound('hit'); return;
      }
    }

    player.unshift(head);

    // Food check
    const foodIdx = foods.findIndex(f => f.x === head.x && f.y === head.y);
    if (foodIdx >= 0) {
      const f = foods[foodIdx];
      foods.splice(foodIdx, 1);
      if (f.type === 'star') {
        multiplier = Math.min( multiplier + 1, 5);
        multTimer = 6;
        score += 25 * multiplier;
        playSound('mult');
        addParticles(f.x, f.y, '#ffff00', 18);
      } else {
        score += 10 * multiplier;
        playSound('eat');
        addParticles(f.x, f.y, '#00ffcc', 10);
      }
      spawnFood();
    } else {
      player.pop();
    }
  }

  // Update AI Enemies
  enemyTimer += dt;
  enemies.forEach(en => {
    if (enemyTimer >= en.speed) {
      const eHead = en.body[0];
      const target = player[0];
      const possibleDirs = [{ x: 1, y: 0 }, { x: -1, y: 0 }, { x: 0, y: 1 }, { x: 0, y: -1 }]
        .filter(d => !(d.x === -en.dir.x && d.y === -en.dir.y))
        .filter(d => !walls.some(w => w.x === eHead.x + d.x && w.y === eHead.y + d.y));

      if (possibleDirs.length > 0) {
        // Choose dir minimizing distance to player or patrol randomly
        possibleDirs.sort((a, b) => {
          const d1 = Math.hypot(eHead.x + a.x - target.x, eHead.y + a.y - target.y);
          const d2 = Math.hypot(eHead.x + b.x - target.x, eHead.y + b.y - target.y);
          return (Math.random() < 0.65 ? d1 - d2 : 0);
        });
        en.dir = possibleDirs[0];
      }

      const nextEHead = { x: eHead.x + en.dir.x, y: eHead.y + en.dir.y };
      en.body.unshift(nextEHead);
      en.body.pop();

      // Check if enemy hit player head
      if (player.some(p => p.x === nextEHead.x && p.y === nextEHead.y)) {
        state = 'lose'; shake = 15; playSound('hit');
      }
    }
  });
  if (enemyTimer >= 0.14) enemyTimer = 0;

  // Update particles
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.x += p.vx; p.y += p.vy; p.life -= dt * 2.2;
    if (p.life <= 0) particles.splice(i, 1);
  }

  if (shake > 0) shake = Math.max(0, shake - dt * 25);
}

function render() {
  ctx.save();
  if (shake > 0) {
    ctx.translate((Math.random() - 0.5) * shake, (Math.random() - 0.5) * shake);
  }

  // Clear background with retro grid
  ctx.fillStyle = '#080812';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = '#121326';
  ctx.lineWidth = 1;
  for (let x = 0; x < canvas.width; x += CELL) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += CELL) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
  }

  // Draw Walls (neon purple/blue)
  ctx.fillStyle = '#1e1b4b';
  ctx.strokeStyle = '#6366f1';
  ctx.lineWidth = 2;
  walls.forEach(w => {
    ctx.fillRect(w.x * CELL + 1, w.y * CELL + 1, CELL - 2, CELL - 2);
    ctx.strokeRect(w.x * CELL + 1, w.y * CELL + 1, CELL - 2, CELL - 2);
  });

  // Draw Foods (pulsing glow)
  const pulse = Math.sin(performance.now() * 0.008) * 2;
  foods.forEach(f => {
    ctx.shadowBlur = 10;
    if (f.type === 'star') {
      ctx.fillStyle = '#ffea00';
      ctx.shadowColor = '#ffff00';
      ctx.beginPath();
      ctx.arc(f.x * CELL + CELL / 2, f.y * CELL + CELL / 2, CELL / 2.5 + pulse * 0.5, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.fillStyle = '#ff007f';
      ctx.shadowColor = '#ff007f';
      ctx.fillRect(f.x * CELL + 4, f.y * CELL + 4, CELL - 8, CELL - 8);
    }
  });
  ctx.shadowBlur = 0;

  // Draw Enemies
  enemies.forEach(en => {
    en.body.forEach((b, i) => {
      ctx.fillStyle = i === 0 ? '#ff0055' : en.color;
      ctx.shadowColor = en.color; ctx.shadowBlur = i === 0 ? 8 : 4;
      ctx.fillRect(b.x * CELL + 2, b.y * CELL + 2, CELL - 4, CELL - 4);
    });
  });

  // Draw Player Snake (Neon Cyan)
  player.forEach((p, i) => {
    ctx.shadowBlur = i === 0 ? 12 : 6;
    ctx.shadowColor = '#00f0ff';
    ctx.fillStyle = i === 0 ? '#ffffff' : `hsl(${175 + i * 2}, 100%, 55%)`;
    ctx.fillRect(p.x * CELL + 1, p.y * CELL + 1, CELL - 2, CELL - 2);
  });
  ctx.shadowBlur = 0;

  // Draw Particles
  particles.forEach(p => {
    ctx.fillStyle = p.color;
    ctx.globalAlpha = Math.max(0, p.life);
    ctx.fillRect(p.x, p.y, 4, 4);
  });
  ctx.globalAlpha = 1.0;

  // Draw HUD Banner
  ctx.fillStyle = 'rgba(5, 5, 15, 0.75)';
  ctx.fillRect(0, 0, canvas.width, 32);
  ctx.font = 'bold 15px "Courier New", monospace';
  ctx.fillStyle = '#00f0ff';
  ctx.fillText(`SCORE: ${score}/${TARGET_SCORE}`, 20, 22);

  ctx.fillStyle = '#ffea00';
  ctx.fillText(`MULT: x${multiplier} ${multTimer > 0 ? `(${multTimer.toFixed(1)}s)` : ''}`, 260, 22);

  const timeLeft = Math.max(0, SURVIVE_TIME - Math.floor(gameTime));
  const m = Math.floor(timeLeft / 60), s = timeLeft % 60;
  ctx.fillStyle = '#ff007f';
  ctx.fillText(`TIME: ${m}:${s < 10 ? '0' : ''}${s}`, 520, 22);

  ctx.fillStyle = '#a5b4fc';
  ctx.fillText(`LEN: ${player.length}`, 700, 22);

  // Overlay Messages
  if (state !== 'play' || paused) {
    ctx.fillStyle = 'rgba(8, 7, 16, 0.85)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.textAlign = 'center';

    if (paused) {
      ctx.fillStyle = '#00f0ff';
      ctx.font = 'bold 36px monospace';
      ctx.fillText('PAUSED', canvas.width / 2, canvas.height / 2);
      ctx.font = '16px monospace';
      ctx.fillText('PRESS SPACE TO RESUME', canvas.width / 2, canvas.height / 2 + 40);
    } else if (state === 'win') {
      ctx.fillStyle = '#00ff88';
      ctx.font = 'bold 42px monospace';
      ctx.fillText('MISSION COMPLETE!', canvas.width / 2, canvas.height / 2 - 20);
      ctx.fillStyle = '#fff';
      ctx.font = '20px monospace';
      ctx.fillText(`FINAL SCORE: ${score}  |  SURVIVED: ${Math.floor(gameTime)}s`, canvas.width / 2, canvas.height / 2 + 25);
      ctx.fillStyle = '#ffea00';
      ctx.fillText('PRESS SPACE OR CLICK TO PLAY AGAIN', canvas.width / 2, canvas.height / 2 + 65);
    } else if (state === 'lose') {
      ctx.fillStyle = '#ff0055';
      ctx.font = 'bold 42px monospace';
      ctx.fillText('SYSTEM OVERLOAD - CRASHED!', canvas.width / 2, canvas.height / 2 - 20);
      ctx.fillStyle = '#fff';
      ctx.font = '20px monospace';
      ctx.fillText(`SCORE: ${score}  |  SURVIVED: ${Math.floor(gameTime)}s`, canvas.width / 2, canvas.height / 2 + 25);
      ctx.fillStyle = '#00f0ff';
      ctx.fillText('PRESS SPACE OR CLICK TO RESTART', canvas.width / 2, canvas.height / 2 + 65);
    }
    ctx.textAlign = 'start';
  }

  ctx.restore();
}

function gameLoop(now: number) {
  const dt = Math.min((now - lastTime) / 1000, 0.1);
  lastTime = now;
  update(dt);
  render();
  requestAnimationFrame(gameLoop);
}

// Start immediately on load
initGame();
requestAnimationFrame(gameLoop);
