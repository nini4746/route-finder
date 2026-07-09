# Request v3 (UX pass)

v1, v2 shipped (review_v1.md PASS, review_v2.md PASS). This pass focuses
on **user-visible polish** so that running `python -m route_finder` on
macOS is an enjoyable visualization tool — and folds in three remaining
review_v1 notes that naturally pair with UX work.

## In scope

### UX-A. Status panel

Add a small status panel inside the sidebar (below the existing controls,
above any free space) showing the live state of the current run. Show all
of the following, each on its own line:

- **Algorithm**: current selected algo name, or `—` if idle.
- **Phase**: `generating | idle | running | done | cancelled` (mirrors the
  existing `AppState.phase` enum).
- **Visited**: count of unique cells visited so far in the current run
  (not the count of step events — unique cells).
- **Frontier**: current frontier size (queue / heap length); `—` for
  algorithms without a meaningful frontier (DFS, RWalk).
- **Steps**: total step events processed in the current run (visit +
  frontier + done, before the v2 budget-billing change is applied —
  this is the raw event count, useful for users curious about IDA*
  re-expansions).
- **Path length**: final path length once the run is `done`; `—` while
  running.
- **Maze**: `WxH (seed=S)` line showing current maze dimensions and the
  seed used to generate it (see UX-C).

The panel should re-render only when one of these values changes (avoid
per-frame text rasterization for performance). Use a monospace font.

### UX-B. Pause and step

Add keyboard shortcuts:

- **Space** — toggle pause/resume of the active run. While paused, the
  app loop still runs (window stays responsive, slider can be moved,
  algorithm can be switched, Reset Colors / New Maze still work) but
  no algorithm step is consumed.
- **`.`** (period) — single-step: advance exactly one algorithm step
  (one `visit` or `done`, ignoring `frontier` events to be consistent
  with v2 budget billing). Only meaningful while paused; while running,
  it's a no-op.

Add a tiny pause indicator in the status panel (`Phase: paused (was
running)` style) so the user knows.

While generating the maze (phase = `generating`), pause/step should
**also** work — the maze generation is paced by the same step loop.

Cancel-on-switch (AC8) still applies: switching algorithms unpause/cancels
the current run and starts the new one running (not paused).

### UX-C. CLI for width/height/seed (handles review_v1 note #2)

`python -m route_finder` currently ignores positional args. Accept up to
three positional integers in order:

```
python -m route_finder            # defaults (whatever they are now)
python -m route_finder 50         # width=50, height=default
python -m route_finder 50 30      # width=50, height=30
python -m route_finder 50 30 42   # width=50, height=30, seed=42
```

- Use `argparse` (stdlib).
- Validate against `MIN_MAZE_DIM <= w,h <= 1000`; invalid → print error,
  exit non-zero.
- Seed is optional; if absent, draw from `random.SystemRandom().randrange(2**31)`
  and **display the chosen seed in the status panel** so the user can
  reproduce a maze they liked.
- Clicking New Maze in the UI generates a fresh seed (also display it).
- Document the new CLI in the program's `--help` (argparse autogenerates).

### UX-D. Frontier visualization (handles review_v1 note #4)

Currently `canvas.mark_frontier` is a no-op. Make it a real visualization:

- Frontier cells get a **light tint** distinct from visited cells. The
  visit color stays primary; frontier is secondary, slightly translucent
  or pale. (Concrete choice: visit = solid medium-blue; frontier = pale
  blue, 50% lighter. The exact hex is your call — keep the existing
  palette aesthetic.)
- When a frontier cell becomes visited, the visit color **overwrites**
  the frontier tint (so the frontier ring shrinks visibly as the
  algorithm progresses).
- The final path overlay (highlight color) overwrites both.
- DFS, Greedy, BiBFS, IDA*, RWalk — keep their existing event protocol;
  the change is canvas-side only.
- Make this **toggleable** by key `F` (frontier on/off). Default on.
  Show the toggle state in the status panel as a single-letter flag
  (`F:on` or `F:off`) — place it on the `Frontier:` line.

AC6 invariant ("every visited cell changes color incrementally, and on
termination the final A to B path is overlaid in a distinct highlight
color") must still hold. Specifically: even with frontier tinting on,
**every visited cell must end up in the visit color** (or the path
color, if it's on the final path).

### Cleanup. review_v1 note #5

Wire `is_perfect_maze` into a debug-mode post-generation assertion. Add a
CLI flag `--debug` (off by default) that, when set, runs
`is_perfect_maze` after each New Maze and raises if the invariants fail.
This actually exercises the import and turns it into a runtime regression
check for developers.

## Out of scope for v3

- review_v1 note #6 (frame-budget last-step micro-loss) — imperceptible.
- Performance optimization beyond what's needed for status-panel re-render
  efficiency.
- New algorithms.
- Networked features. (Still stdlib + pygame only — no new dependencies.)

## Test additions

Update / add `unittest` tests:

1. **`tests/test_cli.py`** (NEW)
   - Parse the CLI with various inputs:
     - `[]` → defaults
     - `["50"]` → width=50
     - `["50", "30"]` → width=50, height=30
     - `["50", "30", "42"]` → width=50, height=30, seed=42
     - `["1"]` → error (below MIN_MAZE_DIM)
     - `["1001"]` → error (above max)
     - `["abc"]` → error (not int)
   - Test the seed plumbing: same seed must produce identical maze
     across two runs.

2. Extend **`tests/test_optimal_parity.py`** to assert that a status
   panel snapshot (or just the underlying counters) is **stable**: a
   parity run with the same seed must produce the same `visited` and
   `path length` values for each optimal algorithm across two
   invocations. (Acts as a determinism regression test.)

3. **No new test for UX-B pause** — interactive only.

4. **No new test for UX-D frontier rendering** — interactive only, but
   keep the existing tests green.

Re-run the full suite at the end and paste verbatim into `draft_v3.md`.

## Self-check requirement (in draft_v3.md)

For each of UX-A through UX-D, Cleanup, and the tests, state which
file(s) were touched and the one-line proof. Re-confirm AC1..AC12 still
met, with fresh attention on:

- **AC6**: every visited cell still ends up in visit color (frontier
  tinting must be overwritten).
- **AC8**: switch-cancel still works while paused / mid-step.
- **AC9**: speed slider still applies live; pause/step doesn't break the
  "next step" semantics.
- **AC10**: Reset Colors still leaves maze + A + B intact (and now should
  also clear frontier tint).

Use `unittest discover` and paste the run's output verbatim.
