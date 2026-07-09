"""AC7 parity: BFS / Dijkstra / A* / BiBFS / IDA* all return the same path
length on the same maze + endpoints. Tie-breaking is deterministic via
fixed neighbor order in ``common.neighbors``.

v3 extension: also assert that a parity run with the same seed produces
identical ``visited`` and ``path length`` snapshot values across two
invocations. This guards against any future PRNG plumbing regression that
would break the "seed in status panel = reproducible run" contract.
"""

from __future__ import annotations

import random
import unittest

from route_finder.algorithms import (
    astar,
    bfs,
    bidirectional_bfs,
    dijkstra,
    ida_star,
)
from route_finder.maze import Maze, generate_maze, pick_endpoints


# Per request_v2 §C.2: parity test for IDA* is allowed to stay at 25x25
# only if 40x30 is too slow; we keep 40x30 in here but cap the upper end
# at 40x30 to keep total runtime under ~10s.
SIZES = [
    (20, 15),
    (25, 25),
    (40, 30),
]


def _build_maze(w: int, h: int, seed: int):
    rng = random.Random(seed)
    maze = Maze(w, h)
    gen = generate_maze(w, h, rng=rng, maze=maze)
    for _ in gen:
        pass
    a, b = pick_endpoints(maze, rng=rng)
    maze.start = a
    maze.end = b
    return maze, a, b


def _drive(algo, maze, a, b) -> int:
    """Drive an algorithm generator to completion; return path length."""
    last_path: list = []
    for event in algo(maze, a, b):
        if event[0] == "done":
            last_path = event[1] if event[1] is not None else []
            # don't break; some algos may not emit anything after done,
            # but returning from the generator on done is the contract
            break
    return len(last_path)


def _drive_with_counters(algo, maze, a, b):
    """Drive an algorithm and report (visited_count, path_len).

    ``visited_count`` is the number of UNIQUE cells emitted via
    ``("visit", cell)`` — mirroring AppState.visited_count exactly. This
    is the value displayed in the v3 status panel.
    """
    visited: set = set()
    path_len = 0
    for event in algo(maze, a, b):
        tag = event[0]
        if tag == "visit":
            visited.add(event[1])
        elif tag == "done":
            path = event[1] if event[1] is not None else []
            path_len = len(path)
            break
    return len(visited), path_len


class OptimalParityTests(unittest.TestCase):
    def test_five_optimal_algos_agree(self) -> None:
        for i, (w, h) in enumerate(SIZES):
            with self.subTest(size=(w, h)):
                maze, a, b = _build_maze(w, h, seed=2000 + i)
                lengths = {
                    "BFS": _drive(bfs, maze, a, b),
                    "Dijkstra": _drive(dijkstra, maze, a, b),
                    "AStar": _drive(astar, maze, a, b),
                    "BiBFS": _drive(bidirectional_bfs, maze, a, b),
                    "IDA*": _drive(ida_star, maze, a, b),
                }
                ref = lengths["BFS"]
                self.assertGreater(ref, 0, f"{w}x{h}: BFS returned empty path")
                for name, ln in lengths.items():
                    self.assertEqual(
                        ln,
                        ref,
                        f"{w}x{h}: {name} path_len={ln} but BFS={ref}",
                    )


class StatusPanelDeterminismTests(unittest.TestCase):
    """v3 UX-C/UX-A regression: same seed -> same (visited, path_len) on
    every optimal algorithm. Runs the parity algorithms twice on the same
    seed and asserts the per-algorithm counters match across runs.

    Why this matters: the status panel surfaces the seed precisely so the
    user can "reproduce a maze they liked". If counters drifted run-to-run
    on a fixed seed the seed display would be a lie.
    """

    PARITY_ALGOS = [
        ("BFS", bfs),
        ("Dijkstra", dijkstra),
        ("AStar", astar),
        ("BiBFS", bidirectional_bfs),
        ("IDA*", ida_star),
    ]

    def test_same_seed_same_counters_across_runs(self) -> None:
        # Use the same sizes as the parity test so we cover the same
        # surface but with two independent invocations.
        for i, (w, h) in enumerate(SIZES):
            for name, algo in self.PARITY_ALGOS:
                with self.subTest(size=(w, h), algo=name):
                    seed = 5000 + i
                    m1, a1, b1 = _build_maze(w, h, seed=seed)
                    v1, p1 = _drive_with_counters(algo, m1, a1, b1)
                    m2, a2, b2 = _build_maze(w, h, seed=seed)
                    v2, p2 = _drive_with_counters(algo, m2, a2, b2)
                    self.assertEqual(
                        (a1, b1), (a2, b2),
                        f"{w}x{h} {name}: endpoints drifted across runs",
                    )
                    self.assertEqual(
                        v1, v2,
                        f"{w}x{h} {name}: visited count drifted "
                        f"({v1} vs {v2}) on seed={seed}",
                    )
                    self.assertEqual(
                        p1, p2,
                        f"{w}x{h} {name}: path length drifted "
                        f"({p1} vs {p2}) on seed={seed}",
                    )


if __name__ == "__main__":
    unittest.main()
