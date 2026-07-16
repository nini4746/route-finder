# route-finder

랜덤 미로 위에서 여러 길찾기 알고리즘이 A → B 경로를 찾아가는 과정을 시각화하는 macOS pygame-ce 데스크톱 프로그램.

## 무엇을 보여주나

- DFS Backtracker로 생성된 **perfect maze**(모든 통로가 이어지고 사이클이 없음). 생성 과정도 한 칸씩 애니메이션으로 표시.
- 같은 미로 · 같은 A · 같은 B 위에서 6가지 길찾기 알고리즘을 **순차로** 비교:
  - BFS, DFS, Dijkstra, A*, Greedy Best-First, Bidirectional BFS
- 알고리즘이 방문하는 칸은 색이 점진적으로 바뀌고, 종료 시 최종 경로가 하이라이트 색으로 덮어 그려짐.

## 설치 (macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pygame-ce
```

> 의존성은 `pygame-ce` 단 하나 + 파이썬 표준 라이브러리. (import 는 `pygame` 이름 그대로 - pygame-ce 가 동일 모듈을 제공.) 다른 패키지를 추가로 깔지 마세요.

## 실행

```bash
python -m route_finder
```

## 조작

| 입력                        | 동작                                                          |
| --------------------------- | ------------------------------------------------------------- |
| 사이드바 `New Maze` 클릭    | 새 미로 생성 (DFS Backtracker, 애니메이션) → A·B 재배치 → 색 리셋 |
| 사이드바 알고리즘 버튼 클릭 | 해당 알고리즘 즉시 시작                                       |
| 키보드 `1` ~ `6`            | 알고리즘 단축키 (1=BFS, 2=DFS, 3=Dijkstra, 4=A*, 5=Greedy BF, 6=Bi-BFS) |
| 속도 슬라이더 (1 ~ 60)      | 한 초당 step 수 — 실행 중에도 즉시 반영                       |
| 사이드바 `Reset Colors` 클릭 | 미로·A·B는 유지, 방문/경로 색만 초기화                        |
| 창 리사이즈                 | 캔버스가 비율 유지하며 자동 스케일                            |

## 색상

- A (시작점): 녹색
- B (도착점): 빨강
- 방문(visited) 셀: 옅은 색
- 최종 경로: 강조 색

## 미로 크기

`1 ≤ width ≤ 1000`, `1 ≤ height ≤ 1000`. A와 B 사이 맨해튼 거리는 항상 `(width + height) × 0.5` 이상이 되도록 자동 보장됩니다.

## 프로젝트 구조

자세한 구조는 `ARCHITECTURE.md`를 보세요. 명세의 원본은 `docs/product-specs/initial-seed.yaml`이며, 다른 문서들은 모두 이 YAML에서 파생된 렌더입니다. 명세를 바꾸려면 YAML을 수정한 뒤 `/harness-spec --rerender`로 다시 렌더하세요.

## 에이전트 협업

이 저장소는 Claude Code 기반 2-에이전트 `producer_reviewer` 패턴(`builder` + `reviewer`)으로 설계되어 있습니다. 에이전트 인프라(`.claude/agents/`, `.claude/skills/`)를 실제로 생성하려면 `/harness-build`를 실행하세요. 단일 사람이 직접 개발하는 경우엔 무시해도 됩니다 — 문서는 단독 개발자도 그대로 읽고 따라가도록 작성되어 있습니다.
