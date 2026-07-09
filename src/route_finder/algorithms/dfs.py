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
