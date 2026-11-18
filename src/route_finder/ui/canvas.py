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

# Colors (RGB). Palette from the Stitch redesign (docs/images/ui-*.png).
COLOR_BG = (22, 26, 32)          # #161A20
COLOR_WALL = (207, 214, 224)     # #CFD6E0
COLOR_PASSAGE = (22, 26, 32)     # #161A20
COLOR_VISITED = (41, 98, 158)    # #29629E
# Pale-blue frontier tint, lighter than COLOR_VISITED while staying in
# the same hue family so the eye groups them together.
COLOR_FRONTIER = (137, 196, 244)  # #89C4F4
COLOR_PATH = (242, 201, 76)      # #F2C94C
COLOR_START = (52, 178, 108)     # #34B26C
COLOR_END = (224, 82, 82)        # #E05252
COLOR_LETTERBOX = (15, 18, 22)   # #0F1216


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
