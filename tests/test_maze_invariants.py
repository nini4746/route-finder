"""AC2: perfect-maze invariants — connectivity + #edges == #non_wall - 1."""

from __future__ import annotations

import random
import unittest

from route_finder.maze import (
    Maze,
    connectivity_ok,
    edge_count,
    generate_maze,
)
from route_finder.maze.invariants import non_wall_count


SIZES = [
    (2, 2),
    (5, 5),
    (20, 15),
    (25, 25),
    (50, 50),
    (100, 50),
]


def _run_generator(w: int, h: int, seed: int) -> Maze:
    rng = random.Random(seed)
    maze = Maze(w, h)
    gen = generate_maze(w, h, rng=rng, maze=maze)
    # Drain the generator; we don't care about the per-step output here.
    for _ in gen:
        pass
    return maze


class MazeInvariantTests(unittest.TestCase):
    def test_perfect_maze_invariants_across_sizes(self) -> None:
        for i, (w, h) in enumerate(SIZES):
            with self.subTest(size=(w, h)):
                maze = _run_generator(w, h, seed=1000 + i)
                self.assertTrue(
                    connectivity_ok(maze),
                    f"{w}x{h}: BFS from (0,0) did not reach all non-wall cells",
                )
                n = non_wall_count(maze)
                e = edge_count(maze)
                self.assertEqual(
                    e,
                    n - 1,
                    f"{w}x{h}: edges={e} but non_wall-1={n - 1}",
                )


if __name__ == "__main__":
    unittest.main()
