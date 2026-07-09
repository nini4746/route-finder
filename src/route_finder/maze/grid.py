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

# Per review_v1 note #1: a 1x1 maze has only one non-wall cell, so endpoint
# selection (which requires A != B) can never succeed. We tighten the lower
# bound to 2 at this single boundary; the spec's stated 1..1000 range is
# intentionally narrowed to 2..1000 for soundness.
MIN_MAZE_DIM = 2
MAX_MAZE_DIM = 1000


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
        # MIN_MAZE_DIM=2 deliberately tightens the spec's 1..1000 lower bound
        # (see review_v1 note #1: 1x1 mazes break endpoint selection).
        if not (
            MIN_MAZE_DIM <= width <= MAX_MAZE_DIM
            and MIN_MAZE_DIM <= height <= MAX_MAZE_DIM
        ):
            raise ValueError(
                f"maze size must satisfy {MIN_MAZE_DIM} <= w,h <= {MAX_MAZE_DIM} "
                f"(got {width}x{height})"
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
