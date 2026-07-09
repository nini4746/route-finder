# Request

## Summary

Build the entire route-finder app in one pass — implement every constraint and
acceptance criterion (AC1..AC12) from `docs/product-specs/initial-seed.yaml`.
This is the project's initial implementation; there is no prior code in the
project tree beyond the harness docs (`AGENTS.md`, `ARCHITECTURE.md`,
`README.md`, `docs/`, `scripts/`).

## Scope (everything from the spec, applied at once)

1. **Maze generation**
   - DFS Backtracker algorithm, exclusively, supporting grids up to 1000x1000
     cells.
   - Generated mazes must be **perfect** (full connectivity + zero cycles).
   - Generation animates step-by-step at the speed slider's current value.

2. **Endpoints A and B**
   - Chosen randomly from non-wall cells such that A != B and
     `|Ax-Bx| + |Ay-By| >= (width + height) * 0.5`.
   - A rendered green, B rendered red.
   - Persist across algorithm runs until "New Maze" is clicked.

3. **Pathfinding algorithms (all six required)**
   - BFS, DFS, Dijkstra, A*, Greedy Best-First, Bidirectional BFS.
   - Behind a common `step()` generator interface so the main loop drives all
     six uniformly.
   - Every visited cell colors incrementally during the search; on termination
     the final A→B path is overlaid in a distinct highlight color.
   - BFS, Dijkstra, A*, and Bidirectional BFS must return identical (optimal)
     path lengths on the same maze with the same A, B. DFS and Greedy
     Best-First may return any valid A→B path.
   - Selecting a different algorithm mid-run cancels the current run, resets
     visualization colors, and starts the newly selected algorithm.

4. **Pygame UI**
   - Sidebar with: New Maze button, six algorithm buttons (1..6), speed slider
     (1..60 steps/sec, integer range, live application to both pathfinding and
     generation), Reset Colors button.
   - Keyboard shortcuts `1`..`6` map to the six algorithms in spec order
     (BFS=1, DFS=2, Dijkstra=3, A*=4, Greedy Best-First=5, Bidirectional
     BFS=6).
   - Canvas auto-scales to current window size while preserving the maze
     aspect ratio.
   - Reset Colors leaves maze + A + B intact and clears visited/path colors.

5. **Constraints**
   - Runtime dependencies: Python standard library + `pygame` only. No
     runtime network calls. macOS only.
   - Entry point launchable on macOS to render a perfect maze of size
     <= 1000x1000.

## Out of scope for v1

- Stretch goal of "at least two additional pathfinding algorithms beyond the
  required six." Skip unless trivial; focus on the required six.

## Notes for builder

- The project tree is empty of source code right now. Choose a layout
  consistent with `ARCHITECTURE.md` / `AGENTS.md`. Reasonable defaults:
  `src/route_finder/` package with `maze.py`, `algorithms/`, `ui.py`,
  `app.py`, plus a `main.py` or `__main__.py` entry point.
- For 1000x1000 grids, prefer numpy-free implementations using bytearray or
  list-of-list for the grid since the dependency budget is stdlib + pygame.
- The speed slider must throttle both maze generation and pathfinding
  uniformly (steps per second), and a change during a run must apply on the
  next step (AC9).
- Self-check at the end of `draft_v1.md` should walk AC1..AC12 explicitly.
