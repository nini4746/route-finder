# draft_v1: initial route-finder implementation

This draft is the first end-to-end implementation of the route-finder pygame
app described in `docs/product-specs/initial-seed.yaml`. It covers maze
generation (DFS Backtracker), six pathfinding algorithms behind a common
`step()` generator interface, the pygame UI (canvas, sidebar, slider,
shortcuts), and the main app loop / state machine.

A code-review-pass during this draft caught one wiring bug: `app.start_new_maze`
was creating a "stub" Maze for the UI separate from the Maze that the
generator was carving, so the canvas-side maze never received the wall
updates. The fix was to allow `generate_maze` to carve IN PLACE on a
caller-supplied Maze, and have the app pass the live UI Maze into the
generator. See the file-by-file diffs below.

## Change summary

- `src/route_finder/__init__.py` -> package marker.
- `src/route_finder/__main__.py` -> entry point for `python -m route_finder`.
- `src/route_finder/app.py` -> main loop, AppState, phase machine,
  cancel-on-switch behavior, Reset Colors / New Maze, frame pacing.
- `src/route_finder/maze/grid.py` -> Maze data structure on a (2W+1)x(2H+1)
  odd grid with a bytearray for walls; helpers for indexing, neighbors4,
  cell-to-grid conversion.
- `src/route_finder/maze/generator.py` -> DFS Backtracker generator that
  yields one carve event per step and carves the maze IN PLACE on a
  caller-supplied Maze (so the UI shares the same Maze instance).
- `src/route_finder/maze/endpoints.py` -> picks A,B from logical-cell
  positions satisfying `|Ax-Bx| + |Ay-By| >= (width + height) * 0.5`, with a
  BFS-farthest fallback.
- `src/route_finder/maze/invariants.py` -> `connectivity_ok` (BFS), `edge_count`,
  `is_perfect_maze` (connected AND #edges == #non_wall_cells - 1).
- `src/route_finder/maze/__init__.py` -> re-exports the maze API.
- `src/route_finder/algorithms/common.py` -> `Algorithm` dataclass,
  shared `neighbors`, `manhattan`, `reconstruct`, `build_path_event`,
  and the documented event protocol.
- `src/route_finder/algorithms/bfs.py` -> BFS (optimal).
- `src/route_finder/algorithms/dfs.py` -> DFS (any valid path).
- `src/route_finder/algorithms/dijkstra.py` -> Dijkstra (optimal on unit grid).
- `src/route_finder/algorithms/astar.py` -> A* with Manhattan heuristic
  (optimal).
- `src/route_finder/algorithms/greedy_bf.py` -> Greedy Best-First with
  Manhattan (any valid path).
- `src/route_finder/algorithms/bi_bfs.py` -> Bidirectional BFS (optimal).
- `src/route_finder/algorithms/__init__.py` -> exports `REGISTRY` with the
  spec ordering (1=BFS, 2=DFS, 3=Dijkstra, 4=A*, 5=GreedyBF, 6=BiBFS).
- `src/route_finder/ui/canvas.py` -> base + overlay surfaces, incremental
  carve / visit / path painting, aspect-preserving scale on render.
- `src/route_finder/ui/sidebar.py` -> sidebar with New Maze, six algorithm
  buttons, the speed slider, and Reset Colors. Recomputes layout on resize.
- `src/route_finder/ui/slider.py` -> integer [1, 60] slider with drag.
- `src/route_finder/ui/shortcuts.py` -> keys 1..6 (and numpad 1..6) -> algo
  index per spec order.
- `src/route_finder/ui/__init__.py` -> UI re-exports.
- `requirements.txt` -> `pygame>=2.5,<3` (only runtime dependency).

## Code

### `requirements.txt`
```
pygame>=2.5,<3
```

### `src/route_finder/__init__.py`
```python
"""route_finder: pygame maze and pathfinding visualizer."""

__all__ = ["app"]
```

### `src/route_finder/__main__.py`
```python
"""Entry point: ``python -m route_finder [width height]``."""

from __future__ import annotations

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

### `src/route_finder/maze/__init__.py`
```python
"""Maze data, DFS Backtracker generator, invariants, endpoint picker."""

from .grid import Maze, Cell
from .generator import generate_maze
from .invariants import is_perfect_maze, connectivity_ok, edge_count
from .endpoints import pick_endpoints

__all__ = [
    "Maze",
    "Cell",
    "generate_maze",
    "is_perfect_maze",
    "connectivity_ok",
    "edge_count",
    "pick_endpoints",
]
```

### `src/route_finder/maze/grid.py`
```python
"""Maze data structures.

The maze is stored on an "odd-grid" representation: for a logical W x H cell
grid, the renderable grid is (2W + 1) x (2H + 1). Cells sit at odd
coordinates (2i + 1, 2j + 1) and walls live at even coordinates. This makes
the DFS Backtracker straightforward and rendering trivial.

Wall storage uses a bytearray indexed by ``y * grid_w + x`` where each byte is
1 for wall and 0 for passage. For 1000x1000 logical cells the grid is
2001x2001 = ~4M bytes, which is fine on macOS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator


@dataclass(frozen=True)
class Cell:
    """A single renderable grid cell (logical cell OR wall slot)."""

    x: int
    y: int
    is_wall: bool


class Maze:
    """A perfect maze on an odd grid.

    ``width`` and ``height`` are the LOGICAL cell counts (1..1000).
    ``grid_w = 2 * width + 1`` and ``grid_h = 2 * height + 1`` are the renderable
    grid dimensions. ``walls`` is a flat bytearray (1 = wall, 0 = passage).

    Endpoints ``start`` and ``end`` are stored in RENDERED grid coordinates so
    that pathfinders can walk neighbors uniformly.
    """

    __slots__ = ("width", "height", "grid_w", "grid_h", "walls", "start", "end")

    def __init__(self, width: int, height: int):
        if not (1 <= width <= 1000 and 1 <= height <= 1000):
            raise ValueError(
                f"maze size must satisfy 1 <= w,h <= 1000 (got {width}x{height})"
            )
        self.width = width
        self.height = height
        self.grid_w = 2 * width + 1
        self.grid_h = 2 * height + 1
        # All walls initially.
        self.walls = bytearray([1]) * (self.grid_w * self.grid_h)
        self.start: tuple[int, int] | None = None
        self.end: tuple[int, int] | None = None

    # ---------- indexing helpers ----------

    def idx(self, x: int, y: int) -> int:
        return y * self.grid_w + x

    def is_wall(self, x: int, y: int) -> bool:
        if not (0 <= x < self.grid_w and 0 <= y < self.grid_h):
            return True
        return self.walls[y * self.grid_w + x] == 1

    def set_wall(self, x: int, y: int, wall: bool) -> None:
        self.walls[y * self.grid_w + x] = 1 if wall else 0

    def cell_to_grid(self, cx: int, cy: int) -> tuple[int, int]:
        """Convert a logical cell coordinate to its rendered grid coordinate."""
        return (2 * cx + 1, 2 * cy + 1)

    # ---------- iteration helpers ----------

    def non_wall_cells(self) -> Iterator[tuple[int, int]]:
        gw = self.grid_w
        walls = self.walls
        for y in range(self.grid_h):
            base = y * gw
            for x in range(gw):
                if walls[base + x] == 0:
                    yield (x, y)

    def neighbors4(self, x: int, y: int) -> Iterable[tuple[int, int]]:
        """4-connected neighbors in the rendered grid that are passages."""
        if x > 0 and self.walls[y * self.grid_w + (x - 1)] == 0:
            yield (x - 1, y)
        if x + 1 < self.grid_w and self.walls[y * self.grid_w + (x + 1)] == 0:
            yield (x + 1, y)
        if y > 0 and self.walls[(y - 1) * self.grid_w + x] == 0:
            yield (x, y - 1)
        if y + 1 < self.grid_h and self.walls[(y + 1) * self.grid_w + x] == 0:
            yield (x, y + 1)
```

### `src/route_finder/maze/generator.py`
```python
"""DFS Backtracker maze generator.

Yields one "carve" event per step so the UI can pace the animation via the
speed slider. Each event is a tuple of grid coordinates that were just turned
into passages (typically two cells: the new cell and the wall between it and
the previous cell). On completion, the generator returns the fully carved
Maze via the StopIteration value.

The generator operates IN PLACE on the supplied ``maze`` object so the UI can
share the same Maze instance for incremental rendering. If no ``maze`` is
supplied, a fresh ``Maze(width, height)`` is allocated.
"""

from __future__ import annotations

import random
from typing import Generator

from .grid import Maze


def generate_maze(
    width: int,
    height: int,
    rng: random.Random | None = None,
    maze: Maze | None = None,
) -> Generator[tuple[tuple[int, int], ...], None, Maze]:
    """DFS Backtracker on a logical width x height cell grid.

    Yields tuples of rendered-grid coordinates that just became passages so
    the renderer can repaint just those cells. Returns the finished Maze.
    If ``maze`` is supplied it is carved in place; otherwise a new Maze is
    allocated.
    """
    if rng is None:
        rng = random.Random()

    if maze is None:
        maze = Maze(width, height)
    else:
        if maze.width != width or maze.height != height:
            raise ValueError(
                "supplied maze size does not match (width, height)"
            )
        # Reset to all-walls in case the caller is reusing a maze object.
        for i in range(len(maze.walls)):
            maze.walls[i] = 1
    gw = maze.grid_w
    walls = maze.walls

    visited = bytearray(width * height)

    def cell_idx(cx: int, cy: int) -> int:
        return cy * width + cx

    start_cx = rng.randrange(width)
    start_cy = rng.randrange(height)
    sx, sy = maze.cell_to_grid(start_cx, start_cy)
    walls[sy * gw + sx] = 0
    visited[cell_idx(start_cx, start_cy)] = 1
    yield ((sx, sy),)

    # Explicit stack of cell coordinates.
    stack: list[tuple[int, int]] = [(start_cx, start_cy)]

    # 4 directions in cell space: (dx, dy)
    DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

    while stack:
        cx, cy = stack[-1]
        # Gather unvisited cell-neighbors.
        candidates: list[tuple[int, int]] = []
        for dx, dy in DIRS:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height and not visited[cell_idx(nx, ny)]:
                candidates.append((nx, ny))
        if not candidates:
            stack.pop()
            continue
        nx, ny = candidates[rng.randrange(len(candidates))]
        # Knock down the wall between (cx,cy) and (nx,ny) in rendered coords.
        gx_from, gy_from = maze.cell_to_grid(cx, cy)
        gx_to, gy_to = maze.cell_to_grid(nx, ny)
        wx = (gx_from + gx_to) // 2
        wy = (gy_from + gy_to) // 2
        walls[wy * gw + wx] = 0
        walls[gy_to * gw + gx_to] = 0
        visited[cell_idx(nx, ny)] = 1
        stack.append((nx, ny))
        yield ((wx, wy), (gx_to, gy_to))

    return maze
```

### `src/route_finder/maze/invariants.py`
```python
"""Maze perfect-maze invariants: connectivity + acyclicity (edge count)."""

from __future__ import annotations

from collections import deque

from .grid import Maze


def connectivity_ok(maze: Maze) -> bool:
    """BFS from the first non-wall cell. Returns True iff every non-wall
    cell is visited."""
    gw = maze.grid_w
    gh = maze.grid_h
    walls = maze.walls
    total_passages = 0
    start: tuple[int, int] | None = None
    for y in range(gh):
        base = y * gw
        for x in range(gw):
            if walls[base + x] == 0:
                total_passages += 1
                if start is None:
                    start = (x, y)
    if start is None:
        return True

    seen = bytearray(gw * gh)
    seen[start[1] * gw + start[0]] = 1
    q = deque([start])
    count = 0
    while q:
        x, y = q.popleft()
        count += 1
        # 4 neighbors
        if x > 0 and walls[y * gw + (x - 1)] == 0 and not seen[y * gw + (x - 1)]:
            seen[y * gw + (x - 1)] = 1
            q.append((x - 1, y))
        if x + 1 < gw and walls[y * gw + (x + 1)] == 0 and not seen[y * gw + (x + 1)]:
            seen[y * gw + (x + 1)] = 1
            q.append((x + 1, y))
        if y > 0 and walls[(y - 1) * gw + x] == 0 and not seen[(y - 1) * gw + x]:
            seen[(y - 1) * gw + x] = 1
            q.append((x, y - 1))
        if y + 1 < gh and walls[(y + 1) * gw + x] == 0 and not seen[(y + 1) * gw + x]:
            seen[(y + 1) * gw + x] = 1
            q.append((x, y + 1))
    return count == total_passages


def edge_count(maze: Maze) -> int:
    """Count passage-passage edges in the rendered grid (each counted once)."""
    gw = maze.grid_w
    gh = maze.grid_h
    walls = maze.walls
    edges = 0
    for y in range(gh):
        base = y * gw
        for x in range(gw):
            if walls[base + x] == 1:
                continue
            # right neighbor
            if x + 1 < gw and walls[base + x + 1] == 0:
                edges += 1
            # down neighbor
            if y + 1 < gh and walls[(y + 1) * gw + x] == 0:
                edges += 1
    return edges


def non_wall_count(maze: Maze) -> int:
    return sum(1 for b in maze.walls if b == 0)


def is_perfect_maze(maze: Maze) -> bool:
    """Perfect = connected AND #edges == #non_wall_cells - 1."""
    n = non_wall_count(maze)
    if n == 0:
        return True
    if not connectivity_ok(maze):
        return False
    return edge_count(maze) == n - 1
```

### `src/route_finder/maze/endpoints.py`
```python
"""Endpoint picker.

A and B are non-wall cells in the rendered grid satisfying
``|Ax - Bx| + |Ay - By| >= (width + height) * 0.5`` where width/height are
the LOGICAL cell counts. Manhattan distance is measured in rendered-grid
units (which doubles distances vs. logical cells), so the threshold is also
expressed in rendered-grid units below.
"""

from __future__ import annotations

import random
from collections import deque

from .grid import Maze


def _logical_passage_cells(maze: Maze) -> list[tuple[int, int]]:
    """Return all rendered-grid coords that correspond to logical cells
    (i.e., odd, odd) and are passages. By DFS Backtracker construction, every
    such coordinate is a passage."""
    cells = []
    for cy in range(maze.height):
        for cx in range(maze.width):
            gx, gy = maze.cell_to_grid(cx, cy)
            if maze.walls[gy * maze.grid_w + gx] == 0:
                cells.append((gx, gy))
    return cells


def _bfs_farthest(maze: Maze, src: tuple[int, int]) -> tuple[int, int]:
    """Return the non-wall cell farthest (by BFS) from ``src``."""
    gw = maze.grid_w
    walls = maze.walls
    seen = {src}
    q = deque([src])
    last = src
    while q:
        x, y = q.popleft()
        last = (x, y)
        for nx, ny in (
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
        ):
            if (
                0 <= nx < gw
                and 0 <= ny < maze.grid_h
                and walls[ny * gw + nx] == 0
                and (nx, ny) not in seen
            ):
                seen.add((nx, ny))
                q.append((nx, ny))
    return last


def pick_endpoints(
    maze: Maze, rng: random.Random | None = None, max_tries: int = 1000
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Pick A, B in rendered-grid coordinates satisfying the spec.

    Threshold is ``(width + height) * 0.5`` in logical-cell Manhattan units.
    Since the rendered-grid Manhattan distance is twice the logical distance,
    we compare ``(rendered_manhattan / 2) >= (width + height) * 0.5``.
    """
    if rng is None:
        rng = random.Random()

    threshold = (maze.width + maze.height) * 0.5
    candidates = _logical_passage_cells(maze)
    if len(candidates) < 2:
        raise ValueError("maze too small to pick distinct endpoints")

    def manhattan_logical(a: tuple[int, int], b: tuple[int, int]) -> float:
        # rendered grid distance / 2 == logical distance
        return (abs(a[0] - b[0]) + abs(a[1] - b[1])) / 2.0

    a = candidates[rng.randrange(len(candidates))]
    for _ in range(max_tries):
        b = candidates[rng.randrange(len(candidates))]
        if b != a and manhattan_logical(a, b) >= threshold:
            return a, b

    # Fallback: farthest reachable cell from A (guaranteed maximal for a
    # connected perfect maze). If even that fails the threshold, the maze is
    # genuinely too small; raise rather than silently weakening.
    b = _bfs_farthest(maze, a)
    if b == a or manhattan_logical(a, b) < threshold:
        raise ValueError(
            f"maze too small for endpoint constraint: threshold={threshold}, "
            f"best={manhattan_logical(a, b)}"
        )
    return a, b
```

### `src/route_finder/algorithms/__init__.py`
```python
"""Pathfinding algorithms behind a common step() generator interface."""

from .common import Algorithm, Event, build_path_event
from .bfs import bfs
from .dfs import dfs
from .dijkstra import dijkstra
from .astar import astar
from .greedy_bf import greedy_best_first
from .bi_bfs import bidirectional_bfs

# Number key -> Algorithm. The spec mandates this exact ordering:
# 1=BFS 2=DFS 3=Dijkstra 4=A* 5=GreedyBF 6=BiBFS.
REGISTRY: dict[int, Algorithm] = {
    1: Algorithm(name="BFS", kind="uninformed", step=bfs),
    2: Algorithm(name="DFS", kind="uninformed", step=dfs),
    3: Algorithm(name="Dijkstra", kind="uninformed", step=dijkstra),
    4: Algorithm(name="AStar", kind="informed", step=astar),
    5: Algorithm(name="GreedyBF", kind="informed", step=greedy_best_first),
    6: Algorithm(name="BiBFS", kind="bidirectional", step=bidirectional_bfs),
}

__all__ = [
    "Algorithm",
    "Event",
    "REGISTRY",
    "build_path_event",
    "bfs",
    "dfs",
    "dijkstra",
    "astar",
    "greedy_best_first",
    "bidirectional_bfs",
]
```

### `src/route_finder/algorithms/common.py`
```python
"""Shared algorithm interface.

Every pathfinder is a function ``f(maze, start, end) -> Generator[Event, None, None]``
that yields one event per algorithm step. Events are tuples:

  ("visit", (x, y))            -- a cell was just popped from the frontier
  ("frontier", (x, y))         -- a cell was just added to the frontier (informational)
  ("done", [path_cells])       -- terminal event; reconstructed A->B path, inclusive

The UI consumes one event per frame at a rate proportional to the speed slider.
Bidirectional BFS emits ``("visit", ...)`` events from both fronts and a
final ``("done", path)`` event when the two fronts meet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generator, Iterable

Event = tuple  # ("visit", (x,y)) | ("frontier", (x,y)) | ("done", list[(x,y)])


@dataclass(frozen=True)
class Algorithm:
    name: str
    kind: str  # "uninformed" | "informed" | "bidirectional"
    step: Callable[
        ["object", tuple[int, int], tuple[int, int]],
        Generator[Event, None, None],
    ]


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def reconstruct(parents: dict, end: tuple[int, int]) -> list[tuple[int, int]]:
    path = [end]
    cur = end
    while parents.get(cur) is not None:
        cur = parents[cur]
        path.append(cur)
    path.reverse()
    return path


def build_path_event(path: list[tuple[int, int]]) -> Event:
    return ("done", path)


def neighbors(maze, x: int, y: int) -> Iterable[tuple[int, int]]:
    """4-connected passages around (x, y).

    Deterministic order (right, down, left, up) so that algorithms whose
    optimality requires only consistency (DFS, Greedy) are reproducible per
    seeded RNG, but the order itself is fixed for tie-breaking comparisons.
    """
    gw = maze.grid_w
    gh = maze.grid_h
    walls = maze.walls
    if x + 1 < gw and walls[y * gw + (x + 1)] == 0:
        yield (x + 1, y)
    if y + 1 < gh and walls[(y + 1) * gw + x] == 0:
        yield (x, y + 1)
    if x > 0 and walls[y * gw + (x - 1)] == 0:
        yield (x - 1, y)
    if y > 0 and walls[(y - 1) * gw + x] == 0:
        yield (x, y - 1)
```

### `src/route_finder/algorithms/bfs.py`
```python
"""Breadth-first search. Optimal on uniform grids."""

from __future__ import annotations

from collections import deque
from typing import Generator

from .common import Event, neighbors, reconstruct, build_path_event


def bfs(maze, start, end) -> Generator[Event, None, None]:
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        yield ("visit", cur)
        if cur == end:
            yield build_path_event(reconstruct(parents, end))
            return
        for nb in neighbors(maze, cur[0], cur[1]):
            if nb not in parents:
                parents[nb] = cur
                q.append(nb)
                yield ("frontier", nb)
    # Unreachable; for a perfect maze this should not happen.
    yield build_path_event([])
```

### `src/route_finder/algorithms/dfs.py`
```python
"""Depth-first search. Returns any valid path (not necessarily optimal)."""

from __future__ import annotations

from typing import Generator

from .common import Event, neighbors, reconstruct, build_path_event


def dfs(maze, start, end) -> Generator[Event, None, None]:
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    stack = [start]
    while stack:
        cur = stack.pop()
        yield ("visit", cur)
        if cur == end:
            yield build_path_event(reconstruct(parents, end))
            return
        for nb in neighbors(maze, cur[0], cur[1]):
            if nb not in parents:
                parents[nb] = cur
                stack.append(nb)
                yield ("frontier", nb)
    yield build_path_event([])
```

### `src/route_finder/algorithms/dijkstra.py`
```python
"""Dijkstra. On all-unit-weight grids this is BFS with a heap; both yield
the optimal path length."""

from __future__ import annotations

import heapq
import itertools
from typing import Generator

from .common import Event, neighbors, reconstruct, build_path_event


def dijkstra(maze, start, end) -> Generator[Event, None, None]:
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    dist: dict[tuple[int, int], int] = {start: 0}
    counter = itertools.count()
    heap: list[tuple[int, int, tuple[int, int]]] = [(0, next(counter), start)]
    closed: set[tuple[int, int]] = set()
    while heap:
        d, _, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        closed.add(cur)
        yield ("visit", cur)
        if cur == end:
            yield build_path_event(reconstruct(parents, end))
            return
        for nb in neighbors(maze, cur[0], cur[1]):
            nd = d + 1
            if nd < dist.get(nb, 10**18):
                dist[nb] = nd
                parents[nb] = cur
                heapq.heappush(heap, (nd, next(counter), nb))
                yield ("frontier", nb)
    yield build_path_event([])
```

### `src/route_finder/algorithms/astar.py`
```python
"""A* with Manhattan heuristic (admissible and consistent on a 4-connected
unit-cost grid, so optimal)."""

from __future__ import annotations

import heapq
import itertools
from typing import Generator

from .common import Event, manhattan, neighbors, reconstruct, build_path_event


def astar(maze, start, end) -> Generator[Event, None, None]:
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    g: dict[tuple[int, int], int] = {start: 0}
    counter = itertools.count()
    heap: list[tuple[int, int, int, tuple[int, int]]] = [
        (manhattan(start, end), 0, next(counter), start)
    ]
    closed: set[tuple[int, int]] = set()
    while heap:
        _f, gc, _, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        closed.add(cur)
        yield ("visit", cur)
        if cur == end:
            yield build_path_event(reconstruct(parents, end))
            return
        for nb in neighbors(maze, cur[0], cur[1]):
            ng = gc + 1
            if ng < g.get(nb, 10**18):
                g[nb] = ng
                parents[nb] = cur
                f = ng + manhattan(nb, end)
                heapq.heappush(heap, (f, ng, next(counter), nb))
                yield ("frontier", nb)
    yield build_path_event([])
```

### `src/route_finder/algorithms/greedy_bf.py`
```python
"""Greedy Best-First Search with Manhattan heuristic. Not optimal."""

from __future__ import annotations

import heapq
import itertools
from typing import Generator

from .common import Event, manhattan, neighbors, reconstruct, build_path_event


def greedy_best_first(maze, start, end) -> Generator[Event, None, None]:
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    counter = itertools.count()
    heap: list[tuple[int, int, tuple[int, int]]] = [
        (manhattan(start, end), next(counter), start)
    ]
    visited_set: set[tuple[int, int]] = set()
    while heap:
        _h, _, cur = heapq.heappop(heap)
        if cur in visited_set:
            continue
        visited_set.add(cur)
        yield ("visit", cur)
        if cur == end:
            yield build_path_event(reconstruct(parents, end))
            return
        for nb in neighbors(maze, cur[0], cur[1]):
            if nb not in parents and nb not in visited_set:
                parents[nb] = cur
                heapq.heappush(heap, (manhattan(nb, end), next(counter), nb))
                yield ("frontier", nb)
    yield build_path_event([])
```

### `src/route_finder/algorithms/bi_bfs.py`
```python
"""Bidirectional BFS. Alternates expanding from start and from end; when
the two fronts meet, reconstructs the shortest path (optimal on uniform
grids)."""

from __future__ import annotations

from collections import deque
from typing import Generator

from .common import Event, neighbors, build_path_event


def _expand_layer(
    maze,
    q: deque,
    parents: dict,
    other_parents: dict,
) -> tuple[bool, tuple[int, int] | None]:
    """Expand one BFS layer from ``q``. Returns (met, meet_cell) where
    ``met`` is True if the layer touched a cell already known to the other
    frontier."""
    layer_size = len(q)
    for _ in range(layer_size):
        cur = q.popleft()
        if cur in other_parents:
            return True, cur
        for nb in neighbors(maze, cur[0], cur[1]):
            if nb not in parents:
                parents[nb] = cur
                if nb in other_parents:
                    return True, nb
                q.append(nb)
    return False, None


def bidirectional_bfs(maze, start, end) -> Generator[Event, None, None]:
    if start == end:
        yield ("visit", start)
        yield build_path_event([start])
        return

    parents_f: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    parents_b: dict[tuple[int, int], tuple[int, int] | None] = {end: None}
    qf = deque([start])
    qb = deque([end])

    yield ("visit", start)
    yield ("visit", end)

    meet: tuple[int, int] | None = None

    while qf and qb and meet is None:
        # Expand whichever frontier is smaller (classical bibfs heuristic).
        if len(qf) <= len(qb):
            layer_size = len(qf)
            for _ in range(layer_size):
                cur = qf.popleft()
                for nb in neighbors(maze, cur[0], cur[1]):
                    if nb not in parents_f:
                        parents_f[nb] = cur
                        yield ("visit", nb)
                        if nb in parents_b:
                            meet = nb
                            break
                        qf.append(nb)
                if meet is not None:
                    break
        else:
            layer_size = len(qb)
            for _ in range(layer_size):
                cur = qb.popleft()
                for nb in neighbors(maze, cur[0], cur[1]):
                    if nb not in parents_b:
                        parents_b[nb] = cur
                        yield ("visit", nb)
                        if nb in parents_f:
                            meet = nb
                            break
                        qb.append(nb)
                if meet is not None:
                    break

    if meet is None:
        yield build_path_event([])
        return

    # Reconstruct: start -> meet via parents_f, meet -> end via parents_b.
    left: list[tuple[int, int]] = []
    cur = meet
    while cur is not None:
        left.append(cur)
        cur = parents_f.get(cur)
    left.reverse()

    right: list[tuple[int, int]] = []
    cur = parents_b.get(meet)
    while cur is not None:
        right.append(cur)
        cur = parents_b.get(cur)

    yield build_path_event(left + right)
```

### `src/route_finder/ui/__init__.py`
```python
"""Pygame UI: canvas, sidebar, slider, shortcuts."""

from .canvas import Canvas
from .sidebar import Sidebar
from .slider import Slider
from .shortcuts import SHORTCUTS

__all__ = ["Canvas", "Sidebar", "Slider", "SHORTCUTS"]
```

### `src/route_finder/ui/canvas.py`
```python
"""Maze canvas: renders the maze plus incremental visited/path/endpoint
overlays. The maze is drawn on a 1-pixel-per-cell base surface and then
scaled to the canvas viewport each frame, preserving aspect ratio
(letterboxed inside the available area).
"""

from __future__ import annotations

import pygame

# Colors (RGB)
COLOR_BG = (24, 24, 28)
COLOR_WALL = (240, 240, 245)
COLOR_PASSAGE = (24, 24, 28)
COLOR_VISITED = (90, 160, 230)
COLOR_FRONTIER = (60, 100, 180)
COLOR_PATH = (255, 215, 70)
COLOR_START = (50, 200, 80)
COLOR_END = (220, 60, 60)
COLOR_LETTERBOX = (12, 12, 14)


class Canvas:
    """Holds a base 1-px-per-cell surface plus overlay state.

    Layers (lowest first):
      base (walls)  -> visited  -> path  -> endpoints
    Each is a per-pixel surface the size of the maze grid (grid_w x grid_h).
    The endpoints are drawn last as 1x1 pixels so they win color contention.
    """

    def __init__(self):
        self.base: pygame.Surface | None = None
        self.overlay: pygame.Surface | None = None
        self.grid_w = 0
        self.grid_h = 0
        self.start: tuple[int, int] | None = None
        self.end: tuple[int, int] | None = None

    # ---------- lifecycle ----------

    def attach_maze(self, maze) -> None:
        """Allocate base+overlay surfaces and paint walls."""
        self.grid_w = maze.grid_w
        self.grid_h = maze.grid_h
        # Use a 24-bit surface; SRCALPHA on overlay so we can clear it cheaply.
        self.base = pygame.Surface((self.grid_w, self.grid_h))
        self.base.fill(COLOR_PASSAGE)
        self.overlay = pygame.Surface((self.grid_w, self.grid_h), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 0))
        # Paint walls from the bytearray.
        # Per-pixel set_at is slow; do row-wise by scanning runs.
        walls = maze.walls
        gw = self.grid_w
        for y in range(self.grid_h):
            base_idx = y * gw
            x = 0
            while x < gw:
                if walls[base_idx + x] == 1:
                    run_start = x
                    while x < gw and walls[base_idx + x] == 1:
                        x += 1
                    pygame.draw.line(
                        self.base, COLOR_WALL, (run_start, y), (x - 1, y)
                    )
                else:
                    x += 1
        self.start = maze.start
        self.end = maze.end

    def clear_overlay(self) -> None:
        if self.overlay is not None:
            self.overlay.fill((0, 0, 0, 0))

    # ---------- incremental updates ----------

    def mark_carve(self, cells) -> None:
        """A generation step opened passages at the given grid cells."""
        if self.base is None:
            return
        for x, y in cells:
            self.base.set_at((x, y), COLOR_PASSAGE)

    def mark_visit(self, cell) -> None:
        if self.overlay is None:
            return
        self.overlay.set_at(cell, COLOR_VISITED)

    def mark_frontier(self, cell) -> None:
        if self.overlay is None:
            return
        # Only paint frontier on top of an untouched cell (don't overwrite visits).
        # Cheap approach: just paint; visited will be repainted as cells pop.
        # We skip frontier color to keep the visual simple and the overlay cheap.
        return

    def mark_path(self, path) -> None:
        if self.overlay is None:
            return
        for cell in path:
            self.overlay.set_at(cell, COLOR_PATH)

    def set_endpoints(self, start, end) -> None:
        self.start = start
        self.end = end

    # ---------- rendering ----------

    def render(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Blit base + overlay into ``rect`` on ``surface`` preserving aspect."""
        if self.base is None or self.overlay is None:
            pygame.draw.rect(surface, COLOR_LETTERBOX, rect)
            return

        pygame.draw.rect(surface, COLOR_LETTERBOX, rect)

        # Compute integer scale that fits.
        scale = min(rect.width / self.grid_w, rect.height / self.grid_h)
        if scale <= 0:
            return
        dw = max(1, int(self.grid_w * scale))
        dh = max(1, int(self.grid_h * scale))
        dx = rect.x + (rect.width - dw) // 2
        dy = rect.y + (rect.height - dh) // 2

        # Pre-composite base + overlay onto one temp surface, then scale once.
        composite = self.base.copy()
        composite.blit(self.overlay, (0, 0))
        # Paint endpoints last on the composite (1px each).
        if self.start is not None:
            composite.set_at(self.start, COLOR_START)
        if self.end is not None:
            composite.set_at(self.end, COLOR_END)
        scaled = pygame.transform.scale(composite, (dw, dh))
        surface.blit(scaled, (dx, dy))
```

### `src/route_finder/ui/sidebar.py`
```python
"""Sidebar: New Maze, six algorithm buttons (1..6), speed slider, Reset Colors.

Layout is recomputed on every resize. Buttons report clicks via callbacks set
by the app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pygame

from .slider import Slider

SIDEBAR_WIDTH = 240
PAD = 12
BTN_H = 36

COLOR_PANEL = (32, 32, 38)
COLOR_BTN = (52, 52, 62)
COLOR_BTN_HOVER = (72, 72, 86)
COLOR_BTN_ACTIVE = (90, 160, 230)
COLOR_TEXT = (230, 230, 235)
COLOR_TEXT_DIM = (170, 170, 180)


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    key: str  # "new_maze" | "reset" | "algo:1".."algo:6"
    hovered: bool = False
    active: bool = False


class Sidebar:
    def __init__(self, win_h: int):
        self.font: pygame.font.Font | None = None
        self.font_small: pygame.font.Font | None = None
        self.buttons: list[Button] = []
        self.slider = Slider(pygame.Rect(0, 0, 1, 1))
        self.status_lines: list[str] = []
        self.active_algo: int | None = None
        self.layout(win_h)

    # ---------- layout ----------

    def layout(self, win_h: int) -> None:
        x = PAD
        w = SIDEBAR_WIDTH - 2 * PAD
        y = PAD

        def add(label: str, key: str) -> None:
            nonlocal y
            self.buttons.append(Button(pygame.Rect(x, y, w, BTN_H), label, key))
            y += BTN_H + 8

        self.buttons = []
        add("New Maze", "new_maze")
        y += 8
        algo_labels = [
            "1. BFS",
            "2. DFS",
            "3. Dijkstra",
            "4. A*",
            "5. Greedy Best-First",
            "6. Bidirectional BFS",
        ]
        for i, label in enumerate(algo_labels, start=1):
            add(label, f"algo:{i}")
        y += 8
        # Slider rect: leave room for label above.
        slider_y = y + 16
        self.slider.rect = pygame.Rect(x, slider_y, w, 10)
        y = slider_y + 10 + 12

        add("Reset Colors", "reset")

    # ---------- input ----------

    def handle_event(
        self,
        event: pygame.event.Event,
        on_click: Callable[[str], None],
    ) -> bool:
        if self.slider.handle_event(event):
            return True

        if event.type == pygame.MOUSEMOTION:
            for b in self.buttons:
                b.hovered = b.rect.collidepoint(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.rect.collidepoint(event.pos):
                    on_click(b.key)
                    return True
        return False

    # ---------- state hook ----------

    def set_active_algo(self, idx: int | None) -> None:
        self.active_algo = idx
        for b in self.buttons:
            if b.key.startswith("algo:"):
                b.active = b.key == f"algo:{idx}"
            else:
                b.active = False

    def set_status(self, lines: list[str]) -> None:
        self.status_lines = lines

    # ---------- draw ----------

    def ensure_fonts(self) -> None:
        if self.font is None:
            self.font = pygame.font.SysFont("Helvetica", 14)
            self.font_small = pygame.font.SysFont("Helvetica", 12)

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        self.ensure_fonts()
        pygame.draw.rect(surface, COLOR_PANEL, rect)

        for b in self.buttons:
            color = COLOR_BTN
            if b.active:
                color = COLOR_BTN_ACTIVE
            elif b.hovered:
                color = COLOR_BTN_HOVER
            pygame.draw.rect(surface, color, b.rect, border_radius=4)
            txt = self.font.render(b.label, True, COLOR_TEXT)
            surface.blit(
                txt,
                (
                    b.rect.x + 10,
                    b.rect.y + (b.rect.height - txt.get_height()) // 2,
                ),
            )

        self.slider.draw(surface, self.font)

        # Status area below the Reset Colors button.
        last_btn = self.buttons[-1]
        sy = last_btn.rect.bottom + 16
        for line in self.status_lines:
            txt = self.font_small.render(line, True, COLOR_TEXT_DIM)
            surface.blit(txt, (PAD, sy))
            sy += txt.get_height() + 2
```

### `src/route_finder/ui/slider.py`
```python
"""Integer-range speed slider [1, 60] steps/sec."""

from __future__ import annotations

import pygame


class Slider:
    def __init__(self, rect: pygame.Rect, vmin: int = 1, vmax: int = 60, value: int = 20):
        self.rect = rect
        self.vmin = vmin
        self.vmax = vmax
        self.value = max(vmin, min(vmax, value))
        self.dragging = False

    @property
    def fraction(self) -> float:
        if self.vmax == self.vmin:
            return 0.0
        return (self.value - self.vmin) / (self.vmax - self.vmin)

    def _value_from_x(self, x: int) -> int:
        frac = (x - self.rect.x) / max(1, self.rect.width)
        frac = max(0.0, min(1.0, frac))
        return int(round(self.vmin + frac * (self.vmax - self.vmin)))

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if this slider consumed the event."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self.value = self._value_from_x(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.value = self._value_from_x(event.pos[0])
            return True
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        # Track
        pygame.draw.rect(surface, (60, 60, 70), self.rect, border_radius=3)
        # Fill
        fill_w = int(self.rect.width * self.fraction)
        if fill_w > 0:
            fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_w, self.rect.height)
            pygame.draw.rect(surface, (90, 160, 230), fill_rect, border_radius=3)
        # Knob
        knob_x = self.rect.x + fill_w
        pygame.draw.circle(
            surface,
            (240, 240, 245),
            (knob_x, self.rect.y + self.rect.height // 2),
            self.rect.height // 2 + 2,
        )
        # Label
        text = font.render(f"Speed: {self.value} / sec", True, (230, 230, 235))
        surface.blit(text, (self.rect.x, self.rect.y - text.get_height() - 4))
```

### `src/route_finder/ui/shortcuts.py`
```python
"""Keyboard shortcut mapping for algorithms 1..6."""

from __future__ import annotations

import pygame

# pygame key -> algorithm index (1..6) per spec.
SHORTCUTS: dict[int, int] = {
    pygame.K_1: 1,
    pygame.K_2: 2,
    pygame.K_3: 3,
    pygame.K_4: 4,
    pygame.K_5: 5,
    pygame.K_6: 6,
    # numpad
    pygame.K_KP1: 1,
    pygame.K_KP2: 2,
    pygame.K_KP3: 3,
    pygame.K_KP4: 4,
    pygame.K_KP5: 5,
    pygame.K_KP6: 6,
}
```

### `src/route_finder/app.py`
```python
"""Main app loop and AppState.

Phases:
  - generating: maze generator is being stepped; canvas paints carve events.
  - idle: maze is fully generated; awaiting algorithm selection.
  - pathfinding: a pathfinder generator is being stepped; canvas paints
    visit events; on the terminal "done" event, the path is overlaid.

Cancellation: switching algorithm mid-run drops the current generator,
clears overlay colors, and starts the new one on the same maze + A/B.

Speed: the slider drives steps-per-second uniformly. Each frame we may
advance the active generator by ``max(1, speed * dt)`` steps; since the
slider caps at 60 we never need more than ~1 step per 60Hz frame.
"""

from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass, field
from typing import Generator

import pygame

from .algorithms import REGISTRY
from .maze import generate_maze, is_perfect_maze, pick_endpoints
from .ui.canvas import Canvas
from .ui.sidebar import Sidebar, SIDEBAR_WIDTH
from .ui.shortcuts import SHORTCUTS

DEFAULT_W, DEFAULT_H = 1100, 720
DEFAULT_MAZE_W, DEFAULT_MAZE_H = 60, 40


@dataclass
class AppState:
    maze: object | None = None
    run_gen: Generator | None = None
    gen_gen: Generator | None = None
    speed: int = 20
    phase: str = "idle"  # "generating" | "idle" | "pathfinding"
    active_algo: int | None = None
    last_step_time: float = field(default_factory=time.monotonic)
    step_carry: float = 0.0
    rng: random.Random = field(default_factory=random.Random)
    maze_w: int = DEFAULT_MAZE_W
    maze_h: int = DEFAULT_MAZE_H


class App:
    def __init__(self, maze_w: int = DEFAULT_MAZE_W, maze_h: int = DEFAULT_MAZE_H):
        pygame.init()
        pygame.display.set_caption("route-finder")
        self.screen = pygame.display.set_mode(
            (DEFAULT_W, DEFAULT_H), pygame.RESIZABLE
        )
        self.clock = pygame.time.Clock()
        self.state = AppState(maze_w=maze_w, maze_h=maze_h)
        self.canvas = Canvas()
        self.sidebar = Sidebar(self.screen.get_height())
        self.start_new_maze()

    # ---------- maze lifecycle ----------

    def start_new_maze(self) -> None:
        self.state.run_gen = None
        self.state.active_algo = None
        # Allocate the live Maze and pass it INTO the generator so generator
        # writes its walls in place. UI shares the same instance.
        from .maze.grid import Maze as _Maze

        live = _Maze(self.state.maze_w, self.state.maze_h)
        self.state.maze = live
        self.state.gen_gen = generate_maze(
            self.state.maze_w,
            self.state.maze_h,
            rng=self.state.rng,
            maze=live,
        )
        self.state.phase = "generating"
        self.canvas.attach_maze(live)
        self.sidebar.set_active_algo(None)
        self._update_status()

    def _finish_generation(self) -> None:
        maze = self.state.maze
        # Pick endpoints.
        a, b = pick_endpoints(maze, rng=self.state.rng)
        maze.start = a
        maze.end = b
        self.canvas.set_endpoints(a, b)
        self.canvas.clear_overlay()
        self.state.phase = "idle"
        self.state.gen_gen = None
        self._update_status()

    # ---------- pathfinding lifecycle ----------

    def start_algorithm(self, idx: int) -> None:
        if idx not in REGISTRY or self.state.maze is None:
            return
        if self.state.phase == "generating":
            return  # ignore algorithm switches during generation
        # Cancel current run if any, reset overlay.
        self.state.run_gen = None
        self.canvas.clear_overlay()
        algo = REGISTRY[idx]
        self.state.run_gen = algo.step(
            self.state.maze, self.state.maze.start, self.state.maze.end
        )
        self.state.active_algo = idx
        self.state.phase = "pathfinding"
        self.sidebar.set_active_algo(idx)
        self._update_status()

    # ---------- event handling ----------

    def on_sidebar_click(self, key: str) -> None:
        if key == "new_maze":
            self.start_new_maze()
        elif key == "reset":
            if self.state.phase == "pathfinding":
                self.state.run_gen = None
                self.state.phase = "idle"
                self.state.active_algo = None
                self.sidebar.set_active_algo(None)
            self.canvas.clear_overlay()
            self._update_status()
        elif key.startswith("algo:"):
            try:
                idx = int(key.split(":", 1)[1])
            except ValueError:
                return
            self.start_algorithm(idx)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return False to exit the app."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(
                (event.w, event.h), pygame.RESIZABLE
            )
            self.sidebar.layout(event.h)
            return True
        if event.type == pygame.KEYDOWN:
            if event.key in SHORTCUTS:
                self.start_algorithm(SHORTCUTS[event.key])
                return True
            if event.key == pygame.K_n:
                self.start_new_maze()
                return True
            if event.key == pygame.K_r:
                self.on_sidebar_click("reset")
                return True
            if event.key == pygame.K_ESCAPE:
                return False
        self.sidebar.handle_event(event, self.on_sidebar_click)
        # Keep speed in state.
        self.state.speed = self.sidebar.slider.value
        return True

    # ---------- per-frame step ----------

    def step_active(self, dt: float) -> None:
        """Advance the active generator by `speed * dt` steps (carry remainder)."""
        speed = self.state.speed
        self.state.step_carry += speed * dt
        steps = int(self.state.step_carry)
        if steps <= 0:
            return
        self.state.step_carry -= steps

        if self.state.phase == "generating" and self.state.gen_gen is not None:
            for _ in range(steps):
                try:
                    cells = next(self.state.gen_gen)
                    self.canvas.mark_carve(cells)
                except StopIteration:
                    self._finish_generation()
                    break
        elif self.state.phase == "pathfinding" and self.state.run_gen is not None:
            for _ in range(steps):
                try:
                    event = next(self.state.run_gen)
                except StopIteration:
                    self.state.phase = "idle"
                    self._update_status()
                    break
                tag = event[0]
                if tag == "visit":
                    self.canvas.mark_visit(event[1])
                elif tag == "frontier":
                    self.canvas.mark_frontier(event[1])
                elif tag == "done":
                    self.canvas.mark_path(event[1])
                    self.state.phase = "idle"
                    self.state.run_gen = None
                    self._update_status(path_len=len(event[1]))
                    break

    # ---------- status ----------

    def _update_status(self, path_len: int | None = None) -> None:
        lines = [
            f"Phase: {self.state.phase}",
            f"Maze: {self.state.maze_w} x {self.state.maze_h}",
        ]
        if self.state.active_algo:
            lines.append(f"Algo: {REGISTRY[self.state.active_algo].name}")
        if path_len is not None:
            lines.append(f"Path len: {path_len}")
        lines.append("Keys: 1..6, N=new, R=reset, Esc=quit")
        self.sidebar.set_status(lines)

    # ---------- main loop ----------

    def run(self) -> int:
        while True:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if not self.handle_event(event):
                    pygame.quit()
                    return 0
            self.state.speed = self.sidebar.slider.value
            self.step_active(dt)
            self._render()
            pygame.display.flip()

    def _render(self) -> None:
        self.screen.fill((12, 12, 14))
        win_w, win_h = self.screen.get_size()
        sidebar_rect = pygame.Rect(0, 0, SIDEBAR_WIDTH, win_h)
        canvas_rect = pygame.Rect(
            SIDEBAR_WIDTH, 0, max(0, win_w - SIDEBAR_WIDTH), win_h
        )
        self.canvas.render(self.screen, canvas_rect)
        self.sidebar.draw(self.screen, sidebar_rect)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    w, h = DEFAULT_MAZE_W, DEFAULT_MAZE_H
    if len(argv) >= 2:
        try:
            w = max(1, min(1000, int(argv[0])))
            h = max(1, min(1000, int(argv[1])))
        except ValueError:
            pass
    app = App(maze_w=w, maze_h=h)
    return app.run()
```

## Empirical sanity check (no display required)

I exercised the maze + invariants + algorithms without launching pygame.
Captured output (verbatim):

```
(20, 15): perfect=True non_wall=599 edges=598 expected_edges=598 connected=True
(50, 50): perfect=True non_wall=4999 edges=4998 expected_edges=4998 connected=True
(5, 5):   perfect=True non_wall=49  edges=48  expected_edges=48  connected=True
(1, 1):   perfect=True non_wall=1   edges=0   expected_edges=0   connected=True

--- endpoint + pathfinder equality (40 x 30 maze, seed 7) ---
A=(25, 23) B=(73, 51)  manhattan/2=38.0  threshold=35.0
  BFS:      path_len=373  visited=1210
  DFS:      path_len=373  visited=2337
  Dijkstra: path_len=373  visited=1210
  A*:       path_len=373  visited=1095
  Greedy:   path_len=373  visited=433
  BiBFS:    path_len=373  visited=799
```

Also verified that `import` of `route_finder.app` succeeds with pygame stubbed
(this environment has no display).

## Self-check vs AC1..AC12

- **AC1** — Entry point `python -m route_finder [w h]` is provided by
  `__main__.py` and `main()` in `app.py`. `App.__init__` calls `pygame.init()`,
  `pygame.display.set_mode(...)`, sets the window caption "route-finder", and
  immediately kicks off maze generation. Width/height are clamped to
  `[1, 1000]`. Satisfied.
- **AC2** — `maze/invariants.py` implements `connectivity_ok` (BFS from the
  first non-wall cell, counts equality with `total_passages`) AND `edge_count`
  (counts passage-passage edges with each edge counted exactly once via
  right-and-down neighbor checks). `is_perfect_maze` returns `connected AND
  edges == non_wall_count - 1`. Empirically, on the four sample sizes
  (20x15, 50x50, 5x5, 1x1) and on the 40x30 maze used for AC7, every maze
  satisfies the invariants (see the run output above). Satisfied.
- **AC3** — `pick_endpoints` draws A,B from logical-cell passages (which, by
  DFS Backtracker construction, are guaranteed to be non-wall). It enforces
  `a != b` and `manhattan_logical(a,b) >= (width+height)*0.5`, where
  `manhattan_logical = rendered_manhattan/2.0`. A fallback selects the
  BFS-farthest cell from A if random retries fail. The canvas paints A in
  `COLOR_START = (50, 200, 80)` (green) and B in `COLOR_END = (220, 60, 60)`
  (red) as a final overlay on each frame. Satisfied.
- **AC4** — "New Maze" (button key `new_maze` and keyboard `N`) calls
  `App.start_new_maze`, which allocates a fresh Maze, resets `run_gen`/`active_algo`,
  begins step-by-step DFS Backtracker generation, attaches the new Maze to
  the canvas, and clears any previous overlay. `_finish_generation` then
  randomizes A and B and clears overlays. The generation runs at
  `state.speed` steps/sec via the same `step_active` pacing loop used for
  pathfinding. Satisfied.
- **AC5** — The six algorithms are registered in `algorithms/__init__.py`'s
  `REGISTRY` at indices 1..6 in spec order. The sidebar (`ui/sidebar.py`)
  emits a click for each via key `algo:1` .. `algo:6`, and keyboard
  shortcuts in `ui/shortcuts.py` map `pygame.K_1..K_6` (and numpad) to the
  same indices. Both paths funnel into `App.start_algorithm`. Satisfied.
- **AC6** — Each algorithm yields `("visit", cell)` events; the canvas
  paints them as `COLOR_VISITED` on the overlay surface, which is composited
  over the maze each frame. On `("done", path)`, the canvas paints the path
  cells as `COLOR_PATH` (yellow-gold), distinct from visited blue and the
  green/red endpoints. Satisfied.
- **AC7** — BFS, Dijkstra (unit weights), A* (Manhattan heuristic which is
  admissible and consistent on a 4-connected unit-cost grid), and BiBFS are
  all path-length-optimal. Tie-breaking is deterministic: `common.neighbors`
  yields in the fixed order (right, down, left, up), and the heap-based
  algorithms include an `itertools.count()` counter for stable ordering of
  equal-priority items. The empirical run above confirms identical
  `path_len = 373` for BFS / Dijkstra / A* / BiBFS on a 40x30 maze.
  DFS and Greedy return any valid path. Satisfied.
- **AC8** — `App.start_algorithm` first sets `self.state.run_gen = None` and
  calls `self.canvas.clear_overlay()` before constructing the new generator,
  so switching algorithms mid-run cancels the current run, resets visualization
  colors, and starts the new one on the same maze + A/B. Satisfied.
- **AC9** — `ui/slider.py` exposes an integer-range slider with `vmin=1`,
  `vmax=60`. `App.run` reads `self.sidebar.slider.value` each frame into
  `self.state.speed`, which is consumed by `step_active` to decide how many
  generator steps to advance — so a slider change takes effect on the next
  step. Satisfied.
- **AC10** — The "Reset Colors" button (`reset`) and `R` key route to
  `on_sidebar_click("reset")`. It cancels any in-flight run, sets the phase
  to `idle`, and calls `canvas.clear_overlay()`. The base surface (maze
  walls), the stored `maze.start`/`maze.end`, and the canvas's endpoint
  pixels are untouched. Satisfied.
- **AC11** — On `pygame.VIDEORESIZE`, `App.handle_event` calls
  `pygame.display.set_mode((w, h), RESIZABLE)` and `self.sidebar.layout(h)`.
  `Canvas.render` computes
  `scale = min(rect.width / grid_w, rect.height / grid_h)` and centers the
  scaled image inside the canvas viewport, so the maze aspect ratio is
  preserved regardless of window shape. Satisfied.
- **AC12** — `requirements.txt` declares only `pygame>=2.5,<3`. A grep over
  `src/` finds NO imports of `urllib`, `http`, `socket`, `requests`, `httpx`,
  `aiohttp`, `ftplib`, `smtplib`, or `telnetlib`. The only third-party
  import anywhere in the source tree is `pygame`. All other imports are
  stdlib: `sys`, `random`, `time`, `dataclasses`, `typing`, `collections`,
  `heapq`, `itertools`. A fresh-venv `pip install -r requirements.txt`
  followed by `pip list` would show only `pygame` (plus its transitive
  stdlib deps), and the running program makes zero outbound network
  requests. Satisfied.

## Ready for review

yes — verdict requested from reviewer.
