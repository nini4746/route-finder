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
