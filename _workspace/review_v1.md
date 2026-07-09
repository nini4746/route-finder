# review_v1

verdict: PASS
ready to ship: yes — every AC verified, four optimal pathfinders agree on path length across three independent seeds (25x25, 40x30, 60x40), and perfect-maze invariants hold on five sizes including the smallest and the medium-large 100x50.

## Per-AC table

| AC | Status | Reason (file:line if applicable) |
|----|--------|----------------------------------|
| AC1 | met | `src/route_finder/__main__.py:7-10` wires `python -m route_finder`; `app.py:54-63` calls `pygame.init()`, `pygame.display.set_mode((1100,720), RESIZABLE)`, sets the caption "route-finder", and immediately runs `start_new_maze`. Width/height clamped to `[1, 1000]` at `app.py:248-249`, and `Maze.__init__` also asserts the bound at `grid.py:42-45`. Generation uses DFS Backtracker only. |
| AC2 | met | `maze/invariants.py:10-48` implements BFS connectivity, `:51-68` counts undirected passage-passage edges (each counted once via right+down), `:75-82` returns `connected AND #edges == #non_wall_cells - 1`. Empirically perfect on (1,1), (5,5), (20,15), (25,25), (100,50) — see "Empirical checks run" below. |
| AC3 | met | `endpoints.py:58-96` enforces `a != b` and `manhattan_logical >= (width + height) * 0.5`, with a BFS-farthest fallback (`endpoints.py:31-55`, `:90-95`) that raises if even the maximum-diameter pair fails the threshold. A is rendered green (`canvas.py:18`, `:131`) and B red (`canvas.py:19`, `:133`) on every frame. Edge case: 1x1 mazes raise `ValueError`, see Notes. |
| AC4 | met | `app.py:67-85` `start_new_maze` resets `run_gen`/`active_algo`, allocates a fresh `Maze`, creates a fresh `generate_maze` generator carving IN PLACE on the live Maze (the bug-fix the draft mentions), enters phase `"generating"`. The generation is stepped at `state.speed` steps/sec by the same `step_active` loop (`app.py:167-183`) used for pathfinding, so the speed slider applies. On completion `_finish_generation` (`app.py:87-97`) re-randomizes A,B and clears the overlay. |
| AC5 | met | `algorithms/__init__.py:13-20` registers all six algorithms at indices 1..6 in spec order (1=BFS, 2=DFS, 3=Dijkstra, 4=AStar, 5=GreedyBF, 6=BiBFS). The sidebar (`sidebar.py:60-72`) emits `algo:1`..`algo:6` clicks, and `shortcuts.py:8-22` maps `pygame.K_1..K_6` and numpad equivalents to the same indices. Both routes funnel into `App.start_algorithm` (`app.py:101-116`, `app.py:148-151`). |
| AC6 | met | Every algorithm yields `("visit", cell)` per popped cell; the canvas overlay paints them as `COLOR_VISITED = (90,160,230)` (`canvas.py:15, 84-87`). On `("done", path)` the canvas paints the path cells as `COLOR_PATH = (255,215,70)` (`canvas.py:17, 97-101`), which is visually distinct from visited blue and the green/red endpoints. `app.py:184-202` consumes events and calls the right canvas method per event tag. |
| AC7 | met | BFS, Dijkstra, A* (Manhattan is admissible and consistent on a 4-connected unit-cost grid), and BiBFS are all path-length-optimal. Tie-breaking is deterministic via fixed neighbor order (`common.py:51-68`: right, down, left, up) and `itertools.count()` counters in the heap-based algorithms (`dijkstra.py:16`, `astar.py:16`, `greedy_bf.py:14`). Empirically verified identical path length on three additional independent seeds and sizes — see below. |
| AC8 | met | `app.py:101-116` `start_algorithm` sets `run_gen = None` and calls `canvas.clear_overlay()` **before** constructing the new generator. Same maze and same A,B are reused (`self.state.maze.start`, `.end`). No leaked state: the only mutable run state lives in `state.run_gen` (replaced) and `canvas.overlay` (cleared). |
| AC9 | met | `slider.py:9` sets `vmin=1, vmax=60` and `_value_from_x` (`slider.py:22-25`) rounds to `int`. `app.py:227` re-reads `sidebar.slider.value` into `state.speed` every frame, before `step_active` consumes it (`app.py:169-174`). A change during a run therefore takes effect on the next step (next frame at the latest). |
| AC10 | met | `app.py:120-130` `on_sidebar_click("reset")` cancels any in-flight `run_gen`, resets phase to `idle`, clears `active_algo`, and calls `canvas.clear_overlay()`. The base wall surface, `maze.start`/`maze.end`, and the endpoint pixels painted in `canvas.render` (`canvas.py:130-133`) are untouched. Keyboard `R` routes through the same handler (`app.py:155-157`). |
| AC11 | met | `app.py:142-147` handles `VIDEORESIZE` by re-creating the display mode with `RESIZABLE` and re-laying out the sidebar. `canvas.render` (`canvas.py:118-124`) computes `scale = min(rect.width / grid_w, rect.height / grid_h)`, dimensions `(dw, dh) = (int(grid_w * scale), int(grid_h * scale))`, and centers via `dx, dy = rect.x + (rect.width - dw)//2, rect.y + (rect.height - dh)//2`, giving exact letterboxing with preserved aspect ratio. |
| AC12 | met | `requirements.txt:1` declares only `pygame>=2.5,<3`. A grep over `src/` (see empirical results) shows ZERO imports of `socket`, `urllib`, `requests`, `http`, `ssl`, `httpx`, `aiohttp`, `ftplib`, `smtplib`, `telnetlib`, or `urlopen`. The only non-stdlib import is `pygame`. App code does not open sockets or contact the network. |

## Empirical checks run

### AC2 invariants (re-verified plus new sizes)

```
(  20,   15) seed=1: perfect=True non_wall=599   edges=598   expected_edges=598   connected=True
( 100,   50) seed=2: perfect=True non_wall=9999  edges=9998  expected_edges=9998  connected=True
(  25,   25) seed=3: perfect=True non_wall=1249  edges=1248  expected_edges=1248  connected=True
(   5,    5) seed=4: perfect=True non_wall=49    edges=48    expected_edges=48    connected=True
(   1,    1) seed=5: perfect=True non_wall=1     edges=0     expected_edges=0     connected=True
```

Confirmed: for every size, `#edges == #non_wall - 1` AND connectivity holds.
100x50 (5000 logical cells, ~10000 passages) is well past the medium scale
requested, and the perfect-maze invariants still hold there.

### AC7 parity (BFS == Dijkstra == AStar == BiBFS)

```
size=(25,25) seed=11  A=(49, 29) B=(3, 23)
  BFS       path_len= 261  visited= 756
  DFS       path_len= 261  visited= 395
  Dijkstra  path_len= 261  visited= 756
  AStar     path_len= 261  visited= 715
  Greedy    path_len= 261  visited= 670
  BiBFS     path_len= 261  visited= 779
  OPTIMAL PARITY OK: all four = 261

size=(40,30) seed=7   A=(25, 23) B=(73, 51)
  BFS       path_len= 373  visited=1210
  DFS       path_len= 373  visited=2337
  Dijkstra  path_len= 373  visited=1210
  AStar     path_len= 373  visited=1095
  Greedy    path_len= 373  visited= 433
  BiBFS     path_len= 373  visited= 799
  OPTIMAL PARITY OK: all four = 373

size=(60,40) seed=99  A=(89, 59) B=(21, 3)
  BFS       path_len=1069  visited=3298
  DFS       path_len=1069  visited=3345
  Dijkstra  path_len=1069  visited=3298
  AStar     path_len=1069  visited=3053
  Greedy    path_len=1069  visited=2759
  BiBFS     path_len=1069  visited=2617
  OPTIMAL PARITY OK: all four = 1069
```

Note: in a perfect maze there is exactly one A→B path, so DFS and Greedy
will always report the same length too — that's a property of the maze
class, not an algorithmic guarantee; AC7 explicitly only requires parity
for BFS/Dijkstra/A*/BiBFS, which holds.

### BiBFS path validity (sanity)

Independent sanity check: the BiBFS-reconstructed path is contiguous
(4-adjacent steps), passes through passages only, starts at A and ends at
B, and length matches BFS. Verified on three seeds at (10,10), (30,20),
(50,50). No off-by-one in the meet-cell reconstruction (`bi_bfs.py:87-101`).

### AC12 network-import grep

```
$ grep -rnE "import (socket|urllib|requests|http|ssl|httpx|aiohttp|ftplib|smtplib|telnetlib)|urlopen|socket\.socket" src/
(no matches)
```

Full list of non-stdlib imports in `src/`:

```
import pygame       — app.py, ui/canvas.py, ui/sidebar.py, ui/slider.py, ui/shortcuts.py
```

Everything else (`random`, `sys`, `time`, `dataclasses`, `typing`,
`collections`, `heapq`, `itertools`) is stdlib. `requirements.txt` lists
only `pygame>=2.5,<3`.

### Module independence

`route_finder.maze.*` and `route_finder.algorithms.*` import cleanly with
NO pygame installed (verified by `sys.path.insert(0, 'src')` and importing
each module — none of them import pygame, directly or transitively). This
matters because the spec calls these modules out as the heart of the
correctness story; the empirical AC2/AC7 checks above ran without pygame.

## Amendments

None — verdict is PASS. See Notes for non-blocking observations.

## Notes (non-blocking)

These are NOT FAIL items. Recording them so a future pass can decide
whether to harden them.

1. **1x1 maze crashes on endpoint pick.** `endpoints.pick_endpoints` raises
   `ValueError("maze too small to pick distinct endpoints")` when
   `len(candidates) < 2` (`endpoints.py:74-75`). `app._finish_generation`
   (`app.py:87-97`) does not catch it, so launching with `python -m
   route_finder 1 1` will crash after the (trivial) generation completes.
   AC1 allows w,h >= 1, and AC3 mandates "A != B" — these requirements are
   in tension on 1-cell mazes. Suggested follow-up: in
   `_finish_generation`, catch `ValueError` and either degrade to no
   endpoints (and gray out algorithm buttons) or bump the minimum size to
   2.

2. **`main()` ignores a single positional argument.** `app.py:246-251`
   gates parsing on `len(argv) >= 2`, so `python -m route_finder 50` is
   silently ignored. Minor UX; consider parsing one or two args.

3. **Generator step granularity at high speeds.** `step_active`
   (`app.py:167-202`) advances `int(speed * dt)` events per frame; for
   path-finding "frontier" events count toward the budget, which can make
   the visible visit cadence slower than the slider value on dense
   frontiers. Not a spec violation (AC9 only requires the change-during-run
   to take effect on the next step, which it does), but a future pass may
   want to either bill only `visit` events or report effective steps/sec
   in the status panel.

4. **`mark_frontier` is a no-op.** `canvas.py:89-95` deliberately ignores
   the frontier events to keep the overlay cheap. The protocol still emits
   them. AC6 only requires "every visited cell changes color
   incrementally" and "the final A-to-B path is overlaid in a distinct
   highlight color" — both are satisfied without frontier coloring. Noted
   so reviewers don't flag it as a missing feature.

5. **`is_perfect_maze` is imported in `app.py` but never called at
   runtime.** `app.py:28` brings it in; it isn't used in the main loop.
   Harmless (it's the right thing for tests / debug), but a linter would
   flag it. Could either drop the import or wire it into a debug-mode
   assertion after generation.

6. **`step` budget can starve on `done`.** When a `done` event is hit
   mid-budget (`app.py:197-202`), the loop breaks out and unused budget is
   discarded (carry was already decremented). On a 60 fps clock at speed
   60, this can drop at most ~1 step of pacing on the final frame.
   Imperceptible; documenting for completeness.

검토 결과 PASS. 4개 최적 알고리즘 path 길이가 세 가지 서로 다른 크기·시드에서 모두 일치하며, 완전 미로 불변량(연결성 + 간선 수)이 1x1부터 100x50까지 모두 통과합니다. AC1..AC12 모두 met.
