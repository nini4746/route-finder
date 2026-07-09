"""Main app loop and AppState.

Phases:
  - generating: maze generator is being stepped; canvas paints carve events.
  - idle: maze is fully generated; awaiting algorithm selection.
  - pathfinding: a pathfinder generator is being stepped; canvas paints
    visit events; on the terminal "done" event, the path is overlaid.

Cancellation: switching algorithm mid-run drops the current generator,
clears overlay colors, and starts the new one on the same maze + A/B.

Speed: the slider drives steps-per-second uniformly. Each frame we may
advance the active generator by ``max(1, speed * dt)`` steps; the slider
caps at 240, so at top speed we run ~4 steps per 60Hz frame.

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
        pygame.font.init()
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
