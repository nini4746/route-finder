# AGENTS.md

## Read Order

- `docs/product-specs/initial-seed.yaml` — canonical spec (do not hand-edit; rerender via `/harness-spec --rerender`)
- `ARCHITECTURE.md` — runtime topology, module boundaries, team architecture
- `docs/design-docs/core-beliefs.md` — invariants stated as beliefs, one per constraint
- `docs/references/development-rules.md` — coding rules, dependencies, what runtime code may not do
- `docs/generated/consistency-manifest.md` — canonical tokens shared across the documents
- `docs/generated/interview-transcript.md` — how this spec was derived (read-only audit trail)

## Mission

Deliver a single macOS pygame program that generates random perfect mazes (DFS Backtracker, up to 1000x1000 cells) with step-by-step animation, then lets the user pick one of six pathfinding algorithms at a time and watch it find a path from a random point A to a random point B while every visited cell changes color.

## Cold-Start Contract

### Goal

A macOS pygame desktop program that generates random perfect mazes up to 1000x1000 cells with the DFS Backtracker algorithm and then visualizes six pathfinding algorithms one at a time finding a path from a randomly chosen point A to point B, coloring every visited cell as the search progresses.

### Constraints

- runtime dependencies are limited to the Python standard library plus pygame
- no runtime network calls; pygame is installed via pip at install time only
- supported OS is macOS only (Apple Silicon and Intel)
- maze grid size is bounded by 1 <= width <= 1000 and 1 <= height <= 1000 cells
- generated mazes are perfect (every non-wall cell is reachable from every other non-wall cell, and the passage graph contains zero cycles)
- maze generation uses the DFS Backtracker algorithm exclusively
- maze generation animates step-by-step at the speed configured by the speed slider
- the six required pathfinding algorithms are BFS, DFS, Dijkstra, A*, Greedy Best-First, and Bidirectional BFS
- stretch goal is to implement at least two additional pathfinding algorithms beyond the required six
- endpoints A and B are chosen randomly from non-wall cells such that A != B and |Ax-Bx| + |Ay-By| >= (width + height) * 0.5
- only one pathfinding algorithm visualizes at a time; selecting another algorithm cancels the current run, resets visualization colors, and starts the selected algorithm
- the same maze and the same A and B persist across algorithm runs until the user clicks New Maze
- the speed slider range is 1 to 60 steps per second and applies live to both pathfinding and maze generation animations
- the sidebar exposes a New Maze button, six algorithm buttons mapped to keyboard shortcuts 1 through 6, a speed slider, and a Reset Colors button
- the canvas auto-scales to the current window size while preserving the maze aspect ratio

### Acceptance Criteria

- AC1 launching the entry point on macOS opens a pygame window and renders a perfect maze of size <= 1000x1000 cells.
- AC2 the generated maze passes a connectivity test (BFS from any non-wall cell reaches all other non-wall cells) and a cycle test (the passage graph has exactly non_wall_cell_count - 1 edges).
- AC3 on every maze generation, A and B are distinct non-wall cells satisfying |Ax-Bx| + |Ay-By| >= (width + height) * 0.5; A is rendered green and B is rendered red.
- AC4 clicking New Maze regenerates the maze with DFS Backtracker, animates the generation at the current speed slider value, then re-randomizes A and B and clears all visualization colors.
- AC5 the six algorithms BFS, DFS, Dijkstra, A*, Greedy Best-First, Bidirectional BFS are each selectable via a sidebar button and via keyboard shortcuts 1 through 6 respectively.
- AC6 during a pathfinding run, every visited cell changes color incrementally, and on termination the final A to B path is overlaid in a distinct highlight color.
- AC7 on the same maze with the same A and B, BFS, Dijkstra, A*, and Bidirectional BFS report identical path lengths (the optimum); DFS and Greedy Best-First report any valid A to B path.
- AC8 selecting a different algorithm during a run cancels the current run, resets visualization colors, and starts the newly selected algorithm immediately.
- AC9 the speed slider exposes the integer range [1, 60] in steps per second, and a change during a run takes effect on the next step.
- AC10 clicking Reset Colors leaves the maze, A, and B intact and clears visited and path colors.
- AC11 resizing the window auto-scales the canvas to fit the new window while preserving the maze aspect ratio.
- AC12 pip list inside a fresh venv after install shows only pygame and Python standard-library packages; the running program makes zero outbound network requests.

### Ontology

- **Cell**: { x: int, y: int, is_wall: bool }
- **Maze**: { width: int, height: int, cells: Cell_grid, start: int_pair, end: int_pair }
- **Algorithm**: { name: enum_BFS_DFS_Dijkstra_AStar_GreedyBF_BiBFS, kind: enum_uninformed_informed_bidirectional, step: generator }
- **PathfindingRun**: { maze: Maze, algorithm: Algorithm, visited: set_of_int_pair, frontier: queue_or_heap, path: list_of_int_pair, status: enum_idle_running_done_cancelled }
- **AppState**: { maze: Maze, run: PathfindingRun_or_None, speed: int, phase: enum_generating_idle_pathfinding }

## Done-When

- AC1 launching the entry point on macOS opens a pygame window and renders a perfect maze of size <= 1000x1000 cells.
- AC2 the generated maze passes a connectivity test (BFS from any non-wall cell reaches all other non-wall cells) and a cycle test (the passage graph has exactly non_wall_cell_count - 1 edges).
- AC3 on every maze generation, A and B are distinct non-wall cells satisfying |Ax-Bx| + |Ay-By| >= (width + height) * 0.5; A is rendered green and B is rendered red.
- AC4 clicking New Maze regenerates the maze with DFS Backtracker, animates the generation at the current speed slider value, then re-randomizes A and B and clears all visualization colors.
- AC5 the six algorithms BFS, DFS, Dijkstra, A*, Greedy Best-First, Bidirectional BFS are each selectable via a sidebar button and via keyboard shortcuts 1 through 6 respectively.
- AC6 during a pathfinding run, every visited cell changes color incrementally, and on termination the final A to B path is overlaid in a distinct highlight color.
- AC7 on the same maze with the same A and B, BFS, Dijkstra, A*, and Bidirectional BFS report identical path lengths (the optimum); DFS and Greedy Best-First report any valid A to B path.
- AC8 selecting a different algorithm during a run cancels the current run, resets visualization colors, and starts the newly selected algorithm immediately.
- AC9 the speed slider exposes the integer range [1, 60] in steps per second, and a change during a run takes effect on the next step.
- AC10 clicking Reset Colors leaves the maze, A, and B intact and clears visited and path colors.
- AC11 resizing the window auto-scales the canvas to fit the new window while preserving the maze aspect ratio.
- AC12 pip list inside a fresh venv after install shows only pygame and Python standard-library packages; the running program makes zero outbound network requests.

## Repo Map

```
route-finder/
  AGENTS.md
  ARCHITECTURE.md
  README.md
  src/                       # implementation lands here (created by builder)
    route_finder/
      __init__.py
      __main__.py            # entry point
      maze/                  # generator (DFS Backtracker)
      algorithms/            # six pathfinders behind a common step() API
      ui/                    # pygame canvas, sidebar, slider, shortcuts
      app.py                 # AppState wiring
  tests/                     # reviewer's correctness suite (created by reviewer)
  docs/
    design-docs/             # core-beliefs and lazy design docs
    exec-plans/              # active / completed work plans, tech-debt tracker
    generated/               # consistency-manifest, interview-transcript, .transcript-chain
    product-specs/           # initial-seed.yaml (canonical)
    references/              # development-rules, stack-reference-llms.txt
  scripts/
    init.sh                  # mkdir -p skeleton (idempotent)
```

## Rules for Agents

- Honor every Cold-Start Contract constraint above. The most load-bearing ones:
  - **Pure stdlib + pygame only.** No `requests`, `numpy`, `pillow`, or any other third-party library. If a feature seems to need one, restate the feature so it can be done in stdlib.
  - **No runtime network.** pygame installation happens at install time; the running program must make zero outbound network requests.
  - **macOS only.** Do not add Windows or Linux conditional code paths.
  - **Maze grid bounded by 1000x1000.** Validate user-driven size inputs at the boundary.
  - **Perfect maze invariant.** Every regeneration must pass the BFS connectivity test and the `edges == non_wall_cell_count - 1` cycle test before the canvas paints. This is the `reviewer` agent's primary check.
  - **One algorithm at a time.** Selecting another mid-run cancels, resets colors, starts the new one — no overlap, no leftover color.
- See `docs/references/development-rules.md` for the full rule set (testing, errors, dependencies, what runtime code may not do).

## Updating This Document

`AGENTS.md` is regenerated by `/harness-spec --rerender` from `docs/product-specs/initial-seed.yaml`. Hand-edits will be overwritten. To change project scope or constraints, edit `initial-seed.yaml` and rerender.
