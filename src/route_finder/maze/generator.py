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
