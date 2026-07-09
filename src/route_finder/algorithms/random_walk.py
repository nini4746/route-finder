"""Random Walk pathfinder.

From A, repeatedly step to a uniformly random open neighbor until B is
reached or a step cap is hit. Not optimal — classified with DFS / Greedy
under AC7's "any valid A->B path" branch.

The step cap is ``width * height * 20`` so hostile mazes can't keep the
animation alive indefinitely. On cap-hit we emit ``("done", None)`` to
signal "no path found this attempt" (callers / UI may interpret a None
payload as a failed run; this is distinct from ``("done", [])`` which
the other algorithms emit when the goal is unreachable).

Determinism: uses an internal ``random.Random`` seeded from the maze's
dimensions and the endpoints so the test suite can rely on reproducible
runs. Production callers can ignore the seed — the step cadence is still
randomised across pygame frames in practice because the maze layout
varies.
"""

from __future__ import annotations

import random
from typing import Generator

from .common import Event, neighbors


# Per the request: cap at width*height*20 logical-cell steps. Width/height
# below refer to the LOGICAL maze dims, not the rendered grid_w/grid_h.
_STEP_CAP_MULTIPLIER = 20


def random_walk(maze, start, end) -> Generator[Event, None, None]:
    # Seed locally for determinism inside tests. Real-time UI runs are not
    # disturbed by this because the maze itself is the dominant variable.
    # Python 3.14 no longer accepts arbitrary tuples as seeds; hash a
    # well-formed tuple down to an int instead.
    rng = random.Random(
        hash((maze.width, maze.height, start, end))
    )

    cur = start
    step_cap = maze.width * maze.height * _STEP_CAP_MULTIPLIER
    steps = 0

    yield ("visit", cur)
    if cur == end:
        yield ("done", [cur])
        return

    # Track the actual walk so we can hand back a valid path on success.
    walk: list[tuple[int, int]] = [cur]

    while steps < step_cap:
        nbrs = list(neighbors(maze, cur[0], cur[1]))
        if not nbrs:
            # Dead end with no open neighbors (shouldn't happen on a
            # perfect maze because every passage has at least one
            # neighbor, but defend anyway).
            break
        cur = nbrs[rng.randrange(len(nbrs))]
        walk.append(cur)
        steps += 1
        yield ("visit", cur)
        if cur == end:
            # Compress the walk into a simple path: drop loops by keeping
            # only the first occurrence of each cell along the walk, then
            # walking back through the trace. Easier: do a loop-eraser
            # pass over ``walk``.
            yield ("done", _loop_erase(walk))
            return

    # Step cap hit; signal "no path found this attempt".
    yield ("done", None)


def _loop_erase(walk: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Loop-erased projection of a self-intersecting random walk.

    Walk left to right; whenever we revisit a cell already in the
    projection, truncate the projection back to (and including) the first
    occurrence. The result is a simple (no repeats) path that is a valid
    A->B path through 4-adjacent passage cells.
    """
    idx: dict[tuple[int, int], int] = {}
    out: list[tuple[int, int]] = []
    for cell in walk:
        if cell in idx:
            keep = idx[cell] + 1
            # Drop tail and reset index map for dropped entries.
            for dropped in out[keep:]:
                idx.pop(dropped, None)
            del out[keep:]
        else:
            idx[cell] = len(out)
            out.append(cell)
    return out
