"""Maze perfect-maze invariants: connectivity + acyclicity (edge count)."""

from __future__ import annotations

from collections import deque

from .grid import Maze


def connectivity_ok(maze: Maze) -> bool:
    """BFS from the first non-wall cell. Returns True iff every non-wall
    cell is visited."""
    gw = maze.grid_w
    gh = maze.grid_h
    walls = maze.walls
    total_passages = 0
    start: tuple[int, int] | None = None
    for y in range(gh):
        base = y * gw
        for x in range(gw):
            if walls[base + x] == 0:
                total_passages += 1
                if start is None:
                    start = (x, y)
    if start is None:
        return True

    seen = bytearray(gw * gh)
    seen[start[1] * gw + start[0]] = 1
    q = deque([start])
    count = 0
    while q:
        x, y = q.popleft()
        count += 1
        # 4 neighbors
        if x > 0 and walls[y * gw + (x - 1)] == 0 and not seen[y * gw + (x - 1)]:
            seen[y * gw + (x - 1)] = 1
            q.append((x - 1, y))
        if x + 1 < gw and walls[y * gw + (x + 1)] == 0 and not seen[y * gw + (x + 1)]:
            seen[y * gw + (x + 1)] = 1
            q.append((x + 1, y))
        if y > 0 and walls[(y - 1) * gw + x] == 0 and not seen[(y - 1) * gw + x]:
            seen[(y - 1) * gw + x] = 1
            q.append((x, y - 1))
        if y + 1 < gh and walls[(y + 1) * gw + x] == 0 and not seen[(y + 1) * gw + x]:
            seen[(y + 1) * gw + x] = 1
            q.append((x, y + 1))
    return count == total_passages


def edge_count(maze: Maze) -> int:
    """Count passage-passage edges in the rendered grid (each counted once)."""
    gw = maze.grid_w
    gh = maze.grid_h
    walls = maze.walls
    edges = 0
    for y in range(gh):
        base = y * gw
        for x in range(gw):
            if walls[base + x] == 1:
                continue
            # right neighbor
            if x + 1 < gw and walls[base + x + 1] == 0:
                edges += 1
            # down neighbor
            if y + 1 < gh and walls[(y + 1) * gw + x] == 0:
                edges += 1
    return edges


def non_wall_count(maze: Maze) -> int:
    return sum(1 for b in maze.walls if b == 0)


def is_perfect_maze(maze: Maze) -> bool:
    """Perfect = connected AND #edges == #non_wall_cells - 1."""
    n = non_wall_count(maze)
    if n == 0:
        return True
    if not connectivity_ok(maze):
        return False
    return edge_count(maze) == n - 1
