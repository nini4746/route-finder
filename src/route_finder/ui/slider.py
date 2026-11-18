"""Integer-range speed slider [1, 240] steps/sec."""

from __future__ import annotations

import pygame


class Slider:
    def __init__(self, rect: pygame.Rect, vmin: int = 1, vmax: int = 240, value: int = 20):
        self.rect = rect
        self.vmin = vmin
        self.vmax = vmax
        self.value = max(vmin, min(vmax, value))
        self.dragging = False

    @property
    def fraction(self) -> float:
        if self.vmax == self.vmin:
            return 0.0
        return (self.value - self.vmin) / (self.vmax - self.vmin)

    def _value_from_x(self, x: int) -> int:
        frac = (x - self.rect.x) / max(1, self.rect.width)
        frac = max(0.0, min(1.0, frac))
        return int(round(self.vmin + frac * (self.vmax - self.vmin)))

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if this slider consumed the event."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self.value = self._value_from_x(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.value = self._value_from_x(event.pos[0])
            return True
        return False

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        font_range: pygame.font.Font | None = None,
    ) -> None:
        # Track
        pygame.draw.rect(surface, (44, 50, 62), self.rect, border_radius=3)
        # Fill (primary violet)
        fill_w = int(self.rect.width * self.fraction)
        if fill_w > 0:
            fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_w, self.rect.height)
            pygame.draw.rect(surface, (99, 84, 217), fill_rect, border_radius=3)
        # Knob: light disc with a primary ring.
        knob = (self.rect.x + fill_w, self.rect.y + self.rect.height // 2)
        pygame.draw.circle(surface, (99, 84, 217), knob, 8)
        pygame.draw.circle(surface, (228, 232, 238), knob, 7)
        # Label and range
        text = font.render(f"Speed: {self.value} / sec", True, (228, 232, 238))
        ty = self.rect.y - text.get_height() - 8
        surface.blit(text, (self.rect.x, ty))
        if font_range is not None:
            rng = font_range.render(f"{self.vmin}-{self.vmax}", True, (154, 163, 178))
            surface.blit(rng, rng.get_rect(bottomright=(self.rect.right, ty + text.get_height())))
