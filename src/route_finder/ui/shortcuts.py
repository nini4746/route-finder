"""Keyboard shortcut mapping for algorithms.

Keys 1..6 are the AC5 spec-mandated mapping (BFS/DFS/Dijkstra/A*/Greedy/BiBFS)
and MUST NOT be renumbered. Keys 7..8 are stretch additions per request_v2
(IDA* and Random Walk respectively) appended to the same dict.
"""

from __future__ import annotations

import pygame

# pygame key -> algorithm index. 1..6 = spec; 7..8 = stretch.
SHORTCUTS: dict[int, int] = {
    pygame.K_1: 1,
    pygame.K_2: 2,
    pygame.K_3: 3,
    pygame.K_4: 4,
    pygame.K_5: 5,
    pygame.K_6: 6,
    pygame.K_7: 7,  # stretch: IDA*
    pygame.K_8: 8,  # stretch: Random Walk
    # numpad
    pygame.K_KP1: 1,
    pygame.K_KP2: 2,
    pygame.K_KP3: 3,
    pygame.K_KP4: 4,
    pygame.K_KP5: 5,
    pygame.K_KP6: 6,
    pygame.K_KP7: 7,
    pygame.K_KP8: 8,
}
