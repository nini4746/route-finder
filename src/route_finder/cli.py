"""CLI argument parsing for ``python -m route_finder``.

Separated from ``app.py`` so the parser can be imported and tested without
pygame installed. ``app.py`` re-exports the same names for backward
compatibility.

Positional args (all optional, in this order):
    width   logical maze width  in [MIN_MAZE_DIM, MAX_MAZE_DIM]
    height  logical maze height in [MIN_MAZE_DIM, MAX_MAZE_DIM]
    seed    PRNG seed           non-negative integer

Flag:
    --debug  after each maze generation, assert is_perfect_maze.

Errors exit non-zero via argparse.
"""

from __future__ import annotations

import argparse

from .maze import MAX_MAZE_DIM, MIN_MAZE_DIM

# Default UI / maze sizes. Kept here (not in app.py) so they can be imported
# without pulling pygame. ``app.py`` re-exports them.
DEFAULT_W, DEFAULT_H = 1100, 720
DEFAULT_MAZE_W, DEFAULT_MAZE_H = 60, 40


def _dim_int(value: str) -> int:
    """argparse type=fn: validate w/h are in [MIN_MAZE_DIM, MAX_MAZE_DIM]."""
    try:
        iv = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            f"must be an integer (got {value!r})"
        )
    if iv < MIN_MAZE_DIM or iv > MAX_MAZE_DIM:
        raise argparse.ArgumentTypeError(
            f"must be in [{MIN_MAZE_DIM}, {MAX_MAZE_DIM}] (got {iv})"
        )
    return iv


def _seed_int(value: str) -> int:
    """argparse type=fn: validate seed is a non-negative integer."""
    try:
        iv = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            f"seed must be an integer (got {value!r})"
        )
    if iv < 0:
        raise argparse.ArgumentTypeError(f"seed must be >= 0 (got {iv})")
    return iv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="route_finder",
        description=(
            "Generate a perfect maze with DFS Backtracker and visualize "
            "six pathfinders one at a time."
        ),
    )
    parser.add_argument(
        "width",
        nargs="?",
        type=_dim_int,
        default=DEFAULT_MAZE_W,
        help=(
            f"logical maze width in cells [{MIN_MAZE_DIM}, {MAX_MAZE_DIM}] "
            f"(default {DEFAULT_MAZE_W})"
        ),
    )
    parser.add_argument(
        "height",
        nargs="?",
        type=_dim_int,
        default=DEFAULT_MAZE_H,
        help=(
            f"logical maze height in cells [{MIN_MAZE_DIM}, {MAX_MAZE_DIM}] "
            f"(default {DEFAULT_MAZE_H})"
        ),
    )
    parser.add_argument(
        "seed",
        nargs="?",
        type=_seed_int,
        default=None,
        help=(
            "PRNG seed (non-negative int); if omitted a random seed is drawn "
            "from os.urandom"
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="post-generation assert is_perfect_maze (slow on 1000x1000)",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the route-finder CLI. See module docstring."""
    return build_parser().parse_args(argv)
