# Development Rules

Concrete rules for writing, reviewing, and shipping code in `route-finder`. Derived from `initial-seed.yaml > constraints` and `metadata.tech_stack`. Updated by `/harness-spec --rerender`.

## Language and tooling

- **Python 3** (any recent macOS-supplied 3.10+ is fine; standardize on `python3` from the active venv).
- **pygame** as the only third-party dependency.
- Format with `python3 -m black` (dev-time only — not a runtime dependency). Linting is best-effort; correctness via tests matters more.
- A single venv at `.venv/` is the canonical environment. CI is not configured; run tests locally.

## Module layout

- All runtime code lives under `src/route_finder/`. No package outside `src/route_finder/` is part of the shipped surface.
- Sub-packages — `maze/`, `algorithms/`, `ui/` — must respect the forbidden-imports rules in `ARCHITECTURE.md`:
  - `algorithms/*` does not import from `ui/*`.
  - `maze/*` does not import from `ui/*` or `algorithms/*`.
  - `ui/*` does not reach into `algorithms/` internals — only the `Algorithm` protocol in `algorithms/common.py`.
- Tests live under `tests/`, mirror the module layout, and import from `src/route_finder/` only.

## Testing

- Use `pytest`. Fixtures seed deterministic mazes via `random.seed(...)`.
- **Perfect-maze invariant test** is the highest-priority test in the repo — every generated maze must pass BFS connectivity and `edges == non_wall_cell_count - 1`.
- **Optimal-path equivalence test** verifies AC7: on a battery of seeded mazes, BFS / Dijkstra / A* / Bidirectional BFS all return identical path lengths.
- **UI invariant tests** for AC8 (algorithm switch cancels + resets), AC9 (slider live-applies), AC10 (Reset Colors preserves maze and endpoints) — driven by simulating pygame events against a headless surface where feasible.

## Errors

- **Programmer errors** raise immediately with a descriptive message: invariant violations, unknown algorithm name, out-of-range maze dimensions. The event loop logs and exits non-zero.
- **User errors** are clamped or no-op silently — clicking an algorithm before a maze exists, slider drag attempting out-of-range, resizing to zero. The UI must never crash on input.
- Do not introduce a general-purpose retry / logging framework. Use `print(..., file=sys.stderr)` for the few error paths.

## Dependencies

- **Allowed runtime imports**: anything in the Python 3 standard library, plus `pygame`.
- **Forbidden runtime imports**: `numpy`, `pillow`, `requests`, `httpx`, any networking library, any data-science library, any GUI library other than pygame.
- **Dev-time only** is acceptable for `pytest` and `black`. They never appear in `src/route_finder/` imports.

## What runtime code may NOT do

Derived directly from `constraints`:

- **No third-party imports beyond pygame.** Every import in `src/route_finder/` must resolve to either the standard library or `pygame`.
- **No outbound network calls.** No `socket`, `urllib`, `http.client`, `ssl` outside of standard-library usage that is not making a network request. The default install workflow uses pip at install time only.
- **No Windows or Linux conditional code paths.** Do not branch on `sys.platform`; macOS-specific behavior is allowed implicitly.
- **No maze sizes outside `[1, 1000]` for either dimension.** Validate at the boundary (entry point or UI input handler).
- **No non-DFS-Backtracker maze generators.** Adding Prim's, Kruskal's, etc., is out of scope until the YAML constraint changes.
- **No simultaneous algorithm runs.** Selecting a new algorithm always cancels the previous run and resets visualization colors before starting.
- **No persistence.** AppState is rebuilt at every launch; do not write files outside `docs/` and `tests/` fixtures.

## Reviewing changes

The `reviewer` agent (see `ARCHITECTURE.md > Team Architecture`) owns AC verification. When reviewing a PR or diff:

1. Run `pytest tests/maze/test_invariants.py` — perfect-maze test must pass on every seeded grid.
2. Run `pytest tests/algorithms/test_optimal_equivalence.py` — BFS / Dijkstra / A* / Bidirectional BFS must agree on path length.
3. Visual smoke-check: launch `python -m route_finder`, click `New Maze`, run each of `1..6` shortcuts, then `Reset Colors`. Confirm AC6, AC8, AC9, AC10 by eye.
4. `pip list` inside the venv: only `pygame` plus stdlib should appear.
5. Reject the change if it adds a third-party dependency, a network call, a non-macOS branch, or weakens the perfect-maze invariant.
