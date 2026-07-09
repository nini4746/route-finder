# Request v2 (follow-up pass)

The v1 implementation passed review (review_v1.md PASS, AC1..AC12 met).
This pass extends the project with three groups of work, in priority order.

## A. Address non-blocking notes from review_v1

Pick up notes #1 and #3 from `_workspace/review_v1.md`. The other notes
(#2, #4, #5, #6) are intentionally deferred — do NOT touch them in this
pass.

1. **Note #1 — 1×1 maze crashes endpoint selection.**
   - On a 1×1 maze the only non-wall cell is `(0,0)`, so `endpoints.py`
     cannot satisfy `A != B`. Currently this raises `ValueError`.
   - Required behavior: enforce a minimum maze size of **2×2** at the
     boundary where size is chosen (CLI args / config / default).
     Document this in code via a `MIN_MAZE_DIM = 2` constant in
     `maze/grid.py` (or wherever the size validation lives) and clamp /
     reject smaller inputs there.
   - Update the AC1 surface: the spec says `1 <= w,h <= 1000`, so this
     is a deliberate tightening for soundness. Add a one-line comment
     at the clamp site referencing this note.

2. **Note #3 — step budget consumed by `frontier` events at high speed.**
   - Currently `step_active` advances `int(speed * dt)` events per
     frame, and `frontier` events count toward the budget. At high
     speeds with dense frontiers, the visible `visit` cadence lags
     the slider value.
   - Required behavior: bill the per-frame step budget only against
     **`visit`** events (and `done`). `frontier` events are consumed
     and drawn (or ignored, per current `mark_frontier` no-op) but do
     NOT decrement the budget.
   - Keep AC9 semantics intact ("a change during a run takes effect
     on the next step" — the next `visit`, in v2 terms).

## B. Stretch goal — two additional pathfinding algorithms

The spec's stretch is "at least two additional pathfinding algorithms
beyond the required six." Add exactly two:

1. **IDA\*** (Iterative Deepening A\*)
   - Same admissible Manhattan heuristic as A*.
   - Optimal (path length must equal BFS/Dijkstra/A*/BiBFS on the same
     maze + A,B).
   - Memory-efficient, depth-bounded DFS waves with f-threshold
     iteration.
   - Yields `("visit", cell)` events on first expansion of each cell
     (across all iterations — same cell may be re-expanded; emit
     `visit` only on the first expansion overall, so the on-screen
     coverage doesn't repaint).
   - File: `src/route_finder/algorithms/ida_star.py`.

2. **Random Walk**
   - From A, step to a random neighbor that is a passage (open cell);
     repeat until B is reached or step limit hit.
   - **Not** optimal; classified with DFS / Greedy under AC7's "any
     valid A→B path" branch.
   - Emits `("visit", cell)` on each step.
   - To keep the run finite on hostile mazes, cap steps at
     `width * height * 20`; on cap-hit emit `("done", None)` to mean
     "no path found this attempt" — UI may show a brief status.
   - File: `src/route_finder/algorithms/random_walk.py`.

### UI integration for stretch algorithms

Add two more sidebar buttons (labels `IDA*` and `RWalk`) and keyboard
shortcuts `7` and `8`. Update:
- `algorithms/__init__.py` registry
- `ui/sidebar.py` buttons
- `ui/shortcuts.py` key mapping
- any AC5-spec text in code comments — note clearly that 1..6 remain
  the required spec mapping and 7..8 are stretch extras

Do NOT change the meaning of keys 1..6 or the required six algorithms'
sidebar order. The stretch additions append.

## C. Fill in `tests/` for regression coverage

The `tests/` directory exists but is empty. Reviewer is currently
re-running AC2 and AC7 invariant checks by hand on every pass. Move
those checks into automated tests so the next reviewer pass can rely
on `python -m pytest` (or `python -m unittest` — pick one; pytest is
not a runtime dep so use unittest if you want to stay in stdlib).

Required tests (use stdlib `unittest`):

1. **`tests/test_maze_invariants.py`**
   - For sizes `[(2,2), (5,5), (20,15), (25,25), (50,50), (100,50)]`:
     - generate a maze
     - assert `connected == True` (BFS from `(0,0)` reaches all
       non-wall cells)
     - assert `edges == non_wall_count - 1`
   - Use a fixed RNG seed per size for determinism.

2. **`tests/test_optimal_parity.py`**
   - On sizes `[(20,15), (25,25), (40,30)]` with fixed seeds:
     - generate maze + pick A,B
     - drive BFS, Dijkstra, A*, BiBFS, **and IDA\*** to completion
     - assert all five report identical path lengths
   - DFS, Greedy, Random Walk are NOT in this test (they're allowed
     to be sub-optimal).

3. **`tests/test_any_valid_path.py`**
   - On the same fixtures, drive DFS, Greedy, Random Walk to
     completion and assert the returned path (if any) is a valid
     A→B path: starts at A, ends at B, every consecutive pair is
     adjacent and both endpoints of each pair are non-wall.
   - For Random Walk, allow the "no path found within step cap"
     outcome on at least one fixture without failing — assert it
     either finds a valid path or reports `None`.

4. **`tests/test_endpoint_constraint.py`**
   - For sizes `[(2,2), (20,15), (100,50)]`:
     - regenerate 5 mazes per size with different seeds
     - assert `A != B` and `|Ax-Bx| + |Ay-By| >= (w+h) * 0.5` for
       each, OR confirm the fallback (farthest-reachable) path is
       used and document the actual Manhattan distance in a comment.

Add a `tests/__init__.py` (empty) if needed.

Make the tests **fast** — total runtime under ~10 seconds on a 100×50
maze. If `IDA*` is slow on a 40×30 maze, drop the parity test for
IDA* to 25×25 only.

## Out of scope for v2

- All other reviewer notes (#2, #4, #5, #6).
- UX polish (status panel, pause/step, seed input).
- Performance work beyond the budget-billing fix in A.2.

## Self-check requirement (in draft_v2.md)

For each of:
- A.1 (1×1 → MIN 2 clamp)
- A.2 (step budget bills only visits)
- B.1 (IDA* implemented, optimal, integrated)
- B.2 (Random Walk implemented, any-valid, integrated)
- B.3 (UI buttons 7, 8 + keyboard shortcuts wired)
- C.1..C.4 (four test files present, runnable, pass locally)

state which file(s) were touched and the one-line proof of correctness.

Re-confirm AC1..AC12 are still met after these changes — at minimum
verify by running the new test suite and posting the output in the
draft.
