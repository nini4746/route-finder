"""End-to-end headless boot test: actually run the pygame App (SDL dummy
video/audio driver) through maze generation, a full pathfinding run, and a
QUIT event - exercising the real render/flip pipeline, not just the pure
algorithm units. This is the "직접 실행" smoke test for the GUI path.
"""
from __future__ import annotations

import os

# Must be set before pygame is imported so it picks the headless drivers.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

# pygame-ce still imports as `pygame`; skip cleanly if the wheel is absent.
App = pytest.importorskip("route_finder.app").App


def _drain(app, done, max_ticks=200_000):
    """Tick the real per-frame step + render until `done()` or the cap."""
    app.state.speed = 240  # top speed so the run converges fast
    for _ in range(max_ticks):
        app.step_active(0.05)
        app._render()  # drives Canvas.render + Sidebar.draw onto the dummy surface
        if done(app):
            return True
    return False


def test_app_boots_generates_runs_algorithm_and_quits_headless():
    app = App(maze_w=15, maze_h=15, seed=7)

    # __init__ kicks off generation; drain it to completion.
    assert _drain(app, lambda a: a.state.phase == "idle"), \
        f"maze generation never finished (phase={app.state.phase})"
    assert app.state.maze is not None

    # Run BFS (REGISTRY index 1) end to end on the real maze.
    app.start_algorithm(1)
    assert app.state.phase == "pathfinding"
    assert _drain(app, lambda a: a.state.phase == "idle" and a.state.run_gen is None), \
        f"pathfinding never finished (phase={app.state.phase})"

    # A real search visited cells and found a path on a perfect maze.
    assert app.state.visited_count > 0
    assert app.state.path_len is not None and app.state.path_len > 0

    # QUIT must tell the loop to stop.
    assert app.handle_event(pygame.event.Event(pygame.QUIT)) is False

    pygame.quit()
