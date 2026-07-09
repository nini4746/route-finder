# Core Beliefs

One numbered belief per constraint in `docs/product-specs/initial-seed.yaml`. Each belief is the rule we are willing to defend during code review.

## 1. **Single binary dependency**

Runtime dependencies are limited to the Python standard library plus pygame.

The moment a second third-party library enters the import graph, install becomes a multi-step debugging session for the user. We trade some convenience (no `numpy` for grids, no `pillow` for images) for a one-liner install.

## 2. **Offline by construction**

No runtime network calls; pygame is installed via pip at install time only.

Any outbound request at runtime would mean a hung event loop on a flaky network or, worse, a privacy leak from a local visualization. We avoid both by never opening a socket.

## 3. **macOS only**

Supported OS is macOS only (Apple Silicon and Intel).

Cross-platform support multiplies test surface and conditional code. We pick one platform and own it well.

## 4. **Bounded grid**

Maze grid size is bounded by `1 <= width <= 1000` and `1 <= height <= 1000` cells.

A 1000x1000 maze is at the edge of what fits in screen pixels and still animates smoothly; anything larger turns the visualization into a useless blur. We reject larger inputs at the boundary rather than degrade silently.

## 5. **Perfect mazes only**

Generated mazes are perfect (every non-wall cell is reachable from every other non-wall cell, and the passage graph contains zero cycles).

If two paths join, the search-algorithm comparison stops being a fair test (you can race through a loop). The perfect-maze invariant is what makes Dijkstra and A* meaningful here.

## 6. **One generator**

Maze generation uses the DFS Backtracker algorithm exclusively.

DFS Backtracker matches the user's stated taste (branchy but not over-branching, long corridors with many dead ends). Supporting alternates is scope creep until the user asks for it.

## 7. **Animated generation**

Maze generation animates step-by-step at the speed configured by the speed slider.

The user explicitly chose to see the generation, not just the result. Hiding it would discard half the program's pedagogy.

## 8. **Six pathfinders, common interface**

The six required pathfinding algorithms are BFS, DFS, Dijkstra, A*, Greedy Best-First, and Bidirectional BFS.

Six is the minimum that lets the user see real differences between informed and uninformed search, and between unidirectional and bidirectional. Fewer would make the comparison thin.

## 9. **Stretch is stretch**

Stretch goal is to implement at least two additional pathfinding algorithms beyond the required six.

We do not block the v1 release on stretch goals. If the six work, the program is shippable.

## 10. **Endpoint distance threshold**

Endpoints A and B are chosen randomly from non-wall cells such that `A != B` and `|Ax-Bx| + |Ay-By| >= (width + height) * 0.5`.

Trivial endpoints make the visualization meaningless — the path is one square long. The threshold guarantees the user always sees algorithms doing real work.

## 11. **One algorithm at a time**

Only one pathfinding algorithm visualizes at a time; selecting another cancels, resets, and restarts.

Overlaying multiple algorithms on the same canvas creates color collisions that defeat the entire visualization. Sequential comparison is the user's choice and it is non-negotiable.

## 12. **Maze persistence across runs**

The same maze and the same A and B persist across algorithm runs until the user clicks New Maze.

The user wants to compare algorithms on identical inputs. Re-randomizing every run would make the comparison incomparable.

## 13. **Live speed slider**

The speed slider range is `[1, 60]` steps per second and applies live to both pathfinding and maze generation animations.

The user wants to slow a search down to inspect a tricky region, then speed it back up. Reading the slider once at run start would force a restart for every adjustment.

## 14. **Fixed sidebar surface**

The sidebar exposes a New Maze button, six algorithm buttons mapped to keyboard shortcuts 1 through 6, a speed slider, and a Reset Colors button.

The control set is small and complete; adding more controls dilutes attention and tempts feature creep. Keyboard shortcuts make repeated comparison fast.

## 15. **Aspect-preserving canvas scale**

The canvas auto-scales to the current window size while preserving the maze aspect ratio.

A stretched maze (squares becoming rectangles) misrepresents the search shape. Letterboxing is preferred over distortion.

## How to amend a belief

Beliefs are derived from `docs/product-specs/initial-seed.yaml > constraints`. To change one, edit the YAML and run `/harness-spec --rerender`. Hand-edits to this file will be overwritten.
