# review_v3

verdict: PASS
ready to ship: yes — UX-A through UX-D plus the `--debug` cleanup all land on disk with sensible defaults, seed plumbing is byte-identical across runs (verified independently of the draft), and 21 tests run green in 1.992s with the new CLI and determinism cases actually exercising the new surface.

## v3 scope items

| Item | Status | Reason (file:line if applicable) |
|------|--------|----------------------------------|
| UX-A status panel | met | `src/route_finder/ui/sidebar.py:42-50` `STATUS_KEY_ORDER` lists the 7 required keys (Algorithm, Phase, Visited, Frontier, Steps, Path length, Maze). `:157-169` `set_status_snapshot` short-circuits on equal snapshot dict (`if snapshot == self._status_snapshot: return`) — text is rasterized only when a value changed. `:178-184` ensures a Menlo/Monaco/Courier monospace font (with `match_font` fallback to pygame's generic `monospace`). `:186-210` `_render_status_surface` aligns the value column by `max(font.size(k+":")[0] for k in STATUS_KEY_ORDER)`. The snapshot is built by `app.py:466-496` `_status_snapshot`, which produces every required field including `Maze: WxH (seed=S)` (`:495`) and the `F:on`/`F:off` flag on the `Frontier:` line (`:492`). |
| UX-B pause/step | met | `app.py:281-289` keyboard handler maps `K_SPACE → _toggle_pause`, `K_PERIOD → _request_single_step`, `K_f → _toggle_frontier`. `:238-247` `_toggle_pause` only enters paused when phase is `generating` or `pathfinding` (no-op in idle) and records `paused_from_phase`. `:249-252` `_request_single_step` only sets `pause_pending_step` if currently paused — explicit no-op while running, per spec. `:314-322` `step_active`'s paused branch consumes exactly one billable event via `_consume_single_step` and drops `step_carry` to 0 to prevent burst on resume. `:407-414` covers the `generating` phase too, so pause/step works during DFS Backtracker animation as the request mandates. `_consume_single_step` (`:398-449`) drains frontier events between visits without counting them — mirrors the v2 budget billing exactly. Switch-cancel while paused: `start_algorithm` (`:176-202`) sets `paused = False`, `paused_from_phase = None`, `pause_pending_step = False` AFTER `canvas.clear_overlay()` and the counter reset, so the new algorithm starts UNPAUSED on a clean slate. |
| UX-C CLI + seed plumbing | met | NEW `src/route_finder/cli.py:58-101` `build_parser` registers three positional ints `width`/`height`/`seed` with `nargs="?"` and `--debug` as `store_true`. `_dim_int` (`:30-42`) enforces `MIN_MAZE_DIM <= iv <= MAX_MAZE_DIM` via `argparse.ArgumentTypeError`, so bad values surface as argparse-style non-zero exits. `_seed_int` (`:45-55`) rejects negative or non-int. `app.py:533-537` `main` calls `parse_args(argv)` and forwards `width/height/seed/debug` into `App.__init__`. Seed plumbing: `App.__init__` (`:104-115`) draws `_new_seed()` via `random.SystemRandom().randrange(2**31)` when CLI seed is None, stashes it in `state.seed`, builds `state.rng = random.Random(chosen_seed)`, and threads it into `start_new_maze(seed=chosen_seed)`. `start_new_maze` (`:119-152`) reseeds on each call and passes the same `Random` instance into both `generate_maze(rng=self.state.rng, maze=live)` (`:138-143`) and later `pick_endpoints(maze, rng=self.state.rng)` (`:165`) — same seed therefore reproduces walls AND endpoints. The reviewer reproduced this independently (see "Reviewer-side determinism probe" below): `bytes(m1.walls) == bytes(m2.walls)` and `(a1,b1) == (a2,b2)` for seed=42 at 20x15. Status panel surfaces the seed via `_status_snapshot` (`:495`). New Maze (sidebar click and `N` key) re-draws a fresh seed: `on_sidebar_click("new_maze")` (`:207-208`) calls `start_new_maze()` with no arg, which lands on `_new_seed()` (`:121`). |
| UX-D frontier tint + F toggle | met | `src/route_finder/ui/canvas.py:35` `COLOR_FRONTIER = (150, 195, 235)` — a pale tint distinct from `COLOR_VISITED = (90, 160, 230)` but in the same hue family. `:55,72-75` allocates an SRCALPHA `frontier` layer. `:131-147` `mark_frontier` paints only when `overlay.get_at(cell).a == 0` (so already-visited cells don't get reverted to tint). `:96-107` `clear_overlay` wipes BOTH `overlay` (visit+path) AND `frontier` — see AC10 below. `:109-112` `clear_frontier` wipes only the frontier layer (used by the F key toggle). `:161-193` `render` composes in the order base → frontier → overlay → endpoints, so visit color sits on top of frontier tint and path sits on top of visit. AC6 invariant holds by composite ordering, not by re-painting (which is more robust). App-side: `app.py:254-259` `_toggle_frontier` flips `state.show_frontier` and immediately calls `canvas.clear_frontier()` when turning off, so the toggle is visible without waiting for the next frame. `state.show_frontier` defaults to True (`app.py:86`). `_status_snapshot` (`:492`) emits `Frontier: <n> (F:on)` / `Frontier: - (F:off)`. The `step_active` pathfinding loop (`:371-375`) skips the frontier paint call when `show_frontier` is False, so the toggle suppresses NEW tint as well as clears existing. |
| Cleanup (`--debug` + `is_perfect_maze` wired) | met | `app.py:154-163` `_finish_generation`: when `state.debug` is True, calls `is_perfect_maze(maze)` and raises `AssertionError(...)` with seed+size context if the invariant fails. This is a real runtime call, not a dead import. `cli.py:96-100` exposes `--debug` as `store_true`. `app.py:48` imports `is_perfect_maze` from `.maze`, and it's now actually used at line 159. Default-off so production runs aren't slowed down. |
| Tests (test_cli, parity determinism) | met | `tests/test_cli.py` has 12 tests: 5 happy-path parses (`test_defaults_when_no_args`, `test_width_only`, `test_width_and_height`, `test_width_height_seed`, `test_debug_flag`), 5 rejections (`test_below_min_rejected`, `test_above_max_rejected`, `test_non_int_rejected`, `test_negative_seed_rejected`, `test_non_int_seed_rejected`), 1 sanity (`test_different_seeds_usually_differ` — guards against seed being silently ignored), and 1 determinism (`test_same_seed_identical_maze_and_endpoints` — 12 (size,seed) sub-cases asserting `bytes(m1.walls) == bytes(m2.walls)` AND `a1 == a2` AND `b1 == b2`). `tests/test_optimal_parity.py` extends with `StatusPanelDeterminismTests.test_same_seed_same_counters_across_runs` (15 sub-cases: 3 sizes × 5 optimal algos), which calls `_drive_with_counters` to build BOTH the unique visited-cell count AND the path length, then asserts both are equal across two independent same-seed runs (`:131-144`). This is strictly stronger than v2's path-length-only parity. Reviewer ran the suite from disk: 21/21 green in 1.992s. |

## AC1..AC12 re-confirm

| AC | Status | Reason |
|----|--------|--------|
| AC1 | met | `__main__.py` unchanged; `app.py:533-537` `main()` now parses argv via `parse_args` and forwards width/height/seed/debug to `App`. Window still `(1100, 720)` with `RESIZABLE`. Carried forward from v2. |
| AC2 | met | `tests/test_maze_invariants.py` unchanged; PASS in 21-test run. v3 also wires `is_perfect_maze` into `--debug` runtime path (`app.py:159`) for live regression checks. |
| AC3 | met | `endpoints.py` unchanged; canvas still renders A green/B red. Seed determinism (`test_cli.SeedDeterminismTests`) reproduces identical A/B across runs at the same seed, which incidentally re-confirms `pick_endpoints(rng=...)` honors its rng arg. |
| AC4 | met | `start_new_maze` (`app.py:119-152`) builds the live `Maze` once and threads it into `generate_maze(maze=live)` so the generator carves in place; same speed-slider-driven `step_active` pumps the generation events. v3 pause/step now also pauses generation, which the request explicitly requires. |
| AC5 | met | `algorithms/__init__.py` registry unchanged; `sidebar.py:96-105` shows 1..6 in spec order with 7..8 appended; `shortcuts.py` unchanged. v3 didn't touch this surface. |
| AC6 | met (fresh check) | Composite order in `canvas.render` (`:184-191`) is base → frontier → overlay → endpoints, with overlay carrying both visit (`:123-129` `mark_visit`) and path (`:149-153` `mark_path`). Since `overlay.set_at(cell, COLOR_VISITED)` writes an opaque pixel into the SRCALPHA overlay, blitting that overlay on top of the frontier surface causes the visit color to overwrite the tint at that cell on every frame — by construction, not by chance. `mark_frontier` additionally early-returns when the visit overlay's pixel at the cell is non-transparent (`:141-144`), preventing tint from re-appearing on top of a visited cell in any intermediate state. Path is painted to the same overlay (`:149-153`), so path > visit > frontier ordering holds. AC6 "every visited cell ends up in visit color (or path color if on final path)" is structurally satisfied. |
| AC7 | met | `test_optimal_parity.test_five_optimal_algos_agree` unchanged from v2 and PASS. New `StatusPanelDeterminismTests` further pins each optimal algo to a stable (visited_count, path_len) tuple per seed. |
| AC8 | met (fresh check) | `start_algorithm` (`app.py:176-202`) sets `run_gen = None`, calls `canvas.clear_overlay()` (which now also wipes the frontier layer per AC10 below), resets all counters (`visited_set`, `visited_count`, `frontier_size`, `step_events`, `path_len`), then constructs the new generator. Critically, the pause-state reset (`:196-200`: `paused = False`, `paused_from_phase = None`, `pause_pending_step = False`) is unconditional and happens AFTER the overlay/counters reset, so pause+switch_algo→new algo starts RUNNING (not paused) on a wiped canvas. Both routes (sidebar click → `on_sidebar_click("algo:N")` → `start_algorithm`, and keyboard `K_1..K_8` → `SHORTCUTS[...]` → `start_algorithm`) funnel through this single function. |
| AC9 | met (fresh check) | Slider range `[1, 60]` unchanged. `state.speed` re-read every frame at `app.py:294` (within `handle_event`) and `:514` (top of the main loop before `step_active`). Pause/step don't touch `state.speed` or `slider.value`, so a slider change made while paused is simply remembered; on resume the very next frame's `step_carry += speed * dt` uses the new value (since `step_carry` was reset to 0 by the pause branch at `:321`). "Slider change applies on the next step" semantics are preserved AND sharpened — there is no stale carry from the pre-pause speed. |
| AC10 | met (fresh check) | `on_sidebar_click("reset")` (`app.py:209-230`) cancels `run_gen` if pathfinding, clears `active_algo`, calls `canvas.clear_overlay()` (which now wipes BOTH visit/path overlay AND frontier tint per `canvas.py:96-107`), and resets all counters. Maze, start, end untouched: `state.maze` is not reassigned, `maze.start/end` remain set, and `canvas.render` re-applies the endpoint colors every frame (`canvas.py:188-191`). The pause-reset at `:227-229` ensures Reset Colors doesn't leave the visualization paused on what is now an empty canvas. Reviewer-side composite probe (independent of pygame import path) confirms after `clear_overlay`, the previously-visit-painted cell returns to `COLOR_PASSAGE` in the composite. |
| AC11 | met | `app.py:265-270` VIDEORESIZE branch re-creates the display mode and re-lays out the sidebar; `canvas.render` aspect-ratio scaling (`canvas.py:174-180`) unchanged. v3 didn't touch this surface. See Notes #1 about status-panel fit on small windows. |
| AC12 | met | No new dependencies. `cli.py` imports stdlib `argparse` only; new tests import stdlib only (`contextlib`, `io`, `random`, `unittest`). `requirements.txt` unchanged. |

## Test suite output (run by reviewer)

```
$ cd /Users/yunho/project/route-finder && PYTHONPATH=src python3 -m unittest discover -s tests -v
test_dfs_returns_valid_path (test_any_valid_path.AnyValidPathTests.test_dfs_returns_valid_path) ... ok
test_greedy_returns_valid_path (test_any_valid_path.AnyValidPathTests.test_greedy_returns_valid_path) ... ok
test_random_walk_can_return_valid_path_on_small_mazes (test_any_valid_path.AnyValidPathTests.test_random_walk_can_return_valid_path_on_small_mazes) ... ok
test_random_walk_returns_valid_path_or_none (test_any_valid_path.AnyValidPathTests.test_random_walk_returns_valid_path_or_none) ... ok
test_above_max_rejected (test_cli.CLIParseTests.test_above_max_rejected) ... ok
test_below_min_rejected (test_cli.CLIParseTests.test_below_min_rejected) ... ok
test_debug_flag (test_cli.CLIParseTests.test_debug_flag) ... ok
test_defaults_when_no_args (test_cli.CLIParseTests.test_defaults_when_no_args) ... ok
test_negative_seed_rejected (test_cli.CLIParseTests.test_negative_seed_rejected) ... ok
test_non_int_rejected (test_cli.CLIParseTests.test_non_int_rejected) ... ok
test_non_int_seed_rejected (test_cli.CLIParseTests.test_non_int_seed_rejected) ... ok
test_width_and_height (test_cli.CLIParseTests.test_width_and_height) ... ok
test_width_height_seed (test_cli.CLIParseTests.test_width_height_seed) ... ok
test_width_only (test_cli.CLIParseTests.test_width_only) ... ok
test_different_seeds_usually_differ (test_cli.SeedDeterminismTests.test_different_seeds_usually_differ)
Sanity: different seeds should produce different mazes (at least ... ok
test_same_seed_identical_maze_and_endpoints (test_cli.SeedDeterminismTests.test_same_seed_identical_maze_and_endpoints) ... ok
test_endpoints_are_non_wall (test_endpoint_constraint.EndpointConstraintTests.test_endpoints_are_non_wall) ... ok
test_endpoints_distinct_and_far (test_endpoint_constraint.EndpointConstraintTests.test_endpoints_distinct_and_far) ... ok
test_perfect_maze_invariants_across_sizes (test_maze_invariants.MazeInvariantTests.test_perfect_maze_invariants_across_sizes) ... ok
test_five_optimal_algos_agree (test_optimal_parity.OptimalParityTests.test_five_optimal_algos_agree) ... ok
test_same_seed_same_counters_across_runs (test_optimal_parity.StatusPanelDeterminismTests.test_same_seed_same_counters_across_runs) ... ok

----------------------------------------------------------------------
Ran 21 tests in 1.992s

OK
```

Matches the draft's claimed 21/21. Confirmed reproducible from a fresh shell.

## Reviewer-side determinism probe (independent of test_cli.py)

```
$ PYTHONPATH=src python3 -c "<inline reproduce of two same-seed runs>"
generate_maze sig: (width, height, rng=None, maze=None) -> Generator[...]
pick_endpoints sig: (maze, rng=None, max_tries=1000) -> tuple[tuple[int,int], tuple[int,int]]
walls equal: True
a equal: True b equal: True
```

Confirms seed=42 at 20x15 produces byte-identical `maze.walls` AND identical (A, B) across two independent invocations through the real `generate_maze`/`pick_endpoints` API. Seed plumbing through `app.py` is the same shape (`random.Random(chosen_seed)` passed to both calls), so the CLI seed flows through faithfully.

## Anti-cheat audit

- **`test_cli.py` actually parses argv.** `test_defaults_when_no_args` (`:57-62`) asserts `ns.width == DEFAULT_MAZE_W`, `ns.height == DEFAULT_MAZE_H`, `ns.seed is None`, `ns.debug is False`. Rejection cases use `_parse_expecting_exit` which captures argparse's `SystemExit` and asserts non-zero code. None of the tests are pass-by-import.
- **Seed determinism test compares byte-by-byte.** `test_same_seed_identical_maze_and_endpoints` (`:116-129`) calls `bytes(m1.walls)` and `bytes(m2.walls)` and uses `assertEqual` — that's structural byte equality, not just a length check. Also asserts `a1 == a2` and `b1 == b2`.
- **Determinism test catches more than v2.** `StatusPanelDeterminismTests.test_same_seed_same_counters_across_runs` (`:120-144`) asserts both visited count and path length match across runs — not just path length. v2 only asserted path-length parity across algos on a single run; v3 adds run-to-run determinism, which is strictly stronger.
- **`_drive_with_counters` builds a real set.** `:67-77` iterates events and adds `event[1]` to `visited` only on tag `"visit"`, mirroring `AppState.visited_count`. The reported count is the unique-cell count, not the raw event count.
- **`is_perfect_maze` is actually called in --debug branch.** `app.py:159` reads `if not is_perfect_maze(maze):` and raises on False. The import at `app.py:48` is no longer dead code.
- **Different-seeds-differ sanity test is non-trivial.** `test_different_seeds_usually_differ` (`:131-146`) tries seeds 2..7 against seed 1 and `assertTrue(differs, ...)` — if seed plumbing were broken (e.g. silently using a global Random), all six pairs would match and the test would fail.

## Amendments

None — verdict is PASS. See Notes for non-blocking observations.

## Notes (optional, non-blocking)

1. **Status panel overflow on small windows.** `ui/sidebar.py` layout puts the status panel below "Reset Colors" at y≈514 (computed manually from `layout`). With 7 lines × (~14 px line_h + 2 px gap), the panel extends to y≈624. That fits the default 720 window comfortably, but a user resizing the window down to 600 or 500 px will see the bottom of the panel get clipped by the sidebar bottom edge. Not a spec violation (AC11 only constrains the maze canvas aspect ratio, not sidebar layout), but a future pass could either truncate the panel to N visible lines or scroll. Recording for visibility.
2. **`step_active` `_update_status` is called every frame during pathfinding** even when the snapshot dict hasn't changed (`app.py:551-554`). The sidebar's `set_status_snapshot` (`:166-167`) does a dict-equality short-circuit so the cost is just one dict comparison + the dict comparison succeeds when the algo state hasn't changed. That's cheap, but a future micro-opt could skip the call entirely when no counter changed in the inner loop.
3. **Step counter `step_events` includes frontier events.** The status panel's `Steps` line shows `step_events` which is incremented on EVERY consumed event (visit + frontier + done) per `app.py:358, 424, 569`. The request explicitly says this is the raw event count "useful for users curious about IDA* re-expansions", so this is correct — flagging only because the field name `Steps` could be misread as "billed steps". Non-blocking.
4. **`active_algo` reset in `on_sidebar_click("reset")`.** v3 now clears `state.active_algo` and the sidebar's active button highlight on Reset Colors (`app.py:217-218`). This is a behavior change vs v2 (v2 left the active button highlighted). The draft documents it explicitly in the comment, and it's an improvement (status panel and sidebar are consistent after Reset), but technically the spec only says "leaves the maze and endpoints A, B intact" — clearing the algo highlight is a UX choice not mandated. No FAIL; recording for visibility.
5. **`paused_from_phase` only useful for the status string.** It's a nice touch (`Phase: paused (was pathfinding)`) but the actual phase resumption uses `state.phase` (which is preserved across pause since the dataclass field doesn't change). Future cleanup could fold the two together if desired. Non-blocking.
6. **Generation phase single-step doesn't honor a frontier-event drain.** `_consume_single_step` for `phase == "generating"` consumes exactly one `next(gen_gen)` call (`app.py:407-414`) — generation events are coarse-grained carve steps so this is fine, but worth noting the asymmetry vs pathfinding which drains frontier between billable steps. Spec is silent on generation step semantics. Non-blocking.

검토 결과 PASS. 21개 테스트가 1.992초에 모두 통과하며, 시드 결정성은 `bytes(m1.walls) == bytes(m2.walls)`와 `(a1,b1) == (a2,b2)`로 독립 재현 확인. AC6 (composite ordering으로 visit이 frontier tint를 덮음), AC8 (pause 중 알고리즘 전환 시 unpause + overlay/카운터 클리어), AC9 (slider 값은 pause 중에도 살아 있고 resume 시 step_carry=0에서 깨끗하게 적용), AC10 (Reset Colors가 visit·frontier·path 모두 클리어) 모두 신규 검증 완료.
