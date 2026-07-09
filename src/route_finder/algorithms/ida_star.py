"""Iterative Deepening A* (IDA*).

A memory-efficient optimal pathfinder: repeated depth-bounded DFS waves
where the bound is the current f-threshold (g + Manhattan heuristic).
Manhattan is admissible and consistent on a 4-connected unit-cost grid,
so IDA* returns the same path length as BFS / Dijkstra / A* / BiBFS.

Event protocol nuance: because the same cell may be re-expanded across
multiple f-threshold iterations, we emit ``("visit", cell)`` only on the
**first** expansion of each cell across all iterations. This keeps the
on-screen visited overlay monotonic (no repaint of cells that are
re-visited on a later iteration).
"""

from __future__ import annotations

from typing import Generator

from .common import Event, manhattan, neighbors, build_path_event

# Infinity sentinel for the next f-threshold computation.
_INF = float("inf")


def ida_star(maze, start, end) -> Generator[Event, None, None]:
    if start == end:
        yield ("visit", start)
        yield build_path_event([start])
        return

    # Cells already announced as visited at least once. Subsequent
    # re-expansions on later f-thresholds will NOT re-emit ("visit", ...).
    announced: set[tuple[int, int]] = set()

    # Current path stack (start..current). We DFS along this and unwind on
    # bound overshoot. ``on_path`` mirrors the stack as a set for O(1)
    # cycle checks (which matter even on perfect mazes when DFS may revisit
    # ancestors via differing parents across iterations).
    bound = manhattan(start, end)

    while True:
        # One bounded DFS iteration. We implement it as an explicit stack
        # generator so we can yield through it; this avoids Python recursion
        # depth limits on large mazes.
        path: list[tuple[int, int]] = [start]
        on_path: set[tuple[int, int]] = {start}
        # For each node on the current path, an iterator over its remaining
        # neighbors to try.
        iters: list = [iter(neighbors(maze, start[0], start[1]))]
        # g-cost of the current top of stack.
        g_stack: list[int] = [0]

        next_bound = _INF
        found = False

        # Emit visit for start on the first iteration only.
        if start not in announced:
            announced.add(start)
            yield ("visit", start)

        while path:
            cur = path[-1]
            g_cur = g_stack[-1]
            it = iters[-1]
            try:
                nb = next(it)
            except StopIteration:
                # Exhausted; backtrack.
                path.pop()
                on_path.discard(cur)
                iters.pop()
                g_stack.pop()
                continue
            if nb in on_path:
                continue  # don't revisit ancestors on the current path
            g_nb = g_cur + 1
            f_nb = g_nb + manhattan(nb, end)
            if f_nb > bound:
                if f_nb < next_bound:
                    next_bound = f_nb
                continue
            # Expand nb.
            if nb not in announced:
                announced.add(nb)
                yield ("visit", nb)
            if nb == end:
                # Reconstruct path from the explicit stack + nb.
                final_path = list(path) + [nb]
                yield build_path_event(final_path)
                found = True
                break
            path.append(nb)
            on_path.add(nb)
            iters.append(iter(neighbors(maze, nb[0], nb[1])))
            g_stack.append(g_nb)

        if found:
            return
        if next_bound is _INF:
            # No node had f <= bound + something reachable; the goal is
            # unreachable. For a perfect maze with valid endpoints this
            # shouldn't happen.
            yield build_path_event([])
            return
        bound = next_bound  # type: ignore[assignment]
