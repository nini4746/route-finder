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

    Threshold is ``(width + height) * 0.5`` in rendered-grid Manhattan units,
    which equates to ``(width + height)`` after the *2 stretch — wait, the
    spec stipulates the threshold in LOGICAL cell counts, so we compare
    against ``(width + height) * 0.5`` directly using the rendered-grid
    Manhattan distance scaled back by /2.
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
