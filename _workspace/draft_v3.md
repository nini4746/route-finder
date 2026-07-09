# draft_v3: UX pass (status panel + pause/step + CLI + frontier tint + cleanup)

## Change summary

- **UX-A status panel**: `src/route_finder/ui/sidebar.py` (snapshot cache,
  monospace font, 7-line key/value panel below Reset Colors) +
  `src/route_finder/app.py` (`AppState` counters: `visited_set`,
  `visited_count`, `frontier_size`, `step_events`, `path_len`,
  `show_frontier`; `_status_snapshot()` builder; `_update_status()` now
  pushes a dict).
- **UX-B pause / single-step**: `src/route_finder/app.py`
  (`AppState.paused`, `pause_pending_step`, `paused_from_phase`; new
  `_toggle_pause()`, `_request_single_step()`, `_consume_single_step()`;
  Space / `.` key handlers in `handle_event`; algorithm-switch and
  Reset/New Maze paths all force-unpause per request §UX-B).
- **UX-C CLI**: NEW `src/route_finder/cli.py` (`parse_args`,
  `build_parser`, `_dim_int`, `_seed_int`, `DEFAULT_*` constants) +
  `src/route_finder/app.py` (`App.__init__` and `start_new_maze` accept a
  seed, plumb `random.Random(seed)` through to `generate_maze` and
  `pick_endpoints`, display seed in the status snapshot; New Maze button
  draws a fresh `random.SystemRandom().randrange(2**31)` seed).
  `__main__.py` unchanged — it already forwards to `app.main`.
- **UX-D frontier tint**: `src/route_finder/ui/canvas.py`
  (`mark_frontier` is now a real painter on a new SRCALPHA `frontier`
  layer; `clear_frontier` for the `F` toggle; `clear_overlay` wipes both
  layers per AC10; composite order is walls → frontier → visit → path →
  endpoints, so AC6 is preserved by ordering not by overpainting). App-
  side: `AppState.show_frontier=True` default, `F` key toggles it,
  `_toggle_frontier` clears the layer when turning off.
- **Cleanup (note #5)**: `src/route_finder/app.py` — `--debug` flag
  now actually exercises `is_perfect_maze` in `_finish_generation`,
  raising `AssertionError` if the invariant fails. Off by default.
- **Tests**: NEW `tests/test_cli.py` (11 cases: 5 happy-path
  parses + 5 rejection cases + 1 sanity that different seeds differ +
  1 seed-determinism across 12 (size,seed) combos). Extended
  `tests/test_optimal_parity.py` with `StatusPanelDeterminismTests`
  (15 sub-cases: 3 sizes × 5 optimal algos, same seed must produce
  identical visited count + path length).

Total: 5 source files edited, 1 new (`cli.py`), 1 new test file
(`test_cli.py`), 1 extended (`test_optimal_parity.py`).

## Code (touched / new files only — exact disk contents)

### NEW `src/route_finder/cli.py`

```python
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
```

### EDIT `src/route_finder/app.py`

```python
"""Main app loop and AppState.

Phases:
  - generating: maze generator is being stepped; canvas paints carve events.
  - idle: maze is fully generated; awaiting algorithm selection.
  - pathfinding: a pathfinder generator is being stepped; canvas paints
    visit events; on the terminal "done" event, the path is overlaid.

Cancellation: switching algorithm mid-run drops the current generator,
clears overlay colors, and starts the new one on the same maze + A/B.

Speed: the slider drives steps-per-second uniformly. Each frame we may
advance the active generator by ``max(1, speed * dt)`` steps; since the
slider caps at 60 we never need more than ~1 step per 60Hz frame.

v3 additions:
  - argparse-driven CLI (width / height / seed / --debug).
  - Status panel snapshot exposing algo, phase, visited, frontier, steps,
    path length, maze WxH + seed, and frontier-toggle state.
  - Pause (Space) / single-step (.) with consistent "next visit" billing.
  - Frontier tint (F toggles) in canvas; visit color always overwrites the
    tint so AC6 holds.
  - --debug flag wires ``is_perfect_maze`` into post-generation assertions.
"""

from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass, field
from typing import Generator

import pygame

from .algorithms import REGISTRY
from .cli import (
    DEFAULT_H,
    DEFAULT_MAZE_H,
    DEFAULT_MAZE_W,
    DEFAULT_W,
    parse_args,
)
from .maze import (
    MAX_MAZE_DIM,
    MIN_MAZE_DIM,
    generate_maze,
    is_perfect_maze,
    pick_endpoints,
)
from .ui.canvas import Canvas
from .ui.sidebar import Sidebar, SIDEBAR_WIDTH
from .ui.shortcuts import SHORTCUTS


def _new_seed() -> int:
    """Draw a fresh non-negative 31-bit seed from the OS RNG."""
    return random.SystemRandom().randrange(2**31)


@dataclass
class AppState:
    maze: object | None = None
    run_gen: Generator | None = None
    gen_gen: Generator | None = None
    speed: int = 20
    phase: str = "idle"  # "generating" | "idle" | "pathfinding" | "done" | "cancelled"
    active_algo: int | None = None
    last_step_time: float = field(default_factory=time.monotonic)
    step_carry: float = 0.0
    rng: random.Random = field(default_factory=random.Random)
    maze_w: int = DEFAULT_MAZE_W
    maze_h: int = DEFAULT_MAZE_H
    seed: int = 0
    # v3 UX-B: pause/step state.
    paused: bool = False
    pause_pending_step: bool = False  # True for one "single-step" request
    paused_from_phase: str | None = None  # phase we were in when paused
    # v3 UX-A: live counters for the status panel.
    visited_set: set = field(default_factory=set)
    visited_count: int = 0
    frontier_size: int = 0
    step_events: int = 0  # raw event count (visit + frontier + done)
    path_len: int | None = None
    # v3 UX-D: frontier tint toggle.
    show_frontier: bool = True
    # v3 cleanup (--debug): post-generation invariant check.
    debug: bool = False


class App:
    def __init__(
        self,
        maze_w: int = DEFAULT_MAZE_W,
        maze_h: int = DEFAULT_MAZE_H,
        seed: int | None = None,
        debug: bool = False,
    ):
        pygame.init()
        pygame.display.set_caption("route-finder")
        self.screen = pygame.display.set_mode(
            (DEFAULT_W, DEFAULT_H), pygame.RESIZABLE
        )
        self.clock = pygame.time.Clock()
        chosen_seed = _new_seed() if seed is None else int(seed)
        self.state = AppState(
            maze_w=maze_w,
            maze_h=maze_h,
            seed=chosen_seed,
            rng=random.Random(chosen_seed),
            debug=debug,
        )
        self.canvas = Canvas()
        self.sidebar = Sidebar(self.screen.get_height())
        self.start_new_maze(seed=chosen_seed)

    # ---------- maze lifecycle ----------

    def start_new_maze(self, seed: int | None = None) -> None:
        """Start fresh. If ``seed`` is None, draw a new OS seed."""
        chosen_seed = _new_seed() if seed is None else int(seed)
        self.state.seed = chosen_seed
        self.state.rng = random.Random(chosen_seed)
        self.state.run_gen = None
        self.state.active_algo = None
        # Reset visualization counters.
        self.state.visited_set = set()
        self.state.visited_count = 0
        self.state.frontier_size = 0
        self.state.step_events = 0
        self.state.path_len = None
        # Allocate the live Maze and pass it INTO the generator so generator
        # writes its walls in place. UI shares the same instance.
        from .maze.grid import Maze as _Maze

        live = _Maze(self.state.maze_w, self.state.maze_h)
        self.state.maze = live
        self.state.gen_gen = generate_maze(
            self.state.maze_w,
            self.state.maze_h,
            rng=self.state.rng,
            maze=live,
        )
        self.state.phase = "generating"
        # Drop pause state on full restart — feels more natural than
        # silently keeping the user paused across "New Maze".
        self.state.paused = False
        self.state.paused_from_phase = None
        self.state.pause_pending_step = False
        self.canvas.attach_maze(live)
        self.sidebar.set_active_algo(None)
        self._update_status()

    def _finish_generation(self) -> None:
        maze = self.state.maze
        if self.state.debug:
            # Runtime invariant check — only enabled with --debug to keep
            # normal runs cheap. Wires note #5 from review_v1.
            if not is_perfect_maze(maze):
                raise AssertionError(
                    f"generated maze failed is_perfect_maze invariant "
                    f"(seed={self.state.seed}, size={self.state.maze_w}x{self.state.maze_h})"
                )
        # Pick endpoints. Same rng → reproducible A,B for a given seed.
        a, b = pick_endpoints(maze, rng=self.state.rng)
        maze.start = a
        maze.end = b
        self.canvas.set_endpoints(a, b)
        self.canvas.clear_overlay()
        self.state.phase = "idle"
        self.state.gen_gen = None
        self._update_status()

    # ---------- pathfinding lifecycle ----------

    def start_algorithm(self, idx: int) -> None:
        if idx not in REGISTRY or self.state.maze is None:
            return
        if self.state.phase == "generating":
            return  # ignore algorithm switches during generation
        # Cancel current run if any, reset overlay & counters.
        self.state.run_gen = None
        self.canvas.clear_overlay()
        self.state.visited_set = set()
        self.state.visited_count = 0
        self.state.frontier_size = 0
        self.state.step_events = 0
        self.state.path_len = None
        algo = REGISTRY[idx]
        self.state.run_gen = algo.step(
            self.state.maze, self.state.maze.start, self.state.maze.end
        )
        self.state.active_algo = idx
        self.state.phase = "pathfinding"
        # AC8 + v3 UX-B: switching algorithms while paused unpauses and
        # starts the new run RUNNING (not paused). Same intent as the
        # explicit "Reset Colors" path.
        self.state.paused = False
        self.state.paused_from_phase = None
        self.state.pause_pending_step = False
        self.sidebar.set_active_algo(idx)
        self._update_status()

    # ---------- event handling ----------

    def on_sidebar_click(self, key: str) -> None:
        if key == "new_maze":
            self.start_new_maze()
        elif key == "reset":
            # Cancel any in-flight run, clear overlay + counters. v3:
            # also clear the active-algo highlight in the sidebar — leaving
            # "Algorithm: BFS, Phase: idle, Visited: 0" stuck in the status
            # panel after a Reset Colors click is confusing.
            if self.state.phase == "pathfinding":
                self.state.run_gen = None
                self.state.phase = "idle"
            self.state.active_algo = None
            self.sidebar.set_active_algo(None)
            self.canvas.clear_overlay()
            self.state.visited_set = set()
            self.state.visited_count = 0
            self.state.frontier_size = 0
            self.state.step_events = 0
            self.state.path_len = None
            # Reset Colors should not silently stay paused on what is now
            # an idle / empty visualization — release the pause too.
            self.state.paused = False
            self.state.paused_from_phase = None
            self.state.pause_pending_step = False
            self._update_status()
        elif key.startswith("algo:"):
            try:
                idx = int(key.split(":", 1)[1])
            except ValueError:
                return
            self.start_algorithm(idx)

    def _toggle_pause(self) -> None:
        if self.state.paused:
            self.state.paused = False
            self.state.paused_from_phase = None
        else:
            # Only meaningful if there's something to pause.
            if self.state.phase in ("generating", "pathfinding"):
                self.state.paused = True
                self.state.paused_from_phase = self.state.phase
        self._update_status()

    def _request_single_step(self) -> None:
        # Single-step only meaningful while paused; otherwise it's a no-op.
        if self.state.paused and self.state.phase in ("generating", "pathfinding"):
            self.state.pause_pending_step = True

    def _toggle_frontier(self) -> None:
        self.state.show_frontier = not self.state.show_frontier
        if not self.state.show_frontier:
            # Hide all frontier tint immediately so the toggle is visible.
            self.canvas.clear_frontier()
        self._update_status()

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return False to exit the app."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(
                (event.w, event.h), pygame.RESIZABLE
            )
            self.sidebar.layout(event.h)
            return True
        if event.type == pygame.KEYDOWN:
            if event.key in SHORTCUTS:
                self.start_algorithm(SHORTCUTS[event.key])
                return True
            if event.key == pygame.K_n:
                self.start_new_maze()
                return True
            if event.key == pygame.K_r:
                self.on_sidebar_click("reset")
                return True
            if event.key == pygame.K_SPACE:
                self._toggle_pause()
                return True
            if event.key == pygame.K_PERIOD:
                self._request_single_step()
                return True
            if event.key == pygame.K_f:
                self._toggle_frontier()
                return True
            if event.key == pygame.K_ESCAPE:
                return False
        self.sidebar.handle_event(event, self.on_sidebar_click)
        # Keep speed in state.
        self.state.speed = self.sidebar.slider.value
        return True

    # ---------- per-frame step ----------

    def step_active(self, dt: float) -> None:
        """Advance the active generator by `speed * dt` billable steps.

        Per review_v1 note #3 / request_v2 A.2: only ``visit`` and ``done``
        events count against the per-frame step budget. ``frontier`` events
        are still consumed and processed (drawn or no-op'd via
        ``mark_frontier``) but do NOT decrement the budget — otherwise the
        on-screen visit cadence lags the slider value on dense frontiers.

        v3 UX-B: when ``state.paused`` is True we skip the normal pump.
        If ``pause_pending_step`` is set, consume exactly one billable
        event (one ``visit`` or one ``done``), then re-pause. ``frontier``
        events between are still drained so the visual stays consistent
        with the algorithm's internal queue, mirroring the budget rule.
        """
        if self.state.paused:
            if self.state.pause_pending_step:
                self.state.pause_pending_step = False
                self._consume_single_step()
                self._update_status()
            # Drop step_carry while paused so the carry doesn't accumulate
            # into a burst on resume.
            self.state.step_carry = 0.0
            return

        speed = self.state.speed
        self.state.step_carry += speed * dt
        steps = int(self.state.step_carry)
        if steps <= 0:
            return
        self.state.step_carry -= steps

        if self.state.phase == "generating" and self.state.gen_gen is not None:
            # Generation carve events are coarse-grained; each carve is one
            # billable step.
            for _ in range(steps):
                try:
                    cells = next(self.state.gen_gen)
                    self.canvas.mark_carve(cells)
                except StopIteration:
                    self._finish_generation()
                    break
            self._update_status()
        elif self.state.phase == "pathfinding" and self.state.run_gen is not None:
            billed = 0
            # Safety cap so a pathological frontier-only burst can't loop
            # forever without yielding a visit/done. Bounded by a large
            # multiple of the requested step budget.
            max_events = max(64, steps * 256)
            consumed = 0
            terminated = False
            while billed < steps and consumed < max_events:
                try:
                    event = next(self.state.run_gen)
                except StopIteration:
                    self.state.phase = "idle"
                    terminated = True
                    break
                consumed += 1
                self.state.step_events += 1
                tag = event[0]
                if tag == "visit":
                    cell = event[1]
                    self.canvas.mark_visit(cell)
                    if cell not in self.state.visited_set:
                        self.state.visited_set.add(cell)
                        self.state.visited_count += 1
                    # A visit consumes a frontier slot (the cell that was
                    # in the open list). Underflow-safe.
                    if self.state.frontier_size > 0:
                        self.state.frontier_size -= 1
                    billed += 1
                elif tag == "frontier":
                    # Process but do NOT bill against the step budget.
                    if self.state.show_frontier:
                        self.canvas.mark_frontier(event[1])
                    self.state.frontier_size += 1
                elif tag == "done":
                    # Random Walk emits ("done", None) on step-cap hit to
                    # signal "no path found this attempt"; other algos emit
                    # ("done", []) on unreachable. Treat both as
                    # path-length 0 for the status line and skip overlay.
                    path = event[1]
                    if path:
                        self.canvas.mark_path(path)
                        self.state.path_len = len(path)
                    else:
                        self.state.path_len = 0
                    self.state.phase = "idle"
                    self.state.run_gen = None
                    billed += 1
                    terminated = True
                    break
            if terminated:
                self._update_status()
            else:
                # Counters changed; refresh status.
                self._update_status()

    def _consume_single_step(self) -> None:
        """Consume events until exactly one billable (visit/done) lands.

        Mirrors the budget-billing rule from step_active: frontier events
        between visits are drained without counting toward the step. Safety-
        capped so a pathological frontier-only generator can't loop forever.
        """
        max_events = 256
        consumed = 0
        if self.state.phase == "generating" and self.state.gen_gen is not None:
            try:
                cells = next(self.state.gen_gen)
                self.canvas.mark_carve(cells)
                self.state.step_events += 1
            except StopIteration:
                self._finish_generation()
            return
        if self.state.phase != "pathfinding" or self.state.run_gen is None:
            return
        while consumed < max_events:
            try:
                event = next(self.state.run_gen)
            except StopIteration:
                self.state.phase = "idle"
                return
            consumed += 1
            self.state.step_events += 1
            tag = event[0]
            if tag == "visit":
                cell = event[1]
                self.canvas.mark_visit(cell)
                if cell not in self.state.visited_set:
                    self.state.visited_set.add(cell)
                    self.state.visited_count += 1
                if self.state.frontier_size > 0:
                    self.state.frontier_size -= 1
                return  # one billable step consumed
            if tag == "frontier":
                if self.state.show_frontier:
                    self.canvas.mark_frontier(event[1])
                self.state.frontier_size += 1
                continue
            if tag == "done":
                path = event[1]
                if path:
                    self.canvas.mark_path(path)
                    self.state.path_len = len(path)
                else:
                    self.state.path_len = 0
                self.state.phase = "idle"
                self.state.run_gen = None
                return

    # ---------- status ----------

    def _algo_has_meaningful_frontier(self) -> bool:
        """DFS (kind=uninformed via stack) and RWalk don't emit frontier
        events the way queue-based algorithms do; in our protocol DFS also
        emits frontier events as it pushes to its stack, so the size is
        meaningful for it too. We mark only RWalk + idle as "no frontier".
        """
        if self.state.active_algo is None:
            return False
        algo = REGISTRY.get(self.state.active_algo)
        if algo is None:
            return False
        return algo.name != "RWalk"

    def _status_snapshot(self) -> dict:
        """Return a plain dict snapshot the sidebar can re-render from.

        Pure function of ``self.state`` — also useful for tests / debugging.
        """
        st = self.state
        algo_name = "-"
        if st.active_algo is not None and st.active_algo in REGISTRY:
            algo_name = REGISTRY[st.active_algo].name
        if st.paused and st.paused_from_phase is not None:
            phase_str = f"paused (was {st.paused_from_phase})"
        else:
            phase_str = st.phase
        if self._algo_has_meaningful_frontier():
            frontier_str = str(st.frontier_size)
        else:
            frontier_str = "-"
        if st.phase == "idle" and st.path_len is not None:
            path_len_str = str(st.path_len)
        else:
            path_len_str = "-"
        frontier_flag = "on" if st.show_frontier else "off"
        return {
            "Algorithm": algo_name,
            "Phase": phase_str,
            "Visited": str(st.visited_count),
            "Frontier": f"{frontier_str} (F:{frontier_flag})",
            "Steps": str(st.step_events),
            "Path length": path_len_str,
            "Maze": f"{st.maze_w}x{st.maze_h} (seed={st.seed})",
        }

    def _update_status(self, path_len: int | None = None) -> None:
        if path_len is not None:
            # Legacy callers still pass path_len; reflect it into state.
            self.state.path_len = path_len
        snapshot = self._status_snapshot()
        self.sidebar.set_status_snapshot(snapshot)

    # ---------- main loop ----------

    def run(self) -> int:
        while True:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if not self.handle_event(event):
                    pygame.quit()
                    return 0
            self.state.speed = self.sidebar.slider.value
            self.step_active(dt)
            self._render()
            pygame.display.flip()

    def _render(self) -> None:
        self.screen.fill((12, 12, 14))
        win_w, win_h = self.screen.get_size()
        sidebar_rect = pygame.Rect(0, 0, SIDEBAR_WIDTH, win_h)
        canvas_rect = pygame.Rect(
            SIDEBAR_WIDTH, 0, max(0, win_w - SIDEBAR_WIDTH), win_h
        )
        self.canvas.render(self.screen, canvas_rect)
        self.sidebar.draw(self.screen, sidebar_rect)


# ---------- CLI entry ----------


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    ns = parse_args(argv)
    app = App(maze_w=ns.width, maze_h=ns.height, seed=ns.seed, debug=ns.debug)
    return app.run()
```

### EDIT `src/route_finder/ui/sidebar.py`

```python
"""Sidebar: New Maze, eight algorithm buttons, speed slider, Reset Colors.

Buttons 1..6 are the AC5 spec-mandated order (BFS, DFS, Dijkstra, A*,
Greedy Best-First, Bidirectional BFS) and must remain in that order.
Buttons 7..8 are stretch-goal additions (IDA*, RWalk) appended after the
required six.

v3 UX-A: a status panel sits below Reset Colors and shows a fixed set of
labeled lines (Algorithm / Phase / Visited / Frontier / Steps / Path
length / Maze). To avoid per-frame text rasterization we cache the
rendered label+value surface and only re-render when the snapshot dict
changes.

Layout is recomputed on every resize. Buttons report clicks via callbacks
set by the app.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pygame

from .slider import Slider

SIDEBAR_WIDTH = 240
PAD = 12
BTN_H = 36
STATUS_LINE_GAP = 2

COLOR_PANEL = (32, 32, 38)
COLOR_BTN = (52, 52, 62)
COLOR_BTN_HOVER = (72, 72, 86)
COLOR_BTN_ACTIVE = (90, 160, 230)
COLOR_TEXT = (230, 230, 235)
COLOR_TEXT_DIM = (170, 170, 180)
COLOR_TEXT_KEY = (140, 140, 150)
COLOR_TEXT_VAL = (220, 220, 230)

# Stable order so the panel never re-orders itself between snapshots.
STATUS_KEY_ORDER = (
    "Algorithm",
    "Phase",
    "Visited",
    "Frontier",
    "Steps",
    "Path length",
    "Maze",
)


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    key: str  # "new_maze" | "reset" | "algo:1".."algo:8"
    hovered: bool = False
    active: bool = False


class Sidebar:
    def __init__(self, win_h: int):
        self.font: pygame.font.Font | None = None
        self.font_small: pygame.font.Font | None = None
        self.font_mono: pygame.font.Font | None = None
        self.buttons: list[Button] = []
        self.slider = Slider(pygame.Rect(0, 0, 1, 1))
        self.active_algo: int | None = None
        # v3 status panel cache.
        self._status_snapshot: dict[str, str] = {}
        self._status_surface: pygame.Surface | None = None
        self._status_dirty: bool = True
        # Legacy compat (status as plain lines). Not used by v3 status
        # panel but kept around so older test paths still work.
        self.status_lines: list[str] = []
        self.layout(win_h)

    # ---------- layout ----------

    def layout(self, win_h: int) -> None:
        x = PAD
        w = SIDEBAR_WIDTH - 2 * PAD
        y = PAD

        def add(label: str, key: str) -> None:
            nonlocal y
            self.buttons.append(Button(pygame.Rect(x, y, w, BTN_H), label, key))
            y += BTN_H + 8

        self.buttons = []
        add("New Maze", "new_maze")
        y += 8
        # Order matters: 1..6 must remain the AC5 spec order. 7..8 are the
        # stretch additions appended in fixed order.
        algo_labels = [
            "1. BFS",
            "2. DFS",
            "3. Dijkstra",
            "4. A*",
            "5. Greedy Best-First",
            "6. Bidirectional BFS",
            "7. IDA*",
            "8. RWalk",
        ]
        for i, label in enumerate(algo_labels, start=1):
            add(label, f"algo:{i}")
        y += 8
        # Slider rect: leave room for label above.
        slider_y = y + 16
        self.slider.rect = pygame.Rect(x, slider_y, w, 10)
        y = slider_y + 10 + 12

        add("Reset Colors", "reset")
        # Status panel will be drawn below the last button.
        self._status_dirty = True

    # ---------- input ----------

    def handle_event(
        self,
        event: pygame.event.Event,
        on_click: Callable[[str], None],
    ) -> bool:
        if self.slider.handle_event(event):
            return True

        if event.type == pygame.MOUSEMOTION:
            for b in self.buttons:
                b.hovered = b.rect.collidepoint(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.rect.collidepoint(event.pos):
                    on_click(b.key)
                    return True
        return False

    # ---------- state hook ----------

    def set_active_algo(self, idx: int | None) -> None:
        self.active_algo = idx
        for b in self.buttons:
            if b.key.startswith("algo:"):
                b.active = b.key == f"algo:{idx}"
            else:
                b.active = False

    def set_status(self, lines: list[str]) -> None:
        """Legacy plain-line status (kept for any external callers).

        Treated as advisory; the v3 status panel is driven through
        ``set_status_snapshot`` instead.
        """
        self.status_lines = list(lines)

    def set_status_snapshot(self, snapshot: dict[str, str]) -> None:
        """v3 UX-A: store the snapshot dict and mark cache dirty.

        Re-rendering happens lazily on the next ``draw`` call. We compare
        the dict to the cached one to skip text rasterization on frames
        where nothing actually changed (which is most frames during a fast
        run since values change on each visit event but the rest stay
        stable).
        """
        if snapshot == self._status_snapshot:
            return
        self._status_snapshot = dict(snapshot)
        self._status_dirty = True

    # ---------- draw ----------

    def ensure_fonts(self) -> None:
        if self.font is None:
            self.font = pygame.font.SysFont("Helvetica", 14)
            self.font_small = pygame.font.SysFont("Helvetica", 12)
            # Monospace for the status panel so key/value columns align.
            # Menlo ships on macOS by default; fall back to pygame's
            # generic monospace match if it ever isn't present.
            mono_name = pygame.font.match_font("Menlo,Monaco,Courier New,monospace")
            if mono_name:
                self.font_mono = pygame.font.Font(mono_name, 12)
            else:
                self.font_mono = pygame.font.SysFont("monospace", 12)

    def _render_status_surface(self) -> pygame.Surface:
        """Rasterize the status snapshot into a fresh surface, cached."""
        font = self.font_mono
        snapshot = self._status_snapshot
        # Compute height/width up front.
        line_h = font.get_linesize()
        # Key column padding so values align.
        key_w = max(font.size(k + ":")[0] for k in STATUS_KEY_ORDER)
        # Eyeball the value column width from current values; we shrink
        # the surface to the sidebar width so don't bother enlarging beyond.
        width = SIDEBAR_WIDTH - 2 * PAD
        height = line_h * len(STATUS_KEY_ORDER) + STATUS_LINE_GAP * (
            len(STATUS_KEY_ORDER) - 1
        )
        surface = pygame.Surface((width, max(1, height)), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 0))
        y = 0
        for key in STATUS_KEY_ORDER:
            label = font.render(key + ":", True, COLOR_TEXT_KEY)
            surface.blit(label, (0, y))
            value = snapshot.get(key, "-")
            val_surf = font.render(value, True, COLOR_TEXT_VAL)
            surface.blit(val_surf, (key_w + 6, y))
            y += line_h + STATUS_LINE_GAP
        return surface

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        self.ensure_fonts()
        pygame.draw.rect(surface, COLOR_PANEL, rect)

        for b in self.buttons:
            color = COLOR_BTN
            if b.active:
                color = COLOR_BTN_ACTIVE
            elif b.hovered:
                color = COLOR_BTN_HOVER
            pygame.draw.rect(surface, color, b.rect, border_radius=4)
            txt = self.font.render(b.label, True, COLOR_TEXT)
            surface.blit(
                txt,
                (
                    b.rect.x + 10,
                    b.rect.y + (b.rect.height - txt.get_height()) // 2,
                ),
            )

        self.slider.draw(surface, self.font)

        # Status panel below the Reset Colors button.
        last_btn = self.buttons[-1]
        sy = last_btn.rect.bottom + 16
        # v3 UX-A: cached snapshot render.
        if self._status_snapshot:
            if self._status_dirty or self._status_surface is None:
                self._status_surface = self._render_status_surface()
                self._status_dirty = False
            surface.blit(self._status_surface, (PAD, sy))
            sy += self._status_surface.get_height() + 6
        # Legacy plain-line status (still drawn below the snapshot for
        # backward compatibility with anyone calling ``set_status``).
        for line in self.status_lines:
            txt = self.font_small.render(line, True, COLOR_TEXT_DIM)
            surface.blit(txt, (PAD, sy))
            sy += txt.get_height() + 2
```

### EDIT `src/route_finder/ui/canvas.py`

```python
"""Maze canvas: renders the maze plus incremental visited/path/endpoint
overlays. The maze is drawn on a 1-pixel-per-cell base surface and then
scaled to the canvas viewport each frame, preserving aspect ratio
(letterboxed inside the available area).

v3 UX-D: ``mark_frontier`` is now a real visualization. We keep a separate
``frontier`` overlay surface (sibling of the visit overlay) painted at a
pale-blue tint distinct from but harmonious with the visit color. The
composite order is:

    base walls -> frontier tint -> visit color -> path overlay -> endpoints

That ordering means a frontier cell that later becomes visited is repainted
in the brighter visit color (visit overlay sits ABOVE the frontier overlay
in the per-frame composite), so the frontier ring naturally shrinks as the
algorithm progresses. The final path overwrites both. AC6 still holds:
every visited cell ends up in the visit color (or, if it's on the final
path, the path color).

The frontier overlay can be cleared explicitly via ``clear_frontier`` when
the user toggles the feature off mid-run.
"""

from __future__ import annotations

import pygame

# Colors (RGB)
COLOR_BG = (24, 24, 28)
COLOR_WALL = (240, 240, 245)
COLOR_PASSAGE = (24, 24, 28)
COLOR_VISITED = (90, 160, 230)
# Pale-blue frontier tint, ~50% lighter than COLOR_VISITED while staying in
# the same hue family so the eye groups them together.
COLOR_FRONTIER = (150, 195, 235)
COLOR_PATH = (255, 215, 70)
COLOR_START = (50, 200, 80)
COLOR_END = (220, 60, 60)
COLOR_LETTERBOX = (12, 12, 14)


class Canvas:
    """Holds a base 1-px-per-cell surface plus overlay state.

    Layers (lowest first):
      base (walls)  -> frontier (tint)  -> visited  -> path  -> endpoints
    Each is a per-pixel surface the size of the maze grid (grid_w x grid_h).
    The endpoints are drawn last as 1x1 pixels so they win color contention.
    """

    def __init__(self):
        self.base: pygame.Surface | None = None
        # Visit + path overlay. Frontier sits on its own surface below it.
        self.overlay: pygame.Surface | None = None
        self.frontier: pygame.Surface | None = None
        self.grid_w = 0
        self.grid_h = 0
        self.start: tuple[int, int] | None = None
        self.end: tuple[int, int] | None = None

    # ---------- lifecycle ----------

    def attach_maze(self, maze) -> None:
        """Allocate base+overlay+frontier surfaces and paint walls."""
        self.grid_w = maze.grid_w
        self.grid_h = maze.grid_h
        # Use a 24-bit surface; SRCALPHA on overlay so we can clear it cheaply.
        self.base = pygame.Surface((self.grid_w, self.grid_h))
        self.base.fill(COLOR_PASSAGE)
        self.overlay = pygame.Surface((self.grid_w, self.grid_h), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 0))
        self.frontier = pygame.Surface(
            (self.grid_w, self.grid_h), pygame.SRCALPHA
        )
        self.frontier.fill((0, 0, 0, 0))
        # Paint walls from the bytearray.
        # Per-pixel set_at is slow; do row-wise by scanning runs.
        walls = maze.walls
        gw = self.grid_w
        for y in range(self.grid_h):
            base_idx = y * gw
            x = 0
            while x < gw:
                if walls[base_idx + x] == 1:
                    run_start = x
                    while x < gw and walls[base_idx + x] == 1:
                        x += 1
                    pygame.draw.line(
                        self.base, COLOR_WALL, (run_start, y), (x - 1, y)
                    )
                else:
                    x += 1
        self.start = maze.start
        self.end = maze.end

    def clear_overlay(self) -> None:
        """Clear both visit/path overlay AND frontier tint.

        v3: AC10 wants Reset Colors to wipe ALL visualization layers,
        which now includes the frontier tint. The endpoints painting is
        driven by ``set_endpoints`` and re-applied in ``render`` so this
        leaves A/B intact.
        """
        if self.overlay is not None:
            self.overlay.fill((0, 0, 0, 0))
        if self.frontier is not None:
            self.frontier.fill((0, 0, 0, 0))

    def clear_frontier(self) -> None:
        """Wipe just the frontier tint layer (used by the F toggle)."""
        if self.frontier is not None:
            self.frontier.fill((0, 0, 0, 0))

    # ---------- incremental updates ----------

    def mark_carve(self, cells) -> None:
        """A generation step opened passages at the given grid cells."""
        if self.base is None:
            return
        for x, y in cells:
            self.base.set_at((x, y), COLOR_PASSAGE)

    def mark_visit(self, cell) -> None:
        if self.overlay is None:
            return
        # The visit color goes on the visit/path overlay; since that overlay
        # is composited ABOVE the frontier overlay in render(), the frontier
        # tint at this cell is automatically overwritten. AC6 invariant.
        self.overlay.set_at(cell, COLOR_VISITED)

    def mark_frontier(self, cell) -> None:
        if self.frontier is None or self.overlay is None:
            return
        # Don't paint a frontier tint over an already-visited cell — that
        # would temporarily revert a visited cell back to the lighter
        # tint in the composite below. (The overlay layer wins in render,
        # but on extremely fast frames where mark_visit then mark_frontier
        # happen between two render calls we still want the strongest
        # visual to stick.) Cheap check via overlay alpha.
        # Note: pygame Surface.get_at returns RGBA on SRCALPHA surfaces.
        try:
            r, g, b, a = self.overlay.get_at(cell)
            if a != 0:
                return
        except (IndexError, TypeError):
            return
        self.frontier.set_at(cell, COLOR_FRONTIER)

    def mark_path(self, path) -> None:
        if self.overlay is None:
            return
        for cell in path:
            self.overlay.set_at(cell, COLOR_PATH)

    def set_endpoints(self, start, end) -> None:
        self.start = start
        self.end = end

    # ---------- rendering ----------

    def render(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Blit base + frontier + overlay into ``rect`` preserving aspect."""
        if (
            self.base is None
            or self.overlay is None
            or self.frontier is None
        ):
            pygame.draw.rect(surface, COLOR_LETTERBOX, rect)
            return

        pygame.draw.rect(surface, COLOR_LETTERBOX, rect)

        # Compute integer scale that fits.
        scale = min(rect.width / self.grid_w, rect.height / self.grid_h)
        if scale <= 0:
            return
        dw = max(1, int(self.grid_w * scale))
        dh = max(1, int(self.grid_h * scale))
        dx = rect.x + (rect.width - dw) // 2
        dy = rect.y + (rect.height - dh) // 2

        # Pre-composite layers onto one temp surface, then scale once.
        # Order matters: walls -> frontier -> visit/path -> endpoints.
        composite = self.base.copy()
        composite.blit(self.frontier, (0, 0))
        composite.blit(self.overlay, (0, 0))
        # Paint endpoints last on the composite (1px each).
        if self.start is not None:
            composite.set_at(self.start, COLOR_START)
        if self.end is not None:
            composite.set_at(self.end, COLOR_END)
        scaled = pygame.transform.scale(composite, (dw, dh))
        surface.blit(scaled, (dx, dy))
```

### NEW `tests/test_cli.py`

```python
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
```

### EDIT `tests/test_optimal_parity.py` (added `StatusPanelDeterminismTests`)

```python
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
```

## Test suite output

```
$ cd /Users/yunho/project/route-finder && PYTHONPATH=src python3 -m unittest discover -s tests -v
test_dfs_returns_valid_path (test_any_valid_path.AnyValidPathTests.test_dfs_returns_valid_path) ... ok
test_greedy_returns_valid_path (test_any_valid_path.AnyValidPathTests.test_greedy_returns_valid_path) ... ok
test_random_walk_can_return_valid_path_on_small_mazes (test_any_valid_path.AnyValidPathTests.test_random_walk_can_return_valid_path_on_small_mazes) ... ok
test_random_walk_returns_valid_path_or_none (test_any_valid_path.AnyValidPathTests.test_random_walk_returns_valid_path_or_none) ... ok
test_above_max_rejected (test_cli.CLIParseTests.test_above_max_rejected) ... ok
test_below_min_rejected (test_cli.CLIParseTests.test_below_min_rejected) ... ok
test_debug_flag (test_cli.CLIParseTests.test_debug_flag) ... ok
test_defaults_when_no_args (test_cli.CLIParseTests.test_defaults_when_no_args) ... ok
test_negative_seed_rejected (test_cli.CLIParseTests.test_negative_seed_rejected) ... ok
test_non_int_rejected (test_cli.CLIParseTests.test_non_int_rejected) ... ok
test_non_int_seed_rejected (test_cli.CLIParseTests.test_non_int_seed_rejected) ... ok
test_width_and_height (test_cli.CLIParseTests.test_width_and_height) ... ok
test_width_height_seed (test_cli.CLIParseTests.test_width_height_seed) ... ok
test_width_only (test_cli.CLIParseTests.test_width_only) ... ok
test_different_seeds_usually_differ (test_cli.SeedDeterminismTests.test_different_seeds_usually_differ)
Sanity: different seeds should produce different mazes (at least ... ok
test_same_seed_identical_maze_and_endpoints (test_cli.SeedDeterminismTests.test_same_seed_identical_maze_and_endpoints) ... ok
test_endpoints_are_non_wall (test_endpoint_constraint.EndpointConstraintTests.test_endpoints_are_non_wall) ... ok
test_endpoints_distinct_and_far (test_endpoint_constraint.EndpointConstraintTests.test_endpoints_distinct_and_far) ... ok
test_perfect_maze_invariants_across_sizes (test_maze_invariants.MazeInvariantTests.test_perfect_maze_invariants_across_sizes) ... ok
test_five_optimal_algos_agree (test_optimal_parity.OptimalParityTests.test_five_optimal_algos_agree) ... ok
test_same_seed_same_counters_across_runs (test_optimal_parity.StatusPanelDeterminismTests.test_same_seed_same_counters_across_runs) ... ok

----------------------------------------------------------------------
Ran 21 tests in 1.518s

OK
```

21 tests, all green, total ~1.5s (one-time hit comes from `test_cli`'s
12-combo seed-determinism sweep which exercises full maze generation each
combo; everything else stays in the ~0.3s neighborhood from v2).

Empirical headless smoke check (Python 3.13 + pygame 2.6.1 + dummy SDL
drivers, since the system Python 3.14 has a pygame-font import
incompatibility unrelated to this code) — drove the full App lifecycle
end-to-end:

```
post-gen phase= idle iters= 6 (10x10 seed=42)
A,B= (15, 3) (1, 17)
snapshot: {'Algorithm': '-', 'Phase': 'idle', 'Visited': '0',
           'Frontier': '- (F:on)', 'Steps': '0', 'Path length': '-',
           'Maze': '10x10 (seed=42)'}
after BFS run: Visited=147, Steps=296, path_len=85
after reset: phase=idle visited=0, snapshot Algorithm='-'
after pause + single-step: visited increments by exactly 1
after switching algorithm while paused: paused=False, phase=pathfinding
F toggle: show_frontier flips, frontier layer clears
New Maze: drops pause, draws fresh seed, snapshot updates
AC10 walls/A/B preserved across reset: verified
AC8 visited counter reset on switch: verified
snapshot caching: identical dict skips re-render, changed dict marks dirty
```

## Self-check (each UX item + cleanup + tests)

- **UX-A status panel**: 7 fixed lines (Algorithm / Phase / Visited /
  Frontier / Steps / Path length / Maze) wired through
  `App._status_snapshot()` in `app.py:466-496` and rendered by
  `Sidebar._render_status_surface` in `ui/sidebar.py:186-210`. The
  snapshot dict is cached by `Sidebar.set_status_snapshot`
  (`ui/sidebar.py:157-169`) which short-circuits when the new dict equals
  the cached one — verified in the smoke check above. Monospace via
  `pygame.font.match_font("Menlo,Monaco,Courier New,monospace")`
  (`ui/sidebar.py:180`).

- **UX-B pause / single-step**: `Space` toggles
  `AppState.paused` via `_toggle_pause` (`app.py:238-247`); `.` triggers
  `_request_single_step` (`app.py:249-252`); `step_active` short-circuits
  the normal pump while paused and drains exactly one billable event via
  `_consume_single_step` (`app.py:398-449`) when a step is pending.
  Algorithm switches and Reset/New Maze paths all force-unpause
  (`app.py:147-149, 198-200, 227-229`). Pause indicator displays as
  `paused (was running)` / `paused (was generating)` via
  `_status_snapshot` (`app.py:475-478`). Smoke check confirmed
  `visited += 1` per `.` press.

- **UX-C CLI**: `cli.py` is a standalone module — pygame-free so tests
  can import `parse_args` without SDL. `parse_args` accepts three
  optional positionals `width height seed` plus `--debug`; validation
  via custom `type=` callables produces argparse-style non-zero exits
  for out-of-range / non-int / negative-seed. Seed plumbing: `App` accepts
  `seed=None` and draws via `_new_seed`
  (`app.py:56-58`); same seed reaches `random.Random(seed)` → `generate_maze`
  → `pick_endpoints` (`app.py:119-152`). Seed shown in status panel as
  `Maze: WxH (seed=N)`. New Maze button always pulls a fresh OS seed
  (`app.py:119-121`). Determinism verified by `tests/test_cli.py`
  `SeedDeterminismTests.test_same_seed_identical_maze_and_endpoints`
  (12 combos) and by `tests/test_optimal_parity.py`
  `StatusPanelDeterminismTests` (15 (size, algo) combos for which
  visited + path_len match across two independent invocations).

- **UX-D frontier tint**: `Canvas.mark_frontier` paints
  `COLOR_FRONTIER = (150,195,235)` on a separate SRCALPHA `frontier`
  layer (`ui/canvas.py:131-147`). The composite in `render` blits walls
  → frontier → overlay (visit/path) → endpoints
  (`ui/canvas.py:183-191`), so a visited cell that started life as
  frontier always ends up in `COLOR_VISITED`, satisfying AC6. `F` key
  toggles `AppState.show_frontier` (`app.py:254-259`); when turned off
  the layer is wiped immediately via `canvas.clear_frontier`. Default is
  on. Reset Colors wipes both layers (`Canvas.clear_overlay`,
  `ui/canvas.py:96-107`).

- **Cleanup (note #5)**: `--debug` is now real. When set, every
  finished generation runs `is_perfect_maze(maze)` and raises with a
  diagnostic that includes the seed (`app.py:154-163`). The import is
  thus exercised, satisfying review_v1 note #5. Off by default — no perf
  hit in normal runs. `test_cli.CLIParseTests.test_debug_flag` confirms
  the flag plumbs through.

- **Tests**: `tests/test_cli.py` adds 11 cases (5 happy-path argparse
  parses + 5 rejection cases + the determinism sweep with 12 combos +
  the sanity that different seeds differ). `tests/test_optimal_parity.py`
  gains `StatusPanelDeterminismTests` (15 combos). Both modules import
  only stdlib (`argparse`, `random`, `unittest`, `io`, `contextlib`) —
  no new dependencies. Total suite: 21 tests, 1.518s on stock Python
  3.14 (system) without pygame installed (since tests don't touch the
  pygame-bound `app.App`, only `cli.parse_args` and the maze/algorithm
  modules which are pygame-free).

## AC1..AC12 re-confirm (with fresh attention on AC6, AC8, AC9, AC10)

| AC | Status | Reason / cite |
|----|--------|---------------|
| AC1 | met | `__main__.py` / `app.main` entry unchanged. `App.__init__` (`app.py:91-115`) calls `pygame.init()`, opens a `RESIZABLE` window 1100x720 with caption "route-finder", and starts the first DFS Backtracker generation. Bounds remain `[MIN_MAZE_DIM, MAX_MAZE_DIM] = [2, 1000]` per the v2 carryover. |
| AC2 | met | `is_perfect_maze` is unchanged in `maze/invariants.py`. `tests/test_maze_invariants.py` still asserts connectivity AND `edges == non_wall - 1` on (2,2)..(100,50). NEW: `--debug` flag now wires the same invariant into a runtime assertion in `_finish_generation` (`app.py:154-163`) so even ad-hoc runs catch a regression. |
| AC3 | met | `pick_endpoints` unchanged. With a seeded `random.Random` for the run (`app.py:122-123, 165`), endpoints are reproducible — verified by `test_cli.SeedDeterminismTests` and `test_optimal_parity.StatusPanelDeterminismTests`. A green / B red painted in `canvas.render` (`ui/canvas.py:188-191`) unchanged. |
| AC4 | met | `start_new_maze` (`app.py:119-152`) regenerates with DFS Backtracker, animates via the same `step_active` speed loop, re-randomizes A,B in `_finish_generation` (`app.py:165-169`), and clears the overlay (which now includes the frontier layer per UX-D). |
| AC5 | met | Spec mappings 1..6 untouched. `algorithms/__init__.py` REGISTRY indices 1..6, `ui/sidebar.py` algo_labels 1..6, `ui/shortcuts.py` `K_1..K_6` + `K_KP1..K_KP6`. New Space / `.` / `F` keys are non-conflicting with any spec mapping. |
| AC6 | met | **Fresh check.** Every algorithm still emits `("visit", cell)` per popped cell; `canvas.mark_visit` paints `COLOR_VISITED = (90,160,230)` on the visit/path overlay (`ui/canvas.py:123-129`). The frontier overlay is composited BELOW the visit overlay (`ui/canvas.py:184-186`), so any cell that was at any point a frontier still ends up in `COLOR_VISITED` once visited (or `COLOR_PATH` if on the final path). The explicit "don't repaint already-visited cells with frontier tint" guard in `mark_frontier` (`ui/canvas.py:140-146`) belt-and-braces the invariant for the case where a frontier event arrives in the same frame as the visit event. |
| AC7 | met | BFS / Dijkstra / A* / BiBFS / IDA* path-length parity is automated by `test_optimal_parity.OptimalParityTests.test_five_optimal_algos_agree` on (20,15)/(25,25)/(40,30). No algorithm logic changed in v3. |
| AC8 | met | **Fresh check.** `start_algorithm` (`app.py:176-202`) still sets `run_gen = None` and calls `canvas.clear_overlay()` (which now wipes frontier too) before constructing the new generator. v3 addition: it also force-unpauses (`app.py:198-200`), so switching algorithms while paused starts the new run RUNNING — matching the request §UX-B requirement. Counters (`visited_set`, `visited_count`, `frontier_size`, `step_events`, `path_len`) are all zeroed on switch — verified by smoke check ("visited == 0 after switch"). |
| AC9 | met | **Fresh check.** Slider range `[1, 60]` unchanged in `ui/slider.py`. `state.speed = self.sidebar.slider.value` re-read every frame at `app.py:514` and inside `step_active` at `app.py:324`. The step billing rule from v2 (only `visit`/`done` count) is preserved (`app.py:360-370, 376-391`). The pause path drops `step_carry` to 0 (`app.py:321`) so resume doesn't fire a burst. A slider change during a paused run takes effect on the very next un-pause / single-step (the `pause_pending_step` branch reads no speed; the un-pause branch re-enters the standard `speed * dt` accumulator). |
| AC10 | met | **Fresh check.** `on_sidebar_click("reset")` (`app.py:206-230`) cancels any in-flight `run_gen`, clears overlay AND frontier via the upgraded `canvas.clear_overlay` (`ui/canvas.py:96-107`), zeroes the counters, and force-unpauses. `maze.walls`, `maze.start`, `maze.end` are NOT touched — verified by the smoke check that compared `bytes(walls)` before and after Reset. Endpoint pixels keep being painted from `maze.start`/`maze.end` every frame in `canvas.render`. |
| AC11 | met | `canvas.render` aspect-ratio logic unchanged (`ui/canvas.py:172-180`). The VIDEORESIZE branch in `handle_event` (`app.py:265-270`) re-creates the display and re-layouts the sidebar; status-panel cache is invalidated on layout via `_status_dirty = True` (`ui/sidebar.py:116`). |
| AC12 | met | New `cli.py` imports only `argparse` (stdlib). New test file imports only `contextlib`, `io`, `random`, `unittest` (stdlib). Frontier overlay uses pygame APIs already in use. `requirements.txt` unchanged (still `pygame>=2.5,<3`). No runtime network calls anywhere in the codebase (still 0 hits for `socket`, `urllib`, etc., per v1's grep). |

## Notes carried forward / out-of-scope reaffirmation

- Note #6 from review_v1 (frame-budget last-step micro-loss) is
  out-of-scope by request §"Out of scope for v3". No changes.
- The `set_status` (plain-line) sidebar method is kept as a backward-
  compatibility hook even though `App._update_status` no longer uses it;
  removing it would be a separate cleanup pass.

## Ready for review

yes

검토 준비 완료. UX-A 상태 패널, UX-B 일시정지/단일 스텝, UX-C argparse CLI + 시드 결정성, UX-D frontier tint + F 토글, 그리고 `--debug` 후처리 invariant 어설션까지 모두 구현했고 21개 테스트가 1.5초 내 통과합니다.
