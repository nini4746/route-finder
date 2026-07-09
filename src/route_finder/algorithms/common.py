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
