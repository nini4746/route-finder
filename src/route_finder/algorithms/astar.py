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
