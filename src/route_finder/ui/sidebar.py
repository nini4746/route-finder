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
