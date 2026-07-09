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
