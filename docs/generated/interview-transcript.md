# Interview Transcript

Audit trail of the `/harness-spec` interview that produced `docs/product-specs/initial-seed.yaml`. Append-only; companion hash chain at `.transcript-chain` (one line per Phase 2 round).

## Phase 1 Metadata Batch

Q1: Project name — is `route-finder` correct?
A1: 맞음 (yes, `route-finder`).

Q2: Tech stack — Python / Node / Go / Rust / recommend?
A2: "c나 파이썬" — C or Python, deferring final choice until the goal is locked.

Q3: AI agents in use?
A3: 클로드만 (Claude Code only).

Q4: Reference libraries needing `llms.txt`?
A4: 없음 (none).

Q5: Team size?
A5: 혼자 (1).

## Phase 2-1 Goal

Round 1:
  Q: One-sentence goal. What is `route-finder`?
  A (user, verbatim): "미로만드는 알고리즘으로 미로 생성 -> 이를 기반으로 시각화된 여러 길찾기 알고리즘을 통해서 a -> b로 이동하는 프로그램 이동한 길은 모두 색깔이 변해야함"
  Restate: "A program that generates a random maze via a maze-generation algorithm, then visualizes several pathfinding algorithms moving from A to B with every traversed cell changing color."
  Tech-stack recommendation (Phase 1 callback): Python + pygame primary; C + raylib alternative.
  User: "잠그고 파이썬" — locked the restate, picked Python.
  Locked goal (English): A macOS pygame desktop program that generates random perfect mazes up to 1000x1000 cells with the DFS Backtracker algorithm and then visualizes six pathfinding algorithms one at a time finding a path from a randomly chosen point A to point B, coloring every visited cell as the search progresses.
  Note: the locked goal sentence was refined incrementally as later Phase 2 slots resolved scope. The final form above is what landed in `initial-seed.yaml`.

## Phase 2-2 Constraints

Round 1:
  Q: What constraints / requirements does this program have? (Open prompt across dependencies, OS, maze size, algorithm coverage, interaction, speed.)
  A: "의존성 제한은 추천대로 지원 os는 맥에서만 일단 되게 미로 크기는 100000 100000까지도 가능할수도 있도록 길찾기 알고리즘은 최대한 여러가지로 생성 알고리즘은 나한테 나중에 페이즈로 해서 물어봐줘 인터렉션은 마우스클릭으로 미로 생성 그후 길찾기 알고리즘 선택이 가능해서 같은 미로에서 여러 알고리즘의 차이를 시각화 그런게 모두 가능하게 속도는 조절 가능하면 좋겠음"
  Ledger (full state after this answer):
    - Python stdlib + pygame only [verified]
    - macOS only [verified]
    - maze size up to 100000x100000 [hand-wavy — physically infeasible at 10^10 cells]
    - pathfinding algorithms "as many as possible" [hand-wavy]
    - maze generation algorithms: deferred by user [TBD, tracked in ledger]
    - mouse click triggers maze generation [hand-wavy]
    - algorithm selection UI [hand-wavy]
    - same-maze multi-algorithm comparison [hand-wavy]
    - speed adjustment [hand-wavy]
    - A/B endpoint selection mechanism [missing]
  Stall counter: 0

Round 2:
  Q: Is 100000x100000 cells (10 billion cells, ~10 GB just for the grid) really intended, or did you mean a smaller upper bound? (Four options: realistic cap, visualization limit, downsampled big maze, custom.)
  A: "1000 1000 근처까지 되도록 그럼"
  Ledger:
    - Python stdlib + pygame only [verified]
    - macOS only [verified]
    - maze size up to ~1000x1000 cells [verified]
    - pathfinding algorithms "as many as possible" [hand-wavy]
    - maze generation algorithms: deferred [TBD]
    - mouse click triggers maze generation [hand-wavy]
    - algorithm selection UI [hand-wavy]
    - same-maze multi-algorithm comparison [hand-wavy]
    - speed adjustment [hand-wavy]
    - A/B endpoint selection [missing]
  Stall counter: 0

Round 3:
  Q: "As many algorithms as possible" is not measurable. Choose: (1) explicit list of algorithm names, or (2) category + minimum count.
  A: "최소 적힌 애들은 모두 구현해야하고 추가로 2개 이상 더 구현 해주면 좋겠다는 희망사항으로" — required = the six examples (BFS, DFS, Dijkstra, A*, Greedy Best-First, Bidirectional BFS); stretch = at least two more.
  Ledger:
    - Python stdlib + pygame only [verified]
    - macOS only [verified]
    - maze size up to ~1000x1000 cells [verified]
    - required pathfinders: BFS, DFS, Dijkstra, A*, Greedy Best-First, Bidirectional BFS [verified]
    - stretch: at least 2 additional pathfinders [verified]
    - maze generation algorithms: deferred [TBD]
    - mouse click triggers maze generation [hand-wavy]
    - algorithm selection UI [hand-wavy]
    - same-maze multi-algorithm comparison [hand-wavy]
    - speed adjustment [hand-wavy]
    - A/B endpoint selection [missing]
  Stall counter: 0

Round 4:
  Q: How are start A and end B chosen? (Five options: two clicks, drag, default-plus-manual, random, custom — plus wall-cell tiebreaker subquestion.)
  A: "랜덤, 이거면 아래거 생각 안해도 되지 않나? 벽 아닌곳에 랜덤으로 찍어야지" — random; only from non-wall cells.
  Ledger:
    - (previous verified entries retained)
    - A/B are randomly chosen from non-wall cells, A != B [verified]
    - mouse click triggers maze generation [hand-wavy]
    - algorithm selection UI [hand-wavy]
    - same-maze multi-algorithm comparison [hand-wavy]
    - speed adjustment [hand-wavy]
  Stall counter: 0

Round 5:
  Q: How should multi-algorithm comparison be visualized? (Sequential / side-by-side / overlay / both.)
  A: "그리고 a , b간 최소거리도 좀 있었으면 좋겠는데 그리고 시각화는 내가 선택했을때 움직이도록 순차랑 비슷하긴 한데 바뀌는 시점과 알고리즘 선택기준은 사용자임" — sequential, on-demand triggered by user's algorithm pick; user also requests a minimum A-B distance.
  Ledger:
    - (previous verified entries retained)
    - visualization mode = sequential on-demand; one algorithm at a time; same maze + same A,B persist [verified]
    - A,B minimum distance required [hand-wavy — metric and threshold]
    - mouse click triggers maze generation [hand-wavy]
    - algorithm selection UI [hand-wavy]
    - speed adjustment [hand-wavy]
  Stall counter: 0

Round 6:
  Q: How to measure the A-B distance? (Manhattan / actual maze path / Euclidean.)
  A: "1인데 미로의 모든길은 이어져 있어야 함" — Manhattan; and adds: all passages must be connected.
  Ledger:
    - (previous verified entries retained)
    - A,B distance metric = Manhattan [verified]
    - maze is fully connected = perfect maze (zero cycles, all passages reachable) [verified]
    - A,B distance threshold value [hand-wavy]
    - mouse click triggers maze generation [hand-wavy]
    - algorithm selection UI [hand-wavy]
    - speed adjustment [hand-wavy]
  Stall counter: 0

Round 7:
  Q: Manhattan threshold value? (a) (w+h)*0.5, (b) (w+h)*0.3, (c) max(w,h)*0.5, (d) absolute N.
  A: "a"
  Ledger:
    - (previous verified entries retained)
    - A,B Manhattan distance >= (width+height)*0.5 [verified]
    - mouse click triggers maze generation [hand-wavy]
    - algorithm selection UI [hand-wavy]
    - speed adjustment [hand-wavy]
  Stall counter: 0

Round 8:
  Q: UI/interaction default proposal — sidebar with New Maze button, algorithm buttons 1..6, speed slider [1..60], Reset Colors, auto-scaling canvas; lock or amend?
  A: "잠그죠?" — lock.
  Ledger:
    - (previous verified entries retained)
    - UI: sidebar with New Maze, six algorithm buttons + shortcuts 1..6, speed slider [1..60] steps/sec, Reset Colors [verified]
    - selecting another algorithm mid-run cancels + resets colors + starts new one [verified]
    - same maze + same A,B persist across runs until New Maze [verified]
    - canvas auto-scales to window, preserving aspect ratio [verified]
    - maze generation algorithm choice [TBD — promised to user as next question]
  Stall counter: 0

Round 9:
  Q: Maze generation algorithm — single or multiple? Six candidate algorithms presented with passage character (DFS Backtracker, Prim's, Kruskal's, Wilson's, Recursive Division, Eller's). Also: animate generation or not?
  A: "길이 갈라지되 갈라진 길이 자주 합쳐지지 않았으면 좋겠음" — branchy passages that do not rejoin often (= perfect maze, already locked; clarification needed).
  Skill response: pointed out that "passages not rejoining" is equivalent to the already-locked perfect-maze invariant; proposed DFS Backtracker as best match for "branchy but not over-branching, long corridors + dead ends".
  Ledger:
    - (previous verified entries retained)
    - maze generation: DFS Backtracker (proposed) [pending confirm]
    - animate generation: not yet confirmed [hand-wavy]
  Stall counter: 0

Round 10:
  Q (follow-up): With "all passages connected" already locked, all listed candidates qualify; the constraint does not narrow the set further. Lock DFS Backtracker as the single generator? Show generation animation or not?
  A: "또한 모든길이 이어져야함 이거까지 반영하면 뭐뭐남아" — meta-question about candidate filtering; skill explained equivalence with perfect-maze invariant.
  Continued same round.
  Final user answer: "dfs, 보여줌 ㄱ" — DFS Backtracker, with step-by-step generation animation.
  Ledger:
    - (previous verified entries retained)
    - maze generation = DFS Backtracker (single) [verified]
    - maze generation animates step-by-step at speed slider [verified]
  Stall counter: 0
  Slot 2-2 complete: every entry verifiable.

## Phase 2-3 Acceptance Criteria

Round 1:
  Q: Twelve AC candidates were synthesized from the locked ledger as measurable predicates (AC1..AC12). Confirm or amend?
  A: "ㄱㄱ" — accept all 12.
  Ledger:
    - AC1 launch + perfect maze rendered [verified — pygame window check + AC2 invariant]
    - AC2 perfect-maze invariants (BFS connectivity + edge count == cells - 1) [verified]
    - AC3 A,B distinct non-wall, Manhattan >= (w+h)*0.5, green/red colors [verified]
    - AC4 New Maze regenerates + animates + re-randomizes + clears [verified]
    - AC5 six algorithms + shortcuts 1..6 [verified]
    - AC6 visited color change + final path highlight [verified]
    - AC7 BFS/Dijkstra/A*/Bi-BFS equal path length; DFS/Greedy any valid path [verified]
    - AC8 mid-run switch cancels + resets + starts new [verified]
    - AC9 slider [1,60] live applied [verified]
    - AC10 Reset Colors preserves maze + endpoints [verified]
    - AC11 window resize auto-scales preserving aspect [verified]
    - AC12 pip list shows only pygame + stdlib; zero runtime network [verified]
  Stall counter: 0

## Phase 2-4 Ontology

Round 1:
  Q: Five domain entities derived from the locked ledger (Cell, Maze, Algorithm, PathfindingRun, AppState) with explicit field schemas and AC coverage map. Confirm or amend?
  A: "ㄱㄱ" — accept.
  Ledger:
    - Cell { x, y, is_wall } [verified — referenced by AC3, AC6]
    - Maze { width, height, cells, start, end } [verified — referenced by AC1, AC2, AC4]
    - Algorithm { name, kind, step } [verified — referenced by AC5, AC7, AC8]
    - PathfindingRun { maze, algorithm, visited, frontier, path, status } [verified — referenced by AC6, AC8, AC10]
    - AppState { maze, run, speed, phase } [verified — referenced by AC8, AC9]
  Stall counter: 0

## Phase 2-5 Team Architecture

Round 1:
  Q: team_size=1, goal has no inherent parallel workstreams. Skip-rule proposal: single-agent `subagent` mode. Confirm or request a team?
  A: "팀만들고 싶으면 만들어 상관없음" — delegated choice to the skill.

Round 2:
  Q: Concrete proposal — 2-agent `producer_reviewer` pattern, agents `builder` and `reviewer`, data_flow `files`. Lock?
  A: "ㄱㄱ" — lock.
  Final team_architecture:
    - execution_mode: team
    - pattern: producer_reviewer
    - agents: [builder, reviewer]
    - data_flow: files

## Phase 3 Self-Check

Coverage map (each ontology entity tied to AC by verb):

- Cell ← AC3: writes (renders A green, B red, both on non-wall cells)
- Cell ← AC6: writes (color update per visited cell)
- Maze ← AC1: creates (launch renders a perfect maze)
- Maze ← AC2: validates (BFS connectivity + cycle test)
- Maze ← AC4: regenerates (New Maze rebuilds with DFS Backtracker)
- Algorithm ← AC5: enumerates (six selectable + shortcuts 1..6)
- Algorithm ← AC7: compares (path length equivalence across optimal pathfinders)
- Algorithm ← AC8: switches (selecting another cancels current run)
- PathfindingRun ← AC6: appends (visited set grows incrementally; path populated on termination)
- PathfindingRun ← AC8: cancels (status -> cancelled on mid-run switch)
- PathfindingRun ← AC10: resets (visited and path cleared, maze and endpoints intact)
- AppState ← AC9: mutates (speed slider live updates AppState.speed)
- AppState ← AC8: tracks (AppState.run holds the active PathfindingRun)

Checks:

- AC measurability: PASS — every AC1..AC12 is a yes/no- or numeric-checkable predicate.
- Constraint verifiability: PASS — every constraint is yes/no checkable (dependency check, OS check, size bounds, perfect-maze invariants, equality of optimal path lengths, etc.).
- Ontology coverage: PASS — every entity in `ontology_schema` is referenced by at least one AC via a concrete verb (above).
- External service hygiene: NA — no AC references an external service, HTTP API, OAuth provider, or database server.
- Goal sentence form: PASS — one concrete sentence.
- team_architecture consistency: PASS — `execution_mode=team` + `pattern=producer_reviewer` + `agents.length=2`; both agent names unique; both roles distinct; `data_flow=files` present.

No retry needed.

## Open Questions

(none — Phase 3 passed without retry.)
