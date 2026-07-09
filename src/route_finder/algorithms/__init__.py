"""Pathfinding algorithms behind a common step() generator interface."""

from .common import Algorithm, Event, build_path_event
from .bfs import bfs
from .dfs import dfs
from .dijkstra import dijkstra
from .astar import astar
from .greedy_bf import greedy_best_first
from .bi_bfs import bidirectional_bfs
from .ida_star import ida_star
from .random_walk import random_walk

# Number key -> Algorithm.
#
# Indices 1..6 are the SPEC-MANDATED order (AC5):
#   1=BFS 2=DFS 3=Dijkstra 4=A* 5=GreedyBF 6=BiBFS
# Do NOT renumber 1..6 or change their meaning.
#
# Indices 7..8 are stretch-goal additions (request_v2 §B):
#   7=IDA* 8=RWalk
# Buttons and key shortcuts append; the required-six order is untouched.
REGISTRY: dict[int, Algorithm] = {
    1: Algorithm(name="BFS", kind="uninformed", step=bfs),
    2: Algorithm(name="DFS", kind="uninformed", step=dfs),
    3: Algorithm(name="Dijkstra", kind="uninformed", step=dijkstra),
    4: Algorithm(name="AStar", kind="informed", step=astar),
    5: Algorithm(name="GreedyBF", kind="informed", step=greedy_best_first),
    6: Algorithm(name="BiBFS", kind="bidirectional", step=bidirectional_bfs),
    7: Algorithm(name="IDA*", kind="informed", step=ida_star),
    8: Algorithm(name="RWalk", kind="uninformed", step=random_walk),
}

__all__ = [
    "Algorithm",
    "Event",
    "REGISTRY",
    "build_path_event",
    "bfs",
    "dfs",
    "dijkstra",
    "astar",
    "greedy_best_first",
    "bidirectional_bfs",
    "ida_star",
    "random_walk",
]
