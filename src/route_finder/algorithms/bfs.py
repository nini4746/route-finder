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
