"""AC7 'any valid A->B path' branch: DFS, Greedy, Random Walk.

For DFS and Greedy the returned path must always be a valid A->B path
(starts at A, ends at B, every consecutive pair is 4-adjacent and both
endpoints non-wall). For Random Walk the same holds when a path is
returned; the step-cap-hit outcome (``("done", None)``) is also a legal
result and is tolerated on at least one fixture.
"""

from __future__ import annotations

import random
import unittest

from route_finder.algorithms import dfs, greedy_best_first, random_walk
from route_finder.maze import Maze, generate_maze, pick_endpoints


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


def _drive(algo, maze, a, b):
    """Return the path payload of the final ``done`` event (list or None)."""
    payload: object = []
    for event in algo(maze, a, b):
        if event[0] == "done":
            payload = event[1]
            break
    return payload


def _assert_valid_path(testcase, maze, a, b, path) -> None:
    testcase.assertTrue(path, "expected a non-empty path")
    testcase.assertEqual(path[0], a, "path must start at A")
    testcase.assertEqual(path[-1], b, "path must end at B")
    gw = maze.grid_w
    walls = maze.walls
    # Every cell in the path must be a passage.
    for cell in path:
        x, y = cell
        testcase.assertEqual(
            walls[y * gw + x],
            0,
            f"path cell {cell} is a wall",
        )
    # Consecutive cells must be 4-adjacent.
    for i in range(1, len(path)):
        x1, y1 = path[i - 1]
        x2, y2 = path[i]
        testcase.assertEqual(
            abs(x1 - x2) + abs(y1 - y2),
            1,
            f"path step {path[i - 1]}->{path[i]} is not 4-adjacent",
        )


class AnyValidPathTests(unittest.TestCase):
    def test_dfs_returns_valid_path(self) -> None:
        for i, (w, h) in enumerate(SIZES):
            with self.subTest(size=(w, h)):
                maze, a, b = _build_maze(w, h, seed=3000 + i)
                path = _drive(dfs, maze, a, b)
                _assert_valid_path(self, maze, a, b, path)

    def test_greedy_returns_valid_path(self) -> None:
        for i, (w, h) in enumerate(SIZES):
            with self.subTest(size=(w, h)):
                maze, a, b = _build_maze(w, h, seed=3100 + i)
                path = _drive(greedy_best_first, maze, a, b)
                _assert_valid_path(self, maze, a, b, path)

    def test_random_walk_returns_valid_path_or_none(self) -> None:
        # Per request_v2 §C.3: each fixture must yield EITHER a valid
        # A->B path OR a None payload (step-cap hit). Random walks on
        # perfect mazes have O(n^2) hitting times; with the spec-mandated
        # step cap of n*20 it's entirely expected that all three fixtures
        # cap out. Both outcomes are legal — what we check is that no
        # fixture returns an invalid path.
        for i, (w, h) in enumerate(SIZES):
            with self.subTest(size=(w, h)):
                maze, a, b = _build_maze(w, h, seed=3200 + i)
                payload = _drive(random_walk, maze, a, b)
                if payload is None:
                    continue  # cap-hit; legal outcome
                _assert_valid_path(self, maze, a, b, payload)

    def test_random_walk_can_return_valid_path_on_small_mazes(self) -> None:
        # Extra sanity check: on small mazes Random Walk should at least
        # sometimes succeed. If we never see a non-None payload across
        # 12 small fixtures, the implementation is broken. This guards
        # against silent regressions where random_walk always reports
        # cap-hit.
        seen_path = False
        for s in range(12):
            try:
                maze, a, b = _build_maze(5, 5, seed=3500 + s)
            except ValueError:
                continue  # endpoint picker raised on this seed
            payload = _drive(random_walk, maze, a, b)
            if payload is not None:
                _assert_valid_path(self, maze, a, b, payload)
                seen_path = True
        self.assertTrue(
            seen_path,
            "random_walk produced no valid path across 12 small 5x5 fixtures",
        )


if __name__ == "__main__":
    unittest.main()
