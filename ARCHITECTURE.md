# ARCHITECTURE.md

## System Map

`route-finder` is a single-process pygame desktop application. A `main` event loop polls pygame events, advances the active maze-generation or pathfinding `step()` generator according to the current speed slider value, repaints the canvas, and renders the sidebar. All state lives in a single in-memory `AppState`; there is no persistence layer, no IPC, and no network.

## Module Boundaries

```
src/route_finder/
  __main__.py        # entry point: builds AppState, runs the event loop
  app.py             # AppState dataclass + phase transitions
  maze/
    grid.py          # Cell, Maze dataclasses
    generator.py     # DFS Backtracker as a generator yielding one carve step
    invariants.py    # BFS connectivity + edge-count cycle test
    endpoints.py     # random A, B pick with manhattan distance threshold
  algorithms/
    common.py        # Algorithm protocol with step() generator interface
    bfs.py
    dfs.py
    dijkstra.py
    astar.py
    greedy_bf.py
    bi_bfs.py
  ui/
    canvas.py        # maze rendering, cell color updates, aspect-preserving scale
    sidebar.py       # New Maze, six algorithm buttons, Reset Colors
    slider.py        # speed slider [1, 60]
    shortcuts.py     # keyboard mapping for 1..6
```

**Forbidden imports**:

- `algorithms/*` may not import from `ui/*`. Pathfinders yield `Cell` coordinates only.
- `maze/*` may not import from `ui/*` or `algorithms/*`. The maze package is a pure data + invariants module.
- `ui/*` may not import from `algorithms/*` internals; it consumes the `Algorithm` protocol from `algorithms/common.py` only.
- Nothing in `src/route_finder/` may import a third-party library other than `pygame`.

## Data Storage

There is no on-disk schema for this project — `AppState` is rebuilt at every launch. The in-memory entities derived from `ontology_schema` are:

- `Cell { x: int, y: int, is_wall: bool }`
- `Maze { width: int, height: int, cells: Cell_grid, start: int_pair, end: int_pair }`
- `Algorithm { name, kind, step }` — `name` is one of `BFS DFS Dijkstra AStar GreedyBF BiBFS`; `kind` is `uninformed | informed | bidirectional`; `step` is a Python generator yielding visited coordinates.
- `PathfindingRun { maze, algorithm, visited, frontier, path, status }` — `status` is one of `idle | running | done | cancelled`.
- `AppState { maze, run, speed, phase }` — `phase` is one of `generating | idle | pathfinding`.

The `cells` grid is stored as a flat `list[Cell]` indexed by `y * width + x` to keep allocations cheap at 1000x1000.

## Invariants

1. Runtime dependencies are limited to the Python standard library plus pygame. No other third-party package may appear in the import graph.
2. No runtime network calls. The process opens zero sockets; pygame is installed via pip at install time only.
3. Supported OS is macOS only (Apple Silicon and Intel). No conditional branches for Windows or Linux.
4. Maze grid size is bounded by `1 <= width <= 1000` and `1 <= height <= 1000` cells. Inputs outside this range are rejected at the boundary.
5. Generated mazes are perfect: every non-wall cell is reachable from every other non-wall cell, and the passage graph contains zero cycles. Enforced by `maze.invariants` after every generation.
6. Maze generation uses the DFS Backtracker algorithm exclusively. No alternate generators are wired in.
7. Maze generation animates step-by-step at the speed slider's current value.
8. The six required pathfinding algorithms are BFS, DFS, Dijkstra, A*, Greedy Best-First, and Bidirectional BFS. Each is registered in `algorithms/__init__.py` keyed to a number `1..6`.
9. Endpoints A and B are chosen randomly from non-wall cells such that `A != B` and `|Ax-Bx| + |Ay-By| >= (width + height) * 0.5`. Picker retries until satisfied; for tiny mazes where the threshold is infeasible, the picker raises rather than weakening the rule silently.
10. Only one pathfinding algorithm visualizes at a time; selecting another mid-run cancels the current run, resets colors, and starts the selected one.
11. The same maze, A, and B persist across runs until New Maze is clicked.
12. The speed slider range is `[1, 60]` steps per second and changes apply on the next step of both pathfinding and maze generation animations.
13. The sidebar exposes New Maze, six algorithm buttons (shortcuts `1..6`), the speed slider, and Reset Colors.
14. The canvas auto-scales to the current window size while preserving the maze aspect ratio.

## Concurrency

Single-user, no concurrent invocations. The event loop is single-threaded; `step()` generators are advanced cooperatively between pygame event polls. Cancellation is observed at generator yield points, so there is no need for threads, locks, or async primitives.

## Error Handling

Programmer errors (invariant violations, unknown algorithm name, out-of-range maze dimensions) raise immediately with a descriptive message; the event loop logs and exits non-zero. User errors (clicking an algorithm before a maze exists, dragging the slider out of range via integer overflow) are clamped or no-op silently — the UI must never crash on input. The `reviewer` agent's correctness suite asserts both classes: invariant violations propagate, UI inputs do not.

## Team Architecture

This project's work is organized as a **team** of **2** agent(s) using the **producer_reviewer** pattern. Inter-agent artifacts flow via **files**.

### Agents

- **builder** — implements maze generation, pathfinding algorithms, pygame UI, and visualization
  - implement the DFS Backtracker maze generator with a step-by-step animation hook
  - implement six pathfinding algorithms (BFS, DFS, Dijkstra, A*, Greedy Best-First, Bidirectional BFS) behind a common step() interface
  - wire the pygame canvas, sidebar buttons, speed slider, and keyboard shortcuts 1 through 6
- **reviewer** — verifies acceptance criteria, especially algorithm correctness and perfect-maze invariants
  - confirm generated mazes are perfect via BFS connectivity plus edge-count cycle test
  - confirm BFS, Dijkstra, A*, and Bidirectional BFS return identical path lengths on the same maze and same A, B
  - confirm UI invariants (color reset on algorithm switch, live speed slider response, Reset Colors leaves maze and endpoints intact)

### Realization

The structure above is a **spec**, not running code. To materialize it as Claude Code artifacts (`.claude/agents/<name>.md`, `.claude/skills/<orchestrator>/SKILL.md`), run the downstream `/harness-build` skill, which reads `team_architecture` from `initial-seed.yaml` and renders the team + orchestrator. On other runtimes (Codex, Antigravity, Claude web), the agent roster above is the authoritative description — translate to that runtime's agent format as needed.

## Open Sections

<!-- filled as implementation lands -->

- Concrete pygame canvas pixel layout (sidebar width, padding, font choices)
- Stretch-goal pathfinder choices beyond the required six
- Test harness shape — pytest layout, fixtures for deterministic maze seeds
