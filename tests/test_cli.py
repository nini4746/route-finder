"""v3 UX-C: argparse-driven CLI tests.

Covers:
  - default behavior with no positional args
  - width-only, width+height, width+height+seed
  - rejection of below-MIN, above-MAX, non-int width
  - seed determinism: same seed -> identical maze, identical A/B
"""

from __future__ import annotations

import contextlib
import io
import random
import unittest

from route_finder.cli import parse_args, DEFAULT_MAZE_W, DEFAULT_MAZE_H
from route_finder.maze import (
    MAX_MAZE_DIM,
    MIN_MAZE_DIM,
    Maze,
    generate_maze,
    pick_endpoints,
)


def _parse_expecting_exit(argv: list[str]) -> SystemExit:
    """Helper: invoke parse_args and capture its argparse error output so
    test runs aren't polluted with usage messages. Returns the raised
    SystemExit so callers can inspect ``code``.
    """
    err_buf = io.StringIO()
    out_buf = io.StringIO()
    with contextlib.redirect_stderr(err_buf), contextlib.redirect_stdout(out_buf):
        try:
            parse_args(argv)
        except SystemExit as exc:
            return exc
    raise AssertionError(
        f"parse_args({argv!r}) did not exit (returned normally); "
        f"captured stderr={err_buf.getvalue()!r}"
    )


def _build_with_seed(w: int, h: int, seed: int):
    """Mirror App.start_new_maze's plumbing: one Random per (seed)."""
    rng = random.Random(seed)
    maze = Maze(w, h)
    gen = generate_maze(w, h, rng=rng, maze=maze)
    for _ in gen:
        pass
    a, b = pick_endpoints(maze, rng=rng)
    return maze, a, b


class CLIParseTests(unittest.TestCase):
    def test_defaults_when_no_args(self) -> None:
        ns = parse_args([])
        self.assertEqual(ns.width, DEFAULT_MAZE_W)
        self.assertEqual(ns.height, DEFAULT_MAZE_H)
        self.assertIsNone(ns.seed)
        self.assertFalse(ns.debug)

    def test_width_only(self) -> None:
        ns = parse_args(["50"])
        self.assertEqual(ns.width, 50)
        self.assertEqual(ns.height, DEFAULT_MAZE_H)
        self.assertIsNone(ns.seed)

    def test_width_and_height(self) -> None:
        ns = parse_args(["50", "30"])
        self.assertEqual(ns.width, 50)
        self.assertEqual(ns.height, 30)
        self.assertIsNone(ns.seed)

    def test_width_height_seed(self) -> None:
        ns = parse_args(["50", "30", "42"])
        self.assertEqual(ns.width, 50)
        self.assertEqual(ns.height, 30)
        self.assertEqual(ns.seed, 42)

    def test_debug_flag(self) -> None:
        ns = parse_args(["--debug", "10", "10", "0"])
        self.assertTrue(ns.debug)
        self.assertEqual(ns.width, 10)
        self.assertEqual(ns.height, 10)
        self.assertEqual(ns.seed, 0)

    def test_below_min_rejected(self) -> None:
        # MIN_MAZE_DIM is 2; a width of 1 is below the floor.
        self.assertGreaterEqual(MIN_MAZE_DIM, 2)
        exc = _parse_expecting_exit(["1"])
        self.assertNotEqual(exc.code, 0)

    def test_above_max_rejected(self) -> None:
        # MAX_MAZE_DIM is 1000; anything strictly greater is invalid.
        exc = _parse_expecting_exit([str(MAX_MAZE_DIM + 1)])
        self.assertNotEqual(exc.code, 0)

    def test_non_int_rejected(self) -> None:
        exc = _parse_expecting_exit(["abc"])
        self.assertNotEqual(exc.code, 0)

    def test_negative_seed_rejected(self) -> None:
        exc = _parse_expecting_exit(["10", "10", "-1"])
        self.assertNotEqual(exc.code, 0)

    def test_non_int_seed_rejected(self) -> None:
        exc = _parse_expecting_exit(["10", "10", "abc"])
        self.assertNotEqual(exc.code, 0)


class SeedDeterminismTests(unittest.TestCase):
    """Same seed must reproduce the same maze + endpoints."""

    def test_same_seed_identical_maze_and_endpoints(self) -> None:
        for size in [(20, 15), (30, 20), (40, 30)]:
            for seed in (0, 1, 42, 12345):
                with self.subTest(size=size, seed=seed):
                    w, h = size
                    m1, a1, b1 = _build_with_seed(w, h, seed)
                    m2, a2, b2 = _build_with_seed(w, h, seed)
                    self.assertEqual(
                        bytes(m1.walls),
                        bytes(m2.walls),
                        f"seed={seed} produced different walls",
                    )
                    self.assertEqual(a1, a2, f"seed={seed} produced different A")
                    self.assertEqual(b1, b2, f"seed={seed} produced different B")

    def test_different_seeds_usually_differ(self) -> None:
        """Sanity: different seeds should produce different mazes (at least
        for one of the seed pairs we try). This guards against the seed
        being silently ignored in plumbing."""
        w, h = 20, 15
        m1, _, _ = _build_with_seed(w, h, 1)
        differs = False
        for s in (2, 3, 4, 5, 6, 7):
            m2, _, _ = _build_with_seed(w, h, s)
            if bytes(m1.walls) != bytes(m2.walls):
                differs = True
                break
        self.assertTrue(
            differs,
            "different seeds all produced identical mazes — seed plumbing broken?",
        )


if __name__ == "__main__":
    unittest.main()
