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
