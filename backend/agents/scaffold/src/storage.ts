// ── Storage ───────────────────────────────────────────────────────────────────
// High-score persistence via localStorage.
// Falls back to an in-memory store when localStorage is unavailable
// (e.g. sandboxed iframes, private browsing, quota exceeded).

const _memory = new Map<string, number>();

function _safeGet(key: string): number {
  try {
    const v = localStorage.getItem(key);
    if (v === null) return 0;
    const n = Number(v);
    return isFinite(n) ? n : 0;
  } catch {
    return _memory.get(key) ?? 0;
  }
}

function _safeSet(key: string, value: number) {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    _memory.set(key, value);
  }
}

/** Get the stored high score for a key (defaults to 0). */
export function getHighScore(key = "hiscore"): number {
  return _safeGet(key);
}

/** Persist a new high score if it beats the current one. Returns the new best. */
export function saveHighScore(score: number, key = "hiscore"): number {
  const current = _safeGet(key);
  if (score > current) {
    _safeSet(key, score);
    return score;
  }
  return current;
}
