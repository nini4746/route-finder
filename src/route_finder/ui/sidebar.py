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
BTN_H = 34
ALGO_BTN_H = 28
ALGO_GAP = 4
STATUS_LINE_GAP = 4
WELL_PAD = 8

# Palette from the Stitch redesign (dark surface + violet primary). The
# primary violet is kept out of the maze overlay colors on purpose.
COLOR_PANEL = (26, 30, 37)          # surface-container #1A1E25
COLOR_EDGE = (56, 64, 79)           # outline #38404F
COLOR_EDGE_SOFT = (38, 43, 53)      # outline-variant #262B35
COLOR_BTN = (35, 40, 50)            # surface-container-high #232832
COLOR_BTN_HOVER = (44, 50, 62)      # surface-container-highest #2C323E
COLOR_BTN_ACTIVE = (99, 84, 217)    # primary #6354D9
COLOR_WELL = (15, 18, 22)           # surface-container-low #0F1216
COLOR_TEXT = (228, 232, 238)        # on-surface #E4E8EE
COLOR_TEXT_DIM = (154, 163, 178)    # on-surface-variant #9AA3B2
COLOR_TEXT_KEY = (154, 163, 178)
COLOR_TEXT_VAL = (228, 232, 238)

LEGEND = (
    ("visited", (41, 98, 158)),
    ("frontier", (137, 196, 244)),
    ("path", (242, 201, 76)),
    ("A", (52, 178, 108)),
    ("B", (224, 82, 82)),
)
KEY_HINT = "Space pause, . step, F frontier, Esc quit"

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
    shortcut: str = ""  # key chip drawn on the right (N, R) or number on the left
    hovered: bool = False
    active: bool = False


class Sidebar:
    def __init__(self, win_h: int):
        self.font: pygame.font.Font | None = None
        self.font_small: pygame.font.Font | None = None
        self.font_mono: pygame.font.Font | None = None
        self.font_title: pygame.font.Font | None = None
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
        self.win_h = win_h
        self.buttons = []
        # Title row (drawn in draw()) occupies PAD..PAD+32.
        self.title_y = PAD
        y = PAD + 40
        self.buttons.append(
            Button(pygame.Rect(x, y, w, BTN_H), "New Maze", "new_maze", shortcut="N")
        )
        y += BTN_H + 14
        self.algo_label_y = y
        y += 20
        # Order matters: 1..6 must remain the AC5 spec order. 7..8 are the
        # stretch additions appended in fixed order.
        algo_labels = [
            "BFS",
            "DFS",
            "Dijkstra",
            "A*",
            "Greedy Best-First",
            "Bidirectional BFS",
            "IDA*",
            "RWalk",
        ]
        for i, label in enumerate(algo_labels, start=1):
            self.buttons.append(
                Button(pygame.Rect(x, y, w, ALGO_BTN_H), label, f"algo:{i}", shortcut=str(i))
            )
            y += ALGO_BTN_H + ALGO_GAP
        y += 10
        # Slider rect: leave room for label above.
        slider_y = y + 22
        self.slider.rect = pygame.Rect(x, slider_y, w, 6)
        y = slider_y + 6 + 16

        self.buttons.append(
            Button(pygame.Rect(x, y, w, BTN_H), "Reset Colors", "reset", shortcut="R")
        )
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
            self.font = pygame.font.SysFont("Helvetica Neue,Helvetica", 14, bold=True)
            self.font_small = pygame.font.SysFont("Helvetica Neue,Helvetica", 12)
            self.font_title = pygame.font.SysFont("Helvetica Neue,Helvetica", 19, bold=True)
            # Monospace for the status panel so key/value columns align.
            # Menlo ships on macOS by default; fall back to pygame's
            # generic monospace match if it ever isn't present.
            mono_name = pygame.font.match_font("Menlo,Monaco,Courier New,monospace")
            if mono_name:
                self.font_mono = pygame.font.Font(mono_name, 11)
            else:
                self.font_mono = pygame.font.SysFont("monospace", 11)

    def _render_status_surface(self) -> pygame.Surface:
        """Rasterize the status snapshot into a fresh surface, cached."""
        font = self.font_mono
        snapshot = self._status_snapshot
        # Compute height/width up front.
        line_h = font.get_linesize()
        # Eyeball the value column width from current values; we shrink
        # the surface to the sidebar width so don't bother enlarging beyond.
        width = SIDEBAR_WIDTH - 2 * PAD - 2 * WELL_PAD
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
            # Right-align values; a long value may run into the key column
            # as long as it clears this row's own key text.
            vx = max(font.size(key + ":")[0] + 6, width - val_surf.get_width())
            surface.blit(val_surf, (vx, y))
            y += line_h + STATUS_LINE_GAP
        return surface

    def _draw_button(self, surface: pygame.Surface, b: Button) -> None:
        is_algo = b.key.startswith("algo:")
        primary = b.active or b.key == "new_maze"
        if primary:
            fill, edge = COLOR_BTN_ACTIVE, COLOR_BTN_ACTIVE
        elif b.hovered:
            fill, edge = COLOR_BTN_HOVER, COLOR_EDGE
        else:
            fill, edge = COLOR_BTN, COLOR_EDGE_SOFT if is_algo else COLOR_EDGE
        pygame.draw.rect(surface, fill, b.rect, border_radius=4)
        pygame.draw.rect(surface, edge, b.rect, width=1, border_radius=4)
        cy = b.rect.centery
        if is_algo:
            num = self.font_small.render(
                b.shortcut, True, COLOR_TEXT if b.active else COLOR_TEXT_DIM
            )
            surface.blit(num, (b.rect.x + 10, cy - num.get_height() // 2))
            txt = self.font.render(b.label, True, COLOR_TEXT)
            surface.blit(txt, (b.rect.x + 26, cy - txt.get_height() // 2))
            return
        txt = self.font.render(b.label, True, COLOR_TEXT)
        surface.blit(txt, (b.rect.x + 14, cy - txt.get_height() // 2))
        if b.shortcut:
            key = self.font_mono.render(b.shortcut, True, COLOR_TEXT if primary else COLOR_TEXT_DIM)
            if primary:
                chip = pygame.Rect(0, 0, key.get_width() + 10, key.get_height() + 4)
                chip.midright = (b.rect.right - 10, cy)
                pygame.draw.rect(surface, COLOR_WELL, chip, border_radius=3)
                surface.blit(key, key.get_rect(center=chip.center))
            else:
                surface.blit(key, key.get_rect(midright=(b.rect.right - 14, cy)))

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        self.ensure_fonts()
        pygame.draw.rect(surface, COLOR_PANEL, rect)
        pygame.draw.line(surface, COLOR_EDGE, (rect.right - 1, rect.y), (rect.right - 1, rect.bottom))
        inner_w = SIDEBAR_WIDTH - 2 * PAD

        # Title row with accent dot and a hairline below it.
        title = self.font_title.render("route-finder", True, COLOR_TEXT)
        surface.blit(title, (PAD, self.title_y + 2))
        pygame.draw.circle(surface, COLOR_BTN_ACTIVE, (PAD + inner_w - 4, self.title_y + 14), 4)
        pygame.draw.line(surface, COLOR_EDGE_SOFT, (PAD, self.title_y + 32), (PAD + inner_w, self.title_y + 32))

        label = self.font_small.render("Algorithms", True, COLOR_TEXT_DIM)
        surface.blit(label, (PAD, self.algo_label_y))

        for b in self.buttons:
            self._draw_button(surface, b)

        self.slider.draw(surface, self.font, self.font_mono)

        # Bottom-anchored block: key hint, legend, then the status panel.
        bottom = rect.bottom - PAD
        hint = self.font_small.render(KEY_HINT, True, COLOR_TEXT_DIM)
        hint_y = bottom - hint.get_height()
        surface.blit(hint, (PAD, hint_y))
        sep_y = hint_y - 8
        pygame.draw.line(surface, COLOR_EDGE_SOFT, (PAD, sep_y), (PAD + inner_w, sep_y))
        legend_y = sep_y - 10 - self.font_small.get_height()
        lx = PAD
        for name, color in LEGEND:
            t = self.font_small.render(name, True, COLOR_TEXT_DIM)
            pygame.draw.rect(surface, color, pygame.Rect(lx, legend_y + 4, 8, 8))
            surface.blit(t, (lx + 12, legend_y))
            lx += 12 + t.get_width() + 10

        # v3 UX-A: cached snapshot render, inside an inset well.
        if self._status_snapshot:
            if self._status_dirty or self._status_surface is None:
                self._status_surface = self._render_status_surface()
                self._status_dirty = False
            sh = self._status_surface.get_height()
            well = pygame.Rect(PAD, legend_y - 12 - (sh + 2 * WELL_PAD), inner_w, sh + 2 * WELL_PAD)
            min_top = self.buttons[-1].rect.bottom + 12
            if well.y < min_top:
                well.y = min_top
            pygame.draw.rect(surface, COLOR_WELL, well, border_radius=4)
            pygame.draw.rect(surface, COLOR_EDGE_SOFT, well, width=1, border_radius=4)
            surface.blit(self._status_surface, (well.x + WELL_PAD, well.y + WELL_PAD))
            sy = well.bottom + 6
        else:
            sy = self.buttons[-1].rect.bottom + 16
        # Legacy plain-line status (still drawn for backward compatibility
        # with anyone calling ``set_status``).
        for line in self.status_lines:
            txt = self.font_small.render(line, True, COLOR_TEXT_DIM)
            surface.blit(txt, (PAD, sy))
            sy += txt.get_height() + 2
