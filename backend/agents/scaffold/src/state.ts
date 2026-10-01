// ── StateMachine ─────────────────────────────────────────────────────────────
// Lightweight state machine with per-state enter/exit/update/render hooks.

type _SM_UpdateFn = (dt: number) => void;
type _SM_RenderFn = (ctx: CanvasRenderingContext2D) => void;
type _SM_LifecycleFn = () => void;

interface StateHandlers {
  enter?:  _SM_LifecycleFn;
  exit?:   _SM_LifecycleFn;
  update?: _SM_UpdateFn;
  render?: _SM_RenderFn;
}

export class StateMachine {
  private _states  = new Map<string, StateHandlers>();
  private _current = "";

  register(name: string, handlers: StateHandlers) {
    this._states.set(name, handlers);
  }

  set(name: string) {
    if (!this._states.has(name)) {
      throw new Error(`StateMachine: unknown state "${name}"`);
    }
    const prev = this._states.get(this._current);
    prev?.exit?.();
    this._current = name;
    const next = this._states.get(name)!;
    next.enter?.();
  }

  get current(): string { return this._current; }

  update(dt: number) {
    this._states.get(this._current)?.update?.(dt);
  }

  render(ctx: CanvasRenderingContext2D) {
    this._states.get(this._current)?.render?.(ctx);
  }
}
