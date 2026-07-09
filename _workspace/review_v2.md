# review_v2

verdict: PASS
ready to ship: yes — v2 scope items (A.1, A.2, B.1-B.3, C.1-C.4) are all met on disk, the 8-test suite runs green in ~0.3s, and AC1..AC12 remain met with AC5/AC7/AC9 freshly re-verified.

## v2 scope items

| Item | Status | Reason (file:line if applicable) |
|------|--------|----------------------------------|
| A.1 1×1 clamp | met | `src/route_finder/maze/grid.py:22` defines `MIN_MAZE_DIM = 2`, `:23` `MAX_MAZE_DIM = 1000`; `:48-58` `Maze.__init__` raises `ValueError("maze size must satisfy 2 <= w,h <= 1000 ...")` outside the range. Comment at `:18-21` cites review_v1 note #1. `src/route_finder/app.py:283-286` `main()` clamps argv with the same constants, so `python -m route_finder 1 1` becomes a 2×2 run (no crash). Smoke check (`PYTHONPATH=src python3 -c "from route_finder.maze.grid import Maze; Maze(1,1)"`) raises as expected. `src/route_finder/maze/__init__.py:3,11` re-exports the constants. |
| A.2 budget bills visits only | met | `src/route_finder/app.py:201-237` `step_active` pathfinding branch: `billed` increments only on `tag == "visit"` (`:219`) and on `tag == "done"` (`:236`); the `frontier` branch (`:220-222`) calls `self.canvas.mark_frontier(event[1])` and does NOT touch `billed`. A safety cap `max_events = max(64, steps * 256)` (`:206`) bounds the inner loop against frontier-only pathological cases. AC9 preserved: `state.speed = self.sidebar.slider.value` is re-read every frame (`:262`) before the next budget cycle. |
| B.1 IDA* optimal | met | `src/route_finder/algorithms/ida_star.py` (NEW, 106 lines). Manhattan heuristic via `common.manhattan` (admissible+consistent on a 4-connected unit-cost grid). Explicit-stack DFS waves avoid recursion limits. `announced: set` (`:33`, `:57-59`, `:83-85`) gates `("visit", cell)` so each cell is emitted at most once across all f-threshold iterations. Empirical: `test_optimal_parity.test_five_optimal_algos_agree` passes — BFS/Dijkstra/A*/BiBFS/IDA* report identical lengths on (20,15)/(25,25)/(40,30). Reviewer-side spot-check on 50×50 seed=999: BFS=1297, IDA*=1297, elapsed 1.46s. First-expansion dedup verified by spot-check on 20×15 seed=2000: 445 `visit` events, 445 unique cells, 0 duplicates. |
| B.2 RWalk any-valid + cap | met | `src/route_finder/algorithms/random_walk.py` (NEW). `:43` `step_cap = maze.width * maze.height * _STEP_CAP_MULTIPLIER` with `_STEP_CAP_MULTIPLIER = 20` (`:30`). Step loop `:54-71` picks a uniformly random open neighbor via `random.Random` seeded from `(maze.width, maze.height, start, end)` (`:38-40`). On reaching `end`, emits `("done", _loop_erase(walk))` (`:65-71`) which is a valid simple A→B path. On cap-hit, emits `("done", None)` (`:74`). `_loop_erase` (`:77-97`) correctly drops self-intersecting tail and keeps the first occurrence of each cell, producing a 4-adjacent passage-only simple path. Validated by `test_random_walk_returns_valid_path_or_none` and `test_random_walk_can_return_valid_path_on_small_mazes`. |
| B.3 UI buttons 7,8 + keys 7,8 | met | `src/route_finder/algorithms/__init__.py:22-31` REGISTRY entries 7=IDA*, 8=RWalk appended after 1..6 (unchanged). `src/route_finder/ui/sidebar.py:69-78` `algo_labels` list contains "1. BFS".."6. Bidirectional BFS" then "7. IDA*", "8. RWalk" — spec order untouched. `src/route_finder/ui/shortcuts.py:13-31` SHORTCUTS adds `K_7→7`, `K_8→8` and `K_KP7→7`, `K_KP8→8` (both top-row and numpad). Status string at `app.py:250` reads "Keys: 1..6 (spec), 7..8 (stretch), N=new, R=reset". Comments at `algorithms/__init__.py:15-21`, `sidebar.py:2-6`, `shortcuts.py:3-5` all explicitly mark 1..6 as the spec-mandated set and 7..8 as stretch. |
| C.1 invariant tests | met | `tests/test_maze_invariants.py` (NEW, 57 lines) drives sizes `[(2,2), (5,5), (20,15), (25,25), (50,50), (100,50)]` (`:17-24`) with deterministic seeds `1000+i`, asserts `connectivity_ok(maze)` AND `edge_count(maze) == non_wall_count(maze) - 1`. Includes the new `(2,2)` lower bound. PASS in 0.297s test run. |
| C.2 parity tests incl IDA* | met | `tests/test_optimal_parity.py:10-16` imports `astar, bfs, bidirectional_bfs, dijkstra, ida_star` — five algorithms. `:59-64` builds the `lengths` dict with all five names including `"IDA*": _drive(ida_star, ...)`. `:67-72` asserts ALL of them equal BFS reference. So IDA* is in the parity assertion, not just listed in a comment. PASS. |
| C.3 any-valid tests | met | `tests/test_any_valid_path.py` has four tests: DFS, Greedy, RWalk-or-None on (20,15)/(25,25)/(40,30), and a small-mazes RWalk sanity test on 12 fixtures of 5×5 (`:103-122`) which requires `seen_path` to be True — guards against trivial pass. Reviewer reproduced the small-mazes test: 4/12 fixtures returned a valid path, 8/12 cap-hit, 0 errors — so the sanity assertion is non-trivially exercised. `_assert_valid_path` (`:48-70`) checks (a) non-empty path, (b) starts at A, (c) ends at B, (d) every cell non-wall (via `maze.walls[y*gw+x] == 0`), (e) consecutive cells 4-adjacent. |
| C.4 endpoint constraint tests | met | `tests/test_endpoint_constraint.py:39-75` iterates sizes `[(2,2), (20,15), (100,50)]` x 5 seeds, asserts `a != b` AND `logical_manhattan >= (w+h)*0.5` on every non-fallback seed (`:61-70`), and requires at least one success per size (`:71-75`) so the picker isn't entirely broken on that size. The fallback path (raised `ValueError`) is tolerated and documented inline. `test_endpoints_are_non_wall` (`:77-89`) confirms both A and B are passages. The 2×2 case is exercised — confirmed it doesn't always hit the fallback (test PASS implies `successes > 0` for 2×2). |

## AC1..AC12 re-confirm (carried forward + fresh attention on AC5/AC7/AC9)

| AC | Status | Reason |
|----|--------|--------|
| AC1 | met | `__main__.py`/`app.py:59-69` entry unchanged; perfect-maze invariant covered by AC2 below. Bounds intentionally tightened to `[2, 1000]` per A.1 (this is a deliberate narrowing of the spec's `[1, 1000]`, documented in `grid.py:18-21`). The spec's "size <= 1000x1000" upper bound still holds; lower bound shifted from 1 to 2. |
| AC2 | met | `test_maze_invariants.py` (NEW) automates connectivity + edge-count on six sizes from 2×2 to 100×50, including the 5000-logical-cell 100×50. PASS. |
| AC3 | met | `endpoints.py` unchanged; `test_endpoint_constraint.py` (NEW) automates A != B and Manhattan threshold across three sizes. Canvas still renders A green / B red (`canvas.py` unchanged in v2). |
| AC4 | met | `app.start_new_maze` / `_finish_generation` (`app.py:73-103`) unchanged in behavior; still runs DFS Backtracker step-by-step via the same speed-slider-driven `step_active`. |
| AC5 | met (fresh check) | The six spec algorithms remain mapped to indices 1..6 in spec order: `algorithms/__init__.py:23-28` registers BFS(1), DFS(2), Dijkstra(3), AStar(4), GreedyBF(5), BiBFS(6) in that order; `sidebar.py:69-75` shows them in that order on the UI; `shortcuts.py:14-19` maps K_1..K_6 (and KP_1..KP_6 at `:23-28`) to indices 1..6. Indices 7..8 are purely appended for stretch and do NOT renumber 1..6. AC5 explicitly says "the six algorithms ... selectable via 1 through 6" — both routes satisfied. |
| AC6 | met | `canvas.py` unchanged. `app.py:228-233` still calls `mark_path(path)` and updates status with `len(path)` when the path is non-empty; for RWalk's `None` payload it skips `mark_path` but the path-overlay contract only applies when a path exists, so AC6 is honored (other algos always emit a non-empty path on success — the RWalk None case is the explicit "no path found this attempt" outcome). |
| AC7 | met (fresh check, IDA* added to the optimal group) | `test_optimal_parity.py` automates BFS/Dijkstra/A*/BiBFS/IDA* parity. Empirically all five report identical lengths on the test fixtures. The spec only mandates BFS/Dijkstra/A*/BiBFS parity — adding IDA* is additive and admissible-heuristic-based, so it does NOT violate AC7. DFS/Greedy/RWalk are validated under the "any valid A→B path" branch by `test_any_valid_path.py`. |
| AC8 | met | `start_algorithm` (`app.py:107-122`) unchanged: sets `run_gen = None`, calls `canvas.clear_overlay()`, replaces algorithm. Sidebar route and keyboard route both funnel through it (`app.py:155-157`, `sidebar.handle_event` → `on_sidebar_click("algo:N")` → `start_algorithm`). |
| AC9 | met (fresh check, billing semantics changed) | Slider range `[1, 60]` unchanged (`slider.py`). `state.speed` re-read every frame at `app.py:168` and `:262`. The change-during-run semantics now bind to "next visit" (the next billed step), which is the user-visible step — strictly more aligned with the spec's user-facing intent. A slider change during a dense frontier no longer requires waiting through frontier-only events; the next `visit` reflects the new speed. AC9's "takes effect on the next step" language remains satisfied (and more sharply so). |
| AC10 | met | `on_sidebar_click("reset")` (`app.py:129-136`) unchanged: cancels `run_gen`, sets phase=idle, clears overlay; maze/start/end untouched (the canvas keeps painting endpoints from `maze.start`/`maze.end` on every frame via `canvas.render`). |
| AC11 | met | `canvas.render` aspect-ratio scaling unchanged. `handle_event` VIDEORESIZE branch (`app.py:148-153`) re-creates the display and re-layouts the sidebar. |
| AC12 | met | New files (`ida_star.py`, `random_walk.py`, four test files, two `__init__.py`) import only stdlib (`random`, `typing`, `unittest`) — no new third-party dependencies. `requirements.txt` unchanged (only `pygame>=2.5,<3`). |

## Test suite output (run by reviewer)

```
$ PYTHONPATH=src python3 -m unittest discover -s tests -v
test_dfs_returns_valid_path (test_any_valid_path.AnyValidPathTests.test_dfs_returns_valid_path) ... ok
test_greedy_returns_valid_path (test_any_valid_path.AnyValidPathTests.test_greedy_returns_valid_path) ... ok
test_random_walk_can_return_valid_path_on_small_mazes (test_any_valid_path.AnyValidPathTests.test_random_walk_can_return_valid_path_on_small_mazes) ... ok
test_random_walk_returns_valid_path_or_none (test_any_valid_path.AnyValidPathTests.test_random_walk_returns_valid_path_or_none) ... ok
test_endpoints_are_non_wall (test_endpoint_constraint.EndpointConstraintTests.test_endpoints_are_non_wall) ... ok
test_endpoints_distinct_and_far (test_endpoint_constraint.EndpointConstraintTests.test_endpoints_distinct_and_far) ... ok
test_perfect_maze_invariants_across_sizes (test_maze_invariants.MazeInvariantTests.test_perfect_maze_invariants_across_sizes) ... ok
test_five_optimal_algos_agree (test_optimal_parity.OptimalParityTests.test_five_optimal_algos_agree) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.297s

OK
```

Matches the draft's claimed 8/8 in ~0.3s. Confirmed reproducible on a fresh shell.

## Anti-cheat audit

- **IDA\* is in the parity comparison, not in a comment.** `test_optimal_parity.py:64` reads `"IDA*": _drive(ida_star, maze, a, b)` and the assertion loop at `:68-72` iterates the dict — IDA*'s length is compared to BFS's reference. Confirmed.
- **IDA\* visit dedup is real.** Reviewer reproduction on 20×15 seed=2000: 445 visit events, 445 unique cells, 0 duplicates — the `announced` set actually suppresses re-emission across f-threshold waves.
- **RWalk any-valid test is not trivially passing on `None`.** Reproduced the small-mazes test manually: 4 of 12 fixtures yielded a real path (validated as A→B passage-only 4-adjacent), 8 capped out with `None`. The `seen_path` assertion (`:119-122`) would FAIL if `random_walk` always returned None. The (20,15)/(25,25)/(40,30) fixtures all cap-hit which is expected (random walks on perfect mazes have ~O(n²) hitting times and `n*20` is well below that for n>~50), and the test correctly allows that outcome while the small-mazes branch keeps the algorithm honest.
- **Budget billing reads correctly.** Reviewer read `app.py:201-237` line by line: `billed += 1` only on `"visit"` (`:219`) and `"done"` (`:236`); `"frontier"` branch (`:220-222`) has no `billed` change. The `consumed`/`max_events` safety cap protects against a hypothetical frontier-only generator but is large enough that real algorithms never hit it on a 1000×1000 maze.
- **Maze(1,1) really raises.** Reproduced: `ValueError: maze size must satisfy 2 <= w,h <= 1000 (got 1x1)`. CLI route via `main()` clamps to 2.

## Amendments

None.

## Notes (optional, non-blocking)

1. `app.py:32` still imports `is_perfect_maze` from `.maze` but doesn't call it at runtime (carried forward from review_v1 note #5). Harmless; could be wired into a debug assertion or dropped.
2. `app.py:38` `DEFAULT_W, DEFAULT_H = 1100, 720` shadows window dims and `DEFAULT_MAZE_W, DEFAULT_MAZE_H = 60, 40`; naming is fine but a future cleanup pass could rename the window constants to `WIN_W/WIN_H` for clarity.
3. `_loop_erase` in `random_walk.py:77-97` is O(n) per cycle truncation worst-case (the `for dropped in out[keep:]` clears its index entries), so on extremely cycle-heavy walks the loop-erase is O(n²) in the walk length. With cap `n*20` it's bounded; no practical concern.
4. The `test_random_walk_returns_valid_path_or_none` test happens to have all three fixtures cap-hit at the chosen seeds. That's legal per the contract but means the "validate path" branch (`_assert_valid_path` call at `:101`) is dead for those three seeds. The small-mazes test exercises the path branch, so coverage is maintained — but a future tweak could pick fixtures that mix successes and cap-hits.
5. `test_endpoint_constraint.test_endpoints_distinct_and_far` requires `successes > 0` per size but doesn't print how many fallbacks were hit. Adding a `print` (or a `self.subTest`) to surface the fallback count would help diagnose if 100×50 ever degrades. Non-blocking.
6. `endpoints.py:84-95` falls back to `_bfs_farthest(maze, a)` then re-raises if even that pair fails the threshold. The test tolerates the raise, but a future pass might prefer to return the farthest pair anyway (with a logged warning) so the UI never crashes mid-run on a small maze.

검토 결과 PASS. v2 범위 9개 항목 (A.1, A.2, B.1~B.3, C.1~C.4) 모두 충족, 8개 테스트 0.297초 내 통과, AC1~AC12 모두 유지 (AC5/AC7/AC9 새로 검증), 안티치트 4건 모두 통과.
